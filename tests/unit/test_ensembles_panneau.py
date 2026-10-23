# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ce que montre et modifie le panneau de l'ensemble (J4c, critères P3 et P5), sans FreeCAD :
colonne « Suit », faces pilotées par une formule, distance au bord saisie."""

from __future__ import annotations

from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    Edge,
    EdgeEdit,
    Follow,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Member,
    driven_edges,
    edge_edit,
    follow_rules,
    follow_summary,
)
from freecad.menuiserie.core.geometry import Vec3
from tests.unit.aides_ensembles import BOX, FREE_BACK, desk, piece, placed, with_options

TURN_Z_180 = [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]  # L selon -X, l selon -Y
TURN_Z_45 = [[0.7071068, -0.7071068, 0.0], [0.7071068, 0.7071068, 0.0], [0.0, 0.0, 1.0]]
ALL_FIXED = frozenset(Edge)


def oblique() -> Member:
    """Pièce tournée de 45° autour de Z : pas d'équerre avec l'ensemble."""
    return Member("T", block=placed((100.0, 100.0, 18.0), (500.0, 100.0, 0.0), TURN_Z_45))


def summaries(members: list[Member]) -> dict[str, tuple[Follow, ...]]:
    rules, _ = follow_rules(BOX, members)
    return {m.key: follow_summary(m, rules.get(m.key)) for m in members}


def member(key: str, **changes: object) -> Member:
    """Membre du bureau aux options par défaut, puis ``changes``."""
    found = next(m for m in with_options(desk()) if m.key == key)
    return replace(found, **changes)  # type: ignore[arg-type]


# --- Colonne « Suit » ---------------------------------------------------------------------


def test_suit_bureau_aux_options_par_defaut() -> None:
    """E9 : la joue gauche, qui ne dépend que de son épaisseur, est tout de même « déplacée »."""
    both = (Follow.STRETCHED, Follow.MOVED)
    assert summaries(with_options(desk())) == {"P": both, "JG": both, "JD": both, "V": both}


def test_suit_voile_en_proportion() -> None:
    members = with_options(desk(V=InteriorMode.PROPORTIONAL), {"V": frozenset({Edge.BACK})})
    assert summaries(members)["V"] == (Follow.STRETCHED, Follow.MOVED, Follow.PROPORTION)


def test_suit_joues_qui_restent_en_place_en_profondeur() -> None:
    assert summaries(with_options(desk(), FREE_BACK))["JG"] == (Follow.STRETCHED, Follow.MOVED)


def test_suit_piece_sans_distance_fixe() -> None:
    shelf = Member(
        "S", block=placed((1000.0, 500.0, 20.0), (100.0, 50.0, 300.0)), fixed=frozenset()
    )
    assert summaries([shelf]) == {"S": (Follow.STAYS,)}


def test_suit_piece_verrouillee_E9() -> None:
    """Une pièce verrouillée montre « Locked » en plus de ce qu'elle fait."""
    voile = member("V", locked=True)
    assert summaries([voile])["V"] == (Follow.LOCKED, Follow.MOVED)
    assert summaries(with_options(desk(), None))["V"] == (Follow.STRETCHED, Follow.MOVED)
    locked = [replace(m, locked=m.key == "V") for m in with_options(desk())]
    assert summaries(locked)["V"] == (Follow.LOCKED, Follow.MOVED)
    shelf = Member(
        "S",
        block=placed((1000.0, 500.0, 20.0), (100.0, 50.0, 300.0)),
        fixed=frozenset(),
        locked=True,
    )
    assert summaries([shelf]) == {"S": (Follow.LOCKED, Follow.STAYS)}


def test_suit_formule_de_l_utilisateur() -> None:
    voile = member("V", driven=frozenset({"Placement.Base.y"}))
    assert summaries([voile])["V"] == (Follow.FORMULA, Follow.STRETCHED)


def test_suit_formule_hors_liaisons_ignoree() -> None:
    """Une épaisseur pilotée par une feuille de calcul n'est pas une liaison de l'atelier."""
    voile = member("V", driven=frozenset({"Thickness"}))
    assert Follow.FORMULA not in summaries([voile])["V"]


def test_suit_pas_d_equerre() -> None:
    assert follow_summary(member("V"), None) == (Follow.NOT_SQUARE,)


