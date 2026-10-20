# SPDX-License-Identifier: LGPL-2.1-or-later
"""Suites de la revue finale de J1b (issue #11) : réouverture de documents altérés ou plus
récents, masse volumique de l'enregistrement de débit, accès à la bibliothèque."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")
library = pytest.importorskip("freecad.menuiserie.features.library")

Reopen = Callable[[Any], Any]
HOSTILE = "\n‮" + "x" * 40


def board(doc: Any, material_id: str = "chene") -> Any:
    """Pièce de 800 x 200 x 22 mm du matériau donné, recalculée."""
    obj = wood_part.create_wood_part(doc, material_id=material_id)
    doc.recompute()
    return obj


def retype(obj: Any, name: str, type_id: str, value: object) -> None:
    """Remplace la propriété ``name`` par une propriété de type ``type_id`` valant ``value``."""
    obj.removeProperty(name)
    obj.addProperty(type_id, name)
    setattr(obj, name, value)


def warnings_with(vue_rapport: Any, text: str) -> list[str]:
    """Avertissements contenant ``text``, chacun sur une seule ligne et sans caractère bidi."""
    warnings = [w for w in vue_rapport.de_niveau("Warning") if text in w]
    for warning in warnings:
        assert warning.count("\n") == 1
        assert "‮" not in warning
    return warnings


# --- Type de chaque propriété contrôlé à la réouverture -----------------------------------

UNITS = {"Length": "mm", "Density": "kg/m^3"}


@pytest.mark.parametrize("version", [0, 1, 2], ids=["ancien", "courant", "plus-recent"])
def test_categorie_d_un_type_inattendu_recreee(
    document: Any, rouvrir: Reopen, vue_rapport: Any, version: int
) -> None:
    obj = board(document, "mdf")
    obj.Version = version
    retype(obj, "Category", "App::PropertyString", "Bogus" + HOSTILE)
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert restored.getTypeIdOfProperty("Category") == "App::PropertyEnumeration"
    assert restored.getEnumerationsOfProperty("Category") == list(wood_part.CATEGORIES)
    assert restored.Category == "MDF"
    assert restored.getEditorMode("Category") == ["ReadOnly"]
    assert restored.Version == max(version, 1)
    assert wood_part.record_of(restored).kind.value == "mdf"
    [warning] = warnings_with(vue_rapport, "type inattendu")
    assert "propriété Category" in warning
    assert "« App::PropertyString »" in warning
    assert "« Bogus\\n\\u202exxx" in warning


# Propriété, type inattendu, valeur écrite, valeur recréée (pièce en MDF).
RETYPED = [
    ("Length", "App::PropertyFloat", 1234.5, 800.0),
    ("Mark", "App::PropertyInteger", 7, ""),
    ("GrainDirection", "App::PropertyString", "Length", "None"),
    ("Density", "App::PropertyFloat", 1.0, 750.0),
]


@pytest.mark.parametrize("case", RETYPED, ids=["cote", "repere", "fil", "masse-volumique"])
def test_chaque_propriete_d_un_type_inattendu_recreee(
    document: Any, rouvrir: Reopen, vue_rapport: Any, case: tuple[str, str, object, object]
) -> None:
    name, type_id, value, expected = case
    obj = board(document, "mdf")
    retype(obj, name, type_id, value)
    part_name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(part_name)
    record = wood_part.record_of(restored)
    restored_value = getattr(restored, name)
    if hasattr(restored_value, "Value"):
        restored_value = round(float(restored_value.getValueAs(UNITS[name])), 6)
    assert restored_value == expected
    assert record.material_id == "mdf"
    assert len(warnings_with(vue_rapport, f"propriété {name} d'un type inattendu")) == 1
    restored.Document.recompute()
    assert restored.isValid()


def test_proprietes_bien_typees_sans_avertissement(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    obj = board(document)
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert vue_rapport.de_niveau("Warning") == []
    assert restored.Version == 1


# --- Document d'une version plus récente : valeurs d'énumération inconnues gardées --------


def future_part(doc: Any) -> Any:
    """Pièce « version 2 » dont les énumérations ont une valeur ajoutée en fin de liste."""
    obj = board(doc)
    obj.Version = 2
    obj.Category = [*wood_part.CATEGORIES, "Future"]
    obj.Category = "Future"
    obj.GrainDirection = [*wood_part.GRAIN_DIRECTIONS, "Diagonal"]
    obj.GrainDirection = "Diagonal"
    return obj


def test_version_plus_recente_garde_les_valeurs_inconnues(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    name = future_part(document).Name
    vue_rapport.messages.clear()
    restored = rouvrir(rouvrir(document)).getObject(name)
    assert (restored.Version, restored.Category, restored.GrainDirection) == (
        2,
        "Future",
        "Diagonal",
    )
    assert restored.getEnumerationsOfProperty("Category") == [*wood_part.CATEGORIES, "Future"]
    assert restored.getEnumerationsOfProperty("GrainDirection")[-1] == "Diagonal"
    kept = warnings_with(vue_rapport, "conservée telle quelle")
    assert len(kept) == 4  # deux par réouverture
    assert "« Future » inconnue pour Category" in kept[0]
    assert "« Diagonal » inconnue pour GrainDirection" in kept[1]
    assert warnings_with(vue_rapport, "remplacée par") == []
    restored.Document.recompute()
    assert restored.isValid()


def test_version_plus_recente_valeur_connue_liste_canonique(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    obj = board(document, "mdf")
    obj.Version = 2
    obj.Category = ["MDF", "Future"]
    obj.Category = "MDF"
    name = obj.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert restored.Category == "MDF"
    assert restored.getEnumerationsOfProperty("Category") == list(wood_part.CATEGORIES)
    assert warnings_with(vue_rapport, "inconnue pour") == []


# --- Masse volumique de l'enregistrement de débit -----------------------------------------


@pytest.mark.parametrize("material_id", ["chene", "hetre", "cp-bouleau", "mdf"])
def test_masse_volumique_exacte_apres_reouverture(
    document: Any, rouvrir: Reopen, material_id: str
) -> None:
    obj = board(document, material_id)
    expected = library.get_library().get(material_id).density
    name = obj.Name
    assert wood_part.record_of(obj).density == expected
    restored = rouvrir(document).getObject(name)
    assert wood_part.record_of(restored).density == expected
