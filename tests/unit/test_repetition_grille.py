# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition en grille X x Y x Z, en Python pur (ADR 0045, spécification § Grille)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.repeat import (
    MAX_COPIES,
    ORIGIN,
    AxisRepeat,
    RepeatAxis,
    RepeatError,
    RepeatParams,
    SpacingMode,
    cell_offsets,
    cells_of,
    grid_overlaps,
    offsets,
    overlapping_axes,
    rank_of,
    resolve,
    resolve_grid,
)

X, Y, Z = RepeatAxis.X, RepeatAxis.Y, RepeatAxis.Z
EXTENT = 40.0


def grid(*lines: AxisRepeat, **changes: object) -> RepeatParams:
    return RepeatParams(grid=lines, **changes)  # type: ignore[arg-type]


def test_exemple_4_x_3_sur_x_et_y() -> None:
    """4 x 3, pas 100 mm sur X et 150 mm sur Y : 11 copies en plus de l'original."""
    params = grid(AxisRepeat(X, 4, 100.0), AxisRepeat(Y, 3, 150.0))
    resolved = resolve_grid(params, EXTENT)
    assert resolved.total == 11 and resolved.dims() == (4, 3, 1)
    found = offsets(params, EXTENT)
    assert len(found) == 11
    assert found[0] == Vec3(100.0, 0.0, 0.0) and found[-1] == Vec3(300.0, 300.0, 0.0)
    assert Vec3(0.0, 150.0, 0.0) in found and Vec3(0.0, 0.0, 0.0) not in found


def test_position_somme_des_axes() -> None:
    params = grid(AxisRepeat(X, 4, 100.0), AxisRepeat(Y, 3, 150.0, reverse=True))
    by_cell = cell_offsets(params, EXTENT)
    assert by_cell[(2, 1, 0)] == Vec3(200.0, -150.0, 0.0)  # i x pas x sens sur chaque axe
    assert by_cell[(0, 2, 0)] == Vec3(0.0, -300.0, 0.0)


def test_trois_axes() -> None:
    params = grid(AxisRepeat(Z, 2, 50.0), AxisRepeat(X, 3, 10.0), AxisRepeat(Y, 2, 20.0))
    assert [line.axis for line in params.lines] == [X, Y, Z]  # triées, quel que soit l'ordre donné
    resolved = resolve_grid(params, EXTENT)
    assert resolved.total == 11
    assert cell_offsets(params, EXTENT)[(2, 1, 1)] == Vec3(20.0, 20.0, 50.0)


def test_axe_de_nombre_1_inactif() -> None:
    params = grid(AxisRepeat(X, 3, 100.0), AxisRepeat(Y, 1, 150.0), AxisRepeat(Z, 1, 0.0))
    assert [line.axis for line in params.lines] == [X]
    assert params.axis is X and params.count == 2  # reflet de la première ligne, en copies
    assert resolve_grid(params, EXTENT).total == 2


def test_aucun_axe_actif_refuse() -> None:
    with pytest.raises(RepeatError, match="aucun axe n'est actif"):
        grid(AxisRepeat(X, 1), AxisRepeat(Y, 1))


def test_axe_donne_deux_fois_refuse() -> None:
    with pytest.raises(RepeatError, match="axe X est donné deux fois"):
        grid(AxisRepeat(X, 2), AxisRepeat(X, 3))


@pytest.mark.parametrize("count", [0, -1, MAX_COPIES + 2, 2.5, True, "3", None])
def test_nombre_d_un_axe_hors_bornes(count: object) -> None:
    with pytest.raises(RepeatError, match=r"entier de 1 \(axe inactif\) à 101"):
        grid(AxisRepeat(X, count))  # type: ignore[arg-type]


def test_pas_d_un_axe_actif_refuse_et_nomme_l_axe() -> None:
    with pytest.raises(RepeatError, match=r"pas \(axe Y\)"):
        grid(AxisRepeat(X, 2, 100.0), AxisRepeat(Y, 2, 0.0))
    grid(AxisRepeat(X, 2, 100.0), AxisRepeat(Y, 1, 0.0))  # axe inactif : non contrôlé


