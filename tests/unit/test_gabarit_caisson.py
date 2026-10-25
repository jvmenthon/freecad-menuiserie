# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarit « Caisson » en Python pur (J4d, critères K1 et K2 de ``docs/specs/J4-ensembles.md``)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    Edge,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Member,
    bindings_for,
    check_resize,
    follow_rules,
    member_spans,
    predict,
)
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dowels import DowelParams
from freecad.menuiserie.core.joints.rabbet import RabbetParams
from freecad.menuiserie.core.templates import JointSpec, Layout, PieceSpec
from freecad.menuiserie.core.templates.carcass import (
    CARCASS_TEMPLATE,
    MAX_SHELVES,
    CarcassError,
    CarcassJoinery,
    CarcassParams,
    carcass_layout,
    check_materials,
    dowel_params,
)

REFERENCE = CarcassParams()  # 600 x 400 x 720, panneaux de 18 en cp-bouleau, fond de 8
ALL = frozenset(Edge)
L, R, F, B, D, T = Edge  # gauche, droite, avant, arrière, bas (dessous), haut


def extents(piece: PieceSpec) -> list[tuple[float, float]]:
    """Étendues de la pièce sur X, Y, Z du repère du caisson."""
    member = Member(piece.key, block=piece.block, fixed=piece.fixed)
    spans = member_spans(member)
    return [(round(spans[axis].lo, 6), round(spans[axis].hi, 6)) for axis in FurnitureAxis]


def sizes(piece: PieceSpec) -> tuple[float, float, float]:
    size = piece.block.dimensions
    return size.length, size.width, size.thickness


# --- K1 : pièces, assemblages, options ------------------------------------------------------

EXPECTED = {  # clé : (L x l x e, étendues X, Y, Z, distances fixes)
    "left": ((720, 400, 18), [(0, 18), (0, 400), (0, 720)], ALL - {R}),
    "right": ((720, 400, 18), [(582, 600), (0, 400), (0, 720)], ALL - {L}),
    "bottom": ((564, 400, 18), [(18, 582), (0, 400), (0, 18)], ALL - {T}),
    "top": ((564, 400, 18), [(18, 582), (0, 400), (702, 720)], ALL - {D}),
    "back": ((704, 584, 8), [(8, 592), (392, 400), (8, 712)], ALL - {F}),
    "shelf1": ((562, 391, 18), [(19, 581), (0, 391), (351, 369)], frozenset({L, R, F, B})),
}


def test_pieces_du_caisson_de_reference() -> None:
    layout = carcass_layout(REFERENCE)
    assert [piece.key for piece in layout.pieces] == list(EXPECTED)
    for key, (size, spans, fixed) in EXPECTED.items():
        piece = layout.piece(key)
        assert sizes(piece) == size, key
        assert extents(piece) == spans, key
        assert piece.fixed == fixed, key
        assert piece.mode is InteriorMode.STAY, key
    materials = {piece.material_id for piece in layout.pieces}
    assert materials == {"cp-bouleau"}


def test_ensemble_du_caisson() -> None:
    layout = carcass_layout(REFERENCE)
    assert layout.template == CARCASS_TEMPLATE == "Carcass"
    assert layout.label == "Caisson"
    assert layout.box == FurnitureBox(600, 400, 720)
    assert layout.origin == Vec3(0, 0, 0)


def test_assemblages_du_caisson_de_reference() -> None:
    layout = carcass_layout(REFERENCE)
    dowels = layout.joints_of(JointKind.DOWELS)
    assert [(j.host, j.guest) for j in dowels] == [
        ("left", "bottom"),
        ("left", "top"),
        ("right", "bottom"),
        ("right", "top"),
    ]
    assert {j.params for j in dowels} == {
        DowelParams(diameter=8, dowel_length=30, host_depth=12, edge_distance=16)
    }
    rabbets = layout.joints_of(JointKind.RABBET)
    assert [(j.host, j.guest) for j in rabbets] == [
        ("left", "back"),
        ("right", "back"),
        ("bottom", "back"),
        ("top", "back"),
    ]
    assert {j.params for j in rabbets} == {RabbetParams(through=True)}
    shelf_joints = [j for j in layout.joints if "shelf1" in (j.host, j.guest)]
    assert shelf_joints == []
    assert len(layout.joints) == 8


def test_options_explicites_et_jamais_par_defaut() -> None:
    """Les options du gabarit diffèrent des options par défaut (Q7) là où il le faut : le fond
    et l'étagère gardent leurs retraits et leurs jeux sans compter sur elles."""
    for piece in carcass_layout(REFERENCE).pieces:
        assert isinstance(piece.fixed, frozenset)
    shelf = carcass_layout(REFERENCE).piece("shelf1")
    assert not shelf.fixed & {D, T}


