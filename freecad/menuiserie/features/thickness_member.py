# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce d'ensemble assemblée : mêmes choix qu'une pièce seule (ADR 0060, jv
2026-11-17), puis l'ensemble est relié d'après le résultat.

Le temps de l'encadré, les liaisons de l'atelier des membres de l'ensemble sont mises de côté
(:class:`MemberFreedom`) : les choix déplacent ou prolongent ses membres comme des pièces seules,
sans qu'un recalcul ne les ramène. À la fin (« OK », autre saisie), la boîte de l'ensemble est
recalée sur l'enveloppe de ses membres et ses membres sont reliés d'après la géométrie obtenue,
puis de même pour chaque parent (ADR 0065,
:func:`~freecad.menuiserie.features.furniture_reframe.relink_framed`). Tout se passe dans la
transaction du panneau : « Annuler » rend les liaisons. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.furniture_bindings import members_of, notice_messages
from freecad.menuiserie.features.furniture_reframe import KeptBindings, relink_framed

__all__ = ["MemberFreedom"]


class MemberFreedom:
    """Liaisons de l'ensemble de ``part`` mises de côté jusqu'à :meth:`finish` ; sans effet pour
    une pièce hors ensemble (:attr:`furniture` vaut alors ``None``). L'enregistrement
    ``FurnitureBindings`` des membres est laissé tel quel pendant ce temps : il sert à rendre
    les liaisons si l'ensemble ne peut pas être relié."""

    def __init__(self, part: DocumentObject) -> None:
        self.furniture = furniture_of(part)
        self._aside: list[KeptBindings] = []
        if self.furniture is None:
            return
        try:
            for member in members_of(self.furniture):
                aside = KeptBindings(member)
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
        une formule de l'utilisateur, par exemple), ses boîtes et ses liaisons d'avant sont
        rendues et la ``ValueError`` traduite de
        :func:`~freecad.menuiserie.features.furniture_reframe.relink_framed` est relancée. Une
        seule fois : sans effet ensuite."""
        if self.furniture is None or not self._aside:
            return []
        try:
            messages = list(notice_messages(relink_framed(self.furniture)))
        except Exception:  # pylint: disable=broad-exception-caught  # rendu puis relevé
            self._give_back()
            raise  # ValueError traduite par relink_framed
        self._aside = []
        return messages
