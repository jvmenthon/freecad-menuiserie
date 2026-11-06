# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fournitures de la liste de débit : faux tenons et biscuits (issue #159, ADR 0033)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.cutlist import (
    FRENCH_CSV,
    Hardware,
    HardwareKind,
    build_cut_list,
    to_csv,
)


def test_regroupement_par_taille_et_largeur() -> None:
    cut_list = build_cut_list(
        [],
        [
            Hardware(HardwareKind.BISCUIT, 4.0, 23.0, 2, 56.0),
            Hardware(HardwareKind.BISCUIT, 4.0, 23.0, 3, 56.0),
            Hardware(HardwareKind.BISCUIT, 4.0, 19.0, 1, 53.0),
            Hardware(HardwareKind.LOOSE_TENON, 8.0, 50.0, 4, 22.0),
            Hardware(HardwareKind.DOWEL, 8.0, 35.0, 6),
        ],
    )
    quantities = {(h.kind, h.length, h.width): h.quantity for h in cut_list.hardware}
    assert quantities == {
        (HardwareKind.BISCUIT, 23.0, 56.0): 5,
        (HardwareKind.BISCUIT, 19.0, 53.0): 1,
        (HardwareKind.LOOSE_TENON, 50.0, 22.0): 4,
        (HardwareKind.DOWEL, 35.0, 0.0): 6,
    }


def test_csv_nomme_la_largeur_des_pieces_plates() -> None:
    cut_list = build_cut_list(
        [],
        [
            Hardware(HardwareKind.LOOSE_TENON, 8.0, 50.0, 4, 22.0),
            Hardware(HardwareKind.DOWEL, 8.0, 35.0, 6),
        ],
    )
    text = to_csv(cut_list, FRENCH_CSV)
    assert "Faux tenon (largeur 22 mm);8;50;4" in text
    assert "Tourillon;8;35;6" in text
    assert "Diamètre ou épaisseur (mm)" in text


def test_largeur_invalide_refusee() -> None:
    with pytest.raises(ValueError):
        Hardware(HardwareKind.BISCUIT, 4.0, 23.0, 1, float("nan"))


def test_csv_pieds_et_coulisses() -> None:
    cut_list = build_cut_list(
        [],
        [
            Hardware(HardwareKind.FOOT, 10.0, 15.0, 4),
            Hardware(HardwareKind.DRAWER_SLIDE, 12.7, 450.0, 2),
        ],
    )
    text = to_csv(cut_list, FRENCH_CSV)
    assert "Pied de caisson;10;15;4" in text
    assert "Coulisse de tiroir;12,7;450;2" in text
