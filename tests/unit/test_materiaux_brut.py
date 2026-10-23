# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseurs de brut de la bibliothèque (J2, § 10.4, critère B1, ADR 0015)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.materials import (
    MAX_THICKNESSES,
    Material,
    MaterialKind,
    Severity,
    load_library,
    normalized_rough_thicknesses,
    parse_materials,
)
from tests.unit.aides import OAK, SOURCE, document, make_material

HARDWOODS = ("chene", "hetre", "frene", "noyer", "merisier")
SOFTWOODS = ("pin-sylvestre", "sapin-epicea", "douglas")
HARDWOOD_ROUGH = (27.0, 34.0, 41.0, 54.0, 65.0, 80.0, 100.0)
SOFTWOOD_ROUGH = (18.0, 22.0, 27.0, 32.0, 38.0, 50.0, 63.0, 75.0, 100.0)


def material(rough: object) -> Material:
    return replace(make_material("chene", "Chêne"), rough_thicknesses=rough)  # type: ignore[arg-type]


def test_regle_triee_sans_doublon() -> None:
    assert normalized_rough_thicknesses([34, 27, 27, 41.5]) == (27.0, 34.0, 41.5)


@pytest.mark.parametrize(
    "value",
    [
        None,
        27,
        "27",
        [],
        [0.05],
        [300.5],
        [27, True],
        [27, float("nan")],
        ["x"],
        list(range(1, MAX_THICKNESSES + 2)),
    ],
)
def test_regle_refuse_les_valeurs_invalides(value: object) -> None:
    assert normalized_rough_thicknesses(value) is None


def test_champ_absent_donne_aucune_epaisseur() -> None:
    [oak], issues = parse_materials(document(OAK), SOURCE)
    assert issues == []
    assert oak.rough_thicknesses == ()


def test_lecture_json_trie_et_normalise() -> None:
    [oak], issues = parse_materials(document({**OAK, "rough_thicknesses": [41, 27, 27]}), SOURCE)
    assert issues == []
    assert oak.rough_thicknesses == (27.0, 41.0)


@pytest.mark.parametrize("value", [[], 27, "27", [0], [301], [27, "x"]])
def test_lecture_json_refuse_une_valeur_invalide_en_citant_le_champ(value: object) -> None:
    materials, [issue] = parse_materials(document({**OAK, "rough_thicknesses": value}), SOURCE)
    assert materials == []
    assert issue.severity is Severity.ERROR
    assert issue.params["field"] == "rough_thicknesses"
    assert "rough_thicknesses" in issue.format()


def test_cle_connue_sans_avertissement() -> None:
    _, issues = parse_materials(document({**OAK, "rough_thicknesses": [27]}), SOURCE)
    assert issues == []


def test_constructeur_normalise_et_refuse() -> None:
    assert material((34, 27)).rough_thicknesses == (27.0, 34.0)
    assert make_material("chene", "Chêne").rough_thicknesses == ()
    for bad in ((0.0,), None, 27):
        with pytest.raises(ValueError, match="champ « rough_thicknesses »"):
            material(bad)


def test_bibliotheque_integree_epaisseurs_de_brut() -> None:
    library, issues = load_library(DATA_DIR / "materiaux.json", None)
    assert issues == []
    for material_id in HARDWOODS:
        assert library.get(material_id).rough_thicknesses == HARDWOOD_ROUGH
    for material_id in SOFTWOODS:
        assert library.get(material_id).rough_thicknesses == SOFTWOOD_ROUGH
    for panel in library.by_kind(MaterialKind.PLYWOOD, MaterialKind.MDF, MaterialKind.MELAMINE):
        assert panel.rough_thicknesses == ()
