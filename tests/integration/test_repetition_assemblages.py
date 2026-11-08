# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages recopiés par une répétition (lot R-b2, ADR 0043, ``docs/specs/repetition.md`` § 3).

R7 cinq barreaux tenonnés entre deux traverses, cas A (deux sources), B (une pièce fixe), C
(ignoré), D (infaisable), E (paramètres partagés), F (copie ajoutée), G (copie retirée), « Recopier
les assemblages » décoché, dissociation, suppression de l'origine, annulation en un bloc,
réouverture, répétition d'une pièce usinée, temps de 20 copies.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.cadre import placement, stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")
repeat_joints = pytest.importorskip("freecad.menuiserie.features.repeat_joints")

Reopen = Callable[[Any], Any]
TRAVERSE = (600, 60, 22)
TENON = "TenonThickness"


def part(doc: Any, mark: str, size: Any, where: Any) -> Any:
    """Pièce de chêne recalculée, au placement ``where``."""
    obj = api.make_wood_part(*size, "chene", mark=mark, doc=doc)
    obj.Placement = where
    doc.recompute()
    return obj


class Scene:
    """Deux traverses (axe X, à y = 0 et y = 340) et un barreau (axe Y) qui les touche."""

    def __init__(self, doc: Any, **tenon: Any) -> None:
        self.doc = doc
        self.low = part(doc, "Basse", TRAVERSE, placement(0, 0))
        self.high = part(doc, "Haute", TRAVERSE, placement(0, 340))
        self.bar = part(doc, "Barreau", (280, 40, 22), placement(140, 60, 90))
        self.joints = [
            api.make_mortise_tenon(self.low, self.bar, **tenon),
            api.make_mortise_tenon(self.high, self.bar, **tenon),
        ]
        doc.recompute()
        self.cut = self.low.Shape.Volume - api.machined_part_of(self.low).Shape.Volume

    def repeat(self, source: Any = None, **values: Any) -> Any:
        """Quatre copies du barreau tous les 100 mm sur X (cinq barreaux), sauf autre réglage."""
        settings = {"count": 4, "step": 100.0, "axis": "X", **values}
        return api.make_repeat([source or self.bar], api.RepeatParams(**settings))

    def machined_volume(self, traverse: Any) -> float:
        return float(api.machined_part_of(traverse).Shape.Volume)


def copies(rep: Any) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep)
    return found


def children(origin: Any) -> list[Any]:
    found: list[Any] = repeat_joints.children_of(origin)
    return found


def all_children(rep: Any) -> list[Any]:
    return [child for copy in copies(rep) for child in repeat_joints.joints_of_part(copy)]


def joints_of(doc: Any) -> list[Any]:
    return [obj for obj in doc.Objects if hasattr(obj, "HostPart")]


def engine(obj: Any) -> dict[str, str]:
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


@pytest.fixture
def scene(document: Any) -> Scene:
    return Scene(document)


# --- R7 : cinq barreaux entre deux traverses -----------------------------------------------


def test_cinq_barreaux_dix_assemblages_cinq_mortaises_par_traverse(scene: Scene) -> None:
    rep = scene.repeat()
    doc = scene.doc
    assert len(joints_of(doc)) == 10
    assert len(all_children(rep)) == 8 and len({j.Name for j in all_children(rep)}) == 8
    for traverse in (scene.low, scene.high):
        machined = api.machined_part_of(traverse)
        assert len(machined.Joints) == 5
        assert scene.machined_volume(traverse) == pytest.approx(
            traverse.Shape.Volume - 5 * scene.cut
        )
    for copy in copies(rep):
        assert api.machined_part_of(copy).Shape.isValid()
        assert len(api.machined_part_of(copy).Joints) == 2
    assert stale_or_invalid(doc) == []


def test_roles_conserves_et_noms_des_assemblages(scene: Scene) -> None:
    rep = scene.repeat()
    first = copies(rep)[0]
    labels = sorted(j.Label for j in repeat_joints.joints_of_part(first))
    assert labels == [f"Tenon-mortaise : {t} {first.Label}" for t in ("Basse", "Haute")]
    for child in all_children(rep):
        assert child.GuestPart in copies(rep) and child.HostPart in (scene.low, scene.high)
        assert type(child.Proxy) is type(scene.joints[0].Proxy)
    assert api.machined_part_of(first).Label == f"{first.Label} (usinée)"


