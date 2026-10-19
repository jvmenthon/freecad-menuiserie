# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chargement de l'atelier dans un vrai FreeCAD (sans interface graphique)."""

import importlib

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")


def test_version_freecad_minimale() -> None:
    major, minor = (int(x) for x in App.Version()[:2])
    assert (major, minor) >= (1, 0)


def test_paquet_importable_en_console() -> None:
    module = importlib.import_module("freecad.menuiserie")
    assert module.__version__


def test_document_vide_se_recalcule() -> None:
    doc = App.newDocument("TestMenuiserie")
    try:
        doc.recompute()
        assert doc.isValid()
    finally:
        App.closeDocument(doc.Name)