@pytest.mark.parametrize(
    ("lines", "copies"),
    [
        ((AxisRepeat(X, 101),), 100),
        ((AxisRepeat(X, 51), AxisRepeat(Y, 2)), None),  # 101 copies
        ((AxisRepeat(X, 10), AxisRepeat(Y, 10)), 99),
        ((AxisRepeat(X, 11), AxisRepeat(Y, 10)), None),  # 109 copies
        ((AxisRepeat(X, 5), AxisRepeat(Y, 5), AxisRepeat(Z, 5)), None),  # 124 copies
        ((AxisRepeat(X, 4), AxisRepeat(Y, 5), AxisRepeat(Z, 5)), 99),
    ],
)
def test_total_borne_par_le_maximum(lines: tuple[AxisRepeat, ...], copies: int | None) -> None:
    if copies is None:
        with pytest.raises(RepeatError, match="en plus de l'original ; le maximum est 100"):
            grid(*lines)
    else:
        assert resolve_grid(grid(*lines), EXTENT).total == copies


def test_message_de_refus_du_total_donne_les_nombres() -> None:
    with pytest.raises(RepeatError, match=r"11 x 10 donneraient 109 copies") as refused:
        grid(AxisRepeat(X, 11), AxisRepeat(Y, 10))
    assert refused.value.params["count"] == "109"


def test_nombre_sur_une_longueur_par_axe() -> None:
    params = grid(
        AxisRepeat(X, 4, span=340.0),
        AxisRepeat(Y, 3, span=140.0),
        spacing=SpacingMode.COUNT_ON_SPAN,
    )
    resolved = resolve_grid(params, {X: 40.0, Y: 40.0, Z: 40.0})
    assert [(a.axis, a.cells, a.step) for a in resolved.axes] == [(X, 4, 100.0), (Y, 3, 50.0)]


def test_nombre_sur_une_longueur_trop_courte_sur_un_axe() -> None:
    params = grid(
        AxisRepeat(X, 4, span=340.0),
        AxisRepeat(Y, 3, span=40.0),
        spacing=SpacingMode.COUNT_ON_SPAN,
    )
    with pytest.raises(RepeatError, match="ne laisse pas de place"):
        resolve_grid(params, EXTENT)


def test_pas_sur_une_longueur_par_axe_et_cotes_par_axe() -> None:
    params = grid(
        AxisRepeat(X, step=60.0, span=400.0),
        AxisRepeat(Y, step=30.0, span=130.0),
        spacing=SpacingMode.STEP_ON_SPAN,
    )
    resolved = resolve_grid(params, {X: 40.0, Y: 10.0, Z: 1.0})
    assert [(a.axis, a.cells) for a in resolved.axes] == [
        (X, 7),
        (Y, 5),
    ]  # floor(360/60), floor(120/30)
    assert resolved.total == 34


def test_pas_sur_une_longueur_total_borne() -> None:
    params = grid(
        AxisRepeat(X, step=10.0, span=EXTENT + 100.0),
        AxisRepeat(Y, step=10.0, span=EXTENT + 100.0),
        spacing=SpacingMode.STEP_ON_SPAN,
    )
    with pytest.raises(RepeatError, match="11 x 11 donneraient 120 copies"):
        resolve_grid(params, EXTENT)


def test_pas_sur_une_longueur_axe_sans_place() -> None:
    params = grid(
        AxisRepeat(X, step=60.0, span=400.0),
        AxisRepeat(Y, step=500.0, span=130.0),
        spacing=SpacingMode.STEP_ON_SPAN,
    )
    with pytest.raises(RepeatError, match="aucune copie"):
        resolve_grid(params, EXTENT)


def test_un_seul_axe_est_le_cas_particulier() -> None:
    """``axis=``, ``count=``… : une grille d'une seule ligne, mêmes décalages."""
    legacy = RepeatParams(count=3, step=70.0, axis=Y, reverse=True)
    explicit = grid(AxisRepeat(Y, 4, 70.0, reverse=True))
    assert legacy.lines == explicit.lines
    assert offsets(legacy, EXTENT) == offsets(explicit, EXTENT)
    assert resolve(explicit, EXTENT).count == 3


