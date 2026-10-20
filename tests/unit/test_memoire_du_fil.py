# SPDX-License-Identifier: LGPL-2.1-or-later
"""Critères C10 et C11 (U) : mémoire et visibilité du sens du fil, règles de ``core``."""

from __future__ import annotations

import pytest

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.materials import Material, MaterialKind, load_library
from freecad.menuiserie.core.part_model import (
    GrainDirection,
    grain_after_material_change,
    material_has_grain,
    remembered_grain,
)

LIBRARY, _ = load_library(DATA_DIR / "materiaux.json", None)
LENGTH = GrainDirection.LENGTH
WIDTH = GrainDirection.WIDTH
NONE = GrainDirection.NONE


def material(material_id: str) -> Material:
    return LIBRARY.get(material_id)


# --- C10 : fil après un changement de matériau ---------------------------------------------


def test_matiere_avec_fil_reprend_le_sens_memorise() -> None:
    assert grain_after_material_change(material("chene"), NONE, preferred=WIDTH) is WIDTH


def test_sens_par_defaut_inchange_sans_memoire() -> None:
    assert grain_after_material_change(material("chene"), NONE) is LENGTH


def test_fil_courant_prime_sur_la_memoire() -> None:
    assert grain_after_material_change(material("chene"), LENGTH, preferred=WIDTH) is LENGTH


def test_matiere_sans_fil_ignore_la_memoire() -> None:
    assert grain_after_material_change(material("mdf"), WIDTH, preferred=WIDTH) is NONE


def test_memoire_sans_sens_refusee() -> None:
    with pytest.raises(ValueError, match="preferred"):
        grain_after_material_change(material("chene"), NONE, preferred=NONE)


# --- C10 : sens à mémoriser ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("grain", "previous", "expected"),
    [(WIDTH, LENGTH, WIDTH), (NONE, WIDTH, WIDTH), (LENGTH, WIDTH, LENGTH)],
)
def test_sens_memorise(
    grain: GrainDirection, previous: GrainDirection, expected: GrainDirection
) -> None:
    assert remembered_grain(grain, previous) is expected


def test_sans_fil_et_sans_memoire_donne_la_longueur() -> None:
    assert remembered_grain(NONE) is LENGTH


def test_memoire_precedente_sans_sens_refusee() -> None:
    with pytest.raises(ValueError, match="previous"):
        remembered_grain(WIDTH, NONE)


# --- C11 : le matériau a-t-il un fil ? -----------------------------------------------------


@pytest.mark.parametrize(
    ("material_id", "kind", "expected"),
    [
        ("chene", MaterialKind.SOLID, True),
        ("mdf", MaterialKind.MDF, False),
        (None, MaterialKind.SOLID, True),
        (None, MaterialKind.PLYWOOD, True),
        (None, MaterialKind.MDF, False),
        (None, MaterialKind.MELAMINE, False),
    ],
)
def test_matiere_avec_fil(material_id: str | None, kind: MaterialKind, expected: bool) -> None:
    known = material(material_id) if material_id is not None else None
    assert material_has_grain(known, kind) is expected
