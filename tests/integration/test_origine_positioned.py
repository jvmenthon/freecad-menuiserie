# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD 1.1 : les plans et axes d'origine (``App::Plane``, ``App::Line``) ne sont pas des objets
à repositionner (``positioned``) et ``_kept_places`` ne les retient jamais."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
entry = pytest.importorskip("freecad.menuiserie.features.furniture_entry")


def test_origine_d_un_std_part_non_positionnee(document: Any) -> None:
    part = document.addObject("App::Part", "Part")
    document.recompute()
    features = list(part.Origin.OriginFeatures)
    assert features
    for feature in features:
        assert feature.TypeId in {"App::Plane", "App::Line", "App::Point"}
        assert not entry.positioned(feature), feature.Name
    assert not entry.positioned(part.Origin)
    kept = entry._kept_places(document)  # pylint: disable=protected-access
    assert not {f.Name for f in features} & set(kept)
    assert part.Name in kept
