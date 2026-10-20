# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contrôles des octets d'une image avant décodage (audit de sécurité J1d, point 1 : JPEG aux
milliers de balayages)."""

from __future__ import annotations

import struct

import pytest

from freecad.menuiserie.core.image_checks import (
    MAX_JPEG_SCANS,
    TOO_MANY_SCANS,
    check_image_bytes,
    check_jpeg,
    jpeg_scan_count,
)
from freecad.menuiserie.core.texture_file import TextureRefusedError

SIDE = 4096


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
