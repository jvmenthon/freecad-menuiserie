# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contrôles des octets d'une image avant décodage (audit de sécurité J1d, point 1 : JPEG aux
milliers de balayages ; point 4 : bombe de décompression PNG)."""

from __future__ import annotations

import struct
import zlib

import pytest

from freecad.menuiserie.core.image_checks import (
    INVALID_PNG,
    MAX_JPEG_SCANS,
    PNG_DATA_TOO_LARGE,
    TOO_MANY_SCANS,
    check_image_bytes,
    check_jpeg,
    check_png,
    jpeg_scan_count,
    png_header,
    png_raw_size,
)
from freecad.menuiserie.core.texture_file import TextureRefusedError

SIDE = 4096
ADAM7 = [
    (0, 0, 8, 8),
    (4, 0, 8, 8),
    (0, 4, 4, 8),
    (2, 0, 4, 4),
    (0, 2, 2, 4),
    (1, 0, 2, 2),
    (0, 1, 1, 2),
]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def segment(marker: int, payload: bytes) -> bytes:
    """Segment JPEG : marqueur ``FF xx``, longueur sur deux octets (comprise), contenu."""
    return bytes((0xFF, marker)) + struct.pack(">H", len(payload) + 2) + payload


def progressive_jpeg(scans: int, entropy: bytes = b"\x7f\xfe\xff\x00\xfd\xff\x00") -> bytes:
    """JPEG progressif en niveaux de gris de 4 096 sur 4 096 pixels annoncés, fait de ``scans``
    balayages de raffinement presque vides (comme celui de l'audit) ; les octets ``FF`` des
    données compressées sont suivis de ``00``, comme l'impose la norme."""
    frame = struct.pack(">BHHB", 8, SIDE, SIDE, 1) + bytes((1, 0x11, 0))
    table = bytes((0x10,)) + bytes(16) + bytes(1)
    scan = segment(0xDA, bytes((1, 1, 0x00, 1, 63, 0x10))) + entropy
    return (
        b"\xff\xd8"
        + segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
        + segment(0xDB, bytes(65))
        + segment(0xC2, frame)
        + segment(0xC4, table)
        + scan * scans
        + b"\xff\xd9"
    )


def test_balayages_comptes_exactement() -> None:
    assert jpeg_scan_count(progressive_jpeg(1000)) == 1000


@pytest.mark.parametrize("scans", [1, 10, MAX_JPEG_SCANS])
def test_jpeg_progressif_ordinaire_accepte(scans: int) -> None:
    check_jpeg(progressive_jpeg(scans))
    check_image_bytes(progressive_jpeg(scans), "jpeg")


@pytest.mark.parametrize("scans", [MAX_JPEG_SCANS + 1, 10_000])
def test_jpeg_aux_balayages_innombrables_refuse(scans: int) -> None:
    with pytest.raises(TextureRefusedError) as raised:
        check_image_bytes(progressive_jpeg(scans), "jpeg")
    assert raised.value.reason == TOO_MANY_SCANS
    assert raised.value.params == {"count": str(scans), "max": str(MAX_JPEG_SCANS)}


def test_octets_ff_bourres_non_comptes() -> None:
    """``FF 00`` (octet ``FF`` des données) et ``FF D0`` à ``FF D7`` (redémarrages) ne sont pas
    des débuts de balayage."""
    restarts = b"".join(bytes((0xFF, marker)) for marker in range(0xD0, 0xD8))
    data = progressive_jpeg(1, entropy=(b"\xff\x00" + restarts) * 1000)
    assert jpeg_scan_count(data) == 1
    check_jpeg(data)


def test_controle_rapide_sur_16_mio() -> None:
    """Le compte se fait en une passe sur les octets, sans décodage."""
    data = progressive_jpeg(MAX_JPEG_SCANS, entropy=bytes(16 * 1024 * 1024 // MAX_JPEG_SCANS))
    check_jpeg(data)


def test_format_sans_controle_de_balayages() -> None:
    """Le contrôle JPEG ne s'applique pas au PNG ni à un format inconnu."""
    check_image_bytes(b"\xff\xda" * (MAX_JPEG_SCANS + 1), "bmp")


# --- Point 4 : bombe de décompression PNG -----------------------------------------------------


def chunk(kind: bytes, payload: bytes) -> bytes:
    """Bloc PNG : longueur, type, contenu, CRC."""
    crc = struct.pack(">I", zlib.crc32(kind + payload))
    return struct.pack(">I", len(payload)) + kind + payload + crc


def png(
    size: tuple[int, int],
    idat: bytes | list[bytes],
    *,
    color: tuple[int, int] = (2, 8),
    interlace: int = 0,
    after_end: bytes = b"",
) -> bytes:
    """PNG fabriqué : en-tête ``size`` (type de couleur, profondeur), blocs ``IDAT`` donnés."""
    color_type, depth = color
    header = struct.pack(">IIBBBBB", *size, depth, color_type, 0, 0, interlace)
    blocks = idat if isinstance(idat, list) else [idat]
    return (
        PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + b"".join(chunk(b"IDAT", block) for block in blocks)
        + chunk(b"IEND", b"")
        + after_end
    )


def zeros_compressed(size: int) -> bytes:
    """``size`` octets nuls compressés par zlib, sans les tenir en mémoire d'un bloc."""
    compressor = zlib.compressobj(9)
    step = 1 << 20
    parts = [compressor.compress(bytes(min(step, size - done))) for done in range(0, size, step)]
    return b"".join(parts) + compressor.flush()


def reference_raw_size(width: int, height: int, bits_per_pixel: int, interlaced: bool) -> int:
    """Taille brute calculée pixel par pixel (indépendante de ``png_raw_size``)."""
    passes = ADAM7 if interlaced else [(0, 0, 1, 1)]
    total = 0
    for x0, y0, dx, dy in passes:
        columns = len(range(x0, width, dx))
        rows = len(range(y0, height, dy))
        if columns and rows:
            total += rows * (1 + (columns * bits_per_pixel + 7) // 8)
    return total


@pytest.mark.parametrize(
    ("size", "color", "expected"),
    [
        ((1, 1), (2, 8), 4),
        ((3, 2), (0, 1), 4),
        ((64, 32), (6, 16), 32 * (1 + 64 * 8)),
        ((4096, 4096), (2, 8), 4096 * (1 + 4096 * 3)),
    ],
)
def test_taille_brute_sans_entrelacement(
    size: tuple[int, int], color: tuple[int, int], expected: int
) -> None:
    header = png_header(png(size, b"", color=color)[16:29])
    assert png_raw_size(header) == expected


@pytest.mark.parametrize("width", [1, 2, 3, 5, 7, 8, 9, 63, 4096])
@pytest.mark.parametrize("height", [1, 2, 4, 5, 8, 17])
@pytest.mark.parametrize("color", [(0, 1), (3, 4), (2, 8), (6, 16)])
def test_taille_brute_adam7(width: int, height: int, color: tuple[int, int]) -> None:
    channels = {0: 1, 3: 1, 2: 3, 6: 4}[color[0]]
    header = png_header(png((width, height), b"", color=color, interlace=1)[16:29])
    assert header.interlaced
    expected = reference_raw_size(width, height, channels * color[1], True)
    assert png_raw_size(header) == expected


def test_bombe_idat_refusee() -> None:
    """PNG de 1 pixel dont l'IDAT se décompresse en 64 Mio de zéros (la bombe de l'audit en
    fait 2 Gio) : refusé après 5 octets décompressés."""
    with pytest.raises(TextureRefusedError) as raised:
        check_image_bytes(png((1, 1), zeros_compressed(64 << 20)), "png")
    assert raised.value.reason == PNG_DATA_TOO_LARGE
    assert raised.value.params == {"size": "4"}


@pytest.mark.parametrize("interlace", [0, 1])
@pytest.mark.parametrize("blocks", [1, 7])
def test_donnees_exactes_acceptees_un_octet_de_plus_refuse(interlace: int, blocks: int) -> None:
    size = (13, 11)
    raw = bytes(reference_raw_size(*size, 24, interlace == 1))
    for data, refused in ((raw, False), (raw + b"\0", True)):
        compressed = zlib.compress(data)
        step = -(-len(compressed) // blocks)
        parts = [compressed[i : i + step] for i in range(0, len(compressed), step)]
        image = png(size, parts, interlace=interlace)
        if refused:
            with pytest.raises(TextureRefusedError, match="décompressées"):
                check_png(image)
        else:
            check_png(image)


def test_donnees_plus_courtes_laissees_au_decodeur() -> None:
    """Moins de données qu'annoncé ne coûte rien : le décodeur Qt tranchera."""
    check_png(png((4096, 4096), zlib.compress(b"")))


def test_octets_apres_iend_ignores() -> None:
    check_png(png((1, 1), zlib.compress(bytes(4)), after_end=b"\xff" * 100))


def test_blocs_auxiliaires_ignores() -> None:
    raw = zlib.compress(bytes(4))
    image = png((1, 1), raw)
    text = chunk(b"tEXt", b"Comment\x00bois")
    with_text = image[:33] + text + image[33:]
    check_png(with_text)


def corrupted(data: bytes, offset: int, value: bytes) -> bytes:
    return data[:offset] + value + data[offset + len(value) :]


VALID = png((1, 1), zlib.compress(bytes(4)))


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"", id="vide"),
        pytest.param(b"GIF89a" + VALID[6:], id="sans-signature"),
        pytest.param(VALID[:20], id="en-tete-tronque"),
        pytest.param(VALID[:-20], id="idat-tronque"),
        pytest.param(PNG_SIGNATURE, id="signature-seule"),
        pytest.param(PNG_SIGNATURE + chunk(b"IDAT", b""), id="idat-avant-ihdr"),
        pytest.param(corrupted(VALID, 8, b"\x00\x00\x00\x0c"), id="ihdr-court"),
        pytest.param(png((0, 1), b""), id="largeur-nulle"),
        pytest.param(png((1, 1), b"", color=(2, 4)), id="profondeur-invalide"),
        pytest.param(png((1, 1), b"", color=(5, 8)), id="type-de-couleur-inconnu"),
        pytest.param(png((1, 1), b"", interlace=2), id="entrelacement-inconnu"),
        pytest.param(png((1, 1), b"pas du zlib"), id="zlib-invalide"),
        pytest.param(corrupted(VALID, 33, b"\xff\xff\xff\xff"), id="longueur-geante"),
    ],
)
def test_png_mal_forme_refuse(data: bytes) -> None:
    with pytest.raises(TextureRefusedError) as raised:
        check_image_bytes(data, "png")
    assert raised.value.reason == INVALID_PNG
