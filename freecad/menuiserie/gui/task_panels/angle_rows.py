# SPDX-License-Identifier: LGPL-2.1-or-later
"""Champs d'angle X, Y, Z du groupe « Rotation » du panneau de la pièce de bois (RO-c, ADR 0025).

Les champs montrent les trois angles du ``Placement`` de la brute (degrés, au dixième). Ils
acceptent de -360 à 360 sur les trois axes (jv) : la pièce tourne comme saisi, puis les champs
sont recalculés à l'enregistrement (fin de saisie) en la forme canonique de :func:`angles_of`
(X et Z dans [-180, 180], Y dans [-90, 90]). Une saisie tourne la pièce aussitôt autour de
son centre (:func:`rotate_to`) et l'aperçu de la seule brute suit, au plus 30 fois par seconde
(comme une poignée de taille) ; en fin de saisie (``editingFinished``), les assemblages sont
contrôlés et le document recalculé comme au relâchement d'un glissement (:func:`end_rotation`,
fenêtre de ``gui/joint_choice``) : « Annuler » remet l'angle d'avant la saisie. Les boutons de
quart de tour, un glissement et un anneau font relire les champs par :meth:`AngleRows.show`,
signaux bloqués : pas de boucle.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Final

from PySide import QtCore

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.rotation import Angles, angles_of
from freecad.menuiserie.features.drag_joints import JointChoice
from freecad.menuiserie.features.freecad_types import DocumentObject, placement_expression
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.part_drag import (
    DragCancelledError,
    DragMemento,
    begin_drag,
    raw_part,
    recompute_blank,
)
from freecad.menuiserie.features.part_rotate import end_rotation, rotate_to
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.gui.drag.geometry import Throttle
from freecad.menuiserie.gui.task_panels.base import connect, weak_callback

__all__ = ["ANGLE_FIELDS", "AngleRows"]

Widget = Any

# Champs d'angle : widget, étiquette associée (axes X, Y, Z du document).
ANGLE_FIELDS: Final = (
    ("angleXEdit", "angleXLabel"),
    ("angleYEdit", "angleYLabel"),
    ("angleZEdit", "angleZLabel"),
)
MAX_ANGLE_DEGREES: Final = (360.0, 360.0, 360.0)  # recalculés en fin de saisie (jv)
DECIMALS: Final = 1
_DRIVEN_BY_FURNITURE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Position pilotée par l'ensemble")
_DRIVEN_BY_FORMULA: Final = QT_TRANSLATE_NOOP("Menuiserie", "Position pilotée par une formule")


class AngleRows:
    """Les trois champs d'angle du formulaire ``form`` pour la pièce ``obj``.

    ``on_edit`` : appelé à chaque saisie (en création, le panneau arrête l'accrochage) ;
    ``on_settled`` : appelé quand une saisie est terminée, acceptée ou annulée (le panneau
    recalcule son aperçu) ; ``choose`` : choix de la fenêtre « Assemblage défait ». Les rappels
    du panneau ne sont pas gardés en vie (pas de cycle avec lui)."""

    def __init__(
        self,
        form: Widget,
        obj: DocumentObject,
        on_edit: Callable[[], None],
        on_settled: Callable[[], None],
        choose: JointChoice,
    ) -> None:
        self._form = form
        self._obj = obj
        self._on_edit = weak_callback(on_edit)
        self._on_settled = weak_callback(on_settled)
        self._choose = choose
        self._memento: DragMemento | None = None  # état d'avant la saisie en cours
        self._throttle = Throttle()
        self._scheduled = False

    def _fields(self) -> list[Widget]:
        return [getattr(self._form, name) for name, _label in ANGLE_FIELDS]

    def setup(self) -> None:
        """Bornes et pas des champs ; grisés, avec la raison en infobulle, si une expression
        pilote la position de la pièce (C4)."""
        for field, limit in zip(self._fields(), MAX_ANGLE_DEGREES, strict=True):
            field.setProperty("minimum", -limit)
            field.setProperty("maximum", limit)
            field.setProperty("singleStep", 1.0)
            field.setProperty("decimals", DECIMALS)
        if placement_expression(self._obj) is None:
            return
        furniture = getattr(self._obj, "Furniture", None)
        reason = translated(_DRIVEN_BY_FURNITURE if is_furniture(furniture) else _DRIVEN_BY_FORMULA)
        for field_name, label_name in ANGLE_FIELDS:
            for name in (field_name, label_name):
                widget = getattr(self._form, name)
                widget.setEnabled(False)
                widget.setToolTip(reason)

    def connect_signals(self) -> None:
        """Saisie en direct (``valueChanged``) et fin de saisie (``editingFinished``)."""
        for field in self._fields():
            connect(field, "valueChanged(double)", self._on_value_changed)
            connect(field, "editingFinished()", self.finish)

    def angles(self) -> Angles:
        """Angles X, Y, Z lus dans les champs, en degrés."""
        x, y, z = (float(field.property("rawValue")) for field in self._fields())
        return (x, y, z)

    def show(self) -> None:
        """Angles du ``Placement`` de la brute dans les champs, signaux bloqués pendant
        l'écriture (C3)."""
        raw = raw_part(self._obj)
        angles = angles_of(rigid_transform(raw.Placement).rotation)
        for field, angle in zip(self._fields(), angles, strict=True):
            blocked = field.blockSignals(True)
            try:
                field.setProperty("rawValue", angle)
            finally:
                field.blockSignals(blocked)

    # --- Saisie ---------------------------------------------------------------------------

    def _on_value_changed(self, _value: float) -> None:
        """Un champ a changé : la pièce tourne aussitôt, l'aperçu de la brute suit."""
        memento = self._memento
        if memento is None:
            memento = self._memento = begin_drag(self._obj)
        self._on_edit()
        try:
            written = rotate_to(self._obj, self.angles(), memento.aside)
        except ValueError as error:  # angle non fini : rien n'est écrit
            report_warning(str(error))
            return
        if written:
            self._preview_later()

    def _preview_later(self) -> None:
        """Aperçu de la brute, 30 fois par seconde au plus ; le dernier angle saisi est toujours
        montré (appel différé quand la cadence est dépassée)."""
        now = time.monotonic()
        if self._throttle.ready(now):
            recompute_blank(raw_part(self._obj))
        elif not self._scheduled:
            self._scheduled = True
            wait = round(self._throttle.wait(now) * 1000) + 1
            QtCore.QTimer.singleShot(wait, weak_callback(self._later))

    def _later(self) -> None:
        self._scheduled = False
        if self._memento is not None:
            self._throttle.ready(time.monotonic())
            recompute_blank(raw_part(self._obj))

    def finish(self) -> None:
        """Fin de la saisie : assemblages contrôlés et document recalculé (C2). Si la rotation
        défait des assemblages et que l'utilisateur annule, l'angle d'avant la saisie revient.
        Sans saisie en cours, ne fait rien."""
        memento, self._memento = self._memento, None
        if memento is None:
            return
        try:
            warnings = end_rotation(memento, self._choose)
        except DragCancelledError:  # « Annuler » : la brute est revenue
            warnings = []
        except ValueError as error:  # refusée (rangée bloquée) : la brute est revenue
            report_warning(str(error))
            warnings = []
        for warning in warnings:
            report_warning(warning)
        self.show()
        self._on_settled()

    def drop(self) -> None:
        """Saisie abandonnée sans contrôle : un glissement ou la fermeture du panneau prend le
        relais, plus rien n'est différé."""
        self._memento = None
