# SPDX-License-Identifier: LGPL-2.1-or-later
"""Citation sûre d'un texte venu d'un fichier (``core.text``, utilisée par la vue rapport)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core import text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("chene", "chene"),
        ("ligne\nsuivante", "ligne\\nsuivante"),
        ("‮enilno", "\\u202eenilno"),
        ("é" * 32, "é" * 32),
        ("x" * 33, "x" * 32 + "…"),
        (12, "12"),
        (None, "None"),
    ],
)
def test_quoted_value(value: object, expected: str) -> None:
    assert text.quoted_value(value) == expected


def test_quoted_value_tronque_avant_d_echapper() -> None:
    quoted = text.quoted_value("\n" * 2_000_000)
    assert quoted == "\\n" * text.MAX_QUOTED_LENGTH + "…"


def test_quoted_value_entier_trop_long() -> None:
    assert text.quoted_value(10**5000) == "?"


class _BrokenRepr:
    def __repr__(self) -> str:
        raise RuntimeError("repr")


def test_quoted_value_ne_rattrape_que_value_error() -> None:
    with pytest.raises(RuntimeError):
        text.quoted_value(_BrokenRepr())


def test_api_publique() -> None:
    assert text.__all__ == ["MAX_QUOTED_LENGTH", "quoted_value"]
