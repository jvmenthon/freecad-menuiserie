# SPDX-License-Identifier: LGPL-2.1-or-later
"""Règles pures des profils d'arête (issue #5, lot CH-a, ADR 0029 : critères A1 à A7)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core._extrusion import Arc, Extrusion, Section, Segment
from freecad.menuiserie.core.edges import (
    BROKEN_EDGE_MM,
    FAMILIES,
    OVERSHOOT_MM,
    EdgeError,
    EdgeFamily,
    EdgeId,
    all_edges,
    broken_edge_cut,
    edge_code,
    edge_cut,
    face_edges,
    loop_edges,
    parse_edge,
    parse_face,
)
from freecad.menuiserie.core.geometry import Axis, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from tests.unit.aides import ROOT, imported_modules

PIECE = Dimensions(600.0, 300.0, 20.0)


# --- A1 : désignation des arêtes ----------------------------------------------------------


def test_aller_retour_code_et_nom_des_douze_aretes() -> None:
    edges = all_edges()
    assert len(edges) == len({edge.code for edge in edges}) == 12
    for edge in edges:
        assert parse_edge(edge_code(edge)) == edge
        assert parse_edge(edge.name) == edge


def test_code_et_nom_connus() -> None:
    edge = parse_edge("Z+Y-")
    assert (edge.name, edge.code, edge.along) == ("dessus-avant", "Z+Y-", 0)
    assert parse_edge("dessous-droite").code == "Z-X+"
    assert parse_edge("arrière-gauche").code == "Y+X-"


@pytest.mark.parametrize(
    "text",
    ["", "Z+", "Z+Z-", "Y-Z+", "Z+Y", "z+y-", "dessus-dessous", "avant-dessus", "dessus", "A+B-",
     "Z+Y-X+", "dessus-avant-gauche", "Z+Y-\n", "Z\uff0bY-"],
)  # fmt: skip
def test_chaine_refusee(text: str) -> None:
    with pytest.raises(EdgeError):
        parse_edge(text)


def test_type_incorrect_refuse() -> None:
    with pytest.raises(EdgeError):
        parse_edge(None)  # type: ignore[arg-type]


def test_message_cite_le_texte_sans_le_laisser_passer_brut() -> None:
    with pytest.raises(EdgeError) as error:
        parse_edge("Z+‮")
    assert "‮" not in str(error.value)


def test_arete_exige_deux_faces_perpendiculaires_dans_l_ordre() -> None:
    with pytest.raises(ValueError, match="parallèles"):
        EdgeId(Axis.Z_POS, Axis.Z_NEG)
    with pytest.raises(ValueError, match="ordre"):
        EdgeId(Axis.Y_NEG, Axis.Z_POS)
    assert EdgeId.between(Axis.Y_NEG, Axis.Z_POS) == EdgeId(Axis.Z_POS, Axis.Y_NEG)


# --- A2 : raccourcis ----------------------------------------------------------------------


def test_aretes_d_une_face() -> None:
    top = face_edges(Axis.Z_POS)
    assert sorted(edge.code for edge in top) == ["Z+X+", "Z+X-", "Z+Y+", "Z+Y-"]
    assert loop_edges("Z+") == top == loop_edges("dessus")
    assert {edge.code for edge in loop_edges("X-")} == {"Z+X-", "Z-X-", "Y+X-", "Y-X-"}


def test_chaque_arete_touche_deux_faces_et_chaque_face_quatre_aretes() -> None:
    edges = all_edges()
    for face in Axis:
        assert sum(face in (edge.first, edge.second) for edge in edges) == 4


def test_face_inconnue_refusee() -> None:
    with pytest.raises(EdgeError):
        loop_edges("W+")


def test_parse_face() -> None:
    assert parse_face("Y-") is Axis.Y_NEG
    assert parse_face("arrière") is Axis.Y_POS


# --- A3 : sections ------------------------------------------------------------------------


def _section(family: EdgeFamily, a: float, b: float) -> Section:
    strategy = FAMILIES[family]
    return strategy.section(a, b)


AREAS = [
    (EdgeFamily.CHAMFER, 4.0, 3.0, 4.0 * 3.0 / 2),
    (EdgeFamily.ROUND, 5.0, 5.0, (1 - math.pi / 4) * 25.0),
    (EdgeFamily.ROUND, 6.0, 3.0, (1 - math.pi / 4) * 18.0),
    (EdgeFamily.COVE, 4.0, 4.0, math.pi / 4 * 16.0),
    (EdgeFamily.BULLNOSE, 5.0, 5.0, (1 - math.pi / 4) * 25.0),
    (EdgeFamily.BEAK, 4.0, 3.0, 4.0 * 3.0 + (1 - math.pi / 4) * 16.0),
    (EdgeFamily.OGEE, 8.0, 6.0, 8.0 * 6.0 / 2),
]


@pytest.mark.parametrize(("family", "a", "b", "area"), AREAS)
def test_aire_et_contour_valide(family: EdgeFamily, a: float, b: float, area: float) -> None:
    section = _section(family, a, b)
    assert section.area() == pytest.approx(area, rel=1e-9)
    # Contenue dans l'encombrement de la famille, et collée aux deux faces de l'angle.
    (low_p, low_q), (high_p, high_q) = section.bounds()
    extent = FAMILIES[family].extent(a, b)
    assert (low_p, low_q) == pytest.approx((0.0, 0.0))
    assert high_p <= extent[0] + 1e-9
    assert high_q <= extent[1] + 1e-9


def test_section_dans_le_carre_a_par_b() -> None:
    for family in (EdgeFamily.CHAMFER, EdgeFamily.ROUND, EdgeFamily.OGEE):
        assert FAMILIES[family].extent(7.0, 3.0) == (7.0, 3.0)
        assert _section(family, 7.0, 3.0).bounds()[1] == pytest.approx((7.0, 3.0))
    assert FAMILIES[EdgeFamily.BEAK].extent(4.0, 3.0) == (4.0, 7.0)
    assert _section(EdgeFamily.BEAK, 4.0, 3.0).bounds()[1] == pytest.approx((4.0, 7.0))


def test_les_arcs_sont_tangents_aux_faces() -> None:
    arc = _section(EdgeFamily.ROUND, 5.0, 5.0).elements[1]
    assert isinstance(arc, Arc)
    assert arc.start == pytest.approx((5.0, 0.0))
    assert arc.end == pytest.approx((0.0, 5.0))
    assert math.dist(arc.middle, (5.0, 5.0)) == pytest.approx(5.0)  # sur le cercle


def test_doucine_en_s_est_tangente_au_raccord() -> None:
    cove, round_part = _section(EdgeFamily.OGEE, 8.0, 6.0).elements[1:3]
    assert isinstance(cove, Arc)
    assert isinstance(round_part, Arc)
    assert cove.end == pytest.approx(round_part.start)
    assert cove.end == pytest.approx((4.0, 3.0))  # milieu de l'encombrement


def test_section_refuse_un_contour_ouvert_ou_qui_se_recoupe() -> None:
    with pytest.raises(ValueError, match="fermé"):
        Section((Segment((0, 0), (1, 0)), Segment((1, 0), (1, 1)), Segment((1, 1), (0.5, 0))))
    bow_tie = (
        Segment((0, 0), (2, 2)),
        Segment((2, 2), (2, 0)),
        Segment((2, 0), (0, 2)),
        Segment((0, 2), (0, 0)),
    )
    with pytest.raises(ValueError, match="recoupe"):
        Section(bow_tie)
    clockwise = (Segment((0, 0), (0, 1)), Segment((0, 1), (1, 0)), Segment((1, 0), (0, 0)))
    with pytest.raises(ValueError, match="aire"):
        Section(clockwise)
    with pytest.raises(ValueError, match="deux"):
        Section((Segment((0, 0), (1, 0)),))


def test_arc_refuse_les_valeurs_invalides() -> None:
    with pytest.raises(ValueError, match="arc"):
        Arc((0, 0), 0.0, 1.0, 0.0, 1.0)
    with pytest.raises(ValueError, match="arc"):
        Arc((0, 0), 1.0, 1.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="finies"):
        Arc((0, 0), 1.0, math.inf, 0.0, 1.0)


# --- A4 : coupe d'une arête ---------------------------------------------------------------


def test_coupe_balaye_toute_l_arete_avec_un_depassement() -> None:
    cut = edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.CHAMFER, 4.0, 3.0)
    assert isinstance(cut, Extrusion)
    assert cut.length == pytest.approx(600.0 + 2 * OVERSHOOT_MM)
    assert cut.origin == Vec3(-OVERSHOOT_MM, 0.0, 20.0)  # arête dessus-avant : y = 0, z = e
    assert cut.direction == Vec3(1.0, 0.0, 0.0)
    assert cut.volume() == pytest.approx(6.0 * (600.0 + 2 * OVERSHOOT_MM))


def test_la_section_penetre_dans_la_piece() -> None:
    """Pour chacune des 12 arêtes, les points de la section sont dans la boîte de la pièce."""
    for edge in all_edges():
        cut = edge_cut(PIECE, edge, EdgeFamily.CHAMFER, 4.0, 3.0)
        sizes = (PIECE.length, PIECE.width, PIECE.thickness)
        for u, v in ((0.0, 0.0), (4.0, 0.0), (0.0, 3.0)):
            for along in (0.0, cut.length):
                point = cut.point(u, v, along)
                for index in range(3):
                    value = point.component(index)
                    assert -OVERSHOOT_MM - 1e-9 <= value <= sizes[index] + OVERSHOOT_MM + 1e-9


def test_a_porte_sur_la_premiere_face_et_b_sur_la_seconde() -> None:
    cut = edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.CHAMFER, 4.0, 3.0)
    on_top = cut.point(4.0, 0.0)  # a le long du dessus (Z+), vers l'intérieur (+Y)
    on_front = cut.point(0.0, 3.0)  # b le long de l'avant (Y-), vers le bas (-Z)
    assert (on_top.y, on_top.z) == pytest.approx((4.0, 20.0))
    assert (on_front.y, on_front.z) == pytest.approx((0.0, 17.0))


def test_coin_oppose_arete_derriere_droite() -> None:
    cut = edge_cut(PIECE, parse_edge("Y+X+"), EdgeFamily.ROUND, 5.0)
    assert cut.origin == Vec3(600.0, 300.0, -OVERSHOOT_MM)
    assert cut.direction == Vec3(0.0, 0.0, 1.0)
    assert cut.length == pytest.approx(20.0 + 2 * OVERSHOOT_MM)
    assert cut.point(5.0, 0.0) == Vec3(595.0, 300.0, -OVERSHOOT_MM)


def test_repere_de_la_coupe_est_orthonormal_direct_ou_indirect() -> None:
    for edge in all_edges():
        cut = edge_cut(PIECE, edge, EdgeFamily.OGEE, 4.0, 3.0)
        assert abs(sum(cut.u_axis.component(i) * cut.v_axis.component(i) for i in range(3))) == 0


def test_arete_cassee_est_un_quart_de_rond_de_1_mm() -> None:
    cut = broken_edge_cut(PIECE, parse_edge("Z+X-"))
    assert BROKEN_EDGE_MM == 1.0
    assert cut.section.area() == pytest.approx((1 - math.pi / 4) * 1.0)
    assert cut.section == edge_cut(PIECE, parse_edge("Z+X-"), EdgeFamily.ROUND, 1.0).section


def test_b_nul_vaut_a_pour_le_chanfrein_et_le_quart_de_rond() -> None:
    assert edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.CHAMFER, 3.0, 0.0).section.area() == (
        pytest.approx(4.5)
    )
    assert edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.ROUND, 3.0, 0.0).section == _section(
        EdgeFamily.ROUND, 3.0, 3.0
    )


def test_b_ignore_pour_la_gorge_et_le_demi_rond() -> None:
    for family in (EdgeFamily.COVE, EdgeFamily.BULLNOSE):
        assert (
            edge_cut(PIECE, parse_edge("Z+Y-"), family, 3.0, 9.0).section
            == edge_cut(PIECE, parse_edge("Z+Y-"), family, 3.0, 0.0).section
        )


# --- A5 : bornes --------------------------------------------------------------------------


@pytest.mark.parametrize("size", [0.0, 0.05, -1.0, math.nan, math.inf])
def test_cote_trop_petite_ou_invalide_refusee(size: float) -> None:
    with pytest.raises(EdgeError, match="dessus-avant"):
        edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.CHAMFER, size, 1.0)


def test_cote_minimale_acceptee() -> None:
    assert edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.CHAMFER, 0.1, 0.1).volume() > 0


def test_b_obligatoire_pour_la_doucine_et_le_bec_de_corbin() -> None:
    for family in (EdgeFamily.OGEE, EdgeFamily.BEAK):
        with pytest.raises(EdgeError):
            edge_cut(PIECE, parse_edge("Z+Y-"), family, 4.0, 0.0)


def test_encombrement_limite_a_la_moitie_de_la_piece_dans_chaque_sens() -> None:
    # Épaisseur 20 : b au plus 10 le long de l'avant ; largeur 300 : a jusqu'à 150 sur le dessus.
    assert edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.CHAMFER, 150.0, 10.0).volume() > 0
    with pytest.raises(EdgeError) as error:
        edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.CHAMFER, 4.0, 10.5)
    message = str(error.value)
    assert "dessus-avant" in message
    assert "10" in message
    assert "150" in message
    with pytest.raises(EdgeError):
        edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.CHAMFER, 150.5, 4.0)


def test_bec_de_corbin_compte_le_epaulement_dans_l_encombrement() -> None:
    assert edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.BEAK, 4.0, 6.0).volume() > 0
    with pytest.raises(EdgeError):
        edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.BEAK, 4.0, 6.5)


def test_deux_aretes_opposees_au_maximum_ne_se_recouvrent_pas() -> None:
    top = edge_cut(PIECE, parse_edge("Z+Y-"), EdgeFamily.ROUND, 10.0)
    bottom = edge_cut(PIECE, parse_edge("Z-Y-"), EdgeFamily.ROUND, 10.0)
    z_top = [top.point(0.0, 10.0).z, top.point(0.0, 0.0).z]
    z_bottom = [bottom.point(0.0, 10.0).z, bottom.point(0.0, 0.0).z]
    assert min(z_top) >= max(z_bottom) - 1e-9  # elles se touchent au plus à mi-épaisseur


def test_demi_rond_au_maximum_est_un_demi_cercle() -> None:
    thin = Dimensions(300.0, 100.0, 20.0)
    cut = edge_cut(thin, parse_edge("Z+Y-"), EdgeFamily.BULLNOSE, 10.0)
    assert cut.section.area() == pytest.approx((1 - math.pi / 4) * 100.0)


# --- A6 : registre ------------------------------------------------------------------------


def test_une_strategie_par_famille() -> None:
    assert set(FAMILIES) == set(EdgeFamily)
    for family, strategy in FAMILIES.items():
        assert strategy.family is family


def test_valeurs_de_la_propriete_freecad_figees() -> None:
    values = [family.value for family in EdgeFamily]
    assert values == ["Chamfer", "Round", "Cove", "Bullnose", "Beak", "Ogee"]


def test_famille_inconnue_refusee() -> None:
    with pytest.raises(ValueError, match="Spline"):
        edge_cut(PIECE, parse_edge("Z+Y-"), "Spline", 1.0, 1.0)  # type: ignore[arg-type]


# --- Extrusion ---------------------------------------------------------------------------


def test_extrusion_refuse_des_axes_incorrects() -> None:
    section = _section(EdgeFamily.CHAMFER, 1.0, 1.0)
    x, y, z = Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)
    zero = Vec3(0, 0, 0)
    assert Extrusion(section, zero, x, y, z, 5.0).volume() == pytest.approx(2.5)
    with pytest.raises(ValueError, match="longueur"):
        Extrusion(section, zero, x, y, z, 0.0)
    with pytest.raises(ValueError, match="unitaires"):
        Extrusion(section, zero, Vec3(2, 0, 0), y, z, 1.0)
    with pytest.raises(ValueError, match="orthogonaux"):
        Extrusion(section, zero, x, x, z, 1.0)
    with pytest.raises(ValueError, match="orthogonaux"):
        Extrusion(section, zero, x, y, x, 1.0)


# --- A7 : pureté -------------------------------------------------------------------------


def test_core_edges_n_importe_ni_freecad_ni_qt() -> None:
    forbidden = ("FreeCAD", "FreeCADGui", "Part", "PySide", "PySide2", "PySide6", "pivy")
    folder = ROOT / "freecad" / "menuiserie" / "core"
    for path in [*sorted((folder / "edges").glob("*.py")), folder / "_extrusion.py"]:
        for module in imported_modules(path):
            assert module.split(".")[0] not in forbidden, (path.name, module)


# --- Choix en 3D (C3, spécification § 4.5) -------------------------------------------------


def test_arete_la_plus_proche_d_un_point() -> None:
    from freecad.menuiserie.core.edges import nearest_edge

    # Milieu de l'arête dessus-avant : x = L/2, y = 0, z = e.
    assert nearest_edge(PIECE, Vec3(300.0, 0.0, 20.0)).code == "Z+Y-"
    assert nearest_edge(PIECE, Vec3(600.0, 300.0, 10.0)).code == "Y+X+"
    # Un point à peine décalé (arête déjà chanfreinée) se rapproche de la même arête.
    assert nearest_edge(PIECE, Vec3(301.0, 2.5, 17.5)).code == "Z+Y-"


def test_chaque_arete_se_retrouve_par_son_milieu() -> None:
    from freecad.menuiserie.core.edges import nearest_edge

    sizes = (PIECE.length, PIECE.width, PIECE.thickness)
    for edge in all_edges():
        values = [sizes[i] / 2 for i in range(3)]
        for face in (edge.first, edge.second):
            values[face.index] = sizes[face.index] if face.sign > 0 else 0.0
        assert nearest_edge(PIECE, Vec3.of(values)) == edge


def test_morceau_d_arete_pres_d_un_bout_garde_son_arete() -> None:
    """Un segment d'arête coupé par un assemblage reste rattaché à son arête (revue M2)."""
    from freecad.menuiserie.core.edges import nearest_edge

    long_piece = Dimensions(1000.0, 50.0, 20.0)
    assert nearest_edge(long_piece, Vec3(25.0, 0.0, 20.0)).code == "Z+Y-"
    assert nearest_edge(long_piece, Vec3(50.0, 0.0, 20.0)).code == "Z+Y-"
    assert nearest_edge(long_piece, Vec3(975.0, 50.0, 0.0)).code == "Z-Y+"
