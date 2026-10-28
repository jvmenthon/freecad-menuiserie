# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu, refus d'un redimensionnement ou d'une épaisseur, sous-ensembles (J4a, critères F10,
F11 ; ADR 0019, critères E2, E3, E6, E7, E8)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    BlockedRowError,
    Edge,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Member,
    Notice,
    NoticeKind,
    check_membership,
    check_resize,
    check_thickness,
    follow_rules,
    member_spans,
    predict,
    with_default_options,
)
from freecad.menuiserie.core.geometry import Vec3
from tests.unit.aides_assemblages import block
from tests.unit.aides_ensembles import BOX, FREE_BACK, desk, placed, with_options

W, D, H = FurnitureAxis.WIDTH, FurnitureAxis.DEPTH, FurnitureAxis.HEIGHT
DEEPER = FurnitureBox(1200, 800, 750)
TALLER = FurnitureBox(1200, 600, 800)


def predicted(
    new: FurnitureBox,
    unfixed: dict[str, frozenset[Edge]] | None = None,
    **modes: InteriorMode,
) -> dict[str, Member]:
    members = with_options(desk(**modes), unfixed)
    rules, _ = follow_rules(BOX, members)
    return dict(predict(new, members, rules))


def span(member: Member, axis: FurnitureAxis) -> tuple[float, float]:
    found = member_spans(member)[axis]
    return round(found.lo, 9), round(found.hi, 9)


def size(member: Member) -> tuple[float, float, float]:
    assert member.block is not None
    dims = member.block.dimensions
    return dims.length, dims.width, dims.thickness


# --- F10 : aperçu -------------------------------------------------------------------------


def test_profondeur_800_options_par_defaut() -> None:
    result = predicted(DEEPER)
    assert size(result["P"]) == (1200, 800, 30)
    assert size(result["JG"]) == (720, 760, 22)
    assert size(result["JD"]) == (720, 760, 22)
    assert span(result["V"], D) == (641, 659)  # suit le fond (141 mm)


def test_profondeur_800_voile_decoche() -> None:
    free = {"V": frozenset({Edge.BACK})}
    assert span(predicted(DEEPER, free)["V"], D) == (441, 459)  # Stay : immobile
    proportional = predicted(DEEPER, free, V=InteriorMode.PROPORTIONAL)
    lo, hi = span(proportional["V"], D)  # les deux écarts gardent leur proportion (E5)
    assert lo == pytest.approx(441 * 782 / 582)
    assert hi - lo == pytest.approx(18)


def test_profondeur_800_arriere_des_joues_decoche() -> None:
    result = predicted(DEEPER, FREE_BACK)
    assert size(result["P"]) == (1200, 800, 30)
    assert size(result["JG"]) == (720, 560, 22)


def test_hauteur_800() -> None:
    result = predicted(TALLER)
    plateau = result["P"]
    assert plateau.block is not None
    assert math.isclose(plateau.block.placement.translation.z, 770)
    assert size(plateau) == (1200, 600, 30)  # la hauteur ne traverse pas sa longueur
    assert size(result["V"]) == (1156, 450, 18)
    assert size(result["JG"]) == (770, 560, 22)


def test_largeur_1400_deplace_la_joue_droite() -> None:
    result = predicted(FurnitureBox(1400, 600, 750))
    assert span(result["JD"], W) == (1378, 1400)
    assert size(result["V"])[0] == 1356


def test_propriete_pilotee_gardee_par_l_apercu() -> None:
    members = with_options(desk(V=InteriorMode.PROPORTIONAL))
    members = [
        replace(m, driven=frozenset({"Placement.Base.y"})) if m.key == "V" else m for m in members
    ]
    rules, _ = follow_rules(BOX, members)
    assert span(predict(DEEPER, members, rules)["V"], D) == (441, 459)
    notices = check_resize(BOX, DEEPER, members, rules, [])
    assert [(n.kind, n.params["property"]) for n in notices] == [
        (NoticeKind.USER_FORMULA, "Placement.Base.y")
    ]
    assert check_resize(BOX, TALLER, members, rules, []) == ()


def test_cote_pilotee_gardee_par_l_apercu() -> None:
    members = with_options(desk())
    members = [replace(m, driven=frozenset({"Width"})) if m.key == "JG" else m for m in members]
    rules, _ = follow_rules(BOX, members)
    assert size(predict(DEEPER, members, rules)["JG"]) == (720, 560, 22)