def test_la_piece_usinee_visible_est_une_source_acceptee(scene: Scene) -> None:
    machined = api.machined_part_of(scene.bar)
    rep = scene.repeat(source=machined)
    assert rep.Source == [scene.bar]  # la répétition porte sur la brute
    assert all(c.RepeatSource == scene.bar for c in copies(rep))
    assert len(joints_of(scene.doc)) == 10 and stale_or_invalid(scene.doc) == []


# --- Liens de l'enfant avec l'origine ------------------------------------------------------


def test_enfant_lie_a_l_origine_en_lecture_seule(scene: Scene) -> None:
    origin = scene.joints[0]
    rep = scene.repeat()
    kids = children(origin)
    assert len(kids) == 4 and all(k.RepeatJoint == origin for k in kids)
    paths = repeat_joints.param_paths(kids[0])
    assert TENON in paths and "Through" in paths and "ObliqueReference" in paths
    for kid in kids:
        assert kid.getEditorMode("RepeatJoint") == ["ReadOnly"]
        assert kid.getGroupOfProperty("RepeatJoint") == "Répétition"
        assert {p for p, t in engine(kid).items() if t == f"{origin.Name}.{p}"} == set(paths)
        for path in paths:
            assert kid.getEditorMode(path) == ["ReadOnly"], path
    assert not hasattr(origin, "RepeatJoint") and origin.getEditorMode(TENON) == []
    assert len(all_children(rep)) == 8


def test_cas_e_changer_l_origine_change_les_enfants(scene: Scene) -> None:
    origin = scene.joints[0]
    scene.repeat()
    before = scene.machined_volume(scene.low)
    origin.TenonThickness = 12
    origin.Through = True
    scene.doc.recompute()
    for kid in children(origin):
        assert kid.TenonThickness.Value == 12.0 and kid.Through is True
    assert scene.machined_volume(scene.low) != pytest.approx(before)
    # les enfants de l'autre assemblage d'origine gardent la configuration de leur origine
    for kid in children(scene.joints[1]):
        assert kid.TenonThickness.Value != 12.0
    assert stale_or_invalid(scene.doc) == []


# --- Cas A : deux sources ------------------------------------------------------------------


def test_cas_a_assemblage_entre_les_copies_homologues(document: Any) -> None:
    host = part(document, "Montant", TRAVERSE, placement(0, 0))
    guest = part(document, "Traverse", (280, 60, 22), placement(60, 60, 90))
    origin = api.make_mortise_tenon(host, guest, tenon_thickness=8)
    rep = api.make_repeat(
        [host, guest], api.RepeatParams(count=2, step=30.0, axis="Z", copy_joints=True)
    )
    hosts, guests = (repeat.copies_of(rep, s) for s in (host, guest))
    kids = children(origin)
    assert len(kids) == 2 and len(joints_of(document)) == 3
    assert [(k.HostPart, k.GuestPart) for k in kids] == list(zip(hosts, guests, strict=True))
    assert all(k.TenonThickness.Value == 8.0 for k in kids)
    assert all(k.Shape is not None and "Invalid" not in k.State for k in kids)
    assert stale_or_invalid(document) == []


# --- Cas C : sans source -------------------------------------------------------------------


def test_cas_c_assemblage_sans_source_ignore(scene: Scene) -> None:
    other = part(scene.doc, "Autre", (300, 60, 22), placement(0, 700))
    third = part(scene.doc, "Tiers", (200, 60, 22), placement(300, 700))
    alone = api.make_mortise_tenon(other, third)
    scene.doc.recompute()
    scene.repeat()
    assert children(alone) == [] and len(joints_of(scene.doc)) == 11


# --- Cas D : infaisable --------------------------------------------------------------------


def test_cas_d_copie_hors_de_l_hote_assemblage_cree_et_signale(scene: Scene) -> None:
    rep = scene.repeat(count=3, step=300.0)  # barreaux à 140, 440, 740 et 1040 mm : 2 hors hôte
    doc = scene.doc
    assert len(all_children(rep)) == 6 and len(joints_of(doc)) == 8
    invalid = [j for j in all_children(rep) if "Invalid" in j.State]
    assert {j.GuestPart.RepeatIndex for j in invalid} == {2, 3}  # la vérification existante
    assert all("Invalid" not in c.State for c in copies(rep))  # la copie reste modifiable
    copies(rep)[1].Length = 300
    api.edit_repeat(rep, api.RepeatParams(count=3, step=100.0, axis="X"))
    assert [j for j in joints_of(doc) if "Invalid" in j.State] == []
    assert stale_or_invalid(doc) == []


