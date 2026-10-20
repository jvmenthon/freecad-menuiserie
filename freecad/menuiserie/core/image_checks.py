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
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.texture_file import TextureRefusedError

__all__ = [
    "MAX_JPEG_SCANS",
    "TOO_MANY_SCANS",
    "check_image_bytes",
    "check_jpeg",
    "jpeg_scan_count",
]

MAX_JPEG_SCANS: Final = 100
_START_OF_SCAN: Final = b"\xff\xda"

TOO_MANY_SCANS: Final = QT_TRANSLATE_NOOP("Menuiserie", "JPEG en {count} balayages, {max} au plus")


def jpeg_scan_count(data: bytes) -> int:
    """Nombre de marqueurs de début de balayage (``FF DA``) dans les octets d'un JPEG."""
    return data.count(_START_OF_SCAN)


def check_jpeg(data: bytes) -> None:
    """Refuse un JPEG de plus de ``MAX_JPEG_SCANS`` balayages."""
    count = jpeg_scan_count(data)
    if count > MAX_JPEG_SCANS:
        raise TextureRefusedError(TOO_MANY_SCANS, {"count": str(count), "max": str(MAX_JPEG_SCANS)})


_CHECKS: Final[Mapping[str, Callable[[bytes], None]]] = {"jpeg": check_jpeg}


def check_image_bytes(data: bytes, image_format: str) -> None:
    """Contrôle de ``data`` selon ``image_format`` (nom du décodeur : ``"png"``, ``"jpeg"``) ;
    ``TextureRefusedError`` si l'image est refusée, rien pour un format sans contrôle."""
    check = _CHECKS.get(image_format)
    if check is not None:
        check(data)
