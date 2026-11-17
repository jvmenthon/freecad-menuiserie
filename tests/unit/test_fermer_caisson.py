# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarit « Fermer le caisson » en Python pur (ADR 0064, critères FC1 à FC3, FC7 et FC9 de
``docs/specs/fermer-le-caisson.md``)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.furniture import Edge, InteriorMode
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dowels import DowelParams
from freecad.menuiserie.core.templates import Layout
from freecad.menuiserie.core.templates.carcass import CarcassParams, carcass_layout
from freecad.menuiserie.core.templates.closing import (
    ANCHOR_KEY,
    CLOSING_TEMPLATE,
    closing_layout,
    nearest_front,
)
from freecad.menuiserie.core.templates.closing_params import (
    ClosingError,
    ClosingParams,
    ClosingRole,
    Element,
    check_materials,
)
from tests.unit.aides_fermeture import ANCHOR, layout, pairs, params, sizes, spans

ALL = frozenset(Edge)
L, R, F, B, D, T = Edge  # gauche, droite, avant, arrière, bas, haut


# --- FC1 : ancre 600 x 400 x 18 prise pour le dessous, hauteur 720 ---------------------------


def test_fc1_pieces_du_caisson_de_reference() -> None:
    result = layout()
    assert [piece.key for piece in result.pieces] == ["anchor", "left", "right", "back", "opposite"]
    expected = {  # clé : (L x l x e, étendues X, Y, Z, distances fixes)
        "anchor": ((600, 400, 18), [(0, 600), (0, 400), (0, 18)], ALL - {T}),
        "left": ((684, 400, 18), [(0, 18), (0, 400), (18, 702)], ALL - {R}),
        "right": ((684, 400, 18), [(582, 600), (0, 400), (18, 702)], ALL - {L}),
        "back": ((704, 584, 8), [(8, 592), (392, 400), (8, 712)], ALL - {F}),
        "opposite": ((600, 400, 18), [(0, 600), (0, 400), (702, 720)], ALL - {D}),
    }
    for key, (size, extents, fixed) in expected.items():
        piece = result.piece(key)
        assert sizes(piece.block) == size, key
        assert spans(result, key) == extents, key
        assert piece.fixed == fixed, key
        assert piece.mode is InteriorMode.STAY, key
    assert {piece.material_id for piece in result.pieces} == {"cp-bouleau"}


def test_fc1_ensemble_et_ancre() -> None:
    result = layout()
    assert (result.template, result.anchor) == (CLOSING_TEMPLATE, ANCHOR_KEY)
    assert CLOSING_TEMPLATE == "ClosedCarcass"
    assert (result.box.width, result.box.depth, result.box.height) == (600, 400, 720)
    assert result.origin == Vec3(0, 0, 0)
    anchor = result.piece(ANCHOR_KEY).block
    assert anchor.dimensions == ANCHOR  # l'ancre est décrite telle qu'elle est
    assert anchor.placement.translation == Vec3(0, 0, 0)


def test_fc1_quatre_tourillons_et_quatre_feuillures() -> None:
    result = layout()
    assert pairs(result) == [
        ("DOWELS", "anchor", "left"),
        ("DOWELS", "opposite", "left"),
        ("DOWELS", "anchor", "right"),
        ("DOWELS", "opposite", "right"),
        ("RABBET", "left", "back"),
        ("RABBET", "right", "back"),
        ("RABBET", "anchor", "back"),
        ("RABBET", "opposite", "back"),
    ]
    assert len(result.joints_of(JointKind.DOWELS)) == 4
    assert len(result.joints_of(JointKind.RABBET)) == 4


def test_fc1_tourillons_de_18_comme_le_gabarit_caisson() -> None:
    dowels = layout().joints_of(JointKind.DOWELS)[0].params
    assert isinstance(dowels, DowelParams)
    assert (dowels.diameter, dowels.dowel_length, dowels.host_depth) == (8.0, 30.0, 12.0)
    assert dowels.edge_distance == 16.0  # 2 Ø, plus que fond (8) + Ø


