# SPDX-License-Identifier: LGPL-2.1-or-later
"""Textures des matériaux dans la vue 3D : décodage par Qt et nœuds Coin (ADR 0004).

- :class:`TextureCache` décode chaque image une fois et partage son nœud ``SoTexture2`` entre
  toutes les pièces (poids-mouche) ; les refus sont mémorisés aussi, d'où un seul avertissement
  par image et par session. Cache explicite, réinitialisable par :func:`reset_texture_cache`.
- :class:`TextureSwitch` porte les nœuds propres à une pièce : un ``SoSwitch`` nommé
  ``MenuiserieTexture`` qui contient la projection (``SoTextureCoordinatePlane``) puis le nœud
  de texture partagé.

Seuls les décodeurs PNG et JPEG de Qt sont sollicités (imposés par l'extension, détection
automatique désactivée) et les dimensions sont bornées, lues dans l'en-tête, avant décodage.
"""

from __future__ import annotations

import os
from collections import OrderedDict
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

import FreeCAD as App
from pivy import coin
from PySide import QtGui

from freecad.menuiserie.core.appearance import MAX_TEXTURE_PIXELS, TextureMapping, Vector3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.appearance import usable_texture_file
from freecad.menuiserie.features.i18n import translated

__all__ = [
    "SWITCH_NAME",
    "TextureCache",
    "TextureSwitch",
    "reset_texture_cache",
    "texture_cache",
]

SoNode = Any  # nœuds Coin (pivy), sans annotations de type
Warn = Callable[[str], None]
FileKey = tuple[str, int, int]  # chemin, taille, date de modification (ns)

SWITCH_NAME: Final = "MenuiserieTexture"
DEFAULT_MAX_ENTRIES: Final = 32
_DECODERS: Final[Mapping[str, bytes]] = {".png": b"png", ".jpg": b"jpeg", ".jpeg": b"jpeg"}
_RGB_COMPONENTS: Final = 3
_MISSING_FILE: Final = -1

_REFUSED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Texture « {image} » non affichée ({reason}) : couleur du matériau utilisée à la place.",
)
_UNUSABLE_FILE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "fichier absent, vide, illisible ou de plus de 16 Mio"
)
_UNSUPPORTED_EXTENSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "extension autre que .png, .jpg ou .jpeg"
)
_UNREADABLE_HEADER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "en-tête illisible ou contenu d'un autre format que l'extension"
)
_TOO_LARGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{width} sur {height} pixels, {max} au plus par côté"
)
_UNREADABLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "image illisible : {error}")


