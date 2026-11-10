# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046, lot 1) : modèle d'arbre pur et lecture du document simulé."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, ClassVar

import pytest

from freecad.menuiserie import ICONS_DIR
from freecad.menuiserie.core.structure_tree import (
    JOINTS_TITLE,
    NodeKind,
    StructureNode,
    build_structure,
)
from tests.unit.aides import ROOT
from tests.unit.aides_debit_document import Doc, Obj, World, simulated_world
from tests.unit.test_commandes_assemblages import (
    commands_of,
    init_gui_themes,
    noop,
    registered_commands,
)

PACKAGE = ROOT / "freecad" / "menuiserie"
COMMAND = PACKAGE / "gui" / "commands" / "structure.py"
NAME = "Menuiserie_Structure"
READ_ONLY_MODULES = (
    PACKAGE / "core" / "structure_tree.py",
    PACKAGE / "features" / "structure_source.py",
    PACKAGE / "core" / "structure_sync.py",
    PACKAGE / "gui" / "structure_panel.py",
    PACKAGE / "gui" / "structure_sync.py",
    PACKAGE / "gui" / "structure_tree_widget.py",
    COMMAND,
)


class FakeSource:
    """Source de l'arbre sur un petit document : bureau (sous-ensemble tiroir) et une planche."""

    LABELS: ClassVar[dict[str, str]] = {
        "Bureau": "Bureau",
        "Tiroir": "Tiroir",
        "P1": "Plateau",
        "P2": "Joue",
        "P3": "Fond",
        "J1": "Tenon-mortaise",
        "D1": "Distance",
        "Loose": "Planche",
    }
    CHILDREN: ClassVar[dict[str, tuple[str, ...]]] = {
        "Bureau": ("sub:Tiroir", "P1", "P2", "J1", "D1"),
        "Tiroir": ("P3",),
    }

    def root_furnitures(self) -> Sequence[str]:
        return ["Bureau"]

    def loose_pieces(self) -> Sequence[str]:
        return ["Loose"]

    def sub_furnitures(self, furniture: str) -> Sequence[str]:
        return [c[4:] for c in self.CHILDREN[furniture] if c.startswith("sub:")]

    def pieces(self, furniture: str) -> Sequence[str]:
        return [c for c in self.CHILDREN[furniture] if c.startswith("P")]

    def joints(self, furniture: str) -> Sequence[str]:
        return [c for c in self.CHILDREN[furniture] if c[0] in "JD"]

    def label(self, key: str) -> str:
        return self.LABELS[key]


def title(count: int) -> str:
    return JOINTS_TITLE.format(count=count)


def labels(nodes: Sequence[StructureNode]) -> list[str]:
    return [node.label for node in nodes]


def test_racines_ensemble_puis_pieces_hors_ensemble() -> None:
    roots = build_structure(FakeSource(), title)
    assert labels(roots) == ["Bureau", "Planche"]
    assert [root.kind for root in roots] == [NodeKind.FURNITURE, NodeKind.PIECE]


def test_ensemble_sous_ensembles_puis_pieces_puis_assemblages() -> None:
    bureau = build_structure(FakeSource(), title)[0]
    assert labels(bureau.children) == ["Tiroir", "Plateau", "Joue", "Assemblages (2)"]
    assert labels(bureau.children[0].children) == ["Fond"]


def test_noeud_assemblages_replie_avec_ses_elements() -> None:
    group = build_structure(FakeSource(), title)[0].children[-1]
    assert (group.kind, group.expanded, group.key) == (NodeKind.JOINTS, False, "")
    assert labels(group.children) == ["Tenon-mortaise", "Distance"]
    assert {child.kind for child in group.children} == {NodeKind.JOINT}


def test_pas_de_noeud_assemblages_sans_assemblage() -> None:
    tiroir = build_structure(FakeSource(), title)[0].children[0]
    assert all(child.kind is not NodeKind.JOINTS for child in tiroir.children)


def test_les_cles_sont_les_noms_des_objets() -> None:
    nodes = build_structure(FakeSource(), title)[0].walk()
    assert [n.key for n in nodes if n.kind is NodeKind.PIECE] == ["P3", "P1", "P2"]


def test_sous_ensemble_cyclique_coupe() -> None:
    class Cyclic(FakeSource):
        def sub_furnitures(self, furniture: str) -> Sequence[str]:
            return ["Tiroir" if furniture == "Bureau" else "Bureau"]

    bureau = build_structure(Cyclic(), title)[0]
    assert labels(bureau.walk()).count("Bureau") == 1


def test_document_vide() -> None:
    class Empty(FakeSource):
        def root_furnitures(self) -> Sequence[str]:
            return []

        def loose_pieces(self) -> Sequence[str]:
            return []

    assert build_structure(Empty(), title) == ()


