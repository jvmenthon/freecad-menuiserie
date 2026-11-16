# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sources d'une répétition et liaisons des copies de pièces en bois (ADR 0050, critère S1), sans
FreeCAD."""

from __future__ import annotations

import types
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie.core.repeat import RepeatAxis
from tests.unit.aides_freecad import simulated_freecad

SHIFT = {RepeatAxis.Y: "2 * (Repeat.Reverse ? -1 : 1) * Repeat.Step"}
DIMENSIONS = {"Length", "Width", "Thickness"}


@pytest.fixture
def modules(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.SimpleNamespace]:
    """Modules de la répétition sur un FreeCAD simulé."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import (
            repeat,
            repeat_furniture_links,
            repeat_links,
            repeat_sources,
            shaped_create,
            shaped_part,
            wood_part,
        )

        yield types.SimpleNamespace(
            repeat=repeat,
            furniture_links=repeat_furniture_links,
            links=repeat_links,
            sources=repeat_sources,
            create=shaped_create,
            shaped=shaped_part,
            wood=wood_part,
        )


def timber(kind: Any, **props: Any) -> Any:
    """Objet simulé dont le proxy est une instance de ``kind`` (sans appeler son ``__init__``)."""
    values = {
        "Label": "Pied",
        "Name": "ShapedPart",
        "PropertiesList": [],
        "Length": types.SimpleNamespace(Value=200.0),
        "Width": types.SimpleNamespace(Value=100.0),
        "Thickness": types.SimpleNamespace(Value=50.0),
        "MaterialId": "chene",
        **props,
    }
    return types.SimpleNamespace(Proxy=kind.__new__(kind), **values)


def test_s1_une_piece_en_bois_est_une_source_valide(modules: types.SimpleNamespace) -> None:
    modules.sources._checked_source(timber(modules.shaped.ShapedPart))
    modules.sources._checked_source(timber(modules.wood.WoodPart))


def test_s1_autre_chose_est_refuse(modules: types.SimpleNamespace) -> None:
    other = types.SimpleNamespace(Label="Corps", Proxy=None)
    with pytest.raises(TypeError, match="n'est pas une pièce de bois"):
        modules.sources._checked_source(other)


def test_s1_le_message_de_refus_ne_dit_plus_que_les_pieces_en_bois_sont_exclues(
    modules: types.SimpleNamespace,
) -> None:
    with pytest.raises(TypeError) as error:
        modules.sources._checked_source(types.SimpleNamespace(Label="Corps", Proxy=None))
    assert "pas les pièces en bois" not in str(error.value)


def test_s1_une_cote_nulle_est_refusee(modules: types.SimpleNamespace) -> None:
    part = timber(modules.shaped.ShapedPart, Length=types.SimpleNamespace(Value=0.0))
    with pytest.raises(ValueError, match="Cote invalide"):
        modules.sources._checked_source(part)


def test_les_cotes_d_une_piece_en_bois_ne_sont_jamais_liees(
    modules: types.SimpleNamespace,
) -> None:
    shaped = modules.links.cell_expressions("Pied", SHIFT, shaped=True)
    assert not DIMENSIONS & set(shaped)
    assert shaped["SourceAxes"] == "Pied.SourceAxes"
    assert shaped["ProfileThickness"] == "Pied.ProfileThickness"
    for name in ("Material", "GrainDirection", "LengthAllowance", "WidthAllowance"):
        assert shaped[name] == f"Pied.{name}"
    assert shaped["Placement.Base.y"].endswith(" + " + SHIFT[RepeatAxis.Y])
    assert shaped["Placement.Rotation"] == "Pied.Placement.Rotation"


def test_les_cotes_d_une_piece_de_bois_restent_liees(modules: types.SimpleNamespace) -> None:
    wood = modules.links.cell_expressions("Barre", SHIFT)
    assert set(wood) >= DIMENSIONS
    assert not {"SourceAxes", "ProfileThickness"} & set(wood)


def test_les_chemins_lies_couvrent_le_repere_et_l_epaisseur_de_profil(
    modules: types.SimpleNamespace,
) -> None:
    assert {"SourceAxes", "ProfileThickness"} <= set(modules.links.BOUND_PATHS)
    assert len(modules.links.BOUND_PATHS) == len(set(modules.links.BOUND_PATHS))


def test_les_copies_ne_comptent_pas_comme_conversion(modules: types.SimpleNamespace) -> None:
    body = types.SimpleNamespace(InList=[])
    free = timber(modules.shaped.ShapedPart, Source=body)
    body.InList.append(free)
    assert modules.create.converted_part_of(body) is free
    body.InList.clear()
    repeat = types.SimpleNamespace(Proxy=modules.repeat.Repeat.__new__(modules.repeat.Repeat))
    linked = timber(
        modules.shaped.ShapedPart,
        Source=body,
        PropertiesList=["Repeat", "RepeatSource", "RepeatIndex"],
        Repeat=repeat,
    )
    body.InList.append(linked)
    assert modules.create.converted_part_of(body) is not linked
