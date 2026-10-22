# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit vivante (J2f, ADR 0013, critères V1 à V4 de ``docs/specs/J2`` § 10).

L'objet ``Menuiserie::CutList`` réécrit sa feuille à chaque recalcul : cote modifiée, pièce
ajoutée ou supprimée, tenon changé, ensemble redimensionné ; Annuler restaure feuille et pièces ;
aucun cycle ; document ouvert sans l'atelier ; suppression de l'objet ou de la feuille.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.integration.aides import touched_names
from tests.integration.bureau import Bureau, build_desk
from tests.integration.cadre import Cadre
from tests.integration.debit import SHEET_NAME, column, link, part, row_of, sheets, text

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
cutlist_object = pytest.importorskip("freecad.menuiserie.features.cutlist_object")

Reopen = Callable[[Any], Any]


def cut_list_object(doc: Any) -> Any:
    """Objet ``CutList`` du document."""
    found = cutlist_object.find_cut_list(doc)
    assert found is not None
    return found


def length_of(sheet: Any, mark: str) -> float:
    """Longueur finie (colonne C) de la ligne du repère ``mark``."""
    return float(text(sheet, f"C{row_of(sheet, mark)}"))


def in_error(doc: Any) -> list[str]:
    """Objets invalides du document."""
    return [obj.Name for obj in doc.Objects if "Invalid" in obj.State or not obj.isValid()]


# --- L'objet créé par make_cut_list ----------------------------------------------------------


def test_make_cut_list_cree_l_objet_et_le_reutilise(document: Any) -> None:
    part(document, "M1")
    sheet = api.make_cut_list(document)
    obj = cut_list_object(document)
    assert (obj.TypeId, obj.Name, obj.Proxy.TYPE) == (
        "App::FeaturePython",
        "CutList",
        "Menuiserie::CutList",
    )
    assert obj.Label == "Mise à jour de la liste de débit"
    assert (obj.Sheet, list(obj.Scope), obj.Version) == (sheet, [], 1)
    assert obj.getTypeIdOfProperty("Sheet") == "App::PropertyLink"
    assert obj.getTypeIdOfProperty("Scope") == "App::PropertyLinkListHidden"
    assert obj.getTypeIdOfProperty("Sources") == "App::PropertyLinkList"
    assert {o.Label for o in obj.Sources} == {"M1"}
    assert "Hidden" in obj.getEditorMode("Sources")
    assert api.make_cut_list(document) == sheet
    assert [o for o in document.Objects if o.TypeId == "App::FeaturePython"] == [obj]
    assert "Proxy" not in sheet.PropertiesList  # la feuille reste ordinaire
    assert touched_names(document) == []


def test_portee_choisie_gardee_par_l_objet(document: Any) -> None:
    first = part(document, "M1")
    part(document, "M2")
    sheet = api.make_cut_list(document, [first])
    obj = cut_list_object(document)
    assert list(obj.Scope) == [first]
    assert {o.Label for o in obj.Sources} == {"M1"}
    assert text(sheet, "A3") == "Sélection : 1 objet"
    api.make_cut_list(document)
    assert list(obj.Scope) == []
    assert text(sheet, "A3") == "Tout le document"
    assert {o.Label for o in obj.Sources} == {"M1", "M2"}


# --- V1 : la liste se met à jour toute seule ---------------------------------------------------


def test_cote_modifiee_puis_recalcul_sans_relancer_la_commande(document: Any) -> None:
    board = part(document, "M1")
    sheet = api.make_cut_list(document)
    assert length_of(sheet, "M1") == board.Length.Value
    board.Length = 1234
    document.recompute()
    assert length_of(sheet, "M1") == 1234
    assert "mise à jour automatiquement" in text(sheet, "A2")
    assert touched_names(document) == []
    assert in_error(document) == []


def test_piece_ajoutee_puis_supprimee(document: Any) -> None:
    first = part(document, "M1")
    sheet = api.make_cut_list(document)
    second = part(document, "M2")  # make_wood_part recalcule le document
    assert {"M1", "M2"} <= set(column(sheet))
    assert {o.Name for o in cut_list_object(document).Sources} == {first.Name, second.Name}
    document.removeObject(second.Name)
    document.recompute()
    assert "M2" not in column(sheet)
    assert "M1" in column(sheet)
    assert touched_names(document) == []


