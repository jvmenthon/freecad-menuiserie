# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit pure : regroupement, ordre, totaux, fournitures, validation (J2b, C1 à C6, C8)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.cutlist import (
    NO_ADDITIONS,
    CutEntry,
    CutNoticeKind,
    Hardware,
    HardwareKind,
    InvalidCutEntryError,
    build_cut_list,
)
from freecad.menuiserie.core.cutlist._build import natural_key
from freecad.menuiserie.core.materials import MaterialKind
from freecad.menuiserie.core.part_model import Allowances, GrainDirection
from tests.unit.aides_debit import entry, plywood, record

TENON = Allowances(60.0, 0.0, 0.0)


def marks(entries: list[CutEntry]) -> list[str]:
    return [line.mark for line in build_cut_list(entries).lines]


# --- C1 : regroupement et ordre -----------------------------------------------------------


def test_pieces_identiques_regroupees() -> None:
    result = build_cut_list([entry(quantity=1), entry(quantity=2), entry("M2", (500, 80, 22))])
    assert [(line.mark, line.quantity) for line in result.lines] == [("M1", 3), ("M2", 1)]
    assert result.warnings == ()


def test_ordre_naturel_des_reperes() -> None:
    entries = [entry(m) for m in ("M10", "M2", "M1", "m3", "A12", "A2")]
    assert marks(entries) == ["A2", "A12", "M1", "M2", "m3", "M10"]


def test_pieces_sans_repere_en_dernier() -> None:
    assert marks([entry(""), entry("Z9"), entry("A1")]) == ["A1", "Z9", ""]


def test_ordre_materiau_puis_cotes_decroissantes() -> None:
    entries = [
        entry("M1", (500, 80, 22)),
        entry("M1", (900, 80, 22)),
        entry("M1", (900, 120, 22)),
        entry("M1", (700, 90, 22), material="alisier"),
    ]
    lines = build_cut_list(entries).lines
    sizes = [(line.material_name, line.finished.length, line.finished.width) for line in lines]
    assert sizes == [
        ("Alisier", 700.0, 90.0),
        ("Chene", 900.0, 120.0),
        ("Chene", 900.0, 80.0),
        ("Chene", 500.0, 80.0),
    ]


def test_cotes_comparees_au_centieme() -> None:
    same = build_cut_list([entry(size=(800.0, 100.0, 22.0)), entry(size=(800.001, 100.0, 22.0))])
    assert len(same.lines) == 1
    other = build_cut_list([entry(), entry(size=(800.02, 100.0, 22.0))])
    assert len(other.lines) == 2


def test_ensembles_cites_sans_doublon_ni_effet_sur_la_cle() -> None:
    entries = [
        entry(furniture="Caisson 10"),
        entry(furniture="Caisson 2"),
        entry(furniture="Caisson 2"),
        entry(),
    ]
    (line,) = build_cut_list(entries).lines
    assert line.furniture == ("Caisson 2", "Caisson 10")
    assert line.quantity == 4


@pytest.mark.parametrize(
    ("text", "other"), [("M2", "M10"), ("a1", "B1"), ("M1", "M1a"), ("M01", "M1")]
)
def test_cle_naturelle(text: str, other: str) -> None:
    assert natural_key(text) < natural_key(other) or natural_key(text) == natural_key(other)
    assert natural_key("M2") < natural_key("M10")


# --- C2 : repère réutilisé ----------------------------------------------------------------


@pytest.mark.parametrize(
    "other",
    [
        entry(size=(700.0, 100.0, 22.0)),
        entry(material="alisier"),
        entry(grain=GrainDirection.WIDTH),
        entry(allowances=Allowances(30.0, 5.0, 0.0)),
        entry(additions=TENON),
    ],
    ids=["cotes", "materiau", "fil", "surcotes", "ajouts"],
)
def test_repere_reutilise_pour_des_pieces_differentes(other: CutEntry) -> None:
    result = build_cut_list([entry(), other])
    assert len(result.lines) == 2
    (warning,) = result.warnings
    assert warning.kind is CutNoticeKind.REPEATED_MARK
    assert warning.message == "Repère M1 utilisé pour des pièces différentes."


def test_avertissement_par_repere_une_seule_fois() -> None:
    entries = [entry(), entry(size=(1.0, 50.0, 20.0)), entry(size=(2.0, 50.0, 20.0))]
    assert len(build_cut_list(entries).warnings) == 1


# --- Q5 : pièces sans repère ---------------------------------------------------------------


def test_pieces_sans_repere_regroupees_par_cotes_avec_avertissement() -> None:
    entries = [entry("", quantity=2), entry("", quantity=1), entry("", (300, 50, 20))]
    result = build_cut_list(entries)
    assert [(line.display_mark, line.quantity) for line in result.lines] == [("—", 3), ("—", 1)]
    (warning,) = result.warnings
    assert warning.kind is CutNoticeKind.MISSING_MARK
    assert warning.message == "4 pièce(s) sans repère, regroupées par cotes."


# --- C3 / C4 : cotes de débit, volumes et masses ------------------------------------------


