# SPDX-License-Identifier: LGPL-2.1-or-later
"""Empreinte textuelle d'un solide d'une forme importée (B11) : ``core/shaped``."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.shaped import encode_fingerprint, fingerprint_matches

VALUES = [3_520_000.0, 123_456.789, 4.2e7, 3.1e8, 9.9e7, 400.0, 100.0, 11.0]


def test_une_empreinte_reconnait_ses_valeurs() -> None:
    assert fingerprint_matches(encode_fingerprint(VALUES), VALUES)


def test_l_arrondi_de_l_ecriture_est_absorbe() -> None:
    text = encode_fingerprint(VALUES)
    jittered = [value * (1.0 + 1e-8) for value in VALUES]
    assert fingerprint_matches(text, jittered)


@pytest.mark.parametrize("index", range(len(VALUES)))
def test_un_solide_different_n_est_pas_reconnu(index: int) -> None:
    changed = list(VALUES)
    changed[index] = changed[index] * 1.01 + 1.0
    assert not fingerprint_matches(encode_fingerprint(VALUES), changed)


def test_zero_et_negatif_sont_representables() -> None:
    values = [0.0, -12.5, 7.0]
    assert fingerprint_matches(encode_fingerprint(values), values)


@pytest.mark.parametrize(
    "text", ["", "abc", "1;2;x", "1;2", "nan;nan;nan", "inf;1;2", ";;", "1;2;3;4;5"]
)
def test_un_texte_illisible_ou_de_longueur_differente_est_refuse(text: str) -> None:
    assert not fingerprint_matches(text, [1.0, 2.0, 3.0])


def test_un_texte_trop_long_est_refuse_sans_etre_lu() -> None:
    assert not fingerprint_matches(";".join(["1"] * 10_000), [1.0])


@pytest.mark.parametrize(
    "values", [[], [math.nan], [1.0, math.inf], [0.0] * 33], ids=["vide", "nan", "inf", "trop"]
)
def test_valeurs_invalides_levent_value_error(values: list[float]) -> None:
    with pytest.raises(ValueError, match="values"):
        encode_fingerprint(values)
