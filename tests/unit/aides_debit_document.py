# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets FreeCAD simulés pour tester ``features/cutlist_*`` sans FreeCAD (J2c).

Le vrai document (liens, Std Part, ensemble, forme usinée, feuille, réouverture) est vérifié par
``tests/integration/test_liste_de_debit*.py``.
"""

from __future__ import annotations

import types
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from tests.unit.aides_freecad import simulated_freecad

DIMENSION_PROPERTIES = ("Length", "Width", "Thickness")
ALLOWANCE_PROPERTIES = ("LengthAllowance", "WidthAllowance", "ThicknessAllowance")


class Obj:
    """Objet de document : propriétés dans un dictionnaire, comme un ``DocumentObject``."""

    def __init__(self, name: str, type_id: str = "", **props: Any) -> None:
        self.props: dict[str, Any] = {"Label": props.pop("Label", name), **props}
        self.Name = name
        self.TypeId = type_id
        self.State: list[str] = []
        self.InList: list[Obj] = []
        self.Document: Any = None

    @property
    def PropertiesList(self) -> list[str]:  # nom imposé par FreeCAD
        return list(self.props)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.__dict__["props"][name]
        except KeyError:
            raise AttributeError(name) from None


class Doc:
    """Document simulé : ses objets, et le rattachement de chacun à ce document."""

    def __init__(self, *objects: Obj) -> None:
        self.Objects = list(objects)
        for obj in objects:
            obj.Document = self


class Box:
    """Boîte englobante d'une forme simulée : (xmin, xmax, ymin, ymax, zmin, zmax)."""

    def __init__(self, bounds: tuple[float, ...]) -> None:
        names = ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
        self.__dict__.update(zip(names, bounds, strict=True))


class Shape:
    """Forme simulée : refaire le repère local rend la boîte donnée."""

    def __init__(self, bounds: tuple[float, ...], *, null: bool = False, valid: bool = True):
        self.Solids = [] if null else [object()]
        self.Placement = types.SimpleNamespace(
            inverse=lambda: types.SimpleNamespace(toMatrix=lambda: "local")
        )
        self._null, self._valid, self._bounds = null, valid, bounds

    def isNull(self) -> bool:
        return self._null

    def isValid(self) -> bool:
        return self._valid

    def transformed(self, matrix: str) -> Any:
        assert matrix == "local"
        return types.SimpleNamespace(BoundBox=Box(self._bounds))


class World:
    """Fabriques d'objets reconnus par ``features/`` (proxys sans objet), sur FreeCAD simulé."""

    def __init__(self, features: types.SimpleNamespace) -> None:
        self.features = features

    def _proxy(self, module: str, name: str) -> Any:
        cls = getattr(getattr(self.features, module), name)
        return cls.__new__(cls)

    def part(
        self,
        name: str,
        mark: str = "",
        size: tuple[float, float, float] = (800, 200, 22),
        **extra: Any,
    ) -> Obj:
        """Pièce de bois en chêne, sans surcote (``extra`` remplace des propriétés)."""
        props: dict[str, Any] = {
            "Mark": mark,
            "MaterialId": "chene",
            "Material": "Chêne",
            "Category": "Solid",
            "GrainDirection": "Length",
            "Density": types.SimpleNamespace(getValueAs=lambda _unit: 710.0),
            "Proxy": self._proxy("wood_part", "WoodPart"),
        }
        for prop, value in zip(DIMENSION_PROPERTIES, size, strict=True):
            props[prop] = types.SimpleNamespace(Value=float(value))
        for prop in ALLOWANCE_PROPERTIES:
            props[prop] = types.SimpleNamespace(Value=0.0)
        return Obj(name, "Part::FeaturePython", **{**props, **extra})

    def machined(self, name: str, blank: Obj, shape: Any) -> Obj:
        """Pièce usinée de ``blank`` (déclarée dans sa ``InList``), de forme ``shape``."""
        proxy = self._proxy("machined_part", "MachinedPart")
        obj = Obj(name, "Part::FeaturePython", Base=blank, Proxy=proxy, Shape=shape)
        blank.InList.append(obj)
        return obj

    def furniture(self, name: str, *members: Obj) -> Obj:
        """Ensemble et ses membres (lien ``Furniture`` et ``FurnitureBindings``)."""
        proxy = self._proxy("furniture", "Furniture")
        owner = Obj(name, "App::FeaturePython", Proxy=proxy)
        for member in members:
            member.props.update(Furniture=owner, FurnitureBindings=[])
            owner.InList.append(member)
        return owner


def link(name: str, target: Obj | None, count: int | None = None) -> Obj:
    """``App::Link`` vers ``target`` (tableau de ``count`` liens si ``count`` est donné)."""
    props: dict[str, Any] = {"LinkedObject": target}
    if count is not None:
        props["ElementCount"] = count
    return Obj(name, "App::Link", **props)


def group(name: str, *children: Obj, type_id: str = "App::Part") -> Obj:
    """Std Part ou groupe qui contient ``children``."""
    return Obj(name, type_id, Group=list(children))


@contextmanager
def simulated_world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    """Modules ``features`` de la liste de débit sur un FreeCAD simulé (traduction neutre)."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import (
            cutlist_collect,
            cutlist_export,
            cutlist_parts,
            cutlist_sheet,
            furniture,
            machined_part,
            wood_part,
        )

        yield World(
            types.SimpleNamespace(
                cutlist_collect=cutlist_collect,
                cutlist_export=cutlist_export,
                cutlist_parts=cutlist_parts,
                cutlist_sheet=cutlist_sheet,
                furniture=furniture,
                machined_part=machined_part,
                wood_part=wood_part,
            )
        )
