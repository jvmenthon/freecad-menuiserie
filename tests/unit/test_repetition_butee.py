# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition jusqu'à une butée, calcul pur (ADR 0047) : longueur, déduction, refus."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.repeat import (
    AxisRepeat,
    RepeatAxis,
    RepeatError,
    RepeatParams,
    SpacingMode,
    StopKind,
    farthest_axis,
    resolve,
    resolve_grid,
    stop_kind,
    stop_reverse,
    stop_span,
)

X = RepeatAxis.X
BOUNDS = (0.0, 30.0)  # sources de 30 mm sur X


def on_span(span: float, count: int = 4, **values: object) -> RepeatParams:
    line = AxisRepeat(X, count, span=span)
    return RepeatParams(spacing=SpacingMode.COUNT_ON_SPAN, grid=(line,), **values)  # type: ignore[arg-type]


def test_longueur_jusqu_a_la_butee() -> None:
    assert stop_span(BOUNDS, 300.0, X) == 300.0
    assert stop_span(BOUNDS, 300.0, X, deduct=False) == 300.0  # indépendante de la case


def test_sens_inverse_part_du_haut_des_sources() -> None:
    assert stop_span((470.0, 500.0), 130.0, X, reverse=True) == 370.0


def test_sens_deduit_de_la_butee() -> None:
    assert stop_reverse(BOUNDS, (300.0, 330.0)) is False  # butée après : sens normal
    assert stop_reverse(BOUNDS, (-130.0, -100.0)) is True  # butée avant : sens inverse
    assert stop_reverse((470.0, 500.0), (100.0, 130.0)) is True


@pytest.mark.parametrize("near", [0.0, -50.0])
def test_butee_derriere_l_original_refusee(near: float) -> None:
    with pytest.raises(RepeatError, match="chevauche") as error:
        stop_span(BOUNDS, near, X)
    assert error.value.params["axis"] == "X"
    with pytest.raises(RepeatError):
        stop_span(BOUNDS, near, X, deduct=False)


def test_butee_derriere_dans_le_sens_inverse() -> None:
    with pytest.raises(RepeatError):
        stop_span(BOUNDS, 40.0, X, reverse=True)


def test_butee_plus_proche_que_l_epaisseur() -> None:
    with pytest.raises(RepeatError) as error:
        stop_span(BOUNDS, 29.99, X)
    assert error.value.params["extent"] == "30"
    assert stop_span(BOUNDS, 30.0, X) == 30.0  # juste l'épaisseur : le calcul des copies décide
    assert stop_span(BOUNDS, 10.0, X, deduct=False) == 10.0  # sans déduction : permis


@pytest.mark.parametrize(
    ("sub", "kind"),
    [
        ("", StopKind.PART),
        ("Face3", StopKind.FACE),
        ("Edge7", StopKind.EDGE),
        ("Vertex12", StopKind.VERTEX),
    ],
)
def test_nature_de_la_butee(sub: str, kind: StopKind) -> None:
    assert stop_kind(sub) is kind


@pytest.mark.parametrize(
    "sub", ["Edge0", "Face", "Face0", "Face3.", "face3", "Vertex-1", "Solid1", "Wire1"]
)
def test_sous_element_ni_face_ni_sommet_refuse(sub: str) -> None:
    with pytest.raises(RepeatError, match="ni une face, ni une arête, ni un sommet"):
        stop_kind(sub)


def test_avec_deduction_la_derniere_copie_est_a_fleur() -> None:
    resolved = resolve(on_span(300.0), 30.0)
    assert (resolved.count, resolved.step) == (3, 90.0)
    assert 3 * resolved.step + 30.0 == 300.0  # copie de 30 mm : fin à la butée


def test_sans_deduction_la_derniere_copie_commence_a_la_butee() -> None:
    params = on_span(300.0, deduct_thickness=False)
    resolved = resolve(params, 30.0)
    assert (resolved.count, resolved.step) == (3, 100.0)
    assert 3 * resolved.step == 300.0  # copie de 30 mm : début à la butée
    assert resolve_grid(params, 30.0).axes[0].step == 100.0


def test_case_cochee_par_defaut() -> None:
    assert RepeatParams().deduct_thickness is True


def test_pas_sur_une_longueur_avec_et_sans_deduction() -> None:
    line = AxisRepeat(X, 2, step=50.0, span=300.0)
    deducted = RepeatParams(spacing=SpacingMode.STEP_ON_SPAN, grid=(line,))
    free = RepeatParams(spacing=SpacingMode.STEP_ON_SPAN, grid=(line,), deduct_thickness=False)
    assert resolve(deducted, 30.0).count == 5  # floor(270 / 50)
    assert resolve(free, 30.0).count == 6  # floor(300 / 50)


def test_sans_deduction_aucune_copie_ne_tient() -> None:
    line = AxisRepeat(X, 2, step=500.0, span=300.0)
    params = RepeatParams(spacing=SpacingMode.STEP_ON_SPAN, grid=(line,), deduct_thickness=False)
    with pytest.raises(RepeatError, match="épaisseur non déduite"):
        resolve(params, 30.0)


def test_axe_deduit_de_la_butee() -> None:
    sources = {X: (0.0, 30.0), RepeatAxis.Y: (0.0, 20.0), RepeatAxis.Z: (0.0, 10.0)}
    mur = {X: (300.0, 330.0), RepeatAxis.Y: (0.0, 20.0), RepeatAxis.Z: (0.0, 10.0)}
    assert farthest_axis(sources, mur) is X
    dessous = {X: (0.0, 30.0), RepeatAxis.Y: (-50.0, 70.0), RepeatAxis.Z: (-400.0, -380.0)}
    assert farthest_axis(sources, dessous) is RepeatAxis.Z  # côté négatif aussi
    cube = dict.fromkeys(RepeatAxis, (0.0, 10.0))
    assert farthest_axis(cube, dict.fromkeys(RepeatAxis, (20.0, 30.0))) is X  # à égalité : X