# --- F10 : refus --------------------------------------------------------------------------


def resize(
    new: FurnitureBox,
    members: list[Member],
    joined: list[tuple[str, str]] | None = None,
) -> tuple[Notice, ...]:
    rules, _ = follow_rules(BOX, members)
    return check_resize(BOX, new, members, rules, joined or [])


def test_joue_trop_petite() -> None:
    with pytest.raises(FurnitureError) as caught:
        resize(FurnitureBox(1200, 30, 750), with_options(desk()))
    assert (
        str(caught.value)
        == "« Joue gauche » deviendrait trop petite : Width = \N{MINUS SIGN}10 mm."
    )


def test_voile_trop_petit() -> None:
    with pytest.raises(FurnitureError) as caught:
        resize(FurnitureBox(1200, 600, 350.05), with_options(desk()))
    assert caught.value.params == {"member": "Voile", "property": "Width", "value": "0,05"}


def test_piece_trop_grande() -> None:
    long = Member(
        "A", block=placed((1300.0, 600.0, 30.0), (-100.0, 0.0, 0.0)), fixed=frozenset(Edge)
    )
    with pytest.raises(FurnitureError, match="trop grande"):
        resize(FurnitureBox(20_000, 600, 750), [long])


def test_contact_d_assemblage_perdu() -> None:
    """La longueur du voile suit une formule de l'utilisateur : elle ne change pas, la joue
    droite s'éloigne et son contact avec le voile est perdu."""
    members = [replace(m, driven=frozenset({"Length"})) if m.key == "V" else m for m in desk()]
    members = with_options(members)
    wider = FurnitureBox(1400, 600, 750)
    assert resize(wider, members, [("JG", "V")])[0].params["property"] == "Length"
    with pytest.raises(FurnitureError) as caught:
        resize(wider, members, [("JG", "V"), ("JD", "V")])
    assert caught.value.params == {"host": "Joue droite", "guest": "Voile"}


def test_voile_libre_garde_le_contact_avec_les_joues() -> None:
    """Sans formule, le voile prend toute la différence : les contacts sont conservés."""
    assert (
        resize(FurnitureBox(1400, 600, 750), with_options(desk()), [("JG", "V"), ("JD", "V")]) == ()
    )


def test_chevauchement_perdu() -> None:
    """Deux pièces qui se chevauchent se partagent la différence au prorata : leur
    chevauchement est conservé, sauf si la longueur de la première suit une formule."""
    first = Member(
        "A", block=placed((600.0, 600.0, 30.0), (0.0, 0.0, 0.0)), fixed=frozenset({Edge.LEFT})
    )
    second = Member(
        "B",
        block=placed((600.0, 600.0, 30.0), (500.0, 0.0, 0.0)),
        fixed=frozenset({Edge.RIGHT}),
        mode=InteriorMode.PROPORTIONAL,
    )
    box = FurnitureBox(1100, 600, 30)
    rules, _ = follow_rules(box, [first, second])
    wide = FurnitureBox(2000, 600, 30)
    assert check_resize(box, wide, [first, second], rules, [("A", "B")]) == ()
    driven = replace(first, driven=frozenset({"Length"}))
    rules, _ = follow_rules(box, [driven, second])
    with pytest.raises(FurnitureError):
        check_resize(box, wide, [driven, second], rules, [("A", "B")])
    notices = check_resize(box, FurnitureBox(1150, 600, 30), [driven, second], rules, [("A", "B")])
    assert [n.kind for n in notices] == [NoticeKind.USER_FORMULA]  # le chevauchement reste


def test_paire_hors_ensemble_ignoree() -> None:
    assert resize(DEEPER, with_options(desk()), [("JG", "Autre")]) == ()


def test_piece_qui_depasse() -> None:
    notices = resize(FurnitureBox(1200, 500, 750), with_options(desk(), FREE_BACK))
    assert [(n.kind, n.params["member"]) for n in notices] == [
        (NoticeKind.OUTSIDE_BOX, "Joue gauche"),
        (NoticeKind.OUTSIDE_BOX, "Joue droite"),
    ]


# --- E6, E7 : rangées bloquées, pièces verrouillées -------------------------------------------


def locked_desk(*keys: str) -> list[Member]:
    return [replace(m, locked=m.key in keys) for m in with_options(desk())]


