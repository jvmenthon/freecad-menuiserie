# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contrôles des octets d'une image de texture avant son décodage (ADR 0004, audit de sécurité).

Python pur, sans FreeCAD ni Qt : chaque format a sa fonction de contrôle, qui lève
``TextureRefusedError`` pour un contenu dont le décodage coûterait sans commune mesure avec
l'image annoncée. Les dimensions sont bornées ailleurs (en-tête lu par Qt).

- JPEG : un JPEG progressif peut enchaîner des milliers de balayages vides, chacun relu sur toute
  l'image par le décodeur (≈ 2 ms par balayage à 4 096 sur 4 096 pixels) ; au-delà de
  ``MAX_JPEG_SCANS`` marqueurs de début de balayage (``FF DA``), l'image est refusée. Le compte
  est exact sur les données compressées (un octet ``FF`` y est toujours suivi de ``00``) et ne
  peut que surestimer si un segment de métadonnées contient ces deux octets.
- PNG : quelques Mio de blocs ``IDAT`` peuvent se décompresser en Gio de zéros (« bombe ») ; les
  blocs sont parcourus et les données décompressées par morceaux, sans les garder, jusqu'à la
  taille brute exacte annoncée par l'en-tête ``IHDR`` (dimensions, profondeur, type de couleur,
  entrelacement Adam7 compris) plus un octet : au-delà, l'image est refusée.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.texture_file import TextureRefusedError

__all__ = [
    "INVALID_PNG",
    "MAX_JPEG_SCANS",
    "PNG_DATA_TOO_LARGE",
    "TOO_MANY_SCANS",
    "PngHeader",
    "check_image_bytes",
    "check_jpeg",
    "check_png",
    "jpeg_scan_count",
    "png_header",
    "png_raw_size",
]

MAX_JPEG_SCANS: Final = 100
_START_OF_SCAN: Final = b"\xff\xda"

TOO_MANY_SCANS: Final = QT_TRANSLATE_NOOP("Menuiserie", "JPEG en {count} balayages, {max} au plus")
INVALID_PNG: Final = QT_TRANSLATE_NOOP("Menuiserie", "blocs ou données PNG invalides")
PNG_DATA_TOO_LARGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "données PNG décompressées au-delà des {size} octets de l'image annoncée"
)

_PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
_CHUNK_HEADER: Final = struct.Struct(">I4s")
_CHUNK_CRC_BYTES: Final = 4
_MAX_CHUNK_LENGTH: Final = 2**31 - 1
_IHDR: Final = struct.Struct(">IIBBBBB")
# Type de couleur → (composantes par pixel, profondeurs autorisées), norme PNG § 11.2.2.
_COLOR_TYPES: Final[Mapping[int, tuple[int, frozenset[int]]]] = {
    0: (1, frozenset({1, 2, 4, 8, 16})),
    2: (3, frozenset({8, 16})),
    3: (1, frozenset({1, 2, 4, 8})),
    4: (2, frozenset({8, 16})),
    6: (4, frozenset({8, 16})),
}
_NOT_INTERLACED: Final = ((0, 0, 1, 1),)
# Passes Adam7 : (colonne de départ, ligne de départ, pas en colonnes, pas en lignes).
_ADAM7: Final = (
    (0, 0, 8, 8),
    (4, 0, 8, 8),
    (0, 4, 4, 8),
    (2, 0, 4, 4),
    (0, 2, 2, 4),
    (1, 0, 2, 2),
    (0, 1, 1, 2),
)
_BITS_PER_BYTE: Final = 8
_INFLATE_STEP: Final = 1 << 20  # octets décompressés par appel, aussitôt oubliés


def jpeg_scan_count(data: bytes) -> int:
    """Nombre de marqueurs de début de balayage (``FF DA``) dans les octets d'un JPEG."""
    return data.count(_START_OF_SCAN)


def check_jpeg(data: bytes) -> None:
    """Refuse un JPEG de plus de ``MAX_JPEG_SCANS`` balayages."""
    count = jpeg_scan_count(data)
    if count > MAX_JPEG_SCANS:
        raise TextureRefusedError(TOO_MANY_SCANS, {"count": str(count), "max": str(MAX_JPEG_SCANS)})


@dataclass(frozen=True)
class PngHeader:
    """En-tête ``IHDR`` utile au calcul de la taille brute de l'image."""

    width: int
    height: int
    bits_per_pixel: int
    interlaced: bool


