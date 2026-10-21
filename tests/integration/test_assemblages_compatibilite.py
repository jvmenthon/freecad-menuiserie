# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces usinées dans les autres ateliers et sans l'atelier (J3b, O13 et O14, ADR 0007)."""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 : FreeCAD relancé sur un script du test, sans shell
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.integration.cadre import RAIL_VOLUME, STILE_VOLUME, Cadre

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
FREECAD_LIB = Path(App.__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]

# Script lancé dans un interpréteur où seul FreeCAD est importable : ouvre le document et
# écrit, en JSON, la présence de l'atelier et le volume et la validité de chaque forme non vide.
WITHOUT_WORKBENCH = """
import importlib.util, json, sys
import FreeCAD
found = importlib.util.find_spec("freecad.menuiserie") is not None
doc = FreeCAD.openDocument(sys.argv[1])
shapes = {
    obj.Name: [obj.Shape.isValid(), obj.Shape.Volume]
    for obj in doc.Objects
    if hasattr(obj, "Shape") and not obj.Shape.isNull() and obj.Shape.Volume > 0
}
print("RESULTAT " + json.dumps({"workbench": found, "shapes": shapes}))
"""


# --- O13 : Part::Cut, TechDraw, STEP -----------------------------------------------------


def test_piece_usinee_base_et_outil_d_un_part_cut(cadre_assemble: Cadre) -> None:
    doc = cadre_assemble.doc
    lower_half = doc.addObject("Part::Box", "MoitieBasse")
    lower_half.Length, lower_half.Width, lower_half.Height = 600, 60, 11
    as_base = doc.addObject("Part::Cut", "CoupeBase")
    as_base.Base, as_base.Tool = cadre_assemble.machined("M1"), lower_half
    slab = doc.addObject("Part::Box", "Plateau")
    slab.Length, slab.Width, slab.Height = 1000, 1000, 22
    slab.Placement.Base = App.Vector(-200, -200, 0)
    as_tool = doc.addObject("Part::Cut", "CoupeOutil")
    as_tool.Base, as_tool.Tool = slab, cadre_assemble.machined("T1")
    doc.recompute()
    # Moitié basse de M1 : 600 x 60 x 11 moins le bas des deux mortaises (z de 7,5 à 11).
    common = 600 * 60 * 11 - 2 * 42 * 40 * 3.5
    assert as_base.isValid()
    assert as_base.Shape.Volume == pytest.approx(STILE_VOLUME - common)
    assert as_tool.isValid()
    assert as_tool.Shape.Volume == pytest.approx(1000 * 1000 * 22 - RAIL_VOLUME)


def test_vue_techdraw_d_une_piece_usinee(cadre_assemble: Cadre) -> None:
    pytest.importorskip("TechDraw", reason="TechDraw non importable dans freecadcmd (critère G)")
    doc = cadre_assemble.doc
    page = doc.addObject("TechDraw::DrawPage", "Page")
    page.Template = doc.addObject("TechDraw::DrawSVGTemplate", "Modele")
    view = doc.addObject("TechDraw::DrawViewPart", "Vue")
    page.addView(view)
    view.Source = [cadre_assemble.machined("M1")]
    doc.recompute()
    assert view.isValid()
    assert "Invalid" not in view.State


def test_export_et_import_step(cadre_assemble: Cadre, tmp_path: Path) -> None:
    import_module = pytest.importorskip("Import")
    path = tmp_path / "montant.step"
    machined = cadre_assemble.machined("M1")
    import_module.export([machined], str(path))
    shape = Part.read(str(path))
    assert shape.isValid()
    assert shape.Volume == pytest.approx(machined.Shape.Volume, rel=1e-6)


# --- O14 : document ouvert sans l'atelier ------------------------------------------------


def run_python(arguments: list[str], cwd: Path, pythonpath: list[Path]) -> str:
    """Sortie d'un interpréteur neuf (sans shell), ``PYTHONPATH`` réduit à ``pythonpath``."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in pythonpath)
    completed = subprocess.run(  # noqa: S603  # nosec B603 : arguments fixés par le test
        [sys.executable, *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return completed.stdout


@pytest.mark.parametrize(
    "module",
    [
        "freecad.menuiserie.features.machined_part",
        "freecad.menuiserie.features.joints.mortise_tenon",
        "freecad.menuiserie.features.joints.tongue_groove",
        "freecad.menuiserie.features.joints.rabbet",
        "freecad.menuiserie.features.joints.dowels",
        "freecad.menuiserie.features.joints.base",
    ],
)
def test_module_de_proxy_importable_seul(module: str, tmp_path: Path) -> None:
    """À la réouverture, FreeCAD importe d'abord le module du premier proxy rencontré."""
    code = f"import FreeCAD, importlib; importlib.import_module({module!r}); print('OK')"
    output = run_python(["-c", code], tmp_path, [FREECAD_LIB, ROOT])
    assert output.strip().endswith("OK")


def assert_opens_without_workbench(doc: Any, expected: dict[str, float], tmp_path: Path) -> None:
    """Enregistre ``doc`` et l'ouvre dans un interpréteur sans l'atelier : objets ``expected``
    (nom → volume) présents, de forme valide et de même volume."""
    path = tmp_path / "sans_atelier.FCStd"
    doc.saveAs(str(path))
    script = tmp_path / "ouvrir.py"
    script.write_text(WITHOUT_WORKBENCH, encoding="utf-8")
    output = run_python([str(script), str(path)], tmp_path, [FREECAD_LIB])
    [line] = [line for line in output.splitlines() if line.startswith("RESULTAT ")]
    result: dict[str, Any] = json.loads(line.removeprefix("RESULTAT "))
    assert result["workbench"] is False
    assert set(expected) <= set(result["shapes"])
    for name, volume in expected.items():
        assert result["shapes"][name][0], name
        assert result["shapes"][name][1] == pytest.approx(volume), name


def test_document_ouvert_sans_l_atelier(cadre_assemble: Cadre, tmp_path: Path) -> None:
    expected = {
        obj.Name: obj.Shape.Volume
        for obj in cadre_assemble.doc.Objects
        if obj.Name.startswith("MachinedPart")
    }
    assert_opens_without_workbench(cadre_assemble.doc, expected, tmp_path)
