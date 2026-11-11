# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensemble à la souris, écriture sur un sous-ensemble et façade api (EN-b, B5, Q7)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import Bureau, build_parts
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_ensemble_membres import caisson
from tests.integration.test_ensemble_souris_ecriture import old_furniture, pull
from tests.integration.test_ensemble_std_part import geometry

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
drag = pytest.importorskip("freecad.menuiserie.features.furniture_drag")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
core_geometry = pytest.importorskip("freecad.menuiserie.core.geometry")

Vec3 = core_geometry.Vec3


# --- B5 : sous-ensemble -------------------------------------------------------------------------


def desk_with_drawer(document: Any) -> tuple[Any, Any, Any]:
    desk = build_parts(document)
    sub, _ = caisson(document)
    furniture, _ = api.make_furniture([desk.parts[m] for m in ("P", "JG", "JD")] + [sub], "B")
    return furniture, sub, container.std_part_of(sub)


def test_sous_ensemble_taille_par_son_std_part(document: Any) -> None:
    furniture, sub, std = desk_with_drawer(document)
    right = tuple(App.Vector(std.Placement.Base).add(App.Vector(sub.Width.Value, 0, 0)))
    memento = drag.begin_furniture_drag(sub)
    assert memento.aside  # liaisons du parent mises de côté
    assert sub.ExpressionEngine == [] and std.ExpressionEngine == []
    assert pull(memento, 0, False, -20).reached  # la face gauche recule de 20 mm
    assert sub.Width.Value == 420 and tuple(sub.Origin) == (0, 0, 0)
    assert std.Placement.Base.x == pytest.approx(20)
    messages = drag.end_furniture_drag(memento)
    assert isinstance(messages, list)
    assert stale_or_invalid(document) == []
    assert (std.Placement.Base.x + sub.Width.Value) == pytest.approx(right[0])  # face droite fixe
    assert sub.ExpressionEngine  # le parent a relié le sous-ensemble à sa nouvelle taille
    furniture.Width = 1400
    document.recompute()
    assert stale_or_invalid(document) == []


def test_sous_ensemble_echap_retrouve_ses_liaisons(document: Any) -> None:
    _, sub, std = desk_with_drawer(document)
    engine = (sub.ExpressionEngine, std.ExpressionEngine)
    before = geometry(document)
    memento = drag.begin_furniture_drag(sub)
    pull(memento, 1, True, 80)
    drag.move_furniture_by(memento, Vec3(0, 0, 0))
    drag.restore(memento)
    assert (sub.ExpressionEngine, std.ExpressionEngine) == engine
    assert geometry(document) == before
    assert stale_or_invalid(document) == []


def test_sous_ensemble_deplacement_et_rotation(document: Any) -> None:
    furniture, sub, std = desk_with_drawer(document)
    memento = drag.begin_furniture_drag(sub)
    assert drag.move_furniture_by(memento, Vec3(0, 0, 30))
    assert std.Placement.Base.z == pytest.approx(430)
    assert drag.rotate_furniture_by(memento, 2, 90)
    assert std.Placement.Rotation.getYawPitchRoll()[0] == pytest.approx(90)
    drag.end_furniture_drag(memento)
    assert stale_or_invalid(document) == []
    assert std.Placement.Rotation.getYawPitchRoll()[0] == pytest.approx(90)
    furniture.Depth = 800  # le sous-ensemble tourné suit par translation seulement
    document.recompute()
    assert stale_or_invalid(document) == []
    assert std.Placement.Rotation.getYawPitchRoll()[0] == pytest.approx(90)


def test_sous_ensemble_formule_utilisateur_refuse(document: Any) -> None:
    _, sub, std = desk_with_drawer(document)
    std.setExpression("Placement.Base.z", "400 mm")
    document.recompute()
    memento = drag.begin_furniture_drag(sub)
    assert not drag.rotate_furniture_by(memento, 2, 30)
    step = pull(memento, 2, False, -50)  # la face basse déplacerait le Std Part
    assert not step.reached and "expression" in step.message


# --- Q7 : « Cotes fixes » d'un sous-ensemble ----------------------------------------------------


def test_cotes_fixes_d_un_sous_ensemble(document: Any) -> None:
    furniture, sub, _ = desk_with_drawer(document)
    assert sub.ExpressionEngine  # suit son parent
    api.set_member_options(sub, locked=True)
    assert sub.Locked is True
    assert sub.ExpressionEngine == []  # plus de liaison sur les cotes
    sizes = (sub.Width.Value, sub.Depth.Value, sub.Height.Value)
    api.resize_furniture(furniture, width=1500, depth=900, height=900)
    assert (sub.Width.Value, sub.Depth.Value, sub.Height.Value) == sizes
    assert stale_or_invalid(document) == []
    api.set_member_options(sub, locked=False)
    assert sub.ExpressionEngine  # de nouveau lié
    api.resize_furniture(furniture, width=1600)
    assert sub.Width.Value == sizes[0] + 100  # il suit de nouveau son parent


# --- Façade api ---------------------------------------------------------------------------------


def test_api_deplacer_et_tourner(bureau: Bureau) -> None:
    std = container.std_part_of(bureau.furniture)
    assert api.move_furniture(bureau.furniture, (100.0, 0.0, 0.0))
    assert api.move_furniture(bureau.furniture, (0.0, 50.0, 0.0))
    assert tuple(std.Placement.Base) == (100, 50, 0)  # relatif à la position courante
    assert api.rotate_furniture(bureau.furniture, (0.0, 0.0, 90.0))
    assert std.Placement.Rotation.getYawPitchRoll()[0] == pytest.approx(90)
    assert stale_or_invalid(bureau.doc) == []


def test_api_refuse_sans_std_part(document: Any) -> None:
    old = old_furniture(document)
    assert not api.move_furniture(old, (10.0, 0.0, 0.0))
    assert not api.rotate_furniture(old, (0.0, 0.0, 10.0))
