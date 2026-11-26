# SPDX-License-Identifier: LGPL-2.1-or-later
"""Reste des réglages de l'atelier dans un vrai document FreeCAD (CA-d, ADR 0069) : sens du fil
d'une pièce neuve, taquets et préfixe des repères copiés à la création, jamais relus ensuite."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import wood

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
config = pytest.importorskip("freecad.menuiserie.features.settings")


@pytest.fixture
def reglages() -> Iterator[Any]:
    """Réglages de l'atelier : toutes les clés du catalogue rétablies avant et après le test."""
    values = config.settings()
    values.reset_all()
    yield values
    values.reset_all()


def test_sens_du_fil_de_l_atelier_copie_dans_la_piece_neuve(document: Any, reglages: Any) -> None:
    before = api.make_wood_part(doc=document)
    assert before.GrainDirection == "Length"
    reglages.set(config.GRAIN, "Width")
    part = api.make_wood_part(doc=document)
    assert part.GrainDirection == "Width"
    reglages.reset(config.GRAIN)
    document.recompute()
    assert part.GrainDirection == "Width" and before.GrainDirection == "Length"
    assert stale_or_invalid(document) == []


def test_fil_de_l_atelier_ignore_un_panneau_sans_fil(document: Any, reglages: Any) -> None:
    reglages.set(config.GRAIN, "Width")
    panel = api.make_wood_part(600, 400, 19, "mdf", doc=document)
    assert panel.GrainDirection == "None"


def test_taquets_prennent_le_reglage_a_la_creation(document: Any, reglages: Any) -> None:
    where = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90))
    side = wood(document, "S", (720, 500, 19), where)
    document.recompute()
    first = api.make_shelf_pins(side)
    assert (first.Pitch.Value, first.HoleDiameter.Value, first.HoleDepth.Value) == (32.0, 0.0, 0.0)
    reglages.set(config.SHELF_PIN_PITCH, 64.0)
    reglages.set(config.SHELF_PIN_DIAMETER, 6.0)
    far = App.Placement(App.Vector(0, 1000, 0), App.Rotation(App.Vector(0, 1, 0), 90))
    other = wood(document, "T", (720, 500, 19), far)
    document.recompute()
    second = api.make_shelf_pins(other)
    assert (second.Pitch.Value, second.HoleDiameter.Value) == (64.0, 6.0)
    reglages.reset_all()
    assert first.Pitch.Value == 32.0 and second.Pitch.Value == 64.0  # rien n'est relu


def test_prefixe_des_reperes_de_l_atelier(document: Any, reglages: Any) -> None:
    reglages.set(config.MARK_PREFIX, "P")
    part = api.make_wood_part(800, 100, 22, "chene", doc=document)
    assert api.number_marks(document) == {part.Name: "P1"}
    reglages.set(config.MARK_PREFIX, "Z")
    assert part.Mark == "P1"
    other = api.make_wood_part(500, 100, 22, "chene", doc=document)
    assert api.number_marks(document, prefix="Q") == {other.Name: "Q1"}
