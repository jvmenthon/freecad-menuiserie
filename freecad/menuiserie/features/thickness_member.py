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

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_bindings import (
    members_of,
    notice_messages,
    remove_bindings,
)
from freecad.menuiserie.features.furniture_envelope import reframe
from freecad.menuiserie.features.furniture_relink import bind_furniture

__all__ = ["MemberFreedom"]


class MemberFreedom:
    """Liaisons de l'ensemble de ``part`` mises de côté jusqu'à :meth:`finish` ; sans effet pour
    une pièce hors ensemble (:attr:`furniture` vaut alors ``None``)."""

    def __init__(self, part: DocumentObject) -> None:
        self.furniture = furniture_of(part)
        self._open = self.furniture is not None
        if self.furniture is not None:
            for member in members_of(self.furniture):
                with writing(member):
                    remove_bindings(member)

    def finish(self) -> list[str]:
        """Boîte de l'ensemble recalée sur ses membres, membres reliés d'après la géométrie
        actuelle ; renvoie les avertissements. Une seule fois : sans effet ensuite."""
        if not self._open or self.furniture is None:
            return []
        self._open = False
        reframe(self.furniture)
        return list(notice_messages(bind_furniture(self.furniture)))
