# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chargement de l'atelier dans un vrai FreeCAD (sans interface graphique)."""

import importlib

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")


def test_version_freecad_minimale() -> None:
    major, minor = (int(x) for x in App.Version()[:2])
    assert (major, minor) >= (1, 0)


@pytest.mark.parametrize(
    "module",
    ["freecad.menuiserie", "freecad.menuiserie.core", "freecad.menuiserie.features"],
)
def test_couches_app_importables_en_console(module: str) -> None:
    assert importlib.import_module(module)


def test_document_se_recalcule_en_console() -> None:
    doc = App.newDocument("TestMenuiserie")
    try:
        boite = doc.addObject("Part::Box", "Boite")
        doc.recompute()
        assert boite.isValid()
        assert boite.Shape.Volume == pytest.approx(1000.0)
    finally:
        App.closeDocument(doc.Name)