def test_fc1_epaisseurs_et_materiaux_de_l_ancre_par_defaut() -> None:
    thick = ClosingParams(ANCHOR.__class__(500.0, 300.0, 25.0), "chene")
    result = closing_layout(thick)
    assert sizes(result.piece("left").block)[2] == 25
    assert sizes(result.piece("opposite").block)[2] == 25
    assert sizes(result.piece("back").block)[2] == 8  # fond mince : 8 mm au plus
    assert {piece.material_id for piece in result.pieces} == {"chene"}


def test_fc1_epaisseurs_et_materiaux_modifiables() -> None:
    result = layout(
        thickness=19.0,
        opposite_thickness=22.0,
        back_thickness=5.0,
        material_id="chene",
        opposite_material_id="noyer",
        back_material_id="hdf",
    )
    assert spans(result, "left") == [(0, 19), (0, 400), (18, 698)]
    assert spans(result, "opposite")[2] == (698, 720)
    assert sizes(result.piece("back").block)[2] == 5
    materials = {piece.key: piece.material_id for piece in result.pieces}
    assert materials == {
        "anchor": "cp-bouleau",
        "left": "chene",
        "right": "chene",
        "back": "hdf",
        "opposite": "noyer",
    }


# --- FC2 : la même ancre prise pour le dessus -------------------------------------------------


def test_fc2_le_caisson_descend() -> None:
    result = layout(role=ClosingRole.TOP)
    expected = {
        "anchor": [(0, 600), (0, 400), (0, 18)],
        "left": [(0, 18), (0, 400), (-684, 0)],
        "right": [(582, 600), (0, 400), (-684, 0)],
        "opposite": [(0, 600), (0, 400), (-702, -684)],
        "back": [(8, 592), (392, 400), (-694, 10)],
    }
    for key, extents in expected.items():
        assert spans(result, key) == extents, key
    assert result.origin == Vec3(0, 0, -702)  # coin bas : l'ensemble couvre z de -702 à 18
    assert result.box.height == 720
    assert result.piece("anchor").fixed == ALL - {D}
    assert result.piece("opposite").fixed == ALL - {T}


def test_fc2_libelles_selon_le_role() -> None:
    labels = {piece.key: piece.label for piece in layout(role=ClosingRole.TOP).pieces}
    assert (labels["anchor"], labels["opposite"]) == ("Dessus", "Dessous")
    labels = {piece.key: piece.label for piece in layout().pieces}
    assert (labels["anchor"], labels["opposite"]) == ("Dessous", "Dessus")


# --- FC3 : éléments désactivés ----------------------------------------------------------------


def test_fc3_sans_piece_opposee_les_cotes_font_702() -> None:
    result = layout(elements=params().elements - {Element.OPPOSITE})
    assert "opposite" not in {piece.key for piece in result.pieces}
    assert spans(result, "left")[2] == (18, 720)
    assert sizes(result.piece("left").block) == (702, 400, 18)
    assert spans(result, "back")[2] == (8, 720)  # le fond monte jusqu'au bout des côtés
    assert pairs(result) == [
        ("DOWELS", "anchor", "left"),
        ("DOWELS", "anchor", "right"),
        ("RABBET", "left", "back"),
        ("RABBET", "right", "back"),
        ("RABBET", "anchor", "back"),
    ]


def test_fc3_sans_fond_ni_feuillure() -> None:
    result = layout(elements=params().elements - {Element.BACK})
    assert "back" not in {piece.key for piece in result.pieces}
    assert not result.joints_of(JointKind.RABBET)
    assert len(result.joints_of(JointKind.DOWELS)) == 4


def test_fc3_sans_cote_droit_ni_ses_assemblages() -> None:
    result = layout(elements=params().elements - {Element.RIGHT})
    assert "right" not in {piece.key for piece in result.pieces}
    assert all("right" not in (j.host, j.guest) for j in result.joints)
    assert pairs(result) == [
        ("DOWELS", "anchor", "left"),
        ("DOWELS", "opposite", "left"),
        ("RABBET", "left", "back"),
        ("RABBET", "anchor", "back"),
        ("RABBET", "opposite", "back"),
    ]
    assert spans(result, "back")[0] == (8, 600)  # fond à fleur du côté sans côté droit


