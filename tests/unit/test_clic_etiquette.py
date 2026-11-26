# SPDX-License-Identifier: LGPL-2.1-or-later
"""Clic sur l'étiquette d'une cote (ADR 0068, point 5) : états ``Idle`` et ``BadgePressed`` de
``gui.drag.states`` (FreeCAD et PySide remplacés par des doublures le temps de l'import), avec
une session factice qui note ce qu'on lui demande."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.unit.aides_freecad import imported_with_stubs

_STUBS = ("FreeCAD", "FreeCAD.Base", "FreeCADGui", "PySide", "Part", "pivy", "pivy.coin")
KEY = "handle0e"


@pytest.fixture(scope="module")
def states() -> Iterator[Any]:
    stubs = {name: MagicMock() for name in _STUBS}
    with imported_with_stubs("freecad.menuiserie.gui.drag.states", stubs) as module:
        yield module


class FakeSession:
    """Session réduite : cible et étiquette sous la souris fixées, appels notés."""

    def __init__(self, states: Any, *, badge: bool = True, begins: bool = True) -> None:
        self.state: Any = states.Idle()
        self.swallow_release = False
        self.badge = badge
        self.begins = begins
        self.calls: list[tuple[Any, ...]] = []

    def sync(self) -> None:
        self.calls.append(("sync",))

    def target_at(self, point: Any) -> str:
        del point
        return KEY

    def on_badge(self, point: Any, key: str) -> bool:
        del point, key
        return self.badge

    def enter(self, state: Any) -> None:
        self.state = state

    def begin(self, key: str, point: Any, shift: bool) -> bool:
        self.calls.append(("begin", key, point, shift))
        return self.begins

    def begin_copy(self, key: str, point: Any, shift: bool) -> bool:
        self.calls.append(("copy", key, point, shift))
        return True

    def move(self, point: Any, shift: bool) -> bool:
        self.calls.append(("move", point, shift))
        return True

    def edit_size(self, key: str) -> bool:
        self.calls.append(("edit", key))
        return True


def names(session: FakeSession) -> list[Any]:
    return [call[0] for call in session.calls if call[0] != "sync"]


def test_clic_sur_place_ouvre_le_champ_sans_rien_tirer(states: Any) -> None:
    session = FakeSession(states)
    assert session.state.press(session, (100, 100), False) is True
    assert type(session.state).__name__ == "BadgePressed" and session.state.dragging
    assert session.state.move(session, (102, 102), False) is True  # moins de 4 pixels
    assert names(session) == []
    assert session.state.release(session, (102, 102)) is True
    assert ("edit", KEY) in session.calls and "begin" not in names(session)
    assert type(session.state).__name__ == "Hover" and session.state.key == KEY


def test_glisser_depuis_l_etiquette_tire_la_poignee(states: Any) -> None:
    session = FakeSession(states)
    session.state.press(session, (100, 100), True)
    session.state.move(session, (110, 100), False)
    assert session.calls[1:] == [("begin", KEY, (100, 100), True), ("move", (110, 100), False)]
    assert not session.swallow_release


def test_poignee_non_saisie_au_glissement(states: Any) -> None:
    session = FakeSession(states, begins=False)
    session.state.press(session, (100, 100), False)
    assert session.state.move(session, (100, 120), False) is True
    assert session.swallow_release and "move" not in names(session)


def test_echap_pendant_le_clic(states: Any) -> None:
    session = FakeSession(states)
    session.state.press(session, (100, 100), False)
    assert session.state.escape(session) is True
    assert session.swallow_release and type(session.state).__name__ == "Idle"
    assert names(session) == []


def test_rond_et_copie_tirent_aussitot(states: Any) -> None:
    session = FakeSession(states, badge=False)  # le rond ou le trait : la poignée tout de suite
    session.state.press(session, (100, 100), False)
    assert names(session) == ["begin"]
    session = FakeSession(states)
    session.state.press(session, (100, 100), False, True)  # Ctrl : copie, même sur l'étiquette
    assert names(session) == ["copy"]
