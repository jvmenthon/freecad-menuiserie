# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plan de pièce : noms d'usinage et lignes propres aux assemblages (angle des queues d'aronde,
onglet, tourillons, bouts coupés en biais), retour de jv du 2026-11-13."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.drawing import (
    NAMES,
    MachiningKind,
    bevel_line,
    joint_note_lines,
    machining_lines,
    machining_name,
    machinings,
)
from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.joints._base import JointKind
from freecad.menuiserie.core.joints.dovetail import DovetailValues
from freecad.menuiserie.core.joints.dowels import DowelValues
from freecad.menuiserie.core.joints.miter import MiterValues

SIZE = (800.0, 400.0, 22.0)
TIMES = chr(0xD7)  # signe de multiplication


def test_queues_d_aronde_nommees_et_reperees_le_long_du_bout() -> None:
    tails = [Box(Vec3(800, y, 0), Vec3(830, y + 58.5, 22)) for y in (138.0, 203.5)]
    name = machining_name(JointKind.DOVETAIL, "guest_additions")
    items = machinings(
        [("Queue d'aronde", tail, MachiningKind.ADDED, name) for tail in tails], SIZE
    )
    ((template, values),) = machining_lines(items)
    assert values["name"] == NAMES["tail"][1]  # « queues », au pluriel
    assert values["count"] == "2"
    assert values["depth"] == "30"
    assert values["size"] == f"58,5 {TIMES} 22"
    assert values["face"] == "au bout droit"
    assert values["positions"] == "y 138; y 203,5"
    assert "longueur" in template and "ajout" not in template


def test_nom_au_singulier_et_mortaise() -> None:
    mortise = Box(Vec3(10, 0, 7.5), Vec3(50, 42, 14.5))
    name = machining_name(JointKind.MORTISE_TENON, "host_cuts")
    (item,) = machinings([("Tenon", mortise, MachiningKind.CUT, name)], SIZE)
    ((_, values),) = machining_lines([item])
    assert values["name"] == "mortaise"
    assert values["size"] == f"40 {TIMES} 7"  # vue du chant : longueur, épaisseur
    assert values["depth"] == "42"


def test_noms_par_type_et_groupe() -> None:
    assert machining_name(JointKind.MORTISE_TENON, "guest_additions") == "tenon"
    assert machining_name(JointKind.DOVETAIL, "host_cuts") == "socket"
    assert machining_name(JointKind.RABBET, "host_cuts") == "rabbet"
    assert machining_name(JointKind.TONGUE_GROOVE, "guest_trims") == "shoulder"
    assert machining_name(JointKind.RABBET, "guest_additions") == ""


def test_nom_inconnu_remplace_par_le_nom_generique() -> None:
    box = Box(Vec3(10, 10, 12), Vec3(50, 30, 22))
    (item,) = machinings([("X", box, MachiningKind.CUT, "inconnu")], SIZE)
    assert item.name == "cut"


def test_ligne_de_la_queue_d_aronde_donne_l_angle_et_la_pente() -> None:
    values = DovetailValues(6, 12.0, 10.0, 30.0, 19.4, ((0.0, 30.0),))
    ((template, line),) = joint_note_lines("Queue d'aronde", values, is_host=False)
    assert "°" in template and "pente" in template
    assert line["angle"] == "10"
    assert line["ratio"] == "5,7"  # 1 / tan 10°
    assert line["count"] == "6"
    assert (line["tail"], line["base"], line["pin"]) == ("30", "19,4", "12")


def test_ligne_des_tourillons() -> None:
    values = DowelValues(8.0, 35.0, 20.0, 3, 40.0, 11.0, 1.0, (40.0, 200.0, 360.0))
    ((_, line),) = joint_note_lines("Tourillons", values, is_host=True)
    assert (line["count"], line["diameter"], line["length"]) == ("3", "8", "35")


@pytest.mark.parametrize(("is_host", "angle"), [(True, "30"), (False, "60")])
def test_onglet_selon_la_piece(is_host: bool, angle: str) -> None:
    cut = Box(Vec3(0, 0, 0), Vec3(1, 1, 1))
    values = MiterValues(30.0, 60.0, cut, cut)
    ((_, line),) = joint_note_lines("Onglet", values, is_host=is_host)
    assert line["angle"] == angle


def test_type_sans_ligne_propre() -> None:
    assert joint_note_lines("Feuillure", object(), is_host=True) == []


def test_bout_coupe_en_biais() -> None:
    line = bevel_line("Tenon", (0, 1), (32.5, 0.0))
    assert line is not None
    _, values = line
    assert (values["end"], values["cut"], values["tilt"]) == ("bout droit", "32,5", "0")
    assert bevel_line("Tenon", (0, 1), (0.0, 0.0)) is None
