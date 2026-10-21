# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche des assemblages (J3e) vérifié sans FreeCAD, par analyse statique.

Critère E1 : formulaire construit d'après la description des paramètres de chaque type
(libellé traduisible, case « Auto » pour les paramètres « 0 = automatique » dont la valeur
effective existe dans le résultat de ``resolve``) ; E7 : textes traduisibles ; commandes qui
ouvrent le panneau ; socle commun aux deux panneaux.
"""

from __future__ import annotations

import ast
import re
from dataclasses import fields
from pathlib import Path

import pytest

from freecad.menuiserie.core.joints._profile import ProfileValues
from freecad.menuiserie.core.joints.dowels import DowelParams, DowelValues
from freecad.menuiserie.core.joints.half_lap import HalfLapParams, HalfLapValues
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.core.joints.rabbet import RabbetParams, RabbetValues
from freecad.menuiserie.core.joints.tongue_groove import TongueGrooveParams
from tests.unit.aides import ROOT, imported_modules

PACKAGE = ROOT / "freecad" / "menuiserie"
FEATURES = PACKAGE / "features" / "joints"
PANELS = PACKAGE / "gui" / "task_panels"
# Fichier du type -> (paramètres de core, valeurs effectives de resolve).
TYPES = {
    "mortise_tenon.py": (MortiseTenonParams, ProfileValues),
    "tongue_groove.py": (TongueGrooveParams, ProfileValues),
    "rabbet.py": (RabbetParams, RabbetValues),
    "dowels.py": (DowelParams, DowelValues),
    "half_lap.py": (HalfLapParams, HalfLapValues),
}


def property_specs(path: Path) -> list[dict[str, ast.expr]]:
    """Arguments (positionnels nommés et mots-clés) de chaque ``PropertySpec(...)``."""
    names = ("name", "type_id", "group", "tooltip")
    specs = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "PropertySpec":
            arguments = dict(zip(names, node.args, strict=False))
            arguments |= {kw.arg: kw.value for kw in node.keywords if kw.arg}
            specs.append(arguments)
    return specs


def snake(name: str) -> str:
    """``TenonThickness`` -> ``tenon_thickness`` (inverse de ``property_name``)."""
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()


@pytest.mark.parametrize("module", list(TYPES))
def test_chaque_parametre_a_un_libelle_traduisible(module: str) -> None:
    specs = property_specs(FEATURES / module)
    params_type, _values = TYPES[module]
    assert {snake(ast.literal_eval(s["name"])) for s in specs} == {
        f.name for f in fields(params_type)
    }
    labels = []
    for spec in specs:
        label = spec.get("label")
        assert isinstance(label, ast.Call), ast.literal_eval(spec["name"])
        assert getattr(label.func, "id", "") == "QT_TRANSLATE_NOOP"
        context, text = (ast.literal_eval(arg) for arg in label.args)
        assert context == "Menuiserie"
        labels.append(text)
    assert len(set(labels)) == len(labels)


@pytest.mark.parametrize("module", list(TYPES))
def test_case_auto_pour_les_cotes_automatiques(module: str) -> None:
    """« Auto » : paramètre à 0 par défaut dont la valeur effective est rendue par ``resolve``."""
    params_type, values_type = TYPES[module]
    defaults = {f.name: f.default for f in fields(params_type)}
    value_names = {f.name for f in fields(values_type)}
    for spec in property_specs(FEATURES / module):
        if "resolved" not in spec:
            continue
        resolved = ast.literal_eval(spec["resolved"])
        assert resolved in value_names
        assert defaults[snake(ast.literal_eval(spec["name"]))] == 0


def test_cotes_automatiques_attendues() -> None:
    """Paramètres « 0 = automatique » des spécifications (J3 § 4.3.3, J4 § 4.8.3)."""
    automatic = {
        (module, ast.literal_eval(spec["name"]))
        for module in TYPES
        for spec in property_specs(FEATURES / module)
        if "resolved" in spec
    }
    assert automatic == {
        ("mortise_tenon.py", "TenonThickness"),
        ("mortise_tenon.py", "TenonWidth"),
        ("mortise_tenon.py", "TenonLength"),
        ("tongue_groove.py", "TongueThickness"),
        ("dowels.py", "Diameter"),
        ("dowels.py", "DowelLength"),
        ("dowels.py", "HostDepth"),
        ("dowels.py", "Count"),
        ("dowels.py", "EdgeDistance"),
        ("half_lap.py", "Depth"),
    }


def test_panneau_sans_formulaire_ui_par_type() -> None:
    assert sorted(p.name for p in PANELS.glob("*.ui")) == ["wood_part.ui"]


def test_les_commandes_ouvrent_le_panneau() -> None:
    modules = imported_modules(PACKAGE / "gui" / "commands" / "joints.py")
    assert "freecad.menuiserie.gui.task_panels.joint" in modules


@pytest.mark.parametrize("panel", ["wood_part.py", "joint.py"])
def test_socle_commun_des_panneaux(panel: str) -> None:
    """Transactions, fermeture forcée et surveillance du document : ``base.py``."""
    tree = ast.parse((PANELS / panel).read_text(encoding="utf-8"))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.endswith("Panel")]
    assert [getattr(b, "id", "") for c in classes for b in c.bases] == ["ObjectTaskPanel"]
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not defined & {"close_transaction", "watch_document", "accept", "reject"}
