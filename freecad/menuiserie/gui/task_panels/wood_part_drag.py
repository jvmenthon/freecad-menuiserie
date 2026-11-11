# SPDX-License-Identifier: LGPL-2.1-or-later
"""Glisser à la souris pendant le panneau de la pièce de bois (SM-c, ADR 0021) : branche la session
du glissement sur le panneau.

Panneau ouvert, les flèches et les poignées (quatre, six pour le massif) sont sur la pièce du
panneau, le glissement écrit dans la transaction du panneau et les champs du panneau relisent les
cotes à chaque écriture. Rien du formulaire n'est gardé ici : le panneau n'est tenu que par une
référence faible (les enveloppes PySide ne doivent pas lui survivre) ; à la fermeture du panneau,
les poignées sont enlevées.
"""

from __future__ import annotations

import weakref
from typing import Any

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.gui.drag import events
from freecad.menuiserie.gui.drag.session import DragSession, PanelContext
from freecad.menuiserie.gui.task_panels.base import connect


class PanelDrag:
    """Lien entre la session de glissement et un panneau de tâche ``panel`` (propriété ``closed``,
    méthode ``after_drag`` qui relit les champs). La pièce est ``panel.obj`` ; un panneau dont
    l'objet est recréé à chaque aperçu (caisson) passe ``follow=True`` et appelle :meth:`follow`
    à chaque aperçu. Sans session (atelier inactif), ne fait rien."""

    def __init__(self, panel: Any, *, follow: bool = False) -> None:
        self._panel = weakref.ref(panel)
        self._session: DragSession | None = events.current_session()
        self._context: PanelContext | None = None
        if self._session is not None:
            connect(panel.form, "destroyed()", self._on_destroyed)
            if not follow:
                self.follow(panel.obj)

    def follow(self, part: DocumentObject | None) -> None:
        """Flèches et poignées sur ``part`` (aucune si ``None``)."""
        session = self._session
        if session is None:
            return
        previous, self._context = self._context, None
        if part is not None:
            self._context = PanelContext(part, self._refresh, self._is_open)
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
