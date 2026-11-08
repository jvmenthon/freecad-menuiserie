# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition en Python pur (lot R-a, critères R1 à R6 de ``docs/specs/repetition.md``)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.repeat import (
    MAX_COPIES,
    RepeatAxis,
    RepeatError,
    RepeatMode,
    RepeatParams,
    Resolved,
    SpacingMode,
    offsets,
    overlaps,
    resolve,
)

EXTENT = 40.0  # tasseau de 40 mm le long de l'axe


def linear(**changes: object) -> RepeatParams:
    return replace(RepeatParams(count=5, step=100.0), **changes)  # type: ignore[arg-type]


def test_stable_enum_values() -> None:
    assert [mode.value for mode in RepeatMode] == ["Linear", "Circular", "Path"]
    assert [spacing.value for spacing in SpacingMode] == [
        "CountAndStep",
        "CountOnSpan",
        "StepOnSpan",
    ]
    assert [axis.value for axis in RepeatAxis] == ["X", "Y", "Z"]
    assert MAX_COPIES == 100


def test_r1_count_and_step() -> None:
    params = linear()
    assert resolve(params, EXTENT) == Resolved(5, 100.0)
    assert offsets(params, EXTENT) == tuple(Vec3(k * 100.0, 0.0, 0.0) for k in range(1, 6))


@pytest.mark.parametrize(
    ("axis", "expected"),
    [
        (RepeatAxis.X, Vec3(100.0, 0.0, 0.0)),
        (RepeatAxis.Y, Vec3(0.0, 100.0, 0.0)),
        (RepeatAxis.Z, Vec3(0.0, 0.0, 100.0)),
    ],
)
def test_r1_axis(axis: RepeatAxis, expected: Vec3) -> None:
    assert offsets(linear(axis=axis, count=1), EXTENT) == (expected,)


def test_r2_count_on_span() -> None:
    params = linear(spacing=SpacingMode.COUNT_ON_SPAN, count=4, span=240.0)
    assert resolve(params, EXTENT) == Resolved(4, 50.0)  # (240 - 40) / 4
    assert [v.x for v in offsets(params, EXTENT)] == [50.0, 100.0, 150.0, 200.0]


@pytest.mark.parametrize("span", [EXTENT, EXTENT - 1.0])
def test_r2_count_on_span_refused_without_room(span: float) -> None:
    with pytest.raises(RepeatError, match="ne laisse pas de place"):
        resolve(linear(spacing=SpacingMode.COUNT_ON_SPAN, count=3, span=span), EXTENT)


def test_r3_step_on_span() -> None:
    params = linear(spacing=SpacingMode.STEP_ON_SPAN, step=60.0, span=400.0)
    assert resolve(params, EXTENT) == Resolved(6, 60.0)  # floor(360 / 60)
    assert [v.x for v in offsets(params, EXTENT)][-1] == 360.0


def test_r3_step_on_span_floors() -> None:
    params = linear(spacing=SpacingMode.STEP_ON_SPAN, step=70.0, span=400.0)
    assert resolve(params, EXTENT).count == 5  # 360 / 70 = 5,14


def test_r3_step_on_span_tolerates_float_error() -> None:
    # (0,3 - 0,0) / 0,1 vaut 2,9999999999999996 en flottant : 3 copies attendues.
    params = linear(spacing=SpacingMode.STEP_ON_SPAN, step=0.1, span=0.3 + 40.0)
    assert resolve(params, EXTENT).count == 3


def test_r3_step_on_span_refused_when_no_copy_fits() -> None:
    params = linear(spacing=SpacingMode.STEP_ON_SPAN, step=100.0, span=EXTENT + 99.0)
    with pytest.raises(RepeatError, match="aucune copie"):
        resolve(params, EXTENT)


def test_r3_step_on_span_at_the_cap() -> None:
    at_cap = linear(spacing=SpacingMode.STEP_ON_SPAN, step=10.0, span=EXTENT + 1000.0)
    assert resolve(at_cap, EXTENT).count == MAX_COPIES
    over = linear(spacing=SpacingMode.STEP_ON_SPAN, step=10.0, span=EXTENT + 1010.0)
    with pytest.raises(RepeatError, match="maximum est 100"):
        resolve(over, EXTENT)


