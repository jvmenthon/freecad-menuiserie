# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaisons du bureau de référence et formules de l'utilisateur (J4a, critères F8, F9 ;
ADR 0019, critères E1, E8)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    Edge,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Linear,
    Member,
    NoticeKind,
    bindings_for,
    bound_by_workshop,
    driven_properties,
    expression_text,
    follow_rules,
    is_driven,
    label_reference,
    piece_reference,
    same_binding,
)
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.templates.carcass import CarcassParams
from tests.unit.aides_ensembles import BOX, FREE_BACK, desk, with_options
from tests.unit.test_gabarit_caisson import carcass_members

DESK = {
    ("P", "Length"): "<<Bureau>>.Width",
    ("P", "Width"): "<<Bureau>>.Depth",
    ("P", "Placement.Base.z"): "<<Bureau>>.Origin.z + <<Bureau>>.Height - Thickness",
    ("JG", "Length"): "<<Bureau>>.Height - P.Thickness",
    ("JG", "Width"): "<<Bureau>>.Depth - 40 mm",
    ("JG", "Placement.Base.x"): "<<Bureau>>.Origin.x + Thickness",
    ("JD", "Length"): "<<Bureau>>.Height - P.Thickness",
    ("JD", "Width"): "<<Bureau>>.Depth - 40 mm",
    ("JD", "Placement.Base.x"): "<<Bureau>>.Origin.x + <<Bureau>>.Width",
    ("V", "Length"): "<<Bureau>>.Width - JD.Thickness - JG.Thickness",
    ("V", "Placement.Base.x"): "<<Bureau>>.Origin.x + JG.Thickness",
    ("V", "Width"): "<<Bureau>>.Height - P.Thickness - 320 mm",
    ("V", "Placement.Base.y"): "<<Bureau>>.Origin.y + <<Bureau>>.Depth - 141 mm",
}


def bindings(
    members: list[Member], label: str = "Bureau", *, nested: bool = False
) -> dict[tuple[str, str], str]:
    rules, _ = follow_rules(BOX, members)
    found, _ = bindings_for(label, members, rules, nested=nested)
    result = {(b.key, b.prop): b.expression for b in found}
    assert len(result) == len(found), "une seule liaison par propriété"
    return result


# --- F8 : expressions exactes -------------------------------------------------------------


def test_bureau_options_par_defaut() -> None:
    """E1 : les expressions exactes du bureau, épaisseurs vivantes comprises."""
    assert bindings(with_options(desk())) == DESK


def test_bureau_arriere_des_joues_decoche() -> None:
    expected = {k: v for k, v in DESK.items() if k not in {("JG", "Width"), ("JD", "Width")}}
    assert bindings(with_options(desk(), FREE_BACK)) == expected


def test_voile_en_proportion() -> None:
    members = with_options(desk(V=InteriorMode.PROPORTIONAL), {"V": frozenset({Edge.BACK})})
    found = bindings(members)
    assert found[("V", "Placement.Base.y")] == (
        "<<Bureau>>.Origin.y + <<Bureau>>.Depth * 0.757731959 + Thickness * 0.242268041"
    )  # les deux écarts gardent leur proportion (441 / 582)
    assert found[("V", "Width")] == DESK[("V", "Width")]  # le bas reste fixe
    assert ("V", "Placement.Base.z") not in found


def test_voile_en_mode_stay_ne_depend_pas_de_la_profondeur() -> None:
    """E5 : aucune liaison de cote ; son origine (face arrière) suit seulement son épaisseur."""
    found = bindings(with_options(desk(), {"V": frozenset({Edge.BACK})}))
    assert found[("V", "Placement.Base.y")] == "<<Bureau>>.Origin.y + Thickness + 441 mm"
    assert ("V", "Width") in found  # la hauteur suit toujours
    assert not any("Depth" in text for (key, prop), text in found.items() if key == "V")


def test_ensemble_imbrique_lie_toutes_les_positions() -> None:
    found = bindings(with_options(desk()), nested=True)
    assert found[("P", "Placement.Base.x")] == "<<Bureau>>.Origin.x"
    assert found[("JG", "Placement.Base.x")] == DESK[("JG", "Placement.Base.x")]
    assert found[("V", "Placement.Base.z")] == "<<Bureau>>.Origin.z + 320 mm"
    assert found[("JD", "Placement.Base.x")] == DESK[("JD", "Placement.Base.x")]
    assert len(found) == len(DESK) + 12 - 5  # douze positions, dont cinq déjà liées


