# SPDX-License-Identifier: LGPL-2.1-or-later
"""Entraxe maximal des tourillons, faux tenons et lamellos dans FreeCAD (ADR 0070) : nombre
calculé, recalcul, réouverture, ancien document avec ``Count``, annuler / rétablir."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from freecad.menuiserie.features.joints import base as joints_base
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_assemblages_persistance import by_name
from tests.integration.types_assemblages import BISCUIT, DOWELS, LOOSE_TENON, Scenario, build

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")

SCENARIOS = (DOWELS, LOOSE_TENON, BISCUIT)
IDS = [scenario.name for scenario in SCENARIOS]
DEFAULTS = {"make_dowels": 128.0, "make_loose_tenons": 150.0, "make_biscuits": 150.0}


def counted(joint: Any) -> int:
    return int(joints_base.resolved_for(joint).count)  # type: ignore[attr-defined]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_plus_de_propriete_nombre(document: Any, scenario: Scenario) -> None:
    joint = build(document, scenario).joint
    assert "Count" not in joint.PropertiesList
    assert joint.getTypeIdOfProperty("MaxSpacing") == "App::PropertyLength"
    assert joint.MaxSpacing.Value == DEFAULTS[scenario.factory]  # copié du réglage (défaut)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_recalcul_apres_changement_d_entraxe(document: Any, scenario: Scenario) -> None:
    joint = build(document, scenario).joint
    joint.MaxSpacing = 1000
    document.recompute()
    assert stale_or_invalid(document) == []
    few = counted(joint)
    joint.MaxSpacing = 20
    document.recompute()
    assert stale_or_invalid(document) == []
    assert counted(joint) >= few
    assert counted(joint) <= 50
    joint.MaxSpacing = 0  # 0 : entraxe historique
    document.recompute()
    assert stale_or_invalid(document) == []


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
@pytest.mark.parametrize("value", [5, 1001, -3])
def test_entraxe_invalide_refuse_sans_planter(
    document: Any, scenario: Scenario, value: float
) -> None:
    joint = build(document, scenario).joint
    joint.MaxSpacing = value
    document.recompute()
    assert joint.MaxSpacing.Value == value  # la valeur reste saisie ; le recalcul signale l'erreur
    joint.MaxSpacing = 90
    document.recompute()
    assert stale_or_invalid(document) == []


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_reouverture_garde_l_entraxe_et_le_nombre(
    document: Any, rouvrir: Callable[[Any], Any], scenario: Scenario
) -> None:
    joint = build(document, scenario).joint
    joint.MaxSpacing = 60
    document.recompute()
    expected, name = counted(joint), joint.Name
    doc = rouvrir(document)
    restored = by_name(doc, name)
    assert restored.MaxSpacing.Value == 60
    assert "Count" not in restored.PropertiesList
    doc.recompute()
    assert counted(restored) == expected
    assert stale_or_invalid(doc) == []


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_ancien_document_avec_nombre(
    document: Any, rouvrir: Callable[[Any], Any], scenario: Scenario
) -> None:
    """Fichier de version 1 : ``Count`` saisi, pas de ``MaxSpacing`` ; à la réouverture le
    nombre disparaît et l'entraxe historique est ajouté, sans erreur."""
    joint = build(document, scenario).joint
    joint.addProperty("App::PropertyIntegerConstraint", "Count", "Mortaises", "ancien nombre")
    joint.Count = (7, 0, 50, 1)
    joint.removeProperty("MaxSpacing")
    joint.Version = 1
    name = joint.Name
    doc = rouvrir(document)
    restored = by_name(doc, name)
    assert "Count" not in restored.PropertiesList
    assert restored.MaxSpacing.Value == DEFAULTS[scenario.factory]
    assert restored.Version == type(restored.Proxy).VERSION == 2
    doc.recompute()
    assert stale_or_invalid(doc) == []


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_annuler_retablir_l_entraxe(document: Any, scenario: Scenario) -> None:
    joint = build(document, scenario).joint
    before = joint.MaxSpacing.Value
    document.openTransaction("entraxe")
    joint.MaxSpacing = 45
    document.commitTransaction()
    document.recompute()
    document.undo()
    document.recompute()
    assert joint.MaxSpacing.Value == before
    document.redo()
    document.recompute()
    assert joint.MaxSpacing.Value == 45
    assert stale_or_invalid(document) == []


def test_api_refuse_le_nombre(document: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        build(document, DOWELS, count=3)
