# SPDX-License-Identifier: LGPL-2.1-or-later
"""Numérotation automatique des repères dans le document (J2f, critère N1 de ``docs/specs/J2``
§ 10) : un repère par groupe de pièces sans repère, premier numéro libre, ensemble puis cotes
décroissantes, une transaction, libellé qui suit le repère, liste vivante à jour.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.aides import touched_names
from tests.integration.cadre import Cadre
from tests.integration.debit import column, sheets

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

TITLE = "Numéroter les repères"


def blank(doc: Any, length: float, mark: str = "", y: float = 0.0) -> Any:
    """Pièce de chêne de ``length`` x 100 x 22, sans repère par défaut."""
    obj = api.make_wood_part(length, 100.0, 22.0, "chene", mark=mark, doc=doc)
    obj.Placement = App.Placement(App.Vector(0, y, 0), App.Rotation())
    doc.recompute()
    return obj


def marks(*parts: Any) -> list[str]:
    return [str(obj.Mark) for obj in parts]


def test_un_repere_par_groupe_cotes_decroissantes(document: Any) -> None:
    small, long_a, long_b, medium = (
        blank(document, 300),
        blank(document, 800, y=200),
        blank(document, 800, y=400),
        blank(document, 500, y=600),
    )
    written = api.number_marks(document)
    assert marks(long_a, long_b, medium, small) == ["M1", "M1", "M2", "M3"]
    assert written == {
        long_a.Name: "M1",
        long_b.Name: "M1",
        medium.Name: "M2",
        small.Name: "M3",
    }
    assert touched_names(document) == []


def test_le_libelle_suit_le_repere(document: Any) -> None:
    first, second, third = blank(document, 800), blank(document, 800, y=200), blank(document, 300)
    api.number_marks(document)
    assert sorted([first.Label, second.Label]) == ["M1", "M1 (2)"]  # J6 : libellés uniques
    assert third.Label == "M2"


def test_les_reperes_existants_sont_gardes_et_sautes(document: Any) -> None:
    kept = blank(document, 100, mark="M1")
    named = blank(document, 100, mark="Plateau", y=200)
    first, second = blank(document, 400, y=400), blank(document, 300, y=600)
    api.number_marks(document)
    assert marks(kept, named, first, second) == ["M1", "Plateau", "M2", "M3"]
    assert (kept.Label, named.Label) == ("M1", "Plateau")


def test_prefixe_personnalise_et_refus(document: Any) -> None:
    first = blank(document, 400)
    blank(document, 300, mark="M1", y=200)
    assert api.number_marks(document, prefix="P") == {first.Name: "P1"}
    for prefix in ("", "  "):
        with pytest.raises(ValueError, match="préfixe"):
            api.number_marks(document, prefix=prefix)


def test_rien_a_numeroter_n_ouvre_aucune_transaction(document: Any) -> None:
    document.UndoMode = 1
    blank(document, 400, mark="M1")
    before = document.UndoCount
    assert api.number_marks(document) == {}
    assert document.UndoCount == before


def test_une_seule_transaction_annulable(document: Any) -> None:
    document.UndoMode = 1
    first, second = blank(document, 800), blank(document, 300, y=200)
    labels = [first.Label, second.Label]
    before = document.UndoCount
    api.number_marks(document)
    assert document.UndoCount == before + 1
    assert document.UndoNames[0] == TITLE
    document.undo()
    assert marks(first, second) == ["", ""]
    assert [first.Label, second.Label] == labels
    document.redo()
    assert marks(first, second) == ["M1", "M2"]


def test_portee_choisie(document: Any) -> None:
    chosen, other = blank(document, 800), blank(document, 800, y=200)
    third = blank(document, 300, y=400)
    written = api.number_marks(document, [chosen, third])
    assert written == {chosen.Name: "M1", third.Name: "M2"}
    assert marks(other) == [""]
    # Les pièces restantes prennent la suite : M1 et M2 sont déjà pris par le document.
    assert api.number_marks(document) == {other.Name: "M3"}


def test_un_ensemble_d_abord_puis_les_cotes_decroissantes(document: Any) -> None:
    outside = blank(document, 900)
    inside_long, inside_short = blank(document, 700, y=200), blank(document, 200, y=400)
    api.make_furniture([inside_long, inside_short], "Caisson")
    api.number_marks(document)
    assert marks(inside_long, inside_short, outside) == ["M1", "M2", "M3"]


def test_objet_d_un_autre_document_refuse(document: Any) -> None:
    other = App.newDocument("AutreNumerotation")
    try:
        stranger = blank(other, 400)
        with pytest.raises(ValueError, match="autre document"):
            api.number_marks(document, [stranger])
        assert marks(stranger) == [""]
    finally:
        App.closeDocument(other.Name)


def test_repere_pilote_par_une_expression_non_touche(document: Any) -> None:
    driven, free = blank(document, 400), blank(document, 300, y=200)
    driven.setExpression("Mark", "<<>>")
    document.recompute()
    assert api.number_marks(document) == {free.Name: "M1"}
    assert marks(driven) == [""]


def test_pieces_usinees_regroupees_avec_leurs_ajouts(cadre: Cadre) -> None:
    for part in cadre.parts.values():
        part.Mark = ""
    cadre.assemble()
    written = api.number_marks(cadre.doc)
    assert sorted(set(written.values())) == ["M1", "M2"]
    assert written[cadre.parts["M1"].Name] == written[cadre.parts["M2"].Name] == "M1"
    assert written[cadre.parts["T1"].Name] == written[cadre.parts["T2"].Name] == "M2"
    assert touched_names(cadre.doc) == []


def test_la_liste_vivante_suit_dans_la_meme_transaction(document: Any) -> None:
    document.UndoMode = 1
    first, second = blank(document, 800), blank(document, 300, y=200)
    sheet = api.make_cut_list(document)
    assert "—" in column(sheet)  # pièces sans repère
    before = document.UndoCount
    api.number_marks(document)
    assert document.UndoCount == before + 1
    assert {"M1", "M2"} <= set(column(sheet))
    assert "—" not in column(sheet)
    document.undo()
    assert "M1" not in column(sheet)
    assert "—" in column(sheet)
    assert marks(first, second) == ["", ""]
    assert len(sheets(document)) == 1


def test_numeroter_puis_lister_donne_une_ligne_par_groupe(document: Any) -> None:
    for y in (0, 200, 400):
        blank(document, 800, y=y)
    blank(document, 300, y=600)
    api.number_marks(document)
    sheet = api.make_cut_list(document)
    rows = [cell for cell in column(sheet)[5:] if cell in ("M1", "M2")]
    assert rows == ["M1", "M2"]  # trois pièces identiques = une seule ligne, quantité 3