@pytest.mark.parametrize(
    ("linear", "expected"),
    [
        (Linear(1.0, 0.0), "<<B>>.Depth"),
        (Linear(1.0, -40.0), "<<B>>.Depth - 40 mm"),
        (Linear(0.5, 12.25), "<<B>>.Depth * 0.5 + 12.25 mm"),
        (Linear(1 / 3, 1e-7), "<<B>>.Depth * 0.333333333"),
        (Linear(1.0000000001, -1e-7), "<<B>>.Depth"),
        (Linear(2.0, 0.1234567), "<<B>>.Depth * 2 + 0.123457 mm"),
        (Linear(0.0, -3.0), "-3 mm"),
    ],
)
def test_format_des_nombres(linear: Linear, expected: str) -> None:
    assert expression_text("<<B>>", FurnitureAxis.DEPTH, linear) == expected


@pytest.mark.parametrize(
    ("linear", "expected"),
    [
        (Linear(0.0, 0.0), "<<B>>.Origin.y"),
        (Linear(0.0, 22.0), "<<B>>.Origin.y + 22 mm"),
        (Linear(0.75, 9.0), "<<B>>.Origin.y + <<B>>.Depth * 0.75 + 9 mm"),
        (Linear(1.0, -141.0), "<<B>>.Origin.y + <<B>>.Depth - 141 mm"),
    ],
)
def test_position_relative_a_l_origine(linear: Linear, expected: str) -> None:
    assert expression_text("<<B>>", FurnitureAxis.DEPTH, linear, from_origin=True) == expected


PIECES = {"A": "<<Joue gauche>>", "B": "WoodPart001"}


@pytest.mark.parametrize(
    ("linear", "expected"),
    [
        (
            Linear.of(1.0, -44.0, {"A": -1.0, "B": -1.0}),
            "<<B>>.Width - <<Joue gauche>>.Thickness - WoodPart001.Thickness - 44 mm",
        ),
        (Linear.of(0.0, 0.0, {"A": 1.0}), "<<Joue gauche>>.Thickness"),
        (Linear.of(0.0, 3.0, {"B": -1.0}), "-WoodPart001.Thickness + 3 mm"),
        (
            Linear.of(0.5, 0.0, {"A": 0.25, "B": -0.125}),
            "<<B>>.Width * 0.5 + <<Joue gauche>>.Thickness * 0.25 - WoodPart001.Thickness * 0.125",
        ),
        (Linear(1.0, 0.0, (("A", 1e-10),)), "<<B>>.Width"),  # coefficient négligeable
        (Linear(0.0, 0.0, (("Z", 1.0),)), "Z.Thickness"),  # clé sans référence : la clé
    ],
)
def test_epaisseurs_citees(linear: Linear, expected: str) -> None:
    """Termes d'épaisseur : triés par clé, coefficient 1 omis, pièce citée par son libellé ou, si
    il est inutilisable, par son Name."""
    assert expression_text("<<B>>", FurnitureAxis.WIDTH, linear, PIECES) == expected


def test_epaisseur_en_position() -> None:
    linear = Linear.of(0.0, 0.0, {"A": 1.0})
    text = expression_text("<<B>>", FurnitureAxis.WIDTH, linear, PIECES, from_origin=True)
    assert text == "<<B>>.Origin.x + <<Joue gauche>>.Thickness"


def test_epaisseur_de_la_piece_elle_meme_s_ecrit_thickness() -> None:
    """FreeCAD réécrit ``<<Joue gauche>>.Thickness`` posé sur la joue en ``Thickness`` : même
    texte, pour que la liaison enregistrée soit celle qu'on relit."""
    linear = Linear.of(0.0, 0.0, {"A": 1.0, "B": 0.5})
    text = expression_text("<<B>>", FurnitureAxis.WIDTH, linear, PIECES, own="A")
    assert text == "Thickness + WoodPart001.Thickness * 0.5"


def test_piece_citee_par_son_name() -> None:
    """Toujours le ``Name`` (la clé), même pour un libellé inutilisable dans ``<<…>>`` : une
    copie du document réécrit les ``Name``, pas les libellés que l'atelier renomme."""
    members = [
        replace(m, label="Joue > gauche") if m.key == "JG" else m for m in with_options(desk())
    ]
    assert piece_reference(members[1]) == "JG"
    assert piece_reference(members[0]) == "P"
    found = bindings(members)
    assert found[("JG", "Placement.Base.x")] == "<<Bureau>>.Origin.x + Thickness"
    assert found[("V", "Length")].endswith(" - JG.Thickness")