def test_objet_d_un_autre_atelier_ne_declenche_aucune_reecriture(document: Any) -> None:
    """Seuls les objets que la collecte lirait comptent : ``mustExecute`` reste faux sinon."""
    part(document, "M1")
    sheet = api.make_cut_list(document)
    document.addObject("Part::Box", "Boite")
    document.recompute()
    stamp = text(sheet, "A2")
    assert document.recompute() == 0
    assert text(sheet, "A2") == stamp
    assert column(sheet).count("M1") == 1


def test_portee_choisie_ignore_les_autres_pieces_mais_suit_les_siennes(document: Any) -> None:
    first = part(document, "M1")
    sheet = api.make_cut_list(document, [first])
    part(document, "M2")
    assert "M2" not in column(sheet)
    first.Length = 777
    document.recompute()
    assert length_of(sheet, "M1") == 777
    assert text(sheet, "A3") == "Sélection : 1 objet"
    assert "M2" not in column(sheet)


def test_tenon_modifie_suit_dans_la_longueur_de_debit(cadre: Cadre) -> None:
    cadre.assemble()
    sheet = api.make_cut_list(cadre.doc)
    row = row_of(sheet, "T1, T2")  # mêmes cotes et mêmes ajouts : une ligne
    before = float(text(sheet, f"F{row}"))
    for joint in cadre.joints.values():
        joint.TenonLength = 30
    cadre.doc.recompute()
    [line] = api.cut_list_of(cadre.doc).lines[-1:]  # tri : repères M1, M2 puis T1, T2
    assert line.marks == ("T1", "T2")
    after = float(text(sheet, f"F{row_of(sheet, 'T1, T2')}"))
    assert after == pytest.approx(line.rough.length)
    assert after != before
    assert line.additions.length == pytest.approx(60)
    assert touched_names(cadre.doc) == []
    assert in_error(cadre.doc) == []


def test_assemblage_a_tourillons_ajoute_apres_la_liste(document: Any) -> None:
    bureau = build_desk(document, joined=False)
    sheet = api.make_cut_list(document)
    assert "Tourillon" not in column(sheet)
    api.make_dowels(bureau.parts["JG"], bureau.parts["V"])
    document.recompute()
    assert "Tourillon" in column(sheet)
    assert touched_names(document) == []


def test_lien_ajoute_apres_la_liste_compte_une_fois_de_plus(document: Any) -> None:
    board = part(document, "M1")
    sheet = api.make_cut_list(document)
    assert text(sheet, f"B{row_of(sheet, 'M1')}") == "1"
    copy = link(document, board)  # recalcule le document
    assert text(sheet, f"B{row_of(sheet, 'M1')}") == "2"
    document.removeObject(copy.Name)
    document.recompute()
    assert text(sheet, f"B{row_of(sheet, 'M1')}") == "1"


def test_ensemble_redimensionne_suit(bureau: Bureau) -> None:
    sheet = api.make_cut_list(bureau.doc)
    assert length_of(sheet, "Plateau") == 1200
    api.resize_furniture(bureau.furniture, width=1400)
    bureau.doc.recompute()
    assert length_of(sheet, "Plateau") == 1400
    assert touched_names(bureau.doc) == []
    assert in_error(bureau.doc) == []


def test_colonnes_de_l_utilisateur_conservees_a_la_mise_a_jour_automatique(document: Any) -> None:
    board = part(document, "M1")
    sheet = api.make_cut_list(document)
    sheet.set("P1", "'ma note")
    sheet.set("Q4", "12")
    board.Length = 900
    document.recompute()
    assert length_of(sheet, "M1") == 900
    assert (text(sheet, "P1"), sheet.getContents("Q4")) == ("ma note", "12")


def test_avertissements_ecrits_dans_la_feuille_sans_inonder_la_vue_rapport(
    document: Any, vue_rapport: Any
) -> None:
    part(document, "M1")
    part(document, "M1", (900, 200, 22))  # même repère, autres cotes
    sheet = api.make_cut_list(document)
    reported = len(vue_rapport.de_niveau("Warning"))
    document.recompute()
    cut_list_object(document).touch()
    document.recompute()
    assert len(vue_rapport.de_niveau("Warning")) == reported
    assert any("Repère M1 utilisé" in cell for cell in column(sheet))


def test_annuler_restaure_la_feuille_et_la_piece_ensemble(document: Any) -> None:
    document.UndoMode = 1
    board = part(document, "M1")
    sheet = api.make_cut_list(document)
    before = length_of(sheet, "M1")
    document.openTransaction("Modifier la longueur")
    board.Length = 1500
    document.recompute()
    document.commitTransaction()
    assert length_of(sheet, "M1") == 1500
    document.undo()
    assert board.Length.Value == before
    assert length_of(sheet, "M1") == before
    document.redo()
    assert board.Length.Value == 1500
    assert length_of(sheet, "M1") == 1500