def test_cotes_de_debit_avec_ajouts_et_surcotes() -> None:
    (line,) = build_cut_list([entry(additions=TENON)]).lines
    assert (line.finished.length, line.rough.length) == (800.0, 880.0)  # 800 + 60 + 20
    assert (line.rough.width, line.rough.thickness) == (105.0, 22.0)
    assert line.additions == TENON
    assert line.allowances == Allowances(20.0, 5.0, 0.0)


def test_volume_et_masse_par_ligne() -> None:
    (line,) = build_cut_list([entry(quantity=3, additions=TENON)]).lines
    assert line.volume_m3() == pytest.approx(3 * 800 * 100 * 22 / 1e9)  # finies : sans ajouts
    assert line.volume_m3(rough=True) == pytest.approx(3 * 880 * 105 * 22 / 1e9)
    assert line.mass_kg() == pytest.approx(3 * 800 * 100 * 22 / 1e9 * 710)
    assert line.mass_kg(rough=True) == pytest.approx(3 * 880 * 105 * 22 / 1e9 * 710)


def test_entree_expose_ses_cotes_de_debit() -> None:
    assert entry(additions=TENON).rough.length == 880.0


# --- C5 : totaux ---------------------------------------------------------------------------


def test_totaux_par_materiau() -> None:
    entries = [entry(quantity=2), entry("M2", (500, 80, 22), quantity=1), plywood(), plywood("P2")]
    result = build_cut_list(entries)
    oak, ply = result.totals
    assert (oak.material_name, oak.quantity, oak.kind) == ("Chene", 3, MaterialKind.SOLID)
    assert oak.volume_m3 == pytest.approx((2 * 820 * 105 * 22 + 520 * 85 * 22) / 1e9)
    assert oak.mass_kg == pytest.approx(oak.volume_m3 * 710)
    assert oak.area_m2 is None
    assert (ply.material_name, ply.quantity) == ("Cp", 2)
    assert ply.area_m2 == pytest.approx(2 * 0.6 * 0.4)
    assert ply.mass_kg == pytest.approx(2 * 600 * 400 * 18 / 1e9 * 600)
    assert result.total_mass_kg == pytest.approx(oak.mass_kg + ply.mass_kg)


def test_surface_de_ligne() -> None:
    (line,) = build_cut_list([plywood()]).lines
    assert line.area_m2() == pytest.approx(0.24)


def test_liste_vide() -> None:
    result = build_cut_list([])
    assert (result.lines, result.totals, result.hardware, result.warnings) == ((), (), (), ())
    assert result.total_mass_kg == 0.0


# --- C6 : fournitures ----------------------------------------------------------------------


def test_tourillons_regroupes_par_diametre_et_longueur() -> None:
    dowels = [
        Hardware(HardwareKind.DOWEL, 8.0, 35.0, 4),
        Hardware(HardwareKind.DOWEL, 10.0, 40.0, 2),
        Hardware(HardwareKind.DOWEL, 8.0, 35.0, 2),
        Hardware(HardwareKind.DOWEL, 8.0, 30.0, 1),
    ]
    result = build_cut_list([], dowels)
    assert [(h.diameter, h.length, h.quantity) for h in result.hardware] == [
        (8.0, 30.0, 1),
        (8.0, 35.0, 6),
        (10.0, 40.0, 2),
    ]


# --- C8 : validation -----------------------------------------------------------------------


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "2", math.nan])
def test_quantite_invalide(quantity: object) -> None:
    with pytest.raises(InvalidCutEntryError, match="quantité"):
        CutEntry(record(), quantity)  # type: ignore[arg-type]


def test_entree_de_mauvais_type() -> None:
    with pytest.raises(InvalidCutEntryError, match="pièce"):
        CutEntry("M1")  # type: ignore[arg-type]
    with pytest.raises(InvalidCutEntryError, match="ajouts"):
        CutEntry(record(), 1, (1, 2, 3))  # type: ignore[arg-type]


def test_cotes_de_debit_hors_bornes() -> None:
    long = record("L", (19_900.0, 100.0, 22.0))
    with pytest.raises(InvalidCutEntryError, match="dépassent 20000 mm"):
        CutEntry(long, 1, Allowances(200.0, 0.0, 0.0))


@pytest.mark.parametrize("value", [math.nan, math.inf, 0.0, -3.0, 30_000.0, "8", None, True])
def test_fourniture_invalide(value: object) -> None:
    with pytest.raises(InvalidCutEntryError, match="Fourniture invalide"):
        Hardware(HardwareKind.DOWEL, value, 35.0, 1)  # type: ignore[arg-type]
    with pytest.raises(InvalidCutEntryError, match="longueur"):
        Hardware(HardwareKind.DOWEL, 8.0, value, 1)  # type: ignore[arg-type]


def test_fourniture_quantite_et_nature_invalides() -> None:
    with pytest.raises(InvalidCutEntryError, match="quantité"):
        Hardware(HardwareKind.DOWEL, 8.0, 35.0, 0)
    with pytest.raises(InvalidCutEntryError, match="nature"):
        Hardware("Dowel", 8.0, 35.0, 1)  # type: ignore[arg-type]


def test_erreur_traduisible() -> None:
    with pytest.raises(InvalidCutEntryError) as caught:
        CutEntry(record(), 0)
    assert caught.value.template.startswith("Entrée de débit invalide")
    assert caught.value.params["field"] == "quantité"
    assert Allowances() == NO_ADDITIONS
