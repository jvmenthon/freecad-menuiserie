# SPDX-License-Identifier: LGPL-2.1-or-later
"""Std Part de l'ensemble (EN-e, ADR 0038, critères E1 à E5, essai E4 sur FreeCAD 1.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.integration.bureau import LAYOUT, build_desk, build_parts
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_ensemble_membres import caisson

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
furniture_module = pytest.importorskip("freecad.menuiserie.features.furniture")

TURNED = App.Placement(App.Vector(150, -80, 25), App.Rotation(App.Vector(0, 0, 1), 30))


def geometry(doc: Any) -> dict[str, tuple[float, ...]]:
    """Boîtes (en repère global) des objets à forme de l'atelier, arrondies."""
    found = {}
    for obj in doc.Objects:
        if obj.TypeId == "Part::FeaturePython" and not obj.Shape.isNull():
            box = obj.Shape.copy()
            box.Placement = obj.getGlobalPlacement()
            b = box.BoundBox
            found[obj.Name] = tuple(round(v, 3) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax))
    return found


def names(part: Any) -> set[str]:
    return {obj.Name for obj in part.Group if obj.TypeId != "App::Origin"}


# --- E1 : Std Part créé avec l'ensemble ---------------------------------------------------------


def test_ensemble_range_dans_son_std_part(document: Any) -> None:
    desk = build_parts(document)
    for side in ("JG", "JD"):
        desk.joints.append(api.make_dowels(desk.parts[side], desk.parts["V"]))
    before = geometry(document)
    furniture, _ = api.make_furniture([desk.parts[m] for m in LAYOUT], label="Bureau")
    std = container.std_part_of(furniture)
    assert std is not None and std.TypeId == "App::Part"
    assert std.Label == "Bureau (Std Part)" and furniture.Label == "Bureau"
    assert tuple(std.Placement.Base) == (0, 0, 0)
    inside = names(std)
    everything = {furniture.Name, *(p.Name for p in desk.parts.values())}
    everything |= {
        api.machined_part_of(p).Name for p in desk.parts.values() if api.machined_part_of(p)
    }
    everything |= {j.Name for j in desk.joints}
    assert inside == everything
    assert geometry(document) == before  # rien ne bouge à l'écran
    api.resize_furniture(furniture, depth=800)
    assert desk.sizes("JG")[1] == 760
    assert stale_or_invalid(document) == []


def test_distance_dans_le_std_part(bureau: Any) -> None:
    from tests.integration.test_distance_gardee import keep

    dist = keep(bureau)
    assert dist.getParentGeoFeatureGroup() == container.std_part_of(bureau.furniture)


def test_ensemble_dans_un_std_part_de_l_utilisateur(document: Any) -> None:
    meuble = document.addObject("App::Part", "Meuble")
    meuble.Placement = TURNED
    desk = build_desk(document, meuble)
    std = container.std_part_of(desk.furniture)
    assert std.getParentGeoFeatureGroup() == meuble
    assert container.guide_container(desk.parts["P"]) == meuble  # E6 : le Std Part est transparent


def test_enregistrement_et_reouverture(bureau: Any, tmp_path: Path) -> None:
    doc = bureau.doc
    path = tmp_path / "e.FCStd"
    doc.saveAs(str(path))
    App.closeDocument(doc.Name)
    reopened = App.openDocument(str(path))
    reopened.recompute()
    assert stale_or_invalid(reopened) == []
    furniture = next(o for o in reopened.Objects if furniture_module.is_furniture(o))
    furniture.Height = 800
    reopened.recompute()
    assert stale_or_invalid(reopened) == []
    App.closeDocument(reopened.Name)


# --- E2 : ajouter, retirer ----------------------------------------------------------------------


def test_ajouter_une_piece_la_range_dans_le_std_part(document: Any) -> None:
    desk = build_parts(document)
    furniture, _ = api.make_furniture([desk.parts[m] for m in ("P", "JG", "JD")], "Bureau")
    std = container.std_part_of(furniture)
    std.Placement = TURNED  # Std Part déplacé et tourné (EN-b) : la pièce garde sa place globale
    document.recompute()
    loose = api.make_wood_part(300, 100, 20, "chene", doc=document)
    loose.Placement = App.Placement(App.Vector(200, 100, 400), App.Rotation())
    document.recompute()
    where = loose.getGlobalPlacement()
    api.add_to_furniture(furniture, [loose])
    assert loose.getParentGeoFeatureGroup() == std
    assert loose.getGlobalPlacement().isSame(where, 1e-6)
    api.remove_from_furniture([loose])
    assert loose.getParentGeoFeatureGroup() is None
    assert loose.getGlobalPlacement().isSame(where, 1e-6)
    assert stale_or_invalid(document) == []


def test_retirer_une_piece_assemblee_la_laisse_dans_le_std_part(bureau: Any) -> None:
    joue = bureau.parts["JG"]
    messages = container.leave([joue])  # appelé après le retrait : la joue touche le voile
    assert messages and "Std Part" in messages[0]
    assert joue.getParentGeoFeatureGroup() == container.std_part_of(bureau.furniture)


# --- E3 : sous-ensemble -------------------------------------------------------------------------


def test_sous_ensemble_a_son_propre_std_part(document: Any) -> None:
    desk = build_parts(document)
    sub, parts = caisson(document)
    sub_std_before = container.std_part_of(sub)
    assert tuple(sub.Origin) == pytest.approx((40, 0, 400))  # ensemble seul : Origin gardée
    before = geometry(document)
    furniture, _ = api.make_furniture(
        [desk.parts["P"], desk.parts["JG"], desk.parts["JD"], sub], "B"
    )
    std = container.std_part_of(furniture)
    sub_std = container.std_part_of(sub)
    assert sub_std == sub_std_before and sub_std.getParentGeoFeatureGroup() == std
    assert tuple(sub.Origin) == (0, 0, 0)
    assert tuple(sub_std.Placement.Base) == pytest.approx((40, 0, 400))
    assert {p.Name for p in parts.values()} <= names(sub_std)
    assert geometry(document) == before  # positions globales inchangées
    furniture.Depth = 800
    furniture.Width = 1400
    document.recompute()
    assert stale_or_invalid(document) == []
    assert sub_std.Placement.Base.x == pytest.approx(40)


def test_sous_ensemble_depuis_des_membres_et_retrait(document: Any) -> None:
    desk = build_parts(document)
    furniture, _ = api.make_furniture(list(desk.parts.values()), label="Bureau")
    drawer, _ = api.make_furniture([desk.parts["P"]], label="Tiroir")
    std, sub_std = container.std_part_of(furniture), container.std_part_of(drawer)
    assert drawer.Furniture == furniture and sub_std.getParentGeoFeatureGroup() == std
    where = desk.parts["P"].getGlobalPlacement()
    api.remove_from_furniture([drawer])
    assert sub_std.getParentGeoFeatureGroup() is None
    assert desk.parts["P"].getGlobalPlacement().isSame(where, 1e-6)
    assert stale_or_invalid(document) == []


def test_un_ensemble_sans_std_part_reste_utilisable(document: Any) -> None:
    """E5 : pas de reprise des anciens documents ; un ensemble sans Std Part n'en a pas."""
    box = furniture_module.FurnitureBox(100, 100, 100)
    old = furniture_module.create_furniture(document, box, container.Vec3(0, 0, 0), "Ancien", None)
    assert container.std_part_of(old) is None
    assert container.position_of(old) == container.Vec3(0, 0, 0)