def test_replace_garde_la_grille() -> None:
    params = grid(AxisRepeat(X, 3, 100.0), AxisRepeat(Y, 2, 50.0))
    changed = replace(params, spacing=SpacingMode.COUNT_AND_STEP, copy_joints=False)
    assert changed.lines == params.lines and changed.copy_joints is False


def test_ordre_des_rangs_x_puis_y_puis_z() -> None:
    cells = cells_of((3, 2, 2))
    assert cells[:4] == ((1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0))
    assert ORIGIN not in cells and len(cells) == 11
    assert [rank_of(cell, (3, 2, 2)) for cell in cells] == list(range(1, 12))


def test_la_cellule_ne_change_pas_quand_le_nombre_change() -> None:
    """Identité par cellule : agrandir X laisse chaque cellule existante dans la grille, mais
    renumérote les rangs linéaires (affichage seulement)."""
    before, after = cells_of((4, 3, 1)), cells_of((5, 3, 1))
    assert set(before) <= set(after)
    assert rank_of((0, 1, 0), (4, 3, 1)) == 4 and rank_of((0, 1, 0), (5, 3, 1)) == 5
    assert rank_of((4, 0, 0), (4, 3, 1)) == 0  # hors grille : pas de rang
    assert rank_of(ORIGIN, (4, 3, 1)) == 0


def test_chevauchement_par_axe_puis_grille() -> None:
    params = grid(AxisRepeat(X, 3, 100.0), AxisRepeat(Y, 3, 20.0))
    resolved = resolve_grid(params, EXTENT)
    assert overlapping_axes(resolved, EXTENT) == (Y,)  # 20 mm < 40 mm
    assert grid_overlaps(resolved, EXTENT) is True
    clear = resolve_grid(grid(AxisRepeat(X, 3, 100.0), AxisRepeat(Y, 3, 50.0)), EXTENT)
    assert overlapping_axes(clear, EXTENT) == () and grid_overlaps(clear, EXTENT) is False


def test_chevauchement_tolerance_et_deux_axes() -> None:
    both = resolve_grid(grid(AxisRepeat(X, 2, 10.0), AxisRepeat(Y, 2, 10.0)), EXTENT)
    assert overlapping_axes(both, EXTENT) == (X, Y)
    exact = resolve_grid(grid(AxisRepeat(X, 2, EXTENT - 0.005), AxisRepeat(Y, 2, EXTENT)), EXTENT)
    assert overlapping_axes(exact, EXTENT) == () and grid_overlaps(exact, EXTENT) is False


def test_chevauchement_avec_cotes_differentes_par_axe() -> None:
    resolved = resolve_grid(grid(AxisRepeat(X, 2, 50.0), AxisRepeat(Y, 2, 50.0)), EXTENT)
    extents = {X: 40.0, Y: 60.0, Z: 5.0}
    assert overlapping_axes(resolved, extents) == (Y,)
    assert grid_overlaps(resolved, extents) is True


@pytest.mark.parametrize("extent", [0.0, -1.0, math.nan, math.inf])
def test_cote_refusee_pour_la_grille(extent: float) -> None:
    with pytest.raises(RepeatError, match="cote de la pièce"):
        resolve_grid(grid(AxisRepeat(X, 2, 10.0), AxisRepeat(Y, 2, 10.0)), extent)


def test_chevauchement_de_la_grille_ne_lit_que_les_axes_actifs() -> None:
    resolved = resolve_grid(grid(AxisRepeat(X, 2, 10.0), AxisRepeat(Y, 2, 10.0)), EXTENT)
    extents = {X: EXTENT, Y: EXTENT}  # pas de cote sur Z : axe inactif
    assert overlapping_axes(resolved, extents) == (X, Y) and grid_overlaps(resolved, extents)


def test_pas_de_chevauchement_en_diagonale_sans_chevauchement_par_axe() -> None:
    clear = resolve_grid(
        grid(AxisRepeat(X, 3, 45.0), AxisRepeat(Y, 3, 45.0), AxisRepeat(Z, 2, 45.0)), EXTENT
    )
    assert grid_overlaps(clear, EXTENT) is False and overlapping_axes(clear, EXTENT) == ()