def png_header(payload: bytes | memoryview) -> PngHeader:
    """En-tête lu dans le contenu du bloc ``IHDR`` ; ``TextureRefusedError`` s'il est invalide."""
    if len(payload) != _IHDR.size:
        raise TextureRefusedError(INVALID_PNG)
    width, height, depth, color_type, compression, filtering, interlace = _IHDR.unpack(payload)
    channels, depths = _COLOR_TYPES.get(color_type, (0, frozenset()))
    valid = width > 0 and height > 0 and depth in depths and compression == filtering == 0
    if not valid or interlace not in (0, 1):
        raise TextureRefusedError(INVALID_PNG)
    return PngHeader(width, height, channels * depth, interlace == 1)


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def png_raw_size(header: PngHeader) -> int:
    """Taille exacte des données décompressées : pour chaque passe (une seule sans
    entrelacement, sept en Adam7), une ligne = un octet de filtre + ses pixels arrondis à
    l'octet."""
    total = 0
    for column, row, column_step, row_step in _ADAM7 if header.interlaced else _NOT_INTERLACED:
        columns = _ceil_div(header.width - column, column_step)
        rows = _ceil_div(header.height - row, row_step)
        if columns > 0 and rows > 0:
            total += rows * (1 + _ceil_div(columns * header.bits_per_pixel, _BITS_PER_BYTE))
    return total


def _png_chunks(data: bytes) -> Iterator[tuple[bytes, memoryview]]:
    """Blocs (type, contenu) jusqu'à ``IEND`` ou la fin des octets ; ``TextureRefusedError``
    si la signature manque ou si un bloc est tronqué."""
    if not data.startswith(_PNG_SIGNATURE):
        raise TextureRefusedError(INVALID_PNG)
    view, offset = memoryview(data), len(_PNG_SIGNATURE)
    while offset < len(data):
        if offset + _CHUNK_HEADER.size > len(data):
            raise TextureRefusedError(INVALID_PNG)
        length, kind = _CHUNK_HEADER.unpack_from(data, offset)
        start = offset + _CHUNK_HEADER.size
        offset = start + length + _CHUNK_CRC_BYTES
        if length > _MAX_CHUNK_LENGTH or offset > len(data):
            raise TextureRefusedError(INVALID_PNG)
        if kind == b"IEND":
            return
        yield kind, view[start : start + length]


def _inflates_beyond(compressed: Iterable[memoryview], limit: int) -> bool:
    """Vrai si le flux zlib ``compressed`` se décompresse en plus de ``limit`` octets ; jamais
    plus de ``limit + 1`` octets ne sont produits, par morceaux aussitôt oubliés."""
    inflater = zlib.decompressobj()
    produced = 0
    for chunk in compressed:
        pending: bytes | memoryview = chunk
        while not inflater.eof:
            wanted = min(_INFLATE_STEP, limit + 1 - produced)
            output = inflater.decompress(pending, wanted)
            produced += len(output)
            if produced > limit:
                return True
            pending = inflater.unconsumed_tail
            if not pending and len(output) < wanted:  # entrée épuisée, rien en attente
                break
    return False


def check_png(data: bytes) -> None:
    """Refuse un PNG mal formé ou dont les blocs ``IDAT`` se décompressent au-delà de la taille
    brute annoncée par son en-tête (bombe de décompression)."""
    chunks = _png_chunks(data)
    kind, payload = next(chunks, (b"", memoryview(b"")))
    if kind != b"IHDR":
        raise TextureRefusedError(INVALID_PNG)
    limit = png_raw_size(png_header(payload))
    try:
        too_large = _inflates_beyond((body for name, body in chunks if name == b"IDAT"), limit)
    except zlib.error as error:
        raise TextureRefusedError(INVALID_PNG) from error
    if too_large:
        raise TextureRefusedError(PNG_DATA_TOO_LARGE, {"size": str(limit)})


_CHECKS: Final[Mapping[str, Callable[[bytes], None]]] = {"jpeg": check_jpeg, "png": check_png}


def check_image_bytes(data: bytes, image_format: str) -> None:
    """Contrôle de ``data`` selon ``image_format`` (nom du décodeur : ``"png"``, ``"jpeg"``) ;
    ``TextureRefusedError`` si l'image est refusée, rien pour un format sans contrôle."""
    check = _CHECKS.get(image_format)
    if check is not None:
        check(data)
