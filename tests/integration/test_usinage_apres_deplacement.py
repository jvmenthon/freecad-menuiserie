# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces usinées après un déplacement à la souris (tenon-mortaise gardé réalisable).

Même chemin que le glissement des flèches, sans interface : ``begin_drag`` / ``move_part`` /
``end_drag`` dans une seule transaction, puis le recalcul du document. La pièce usinée visible
doit avoir la forme recalculée (mortaise creusée, tenon présent), suivre sa brute, la brute
rester cachée, et rien ne doit rester « Touched » ou invalide."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import Cadre, build_frame, stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
geometry = pytest.importorskip("freecad.menuiserie.core.geometry")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")

Vec3 = geometry.Vec3
TRANSACTION = "Déplacer la pièce"
# (pièce déplacée, déplacement dans son repère, déplacement dans le repère du document) : la
# traverse T1 (invitée, porte le tenon) glisse le long de la rive de M1 (hôte, porte la mortaise).
CASES = {
    "invitee": ("T1", Vec3(0, -20, 0), App.Vector(20, 0, 0)),
    "hote": ("M1", Vec3(-100, 0, 0), App.Vector(-100, 0, 0)),
}


def never_asked(labels: Any) -> bool:
    raise AssertionError(f"assemblage déclaré défait alors qu'il est réalisable : {labels}")


def check_state(montage: Cadre, volumes: dict[str, float]) -> None:
    for mark, volume in volumes.items():
        blank = montage.parts[mark]
        machined = montage.machined(mark)
        assert machined.Visibility is True, mark
        assert blank.Visibility is False, mark
        assert machined.Placement == blank.Placement, mark
        assert machined.Shape.Placement == blank.Placement, mark
        assert machined.Shape.isValid() and len(machined.Shape.Solids) == 1, mark
        assert machined.Shape.Volume == pytest.approx(volume), mark
    assert stale_or_invalid(montage.doc) == []


def assembled(document: Any) -> tuple[Cadre, dict[str, float]]:
    montage = build_frame(document)
    montage.assemble((("M1", "T1"),))
    document.recompute()
    volumes = {name: montage.volume(name) for name in ("M1", "T1")}
    assert volumes["M1"] < montage.parts["M1"].Shape.Volume  # mortaise creusée
    assert volumes["T1"] > montage.parts["T1"].Shape.Volume  # tenon présent
    return montage, volumes


@pytest.mark.parametrize("case", sorted(CASES))
def test_pieces_usinees_apres_un_glissement(document: Any, case: str) -> None:
    mark, local, world = CASES[case]
    montage, volumes = assembled(document)
    before = {name: montage.machined(name).Shape.BoundBox.Center for name in volumes}

    document.openTransaction(TRANSACTION)
    memento = drag.begin_drag(montage.machined(mark))  # la souris saisit la pièce visible
    drag.move_part(memento, local)
    messages = drag.end_drag(memento, never_asked)
    document.commitTransaction()

    assert messages == []
    check_state(montage, volumes)
    moved = montage.machined(mark).Shape.BoundBox.Center
    assert moved.sub(before[mark]).isEqual(world, 1e-6)
    other = "M1" if mark == "T1" else "T1"
    assert montage.machined(other).Shape.BoundBox.Center.isEqual(before[other], 1e-6)


@pytest.mark.parametrize("case", sorted(CASES))
def test_pieces_usinees_apres_annulation_du_glissement(document: Any, case: str) -> None:
    """Annuler la transaction (Ctrl+Z) rend l'état d'avant, tout visible."""
    mark, local, _ = CASES[case]
    montage, volumes = assembled(document)
    document.openTransaction(TRANSACTION)
    memento = drag.begin_drag(montage.machined(mark))
    drag.move_part(memento, local)
    drag.end_drag(memento, never_asked)
    document.commitTransaction()
    document.undo()
    document.recompute()
    assert montage.machined(mark).Visibility is True
    assert stale_or_invalid(document) == []
    assert montage.machined(mark).Shape.Volume == pytest.approx(volumes[mark])


@pytest.mark.parametrize("shift", [-10.0, 10.0, -40.0])
def test_traverse_tiree_dans_son_axe(document: Any, shift: float) -> None:
    """La traverse (tenon) tirée le long de sa longueur, vers le montant (recouvrement) ou à
    l'opposé (jour) : soit l'assemblage tient et les deux pièces restent usinées et visibles,
    soit il est défait et la fenêtre de choix en est informée ; jamais de pièce disparue."""
    montage, volumes = assembled(document)
    asked: list[Any] = []

    def choose(labels: Any) -> bool:
        asked.append(list(labels))
        return False  # « Annuler le déplacement »

    document.openTransaction(TRANSACTION)
    memento = drag.begin_drag(montage.machined("T1"))
    drag.move_part(memento, Vec3(shift, 0, 0))
    try:
        drag.end_drag(memento, choose)
        document.commitTransaction()
    except drag.DragCancelledError:
        document.abortTransaction()
    if asked:  # annulé : tout est revenu (l'annulation de FreeCAD marque les objets à recalculer)
        document.recompute()
        check_state(montage, volumes)
        return
    for mark in volumes:
        machined = montage.machined(mark)
        info = (shift, mark, machined.Shape.Volume, machined.Shape.isValid(), machined.State)
        assert machined.Visibility is True, info
        assert montage.parts[mark].Visibility is False, info
        assert machined.Shape.Volume > 0, info
        assert machined.Placement == montage.parts[mark].Placement, info
    assert stale_or_invalid(document) == [], (shift, stale_or_invalid(document))