def test_rangee_bloquee_par_le_voile_verrouille_E6() -> None:
    members = locked_desk("V")
    with pytest.raises(BlockedRowError) as caught:
        resize(FurnitureBox(1300, 600, 750), members)
    error = caught.value
    assert isinstance(error, FurnitureError)
    assert error.locked == ("V",)
    assert sorted(error.members) == ["JD", "JG", "V"]
    assert str(error) == (
        "Impossible de changer la largeur de l'ensemble à 1300 mm : aucune pièce de la rangée "
        "(« Joue gauche », « Joue droite », « Voile ») ne peut s'adapter "
        "(cotes fixes : « Voile »)."
    )
    assert resize(DEEPER, members) == ()  # la profondeur reste possible
    assert resize(TALLER, members) == ()  # le voile suit le plateau, sans changer de cotes


def test_voile_verrouille_suit_la_hauteur() -> None:
    members = locked_desk("V")
    rules, _ = follow_rules(BOX, members)
    after = predict(TALLER, members, rules)
    assert size(after["V"]) == (1156, 400, 18)  # cotes inchangées
    assert span(after["V"], H) == (370, 770)  # il reste sous le plateau


def test_pieces_verrouillees_citees_dans_l_ordre_de_la_rangee() -> None:
    members = locked_desk("V", "JG")
    with pytest.raises(BlockedRowError) as caught:
        resize(FurnitureBox(1300, 600, 750), members)
    assert caught.value.locked == ("JG", "V")
    assert "cotes fixes : « Joue gauche », « Voile »" in str(caught.value)


def stacked() -> tuple[list[Member], FurnitureBox]:
    """Deux planches de 18 mm empilées qui remplissent la hauteur de l'ensemble."""
    boards = [
        Member("A", block=placed((600.0, 400.0, 18.0), (0.0, 0.0, 0.0)), label="Fond"),
        Member("B", block=placed((600.0, 400.0, 18.0), (0.0, 0.0, 18.0)), label="Dessus"),
    ]
    box = FurnitureBox(600, 400, 36)
    return list(with_default_options(box, boards)), box


def test_rangee_bloquee_sans_piece_verrouillee() -> None:
    members, box = stacked()
    rules, _ = follow_rules(box, members)
    with pytest.raises(BlockedRowError) as caught:
        check_resize(box, FurnitureBox(600, 400, 50), members, rules, [])
    assert caught.value.locked == ()
    assert str(caught.value) == (
        "Impossible de changer la hauteur de l'ensemble à 50 mm : aucune pièce de la rangée "
        "(« Fond », « Dessus ») ne peut s'adapter (les épaisseurs la remplissent)."
    )
    assert check_resize(box, FurnitureBox(900, 400, 36), members, rules, []) == ()


def test_epaisseur_de_joue_acceptee_E7() -> None:
    assert check_thickness(BOX, with_options(desk()), "JG", 25.0, [("JG", "V")]) == ()


def test_epaisseur_refusee_par_le_voile_verrouille_E7() -> None:
    with pytest.raises(BlockedRowError) as caught:
        check_thickness(BOX, locked_desk("V"), "JG", 25.0, [])
    assert caught.value.locked == ("V",)
    assert str(caught.value) == (
        "Impossible de changer l'épaisseur de « Joue gauche » à 25 mm : aucune pièce de la "
        "rangée (« Joue gauche », « Joue droite », « Voile ») ne peut s'adapter "
        "(cotes fixes : « Voile »)."
    )
    # une épaisseur qui ne change pas, ou qui n'est pas dans la rangée, n'est pas refusée
    assert check_thickness(BOX, locked_desk("V"), "JG", 22.0, []) == ()
    assert check_thickness(BOX, locked_desk("V"), "P", 40.0, []) == ()


def test_epaisseur_de_plateau_E7() -> None:
    """Le plateau plus épais raccourcit les joues et le voile ; le contact tient."""
    members = with_options(desk())
    rules, _ = follow_rules(BOX, members)
    after = predict(BOX, members, rules, {"P": 40.0})
    assert size(after["JG"]) == (710, 560, 22)
    assert size(after["V"]) == (1156, 390, 18)
    assert span(after["P"], H) == (710, 750)
    assert check_thickness(BOX, members, "P", 40.0, [("JG", "P"), ("V", "P")]) == ()


