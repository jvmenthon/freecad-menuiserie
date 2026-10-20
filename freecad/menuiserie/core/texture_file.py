# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ouverture unique et confinée du fichier image d'une texture (ADR 0004).

Python pur, sans FreeCAD ni Qt. Le fichier est ouvert **une seule fois** : le chemin est résolu,
son confinement au dossier de la bibliothèque vérifié, puis la cible ouverte sans suivre de lien
(``O_NOFOLLOW`` sur le dernier composant) ni bloquer (``O_NONBLOCK`` : un tube nommé ne fige
rien) ; le type et la taille sont contrôlés sur le descripteur ouvert (``fstat``), et les octets
lus au plus une fois, bornés. Aucun autre accès par le nom ne suit : le décodage se fait en
mémoire (``gui/textures.py``).
"""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Final

from freecad.menuiserie.core.appearance import MAX_TEXTURE_FILE_BYTES
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Texture

__all__ = [
    "OUTSIDE_LIBRARY",
    "UNUSABLE_FILE",
    "FileKey",
    "TextureFile",
    "TextureRefusedError",
    "confined_image",
]

FileKey = tuple[int, int, int, int]  # périphérique, inode, taille, date de modification (ns)

# Drapeaux absents sous Windows (O_NOFOLLOW, O_NONBLOCK, O_CLOEXEC, O_NOCTTY) ou ailleurs
# (O_BINARY) : valent 0 là où ils n'existent pas.
_OPEN_FLAGS: Final = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOCTTY", 0)
    | getattr(os, "O_BINARY", 0)
)

UNUSABLE_FILE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "fichier absent, vide, illisible ou de plus de 16 Mio"
)
OUTSIDE_LIBRARY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "fichier sorti du dossier de la bibliothèque"
)


class TextureRefusedError(Exception):
    """Image refusée ; ``reason`` est un gabarit français traduisible rempli par ``params``."""

    def __init__(self, reason: str, params: Mapping[str, str] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.params = dict(params or {})


def confined_image(texture: Texture) -> Path:
    """Chemin de l'image, liens résolus, s'il reste dans le dossier de la bibliothèque.

    La résolution est refaite à chaque ouverture : un lien interne au dossier est accepté, un
    lien (ou un dossier intermédiaire) remplacé depuis le chargement et qui mène dehors est
    refusé. ``TextureRefusedError`` sinon.
    """
    try:
        image = texture.image.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:  # absent, boucle de liens, octet nul
        raise TextureRefusedError(UNUSABLE_FILE) from error
    folder = texture.library_folder
    if image == folder or not image.is_relative_to(folder):
        raise TextureRefusedError(OUTSIDE_LIBRARY)
    return image


def _file_key(descriptor: int) -> FileKey:
    """Identité du fichier ouvert s'il est ordinaire, non vide et d'au plus 16 Mio ;
    ``TextureRefusedError`` sinon (dossier, tube, périphérique…)."""
    try:
        status = os.fstat(descriptor)
    except OSError as error:
        raise TextureRefusedError(UNUSABLE_FILE) from error
    if not stat.S_ISREG(status.st_mode) or not 0 < status.st_size <= MAX_TEXTURE_FILE_BYTES:
        raise TextureRefusedError(UNUSABLE_FILE)
    return status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns


class TextureFile:
    """Fichier image ouvert une fois, contrôlé sur son descripteur ; à fermer (``with``).

    ``key`` identifie le contenu (deux liens physiques vers le même fichier ont la même clé ;
    un fichier réécrit en change). ``TextureRefusedError`` dès la construction si le fichier
    est absent, hors du dossier, d'un autre type qu'ordinaire, vide ou trop gros.
    """

    def __init__(self, texture: Texture) -> None:
        image = confined_image(texture)
        try:
            self._fd = os.open(image, _OPEN_FLAGS)
        except (OSError, ValueError) as error:  # lien substitué (O_NOFOLLOW), droits…
            raise TextureRefusedError(UNUSABLE_FILE) from error
        try:
            self.key: FileKey = _file_key(self._fd)
        except TextureRefusedError:
            os.close(self._fd)
            raise

    def read(self) -> bytes:
        """Contenu du fichier, lu au plus une fois ; ``TextureRefusedError`` s'il est devenu
        vide ou plus gros que 16 Mio depuis l'ouverture."""
        data = bytearray()
        try:
            while len(data) <= MAX_TEXTURE_FILE_BYTES:
                chunk = os.read(self._fd, MAX_TEXTURE_FILE_BYTES + 1 - len(data))
                if not chunk:
                    break
                data += chunk
        except OSError as error:
            raise TextureRefusedError(UNUSABLE_FILE) from error
        if not 0 < len(data) <= MAX_TEXTURE_FILE_BYTES:
            raise TextureRefusedError(UNUSABLE_FILE)
        return bytes(data)

    def close(self) -> None:
        """Ferme le descripteur (sans effet s'il l'est déjà)."""
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> TextureFile:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()