def test_annuler_l_ajout_d_une_piece_retire_sa_ligne(document: Any) -> None:
    document.UndoMode = 1
    part(document, "M1")
    sheet = api.make_cut_list(document)
    document.openTransaction("Ajouter une pièce")
    part(document, "M2")
    document.commitTransaction()
    assert "M2" in column(sheet)
    document.undo()
    assert "M2" not in column(sheet)
    assert [o.Label for o in cut_list_object(document).Sources] == ["M1"]


# --- V2 : aucun cycle, rien de « Touched » ------------------------------------------------------


def test_bureau_recalcule_comme_avant_et_reste_stable(bureau: Bureau) -> None:
    doc = bureau.doc
    sheet = api.make_cut_list(doc)
    obj = cut_list_object(doc)
    assert obj.InList == []  # nul ne dépend de la liste
    assert sheet.OutList == []
    names = {o.Name for o in obj.Sources}
    assert {bureau.furniture.Name, *(j.Name for j in bureau.joints)} <= names
    assert {p.Name for p in bureau.parts.values()} <= names
    sizes = {mark: bureau.sizes(mark) for mark in bureau.parts}
    doc.recompute()
    assert doc.recompute() == 0  # rien à refaire : aucune réécriture permanente
    assert touched_names(doc) == []
    assert in_error(doc) == []
    assert {mark: bureau.sizes(mark) for mark in bureau.parts} == sizes


def test_recalcul_force_ne_laisse_rien_touched(bureau: Bureau) -> None:
    api.make_cut_list(bureau.doc)
    for obj in bureau.doc.Objects:
        obj.touch()
    assert bureau.doc.recompute() > 0
    assert touched_names(bureau.doc) == []
    assert in_error(bureau.doc) == []


def test_piece_pilotee_par_expression_et_liste_vivante(document: Any) -> None:
    driver = part(document, "M1")
    driven = part(document, "M2")
    driven.setExpression("Length", f"{driver.Name}.Length * 2")
    sheet = api.make_cut_list(document)
    driver.Length = 400
    document.recompute()
    assert (length_of(sheet, "M1"), length_of(sheet, "M2")) == (400, 800)
    assert touched_names(document) == []
    assert in_error(document) == []


def test_liste_sur_un_ensemble_seul_dans_le_perimetre(bureau: Bureau) -> None:
    sheet = api.make_cut_list(bureau.doc, [bureau.furniture])
    assert text(sheet, "A3") == "Sélection : 1 objet"
    api.resize_furniture(bureau.furniture, width=1300)
    bureau.doc.recompute()
    assert length_of(sheet, "Plateau") == 1300


# --- V3 : document ouvert sans l'atelier ------------------------------------------------------


