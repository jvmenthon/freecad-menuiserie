# SPDX-License-Identifier: LGPL-2.1-or-later
"""Partie « accrochage » du panneau de la pièce de bois (J6d) : ligne « Contre : … », notices de
l'accrochage et case « Ajouter à l'ensemble ».

Séparée de :mod:`freecad.menuiserie.gui.task_panels.wood_part` pour garder chaque panneau
court ; les widgets sont ceux du formulaire du panneau, que cette classe ne garde que le temps
de la vie du panneau.
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_members import quoted_label
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.placement import SnapSession
from freecad.menuiserie.features.snap_geometry import global_shape
from freecad.menuiserie.features.snap_targets import touches

_AGAINST: Final = QT_TRANSLATE_NOOP("Menuiserie", "Contre : {elements}")
_JOIN_FURNITURE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ajouter à l'ensemble « {label} »")
_NOT_TOUCHING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La pièce ne touche pas « {target} » : changez son orientation avec X, Y, Z ou ses cotes.",
)
_FURNITURE_REFUSED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La pièce est créée hors de l'ensemble « {label} » : {reason}",
)
_FURNITURE_GONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "cet ensemble n'existe plus.")


class SnapRows:
    """Lignes d'accrochage du formulaire ``form`` pour la pièce ``obj`` en création (rien si
    ``session`` est ``None``, en modification)."""

    def __init__(self, form: Any, obj: DocumentObject, session: SnapSession | None) -> None:
        self._form = form
        self._obj = obj
        self._session = session
        self._furniture_params: dict[str, str] = {}  # libellé de l'ensemble de la case
        self._setup()

    def _setup(self) -> None:
        """Case « Ajouter à l'ensemble » (cochée par défaut, Q3) quand le premier élément
        sélectionné appartient à un ensemble ; texte posé une fois pour garder la case cochée."""
        session = self._session
        if session is None:
            return
        furniture = session.furniture if session.targets else None
        if furniture is not None:
            self._furniture_params = quoted_label(furniture)
            self._form.furnitureCheck.setText(translated(_JOIN_FURNITURE, quoted_label(furniture)))
            self._form.furnitureCheck.setVisible(True)
            self._form.furnitureCheck.setChecked(True)
        self.show()

    def show(self) -> None:
        """Ligne « Contre : … » et notices (éléments ignorés, avis de l'accrochage, éléments que
        la pièce ne touche pas) ; rien sans sélection."""
        session = self._session
        if session is None:
            return
        used = ", ".join(session.used)
        self._form.snapLabel.setText(translated(_AGAINST, {"elements": used}) if used else "")
        self._form.snapLabel.setVisible(bool(used))
        notices = [
            *session.ignored,
            *(translated(notice.template, notice.params) for notice in session.notices),
            *(translated(_NOT_TOUCHING, {"target": name}) for name in self._untouched(session)),
        ]
        self._form.snapNotices.setText("\n".join(notices))
        self._form.snapNotices.setVisible(bool(notices))

    def _untouched(self, session: SnapSession) -> list[str]:
        """Éléments retenus que la pièce, une fois recalculée, ne touche pas (T3)."""
        if not session.used or self._obj.Shape.isNull():
            return []
        part = global_shape(self._obj)
        pairs = zip(session.targets, session.shapes, strict=False)
        return [
            target.name
            for target, shape in pairs
            if target.name in session.used and not touches(part, shape)
        ]

    def join_furniture(self) -> None:
        """Entrée dans l'ensemble de l'élément touché (options par défaut de J4, dans la même
        transaction) ; refusée : la pièce reste hors de l'ensemble, avec un message traduit."""
        session = self._session
        if (
            session is None
            or session.furniture is None
            or not self._form.furnitureCheck.isChecked()
        ):
            return
        if _furniture_gone(session.furniture, self._obj.Document):
            reason = translated(_FURNITURE_GONE)
            report_warning(
                translated(_FURNITURE_REFUSED, {**self._furniture_params, "reason": reason})
            )
            return
        try:
            api.add_to_furniture(session.furniture, [self._obj])
        except (TypeError, ValueError) as error:
            params = {**quoted_label(session.furniture), "reason": str(error)}
            report_warning(translated(_FURNITURE_REFUSED, params))


def _furniture_gone(furniture: DocumentObject, document: DocumentObject) -> bool:
    """Vrai si l'ensemble a été supprimé pendant que le panneau était ouvert. Dans une
    transaction ouverte, FreeCAD garde l'objet supprimé pour l'annulation : on vérifie qu'il est
    encore dans le document."""
    try:
        return not is_furniture(furniture) or document.getObject(furniture.Name) is None
    except Exception:  # pylint: disable=broad-exception-caught  # objet supprimé : type variable
        return True
