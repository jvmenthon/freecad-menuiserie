# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce en bois et sélection d'un élément pour l'accrochage (D6, spec § 4.4 : ``is_timber`` pour
la sélection) : l'ensemble d'une face choisie est celui de la pièce, de bois ou en bois."""

from __future__ import annotations

import importlib
import types
from collections.abc import Iterator
from typing import Any

import pytest

from tests.unit.aides_freecad import simulated_freecad


@pytest.fixture
def modules(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.SimpleNamespace]:
    """Modules de la sélection, de l'ensemble et des deux pièces sur un FreeCAD simulé."""
    with simulated_freecad(monkeypatch):
        importlib.import_module("freecad.menuiserie.api")
        from freecad.menuiserie.features import furniture, picked, shaped_part, wood_part

        yield types.SimpleNamespace(
            furniture=furniture, picked=picked, shaped=shaped_part, wood=wood_part
        )


class FakeObject:
    """Objet du document simulé : type, proxy, propriétés d'appartenance à un ensemble."""

    def __init__(self, proxy: object, furniture: object | None = None) -> None:
        self.Proxy = proxy
        self.TypeId = "Part::FeaturePython"
        self.Furniture = furniture
        self.FurnitureBindings: list[str] = []
        self.PropertiesList = ["Furniture", "FurnitureBindings"]


class FakeRoot:
    """Racine de sélection : le chemin ne contient que ``owner``."""

    def __init__(self, owner: FakeObject) -> None:
        self.owner = owner

    def getSubObjectList(self, _subname: str) -> list[FakeObject]:  # nom imposé par FreeCAD
        return [self.owner]


def proxy_of(cls: type) -> Any:
    """Proxy sans objet (``__init__`` n'est pas rappelé à la réouverture)."""
    return cls.__new__(cls)


@pytest.mark.parametrize("kind", ["wood", "shaped"])
def test_ensemble_d_une_face_choisie_sur_un_membre(modules: Any, kind: str) -> None:
    ensemble = FakeObject(proxy_of(modules.furniture.Furniture))
    cls = modules.wood.WoodPart if kind == "wood" else modules.shaped.ShapedPart
    member = FakeObject(proxy_of(cls), ensemble)
    element = modules.picked.PickedElement(FakeRoot(member), "Face3")
    assert modules.picked.furniture_candidate(element) is ensemble


def test_pas_d_ensemble_pour_une_piece_en_bois_libre(modules: Any) -> None:
    member = FakeObject(proxy_of(modules.shaped.ShapedPart))
    element = modules.picked.PickedElement(FakeRoot(member), "Face3")
    assert modules.picked.furniture_candidate(element) is None
