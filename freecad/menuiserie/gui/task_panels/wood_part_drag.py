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

from freecad.menuiserie.gui.drag import events
from freecad.menuiserie.gui.drag.session import DragSession, PanelContext
from freecad.menuiserie.gui.task_panels.base import connect


class PanelDrag:
    """Lien entre la session de glissement et un panneau de tâche ``panel`` (pièce ``panel.obj``,
    propriété ``closed``, méthode ``after_drag`` qui relit les champs). Sans session (atelier
    inactif), ne fait rien."""

    def __init__(self, panel: Any) -> None:
        self._panel = weakref.ref(panel)
        self._session: DragSession | None = events.current_session()
        self._context = PanelContext(panel.obj, self._refresh, self._is_open)
        if self._session is not None:
            self._session.set_panel(self._context)
            connect(panel.form, "destroyed()", self._on_destroyed)

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
        if session is not None:
            session.clear_panel(self._context)
