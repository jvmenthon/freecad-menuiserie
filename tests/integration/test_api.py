# SPDX-License-Identifier: LGPL-2.1-or-later
"""Façade ``api`` dans ``freecadcmd``, sans interface (critère B13, volet intégration)."""

from __future__ import annotations

import sys
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

VIEW_PROVIDER_MODULE = "freecad.menuiserie.gui.view_providers.wood_part"


# --- B13 : make_wood_part dans freecadcmd -------------------------------------------------


def test_make_wood_part_sans_interface(document: Any) -> None:
    obj = api.make_wood_part(800, 200, 22, "chene", doc=document)
    assert not App.GuiUp
    assert "FreeCADGui" not in sys.modules
    assert VIEW_PROVIDER_MODULE not in sys.modules
    assert obj.isValid()
    assert obj.Shape.Volume == pytest.approx(3_520_000)
    assert "Touched" not in obj.State


def test_make_wood_part_dans_le_document_actif(document: Any) -> None:
    App.setActiveDocument(document.Name)
    obj = api.make_wood_part(1000, 250, 27, "hetre", mark="M2")
    assert obj.Document.Name == document.Name
    assert (obj.MaterialId, obj.Mark, obj.Length.Value) == ("hetre", "M2", 1000)


def test_make_wood_part_cree_un_document_si_besoin() -> None:
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    obj = api.make_wood_part()
    try:
        assert obj.isValid()
        assert (obj.MaterialId, obj.Length.Value, obj.Thickness.Value) == ("chene", 800, 22)
    finally:
        App.closeDocument(obj.Document.Name)