@pytest.mark.parametrize("label", ["", "a>>b", "Bureau <bis>", "a\nb", "Bur\\'eau", "a\\", None])
def test_libelle_refuse(label: object) -> None:
    with pytest.raises(FurnitureError, match="Libellé d'ensemble"):
        label_reference(label)  # type: ignore[arg-type]


def test_libelle_accepte() -> None:
    assert label_reference("Bureau (bis) <") == "<<Bureau (bis) <>>"
    assert bindings(with_options(desk()), label="Mon bureau")[("P", "Length")] == (
        "<<Mon bureau>>.Width"
    )


def test_sous_ensemble_lie_par_origin_et_cotes() -> None:
    caisson = Member(
        "C",
        box=FurnitureBox(600, 520, 720),
        origin=Vec3(22, 0, 0),
        fixed=frozenset({Edge.FRONT, Edge.BACK}),
        mode=InteriorMode.PROPORTIONAL,
        label="Caisson",
    )
    found = bindings([caisson])
    assert found[("C", "Depth")] == "<<Bureau>>.Depth - 80 mm"
    assert found[("C", "Width")] == "<<Bureau>>.Width * 0.5"
    assert found[("C", "Origin.x")] == "<<Bureau>>.Origin.x + <<Bureau>>.Width * 0.018333333"
    assert found[("C", "Height")] == "<<Bureau>>.Height * 0.96"
    assert ("C", "Origin.y") not in found


# --- F9 : formules de l'utilisateur -------------------------------------------------------


def test_formule_de_l_utilisateur_jamais_remplacee() -> None:
    members = with_options(desk())
    members = [
        replace(m, driven=frozenset({"Width", "Placement.Base.y", "Thickness"}))
        if m.key == "JG"
        else m
        for m in members
    ]
    rules, _ = follow_rules(BOX, members)
    found, notices = bindings_for("Bureau", members, rules)
    assert ("JG", "Width") not in {(b.key, b.prop) for b in found}
    assert [(n.kind, n.params["member"], n.params["property"]) for n in notices] == [
        (NoticeKind.USER_FORMULA, "Joue gauche", "Placement.Base.y"),
        (NoticeKind.USER_FORMULA, "Joue gauche", "Width"),
    ]
    assert "Joue gauche" in notices[1].message


def test_placement_pilote_bloque_ses_sous_chemins() -> None:
    members = [
        replace(m, driven=frozenset({"Placement"})) if m.key == "JD" else m
        for m in with_options(desk())
    ]
    assert ("JD", "Placement.Base.x") not in bindings(members)
    assert is_driven(members[2], "Placement.Base.x")
    assert not is_driven(members[2], "PlacementBis")


def test_liaison_reecrite_traitee_comme_formule() -> None:
    recorded = {"Width": "<<Bureau>>.Depth - 40 mm", "Length": "<<Bureau>>.Height - 30 mm"}
    current = {
        "Width": "<<Bureau>>.Depth - 40 mm",
        "Length": "<<Bureau>>.Height - 31 mm",
        "Placement.Base.y": "<<Bureau>>.Depth - 141 mm",
    }
    assert driven_properties(current, recorded) == {"Length", "Placement.Base.y"}
    # Liaison effacée par l'utilisateur : non pilotée, « Relier » la remet.
    assert driven_properties({}, recorded) == frozenset()


def test_avertissement_seulement_pour_les_proprietes_liees() -> None:
    caisson = Member(
        "C",
        box=FurnitureBox(600, 520, 720),
        origin=Vec3(0, 0, 0),
        fixed=frozenset(),
        driven=frozenset({"Depth", "Origin.y", "Label", "Thickness"}),
    )
    _, notices = bindings_for("Bureau", [caisson], {})
    assert [n.params["property"] for n in notices] == ["Depth", "Origin.y"]
    assert bound_by_workshop(caisson, "Height")
    assert not bound_by_workshop(caisson, "Length")


@pytest.mark.parametrize(
    "current",
    [
        "<<Bureau>>.Depth - 40 mm",
        "<<Nouveau>>.Depth - 40 mm",  # ensemble renommé : FreeCAD réécrit la référence
        "<<Bureau d\\'angle>>.Depth - 40 mm",  # apostrophe échappée par FreeCAD
        '<<Meuble \\"TV\\">>.Depth - 40 mm',  # guillemets échappés
        "<<Bureau001>>.Depth - 40 mm",  # copie du document
    ],
)
def test_liaison_reconnue_au_libelle_pres(current: str) -> None:
    recorded = {"Width": "<<Bureau>>.Depth - 40 mm"}
    assert same_binding(current, recorded["Width"])
    assert driven_properties({"Width": current}, recorded) == frozenset()