# --- Cas F et G ----------------------------------------------------------------------------


def test_cas_f_copie_ajoutee_recoit_ses_assemblages(scene: Scene) -> None:
    rep = scene.repeat(count=2)
    assert len(joints_of(scene.doc)) == 6
    api.edit_repeat(rep, api.RepeatParams(count=4, step=100.0, axis="X"))
    assert len(joints_of(scene.doc)) == 10 and len(all_children(rep)) == 8
    last = copies(rep)[-1]
    assert len(repeat_joints.joints_of_part(last)) == 2
    assert len(api.machined_part_of(scene.low).Joints) == 5
    assert scene.machined_volume(scene.low) == pytest.approx(scene.low.Shape.Volume - 5 * scene.cut)
    assert stale_or_invalid(scene.doc) == []


def test_cas_g_copie_retiree_emporte_ses_assemblages(scene: Scene) -> None:
    rep = scene.repeat()
    gone = copies(rep)[-1].Name
    api.edit_repeat(rep, api.RepeatParams(count=2, step=100.0, axis="X"))
    assert scene.doc.getObject(gone) is None and len(joints_of(scene.doc)) == 6
    assert len(api.machined_part_of(scene.low).Joints) == 3
    assert scene.machined_volume(scene.high) == pytest.approx(
        scene.high.Shape.Volume - 3 * scene.cut
    )
    assert stale_or_invalid(scene.doc) == []
    api.edit_repeat(rep, api.RepeatParams(count=1, step=100.0, axis="X"))
    assert len(joints_of(scene.doc)) == 4 and len(children(scene.joints[0])) == 1
    assert stale_or_invalid(scene.doc) == []


# --- « Recopier les assemblages » ----------------------------------------------------------


def test_copy_joints_faux_aucune_copie_d_assemblage(scene: Scene) -> None:
    rep = scene.repeat(copy_joints=False)
    assert rep.CopyJoints is False and len(joints_of(scene.doc)) == 2
    assert all(api.machined_part_of(c) is None for c in copies(rep))
    api.edit_repeat(rep, api.RepeatParams(count=5, step=100.0, axis="X", copy_joints=False))
    assert len(joints_of(scene.doc)) == 2


def test_copy_joints_modifiable_par_edit_repeat(scene: Scene) -> None:
    rep = scene.repeat()
    assert rep.CopyJoints is True and len(joints_of(scene.doc)) == 10
    api.edit_repeat(rep, api.RepeatParams(count=4, step=100.0, axis="X", copy_joints=False))
    doc = scene.doc
    assert rep.CopyJoints is False and len(joints_of(doc)) == 2
    assert all(api.machined_part_of(c) is None for c in copies(rep))
    assert len(api.machined_part_of(scene.low).Joints) == 1
    assert stale_or_invalid(doc) == []
    api.edit_repeat(rep, api.RepeatParams(count=4, step=100.0, axis="X", copy_joints=True))
    assert rep.CopyJoints is True and len(joints_of(doc)) == 10
    assert len(api.machined_part_of(scene.high).Joints) == 5 and stale_or_invalid(doc) == []


# --- Dissocier, supprimer l'origine --------------------------------------------------------


def test_dissocier_la_copie_dissocie_ses_assemblages(document: Any) -> None:
    scene = Scene(document, tenon_thickness=8)
    origin = scene.joints[0]
    rep = scene.repeat()
    target = copies(rep)[1]
    mine = repeat_joints.joints_of_part(target)
    api.dissociate(target)
    assert len(mine) == 2 and not repeat_joints.origin_of(mine[0])
    for joint in mine:
        assert not hasattr(joint, "RepeatJoint") and engine(joint) == {}
        assert joint.getEditorMode(TENON) == [] and joint.TenonThickness.Value == 8.0
    origin.TenonThickness = 11
    scene.doc.recompute()
    assert [k.TenonThickness.Value for k in children(origin)] == [11.0] * 3
    assert mine[0].TenonThickness.Value == 8.0  # valeur gardée, plus de lien
    assert len(joints_of(scene.doc)) == 10 and stale_or_invalid(scene.doc) == []
    api.edit_repeat(rep, api.RepeatParams(count=4, step=100.0, axis="X"))
    assert len(joints_of(scene.doc)) == 10  # la copie dissociée ne reçoit pas de doublon


