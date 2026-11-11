# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aides des tests d'intégration de la répétition en grille (ADR 0045)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

api = pytest.importorskip("freecad.menuiserie.api")

Reopen = Callable[[Any], Any]
X, Y, Z = api.RepeatAxis.X, api.RepeatAxis.Y, api.RepeatAxis.Z
Line = api.AxisRepeat


def grid(*lines: Any, **values: Any) -> Any:
    """Paramètres d'une grille : une ligne par axe, mêmes réglages communs."""
    return api.RepeatParams(grid=lines, **values)