def test_epaisseur_hors_bornes_et_cas_particuliers_E7() -> None:
    members = with_options(desk())
    with pytest.raises(FurnitureError, match="trop petite : Thickness"):
        check_thickness(BOX, members, "JG", 0.05, [])
    with pytest.raises(FurnitureError, match="trop grande"):
        check_thickness(BOX, members, "JG", 30_000.0, [])
    with pytest.raises(FurnitureError, match="trop petite : Length"):
        check_thickness(BOX, members, "P", 749.95, [])  # les joues n'ont plus que 0,05 mm
    with pytest.raises(ValueError, match="membre inconnu"):
        check_thickness(BOX, members, "Autre", 20.0, [])
    turned = Member(
        "X", block=block((100.0, 100.0, 18.0), (500.0, 200.0, 0.0), 45.0), fixed=frozenset()
    )
    assert check_thickness(BOX, [*members, turned], "X", 30.0, []) == ()  # pas d'équerre


def test_epaisseur_et_formule_de_l_utilisateur_E8() -> None:
    members = [
        replace(m, driven=frozenset({"Placement.Base.x"})) if m.key == "JG" else m
        for m in with_options(desk())
    ]
    notices = check_thickness(BOX, members, "JG", 25.0, [])
    assert [(n.kind, n.params["member"]) for n in notices] == [
        (NoticeKind.USER_FORMULA, "Joue gauche"),
        (NoticeKind.OUTSIDE_BOX, "Joue gauche"),  # sa position reste : la joue déborde
    ]
    assert notices[0].params["property"] == "Placement.Base.x"
    assert check_thickness(BOX, members, "P", 40.0, []) == ()  # cette joue ne cite pas P.x


# --- F11 : sous-ensemble ------------------------------------------------------------------


def caisson(**changes: object) -> Member:
    member = Member(
        "C",
        box=FurnitureBox(600, 560, 720),
        origin=Vec3(300, 0, 0),
        fixed=frozenset({Edge.FRONT, Edge.BACK, Edge.BOTTOM}),
        label="Caisson",
    )
    return replace(member, **changes)  # type: ignore[arg-type]


def test_sous_ensemble_suit_la_profondeur() -> None:
    member = caisson()
    rules, _ = follow_rules(BOX, [member])
    result = predict(DEEPER, [member], rules)["C"]
    assert result.box == FurnitureBox(600, 760, 720)
    assert result.origin == Vec3(300, 0, 0)


def test_sous_ensemble_en_proportion() -> None:
    member = caisson(fixed=frozenset(), mode=InteriorMode.PROPORTIONAL)
    rules, _ = follow_rules(BOX, [member])
    result = predict(FurnitureBox(2400, 600, 750), [member], rules)["C"]
    assert result.box is not None
    assert result.origin is not None
    assert math.isclose(result.box.width, 1200)
    assert math.isclose(result.box.depth, 560)
    assert math.isclose(result.box.height, 720)
    assert math.isclose(result.origin.x, 600)


def test_sous_ensemble_en_contact_avec_une_piece() -> None:
    assert resize(DEEPER, [caisson(), *with_options(desk())], [("C", "P")]) == ()


LABELS = {"B": "Bureau", "C": "Caisson", "T": "Tiroir"}


@pytest.mark.parametrize(
    ("furniture", "candidate", "parents"),
    [("B", "B", {}), ("C", "B", {"C": "B"}), ("T", "B", {"T": "C", "C": "B"})],
    ids=["lui-même", "parent", "ancêtre"],
)
def test_cycle_d_ensembles_refuse(furniture: str, candidate: str, parents: dict[str, str]) -> None:
    with pytest.raises(FurnitureError, match="un ensemble ne peut pas être membre"):
        check_membership(furniture, candidate, parents, LABELS)


def test_ensemble_accepte() -> None:
    check_membership("B", "C", {}, LABELS)
    check_membership("B", "T", {"T": "C"}, {})
    check_membership("A", "C", {"A": "X", "X": "A"}, {})  # boucle déjà présente : pas d'attente


def test_membre_pas_d_equerre_ignore() -> None:
    turned = Member(
        "X", block=block((100.0, 100.0, 18.0), (500.0, 200.0, 0.0), 45.0), fixed=frozenset()
    )
    members = [*with_options(desk()), turned]
    rules, notices = follow_rules(BOX, members)
    assert "X" not in predict(DEEPER, members, rules)
    assert check_resize(BOX, DEEPER, members, rules, [("X", "P")]) == ()
    assert [n.kind for n in notices] == [NoticeKind.NOT_SQUARE]
