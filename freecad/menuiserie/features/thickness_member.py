# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce d'ensemble assemblée : mêmes choix qu'une pièce seule (ADR 0060, jv
2026-11-17), puis l'ensemble est relié d'après le résultat.

Le temps de l'encadré, les liaisons de l'atelier des membres de l'ensemble sont mises de côté
(:class:`MemberFreedom`) : les choix déplacent ou prolongent ses membres comme des pièces seules,
sans qu'un recalcul ne les ramène. À la fin (« OK », autre saisie), la boîte de l'ensemble est
recalée sur l'enveloppe de ses membres (ADR 0049) et tous ses membres sont reliés d'après la
géométrie obtenue (:func:`~freecad.menuiserie.features.furniture_relink.bind_furniture`). Tout se
passe dans la transaction du panneau : « Annuler » rend les liaisons. Aucun import de
``FreeCADGui``.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_bindings import (
    members_of,
    notice_messages,
    remove_bindings,
    workshop_expressions,
)
from freecad.menuiserie.features.furniture_container import set_member_expression
from freecad.menuiserie.features.furniture_envelope import frame_of, reframe, restore_frame
from freecad.menuiserie.features.furniture_relink import bind_furniture
from freecad.menuiserie.features.i18n import translated

__all__ = ["MemberFreedom"]

_NOT_RELINKED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "L'ensemble n'a pas pu être relié après le changement d'épaisseur : ses liaisons d'avant "
    "sont rétablies et le recalcul replace ses pièces d'après elles. {error}",
)


class _Aside:
    """Liaisons de l'atelier d'un membre (expressions et enregistrement ``FurnitureBindings``),
    gardées pour être rendues si l'ensemble ne peut pas être relié."""

    def __init__(self, member: DocumentObject) -> None:
        self.member = member
        self.texts = dict(workshop_expressions(member))
        recorded = "FurnitureBindings" in member.PropertiesList
        self.recorded = dict(member.FurnitureBindings) if recorded else None

    def remove(self) -> None:
        with writing(self.member):
            remove_bindings(self.member)

    def give_back(self) -> None:
        with writing(self.member):
            remove_bindings(self.member)
            for prop, text in self.texts.items():
                set_member_expression(self.member, prop, text)
            if self.recorded is not None:
                self.member.FurnitureBindings = self.recorded


class MemberFreedom:
    """Liaisons de l'ensemble de ``part`` mises de côté jusqu'à :meth:`finish` ; sans effet pour
    une pièce hors ensemble (:attr:`furniture` vaut alors ``None``). L'enregistrement
    ``FurnitureBindings`` des membres est laissé tel quel pendant ce temps : il sert à rendre
    les liaisons si l'ensemble ne peut pas être relié."""

    def __init__(self, part: DocumentObject) -> None:
        self.furniture = furniture_of(part)
        self._aside: list[_Aside] = []
        if self.furniture is None:
            return
        try:
            for member in members_of(self.furniture):
                aside = _Aside(member)
                self._aside.append(aside)
                aside.remove()
        except Exception:  # pylint: disable=broad-exception-caught  # rendu puis relevé
            self._give_back()
            raise

    def _give_back(self) -> None:
        for aside in self._aside:
            aside.give_back()
        self._aside = []

    def finish(self) -> list[str]:
        """Boîte de l'ensemble recalée sur ses membres, membres reliés d'après la géométrie
        actuelle ; renvoie les avertissements. Si l'ensemble ne peut pas être relié (cycle avec
        une formule de l'utilisateur, par exemple), sa boîte et ses liaisons d'avant sont rendues
        et ``ValueError`` traduite le dit. Une seule fois : sans effet ensuite."""
        if self.furniture is None or not self._aside:
            return []
        frame = frame_of(self.furniture)
        try:
            reframe(self.furniture)
            messages = list(notice_messages(bind_furniture(self.furniture)))
        except Exception as error:  # pylint: disable=broad-exception-caught  # rendu, relevé
            restore_frame(self.furniture, frame)
            self._give_back()
            raise ValueError(translated(_NOT_RELINKED, {"error": str(error)})) from error
        self._aside = []
        return messages
