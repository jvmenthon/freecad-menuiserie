# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD, Qt et chaîne d'ensembles simulés pour exercer ``gui/click_select.py`` sans écran
(ADR 0047). Le module est chargé depuis son fichier, ses dépendances de ``gui/`` et de
``features/`` sont remplacées : seule la logique du filtre est réelle."""

from __future__ import annotations

import importlib.util
import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tests.unit.aides import ROOT

MODULE = ROOT / "freecad" / "menuiserie" / "gui" / "click_select.py"
PRESS, RELEASE, DOUBLE = 2, 3, 4  # types d'évènements de souris (valeurs sans importance)
LEFT, RIGHT, NO_MODIFIER, CONTROL = 1, 2, 0, 0x04000000


class Point:
    """``QPointF`` minimal (le constructeur de copie est celui de Qt)."""

    def __init__(self, x: float = 0, y: float = 0) -> None:
        self._x, self._y = x, y

    @classmethod
    def copy(cls, other: Point) -> Point:
        return cls(other._x, other._y)

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y

    def __sub__(self, other: Point) -> Point:
        return Point(self._x - other._x, self._y - other._y)


class Event:
    """Évènement de souris simulé (API Qt 6)."""

    def __init__(
        self, kind: int, x: float = 10, y: float = 10, button: int = LEFT, modifiers: int = 0
    ) -> None:
        self._kind, self._point, self._button, self._modifiers = (
            kind,
            Point(x, y),
            button,
            modifiers,
        )

    def type(self) -> int:
        return self._kind

    def button(self) -> int:
        return self._button

    def modifiers(self) -> int:
        return self._modifiers

    def position(self) -> Point:
        return self._point


class Obj:
    """Objet de document simulé ; ``delete()`` le détache du document et rend ses attributs
    inaccessibles (``ReferenceError``, comme un objet FreeCAD supprimé)."""

    def __init__(self, document: Doc, name: str) -> None:
        self.document: Doc | None = document
        self.dead = False
        self._name = name
        self.parent_group: Obj | None = None
        document.objects[name] = self

    @property
    def Name(self) -> str:  # pylint: disable=invalid-name
        if self.dead:
            raise ReferenceError("Cannot access attribute of deleted object")
        return self._name

    Label = Name

    @property
    def Document(self) -> Doc | None:  # pylint: disable=invalid-name
        return None if self.dead else self.document

    def getParentGeoFeatureGroup(self) -> Obj | None:  # pylint: disable=invalid-name
        return self.parent_group

    def delete(self) -> None:
        """Supprimé : ``Document`` vaut ``None`` (comme ``obj.Document`` d'un objet retiré)."""
        assert self.document is not None
        del self.document.objects[self._name]
        self.document = None

    def invalidate(self) -> None:
        """Objet C++ détruit : tout accès lève ``ReferenceError``."""
        self.dead = True


class Doc:
    def __init__(self) -> None:
        self.Name = "Doc"
        self.objects: dict[str, Obj] = {}

    def getObject(self, name: str) -> Obj | None:
        return self.objects.get(name)


class World:
    """État partagé des faux modules : sélection, panneau, instant, minuteries, rapport."""

    def __init__(self) -> None:
        self.doc = Doc()
        self.selection: list[Obj] = []
        self.dialog = False
        self.now = 1000
        self.timers: list[Any] = []
        self.errors: list[str] = []
        self.chains: dict[str, list[str]] = {}
        self.pick: str | None = None  # nom de l'objet sous le curseur
        self.pick_error: Exception | None = None
        self.session: Any = None
        self.module: Any = None

    def obj(self, name: str) -> Obj:
        return Obj(self.doc, name)

    def link(self, *names: str) -> list[Obj]:
        """Déclare la chaîne ``names`` (ensemble de plus haut niveau d'abord, pièce en dernier)
        et la donne pour chacun de ses éléments (sauf le premier : la chaîne d'un ensemble de
        plus haut niveau est vide, comme ``chain_of``)."""
        objs = [self.doc.objects.get(n) or self.obj(n) for n in names]
        for i in range(1, len(names)):
            self.chains[names[i]] = list(names[: i + 1])
        return objs

    def selected(self) -> list[str]:
        return [o.Name for o in self.selection]

    def flush(self) -> None:
        """Exécute les minuteries à zéro en attente (après la sélection native)."""
        pending, self.timers = self.timers, []
        for callback in pending:
            callback()

    def filter(self) -> Any:
        return self.module._ClickFilter()  # pylint: disable=protected-access

    def view(self) -> Any:
        world = self

        class View:
            @staticmethod
            def getObjectInfo(_point: tuple[int, int]) -> dict[str, str] | None:
                if world.pick_error is not None:
                    raise world.pick_error
                if world.pick is None:
                    return None
                return {"Document": world.doc.Name, "Object": world.pick}

        return View()


def _QPointF(x: float | Point = 0, y: float = 0) -> Point:  # pylint: disable=invalid-name
    return Point.copy(x) if isinstance(x, Point) else Point(x, y)


def _module(name: str, **attrs: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    return module


@contextmanager
def simulated_click_select(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    """Charge ``click_select`` avec FreeCAD, Qt et la chaîne d'ensembles simulés."""
    world = World()
    quit_ = types.SimpleNamespace

    class QObject:
        def __init__(self) -> None:
            pass

    class QTimer:
        @staticmethod
        def singleShot(_ms: int, callback: Any) -> None:
            world.timers.append(callback)

    class QDateTime:
        @staticmethod
        def currentMSecsSinceEpoch() -> int:
            return world.now

    qt_core = _module(
        "QtCore",
        QObject=QObject,
        QTimer=QTimer,
        QDateTime=QDateTime,
        QPointF=_QPointF,
        QEvent=quit_(
            MouseButtonPress=PRESS, MouseButtonRelease=RELEASE, MouseButtonDblClick=DOUBLE
        ),
        Qt=quit_(LeftButton=LEFT, NoModifier=NO_MODIFIER),
    )
    qt_gui = _module("QtGui", QApplication=quit_(doubleClickInterval=lambda: 400))
    pyside = _module("PySide", QtCore=qt_core, QtGui=qt_gui)

    def get_selection() -> list[Obj]:
        return list(world.selection)

    def add_selection(_doc: str, name: str, *_path: str) -> None:
        world.selection.append(world.doc.objects[name])

    gui = _module(
        "FreeCADGui",
        Selection=quit_(
            getSelection=get_selection,
            clearSelection=world.selection.clear,
            addSelection=add_selection,
        ),
        Control=quit_(activeDialog=lambda: world.dialog),
        activeView=world.view,
    )
    app = _module(
        "FreeCAD",
        listDocuments=lambda: {world.doc.Name: world.doc},
        Console=quit_(PrintLog=lambda _m: None, PrintError=world.errors.append),
    )

    def chain_of(obj: Obj) -> list[Obj]:
        return [world.doc.objects[n] for n in world.chains.get(obj.Name, [])]

    class Installation:
        def __init__(self, factory: Any) -> None:
            self.filter = None
            self.factory = factory

    stubs = {
        "FreeCAD": app,
        "FreeCADGui": gui,
        "PySide": pyside,
        "freecad.menuiserie.features.freecad_types": _module("freecad_types", DocumentObject=Obj),
        "freecad.menuiserie.features.selection_chain": _module(
            "selection_chain", chain_of=chain_of, normalized=lambda obj: obj
        ),
        "freecad.menuiserie.gui.double_click": _module(
            "double_click",
            Installation=Installation,
            is_viewport_3d=lambda _w: True,
            view_point=lambda _w, x, y: (int(x), int(y)),
        ),
        "freecad.menuiserie.gui.drag.events": _module(
            "events", current_session=lambda: world.session
        ),
    }
    for key, value in stubs.items():
        monkeypatch.setitem(sys.modules, key, value)
    spec = importlib.util.spec_from_file_location("click_select_sous_test", Path(MODULE))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "click_select_sous_test", module)
    spec.loader.exec_module(module)
    world.module = module
    yield world
