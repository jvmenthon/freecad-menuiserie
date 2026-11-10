# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu de la pièce en création : transparence posée le temps du panneau (J6c, ADR 0011).

L'aperçu est l'objet réel, dans la transaction du panneau ; seul son affichage change.
:class:`PartsPreview` rend transparents les objets affichés des pièces tant que son panneau est
ouvert (l'usinage se voit à l'intérieur) et leur rend l'affichage d'origine à la fermeture. Il
pose le calque « édition » de ``display_layers`` : la transparence de sélection de la ligne du
panneau « Structure » coexiste avec lui, l'édition l'emportant visuellement, sans que l'un ne
restaure ni n'écrase l'autre. Seules des propriétés du ViewObject sont écrites : le document
n'enregistre ni entrée d'annulation ni modification.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import Any, Final

from freecad.menuiserie.core.display_layers import EDIT_LOOK, EDIT_TRANSPARENCY
from freecad.menuiserie.gui.display_layers import DisplayLayers

PREVIEW_TRANSPARENCY: Final = EDIT_TRANSPARENCY  # pour cent


class PartsPreview:
    """Transparence d'aperçu des objets affichés de plusieurs pièces (``shown`` les donne à
    chaque appel), appliquée à l'ouverture et à chaque :meth:`sync`, rétablie par
    :meth:`restore`. ``alive(obj)`` dit si un objet existe encore dans son document : l'affichage
    n'est jamais rétabli sur un objet supprimé. ``layers`` : calques partagés avec les autres
    mécanismes (``DISPLAY``) ; par défaut, des calques à soi seul."""

    def __init__(
        self,
        shown: Callable[[], Iterable[Any]],
        alive: Callable[[Any], bool],
        layers: DisplayLayers | None = None,
    ) -> None:
        self._shown = shown
        self._alive = alive
        self._layers = layers if layers is not None else DisplayLayers(alive, quiet=_no_quiet)
        self._released = False
        self.sync()

    def sync(self) -> None:
        """Objets affichés relus : transparence posée sur ceux qui le deviennent (pièce usinée
        créée par un recalcul), rétablie sur ceux qui ne le sont plus. Sans effet une fois
        :meth:`restore` appelée."""
        if not self._released:
            self._layers.show(self, self._current(), EDIT_LOOK)

    def restore(self) -> None:
        """Affichage d'origine rétabli sur les objets qui existent encore ; idempotent, et
        l'aperçu ne se pose plus ensuite."""
        self._released = True
        self._layers.release(self)

    def _current(self) -> list[Any]:
        """Objets affichés qui existent ; aucun si les pièces sont illisibles."""
        try:
            return [obj for obj in self._shown() if self._alive(obj)]
        except (ReferenceError, RuntimeError, TypeError):
            return []


@contextmanager
def _no_quiet() -> Iterator[None]:
    """Calques propres à un aperçu isolé (tests) : aucune transaction à contourner."""
    yield