def test_fc3_ancre_seule() -> None:
    result = layout(elements=frozenset())
    assert [piece.key for piece in result.pieces] == ["anchor"]
    assert result.joints == ()


def test_avant_actif_entre_les_cotes() -> None:
    result = layout(elements=params().elements | {Element.FRONT})
    assert spans(result, "front") == [(18, 582), (0, 18), (18, 702)]
    assert result.piece("front").fixed == ALL - {B}
    assert pairs(result)[4:6] == [("DOWELS", "left", "front"), ("DOWELS", "right", "front")]


# --- Variantes d'assemblage -------------------------------------------------------------------


def test_onglet_cotes_hors_tout_qui_chevauchent_l_ancre_et_le_dessus() -> None:
    result = layout(joinery="Miter")
    assert sizes(result.piece("left").block) == (720, 400, 18)
    assert spans(result, "left")[2] == (0, 720)
    miters = result.joints_of(JointKind.MITER)
    assert [(j.host, j.guest) for j in miters] == [
        ("anchor", "left"),
        ("opposite", "left"),
        ("anchor", "right"),
        ("opposite", "right"),
    ]
    assert not result.joints_of(JointKind.DOWELS)


def test_onglet_sans_assemblage_pour_l_avant() -> None:
    result = layout(joinery="Miter", elements=params().elements | {Element.FRONT})
    assert len(result.joints_of(JointKind.MITER)) == 4
    assert all("front" not in (j.host, j.guest) for j in result.joints_of(JointKind.MITER))


@pytest.mark.parametrize(
    ("joinery", "kind"),
    [("Dowels", JointKind.DOWELS), ("Dovetail", JointKind.DOVETAIL), ("Rabbet", JointKind.RABBET)],
)
def test_un_seul_assemblage_pour_tous_les_angles(joinery: str, kind: JointKind) -> None:
    result = layout(joinery=joinery, elements=params().elements | {Element.FRONT})
    corners = [j for j in result.joints if j.guest != "back"]
    assert {j.kind for j in corners} == {kind}
    assert len(corners) == 6  # quatre angles côté ↔ ancre ou dessus, deux angles avec l'avant


def test_sans_assemblage_des_cotes() -> None:
    result = layout(joinery="None")
    assert {j.kind for j in result.joints} == {JointKind.RABBET}
    assert all(j.guest == "back" for j in result.joints)


def test_fond_en_rainure() -> None:
    result = layout(back_joinery="Groove")
    assert spans(result, "back") == [(18, 582), (382, 390), (18, 702)]  # reculé de 10 mm
    grooves = result.joints_of(JointKind.TONGUE_GROOVE)
    assert [j.host for j in grooves] == ["left", "right", "anchor", "opposite"]
    assert not result.joints_of(JointKind.RABBET)


def test_fond_pose_sans_assemblage() -> None:
    result = layout(back_joinery="None")
    assert spans(result, "back") == [(18, 582), (392, 400), (18, 702)]
    assert all(j.guest != "back" for j in result.joints)


def test_fond_epais_entre_les_cotes_avec_l_assemblage_des_cotes() -> None:
    result = layout(thick_back=True, thickness=18.0)
    assert spans(result, "back") == [(18, 582), (382, 400), (18, 702)]
    assert sizes(result.piece("back").block)[2] == 18
    assert [(j.host, j.guest) for j in result.joints if j.guest == "back"] == [
        ("left", "back"),
        ("right", "back"),
    ]
    assert not result.joints_of(JointKind.RABBET)


def test_profondeur_de_feuillure_reduite_aux_pieces_minces() -> None:
    thin = layout(opposite_thickness=6.0, joinery="None")
    # feuillure de 10 mm dans le côté et l'ancre, mais 6 mm dans le dessus : r = 6
    assert spans(thin, "back")[0] == (12, 588)  # retrait = t - r = 18 - 6
    assert params(opposite_thickness=6.0, joinery="None").rabbet_depth == 6.0
    assert params().rabbet_depth == 10.0


# --- Avant du caisson : quarts de tour --------------------------------------------------------


