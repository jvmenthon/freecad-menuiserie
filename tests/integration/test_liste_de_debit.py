# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture du document par la liste de débit (J2c, critères D1 à D8 de ``docs/specs/J2``).

Pièces, pièces usinées, sélection, liens (``App::Link``, ``ElementCount``), Std Part, ensembles,
ajouts des assemblages (tenon-mortaise, rainure-languette, queue d'aronde), tourillons, pièces
en erreur ou d'une version plus récente.
"""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.core.cutlist import HardwareKind
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.part_model import Allowances
from tests.integration.aides import touched_names
from tests.integration.bureau import LAYOUT, Bureau
from tests.integration.cadre import Cadre, placement
from tests.integration.debit import (
    has_mark_in,
    kinds,
    line_of,
    link,
    marks_of,
    part,
    quantities,
)
from tests.integration.types_assemblages import DOWELS, SCENARIOS, build

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
joints_base = pytest.importorskip("freecad.menuiserie.features.joints.base")
schema = pytest.importorskip("freecad.menuiserie.features.wood_part_schema")

DESK_MARKS = {label for label, *_ in LAYOUT.values()}
# Ajouts attendus de l'invitée (somme des trois axes, mm) pour chaque montage de J3/J4 :
# languette de 10 mm, queues de 18 mm ; les autres assemblages ne font que retirer de la matière.
GUEST_ADDITIONS = {"rainure-languette": 10.0, "queue d'aronde": 18.0}


def total_additions(additions: Allowances) -> float:
    """Somme des ajouts sur les trois axes (mm)."""
    return additions.length + additions.width + additions.thickness


def dowel_total(bureau: Bureau) -> int:
    """Nombre de tourillons effectifs des assemblages du bureau."""
    return sum(joints_base.resolved_for(joint).count for joint in bureau.joints)


# --- D1 : une entrée par pièce brute --------------------------------------------------------


def test_une_ligne_par_piece_et_objets_d_autres_ateliers_ignores(document: Any) -> None:
    part(document, "M1")
    part(document, "M2", (600, 100, 18))
    document.addObject("Part::Box", "Bloc")
    document.addObject("Spreadsheet::Sheet", "Feuille")
    document.recompute()
    cut_list = api.cut_list_of(document)
    assert quantities(cut_list) == {"M1": 1, "M2": 1}
    assert cut_list.warnings == ()
    assert line_of(cut_list, "M2").finished.thickness == 18


def test_pieces_identiques_regroupees_et_ordre_naturel(document: Any) -> None:
    for mark in ("M10", "M2", "M2"):
        part(document, mark)
    cut_list = api.cut_list_of(document)
    assert [(line.marks, line.quantity) for line in cut_list.lines] == [
        (("M2",), 2),
        (("M10",), 1),
    ]


def test_piece_usinee_comptee_par_sa_brute(cadre_assemble: Cadre) -> None:
    doc = cadre_assemble.doc
    machined = [o for o in doc.Objects if api.is_machined_part(o)]
    assert len(machined) == 4
    cut_list = api.cut_list_of(doc)
    # C1' : M1 et M2 (hôtes), T1 et T2 (invitées) ont les mêmes cotes, ajouts et surcotes.
    assert quantities(cut_list) == {"M1, M2": 2, "T1, T2": 2}


def test_liste_en_lecture_seule(cadre_assemble: Cadre) -> None:
    doc = cadre_assemble.doc
    names = [o.Name for o in doc.Objects]
    states = {o.Name: list(o.State) for o in doc.Objects}
    api.cut_list_of(doc)
    api.cut_list_of(doc, [cadre_assemble.parts["T1"]])
    assert [o.Name for o in doc.Objects] == names
    assert {o.Name: list(o.State) for o in doc.Objects} == states
    assert touched_names(doc) == []


# --- D2 : sélection -------------------------------------------------------------------------


def test_selection_piece_et_piece_usinee_sans_doublon(cadre_assemble: Cadre) -> None:
    doc, parts = cadre_assemble.doc, cadre_assemble.parts
    assert quantities(api.cut_list_of(doc, [cadre_assemble.machined("M1")])) == {"M1": 1}
    both = [parts["M1"], cadre_assemble.machined("M1"), parts["M1"]]
    assert quantities(api.cut_list_of(doc, both)) == {"M1": 1}
    assert quantities(api.cut_list_of(doc, [parts["T1"], parts["M2"]])) == {"T1": 1, "M2": 1}


def test_selection_std_part_et_groupe_recursifs_sans_doublon(document: Any) -> None:
    meuble = document.addObject("App::Part", "Meuble")
    group = document.addObject("App::DocumentObjectGroup", "Groupe")
    first, second, third = (part(document, mark) for mark in ("A", "B", "C"))
    outside = part(document, "Z")
    meuble.addObject(first)
    meuble.addObject(second)
    group.addObject(meuble)
    group.addObject(third)
    document.recompute()
    assert quantities(api.cut_list_of(document, [group])) == {"A": 1, "B": 1, "C": 1}
    assert quantities(api.cut_list_of(document, [meuble])) == {"A": 1, "B": 1}
    twice = api.cut_list_of(document, [group, meuble, first, group])
    assert quantities(twice) == {"A": 1, "B": 1, "C": 1}
    everything = quantities(api.cut_list_of(document))
    assert everything == {"A": 1, "B": 1, "C": 1, outside.Mark: 1}
    assert quantities(api.cut_list_of(document, [])) == everything


def test_selection_d_un_autre_document_refusee(document: Any) -> None:
    other = App.newDocument("AutreDebit")
    try:
        stranger = part(other, "E")
        with pytest.raises(ValueError, match="autre document"):
            api.cut_list_of(document, [stranger])
        with pytest.raises(ValueError, match="autre document"):
            api.make_cut_list(document, [stranger])
        assert api.cut_list_of(other).lines[0].marks == ("E",)
    finally:
        App.closeDocument(other.Name)


# --- D3 : liens -----------------------------------------------------------------------------


def test_chaque_lien_ajoute_une_occurrence_et_l_original_compte(document: Any) -> None:
    board = part(document, "M1")
    link(document, board)
    link(document, board, name="Lien001")
    assert quantities(api.cut_list_of(document)) == {"M1": 3}
    only_link = document.getObject("Lien")
    assert quantities(api.cut_list_of(document, [only_link])) == {"M1": 1}


def test_tableau_de_liens_fois_element_count(document: Any) -> None:
    board = part(document, "M1")
    link(document, board, count=4, name="Reseau")
    assert quantities(api.cut_list_of(document)) == {"M1": 5}


def test_lien_vers_un_lien_suivi(document: Any) -> None:
    board = part(document, "M1")
    inner = link(document, board, count=3, name="Interne")
    link(document, inner, count=2, name="Externe")
    assert quantities(api.cut_list_of(document, [document.getObject("Externe")])) == {"M1": 6}
    assert quantities(api.cut_list_of(document)) == {"M1": 1 + 3 + 6}


def test_lien_vers_une_piece_usinee_garde_ses_ajouts(cadre: Cadre) -> None:
    api.make_mortise_tenon(cadre.parts["M1"], cadre.parts["T1"], tenon_length=30)
    copy = link(cadre.doc, cadre.machined("T1"), name="Copie")
    cut_list = api.cut_list_of(cadre.doc, [copy])
    assert quantities(cut_list) == {"T1": 1}
    assert line_of(cut_list, "T1").additions.length == pytest.approx(30)
    assert quantities(api.cut_list_of(cadre.doc))["T1"] == 2


def test_lien_vers_un_std_part(document: Any) -> None:
    meuble = document.addObject("App::Part", "Meuble")
    for mark in ("A", "B"):
        meuble.addObject(part(document, mark))
    copy = link(document, meuble, name="Copie")
    assert quantities(api.cut_list_of(document, [copy])) == {"A": 1, "B": 1}
    assert quantities(api.cut_list_of(document)) == {"A": 2, "B": 2}


def test_lien_vers_un_ensemble_compte_aussi_les_tourillons(bureau: Bureau) -> None:
    doc = bureau.doc
    copy = link(doc, bureau.furniture, name="Copie")
    once = api.cut_list_of(doc, [bureau.furniture])
    twice = api.cut_list_of(doc)
    assert marks_of(once) == DESK_MARKS
    assert quantities(api.cut_list_of(doc, [copy])) == quantities(once)
    assert quantities(twice) == {mark: 2 * count for mark, count in quantities(once).items()}
    assert sum(item.quantity for item in once.hardware) == dowel_total(bureau)
    assert api.cut_list_of(doc, [copy]).hardware == once.hardware
    assert sum(item.quantity for item in twice.hardware) == 2 * dowel_total(bureau)


# --- D4 : ajouts des assemblages ------------------------------------------------------------


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_ajouts_selon_l_assemblage(document: Any, scenario: Any) -> None:
    build(document, scenario)
    cut_list = api.cut_list_of(document)
    host, guest = line_of(cut_list, "H"), line_of(cut_list, "I")
    assert host.additions == Allowances()  # une mortaise, une rainure, une entaille : retraits
    assert total_additions(guest.additions) == pytest.approx(
        GUEST_ADDITIONS.get(scenario.name, 0.0)
    )
    for line in (host, guest):
        for axis in ("length", "width", "thickness"):
            expected = (
                getattr(line.finished, axis)
                + getattr(line.additions, axis)
                + getattr(line.allowances, axis)
            )
            assert getattr(line.rough, axis) == pytest.approx(expected), (line.marks, axis)


def test_tenons_inclus_dans_la_longueur_de_debit(cadre: Cadre) -> None:
    for host in ("M1", "M2"):
        api.make_mortise_tenon(cadre.parts[host], cadre.parts["T1"], tenon_length=30)
    cut_list = api.cut_list_of(cadre.doc)
    rail, bare = line_of(cut_list, "T1"), line_of(cut_list, "T2")
    assert rail.additions == Allowances(60.0, 0.0, 0.0)
    assert rail.rough.length == pytest.approx(280 + 60 + rail.allowances.length)
    assert bare.additions == Allowances()
    assert bare.rough.length == pytest.approx(280 + bare.allowances.length)
    assert line_of(cut_list, "M1").additions == Allowances()  # mortaises : retraits
    assert rail.finished.length == 280  # les cotes finies ne changent pas


# --- D5 : tourillons ------------------------------------------------------------------------


def test_tourillons_effectifs_automatiques(document: Any) -> None:
    montage = build(document, DOWELS)
    values = joints_base.resolved_for(montage.joint)
    [item] = api.cut_list_of(document).hardware
    assert item.kind is HardwareKind.DOWEL
    assert (item.diameter, item.length, item.quantity) == (10.0, 40.0, 2)  # Ø 10 x 40, deux
    assert (item.diameter, item.length, item.quantity) == (
        values.diameter,
        values.dowel_length,
        values.count,
    )


def test_tourillons_de_diametre_choisi(document: Any) -> None:
    montage = build(document, DOWELS, diameter=8)
    values = joints_base.resolved_for(montage.joint)
    [item] = api.cut_list_of(document).hardware
    assert (item.diameter, item.length) == (8.0, 35.0)  # longueur automatique du commerce
    assert item.quantity == values.count


def test_tourillons_seulement_si_les_deux_pieces_sont_dans_la_portee(document: Any) -> None:
    montage = build(document, DOWELS)
    assert api.cut_list_of(document, [montage.host]).hardware == ()
    assert len(api.cut_list_of(document, [montage.host, montage.guest]).hardware) == 1


def test_tourillons_regroupes_par_diametre_et_longueur(bureau: Bureau) -> None:
    hardware = api.cut_list_of(bureau.doc).hardware
    assert len(bureau.joints) == 2
    assert len({(item.diameter, item.length) for item in hardware}) == len(hardware)
    assert sum(item.quantity for item in hardware) == dowel_total(bureau)


# --- D6 : ensembles -------------------------------------------------------------------------


def test_colonne_ensemble_et_selection_d_un_ensemble(bureau: Bureau) -> None:
    extra = part(bureau.doc, "Hors ensemble")
    whole = api.cut_list_of(bureau.doc)
    assert marks_of(whole) == DESK_MARKS | {"Hors ensemble"}
    assert line_of(whole, "Hors ensemble").furniture == ()
    assert {line.furniture for line in whole.lines if has_mark_in(line, DESK_MARKS)} == {
        ("Bureau",)
    }
    selected = api.cut_list_of(bureau.doc, [bureau.furniture])
    assert marks_of(selected) == DESK_MARKS
    assert extra.isValid()


def test_sous_ensemble_lu_avec_son_propre_libelle(bureau: Bureau) -> None:
    api.make_carcass(
        bureau.doc,
        width=400,
        depth=400,
        height=300,
        origin=Vec3(40, 0, 0),
        furniture=bureau.furniture,
    )
    cut_list = api.cut_list_of(bureau.doc, [bureau.furniture])
    carcass_lines = [line for line in cut_list.lines if not has_mark_in(line, DESK_MARKS)]
    assert sum(line.quantity for line in carcass_lines) == 6
    assert {line.furniture for line in carcass_lines} == {("Caisson",)}
    assert {line.furniture for line in cut_list.lines if has_mark_in(line, DESK_MARKS)} == {
        ("Bureau",)
    }


def test_ensembles_differents_meme_ligne(document: Any) -> None:
    """La clé de regroupement ignore l'ensemble (Q2) : une ligne, les deux ensembles cités."""
    first, second = part(document, "M1"), part(document, "M1")
    second.Placement = App.Placement(App.Vector(0, 500, 0), App.Rotation())
    api.make_furniture([first], "Armoire A")
    api.make_furniture([second], "Armoire B")
    [line] = api.cut_list_of(document).lines
    assert (line.marks, line.quantity, line.furniture) == (("M1",), 2, ("Armoire A", "Armoire B"))


def test_caisson_complet(document: Any) -> None:
    furniture, _ = api.make_carcass(document)
    cut_list = api.cut_list_of(document, [furniture])
    assert sum(line.quantity for line in cut_list.lines) == 6
    assert {line.furniture for line in cut_list.lines} == {("Caisson",)}
    dowel_joints = [o for o in document.Objects if o.Name.startswith("Dowels")]
    expected = sum(joints_base.resolved_for(joint).count for joint in dowel_joints)
    assert expected == 16
    assert sum(item.quantity for item in cut_list.hardware) == expected
    assert all(total.area_m2 is not None for total in cut_list.totals)  # contreplaqué : panneaux
    assert cut_list.total_mass_kg > 0


# --- D7 : pièces en erreur ------------------------------------------------------------------


def test_piece_en_erreur_n_interrompt_pas_la_liste(document: Any) -> None:
    broken, fine = part(document, "Cassée"), part(document, "Bonne")
    broken.Length = 0
    document.recompute()
    assert not broken.isValid()
    cut_list = api.cut_list_of(document)
    assert quantities(cut_list) == {"Bonne": 1}
    [notice] = cut_list.warnings
    assert notice.kind.value == "IgnoredPart"
    assert "Cassée" in notice.message
    assert fine.isValid()


def test_forme_usinee_invalide_ajouts_nuls_et_avertissement(cadre: Cadre) -> None:
    api.make_mortise_tenon(cadre.parts["M1"], cadre.parts["T1"], tenon_length=30)
    cadre.parts["T1"].Placement = placement(5000, 5000)  # l'assemblage ne tient plus
    cadre.doc.recompute()
    machined = cadre.machined("T1")
    assert "Invalid" in machined.State or "Touched" in machined.State
    cut_list = api.cut_list_of(cadre.doc)
    # T1 (ajouts nuls faute de forme valide) et T2 (sans assemblage) se regroupent.
    assert line_of(cut_list, "T1").marks == ("T1", "T2")
    assert line_of(cut_list, "T1").quantity == 2
    assert line_of(cut_list, "T1").additions == Allowances()
    assert "NoMachinedShape" in kinds(cut_list)


def test_tourillons_impossibles_signales(document: Any) -> None:
    montage = build(document, DOWELS)
    montage.guest.Placement = placement(5000, 5000)
    document.recompute()
    cut_list = api.cut_list_of(document)
    assert cut_list.hardware == ()
    assert "UnreadableDowels" in kinds(cut_list)
    assert marks_of(cut_list) == {"H", "I"}


# --- D8 : pièce d'un document plus récent ---------------------------------------------------


def test_categorie_inconnue_listee_avec_point_d_interrogation(document: Any, board: Any) -> None:
    future = board(document)
    future.Mark = "F1"
    future.Version = schema.MODEL_VERSION + 1
    future.Category = [*schema.CATEGORIES, "Future"]
    future.Category = "Future"
    fine = board(document)
    fine.Mark = "M1"
    cut_list = api.cut_list_of(document)
    assert quantities(cut_list) == {"F1": 1, "M1": 1}
    assert line_of(cut_list, "F1").material_name.startswith("? ")
    assert not line_of(cut_list, "M1").material_name.startswith("?")
    [notice] = cut_list.warnings
    assert notice.kind.value == "UnreadablePart"
    assert future.Label in notice.message


# --- lecture seule des bureau et caisson (D1 sur des ensembles réels) -----------------------


def test_bureau_lignes_et_cotes(bureau: Bureau) -> None:
    cut_list = api.cut_list_of(bureau.doc)
    # C1' : les deux joues (mêmes cotes) forment une ligne ; tri par premier repère.
    assert [line.marks for line in cut_list.lines] == [
        ("Joue droite", "Joue gauche"),
        ("Plateau",),
        ("Voile",),
    ]
    plateau = line_of(cut_list, "Plateau")
    assert (plateau.finished.length, plateau.finished.width, plateau.finished.thickness) == (
        1200,
        600,
        30,
    )
