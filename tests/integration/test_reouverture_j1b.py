# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réouverture de documents altérés ou hostiles (audit de sécurité de J1b, S1 à S3).

Un document ``.FCStd`` est une donnée externe : ses textes sont cités tronqués et échappés
dans la vue rapport, ses énumérations et sa ``Version`` sont contrôlées avant la migration.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

Reopen = Callable[[Any], Any]
HOSTILE = "\n‮" + "x" * 40


def board(doc: Any, material_id: str = "chene") -> Any:
    """Pièce de 800 x 200 x 22 mm du matériau donné, recalculée."""
    obj = wood_part.create_wood_part(doc, material_id=material_id)
    doc.recompute()
    return obj


def assert_safe(warning: str) -> None:
    """Une seule ligne, sans caractère bidi ni texte démesuré."""
    assert warning.endswith("\n")
    assert warning.count("\n") == 1
    assert "‮" not in warning
    assert len(warning) < 400


# --- S1 : textes du document cités dans la vue rapport ------------------------------------


def test_libelle_et_identifiant_cites_tronques_et_echappes(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    obj = board(document)
    obj.Label = "Pièce" + HOSTILE
    obj.MaterialId = "inconnu" + HOSTILE + "y" * 2_000_000
    vue_rapport.messages.clear()
    rouvrir(document)
    [warning] = vue_rapport.de_niveau("Warning")
    assert_safe(warning)
    assert "« Pièce\\n\\u202exxx" in warning
    assert "« inconnu\\n\\u202exxx" in warning
    assert warning.count("…") == 2


# --- S2 : énumérations relues du fichier ---------------------------------------------------


def set_enumeration(obj: Any, name: str, choices: list[str], value: str) -> None:
    """Écrit dans la pièce une liste d'énumération et une valeur arbitraires."""
    setattr(obj, name, choices)
    setattr(obj, name, value)


def unknown_value_warnings(vue_rapport: Any) -> list[str]:
    warnings = [w for w in vue_rapport.de_niveau("Warning") if "inconnue pour" in w]
    for warning in warnings:
        assert_safe(warning)
    return warnings


# Matériau de la pièce → catégorie, fil et famille attendus après réouverture.
RESTORED = [
    ("mdf", ("MDF", "None", "mdf")),
    ("chene", ("Solid", "Length", "solid")),
    ("cp-bouleau", ("Plywood", "Length", "plywood")),
]


@pytest.mark.parametrize(("material_id", "expected"), RESTORED, ids=[m for m, _ in RESTORED])
def test_valeurs_inconnues_remplacees_par_celles_du_materiau(
    document: Any,
    rouvrir: Reopen,
    vue_rapport: Any,
    material_id: str,
    expected: tuple[str, str, str],
) -> None:
    obj = board(document, material_id)
    set_enumeration(obj, "Category", ["Solid", "Bogus" + HOSTILE], "Bogus" + HOSTILE)
    set_enumeration(obj, "GrainDirection", ["Diagonal"], "Diagonal")
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    kind = wood_part.record_of(restored).kind.value
    assert (restored.Category, restored.GrainDirection, kind) == expected
    assert restored.getEnumerationsOfProperty("Category") == list(wood_part.CATEGORIES)
    assert restored.getEnumerationsOfProperty("GrainDirection") == list(wood_part.GRAIN_DIRECTIONS)
    first, second = unknown_value_warnings(vue_rapport)
    assert "« Bogus\\n\\u202exxx" in first
    assert "« Diagonal »" in second


def test_categorie_inconnue_d_un_materiau_inconnu_devient_massif(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    obj = board(document, "mdf")
    obj.MaterialId = "disparu"
    set_enumeration(obj, "Category", ["Bogus"], "Bogus")
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert (restored.Category, restored.GrainDirection) == ("Solid", "None")
    assert len(unknown_value_warnings(vue_rapport)) == 1


def test_liste_alteree_valeur_connue_conservee(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    obj = board(document, "mdf")
    set_enumeration(obj, "Category", ["Melamine", "MDF", "Extra"], "MDF")
    set_enumeration(obj, "GrainDirection", ["None"], "None")
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert (restored.Category, restored.GrainDirection) == ("MDF", "None")
    assert restored.getEnumerationsOfProperty("Category") == list(wood_part.CATEGORIES)
    assert unknown_value_warnings(vue_rapport) == []


def test_document_version_0_avec_categorie_inconnue(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    obj = board(document, "mdf")
    obj.removeProperty("Version")
    obj.removeProperty("ThicknessAllowance")
    obj.removeProperty("GrainDirection")
    set_enumeration(obj, "Category", ["Bogus" + HOSTILE], "Bogus" + HOSTILE)
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert (restored.Version, restored.Category, restored.GrainDirection) == (1, "MDF", "None")
    assert restored.ThicknessAllowance.Value == 0
    assert len(unknown_value_warnings(vue_rapport)) == 1
    restored.Document.recompute()
    assert restored.isValid()


# --- S3 : Version d'un type inattendu ou plus récente -------------------------------------


@pytest.mark.parametrize(
    ("type_id", "value"),
    [("App::PropertyString", "abc" + HOSTILE), ("App::PropertyFloat", 1.0)],
    ids=["texte", "flottant"],
)
def test_version_d_un_type_inattendu_traitee_comme_0(
    document: Any, rouvrir: Reopen, vue_rapport: Any, type_id: str, value: object
) -> None:
    obj = board(document, "mdf")
    obj.removeProperty("Version")
    obj.removeProperty("ThicknessAllowance")
    obj.addProperty(type_id, "Version")
    obj.Version = value
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert restored.getTypeIdOfProperty("Version") == "App::PropertyInteger"
    assert restored.Version == 1
    assert restored.getEditorMode("Version") == ["Hidden"]
    assert restored.ThicknessAllowance.Value == 0
    [warning] = vue_rapport.de_niveau("Warning")
    assert_safe(warning)
    assert "version du modèle illisible" in warning
    restored.Document.recompute()
    assert restored.isValid()


@pytest.mark.parametrize(("version", "warned"), [(1, False), (2, True), (2**31 - 1, True)])
def test_version_plus_recente_signalee(
    document: Any, rouvrir: Reopen, vue_rapport: Any, version: int, warned: bool
) -> None:
    obj = board(document)
    obj.Version = version
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert restored.Version == version
    warnings = [w for w in vue_rapport.de_niveau("Warning") if "plus récente" in w]
    assert len(warnings) == int(warned)
    assert all(f"modèle {version}, 1 au plus" in w for w in warnings)