@pytest.mark.parametrize("turns", [0, 1, 2, 3])
def test_l_ancre_occupe_toujours_le_dessous_du_caisson_tourne(turns: int) -> None:
    result = layout(front_turns=turns)
    wide = (400.0, 600.0) if turns % 2 else (600.0, 400.0)
    assert spans(result, "anchor") == [(0, wide[0]), (0, wide[1]), (0, 18)]
    assert (result.box.width, result.box.depth) == wide
    for piece in result.pieces:  # repères directs : aucune pièce en miroir
        rows = piece.block.placement.rotation
        det = (
            rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
            - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
            + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
        )
        assert det == pytest.approx(1.0), piece.key


def test_quart_de_tour_transforme_les_axes_de_l_ancre() -> None:
    # Avant sur le bord X = longueur de l'ancre : le X de l'ancre devient la profondeur.
    anchor = layout(front_turns=1).piece("anchor").block.placement
    assert anchor.apply(Vec3(600, 0, 0)) == Vec3(0, 0, 0)  # bout de l'ancre à l'avant
    assert anchor.apply(Vec3(0, 0, 0)) == Vec3(0, 600, 0)
    assert anchor.apply(Vec3(0, 400, 0)) == Vec3(400, 600, 0)


def test_demi_tour_garde_les_cotes() -> None:
    result = layout(front_turns=2)
    assert spans(result, "left") == spans(layout(), "left")
    placement = result.piece("anchor").block.placement
    assert placement.apply(Vec3(0, 0, 0)) == Vec3(600, 400, 0)


# --- FC7 : refus -------------------------------------------------------------------------------


def _field(error: ClosingError) -> str:
    return str(error.params["field"])


def test_fc7_hauteur_trop_faible() -> None:
    minimum = 18 + 18 + 1  # ancre + dessus + 1 mm d'intérieur
    for height in (0.0, -5.0, 36.0, minimum - 0.01):
        with pytest.raises(ClosingError, match="hauteur hors tout") as caught:
            params(height=height)
        assert _field(caught.value) == "hauteur hors tout"
    assert layout(height=minimum).box.height == minimum  # au minimum : accepté
    assert layout(height=minimum - 18, elements=frozenset({Element.LEFT})).box.height == 19


@pytest.mark.parametrize("height", [float("nan"), float("inf"), 20_001.0, True, "720", None])
def test_fc7_hauteur_illisible_ou_enorme(height: object) -> None:
    with pytest.raises(ClosingError, match="hauteur hors tout"):
        params(height=height)


def test_fc7_tourillons_sous_12_mm() -> None:
    for thickness in (11.99, 10.0, 1.0):
        with pytest.raises(ClosingError, match="12 mm pour des tourillons") as caught:
            params(thickness=thickness)
        assert _field(caught.value) == "épaisseur des côtés"
    assert params(thickness=12.0).side_t == 12.0
    assert layout(thickness=12.0, joinery="None").box.width == 600  # sans tourillons : accepté


def test_fc7_tourillons_et_pieces_minces() -> None:
    thin = ANCHOR.__class__(600.0, 400.0, 10.0)
    with pytest.raises(ClosingError, match="pièce sélectionnée"):
        ClosingParams(thin, "cp-bouleau", thickness=18.0)
    with pytest.raises(ClosingError, match="pièce opposée"):
        params(opposite_thickness=8.0)
    assert params(opposite_thickness=8.0, joinery="Rabbet").opposite_t == 8.0
    assert params(opposite_thickness=8.0, elements=frozenset({Element.LEFT, Element.RIGHT}))


@pytest.mark.parametrize("name", ["thickness", "opposite_thickness", "back_thickness"])
@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf"), True, "18"])
def test_fc7_epaisseurs_nulles_ou_illisibles(name: str, value: object) -> None:
    with pytest.raises(ClosingError):
        params(joinery="None", **{name: value})


def test_fc7_epaisseur_des_cotes_au_plus_la_moitie_de_la_plus_petite_cote() -> None:
    with pytest.raises(ClosingError, match="moitié") as caught:
        params(joinery="None", thickness=200.0)
    assert caught.value.params["max"] == "200"
    assert params(joinery="None", thickness=199.99).side_t == 199.99