# --- Lecture d'un document (FreeCAD simulé) -----------------------------------------------


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def joint_between(world: World, name: str, host: Obj, guest: Obj) -> Obj:
    """Assemblage de l'atelier entre deux pièces (déclaré dans leur ``InList``)."""
    del world  # FreeCAD simulé déjà en place : le module des assemblages s'importe ici
    from freecad.menuiserie.features.joints.base import JointFeature

    joint = Obj(name, "Part::FeaturePython", HostPart=host, GuestPart=guest)
    joint.props["Proxy"] = JointFeature.__new__(JointFeature)
    host.InList.append(joint)
    guest.InList.append(joint)
    return joint


def read(world: World, *objects: Obj) -> tuple[StructureNode, ...]:
    from freecad.menuiserie.features.structure_source import structure_of

    doc: Any = Doc(*objects)
    del world
    return structure_of(doc)


def test_document_brute_et_usinee_forment_une_ligne(world: World) -> None:
    blank = world.part("Planche", Label="Plateau")
    machined = world.machined("Planche_usinee", blank, shape=None)
    machined.props["Label"] = "Plateau (usinée)"
    furniture = world.furniture("Bureau", blank)
    furniture.props["Label"] = "Bureau"
    roots = read(world, furniture, blank, machined)
    assert [(n.kind, n.label, n.key) for n in roots[0].walk()] == [
        (NodeKind.FURNITURE, "Bureau", "Bureau"),
        (NodeKind.PIECE, "Plateau", "Planche_usinee"),
    ]


def test_document_pieces_hors_ensemble_a_la_racine(world: World) -> None:
    blank = world.part("Planche", Label="Etagere")
    assert [(n.label, n.key) for n in read(world, blank)] == [("Etagere", "Planche")]


def test_document_sous_ensemble_enfant_et_assemblages(world: World) -> None:
    left = world.part("G", Label="Joue")
    right = world.part("D", Label="Joue D")
    drawer_part = world.part("F", Label="Fond")
    drawer = world.furniture("Tiroir", drawer_part)
    desk = world.furniture("Bureau", left, right, drawer)
    desk.props["Label"], drawer.props["Label"] = "Bureau", "Tiroir"
    joint = joint_between(world, "J", left, right)
    joint.props["Label"] = "Tenon"
    roots = read(world, desk, drawer, left, right, drawer_part, joint)
    assert [n.label for n in roots] == ["Bureau"]
    assert [n.label for n in roots[0].children] == ["Tiroir", "Joue D", "Joue", "Assemblages (1)"]
    assert [n.label for n in roots[0].children[0].children] == ["Fond"]
    assert [n.label for n in roots[0].children[-1].children] == ["Tenon"]


def test_document_ne_montre_ni_std_part_ni_origine(world: World) -> None:
    blank = world.part("Planche", Label="Plateau")
    std_part = Obj("Part", "App::Part", Label="Part")
    origin = Obj("Origin", "App::Origin", Label="Origine")
    labels_found = [n.label for r in read(world, std_part, origin, blank) for n in r.walk()]
    assert labels_found == ["Plateau"]


def test_le_vocabulaire_du_debutant() -> None:
    texts = [FakeSource.LABELS.values(), [title(3)]]
    assert not any("usinée" in t or "Std Part" in t for group in texts for t in group)


# --- Commande d'ouverture (analyse statique : le module importe FreeCADGui) ----------------


def test_commande_nommee_et_traduisible() -> None:
    attributes = commands_of(COMMAND)[NAME]
    assert noop(attributes["MENU_TEXT"]) == (NAME, "Structure")
    context, tool_tip = noop(attributes["TOOL_TIP"])
    assert (context, bool(tool_tip.strip())) == (NAME, True)


def test_commande_enregistree_et_dans_la_barre() -> None:
    assert registered_commands(COMMAND) == [NAME]
    assert NAME in init_gui_themes()["Vue"]


def test_icone_generee_par_le_script() -> None:
    assert (ICONS_DIR / f"{NAME}.svg").is_file()
    assert f'"{NAME}.svg"' in (ROOT / "tools" / "generer_icones.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("path", READ_ONLY_MODULES, ids=lambda path: path.name)
def test_aucune_ecriture_dans_le_document_ni_l_arbre_natif(path: Any) -> None:
    """ADR 0046 : ni ShowInTree, ni claimChildren, ni objet, propriété ou transaction."""
    source = path.read_text(encoding="utf-8")
    for forbidden in ("ShowInTree", "claimChildren", "addObject", "addProperty", "openTransaction"):
        assert forbidden not in source
