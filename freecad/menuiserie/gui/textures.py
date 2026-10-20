# SPDX-License-Identifier: LGPL-2.1-or-later
"""Textures des matériaux dans la vue 3D : décodage par Qt et nœuds Coin (ADR 0004).

- :class:`TextureCache` décode chaque image une fois et partage son nœud ``SoTexture2`` entre
  toutes les pièces (poids-mouche), clé = identité du fichier (périphérique, inode, taille,
  date : deux liens physiques partagent un nœud) ; les refus sont mémorisés aussi, d'où un seul
  avertissement par image et par session. Les octets décodés encore vivants (dans le cache ou
  sous une pièce affichée) sont bornés par un budget global : au-delà, couleur du matériau et
  avertissement unique. Cache explicite, réinitialisable par :func:`reset_texture_cache`.
- :class:`TextureSwitch` porte les nœuds propres à une pièce : un ``SoSwitch`` nommé
  ``MenuiserieTexture`` qui contient la projection (``SoTextureCoordinatePlane``) puis le nœud
  de texture partagé, retiré quand la texture est masquée.

Le fichier est ouvert une seule fois et lu en mémoire (``core/texture_file.py`` : confinement
au dossier de la bibliothèque, ``O_NOFOLLOW``, ``fstat``) ; Qt décode ces octets, jamais le
fichier par son nom. Seuls les décodeurs PNG et JPEG de Qt sont sollicités (imposés par
l'extension, détection automatique désactivée) ; les dimensions sont bornées, lues dans
l'en-tête, et les octets contrôlés selon le format (``core/image_checks.py``), avant décodage.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping
from typing import Any, Final

import FreeCAD as App
from pivy import coin
from PySide import QtCore, QtGui

from freecad.menuiserie.core.appearance import MAX_TEXTURE_PIXELS, TextureMapping, Vector3
from freecad.menuiserie.core.budget_cache import BudgetedCache, Decoded
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.image_checks import check_image_bytes
from freecad.menuiserie.core.materials import Texture
from freecad.menuiserie.core.text import escaped_text, quoted_value
from freecad.menuiserie.core.texture_file import TextureFile, TextureRefusedError
from freecad.menuiserie.features.i18n import translated

__all__ = [
    "DEFAULT_MAX_BYTES",
    "SWITCH_NAME",
    "TextureCache",
    "TextureNode",
    "TextureSwitch",
    "reset_texture_cache",
    "texture_cache",
]

SoNode = Any  # nœuds Coin (pivy), sans annotations de type
Warn = Callable[[str], None]
TextureNode = Decoded[SoNode]  # nœud SoTexture2 partagé et octets de son image
Reserve = Callable[[int], None]

SWITCH_NAME: Final = "MenuiserieTexture"
DEFAULT_MAX_ENTRIES: Final = 32
DEFAULT_MAX_BYTES: Final = 256 * 1024 * 1024  # images décodées vivantes, toutes pièces confondues
_MEBIBYTE: Final = 1024 * 1024
_DECODERS: Final[Mapping[str, str]] = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}
_RGB_COMPONENTS: Final = 3
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
_OVER_BUDGET: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Textures non affichées au-delà de {max} Mio d'images décodées (première : « {image} ») : "
    "couleur du matériau utilisée à la place. Cet avertissement n'est pas répété.",
)


class _OverBudgetError(Exception):
    """L'image décodée dépasserait le budget mémoire des textures."""


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


def _decoded(data: bytes, decoder: str, reserve: Reserve) -> QtGui.QImage:
    """Image décodée en mémoire par ``decoder`` ; ``TextureRefusedError`` si elle est refusée
    (en-tête, dimensions, puis contrôles des octets propres au format, avant décodage).
    ``reserve`` reçoit les octets RVB de l'image avant tout décodage et peut l'interdire."""
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
    reserve(size.width() * size.height() * _RGB_COMPONENTS)
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


def _texture_node(picture: QtGui.QImage) -> TextureNode:
    """Nœud ``SoTexture2`` (modèle ``MODULATE``, répété en S et T) portant l'image, avec la
    taille de ses pixels en octets."""
    node = coin.SoTexture2()
    size = coin.SbVec2s(picture.width(), picture.height())
    pixels = _rgb_rows(picture)
    node.image.setValue(size, _RGB_COMPONENTS, pixels)
    node.model = coin.SoTexture2.MODULATE
    node.wrapS = coin.SoTexture2.REPEAT
    node.wrapT = coin.SoTexture2.REPEAT
    return Decoded(node, len(pixels))