class TextureRefusedError(Exception):
    """Image refusée ; ``reason`` est un gabarit traduisible rempli par ``params``."""

    def __init__(self, reason: str, params: Mapping[str, str] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.params = dict(params or {})

    def message(self) -> str:
        """Raison traduite et remplie."""
        return translated(self.reason, self.params)


def _report_warning(message: str) -> None:
    """Avertissement dans la vue rapport (``PrintWarning`` lu à l'appel : remplaçable)."""
    App.Console.PrintWarning(f"Menuiserie : {message}\n")


def _file_key(image: Path) -> FileKey:
    """Clé de cache : une image remplacée (taille ou date changée) est relue."""
    try:
        status = os.stat(image)
    except (OSError, ValueError):
        return str(image), _MISSING_FILE, _MISSING_FILE
    return str(image), status.st_size, status.st_mtime_ns


def _decoded(image: Path) -> QtGui.QImage:
    """Image décodée par le décodeur de son extension ; ``TextureRefusedError`` sinon."""
    if not usable_texture_file(image):
        raise TextureRefusedError(_UNUSABLE_FILE)
    decoder = _DECODERS.get(image.suffix.lower())
    if decoder is None:
        raise TextureRefusedError(_UNSUPPORTED_EXTENSION)
    reader = QtGui.QImageReader(str(image), decoder)
    reader.setAutoDetectImageFormat(False)
    size = reader.size()  # lue dans l'en-tête, avant décodage
    if size.isEmpty():
        raise TextureRefusedError(_UNREADABLE_HEADER)
    if max(size.width(), size.height()) > MAX_TEXTURE_PIXELS:
        params = {"width": str(size.width()), "height": str(size.height())}
        raise TextureRefusedError(_TOO_LARGE, {**params, "max": str(MAX_TEXTURE_PIXELS)})
    picture = reader.read()
    if picture.isNull():
        raise TextureRefusedError(_UNREADABLE, {"error": quoted_value(reader.errorString())})
    return picture


def _rgb_rows(picture: QtGui.QImage) -> bytes:
    """Pixels RVB opaques, de la ligne du bas à celle du haut (origine de Coin en bas à
    gauche), sans le bourrage de fin de ligne de Qt."""
    rgb = picture.convertToFormat(QtGui.QImage.Format.Format_RGB888)
    row, stride = rgb.width() * _RGB_COMPONENTS, rgb.bytesPerLine()
    data = bytes(rgb.constBits())
    starts = (line * stride for line in reversed(range(rgb.height())))
    return b"".join(data[start : start + row] for start in starts)


def _texture_node(picture: QtGui.QImage) -> SoNode:
    """Nœud ``SoTexture2`` (modèle ``MODULATE``, répété en S et T) portant l'image."""
    node = coin.SoTexture2()
    size = coin.SbVec2s(picture.width(), picture.height())
    node.image.setValue(size, _RGB_COMPONENTS, _rgb_rows(picture))
    node.model = coin.SoTexture2.MODULATE
    node.wrapS = coin.SoTexture2.REPEAT
    node.wrapT = coin.SoTexture2.REPEAT
    return node


class TextureCache:
    """Un nœud ``SoTexture2`` partagé par image ; succès et refus mémorisés.

    Au plus ``max_entries`` images sont retenues (les plus anciennes sont oubliées). ``warn``
    reçoit le message traduit de chaque refus (par défaut : la vue rapport).
    """

    def __init__(self, warn: Warn | None = None, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._warn = warn or _report_warning
        self._max_entries = max_entries
        self._entries: OrderedDict[FileKey, SoNode | None] = OrderedDict()

    def node(self, image: Path) -> SoNode | None:
        """Nœud partagé de ``image`` ; ``None`` si l'image est refusée (avertissement unique)."""
        key = _file_key(image)
        if key in self._entries:
            self._entries.move_to_end(key)
            return self._entries[key]
        texture = self._load(image)
        self._remember(key, texture)
        return texture

    def usable(self, image: Path) -> bool:
        """Vrai si ``image`` peut être affichée (contrôle du fichier puis décodage)."""
        return self.node(image) is not None

    def clear(self) -> None:
        """Oublie toutes les images (elles seront relues et, si besoin, signalées à nouveau)."""
        self._entries.clear()

    def _load(self, image: Path) -> SoNode | None:
        try:
            return _texture_node(_decoded(image))
        except TextureRefusedError as refusal:
            params = {"image": str(image), "reason": refusal.message()}
            self._warn(translated(_REFUSED, params))
            return None

    def _remember(self, key: FileKey, texture: SoNode | None) -> None:
        """Retient ``texture`` à la place des versions précédentes de la même image."""
        for stale in [known for known in self._entries if known[0] == key[0]]:
            del self._entries[stale]
        self._entries[key] = texture
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


_SESSION: Final[dict[str, TextureCache]] = {}


def texture_cache() -> TextureCache:
    """Cache de la session, créé au premier appel."""
    cache = _SESSION.get("cache")
    return cache if cache is not None else reset_texture_cache()


def reset_texture_cache(warn: Warn | None = None) -> TextureCache:
    """Remplace le cache de la session par un cache vide (tests : ``warn`` de comptage)."""
    cache = TextureCache(warn)
    _SESSION["cache"] = cache
    return cache


def _set_direction(field: SoNode, direction: Vector3) -> None:
    """Écrit une direction de projection seulement si elle change."""
    wanted = coin.SbVec3f(*direction)
    if field.getValue() != wanted:
        field.setValue(wanted)


class TextureSwitch:
    """Nœuds de texture d'une pièce : ``SoSwitch`` → ``SoGroup`` → (projection, texture)."""

    def __init__(self) -> None:
        self.root = coin.SoSwitch()
        self.root.setName(SWITCH_NAME)
        self.root.whichChild = coin.SO_SWITCH_NONE
        self._plane = coin.SoTextureCoordinatePlane()
        self._group = coin.SoGroup()
        self._group.addChild(self._plane)
        self.root.addChild(self._group)
        self._texture: SoNode | None = None

    @property
    def active(self) -> bool:
        """Vrai si la texture est affichée."""
        return bool(self.root.whichChild.getValue() != coin.SO_SWITCH_NONE)

    def insert_before(self, parent: SoNode, sibling: SoNode) -> None:
        """Insère le switch dans ``parent`` juste avant ``sibling`` (à la fin s'il est absent)."""
        index = parent.findChild(sibling)
        parent.insertChild(self.root, index if index >= 0 else parent.getNumChildren())

    def show(self, mapping: TextureMapping, texture: SoNode) -> None:
        """Affiche ``texture`` projetée selon ``mapping`` ; seules les valeurs changées sont
        écrites."""
        _set_direction(self._plane.directionS, mapping.direction_s)
        _set_direction(self._plane.directionT, mapping.direction_t)
        if self._texture is not texture:
            if self._texture is None:
                self._group.addChild(texture)
            else:
                self._group.replaceChild(1, texture)
            self._texture = texture
        if not self.active:
            self.root.whichChild = 0

    def hide(self) -> None:
        """Masque la texture (la couleur du matériau est alors affichée)."""
        if self.active:
            self.root.whichChild = coin.SO_SWITCH_NONE