EXPECTED_BINDINGS = {
    "left": {"Length": "<<Caisson>>.Height", "Width": "<<Caisson>>.Depth"},
    "back": {
        "Length": "<<Caisson>>.Height - 16 mm",
        "Width": "<<Caisson>>.Width - 16 mm",
        "Placement.Base.y": "<<Caisson>>.Origin.y + <<Caisson>>.Depth - Thickness",
    },
    "shelf1": {  # jeux de 1 mm rigides : la pièce libre de la rangée est l'étagère (ADR 0019)
        "Length": "<<Caisson>>.Width - <<left>>.Thickness - <<right>>.Thickness - 2 mm",
        "Placement.Base.x": "<<Caisson>>.Origin.x + <<left>>.Thickness + 1 mm",
        "Width": "<<Caisson>>.Depth - <<back>>.Thickness - 1 mm",
        "Placement.Base.z": "<<Caisson>>.Origin.z + <<Caisson>>.Height * 0.5"
        " + <<bottom>>.Thickness * 0.5 - Thickness * 0.5 - <<top>>.Thickness * 0.5",
    },
    "top": {
        "Length": "<<Caisson>>.Width - 36 mm",
        "Width": "<<Caisson>>.Depth",
        "Placement.Base.z": "<<Caisson>>.Origin.z + <<Caisson>>.Height - 18 mm",
    },
}


def carcass_members(params: CarcassParams = REFERENCE) -> tuple[Layout, list[Member]]:
    layout = carcass_layout(params)
    members = [
        Member(p.key, block=p.block, fixed=p.fixed, mode=p.mode, label=p.key) for p in layout.pieces
    ]
    return layout, members


def test_liaisons_des_options_du_gabarit() -> None:
    """Les options explicites donnent les liaisons attendues, sans avertissement : le fond cite
    sa propre épaisseur (``Thickness``), l'étagère garde ses jeux et se règle sur les panneaux,
    les côtés suivent la hauteur et la profondeur."""
    layout, members = carcass_members()
    rules, rule_notices = follow_rules(layout.box, members)
    bindings, notices = bindings_for("Caisson", members, rules)
    assert (rule_notices, notices) == ((), ())
    for key, expected in EXPECTED_BINDINGS.items():
        assert {b.prop: b.expression for b in bindings if b.key == key} == expected, key
    assert not any(rule.row.blocked for found in rules.values() for rule in found)


@pytest.mark.parametrize(
    "new",
    [
        FurnitureBox(800, 400, 720),
        FurnitureBox(600, 500, 720),
        FurnitureBox(600, 400, 900),
        FurnitureBox(800, 500, 900),
        FurnitureBox(500, 300, 500),
    ],
    ids=["plus large", "plus profond", "plus haut", "plus large et plus haut", "plus petit"],
)
def test_caisson_redimensionne_reste_valide_D6(new: FurnitureBox) -> None:
    """Les assemblages (tourillons, feuillures) gardent leur position relative ; le fond reste
    logé dans les feuillures et les étagères restent entre les panneaux."""
    layout, members = carcass_members()
    rules, _ = follow_rules(layout.box, members)
    joined = [(joint.host, joint.guest) for joint in layout.joints]
    assert check_resize(layout.box, new, members, rules, joined) == ()
    after = predict(new, members, rules)
    assert extents_of(after["back"])[0] == (8, new.width - 8)
    assert extents_of(after["right"])[0] == (new.width - 18, new.width)
    shelf = extents_of(after["shelf1"])
    assert shelf[2][0] == pytest.approx((new.height - 18) / 2)  # reste au milieu
    assert 18 < shelf[0][0] < shelf[0][1] < new.width - 18


def extents_of(member: Member) -> list[tuple[float, float]]:
    spans = member_spans(member)
    return [(round(spans[axis].lo, 6), round(spans[axis].hi, 6)) for axis in FurnitureAxis]


def test_etageres_reparties_a_intervalles_egaux() -> None:
    layout = carcass_layout(replace(REFERENCE, shelf_count=3))
    shelves = [p for p in layout.pieces if p.key.startswith("shelf")]
    assert [extents(p)[2] for p in shelves] == [
        (175.5, 193.5),
        (351.0, 369.0),
        (526.5, 544.5),
    ]  # intervalles de 157,5 mm entre dessous, étagères et dessus
    assert (
        carcass_layout(replace(REFERENCE, shelf_count=0)).joints == carcass_layout(REFERENCE).joints
    )


def test_caisson_sans_tourillons_et_decale() -> None:
    params = replace(REFERENCE, joinery=CarcassJoinery.NONE, origin=Vec3(100, 50, 0))
    layout = carcass_layout(params)
    assert [j.kind for j in layout.joints] == [JointKind.RABBET] * 4
    assert layout.origin == Vec3(100, 50, 0)
    assert extents(layout.piece("right"))[0] == (582, 600)  # relatives à l'Origin