def test_fc7_matiere_inconnue() -> None:
    known = {"cp-bouleau", "chene"}
    check_materials(params(material_id="chene"), known)
    for field in ("material_id", "opposite_material_id", "back_material_id"):
        with pytest.raises(ClosingError, match="inconnu") as caught:
            check_materials(params(**{field: "pas-un-bois"}), known)
        assert "pas-un-bois" in str(caught.value)


@pytest.mark.parametrize("value", ["", 3, True, ["a"]])
def test_fc7_materiau_invalide(value: object) -> None:
    with pytest.raises(ClosingError, match="matériau"):
        params(material_id=value)


@pytest.mark.parametrize("turns", [-1, 4, 1.0, True, "0", None])
def test_fc7_quarts_de_tour_bornes(turns: object) -> None:
    with pytest.raises(ClosingError, match="avant du caisson"):
        params(front_turns=turns)


@pytest.mark.parametrize(
    "changes",
    [{"joinery": "Colle"}, {"back_joinery": "Clous"}, {"role": "milieu"}, {"elements": {"toit"}}],
)
def test_fc7_choix_inconnus(changes: dict[str, object]) -> None:
    with pytest.raises(ClosingError, match="inconnu"):
        params(**changes)


def test_fc7_ancre_qui_n_est_pas_un_bloc() -> None:
    with pytest.raises(ClosingError, match="pièce sélectionnée"):
        ClosingParams((600.0, 400.0, 18.0), "cp-bouleau")  # type: ignore[arg-type]


def test_fc7_message_en_francais_et_gabarit_traduisible() -> None:
    with pytest.raises(ClosingError) as caught:
        params(height=30.0)
    assert caught.value.template.startswith("Fermer le caisson : {field} = {value} mm")
    assert "hauteur hors tout = 30 mm" in str(caught.value)


# --- FC9 : le gabarit Caisson ne change pas ----------------------------------------------------


def test_fc9_le_gabarit_caisson_n_a_pas_d_ancre() -> None:
    result = carcass_layout(CarcassParams())
    assert result.anchor is None
    assert [piece.key for piece in result.pieces] == [
        "left",
        "right",
        "bottom",
        "top",
        "back",
        "shelf1",
    ]
    assert len(result.joints) == 8
    assert result.template == "Carcass"


def test_fc9_layout_inchange_par_defaut() -> None:
    result = carcass_layout(CarcassParams())
    same = Layout(
        result.template,
        result.label,
        result.box,
        result.origin,
        result.pieces,
        result.joints,
    )
    assert same == result  # champ ajouté : ``anchor`` vaut ``None`` par défaut


def test_layout_refuse_une_ancre_inconnue() -> None:
    result = layout()
    with pytest.raises(ValueError, match="anchor"):
        Layout(result.template, result.label, result.box, result.origin, result.pieces, anchor="x")


# --- Avant le plus proche de l'observateur ------------------------------------------------------


@pytest.mark.parametrize(
    ("viewer", "turns"),
    [
        ((300, -5000, 400), 0),  # devant : bord Y = 0
        ((300, 5000, 400), 2),  # derrière : bord Y = largeur
        ((5000, 100, 400), 0),  # sur le côté : toujours un grand chant, le plus proche
        ((5000, 300, 400), 2),
        ((300, 200, 400), 0),  # au-dessus du milieu : égalité, le premier
    ],
)
def test_avant_sur_le_grand_chant_le_plus_proche(
    viewer: tuple[float, float, float], turns: int
) -> None:
    assert nearest_front(ANCHOR, Vec3(*viewer)) == turns


def test_avant_sur_les_chants_de_la_largeur_pour_une_ancre_plus_large_que_longue() -> None:
    wide = ANCHOR.__class__(400.0, 600.0, 18.0)  # grands chants : X = 0 et X = longueur
    assert nearest_front(wide, Vec3(5000, 300, 0)) == 1
    assert nearest_front(wide, Vec3(-5000, 300, 0)) == 3
