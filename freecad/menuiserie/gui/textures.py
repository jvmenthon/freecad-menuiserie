# SPDX-License-Identifier: LGPL-2.1-or-later
"""Textures des matériaux dans la vue 3D : décodage par Qt et nœuds Coin (ADR 0004).

- :class:`TextureCache` décode chaque image une fois et partage son nœud ``SoTexture2`` entre
  toutes les pièces (poids-mouche) ; les refus sont mémorisés aussi, d'où un seul avertissement
  par image et par session. Cache explicite, réinitialisable par :func:`reset_texture_cache`.
- :class:`TextureSwitch` porte les nœuds propres à une pièce : un ``SoSwitch`` nommé
  ``MenuiserieTexture`` qui contient la projection (``SoTextureCoordinatePlane``) puis le nœud
  de texture partagé.

Le fichier est ouvert une seule fois et lu en mémoire (``core/texture_file.py`` : confinement
au dossier de la bibliothèque, ``O_NOFOLLOW``, ``fstat``) ; Qt décode ces octets, jamais le
fichier par son nom. Seuls les décodeurs PNG et JPEG de Qt sont sollicités (imposés par
l'extension, détection automatique désactivée) ; les dimensions sont bornées, lues dans
l'en-tête, et les octets contrôlés selon le format (``core/image_checks.py``), avant décodage.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any, Final

import FreeCAD as App
from pivy import coin
from PySide import QtCore, QtGui

from freecad.menuiserie.core.appearance import MAX_TEXTURE_PIXELS, TextureMapping, Vector3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.image_checks import check_image_bytes
from freecad.menuiserie.core.materials import Texture
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.core.texture_file import TextureFile, TextureRefusedError
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
CacheKey = tuple[str, int, int]  # chemin, taille, date de modification (ns)

SWITCH_NAME: Final = "MenuiserieTexture"
DEFAULT_MAX_ENTRIES: Final = 32
_DECODERS: Final[Mapping[str, str]] = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}
_RGB_COMPONENTS: Final = 3
_MISSING_FILE: Final = -1
_BUFFER_MODE: Final = QtCore.QIODevice.OpenModeFlag.ReadOnly

_REFUSED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Texture « {image} » non affichée ({reason}) : couleur du matériau utilisée à la place.",
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


def _refusal_message(refusal: TextureRefusedError) -> str:
    """Raison du refus, traduite et remplie."""
    return translated(refusal.reason, refusal.params)


def _report_warning(message: str) -> None:
    """Avertissement dans la vue rapport (``PrintWarning`` lu à l'appel : remplaçable)."""
    App.Console.PrintWarning(f"Menuiserie : {message}\n")


def _decoder(texture: Texture) -> str:
    """Nom du décodeur Qt imposé par l'extension ; ``TextureRefusedError`` sinon."""
    decoder = _DECODERS.get(texture.image.suffix.lower())
    if decoder is None:
        raise TextureRefusedError(_UNSUPPORTED_EXTENSION)
    return decoder


def _decoded(data: bytes, decoder: str) -> QtGui.QImage:
    """Image décodée en mémoire par ``decoder`` ; ``TextureRefusedError`` si elle est refusée
    (en-tête, dimensions, puis contrôles des octets propres au format, avant décodage)."""
    buffer = QtCore.QBuffer()
    buffer.setData(QtCore.QByteArray(data))
    buffer.open(_BUFFER_MODE)
    reader = QtGui.QImageReader(buffer, decoder.encode("ascii"))
    reader.setAutoDetectImageFormat(False)
    size = reader.size()  # lue dans l'en-tête, avant décodage
    if size.isEmpty():
        raise TextureRefusedError(_UNREADABLE_HEADER)
    if max(size.width(), size.height()) > MAX_TEXTURE_PIXELS:
        params = {"width": str(size.width()), "height": str(size.height())}
        raise TextureRefusedError(_TOO_LARGE, {**params, "max": str(MAX_TEXTURE_PIXELS)})
    check_image_bytes(data, decoder)
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
        self._entries: OrderedDict[CacheKey, SoNode | None] = OrderedDict()

    def node(self, texture: Texture) -> SoNode | None:
        """Nœud partagé de l'image de ``texture`` ; ``None`` si elle est refusée (avertissement
        unique). Le fichier est ouvert une seule fois et décodé en mémoire."""
        try:
            with TextureFile(texture) as opened:
                return self._node_of(texture, opened)
        except TextureRefusedError as refusal:  # fichier inutilisable : identifié par son nom
            self._refused((str(texture.image), _MISSING_FILE, _MISSING_FILE), refusal)
            return None

    def usable(self, texture: Texture) -> bool:
        """Vrai si l'image de ``texture`` peut être affichée (contrôle du fichier puis décodage)."""
        return self.node(texture) is not None

    def clear(self) -> None:
        """Oublie toutes les images (elles seront relues et, si besoin, signalées à nouveau)."""
        self._entries.clear()

    def _node_of(self, texture: Texture, opened: TextureFile) -> SoNode | None:
        """Nœud mémorisé du fichier ouvert, sinon décodé depuis ses octets."""
        key = str(texture.image), opened.key[2], opened.key[3]
        if key in self._entries:
            return self._known(key)
        try:
            decoder = _decoder(texture)
            loaded = _texture_node(_decoded(opened.read(), decoder))
        except TextureRefusedError as refusal:
            self._refused(key, refusal)
            return None
        self._remember(key, loaded)
        return loaded

    def _known(self, key: CacheKey) -> SoNode | None:
        self._entries.move_to_end(key)
        return self._entries[key]

    def _refused(self, key: CacheKey, refusal: TextureRefusedError) -> None:
        """Mémorise le refus ; l'avertissement n'est émis que la première fois."""
        if key in self._entries:
            self._known(key)
            return
        params = {"image": key[0], "reason": _refusal_message(refusal)}
        self._warn(translated(_REFUSED, params))
        self._remember(key, None)

    def _remember(self, key: CacheKey, texture: SoNode | None) -> None:
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
