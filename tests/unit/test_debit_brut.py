# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur de débit arrondie au brut standard (J2, § 10.4, critère B2, ADR 0014)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.cutlist import (
    MIN_PLANING_MM,
    NO_ADDITIONS,
    CutEntry,
    CutNoticeKind,
    InvalidCutEntryError,
    build_cut_list,
)
from freecad.menuiserie.core.part_model import Allowances
from tests.unit.aides_debit import entry, plywood, record

OAK = (27.0, 34.0, 41.0, 54.0, 65.0, 80.0, 100.0)
PINE = (18.0, 22.0, 27.0, 32.0, 38.0, 50.0, 63.0, 75.0, 100.0)
NO_ALLOWANCE = Allowances()


def solid(
    thickness: float,
    rough: tuple[float, ...] = OAK,
    *,
    allowances: Allowances = NO_ALLOWANCE,
    additions: Allowances = NO_ADDITIONS,
) -> CutEntry:
    part = record("M1", (800.0, 100.0, thickness), allowances=allowances)
    return CutEntry(part, 1, additions, rough_thicknesses=rough)


def rough_thickness(entry_: CutEntry) -> float:
    return entry_.rough.thickness


@pytest.mark.parametrize(
    ("finished", "expected"),
    [(18, 27), (22, 27), (23, 27), (24, 27), (25, 34), (27, 34), (31, 34), (34, 41), (97, 100)],
)
def test_chene_arrondi_au_brut_superieur(finished: float, expected: float) -> None:
    assert rough_thickness(solid(finished)) == expected


def test_exemples_resineux() -> None:
    assert rough_thickness(solid(18, PINE)) == 22.0
    assert rough_thickness(solid(19, PINE)) == 22.0
    assert rough_thickness(solid(20, PINE)) == 27.0


def test_marge_de_rabotage_exacte_acceptee() -> None:
    assert MIN_PLANING_MM == 3.0
    assert rough_thickness(solid(24)) == 27.0  # 24 + 3 = 27 pile
    assert rough_thickness(solid(24.1)) == 34.0


def test_surcote_plus_grande_que_la_marge_prise_telle_quelle() -> None:
    assert rough_thickness(solid(18, allowances=Allowances(0.0, 0.0, 10.0))) == 34.0  # 28
    assert rough_thickness(solid(18, allowances=Allowances(0.0, 0.0, 9.0))) == 27.0  # 27 pile


def test_ajout_d_epaisseur_plus_grand_que_la_marge() -> None:
    assert rough_thickness(solid(18, additions=Allowances(0.0, 0.0, 10.0))) == 34.0
    # surcote et ajout s'additionnent avant la comparaison à la marge : 18 + 11 = 29 -> 34
    both = solid(18, allowances=Allowances(0.0, 0.0, 6.0), additions=Allowances(0.0, 0.0, 5.0))
    assert rough_thickness(both) == 34.0


def test_longueur_et_largeur_inchangees() -> None:
    standard = solid(18, allowances=Allowances(20.0, 5.0, 0.0))
    plain = solid(18, rough=(), allowances=Allowances(20.0, 5.0, 0.0))
    assert (standard.rough.length, standard.rough.width) == (plain.rough.length, plain.rough.width)
    assert plain.rough.thickness == 18.0


def test_sans_epaisseurs_de_brut_calcul_inchange() -> None:
    assert rough_thickness(solid(18, rough=())) == 18.0
    assert rough_thickness(entry()) == 22.0
    assert rough_thickness(plywood()) == 18.0
    assert not solid(18, rough=()).over_standard


def test_au_dela_du_plus_gros_brut_epaisseur_demandee_et_avertissement() -> None:
    over = solid(98)
    assert over.over_standard
    assert rough_thickness(over) == 101.0
    over_with_allowance = solid(100, allowances=Allowances(0.0, 0.0, 5.0))
    assert rough_thickness(over_with_allowance) == 105.0
    result = build_cut_list([over])
    (warning,) = result.warnings
    assert warning.kind is CutNoticeKind.ROUGH_THICKNESS_OVER_STANDARD
    assert warning.params == {"thickness": "101", "material": "Chene"}
    assert warning.message == (
        "Épaisseur de débit de 101 mm au-delà des épaisseurs de brut du Chene : "
        "à commander ou à contrecoller."
    )


def test_un_avertissement_par_ligne() -> None:
    first = solid(98)
    second = CutEntry(
        record("M2", (500.0, 100.0, 98.0), allowances=NO_ALLOWANCE), rough_thicknesses=OAK
    )
    twin = CutEntry(first.record, 2, rough_thicknesses=OAK)
    result = build_cut_list([first, second, twin, solid(18)])
    assert len(result.lines) == 3
    kinds = [w.kind for w in result.warnings]
    assert kinds.count(CutNoticeKind.ROUGH_THICKNESS_OVER_STANDARD) == 2


def test_volume_masse_surface_et_totaux_suivent_le_brut() -> None:
    result = build_cut_list([solid(18)])
    (line,) = result.lines
    assert line.rough.thickness == 27.0
    assert line.volume_m3(rough=True) == pytest.approx(800 * 100 * 27 / 1e9)
    assert line.mass_kg(rough=True) == pytest.approx(800 * 100 * 27 / 1e9 * line.density)
    (total,) = result.totals
    assert total.thickness == 27.0
    assert total.volume_m3 == pytest.approx(line.volume_m3(rough=True))


def test_totaux_par_epaisseur_de_plot() -> None:
    result = build_cut_list([solid(18), solid(22), solid(25)])
    assert [(t.thickness, t.quantity) for t in result.totals] == [(27.0, 2), (34.0, 1)]


def test_regroupement_des_pieces_identiques_conserve() -> None:
    result = build_cut_list([solid(18), solid(18), solid(18, rough=())])
    assert sorted(line.quantity for line in result.lines) == [1, 2]


def test_epaisseurs_de_brut_normalisees_et_validees() -> None:
    assert solid(18, rough=(34.0, 27.0, 27.0)).rough_thicknesses == (27.0, 34.0)
    for bad in ((0.0,), (-1.0,), (301.0,), "27", None, (27.0, "x")):
        with pytest.raises(InvalidCutEntryError, match="épaisseurs de brut"):
            solid(18, rough=bad)  # type: ignore[arg-type]
