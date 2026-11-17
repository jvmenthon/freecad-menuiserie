# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensemble relié d'après sa géométrie, sa boîte et celles de ses parents recalées (ADR 0065).

Après un geste qui change ses membres (épaisseur choisie dans l'encadré, sous-ensemble déplacé,
pièce déplacée à la souris), la boîte de l'ensemble est recalée sur ses membres
(:func:`~freecad.menuiserie.features.furniture_envelope.reframe`), ses membres sont reliés, puis
on remonte : la boîte du parent est recalée à son tour et il est relié, jusqu'à l'ensemble de plus
haut niveau. En cas d'erreur, boîtes, positions et liaisons sont rendues avant de relancer. Aucun
import de ``FreeCADGui``.
"""

from __future__ import annotations

import FreeCAD as App

from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.core.geometry import Box
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture, writing
from freecad.menuiserie.features.furniture_bindings import (
    members_of,
    remove_bindings,
    workshop_expressions,
)
from freecad.menuiserie.features.furniture_container import set_member_expression, std_part_of
from freecad.menuiserie.features.furniture_drag_state import write_std_placement
from freecad.menuiserie.features.furniture_envelope import frame_of, reframe, restore_frame
from freecad.menuiserie.features.furniture_relink import bind_furniture
from freecad.menuiserie.features.part_drag import write_placement
from freecad.menuiserie.features.thickness_common import is_alive

__all__ = ["KeptBindings", "relink_framed"]


class KeptBindings:
    """Liaisons de l'atelier d'un membre (expressions et enregistrement ``FurnitureBindings``),
    gardées pour être rendues si l'ensemble ne peut pas être relié."""

    def __init__(self, member: DocumentObject) -> None:
        self.member = member
        self.texts = dict(workshop_expressions(member))
        recorded = "FurnitureBindings" in member.PropertiesList
        self.recorded = dict(member.FurnitureBindings) if recorded else None

    def remove(self) -> None:
        """Liaisons de l'atelier retirées du membre (mises de côté)."""
        with writing(self.member):
            remove_bindings(self.member)

    def give_back(self) -> None:
        """Liaisons gardées rendues au membre (sans effet s'il a été supprimé)."""
        if not is_alive(self.member):  # supprimé entre-temps : rien à rendre
            return
        with writing(self.member):
            remove_bindings(self.member)
            for prop, text in self.texts.items():
                set_member_expression(self.member, prop, text)
            if self.recorded is not None:
                self.member.FurnitureBindings = self.recorded


class _Snapshot:
    """Boîtes des ensembles de la chaîne, placements de leurs membres et de leurs Std Parts."""

    def __init__(self, chain: list[DocumentObject]) -> None:
        self.frames: list[tuple[DocumentObject, Box]] = [(f, frame_of(f)) for f in chain]
        self.parts: list[tuple[DocumentObject, App.Placement]] = []
        self.raws: list[tuple[DocumentObject, App.Placement]] = []
        self.bindings: list[KeptBindings] = []
        for furniture in chain:
            self._keep_part(furniture)
            for member in members_of(furniture):
                self.bindings.append(KeptBindings(member))
                if is_furniture(member):
                    self._keep_part(member)
                else:
                    self.raws.append((member, App.Placement(member.Placement)))

    def _keep_part(self, furniture: DocumentObject) -> None:
        part = std_part_of(furniture)
        if part is not None:
            self.parts.append((part, App.Placement(part.Placement)))

    def restore(self) -> None:
        for furniture, frame in self.frames:
            restore_frame(furniture, frame)
        for part, placement in self.parts:
            write_std_placement(part, placement)
        for raw, placement in self.raws:
            if is_alive(raw) and not raw.Placement.isSame(placement, 1e-9):
                write_placement(raw, placement)
        for kept in self.bindings:
            kept.give_back()


def _chain(furniture: DocumentObject) -> list[DocumentObject]:
    """``furniture`` et ses parents, du plus proche au plus haut."""
    found = [furniture]
    parent = furniture_of(furniture)
    while parent is not None and parent not in found:
        found.append(parent)
        parent = furniture_of(parent)
    return found


def relink_framed(furniture: DocumentObject) -> list[Notice]:
    """Boîte de ``furniture`` recalée sur ses membres et membres reliés d'après la géométrie
    actuelle, puis de même pour chaque parent ; renvoie les avertissements. ``ValueError``
    traduite (liaison impossible) : boîtes, positions et liaisons sont rendues, l'erreur est
    relancée. Les liaisons que chaque parent pose sur un sous-ensemble de la chaîne (cotes,
    position de son Std Part) sont retirées d'abord : elles ramèneraient sa boîte au recalcul ;
    le parent les repose ensuite d'après la boîte recalée."""
    chain = _chain(furniture)
    snapshot = _Snapshot(chain)
    notices: list[Notice] = []
    try:
        for level in chain[:-1]:  # sous-ensembles : liaisons posées par leur parent
            with writing(level):
                remove_bindings(level)
        for level in chain:
            reframe(level)
            notices.extend(bind_furniture(level))
    except Exception:
        snapshot.restore()
        raise
    return notices
