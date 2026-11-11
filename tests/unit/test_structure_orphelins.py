# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046) : tout objet de l'atelier apparaît exactement une fois.

Assemblages et Distances sans ensemble de rattachement (pieds, coulisses, LR32 d'une pièce hors
ensemble…) : nœud « Assemblages (N) » à la racine ; tout autre objet de l'atelier invisible :
« Autres objets de l'atelier (N) ».
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from typing import Any, ClassVar

import pytest

from freecad.menuiserie.core.structure_actions import (
    DRAGGABLE_KINDS,
    NO_DROP_KINDS,
    decide_delete,
    decide_open,
    drop_blocked,
    drop_target,
)
from freecad.menuiserie.core.structure_icons import icon_name
from freecad.menuiserie.core.structure_sync import keys_to_select_in_freecad, rows_for_selection
from freecad.menuiserie.core.structure_tree import (
    HARDWARE_TITLE,
    JOINTS_TITLE,
    LEFTOVERS_TITLE,
    NodeKind,
    StructureNode,
    build_structure,
)
from tests.unit.aides_debit_document import Doc, Obj, World, simulated_world
from tests.unit.test_structure_arbre import FakeSource, joint_between


class LooseSource(FakeSource):
    """Le petit document de ``FakeSource`` plus deux assemblages hors de tout ensemble."""

    LABELS: ClassVar[dict[str, str]] = {
        **FakeSource.LABELS,
        "Foot": "Pieds",
        "Slide": "Coulisse",
        "Lap": "Mi-bois",
        "Ghost": "Fantôme",
    }

    def loose_joints(self) -> Sequence[str]:
        return ["Lap"]

    def loose_hardware(self) -> Sequence[str]:
        return ["Foot", "Slide"]

    def subtype(self, key: str) -> str:
        return {"Foot": "Foot", "Slide": "DrawerSlide", "Lap": "HalfLap"}.get(key, "")


class AllObjects:
    """Extras : tous les objets de l'atelier, dont un (« Ghost ») qu'aucune ligne ne montre."""

    def __init__(self, keys: Sequence[str]) -> None:
        self._keys = keys

    def repetitions(self, container: str | None) -> Sequence[str]:
        return []

    def copies(self, repetition: str) -> Sequence[str]:
        return []

    def all_copies(self) -> Collection[str]:
        return set()

    def furniture_copies(self) -> Collection[str]:
        return set()

    def cut_lists(self) -> Sequence[str]:
        return []

    def other_objects(self) -> Sequence[str]:
        return []

    def workshop_objects(self) -> Sequence[str]:
        return self._keys


EVERYTHING = ["Bureau", "Tiroir", "P1", "P2", "P3", "J1", "D1", "Loose", "Lap", "Foot", "Slide"]


def roots_of(keys: Sequence[str]) -> tuple[StructureNode, ...]:
    return build_structure(LooseSource(), AllObjects(keys))


def keys_of(roots: Sequence[StructureNode]) -> list[str]:
    return [node.key for root in roots for node in root.walk() if node.key]


def test_assemblages_sans_ensemble_dans_un_noeud_a_la_racine() -> None:
    roots = build_structure(LooseSource())
    assert [root.kind for root in roots] == [
        NodeKind.FURNITURE,
        NodeKind.PIECE,
        NodeKind.JOINTS,
        NodeKind.HARDWARE,
    ]
    group = roots[2]
    assert (group.label, group.key, group.expanded) == (JOINTS_TITLE.format(count=1), "", False)
    assert [(c.kind, c.key, c.subtype) for c in group.children] == [
        (NodeKind.JOINT, "Lap", "HalfLap")
    ]


def test_quincaillerie_libre_dans_son_noeud_a_la_racine() -> None:
    group = build_structure(LooseSource())[3]
    assert (group.label, group.key, group.expanded) == (HARDWARE_TITLE.format(count=2), "", False)
    assert [(c.kind, c.key, c.label, c.subtype) for c in group.children] == [
        (NodeKind.HARDWARE_ITEM, "Foot", "Pieds", "Foot"),
        (NodeKind.HARDWARE_ITEM, "Slide", "Coulisse", "DrawerSlide"),
    ]


def test_quincaillerie_sous_un_ensemble_apres_les_assemblages() -> None:
    class InDesk(LooseSource):
        def hardware(self, furniture: str) -> Sequence[str]:
            return ["Foot"] if furniture == "Bureau" else []

    desk = build_structure(InDesk())[0]
    assert [c.kind for c in desk.children][-2:] == [NodeKind.JOINTS, NodeKind.HARDWARE]
    assert desk.children[-1].label == HARDWARE_TITLE.format(count=1)


def test_pas_de_noeud_a_la_racine_sans_assemblage_libre() -> None:
    assert all(root.kind is not NodeKind.JOINTS for root in build_structure(FakeSource()))


def test_tout_objet_de_l_atelier_est_dans_l_arbre_une_seule_fois() -> None:
    keys = keys_of(roots_of(EVERYTHING))
    assert sorted(keys) == sorted(EVERYTHING)
    assert all(root.kind is not NodeKind.LEFTOVERS for root in roots_of(EVERYTHING))


