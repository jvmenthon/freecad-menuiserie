# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nom de la pièce = repère dans un vrai document FreeCAD (critères L3 à L7 de J6b, ADR 0011).

Vérifie aussi, sur la version de FreeCAD qui exécute les tests (1.0 et 1.1 en CI), que
``onBeforeChangeLabel`` et ``allowDuplicateLabel`` sont appelés pour un ``FeaturePython`` et que
le libellé saisi arrive tel que tapé (risque R1 de la spécification).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
machined_part = pytest.importorskip("freecad.menuiserie.features.machined_part")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

DEFAULT = "Pièce de bois"


def part(doc: Any, mark: str = "") -> Any:
    obj = api.make_wood_part(800, 200, 22, "chene", mark=mark, doc=doc)
    doc.recompute()
    return obj


# --- R1 : le rappel existe et reçoit le libellé saisi -----------------------------------------


def test_rappels_de_libelle_appeles_avec_le_libelle_saisi(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    original = wood_part.WoodPart.onBeforeChangeLabel

    def spy(self: Any, obj: Any, label: str) -> str | None:
        seen.append(label)
        result: str | None = original(self, obj, label)
        return result

    # le proxy est lu à la création de l'objet : la pièce est créée après l'espion
    monkeypatch.setattr(wood_part.WoodPart, "onBeforeChangeLabel", spy)
    first, second = part(document, "M1"), part(document)
    seen.clear()
    second.Label = "M1"
    assert seen == ["M1"], "FreeCAD a modifié le libellé avant le rappel"
    assert (second.Mark, second.Label, first.Label) == ("M1", "M1 (2)", "M1")


# --- L3 : repère -> nom ------------------------------------------------------------------------


def test_nouvelle_piece_prend_le_libelle_de_son_repere(document: Any) -> None:
    assert part(document, "M1").Label == "M1"
    assert part(document).Label == DEFAULT


def test_changer_le_repere_change_le_libelle_dans_la_meme_transaction(document: Any) -> None:
    document.UndoMode = 1
    obj = part(document)
    document.openTransaction("Repère")
    obj.Mark = "M5"
    document.commitTransaction()
    assert (obj.Mark, obj.Label) == ("M5", "M5")
    document.undo()
    assert (obj.Mark, obj.Label) == ("", DEFAULT)
    document.redo()
    assert (obj.Mark, obj.Label) == ("M5", "M5")


def test_la_piece_usinee_suit_le_repere(document: Any) -> None:
    obj = part(document)
    machined = machined_part.ensure_machined_part(obj)
    obj.Mark = "E2"
    assert machined.Label == "E2 (usinée)"


def test_repere_pilote_par_expression_met_le_libelle_a_jour(document: Any) -> None:
    obj = part(document, "M1")
    obj.setExpression("Mark", "<<M8>>")
    document.recompute()
    assert (obj.Mark, obj.Label) == ("M8", "M8")


# --- L4 : nom -> repère ------------------------------------------------------------------------


def test_renommer_dans_l_arborescence_change_le_repere(document: Any) -> None:
    obj = part(document, "M1")
    obj.Label = "Traverse"
    assert (obj.Mark, obj.Label) == ("Traverse", "Traverse")


def test_renommer_l_usinee_change_le_repere_de_la_brute(document: Any) -> None:
    obj = part(document, "M1")
    machined = machined_part.ensure_machined_part(obj)
    machined.Label = "Pied (usinée)"
    assert (obj.Mark, obj.Label, machined.Label) == ("Pied", "Pied", "Pied (usinée)")


def test_repere_pilote_le_nom_revient_avec_un_avertissement(
    document: Any, vue_rapport: Any
) -> None:
    obj = part(document, "M1")
    obj.setExpression("Mark", "<<M1>>")
    document.recompute()
    vue_rapport.messages.clear()
    obj.Label = "Autre"
    assert (obj.Mark, obj.Label) == ("M1", "M1")
    assert vue_rapport.de_niveau("Warning")


# --- L5 : doublons -----------------------------------------------------------------------------


def test_doublons_et_renommage_en_le_repere(document: Any) -> None:
    first, second = part(document, "M1"), part(document, "M1")
    assert (first.Label, second.Label) == ("M1", "M1 (2)")
    assert (first.Mark, second.Mark) == ("M1", "M1")
    second.Label = "M1"
    assert (second.Mark, second.Label) == ("M1", "M1 (2)")


def test_aucune_preference_de_freecad_modifiee(document: Any) -> None:
    group = App.ParamGet("User parameter:BaseApp/Preferences/Document")
    before = group.GetBool("DuplicateLabels", False)
    part(document, "M1"), part(document, "M1")
    assert group.GetBool("DuplicateLabels", False) == before


# --- L6 : réouverture, annuler, rétablir -------------------------------------------------------


def test_document_ancien_rouvert_sans_changement(
    document: Any, rouvrir: Callable[[Any], Any]
) -> None:
    obj = part(document, "JG")
    with obj.Proxy.synchronizing():
        obj.Label = "Joue gauche"  # état d'un document J1 à J4
    name = obj.Name
    reopened = rouvrir(document)
    restored = reopened.getObject(name)
    assert (restored.Mark, restored.Label) == ("JG", "Joue gauche")
    assert [o.Name for o in reopened.Objects if "Touched" in o.State] == []
    restored.Mark = "JD"  # première modification : la synchronisation s'applique
    assert restored.Label == "JD"


def test_annuler_un_renommage(document: Any) -> None:
    document.UndoMode = 1
    obj = part(document, "M1")
    document.openTransaction("Renommer")
    obj.Label = "Traverse"
    document.commitTransaction()
    document.undo()
    assert (obj.Mark, obj.Label) == ("M1", "M1")
    document.redo()
    assert (obj.Mark, obj.Label) == ("Traverse", "Traverse")


# --- L7 : expressions --------------------------------------------------------------------------


def test_expression_qui_cite_le_libelle_suit_le_repere(document: Any) -> None:
    source, other = part(document, "M1"), part(document, "Z")
    other.setExpression("Length", "<<M1>>.Length")
    source.Mark = "M9"
    engine = {path.lstrip("."): text for path, text in other.ExpressionEngine}
    assert engine["Length"] == "<<M9>>.Length"
    document.recompute()
    assert other.isValid()
