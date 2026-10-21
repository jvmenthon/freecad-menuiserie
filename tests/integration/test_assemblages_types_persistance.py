# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réouverture, annulation et compatibilité des assemblages de J3c et J4 (R1, T5, B3, D5, A4 ;
O8, O10, O13, O14 sur la rainure-languette, la feuillure, les tourillons, le mi-bois, la queue
d'aronde et l'onglet)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.test_assemblages_compatibilite import assert_opens_without_workbench
from tests.integration.test_assemblages_persistance import by_name, snapshot
from tests.integration.types_assemblages import (
    PROXIES,
    SCENARIOS,
    Montage,
    Scenario,
    assemble,
    blanks,
    build,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")

Reopen = Callable[[Any], Any]
# Modification annulable de chaque type qui a des propriétés propres (pas l'onglet) : propriété,
# valeur.
CHANGES = {
    "make_tongue_groove": ("TongueThickness", 8),
    "make_rabbet": ("Through", False),
    "make_dowels": ("Count", 3),
    "make_half_lap": ("Depth", 8),
    "make_dovetail": ("TailCount", 2),
}
SLAB = 4000  # bloc qui contient toutes les pièces, quel que soit le repère des montages
IDS = [scenario.name for scenario in SCENARIOS]
TUNABLE = [scenario for scenario in SCENARIOS if scenario.factory in CHANGES]


# --- R1 et T5 : réouverture (comme O8) ---------------------------------------------------


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_reouverture_a_l_identique(document: Any, rouvrir: Reopen, scenario: Scenario) -> None:
    montage = build(document, scenario)
    before = snapshot(document)
    name = montage.joint.Name
    doc = rouvrir(document)
    assert snapshot(doc) == before
    assert stale_or_invalid(doc) == []
    joint = by_name(doc, name)
    module, cls = PROXIES[scenario.factory]
    proxy = type(joint.Proxy)
    assert (proxy.__module__, proxy.__name__) == (
        f"freecad.menuiserie.features.joints.{module}",
        cls,
    )
    assert joint.Proxy.dumps() is None
    assert joint.Version == 1
    doc.recompute()
    restored = Montage(scenario, joint.HostPart, joint.GuestPart, joint)
    restored.assert_expected()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_version_absente_migree(document: Any, rouvrir: Reopen, scenario: Scenario) -> None:
    joint = build(document, scenario).joint
    joint.removeProperty("Version")
    name = joint.Name
    assert by_name(rouvrir(document), name).Version == 1


@pytest.mark.parametrize("scenario", TUNABLE, ids=lambda s: s.name)
def test_propriete_absente_recreee(document: Any, rouvrir: Reopen, scenario: Scenario) -> None:
    """Ancien fichier (sans ``Version``) sans une propriété du type : recréée à son défaut."""
    joint = build(document, scenario).joint
    joint.removeProperty("Version")
    prop, _ = CHANGES[scenario.factory]
    default = joint.getPropertyByName(prop)
    joint.removeProperty(prop)
    name = joint.Name
    assert by_name(rouvrir(document), name).getPropertyByName(prop) == default


# --- R1 et T5 : annuler / rétablir (comme O10) -------------------------------------------


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_annuler_retablir_la_creation(document: Any, scenario: Scenario) -> None:
    document.UndoMode = 1
    host, guest = blanks(document, scenario)
    count = len(document.Objects)
    document.openTransaction("Créer un assemblage")
    montage = assemble(scenario, host, guest)
    document.commitTransaction()
    assert len(document.Objects) == count + 3
    document.undo()
    assert len(document.Objects) == count
    assert (host.Visibility, guest.Visibility) == (True, True)
    document.redo()
    document.recompute()
    assert len(document.Objects) == count + 3
    assert (host.Visibility, guest.Visibility) == (False, False)
    montage.assert_expected()


@pytest.mark.parametrize("scenario", TUNABLE, ids=lambda s: s.name)
def test_annuler_une_modification(document: Any, scenario: Scenario) -> None:
    document.UndoMode = 1
    montage = build(document, scenario)
    prop, value = CHANGES[scenario.factory]
    document.openTransaction("Modifier un assemblage")
    setattr(montage.joint, prop, value)
    document.commitTransaction()
    document.recompute()
    document.undo()
    document.recompute()
    montage.assert_expected()


# --- T5 : O13 et O14 sur un document aux quatre types -------------------------------------


@pytest.fixture
def tous_les_types(document: Any) -> list[Montage]:
    """Les montages de tous les types dans un même document, recalculés."""
    return [build(document, scenario) for scenario in SCENARIOS]


def machined_parts(montages: list[Montage]) -> list[Any]:
    return [api.machined_part_of(blank) for m in montages for blank in (m.host, m.guest)]


def test_pieces_usinees_outils_d_un_part_cut(tous_les_types: list[Montage]) -> None:
    doc = tous_les_types[0].host.Document
    for index, machined in enumerate(machined_parts(tous_les_types)):
        slab = doc.addObject("Part::Box", f"Bloc{index}")
        slab.Length = slab.Width = slab.Height = SLAB
        slab.Placement.Base = App.Vector(-SLAB / 2, -SLAB / 2, -SLAB / 2)
        cut = doc.addObject("Part::Cut", f"Coupe{index}")
        cut.Base, cut.Tool = slab, machined
        doc.recompute()
        assert cut.isValid()
        assert cut.Shape.Volume == pytest.approx(SLAB**3 - machined.Shape.Volume)


def test_vue_techdraw_de_tous_les_types(tous_les_types: list[Montage]) -> None:
    pytest.importorskip("TechDraw", reason="TechDraw non importable dans freecadcmd (critère G)")
    doc = tous_les_types[0].host.Document
    page = doc.addObject("TechDraw::DrawPage", "Page")
    page.Template = doc.addObject("TechDraw::DrawSVGTemplate", "Modele")
    view = doc.addObject("TechDraw::DrawViewPart", "Vue")
    page.addView(view)
    view.Source = machined_parts(tous_les_types)
    doc.recompute()
    assert view.isValid()


def test_export_et_import_step(tous_les_types: list[Montage], tmp_path: Path) -> None:
    import_module = pytest.importorskip("Import")
    for index, machined in enumerate(machined_parts(tous_les_types)):
        path = tmp_path / f"piece{index}.step"
        import_module.export([machined], str(path))
        shape = Part.read(str(path))
        assert shape.isValid()
        assert shape.Volume == pytest.approx(machined.Shape.Volume, rel=1e-6)


def test_document_ouvert_sans_l_atelier(tous_les_types: list[Montage], tmp_path: Path) -> None:
    doc = tous_les_types[0].host.Document
    expected = {obj.Name: obj.Shape.Volume for obj in machined_parts(tous_les_types)}
    assert_opens_without_workbench(doc, expected, tmp_path)
