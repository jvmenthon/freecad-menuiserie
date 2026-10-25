# SPDX-License-Identifier: LGPL-2.1-or-later
"""Distance gardée dans les rangées d'un ensemble (DI-c, critères F1 à F4, ADR 0022).

Bureau de référence de J4 / #86 : la Distance relie le bas de la joue gauche (z = 0) au bas du
voile (z = 320) sur l'axe Z. Les deux pièces ne se recouvrent pas sur X (règle 1 bis).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    BlockedRowError,
    FurnitureAxis,
    FurnitureBox,
    KeptGap,
    Member,
    NoticeKind,
    bindings_for,
    check_resize,
    check_thickness,
    follow_rules,
    gap_term,
    same_binding,
)
from tests.unit.aides_ensembles import BOX, desk, evaluate, row_of, with_options

Z = FurnitureAxis.HEIGHT
KEY = "Distance001"
TERM = gap_term(KEY)
LABEL = "Distance : Joue gauche \N{EN DASH} Voile"
GAP = KeptGap(KEY, "JG", False, "V", False, Z, LABEL)


def kept(*keys: str, gap: KeptGap = GAP) -> list[Member]:
    """Bureau dont les membres ``keys`` portent la Distance ``gap``."""
    return [replace(m, gaps=(gap,)) if m.key in keys else m for m in with_options(desk())]


def both() -> list[Member]:
    return kept("JG", "V")


def expressions(members: list[Member]) -> dict[tuple[str, str], str]:
    rules, _ = follow_rules(BOX, members)
    bindings, _ = bindings_for("Bureau", members, rules)
    return {(b.key, b.prop): b.expression for b in bindings}


def test_f2_vis_a_vis_sans_recouvrement() -> None:
    assert "JG" not in row_of(with_options(desk()), "V", Z).keys
    row = row_of(both(), "V", Z)
    assert set(row.keys) == {"P", "JG", "V"}
    assert row.locked == (KEY,)
    assert not row.blocked
    assert "V" in row_of(both(), "JG", Z).keys  # dans les deux sens


def test_f1_une_seule_cellule_vaut_name_value() -> None:
    texts = expressions(both())
    assert texts[("V", "Width")] == "<<Bureau>>.Height - P.Thickness - Distance001.Value"
    assert texts[("V", "Placement.Base.z")] == "<<Bureau>>.Origin.z + Distance001.Value"
    assert texts[("JG", "Length")] == "<<Bureau>>.Height - P.Thickness"  # le terme se simplifie


def test_f1_une_distance_n_est_lue_que_par_ses_deux_pieces() -> None:
    """Une pièce qui ne porte pas la Distance dans ses ``gaps`` ne la cite pas."""
    assert expressions(kept("JG"))[("V", "Width")].endswith("Distance001.Value")
    rules, _ = follow_rules(BOX, with_options(desk()))
    assert not any(TERM in str(rule.size) for rule in rules["V"])


def test_f3_bureau_de_reference() -> None:
    rules, _ = follow_rules(BOX, both())
    base = {TERM: 320.0}
    assert evaluate(rules, "V", Z, 750.0, base) == (320.0, 400.0)
    # Height -> 800 : le haut du voile suit le plateau, les 320 mm sont conservés
    assert evaluate(rules, "V", Z, 800.0, base) == (320.0, 450.0)
    # plateau 30 -> 25 : le haut du voile suit la sous-face du plateau
    assert evaluate(rules, "V", Z, 750.0, {**base, "P": 25.0}) == (320.0, 405.0)
    # Distance.Value -> 300 : le voile s'écarte de 20 mm, sans code de l'atelier
    assert evaluate(rules, "V", Z, 750.0, {TERM: 300.0}) == (300.0, 420.0)


def test_f1_la_distance_coupee_est_figee_avec_une_notice() -> None:
    cut = KeptGap(KEY, "JG", False, "V", True, Z, LABEL)  # le bas du voile coupe l'intervalle
    members = kept("JG", "V", gap=cut)
    rules, notices = follow_rules(BOX, members)
    assert [n.kind for n in notices] == [NoticeKind.GAP_SPLIT]
    assert notices[0].params["member"] == LABEL
    bindings, _ = bindings_for("Bureau", members, rules)
    assert not any("Distance001" in b.expression for b in bindings)


def test_f1_distance_nulle_sans_effet() -> None:
    touching = KeptGap(KEY, "P", False, "V", True, Z)  # le haut du voile touche le plateau
    members = kept("P", "V", gap=touching)
    assert expressions(members) == expressions(with_options(desk()))


def test_f1_liaison_reconnue_apres_copie() -> None:
    """Une copie du document réécrit ``Distance001`` : ce n'est pas une formule utilisateur."""
    recorded = "<<Bureau>>.Height - P.Thickness - Distance001.Value"
    assert same_binding("<<Bureau>>.Height - P.Thickness - Distance002.Value", recorded)


def test_f1_pas_de_cycle_d_expressions() -> None:
    """Une Distance n'a aucune dépendance de pièce : citée par plusieurs pièces sans gel."""
    texts = expressions(both())
    assert sum("Distance001" in text for text in texts.values()) == 2


def test_f4_une_distance_bloque_la_rangee() -> None:
    members = [replace(m, locked=m.key == "V") for m in both()]
    row = row_of(members, "V", Z)
    assert row.blocked
    assert row.locked == ("V", KEY)
    rules, _ = follow_rules(BOX, members)
    with pytest.raises(BlockedRowError) as error:
        check_resize(BOX, FurnitureBox(1200.0, 600.0, 800.0), members, rules, [])
    assert error.value.locked == ("V", KEY)
    assert LABEL in str(error.value.params["locked"])


def test_f4_sans_distance_la_meme_rangee_n_est_pas_bloquee() -> None:
    members = [replace(m, locked=m.key == "V") for m in with_options(desk())]
    assert not row_of(members, "V", Z).blocked


def test_f4_epaisseur_refusee_dans_une_rangee_bloquee_par_la_distance() -> None:
    members = [replace(m, locked=m.key == "V") for m in both()]
    with pytest.raises(BlockedRowError) as error:
        check_thickness(BOX, members, "P", 40.0, [])
    assert KEY in error.value.locked