# --- Faces pilotées (P5) --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("driven", "expected"),
    [
        (frozenset(), frozenset()),
        (frozenset({"Placement.Base.y"}), frozenset({Edge.FRONT, Edge.BACK})),
        (frozenset({"Placement"}), ALL_FIXED),
        (frozenset({"Length"}), frozenset({Edge.LEFT, Edge.RIGHT})),
        (frozenset({"Thickness"}), frozenset()),
    ],
    ids=["aucune", "position-y", "placement", "longueur", "epaisseur"],
)
def test_faces_pilotees(driven: frozenset[str], expected: frozenset[Edge]) -> None:
    assert driven_edges(member("V", driven=driven)) == expected


def test_faces_pilotees_pas_d_equerre() -> None:
    assert driven_edges(oblique()) == ALL_FIXED


# --- Distance au bord saisie ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "edge", "distance", "expected"),
    [
        ("P", Edge.LEFT, 10.0, EdgeEdit(FurnitureAxis.WIDTH, 10.0, "Length", 1190.0)),
        ("P", Edge.RIGHT, 50.0, EdgeEdit(FurnitureAxis.WIDTH, 0.0, "Length", 1150.0)),
        ("JG", Edge.LEFT, 5.0, EdgeEdit(FurnitureAxis.WIDTH, 5.0)),
        ("JG", Edge.BACK, 20.0, EdgeEdit(FurnitureAxis.DEPTH, 0.0, "Width", 580.0)),
        ("P", Edge.TOP, 10.0, EdgeEdit(FurnitureAxis.HEIGHT, -10.0)),
    ],
    ids=["plateau-gauche", "plateau-droite", "joue-epaisseur", "joue-arriere", "plateau-haut"],
)
def test_distance_saisie(key: str, edge: Edge, distance: float, expected: EdgeEdit) -> None:
    """Face opposée fixe sur un axe étirable : la cote change ; sinon la pièce se déplace."""
    assert edge_edit(member(key), BOX, edge, distance) == expected


def test_distance_saisie_face_opposee_non_fixe_deplace() -> None:
    """Avant décochée : la joue garde sa largeur et recule."""
    joue = member("JG", fixed=frozenset({Edge.LEFT, Edge.BACK, Edge.BOTTOM, Edge.TOP}))
    assert edge_edit(joue, BOX, Edge.BACK, 20.0) == EdgeEdit(FurnitureAxis.DEPTH, 20.0)


@pytest.mark.parametrize(
    ("edge", "distance", "expected"),
    [
        (Edge.LEFT, 10.0, EdgeEdit(FurnitureAxis.WIDTH, 0.0, "Length", 990.0)),
        (Edge.RIGHT, 150.0, EdgeEdit(FurnitureAxis.WIDTH, 50.0, "Length", 1050.0)),
    ],
    ids=["gauche", "droite"],
)
def test_distance_saisie_axe_retourne(edge: Edge, distance: float, expected: EdgeEdit) -> None:
    """Pièce tournée de 180° : son origine locale est au bout droit de son étendue."""
    turned = placed((1000.0, 100.0, 20.0), (1000.0, 100.0, 0.0), TURN_Z_180)
    traverse = Member("T", block=turned, fixed=frozenset({Edge.LEFT, Edge.RIGHT}))
    assert edge_edit(traverse, BOX, edge, distance) == expected


def test_distance_saisie_sous_ensemble() -> None:
    caisson = Member(
        "C", box=FurnitureBox(600, 560, 720), origin=Vec3(0, 0, 0), fixed=frozenset(Edge)
    )
    assert edge_edit(caisson, BOX, Edge.LEFT, 100.0) == EdgeEdit(
        FurnitureAxis.WIDTH, 100.0, "Width", 500.0
    )


@pytest.mark.parametrize(
    ("changes", "edge", "distance", "text"),
    [
        ({}, Edge.LEFT, 1199.95, "trop petite : Length = 0,05 mm"),
        ({}, Edge.LEFT, -20000.0, "trop grande"),
        ({"driven": frozenset({"Placement.Base.x"})}, Edge.LEFT, 10.0, "Placement.Base.x"),
    ],
    ids=["trop-petite", "trop-grande", "formule"],
)
def test_distance_saisie_refusee(
    changes: dict[str, object], edge: Edge, distance: float, text: str
) -> None:
    with pytest.raises(FurnitureError) as error:
        edge_edit(member("P", **changes), BOX, edge, distance)
    assert text in str(error.value)


def test_distance_saisie_pas_d_equerre() -> None:
    with pytest.raises(FurnitureError):
        edge_edit(oblique(), BOX, Edge.LEFT, 1.0)