def test_reouverture_avec_l_atelier_la_liste_reste_vivante(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    part(document, "M1")
    sheet = api.make_cut_list(document)
    sheet.set("P2", "'garde")
    name = sheet.Name
    vue_rapport.messages.clear()
    doc = rouvrir(document)
    obj = cut_list_object(doc)
    restored = doc.getObject(name)
    assert (obj.Sheet, obj.Version, obj.Proxy.TYPE) == (restored, 1, "Menuiserie::CutList")
    assert [o.Label for o in obj.Sources] == ["M1"]
    assert not [w for w in vue_rapport.de_niveau("Warning") if "iste de débit" in w]
    board = next(o for o in doc.Objects if o.Label == "M1")
    board.Length = 1111
    doc.recompute()
    assert length_of(restored, "M1") == 1111
    assert text(restored, "P2") == "garde"
    assert touched_names(doc) == []


PROBE = """
import json, sys
import FreeCAD as App
doc = App.openDocument(sys.argv[1])
by_label = {o.Label: o for o in doc.Objects}
sheet = by_label["Liste de débit"]
cut = [o for o in doc.Objects if o.Name == "CutList"][0]
first = [o for o in doc.Objects if o.Label == "M1"][0]
before = [str(sheet.getContents(a)) for a in ("A1", "A6", "B6", "C6", "P2")]
first.Length = 999
doc.recompute()
print(json.dumps({
    "sheet_type": sheet.TypeId,
    "sheet_has_proxy": "Proxy" in sheet.PropertiesList,
    "cut_type": cut.TypeId,
    "cut_has_proxy": getattr(cut, "Proxy", None) is not None,
    "cells": before,
    "after_cells": [str(sheet.getContents(a)) for a in ("A6", "C6", "P2")],
    "invalid": [o.Name for o in doc.Objects if "Invalid" in o.State],
    "sheet_value": sheet.get("C6"),
}))
"""


def test_document_ouvert_sans_l_atelier_feuille_lisible(document: Any, tmp_path: Path) -> None:
    board = part(document, "M1", (850, 200, 22))
    assert board.Length.Value == 850
    sheet = api.make_cut_list(document)
    sheet.set("P2", "'garde")
    path = tmp_path / "debit.FCStd"
    document.saveAs(str(path))
    lib = Path(App.__file__).resolve().parent
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = str(lib)  # FreeCAD seul : le paquet de l'atelier n'est pas importable
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", PROBE, str(path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["sheet_type"] == "Spreadsheet::Sheet"
    assert report["sheet_has_proxy"] is False
    assert report["cut_type"] == "App::FeaturePython"
    assert report["cut_has_proxy"] is False
    assert report["cells"] == ["'Liste de débit", "'M1", "1", "850", "'garde"]
    assert report["sheet_value"] == 850.0  # valeur enregistrée : la liste ne bouge pas seule
    assert report["after_cells"] == ["'M1", "850", "'garde"]
    assert report["invalid"] == []


# --- V4 : supprimer l'objet ou la feuille ---------------------------------------------------


def test_supprimer_l_objet_arrete_la_mise_a_jour_puis_la_relance_la_recree(
    document: Any, vue_rapport: Any
) -> None:
    board = part(document, "M1")
    sheet = api.make_cut_list(document)
    sheet.set("P2", "'garde")
    document.removeObject(cut_list_object(document).Name)
    document.recompute()
    board.Length = 1000
    document.recompute()
    assert length_of(sheet, "M1") != 1000  # plus de mise à jour
    assert vue_rapport.de_niveau("Error") == []
    assert cutlist_object.find_cut_list(document) is None
    assert sheet.Name == SHEET_NAME
    again = api.make_cut_list(document)
    assert again == sheet
    assert cut_list_object(document).Sheet == sheet
    assert length_of(sheet, "M1") == 1000
    assert text(sheet, "P2") == "garde"
    assert len(sheets(document)) == 1


def test_supprimer_la_feuille_arrete_la_mise_a_jour_puis_la_relance_la_recree(
    document: Any, vue_rapport: Any
) -> None:
    board = part(document, "M1")
    sheet = api.make_cut_list(document)
    document.removeObject(sheet.Name)
    document.recompute()
    obj = cut_list_object(document)
    assert obj.Sheet is None
    board.Length = 1000
    assert document.recompute() >= 1
    assert vue_rapport.de_niveau("Error") == []
    assert touched_names(document) == []
    assert in_error(document) == []
    assert sheets(document) == []
    again = api.make_cut_list(document)
    assert (cut_list_object(document), obj) == (obj, obj)
    assert obj.Sheet == again
    assert length_of(again, "M1") == 1000
    assert len(sheets(document)) == 1


def test_supprimer_les_deux_puis_relancer(document: Any) -> None:
    part(document, "M1")
    sheet = api.make_cut_list(document)
    document.removeObject(cut_list_object(document).Name)
    document.removeObject(sheet.Name)
    document.recompute()
    fresh = api.make_cut_list(document)
    assert fresh.Name == SHEET_NAME
    assert cut_list_object(document).Sheet == fresh
    assert "M1" in column(fresh)


def test_annuler_la_creation_retire_la_feuille_et_l_objet(document: Any) -> None:
    document.UndoMode = 1
    part(document, "M1")
    api.make_cut_list(document)
    document.undo()
    assert cutlist_object.find_cut_list(document) is None
    assert sheets(document) == []
    document.redo()
    assert cut_list_object(document).Sheet is not None
    assert "M1" in column(cut_list_object(document).Sheet)


def test_objet_d_un_autre_document_refuse_avant_toute_creation(document: Any) -> None:
    other = App.newDocument("AutreVivante")
    try:
        stranger = part(other, "E")
        with pytest.raises(ValueError, match="autre document"):
            api.make_cut_list(document, [stranger])
    finally:
        App.closeDocument(other.Name)
    assert cutlist_object.find_cut_list(document) is None
    assert sheets(document) == []


def test_document_plus_recent_la_liste_ne_reecrit_rien(document: Any) -> None:
    board = part(document, "M1")
    sheet = api.make_cut_list(document)
    obj = cut_list_object(document)
    obj.Version = 99
    board.Length = 1000
    document.recompute()
    assert length_of(sheet, "M1") != 1000
    assert in_error(document) == []