def test_supprimer_l_origine_dissocie_ses_enfants(scene: Scene) -> None:
    origin = scene.joints[0]
    scene.repeat()
    origin.TenonThickness = 9
    scene.doc.recompute()
    kids = children(origin)
    names = [k.Name for k in kids]
    scene.doc.openTransaction("Supprimer")
    scene.doc.removeObject(origin.Name)
    scene.doc.commitTransaction()
    scene.doc.recompute()
    for name in names:
        kid = scene.doc.getObject(name)
        assert not hasattr(kid, "RepeatJoint") and engine(kid) == {}
        assert kid.TenonThickness.Value == 9.0 and kid.getEditorMode(TENON) == []
    assert stale_or_invalid(scene.doc) == []


# --- Annulation et réouverture -------------------------------------------------------------


def test_annulation_en_un_bloc(document: Any) -> None:
    document.UndoMode = 1
    scene = Scene(document)
    document.recompute()
    count = len(document.Objects)
    volume = scene.machined_volume(scene.low)
    rep_name = scene.repeat().Name
    assert len(joints_of(document)) == 10 and document.UndoCount >= 1
    document.undo()
    document.recompute()
    assert len(document.Objects) == count and len(joints_of(document)) == 2
    assert document.getObject(rep_name) is None
    assert scene.machined_volume(scene.low) == pytest.approx(volume)
    assert stale_or_invalid(document) == []
    document.redo()
    document.recompute()
    assert len(joints_of(document)) == 10 and stale_or_invalid(document) == []


def test_annulation_de_la_baisse_du_nombre(document: Any) -> None:
    document.UndoMode = 1
    scene = Scene(document)
    rep = scene.repeat()
    api.edit_repeat(rep, api.RepeatParams(count=1, step=100.0, axis="X"))
    assert len(joints_of(document)) == 4
    document.undo()
    document.recompute()
    assert len(joints_of(document)) == 10 and stale_or_invalid(document) == []


def test_reouverture_conserve_liens_expressions_et_lecture_seule(
    document: Any, rouvrir: Reopen
) -> None:
    scene = Scene(document)
    rep = scene.repeat()
    origin_name, rep_name = scene.joints[0].Name, rep.Name
    engines = {j.Name: engine(j) for j in all_children(rep)}
    doc = rouvrir(document)
    origin, rep = doc.getObject(origin_name), doc.getObject(rep_name)
    kids = all_children(rep)
    assert {j.Name: engine(j) for j in kids} == engines and len(kids) == 8
    for kid in children(origin):
        assert kid.RepeatJoint == origin
        assert kid.getEditorMode(TENON) == ["ReadOnly"]
        assert kid.getEditorMode("RepeatJoint") == ["ReadOnly"]
    assert origin.getEditorMode(TENON) == []
    assert stale_or_invalid(doc) == []
    origin.TenonThickness = 10
    doc.recompute()
    assert {k.TenonThickness.Value for k in children(origin)} == {10.0}
    api.dissociate(copies(rep)[0])
    api.edit_repeat(rep, api.RepeatParams(count=4, step=90.0, axis="X"))
    assert stale_or_invalid(doc) == []


# --- Temps ---------------------------------------------------------------------------------


def test_vingt_copies_avec_deux_assemblages_chacune(document: Any) -> None:
    low = part(document, "Basse", (2400, 60, 22), placement(0, 0))
    high = part(document, "Haute", (2400, 60, 22), placement(0, 340))
    bar = part(document, "Barreau", (280, 40, 22), placement(140, 60, 90))
    api.make_mortise_tenon(low, bar)
    api.make_mortise_tenon(high, bar)
    document.recompute()
    started = time.perf_counter()
    rep = api.make_repeat([bar], api.RepeatParams(count=20, step=100.0, axis="X"))
    created = time.perf_counter() - started
    assert len(all_children(rep)) == 40 and stale_or_invalid(document) == []
    repeat_joints.children_of(document.getObject(rep.Name))  # appel sans effet de bord
    next(iter(children(low.InList[0]))) if False else None
    started = time.perf_counter()
    for joint in joints_of(document)[:1]:
        joint.TenonThickness = 11
    document.recompute()
    edited = time.perf_counter() - started
    print(f"\n20 copies x 2 assemblages : création {created:.2f} s, recalcul {edited:.2f} s")
    assert created < 120 and edited < 60