@pytest.mark.parametrize("count", [0, -1, MAX_COPIES + 1, 2.5, True, "3", None])
def test_r4_count_refused(count: object) -> None:
    with pytest.raises(RepeatError, match="nombre entier de 1 à 100"):
        linear(count=count)


@pytest.mark.parametrize("count", [1, MAX_COPIES])
def test_r4_count_bounds_accepted(count: int) -> None:
    assert len(offsets(linear(count=count), EXTENT)) == count


@pytest.mark.parametrize("step", [0.0, -5.0, math.nan, math.inf, -math.inf, "10", None, True])
def test_r4_step_refused(step: object) -> None:
    with pytest.raises(RepeatError, match="supérieur à 0"):
        linear(step=step)


@pytest.mark.parametrize("span", [0.0, -5.0, math.nan, math.inf])
@pytest.mark.parametrize("spacing", [SpacingMode.COUNT_ON_SPAN, SpacingMode.STEP_ON_SPAN])
def test_r4_span_refused_when_used(spacing: SpacingMode, span: float) -> None:
    with pytest.raises(RepeatError, match="longueur"):
        linear(spacing=spacing, span=span)


def test_r4_unused_fields_are_not_checked() -> None:
    RepeatParams(spacing=SpacingMode.COUNT_ON_SPAN, count=3, span=100.0, step=0.0)
    RepeatParams(spacing=SpacingMode.STEP_ON_SPAN, count=0, step=10.0, span=100.0)
    RepeatParams(spacing=SpacingMode.COUNT_AND_STEP, count=3, step=10.0, span=-1.0)


@pytest.mark.parametrize("extent", [0.0, -1.0, math.nan, math.inf])
def test_r4_extent_refused(extent: float) -> None:
    with pytest.raises(RepeatError, match="cote de la pièce"):
        resolve(linear(), extent)


@pytest.mark.parametrize("mode", [RepeatMode.CIRCULAR, RepeatMode.PATH])
def test_reserved_modes_are_refused(mode: RepeatMode) -> None:
    with pytest.raises(RepeatError, match="pas encore disponible") as error:
        RepeatParams(mode=mode)
    assert error.value.params["value"] == mode.value


@pytest.mark.parametrize("field", ["mode", "spacing", "axis"])
def test_unknown_enum_value_is_refused(field: str) -> None:
    with pytest.raises(RepeatError, match="inconnu"):
        RepeatParams(**{field: "Spirale"})  # type: ignore[arg-type]


def test_enums_accept_their_stable_text() -> None:
    params = RepeatParams(mode="Linear", spacing="CountOnSpan", axis="Z", span=200.0)  # type: ignore[arg-type]
    assert (params.mode, params.spacing, params.axis) == (
        RepeatMode.LINEAR,
        SpacingMode.COUNT_ON_SPAN,
        RepeatAxis.Z,
    )


def test_defaults() -> None:
    params = RepeatParams()
    assert params.copy_joints is True
    assert params.follow_resize is False
    assert params.reverse is False


def test_r5_overlap_flagged() -> None:
    assert overlaps(Resolved(3, 30.0), EXTENT)
    assert overlaps(Resolved(3, EXTENT - 0.02), EXTENT)


@pytest.mark.parametrize("step", [EXTENT - 0.01, EXTENT, EXTENT + 10.0])
def test_r5_no_overlap_at_or_above_the_tolerance(step: float) -> None:
    assert not overlaps(Resolved(3, step), EXTENT)


def test_r5_overlap_does_not_block() -> None:
    params = linear(step=10.0)
    resolved = resolve(params, EXTENT)
    assert overlaps(resolved, EXTENT)
    assert len(offsets(params, EXTENT)) == 5


def test_r6_reverse() -> None:
    forward = offsets(linear(axis=RepeatAxis.Y), EXTENT)
    backward = offsets(linear(axis=RepeatAxis.Y, reverse=True), EXTENT)
    assert [-v.y for v in backward] == [v.y for v in forward]
    assert all(v.x == 0.0 and v.z == 0.0 for v in backward)
    assert backward[0] == Vec3(0.0, -100.0, 0.0)


def test_params_are_frozen() -> None:
    with pytest.raises(AttributeError):
        linear().count = 3  # type: ignore[misc]