@pytest.mark.parametrize(
    ("thickness", "expected"),
    [(18, (8, 30, 12)), (12, (6, 20, 8)), (22, (10, 37, 15)), (16, (8, 27, 11))],
)
def test_tourillons_selon_l_epaisseur(thickness: float, expected: tuple[float, ...]) -> None:
    params = dowel_params(thickness, 4)
    assert (params.diameter, params.dowel_length, params.host_depth) == expected
    assert thickness - params.host_depth - params.hole_clearance >= 3  # fond de perçage
    assert params.edge_distance == 2 * params.diameter


@pytest.mark.parametrize(("back", "edge"), [(4, 16), (8, 16), (14, 22), (17.9, 25.9)])
def test_tourillons_devant_la_feuillure_du_fond(back: float, edge: float) -> None:
    """Le dernier perçage (rayon ½ Ø) reste à ½ Ø au moins devant la feuillure du fond."""
    params = dowel_params(18, back)
    assert params.edge_distance == pytest.approx(edge)
    assert params.edge_distance - params.diameter / 2 >= back + params.diameter / 2 - 1e-9


# --- K2 : validation des paramètres ---------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"width": 0.05}, "largeur"),
        ({"depth": math.inf}, "profondeur"),
        ({"height": 20_000.5}, "hauteur"),
        ({"thickness": 0}, "épaisseur des panneaux"),
        ({"thickness": 200}, "épaisseur des panneaux"),  # moitié de la profondeur
        ({"thickness": "18"}, "épaisseur des panneaux"),
        ({"back_thickness": 18}, "épaisseur du fond"),
        ({"back_thickness": -1}, "épaisseur du fond"),
        ({"rabbet_depth": 18.5}, "profondeur de la feuillure"),
        ({"rabbet_depth": 0}, "profondeur de la feuillure"),
        ({"shelf_count": 11}, "nombre d'étagères"),
        ({"shelf_count": -1}, "nombre d'étagères"),
        ({"shelf_count": 1.0}, "nombre d'étagères"),
        ({"shelf_count": True}, "nombre d'étagères"),
        ({"height": 100, "thickness": 18, "shelf_count": 4}, "nombre d'étagères"),
        ({"material_id": ""}, "matériau des panneaux"),
        ({"back_material_id": 3}, "matériau du fond"),
        ({"joinery": "Screws"}, "type d'assemblage"),
        ({"thickness": 11, "back_thickness": 6, "rabbet_depth": 6}, "épaisseur des panneaux"),
        ({"origin": Vec3(math.nan, 0, 0)}, "position du caisson"),
        ({"origin": (0, 0, 0)}, "position du caisson"),
    ],
)
def test_parametres_refuses(changes: dict[str, object], field: str) -> None:
    with pytest.raises(ValueError) as error:
        replace(REFERENCE, **changes)  # type: ignore[arg-type]
    assert isinstance(error.value, (CarcassError, FurnitureError))
    assert field in str(error.value) or error.value.params.get("field") == field


@pytest.mark.parametrize(
    "changes",
    [
        {"thickness": 199.99, "back_thickness": 1, "rabbet_depth": 199.99},  # < 400 / 2
        {"rabbet_depth": 18},  # feuillure = épaisseur
        {"back_thickness": 17.9},
        {"shelf_count": 0},
        {"shelf_count": MAX_SHELVES, "height": 2000},
        {"thickness": 12, "back_thickness": 6, "rabbet_depth": 6},  # tourillons de 6
        {"thickness": 10, "back_thickness": 5, "rabbet_depth": 5, "joinery": "None"},
        {"joinery": "Dowels"},
    ],
)
def test_cas_limites_acceptes(changes: dict[str, object]) -> None:
    params = replace(REFERENCE, **changes)  # type: ignore[arg-type]
    assert isinstance(params.joinery, CarcassJoinery)
    assert carcass_layout(params).pieces


def test_materiaux_connus() -> None:
    check_materials(REFERENCE, {"cp-bouleau", "chene"})
    with pytest.raises(CarcassError) as error:
        check_materials(replace(REFERENCE, back_material_id="inconnu"), {"cp-bouleau"})
    assert error.value.params["field"] == "matériau du fond"
    assert error.value.params["value"] == "inconnu"


# --- Objets valeur du Layout ----------------------------------------------------------------


def test_objets_valeur_du_layout_valides() -> None:
    layout = carcass_layout(REFERENCE)
    piece = layout.pieces[0]
    with pytest.raises(ValueError, match="clés uniques"):
        replace(layout, pieces=(piece, piece))
    with pytest.raises(ValueError, match="pièces du gabarit"):
        replace(layout, joints=(JointSpec(JointKind.RABBET, "left", "ailleurs", RabbetParams()),))
    with pytest.raises(ValueError, match="fixed"):
        replace(piece, fixed=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="distinctes"):
        JointSpec(JointKind.RABBET, "left", "left", RabbetParams())
    with pytest.raises(ValueError, match="objet valeur"):
        JointSpec(JointKind.RABBET, "left", "back", {"through": True})
    with pytest.raises(ValueError, match="textes"):
        Layout("", "Caisson", layout.box, layout.origin, layout.pieces)
    with pytest.raises(KeyError):
        layout.piece("absente")
