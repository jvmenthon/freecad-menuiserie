# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu et boutons de rotation (J6c) : parties vérifiables sans FreeCAD."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import pytest

from freecad.menuiserie import ICONS_DIR
from freecad.menuiserie.core.geometry import squared_rotation
from freecad.menuiserie.gui.task_panels.preview import PREVIEW_TRANSPARENCY, PreviewStyle
from tests.unit.aides import ROOT

UI_FILE = ROOT / "freecad/menuiserie/gui/task_panels/wood_part.ui"
EXACT = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))


class FakeViewObject:
    def __init__(self, transparency: int = 25) -> None:
        self.Transparency = transparency


class DeletedViewObject(FakeViewObject):
    def __setattr__(self, name: str, value: Any) -> None:
        if name == "Transparency" and "Transparency" in self.__dict__ and value != 60:
            raise ReferenceError("Cannot access attribute of deleted object")
        super().__setattr__(name, value)


def test_rotation_d_equerre_ramenee_a_la_permutation_exacte() -> None:
    noisy = tuple(tuple(v + 1e-13 for v in row) for row in EXACT)
    assert squared_rotation(noisy) == EXACT  # type: ignore[arg-type]
    assert squared_rotation(EXACT) == EXACT


def test_rotation_oblique_inchangee() -> None:
    c = 0.8660254037844386
    oblique = ((c, -0.5, 0.0), (0.5, c, 0.0), (0.0, 0.0, 1.0))
    assert squared_rotation(oblique) == oblique
    almost = ((1.001, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    assert squared_rotation(almost) == almost


def test_apercu_pose_puis_retablit_la_transparence() -> None:
    vobj = FakeViewObject(25)
    style = PreviewStyle(vobj)
    assert vobj.Transparency == PREVIEW_TRANSPARENCY == 60
    style.restore()
    assert vobj.Transparency == 25
    vobj.Transparency = 80
    style.restore()  # déjà rétabli : sans effet
    assert vobj.Transparency == 80


def test_apercu_sans_interface_ou_objet_disparu() -> None:
    PreviewStyle(None).restore()
    vobj = DeletedViewObject(10)
    style = PreviewStyle(vobj)
    style.restore()  # l'objet a disparu : aucune exception


def groups() -> list[str]:
    root = ET.parse(UI_FILE).getroot()  # noqa: S314 (fichier du dépôt)
    layout = root.find("widget/layout")
    assert layout is not None
    names = []
    for item in layout.findall("item"):
        widget = item.find("widget")
        assert widget is not None
        names.append(widget.get("name", ""))
    return names


def test_ordre_des_groupes_identification_materiau_dimensions_rotation() -> None:
    assert [name for name in groups() if name.endswith("Group")] == [
        "identificationGroup",
        "materialGroup",
        "dimensionsGroup",
        "rotationGroup",
    ]


@pytest.mark.parametrize("axis", "XYZ")
def test_bouton_et_icone_de_chaque_axe(axis: str) -> None:
    root = ET.parse(UI_FILE).getroot()  # noqa: S314 (fichier du dépôt)
    names = {w.get("name") for w in root.iter("widget")}
    assert f"rotate{axis}Button" in names
    assert (ICONS_DIR / f"Menuiserie_Rotate{axis}.svg").is_file()
    tooltips = [
        s.text or ""
        for w in root.iter("widget")
        if w.get("name") == f"rotate{axis}Button"
        for p in w.findall("property")
        if p.get("name") == "toolTip"
        for s in p.findall("string")
    ]
    assert tooltips
    assert f"axe {axis}" in tooltips[0]
