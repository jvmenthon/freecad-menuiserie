# SPDX-License-Identifier: LGPL-2.1-or-later
"""Relecture de fin du jalon J2 : cas limites de la liste de débit non couverts ailleurs.

Document vide, sélection mixte, pièces « Touched », renumérotation répétée, suppression d'une
pièce de la portée, chemins d'export refusés, liens dégénérés.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.integration.aides import touched_names
from tests.integration.debit import column, link, part, quantities, row_of, sheets, text

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
cutlist_object = pytest.importorskip("freecad.menuiserie.features.cutlist_object")


def blank(doc: Any, length: float, y: float = 0.0) -> Any:
    """Pièce de chêne sans repère."""
    obj = api.make_wood_part(length, 100.0, 22.0, "chene", doc=doc)
    obj.Placement = App.Placement(App.Vector(0, y, 0), App.Rotation())
    doc.recompute()
    return obj


# --- Document vide --------------------------------------------------------------------------


def test_document_vide_liste_vide_sans_erreur(document: Any, tmp_path: Path) -> None:
    cut_list = api.cut_list_of(document)
    assert (cut_list.lines, cut_list.totals, cut_list.hardware) == ((), (), ())
    sheet = api.make_cut_list(document)
    assert text(sheet, "A3") == "Tout le document"
    assert touched_names(document) == []
    path = tmp_path / "vide.csv"
    api.export_cut_list_csv(document, path)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    document.recompute()  # la liste vivante d'un document vide recalcule sans erreur
    assert not [o.Name for o in document.Objects if "Invalid" in o.State]


def test_document_vide_numerotation_ne_fait_rien(document: Any) -> None:
    document.UndoMode = 1
    assert api.number_marks(document) == {}
    assert document.UndoCount == 0


def test_la_liste_d_un_document_vide_se_remplit_avec_la_premiere_piece(document: Any) -> None:
    sheet = api.make_cut_list(document)
    part(document, "M1")
    document.recompute()
    assert "M1" in column(sheet, "A")


# --- Sélection mixte ------------------------------------------------------------------------


def test_selection_mixte_piece_objet_etranger_et_groupe(document: Any) -> None:
    first, second = part(document, "M1"), part(document, "M2")
    box = document.addObject("Part::Box", "Boite")
    group = document.addObject("App::DocumentObjectGroup", "Groupe")
    group.addObject(second)
    document.recompute()
    cut_list = api.cut_list_of(document, [first, box, group])
    assert quantities(cut_list) == {"M1": 1, "M2": 1}
    assert api.cut_list_of(document, [box]).lines == ()


def test_selection_d_une_piece_et_de_son_lien_compte_les_deux(document: Any) -> None:
    original = part(document, "M1")
    reference = link(document, original)
    cut_list = api.cut_list_of(document, [original, reference])
    assert quantities(cut_list) == {"M1": 2}


def test_lien_dont_la_cible_est_supprimee_ne_leve_rien(document: Any) -> None:
    target = part(document, "M1")
    part(document, "M2")
    broken = link(document, target)
    broken.LinkedObject = None
    document.recompute()
    assert quantities(api.cut_list_of(document)) == {"M1": 1, "M2": 1}


def test_tableau_de_liens_vide(document: Any) -> None:
    target = part(document, "M1")
    link(document, target, count=1)
    assert quantities(api.cut_list_of(document)) == {"M1": 2}


# --- Pièces Touched -------------------------------------------------------------------------


def test_piece_touched_listee_d_apres_ses_proprietes(document: Any) -> None:
    obj = part(document, "M1", (800.0, 100.0, 22.0))
    obj.Length = 900  # non recalculée : « Touched »
    assert "Touched" in obj.State
    line = api.cut_list_of(document).lines[0]
    assert line.finished.length == 900
    assert "Touched" in obj.State  # la lecture n'a rien recalculé


# --- Suppression d'une pièce ----------------------------------------------------------------


def test_supprimer_une_piece_de_la_portee_choisie(document: Any) -> None:
    first, second = part(document, "M1"), part(document, "M2")
    sheet = api.make_cut_list(document, [first, second])
    document.removeObject(second.Name)
    document.recompute()
    assert "M2" not in column(sheet, "A")
    assert "M1" in column(sheet, "A")
    assert touched_names(document) == []
    assert not [o.Name for o in document.Objects if "Invalid" in o.State]


def test_supprimer_toutes_les_pieces_laisse_une_feuille_vide(document: Any) -> None:
    only = part(document, "M1")
    sheet = api.make_cut_list(document)
    document.removeObject(only.Name)
    document.recompute()
    assert "M1" not in column(sheet, "A")
    assert text(sheet, "A1") != ""  # titre toujours écrit


def test_annuler_puis_retablir_la_suppression_d_une_piece(document: Any) -> None:
    document.UndoMode = 1
    keep, drop = part(document, "M1"), part(document, "M2")
    sheet = api.make_cut_list(document)
    assert keep.Name and "M2" in column(sheet, "A")
    document.openTransaction("Suppression")
    document.removeObject(drop.Name)
    document.recompute()
    document.commitTransaction()
    assert "M2" not in column(sheet, "A")
    document.undo()
    document.recompute()
    assert "M2" in column(sheet, "A")
    document.redo()
    document.recompute()
    assert "M2" not in column(sheet, "A")


# --- Renumérotation -------------------------------------------------------------------------


def test_numeroter_deux_fois_ne_change_rien(document: Any) -> None:
    blank(document, 800)
    blank(document, 300, y=200)
    first = api.number_marks(document)
    document.UndoMode = 1
    count = document.UndoCount
    assert api.number_marks(document) == {}
    assert document.UndoCount == count
    assert sorted(first.values()) == ["M1", "M2"]


def test_nouvelle_piece_apres_numerotation_prend_le_numero_suivant(document: Any) -> None:
    blank(document, 800)
    api.number_marks(document)
    fresh = blank(document, 300, y=200)
    assert api.number_marks(document) == {fresh.Name: "M2"}


def test_numerotation_saute_les_reperes_hors_serie(document: Any) -> None:
    part(document, "M3")
    part(document, "m1")  # minuscule : n'est pas « M1 »
    part(document, "M1a")  # suffixe : n'est pas « M1 » non plus
    fresh = blank(document, 300)
    assert api.number_marks(document) == {fresh.Name: "M1"}


def test_numerotation_apres_suppression_reutilise_le_numero_libre(document: Any) -> None:
    first = blank(document, 800)
    api.number_marks(document)
    document.removeObject(first.Name)
    fresh = blank(document, 300, y=200)
    assert api.number_marks(document) == {fresh.Name: "M1"}


def test_numerotation_de_pieces_touched(document: Any) -> None:
    obj = blank(document, 800)
    obj.Length = 900
    assert api.number_marks(document) == {obj.Name: "M1"}
    assert touched_names(document) == []


def test_numerotation_et_liste_vivante_regroupent_les_reperes(document: Any) -> None:
    blank(document, 800)
    blank(document, 800, y=200)
    sheet = api.make_cut_list(document)
    api.number_marks(document)
    row = row_of(sheet, "M1")
    assert text(sheet, f"B{row}") == "2"


# --- Chemins d'export refusés ---------------------------------------------------------------


def test_export_csv_extension_en_majuscules_acceptee(document: Any, tmp_path: Path) -> None:
    part(document, "M1")
    path = tmp_path / "DEBIT.CSV"
    assert Path(api.export_cut_list_csv(document, path)) == path
    assert path.exists()


def test_export_csv_vers_un_fichier_existant_non_inscriptible(
    document: Any, tmp_path: Path
) -> None:
    if os.geteuid() == 0:
        pytest.skip("droits POSIX, hors root")
    part(document, "M1")
    path = tmp_path / "debit.csv"
    path.write_text("ancien", encoding="utf-8")
    path.chmod(0o444)
    with pytest.raises(ValueError, match="accessible en écriture"):
        api.export_cut_list_csv(document, path)
    assert path.read_text(encoding="utf-8") == "ancien"


def test_export_csv_ne_laisse_aucun_temporaire_apres_succes(document: Any, tmp_path: Path) -> None:
    part(document, "M1")
    api.export_cut_list_csv(document, tmp_path / "debit.csv")
    api.export_cut_list_csv(document, tmp_path / "debit.csv")
    assert sorted(set(os.listdir(tmp_path)) - {"bibliotheque"}) == ["debit.csv"]


def test_export_csv_chemin_vide_refuse(document: Any) -> None:
    part(document, "M1")
    with pytest.raises(ValueError):
        api.export_cut_list_csv(document, "")


def test_export_pdf_selection_d_un_autre_document_refusee(document: Any, tmp_path: Path) -> None:
    other = App.newDocument("Autre")
    try:
        foreign = part(other, "M1")
        with pytest.raises(ValueError):
            api.export_cut_list_csv(document, tmp_path / "x.csv", [foreign])
        assert not (tmp_path / "x.csv").exists()
    finally:
        App.closeDocument(other.Name)


# --- Suppression de l'objet dans une liste vivante ------------------------------------------


def test_deux_appels_gardent_un_seul_objet_et_une_seule_feuille(document: Any) -> None:
    part(document, "M1")
    api.make_cut_list(document)
    api.make_cut_list(document)
    objects = [o for o in document.Objects if cutlist_object.is_cut_list(o)]
    assert len(objects) == 1
    assert len(sheets(document)) == 1
