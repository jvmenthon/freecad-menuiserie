# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages recopiés par une répétition en grille (ADR 0045, spécification § Grille).

L'assemblage entre copies homologues vise la même cellule ``(i, j, k)`` ; une pièce fixe reçoit un
assemblage par copie ; modifier la grille garde les assemblages enfants des cellules conservées.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.aides_grille import Line, Reopen, X, Z, grid
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_repetition_assemblages import Scene, all_children, joints_of

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")
repeat_joints = pytest.importorskip("freecad.menuiserie.features.repeat_joints")


def x_by_z(columns: int = 3, rows: int = 2, **values: Any) -> Any:
    """``columns`` x ``rows`` éléments sur X (pas 100 mm) et Z (pas 4 mm, le tenon reste dans
    l'épaisseur de la traverse)."""
    return grid(Line(X, columns, 100.0), Line(Z, rows, 4.0), **values)


def cell(part: Any) -> tuple[int, int, int]:
    found: tuple[int, int, int] = repeat.cell_of(part)
    return found


def copies(rep: Any) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep)
    return found


@pytest.fixture
def scene(document: Any) -> Scene:
    return Scene(document)


def test_une_piece_fixe_recoit_un_assemblage_par_copie(scene: Scene) -> None:
    rep = api.make_repeat([scene.bar], x_by_z())
    assert len(copies(rep)) == 5
    assert len(joints_of(scene.doc)) == 2 + 5 * 2  # origines + deux traverses par copie
    for traverse in (scene.low, scene.high):
        assert len(api.machined_part_of(traverse).Joints) == 1 + 5
    for child in all_children(rep):
        assert child.GuestPart in copies(rep) and child.HostPart in (scene.low, scene.high)
        assert repeat_joints.origin_of(child) in scene.joints
    assert stale_or_invalid(scene.doc) == []


def test_assemblage_entre_deux_sources_vise_la_meme_cellule(scene: Scene) -> None:
    rep = api.make_repeat([scene.low, scene.bar], x_by_z(2, 2))
    between = [
        child
        for child in joints_of(scene.doc)
        if repeat_joints.origin_of(child) is not None
        and child.HostPart in copies(rep)
        and child.GuestPart in copies(rep)
    ]
    assert len(between) == 3  # les trois cellules de la grille 2 x 2
    assert {cell(child.HostPart) for child in between} == {cell(c) for c in copies(rep)[:3]}
    for child in between:
        assert cell(child.HostPart) == cell(child.GuestPart)
        assert (
            child.HostPart.RepeatSource == scene.low and child.GuestPart.RepeatSource == scene.bar
        )
    fixed = [
        j for j in joints_of(scene.doc) if j.HostPart == scene.high and j.GuestPart in copies(rep)
    ]
    assert len(fixed) == 3  # la traverse haute, fixe, reçoit le tenon de chaque copie du barreau


def test_modifier_la_grille_garde_les_assemblages_des_cellules_conservees(scene: Scene) -> None:
    rep = api.make_repeat([scene.bar], x_by_z())
    kept = {child.Name: cell(child.GuestPart) for child in all_children(rep)}
    api.edit_repeat(rep, x_by_z(2, 2))  # la colonne i = 2 sort : une copie en moins en Z = 0 et 1
    remaining = {child.Name for child in all_children(rep)}
    assert len(copies(rep)) == 3 and len(remaining) == 6
    assert remaining == {name for name, c in kept.items() if c[0] < 2}  # mêmes objets
    assert len(joints_of(scene.doc)) == 2 + 6
    api.edit_repeat(rep, x_by_z(3, 2))
    assert len(joints_of(scene.doc)) == 12
    assert remaining < {
        child.Name for child in all_children(rep)
    }  # les enfants gardés sont les mêmes
    assert stale_or_invalid(scene.doc) == []


def test_changer_le_pas_garde_les_assemblages_enfants(scene: Scene) -> None:
    rep = api.make_repeat([scene.bar], x_by_z())
    names = {child.Name for child in all_children(rep)}
    api.edit_repeat(rep, grid(Line(X, 3, 150.0), Line(Z, 2, 6.0)))
    assert {child.Name for child in all_children(rep)} == names
    assert len(joints_of(scene.doc)) == 12


def test_recopier_les_assemblages_coche_puis_decoche(scene: Scene) -> None:
    rep = api.make_repeat([scene.bar], x_by_z(copy_joints=False))
    assert len(joints_of(scene.doc)) == 2 and len(copies(rep)) == 5
    api.edit_repeat(rep, x_by_z(copy_joints=True))
    assert len(joints_of(scene.doc)) == 12
    api.edit_repeat(rep, x_by_z(copy_joints=False))
    assert len(joints_of(scene.doc)) == 2 and len(copies(rep)) == 5


def test_une_copie_dissociee_garde_ses_assemblages_et_ne_revient_pas(scene: Scene) -> None:
    rep = api.make_repeat([scene.bar], x_by_z())
    freed = next(c for c in copies(rep) if cell(c) == (1, 0, 1))
    api.dissociate(freed)
    assert all(repeat_joints.origin_of(j) is None for j in repeat_joints.joints_of_part(freed))
    api.edit_repeat(rep, x_by_z(3, 3))
    assert freed not in copies(rep) and len(joints_of(scene.doc)) == 2 + 2 * len(copies(rep)) + 2
    assert stale_or_invalid(scene.doc) == []


def test_annulation_en_un_bloc_et_reouverture(scene: Scene, rouvrir: Reopen) -> None:
    scene.doc.UndoMode = 1
    api.make_repeat([scene.bar], x_by_z())
    assert scene.doc.UndoNames == ["Répéter"]  # une seule entrée : copies et assemblages
    scene.doc.undo()
    assert len(joints_of(scene.doc)) == 2 and scene.doc.getObject("Repeat") is None
    scene.doc.redo()
    assert len(joints_of(scene.doc)) == 12
    doc = rouvrir(scene.doc)
    rep = doc.getObject("Repeat")
    assert len(copies(rep)) == 5 and len([o for o in doc.Objects if hasattr(o, "HostPart")]) == 12
    api.edit_repeat(rep, x_by_z(2, 2))
    assert len([o for o in doc.Objects if hasattr(o, "HostPart")]) == 2 + 3 * 2
    assert stale_or_invalid(doc) == []