def test_liaison_reconnue_aux_pieces_copiees_pres() -> None:
    """Une copie du document réécrit ``WoodPart001.Thickness`` vers la pièce copiée."""
    recorded = "<<Bureau>>.Width - WoodPart001.Thickness - WoodPart002.Thickness"
    assert same_binding(
        "<<Bureau001>>.Width - WoodPart005.Thickness - WoodPart006.Thickness", recorded
    )
    assert not same_binding("<<Bureau>>.Width - WoodPart001.Thickness", recorded)
    assert not same_binding("<<Bureau>>.Width - Thickness - WoodPart002.Thickness", recorded)


@pytest.mark.parametrize(
    ("current", "recorded"),
    [
        ("<<Bureau>>.Depth - 41 mm", "<<Bureau>>.Depth - 40 mm"),
        ("<<Bureau>>.Width - 40 mm", "<<Bureau>>.Depth - 40 mm"),
        ("Depth - 40 mm", "<<Bureau>>.Depth - 40 mm"),
        ("<<Bureau>>.Depth - 40 mm", None),
    ],
)
def test_formule_differente_pilotee(current: str, recorded: str | None) -> None:
    assert not same_binding(current, recorded)


# --- ADR 0019 : écarts entre pièces et cycles -------------------------------------------------


def test_sous_ensemble_entre_les_joues_garde_ses_ecarts() -> None:
    """Seules les pièces changent de cote : les écarts entre la joue et le caisson sont rigides,
    le caisson absorbe toute la différence (aucune part du jeu)."""
    members = with_options(desk())[:3]
    caisson = Member(
        "C",
        box=FurnitureBox(400, 560, 300),
        origin=Vec3(40, 0, 400),
        label="Caisson",
        fixed=frozenset(Edge),
    )
    found = bindings([*members, caisson])
    assert found[("C", "Width")] == ("<<Bureau>>.Width - JD.Thickness - JG.Thickness - 756 mm")
    assert found[("C", "Origin.x")] == "<<Bureau>>.Origin.x + JG.Thickness + 18 mm"
    assert found[("C", "Height")] == "<<Bureau>>.Height - P.Thickness - 420 mm"


def carcass_bindings(box: FurnitureBox, members: list[Member]) -> dict[tuple[str, str], str]:
    rules, _ = follow_rules(box, members)
    found, _ = bindings_for("Caisson", members, rules)
    return {(b.key, b.prop): b.expression for b in found}


def test_etagere_seule_entre_deux_montants_partage_les_ecarts() -> None:
    """Aucune pièce libre dans sa rangée verticale (épaisseurs seules) : les jeux au-dessus et
    au-dessous de l'étagère se partagent au prorata."""
    layout, members = carcass_members()
    found = carcass_bindings(layout.box, members)
    assert found[("shelf1", "Placement.Base.z")] == (
        "<<Caisson>>.Origin.z + <<Caisson>>.Height * 0.5 + bottom.Thickness * 0.5"
        " - Thickness * 0.5 - top.Thickness * 0.5"
    )


def test_deux_etageres_ne_se_citent_pas_l_une_l_autre() -> None:
    """Chaque étagère cite l'épaisseur de l'autre : le graphe de FreeCAD serait cyclique. La
    seconde, dans l'ordre des clés, fige l'épaisseur de la première (18 mm x 1/3 = 6 mm)."""
    layout, members = carcass_members(CarcassParams(shelf_count=2))
    found = carcass_bindings(layout.box, members)
    first, second = found[("shelf1", "Placement.Base.z")], found[("shelf2", "Placement.Base.z")]
    assert "shelf2.Thickness" in first
    assert "<<shelf1>>" not in second
    assert second.endswith(" + 6 mm")


def test_relier_un_seul_membre_donne_les_memes_liaisons() -> None:
    """Le cycle est coupé sur tous les membres puis filtré par ``keys``."""
    layout, members = carcass_members(CarcassParams(shelf_count=2))
    rules, _ = follow_rules(layout.box, members)
    everything, _ = bindings_for("Caisson", members, rules)
    only, _ = bindings_for("Caisson", members, rules, keys={"shelf2"})
    assert only == tuple(b for b in everything if b.key == "shelf2")


def test_epaisseur_figee_en_constante() -> None:
    linear = Linear.of(1.0, 5.0, {"A": 2.0, "B": 0.5})
    frozen = linear.frozen({"A": 18.0})
    assert frozen == Linear.of(1.0, 41.0, {"B": 0.5})
    assert frozen.frozen({}) == frozen
    assert Linear.of(0.0, 0.0, {"A": 1.0}).frozen({"A": 18.0}).constant
