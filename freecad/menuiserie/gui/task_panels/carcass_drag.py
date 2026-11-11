# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flèches, anneaux et poignées de la vue 3D pendant le panneau « Caisson » (ADR 0038).

Comme pour la pièce de bois, le geste écrit dans la transaction du panneau. Le caisson d'aperçu
est recréé à chaque saisie : la session est donc rebranchée sur le nouveau caisson à chaque
aperçu (:meth:`CarcassDrag.follow`). Le panneau n'est tenu que par une référence faible.
"""

from __future__ import annotations

import weakref
from typing import Any

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.gui.drag import events
from freecad.menuiserie.gui.drag.session import DragSession, PanelContext
from freecad.menuiserie.gui.task_panels.base import connect


class CarcassDrag:
    """Lien entre la session de glissement et le panneau ``panel`` (propriété ``closed``, méthode
    ``after_drag``). Sans session (atelier inactif), ne fait rien."""

    def __init__(self, panel: Any) -> None:
        self._panel = weakref.ref(panel)
        self._session: DragSession | None = events.current_session()
        self._context: PanelContext | None = None
        if self._session is not None:
            connect(panel.form, "destroyed()", self._on_destroyed)

    def follow(self, furniture: DocumentObject | None) -> None:
        """Poignées sur le caisson d'aperçu ``furniture`` (aucune s'il n'y en a pas)."""
        session = self._session
        if session is None:
            return
        previous, self._context = self._context, None
        if furniture is not None:
            self._context = PanelContext(furniture, self._refresh, self._is_open)
            session.set_panel(self._context)
        elif previous is not None:
            session.clear_panel(previous)

    def _is_open(self) -> bool:
        panel = self._panel()
        return panel is not None and not panel.closed

    def _refresh(self) -> None:
        panel = self._panel()
        if panel is not None and not panel.closed:
            panel.after_drag()

    def _on_destroyed(self) -> None:
        """Formulaire détruit (panneau fermé) : poignées enlevées."""
        session, self._session = self._session, None
        context, self._context = self._context, None
        if session is not None and context is not None:
            session.clear_panel(context)
