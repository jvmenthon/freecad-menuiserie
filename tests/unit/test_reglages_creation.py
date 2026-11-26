# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier lus à la création des pièces et des assemblages, et « Dernier utilisé »
(ADR 0031, 0069). Sans réglage modifié, le comportement est celui d'avant."""

from __future__ import annotations

import importlib
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core.edges import BROKEN_EDGE_MM, EdgeFamily, all_edges
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.materials import MaterialKind, MaterialLibrary
from freecad.menuiserie.core.part_model import (
    DEFAULT_DIMENSIONS,
    DEFAULT_PANEL_ALLOWANCES,
    DEFAULT_SOLID_ALLOWANCES,
)
from tests.unit.aides import make_material
from tests.unit.aides_reglages import settings_module


class Modules:
    """Modules de ``features`` importés avec le FreeCAD simulé, au-dessus des réglages."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.part: Any = importlib.import_module("freecad.menuiserie.features.new_part_settings")
        self.joint: Any = importlib.import_module("freecad.menuiserie.features.joint_settings")
        self.edge: Any = importlib.import_module("freecad.menuiserie.features.edge_settings")
        self.record: Any = importlib.import_module("freecad.menuiserie.features.record_created")
        self.values = config.settings()


@pytest.fixture
def modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Modules]:
    with settings_module(monkeypatch, tmp_path) as config:
        yield Modules(config)


def _quantity(value: float) -> Any:
    return types.SimpleNamespace(Value=value)


def _part(category: str = "Solid", **allowances: float) -> Any:
    """Pièce simulée : famille et surcotes (en mm) lues par ``Value``."""
    defaults = {"LengthAllowance": 20.0, "WidthAllowance": 5.0, "ThicknessAllowance": 0.0}
    values = {**defaults, **allowances}
    return types.SimpleNamespace(
        PropertiesList=["Category"],
        Category=category,
        **{name: _quantity(value) for name, value in values.items()},
    )


# --- pièces neuves ---------------------------------------------------------------------------


def test_pieces_neuves_sans_reglage_modifie_comme_avant(modules: Modules) -> None:
    assert modules.part.new_dimensions() == DEFAULT_DIMENSIONS
    assert modules.part.new_material_id() is None
    assert modules.part.new_allowances(MaterialKind.SOLID) == DEFAULT_SOLID_ALLOWANCES
    assert modules.part.new_allowances(MaterialKind.MDF) == DEFAULT_PANEL_ALLOWANCES
    assert modules.part.broken_edge_size() is None
    part = _part()
    modules.part.apply_new_allowances(part)
    assert (part.LengthAllowance.Value, part.WidthAllowance.Value) == (20.0, 5.0)


def test_cotes_et_surcotes_de_l_atelier(modules: Modules) -> None:
    config, values = modules.config, modules.values
    for key, value in ((config.LENGTH, 1200.0), (config.WIDTH, 300.0), (config.THICKNESS, 19.0)):
        values.set(key, value)
    values.set(config.SOLID_ALLOWANCES[0], 30.0)
    values.set(config.PANEL_ALLOWANCES[1], 4.0)
    dimensions = modules.part.new_dimensions()
    assert (dimensions.length, dimensions.width, dimensions.thickness) == (1200.0, 300.0, 19.0)
    assert modules.part.new_allowances(MaterialKind.SOLID).length == 30.0
    assert modules.part.new_allowances(MaterialKind.MDF).width == 4.0
    solid, panel = _part(), _part("MDF", LengthAllowance=0.0, WidthAllowance=0.0)
    modules.part.apply_new_allowances(solid)
    modules.part.apply_new_allowances(panel)
    assert solid.LengthAllowance == 30.0  # réécrite ; la largeur, déjà égale, ne l'est pas
    assert isinstance(solid.WidthAllowance, types.SimpleNamespace)
    assert panel.WidthAllowance == 4.0


def test_materiau_de_l_atelier_seulement_s_il_est_dans_la_bibliotheque(
    modules: Modules, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        modules.part, "get_library", lambda: MaterialLibrary([make_material("chene", "Chêne")])
    )
    modules.values.set(modules.config.MATERIAL, "chene")
    assert modules.part.new_material_id() == "chene"
    modules.values.set(modules.config.MATERIAL, "disparu")  # matériau retiré de la bibliothèque
    assert modules.part.new_material_id() is None


def test_arete_cassee_des_pieces_neuves(modules: Modules) -> None:
    modules.values.set(modules.config.BROKEN_EDGE, True)
    assert modules.part.broken_edge_size() == BROKEN_EDGE_MM
    modules.values.set(modules.config.BROKEN_EDGE_SIZE, 2.5)
    assert modules.part.broken_edge_size() == 2.5
    box = types.SimpleNamespace(PropertiesList=[])
    assert modules.part.broken_edge_designation(box) == list(all_edges())
    assert len(all_edges()) == 12


def test_dernier_utilise_des_pieces(modules: Modules) -> None:
    config, values = modules.config, modules.values
    values.set_remember_last(config.BROKEN_EDGE, True)
    assert values.record_used(config.BROKEN_EDGE, True)
    assert values.value(config.BROKEN_EDGE) is True
    part = _part()
    part.Length, part.Width, part.Thickness = _quantity(900.0), _quantity(250.0), _quantity(18.0)
    part.MaterialId = "chene"
    modules.part.record_part_used(part)  # aucune case cochée sur ces réglages : rien ne change
    assert values.value(config.LENGTH) == DEFAULT_DIMENSIONS.length


# --- assemblages -----------------------------------------------------------------------------


def test_assemblages_sans_reglage_modifie_comme_avant(modules: Modules) -> None:
    for kind in JointKind:
        assert modules.joint.apply_joint_settings(kind, {}) == {}
    given = {"through": True}
    assert modules.joint.apply_joint_settings(JointKind.RABBET, given) == given


def test_reglages_modifies_donnes_aux_parametres_absents(modules: Modules) -> None:
    config, values = modules.config, modules.values
    values.set(config.MORTISE_CLEARANCE, 3.0)
    values.set(config.MORTISE_THROUGH, True)
    values.set(config.TONGUE_LENGTH, 15.0)
    values.set(config.DOVETAIL_ANGLE, 8.0)
    values.set(config.SLOT_FREE_SIZE, True)
    apply = modules.joint.apply_joint_settings
    assert apply(JointKind.MORTISE_TENON, {}) == {"mortise_clearance": 3.0, "through": True}
    assert apply(JointKind.MORTISE_TENON, {"mortise_clearance": 1.0}) == {
        "mortise_clearance": 1.0,  # le paramètre donné par l'appelant l'emporte
        "through": True,
    }
    assert apply(JointKind.TONGUE_GROOVE, {}) == {"tongue_length": 15.0}
    assert apply(JointKind.DOVETAIL, {}) == {"angle": 8.0}
    assert apply(JointKind.LOOSE_TENON, {}) == {"custom_size": True}
    assert apply(JointKind.MITER, {}) == {}  # aucun réglage pour cet assemblage


def test_dernier_utilise_d_un_assemblage(modules: Modules) -> None:
    config, values = modules.config, modules.values
    values.set_remember_last(config.MORTISE_CLEARANCE, True)
    mortise_tenon = importlib.import_module("freecad.menuiserie.features.joints.mortise_tenon")
    proxy = object.__new__(mortise_tenon.MortiseTenonJoint)  # sans objet FreeCAD
    joint = types.SimpleNamespace(Proxy=proxy, MortiseClearance=_quantity(4.0), Through=True)
    modules.record.record_created(joint)
    assert values.value(config.MORTISE_CLEARANCE) == 4.0
    assert values.value(config.MORTISE_THROUGH) is False  # case « Dernier utilisé » non cochée


def test_record_created_ignore_un_autre_objet(modules: Modules) -> None:
    modules.record.record_created(types.SimpleNamespace(Proxy=None))
    modules.record.record_created(types.SimpleNamespace())


# --- finition des chants ---------------------------------------------------------------------


def test_profil_propose_puis_dernier_utilise(modules: Modules) -> None:
    config, values = modules.config, modules.values
    assert modules.edge.proposed_profile() == (EdgeFamily.ROUND, BROKEN_EDGE_MM)
    modules.edge.record_profile_used(EdgeFamily.CHAMFER.value, 3.0)  # cases non cochées
    assert modules.edge.proposed_profile() == (EdgeFamily.ROUND, BROKEN_EDGE_MM)
    values.set_remember_last(config.EDGE_PROFILE, True)
    values.set_remember_last(config.EDGE_PROFILE_SIZE, True)
    modules.edge.record_profile_used(EdgeFamily.CHAMFER.value, 3.0)
    assert modules.edge.proposed_profile() == (EdgeFamily.CHAMFER, 3.0)
    modules.edge.record_profile_used(EdgeFamily.OGEE.value, 0.0)  # cote refusée : ignorée
    assert modules.edge.proposed_profile() == (EdgeFamily.OGEE, 3.0)


def test_fabrique_d_assemblage_applique_les_reglages(
    modules: Modules, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``create_mortise_tenon`` : réglage modifié donné, valeur de l'appelant prioritaire,
    défauts de ``core`` sans réglage."""
    factories = importlib.import_module("freecad.menuiserie.features.joints.factories")
    created: list[Any] = []

    def capture(_joint_class: Any, _doc: Any, _host: Any, _guest: Any, params: Any) -> str:
        created.append(params)
        return "joint"

    monkeypatch.setattr(factories, "create_joint", capture)
    assert factories.create_mortise_tenon("doc", "hote", "invitee") == "joint"
    assert created[0].mortise_clearance == 2.0
    modules.values.set(modules.config.MORTISE_CLEARANCE, 3.0)
    factories.create_mortise_tenon("doc", "hote", "invitee")
    factories.create_mortise_tenon("doc", "hote", "invitee", mortise_clearance=1.0)
    assert [params.mortise_clearance for params in created[1:]] == [3.0, 1.0]