class TextureCache:
    """Un nœud ``SoTexture2`` partagé par fichier image ; succès et refus mémorisés.

    Au plus ``max_entries`` images sont retenues (les plus anciennes sont oubliées) et au plus
    ``max_bytes`` octets d'images décodées vivent à la fois, y compris les nœuds oubliés par le
    cache mais encore affichés. ``warn`` reçoit le message traduit de chaque refus (par défaut :
    la vue rapport).
    """

    def __init__(
        self,
        warn: Warn | None = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self._warn = warn or _report_warning
        self._cache: BudgetedCache[Hashable, SoNode] = BudgetedCache(max_entries, max_bytes)
        self._over_budget_reported = False

    def node(self, texture: Texture) -> TextureNode | None:
        """Nœud partagé de l'image de ``texture`` ; ``None`` si elle est refusée (avertissement
        unique). Le fichier est ouvert une seule fois et décodé en mémoire."""
        try:
            with TextureFile(texture) as opened:
                return self._node_of(texture, opened)
        except TextureRefusedError as refusal:  # fichier inutilisable : identifié par son nom
            self._refused(str(texture.image), texture, refusal)
            return None

    def usable(self, texture: Texture) -> bool:
        """Vrai si l'image de ``texture`` peut être affichée (contrôle du fichier puis décodage)."""
        return self.node(texture) is not None

    def clear(self) -> None:
        """Oublie toutes les images (elles seront relues et, si besoin, signalées à nouveau)."""
        self._cache.clear()

    def _node_of(self, texture: Texture, opened: TextureFile) -> TextureNode | None:
        """Nœud mémorisé ou encore vivant du fichier ouvert, sinon décodé depuis ses octets."""
        if opened.key in self._cache:
            return self._cache.get(opened.key)
        try:
            decoder = _decoder(texture)
            loaded = _texture_node(_decoded(opened.read(), decoder, self._reserve))
        except _OverBudgetError:  # pas mémorisé : l'image s'affichera quand la mémoire sera libre
            self._report_over_budget(texture)
            return None
        except TextureRefusedError as refusal:
            self._refused(opened.key, texture, refusal)
            return None
        self._cache.remember(opened.key, loaded)
        return loaded

    def _reserve(self, nbytes: int) -> None:
        if not self._cache.reserve(nbytes):
            raise _OverBudgetError

    def _report_over_budget(self, texture: Texture) -> None:
        """Avertit une seule fois par cache que le budget mémoire est atteint."""
        if self._over_budget_reported:
            return
        self._over_budget_reported = True
        params = {"max": str(self._cache.max_bytes // _MEBIBYTE), "image": _cited(texture)}
        self._warn(translated(_OVER_BUDGET, params))

    def _refused(self, key: Hashable, texture: Texture, refusal: TextureRefusedError) -> None:
        """Mémorise le refus ; l'avertissement n'est émis que la première fois."""
        if key in self._cache:
            self._cache.get(key)
            return
        params = {"image": _cited(texture), "reason": _refusal_message(refusal)}
        self._warn(translated(_REFUSED, params))
        self._cache.remember(key, None)


def _cited(texture: Texture) -> str:
    """Chemin de l'image cité dans un avertissement, entier, caractères non imprimables
    échappés (le dossier de la bibliothèque est choisi librement)."""
    return escaped_text(str(texture.image))


_SESSION: Final[dict[str, TextureCache]] = {}


def texture_cache() -> TextureCache:
    """Cache de la session, créé au premier appel."""
    cache = _SESSION.get("cache")
    return cache if cache is not None else reset_texture_cache()


def reset_texture_cache(
    warn: Warn | None = None,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TextureCache:
    """Remplace le cache de la session par un cache vide (tests : ``warn`` de comptage, bornes
    réduites)."""
    cache = TextureCache(warn, max_entries, max_bytes)
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
        self._texture: TextureNode | None = None

    @property
    def active(self) -> bool:
        """Vrai si la texture est affichée."""
        return bool(self.root.whichChild.getValue() != coin.SO_SWITCH_NONE)

    def insert_before(self, parent: SoNode, sibling: SoNode) -> None:
        """Insère le switch dans ``parent`` juste avant ``sibling`` (à la fin s'il est absent)."""
        index = parent.findChild(sibling)
        parent.insertChild(self.root, index if index >= 0 else parent.getNumChildren())

    def show(self, mapping: TextureMapping, texture: TextureNode) -> None:
        """Affiche ``texture`` projetée selon ``mapping`` ; seules les valeurs changées sont
        écrites. Le nœud est gardé tant qu'il est affiché (compté dans le budget du cache)."""
        _set_direction(self._plane.directionS, mapping.direction_s)
        _set_direction(self._plane.directionT, mapping.direction_t)
        if self._texture is not texture:
            if self._texture is None:
                self._group.addChild(texture.value)
            else:
                self._group.replaceChild(1, texture.value)
            self._texture = texture
        if not self.active:
            self.root.whichChild = 0

    def hide(self) -> None:
        """Masque la texture (la couleur du matériau est alors affichée) et lâche son nœud, que
        le cache peut alors libérer."""
        if self.active:
            self.root.whichChild = coin.SO_SWITCH_NONE
        if self._texture is not None:
            self._group.removeChild(1)
            self._texture = None
