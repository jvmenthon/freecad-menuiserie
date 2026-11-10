# SPDX-License-Identifier: LGPL-2.1-or-later
"""Critère de l'assemblage vers l'extérieur (M1) : cas limites du module pur."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.assembly_scope import keeps_assembly, nearest_common


def test_ensemble_commun_le_plus_proche() -> None:
    assert nearest_common(["S", "A"], ["A"]) == "A"
    assert nearest_common(["S", "A"], ["T", "S", "A"]) == "S"
    assert nearest_common(["A"], ["B"]) is None
    assert nearest_common([], ["A"]) is None


@pytest.mark.parametrize(
    ("moved", "other", "expected"),
    [
        (["S", "A"], ["A"], True),  # rangée dans un sous-ensemble de l'ensemble de l'autre
        (["A"], ["S", "A"], True),  # rangée dans l'ensemble qui contient l'autre
        (["B"], ["A"], False),  # ensembles différents
        (["B"], [], False),  # l'autre est hors ensemble
        ([], ["A"], False),  # la pièce sort, l'autre reste
        ([], [], True),  # toutes deux hors ensemble
    ],
)
def test_assemblage_garde_ou_non_un_ensemble_commun(
    moved: list[str], other: list[str], expected: bool
) -> None:
    assert keeps_assembly(moved, other) is expected
