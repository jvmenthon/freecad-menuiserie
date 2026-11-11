# SPDX-License-Identifier: LGPL-2.1-or-later
"""Calques d'affichage temporaires d'un objet : transparence d'édition et de sélection (ADR 0046).

Logique pure, sans FreeCAD ni Qt. Plusieurs mécanismes (le panneau de tâche en cours, la ligne
sélectionnée du panneau « Structure ») peuvent rendre le même objet transparent sans se
connaître : chacun pose un calque (:class:`Look`) sous son nom. :class:`LayerStack` retient
**une seule fois** l'état d'origine de l'objet (au premier calque posé) et dit quel aspect
afficher : celui du calque le plus prioritaire ; l'état d'origine n'est rendu que quand le
dernier calque est retiré. Ainsi aucun calque ne restaure ni n'écrase l'autre.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Final, Generic, TypeVar

from freecad.menuiserie.core.colors import Rgb

__all__ = [
    "EDIT_LOOK",
    "EDIT_PRIORITY",
    "EDIT_TRANSPARENCY",
    "ORIGIN_LOOK",
    "ORIGIN_TINT",
    "SELECTION_LOOK",
    "SELECTION_PRIORITY",
    "SELECTION_TINT",
    "SELECTION_TRANSPARENCY",
    "LayerStack",
    "Look",
    "Update",
]

T = TypeVar("T")

EDIT_TRANSPARENCY: Final = 60  # pour cent : pièce en cours d'édition (ADR 0011)
SELECTION_TRANSPARENCY: Final = 50  # pour cent : pièce de la ligne sélectionnée
SELECTION_TINT: Final = (70, 160, 255)  # bleu clair, distinct du bois et de l'édition (sans teinte)
ORIGIN_TINT: Final = (70, 140, 230)  # bleu des pièces d'origine teintes par un panneau (répétition)
EDIT_PRIORITY: Final = 20  # l'édition prime visuellement sur la sélection
SELECTION_PRIORITY: Final = 10


@dataclass(frozen=True)
class Look:
    """Aspect temporaire : transparence (0 à 100 %), teinte facultative (``None`` : couleur
    d'origine) et priorité (le plus haut l'emporte)."""

    transparency: int
    tint: Rgb | None
    priority: int


EDIT_LOOK: Final = Look(EDIT_TRANSPARENCY, None, EDIT_PRIORITY)
ORIGIN_LOOK: Final = Look(EDIT_TRANSPARENCY, ORIGIN_TINT, EDIT_PRIORITY)
SELECTION_LOOK: Final = Look(SELECTION_TRANSPARENCY, SELECTION_TINT, SELECTION_PRIORITY)


@dataclass(frozen=True)
class Update(Generic[T]):
    """Ce qu'il faut afficher après un changement : ``look`` ; ``None`` : rendre ``original``
    (plus aucun calque)."""

    look: Look | None
    original: T


def _rank(entry: tuple[int, Look]) -> tuple[int, int]:
    """Ordre des calques : priorité, puis ancienneté de la pose."""
    return entry[1].priority, entry[0]


class LayerStack(Generic[T]):
    """Calques par objet (``key``) et par propriétaire (``owner``, nom du mécanisme)."""

    def __init__(self) -> None:
        self._originals: dict[Hashable, T] = {}
        self._layers: dict[Hashable, dict[Hashable, Look]] = {}

    def __len__(self) -> int:
        return len(self._layers)

    def __contains__(self, key: object) -> bool:
        return key in self._layers

    def tracked(self) -> list[Hashable]:
        """Objets qui portent au moins un calque."""
        return list(self._layers)

    def keys_of(self, owner: Hashable) -> list[Hashable]:
        """Objets sur lesquels ``owner`` a un calque."""
        return [key for key, layers in self._layers.items() if owner in layers]

    def layer(self, key: Hashable, owner: Hashable) -> Look | None:
        """Calque de ``owner`` sur ``key`` (``None`` s'il n'en a pas)."""
        return self._layers.get(key, {}).get(owner)

    def original(self, key: Hashable) -> T:
        """État d'origine retenu pour ``key`` (``KeyError`` si aucun calque)."""
        return self._originals[key]

    def rebase(self, key: Hashable, original: T) -> None:
        """Un tiers a modifié l'objet pendant les calques : son nouvel état devient l'origine."""
        if key in self._originals:
            self._originals[key] = original

    def effective(self, key: Hashable) -> Look | None:
        """Aspect à afficher : calque le plus prioritaire, à égalité le plus récent."""
        layers = self._layers.get(key)
        if not layers:
            return None
        return max(enumerate(layers.values()), key=_rank)[1]

    def put(self, key: Hashable, owner: Hashable, look: Look, original: T) -> Update[T]:
        """Pose le calque de ``owner`` ; ``original`` n'est retenu que pour le premier."""
        if key not in self._layers:
            self._layers[key] = {}
            self._originals[key] = original
        self._layers[key].pop(owner, None)  # re-posé : redevient le plus récent
        self._layers[key][owner] = look
        return Update(self.effective(key), self._originals[key])

    def drop(self, key: Hashable, owner: Hashable) -> Update[T] | None:
        """Retire le calque de ``owner`` ; ``None`` s'il n'en avait pas. Sans calque restant,
        l'objet est oublié et ``look`` vaut ``None``."""
        layers = self._layers.get(key)
        if layers is None or owner not in layers:
            return None
        del layers[owner]
        original = self._originals[key]
        if not layers:
            del self._layers[key]
            del self._originals[key]
        return Update(self.effective(key), original)

    def forget(self, key: Hashable) -> None:
        """Objet supprimé : plus rien à rétablir."""
        self._layers.pop(key, None)
        self._originals.pop(key, None)