def test_objet_invisible_sous_autres_objets_de_l_atelier() -> None:
    roots = roots_of([*EVERYTHING, "Ghost", "Ghost"])
    group = roots[-1]
    assert (group.kind, group.expanded, group.key) == (NodeKind.LEFTOVERS, False, "")
    assert group.label == LEFTOVERS_TITLE.format(count=1)
    assert [(c.kind, c.key, c.label) for c in group.children] == [
        (NodeKind.LEFTOVER, "Ghost", "Fantôme")
    ]
    assert sorted(keys_of(roots)) == sorted([*EVERYTHING, "Ghost"])


def test_sans_extras_pas_de_noeud_des_objets_invisibles() -> None:
    roots = build_structure(LooseSource())
    assert all(root.kind is not NodeKind.LEFTOVERS for root in roots)


def test_lignes_racines_sans_dependance_a_un_ensemble() -> None:
    path = [
        (NodeKind.JOINT, "Foot"),
        (NodeKind.JOINTS, ""),
    ]
    assert drop_target(path) is None
    assert drop_blocked(path) == ""


def test_selection_synchronisee_avec_les_lignes_libres() -> None:
    row_keys = set(keys_of(roots_of([*EVERYTHING, "Ghost"])))
    assert rows_for_selection(["Foot", "Ghost", "Zzz"], row_keys) == ["Foot", "Ghost"]
    assert keys_to_select_in_freecad(["Foot", "", "Foot"]) == ["Foot"]


def test_actions_sur_les_lignes_libres() -> None:
    for kind in (NodeKind.JOINT, NodeKind.JOINTS, NodeKind.HARDWARE, NodeKind.HARDWARE_ITEM):
        assert kind not in DRAGGABLE_KINDS
    for kind in (NodeKind.LEFTOVERS, NodeKind.LEFTOVER):
        assert kind in NO_DROP_KINDS and kind not in DRAGGABLE_KINDS
    assert decide_delete(["Foot"], busy=False).allowed
    assert decide_open(["Foot"], busy=False).allowed
    assert decide_delete(["Ghost"], busy=False).allowed


@pytest.mark.parametrize(
    "kind",
    [
        NodeKind.JOINTS,
        NodeKind.JOINT,
        NodeKind.HARDWARE,
        NodeKind.HARDWARE_ITEM,
        NodeKind.LEFTOVERS,
        NodeKind.LEFTOVER,
    ],
)
def test_icone_de_chaque_genre(kind: NodeKind) -> None:
    assert icon_name(kind).endswith(".svg")


# --- Lecture d'un document (FreeCAD simulé) -----------------------------------------------


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def read(*objects: Obj) -> tuple[StructureNode, ...]:
    from freecad.menuiserie.features.structure_source import structure_of

    doc: Any = Doc(*objects)
    return structure_of(doc)


def hardware_on(name: str, part: Obj) -> Obj:
    """Pieds de l'atelier (type de quincaillerie) posés sous ``part``."""
    from freecad.menuiserie.features.joints.feet import FootJoint

    foot = Obj(name, "Part::FeaturePython", HostPart=part, GuestPart=part, Label=name)
    foot.props["Proxy"] = FootJoint.__new__(FootJoint)
    part.InList.append(foot)
    return foot


def test_document_pied_sur_une_piece_hors_ensemble_sous_quincaillerie(world: World) -> None:
    loose = world.part("Planche", Label="Plateau")
    foot = hardware_on("Pieds", loose)
    roots = read(loose, foot)
    assert [(n.kind, n.key) for n in roots] == [
        (NodeKind.PIECE, "Planche"),
        (NodeKind.HARDWARE, ""),
    ]
    assert [(c.kind, c.key, c.subtype) for c in roots[1].children] == [
        (NodeKind.HARDWARE_ITEM, "Pieds", "Foot")
    ]


def test_document_assemblage_et_quincaillerie_separes_sous_l_ensemble(world: World) -> None:
    left, right = world.part("G", Label="G"), world.part("D", Label="D")
    furniture = world.furniture("A", left, right)
    furniture.props["Label"] = "A"
    lap = joint_between(world, "J", left, right)
    lap.props["Label"] = "Lien"
    foot = hardware_on("Pieds", left)
    (root,) = read(furniture, left, right, lap, foot)
    groups = {n.kind: [c.key for c in n.children] for n in root.children if n.children}
    assert groups[NodeKind.JOINTS] == ["J"]
    assert groups[NodeKind.HARDWARE] == ["Pieds"]


def test_document_assemblage_entre_ensembles_sans_ensemble_commun(world: World) -> None:
    left, right = world.part("G", Label="G"), world.part("D", Label="D")
    first, second = world.furniture("A", left), world.furniture("B", right)
    first.props["Label"], second.props["Label"] = "A", "B"
    joint = joint_between(world, "J", left, right)
    joint.props["Label"] = "Lien"
    roots = read(first, second, left, right, joint)
    keys = keys_of(roots)
    assert keys.count("J") == 1
    assert roots[-1].kind is NodeKind.JOINTS


def test_document_assemblage_dans_un_ensemble_n_est_pas_repete(world: World) -> None:
    left, right = world.part("G", Label="G"), world.part("D", Label="D")
    furniture = world.furniture("A", left, right)
    furniture.props["Label"] = "A"
    joint = joint_between(world, "J", left, right)
    joint.props["Label"] = "Lien"
    roots = read(furniture, left, right, joint)
    assert [r.kind for r in roots] == [NodeKind.FURNITURE]
    assert keys_of(roots).count("J") == 1
