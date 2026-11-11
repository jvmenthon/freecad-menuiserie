# SPDX-License-Identifier: LGPL-2.1-or-later
"""Copie par glissement : Ctrl + flèche tirée (lot R-d, ADR 0043, spécification
``repetition.md`` § 4, Q9 et Q10).

Au lieu de déplacer la pièce, le glissement fait suivre la souris à un **fantôme** (boîte
translucide dessinée par l'incrustation du glissement, aimantée comme un déplacement, Maj la coupe)
; la pièce reste en place et le document n'est pas touché avant le lâcher. Au lâcher,
:func:`~freecad.menuiserie.api.make_repeat` crée une répétition de **une copie** liée, en
``CountAndStep`` : axe X, Y ou Z du repère du conteneur (le document à la racine), pas = distance
parcourue, ``reverse`` si le déplacement va dans le sens négatif de l'axe. C'est une seule
transaction (« Répéter », un Ctrl+Z). Le panneau « Modifier la répétition » s'ouvre aussitôt
(nombre, pas). Échap ne laisse rien : aucune transaction n'a été ouverte.

Une flèche est tirée **sur un seul axe de la pièce** ; la copie n'est donc possible que si cet axe
est un axe X, Y ou Z du repère du conteneur de la pièce, celui de son ``Placement`` (pièce non
tournée, ou tournée d'un multiple de 90° ; le conteneur peut, lui, être tourné de n'importe quel
angle) : sinon le geste est refusé avec un message, plutôt que de répéter dans une direction que le
panneau ne sait pas montrer. Une copie liée ne se copie pas par glissement (elle suit déjà sa
source) : son placement est piloté par la répétition, donc elle ne porte aucune flèche à saisir ; si
elle en portait une, :func:`check_copyable` refuserait le geste avec un message (copier la source, «
Modifier la répétition », ou dissocier la copie d'abord).

Ctrl et FreeCAD : le filtre ne prend que Ctrl + clic gauche **sur une flèche** de la pièce
sélectionnée seule ; Ctrl + clic ailleurs (sélection multiple, dont Ctrl+clic sur un objet sous une
poignée ou un anneau) et tous les raccourcis clavier avec Ctrl (aucun évènement clavier de Ctrl
n'est consommé) restent à FreeCAD. Comme un clic simple, un Ctrl + clic sur une flèche est consommé,
qu'il glisse ou non : sans glissement, rien n'est créé.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import RepeatAxis
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.part_drag import DragMemento
from freecad.menuiserie.features.repeat import is_copy
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.drag.copy_rules import copy_params, global_axis
from freecad.menuiserie.gui.drag.geometry import parse_key
from freecad.menuiserie.gui.drag.parts import Grab
from freecad.menuiserie.gui.drag.states import Moving
from freecad.menuiserie.gui.task_panels.repeat import start_editing
from freecad.menuiserie.gui.view_providers.repeat import ensure_view_provider

if TYPE_CHECKING:
    from freecad.menuiserie.gui.drag.session import DragSession

__all__ = ["Copying", "check_copyable", "copy_axis", "passive_memento"]

_IS_A_COPY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est une copie liée à une répétition : elle ne se copie pas par glissement. "
    "Copiez sa source, ou utilisez « Modifier la répétition » (nombre, pas), ou dissociez-la "
    "d'abord.",
)
_PANEL_OPEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Copie par glissement impossible : un panneau de tâche est ouvert. Validez-le ou annulez-le "
    "d'abord.",
)


def copy_axis(frame: Frame, axis: int) -> tuple[RepeatAxis, float]:
    """:func:`~freecad.menuiserie.gui.drag.copy_rules.global_axis` avec le refus traduit."""
    with translated_errors():
        return global_axis(frame, axis)


def check_copyable(part: DocumentObject) -> None:
    """``ValueError`` traduite si ``part`` ne peut pas être copiée par glissement : copie déjà
    liée, ou panneau de tâche ouvert (celui de la copie ne pourrait pas s'ouvrir)."""
    if is_copy(part):
        raise ValueError(translated(_IS_A_COPY, {"label": quoted_value(part.Label)}))
    if Gui.Control.activeDialog():
        raise ValueError(translated(_PANEL_OPEN))


def passive_memento(part: DocumentObject) -> DragMemento:
    """Mémento qui ne touche à rien : la pièce n'est pas écrite par une copie."""
    return DragMemento(
        part,
        App.Placement(part.Placement),
        part.Length.Value,
        part.Width.Value,
        part.Thickness.Value,
        {},
        {},
        frozenset(),
    )


class Copying(Moving):
    """Flèche tirée avec Ctrl : un fantôme suit la souris le long de l'axe (aimanté sauf Maj), la
    pièce ne bouge pas. Au relâchement, répétition d'une copie puis panneau « Modifier la
    répétition » (voir le module)."""

    def __init__(self, grab: Grab, axis: RepeatAxis, sign: float) -> None:
        super().__init__(grab)
        self.axis, self.sign = axis, sign
        self.ghost: Vec3 | None = Vec3(0.0, 0.0, 0.0)  # décalage du fantôme, repère de la pièce

    def _local_axis(self) -> int:
        local = parse_key(self.grabbed)
        return local if isinstance(local, int) else 0

    def apply(self, session: DragSession, delta: float) -> None:
        result = self.solve(self._local_axis(), delta)
        self.ghost = result.delta
        session.written([self.guides[hit.guide] for hit in result.hits], self.frame)

    def escape(self, session: DragSession) -> bool:
        """Échap : fantôme enlevé, rien n'a été écrit ; le relâchement du bouton est consommé."""
        session.swallow_release = True
        session.leave()
        return True

    def _finish(self, session: DragSession) -> None:
        """Relâchement : une copie liée est créée (une transaction) puis son panneau s'ouvre ;
        un refus de l'api est affiché, rien n'est créé."""
        part = self.target.obj
        offset = self.ghost.component(self._local_axis()) if self.ghost else 0.0
        session.leave()
        params = copy_params(self.axis, self.sign, offset)
        if params is None:
            return
        try:
            repeat = api.make_repeat([part], params)
        except (TypeError, ValueError, KeyError) as error:
            report_refusal(str(error.args[0] if isinstance(error, KeyError) else error))
            return
        ensure_view_provider(repeat)
        start_editing(repeat)
        session.refresh()
