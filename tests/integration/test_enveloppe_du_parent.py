# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes du parent recalées sur l'enveloppe de ses membres (ADR 0049) : non-régression."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import build_parts
from tests.integration.test_ensemble_membres import caisson

pytestmark = pytest.mark.integration

api = pytest.importorskip("freecad.menuiserie.api")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")


def names(objects: list[Any]) -> list[str]:
    return [obj.Name for obj in objects]


def meuble(document: Any) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Bureau qui contient le sous-ensemble Caisson : (bureau, caisson, plateau, pièces du
    caisson)."""
    bureau = build_parts(document)
    sub, parts = caisson(document)
    furniture, _ = api.make_furniture(
        [*(bureau.parts[mark] for mark in ("P", "JG", "JD")), sub], label="Bureau"
    )
    return furniture, sub, bureau.parts["P"], parts


drag = pytest.importorskip("freecad.menuiserie.features.furniture_drag")
envelope = pytest.importorskip("freecad.menuiserie.features.furniture_envelope")


def global_boxes(document: Any, skip: set[str]) -> dict[str, tuple[float, ...]]:
    """Boîtes globales arrondies des objets à forme, sauf ``skip``."""
    found = {}
    for obj in document.Objects:
        if obj.Name in skip or obj.TypeId != "Part::FeaturePython" or obj.Shape.isNull():
            continue
        shape = obj.Shape.copy()
        shape.Placement = obj.getGlobalPlacement()
        b = shape.BoundBox
        found[obj.Name] = tuple(
            round(v, 3) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)
        )
    return found


def sizes(furniture: Any) -> tuple[float, ...]:
    origin = furniture.Origin
    return tuple(
        round(v, 3)
        for v in (
            origin.x,
            origin.y,
            origin.z,
            furniture.Width.Value,
            furniture.Depth.Value,
            furniture.Height.Value,
        )
    )


def assert_enveloppe(furniture: Any) -> None:
    box = envelope.member_envelope(furniture)
    expected = (*(box.lo(i) for i in range(3)), *(box.size(i) for i in range(3)))
    assert sizes(furniture) == pytest.approx(expected, abs=1e-3)


def caisson_names(parts: dict[str, Any]) -> set[str]:
    """Brutes et pièces usinées du caisson (celles qui bougent avec lui)."""
    found = {part.Name for part in parts.values()}
    found |= {m.Name for part in parts.values() if (m := api.machined_part_of(part)) is not None}
    return found


def test_sous_ensemble_deplace_hors_du_parent_l_agrandit(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    skip = caisson_names(parts)
    others = global_boxes(document, skip)
    width = furniture.Width.Value
    assert api.move_furniture(sub, (900, 0, 0))
    document.recompute()
    # Le plateau va de 0 à 1200, le caisson sorti à droite finit à 1340 : le parent s'agrandit.
    assert furniture.Width.Value > width + 100
    assert_enveloppe(furniture)
    assert global_boxes(document, skip) == others  # les autres pièces ne bougent pas


def test_sous_ensemble_deplace_a_gauche_decale_l_origine(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    skip = caisson_names(parts)
    others = global_boxes(document, skip)
    x0 = furniture.Origin.x
    assert api.move_furniture(sub, (-700, 0, 0))
    document.recompute()
    assert furniture.Origin.x < x0 - 600
    assert_enveloppe(furniture)
    assert global_boxes(document, skip) == others


def test_sous_ensemble_tourne_le_parent_englobe_la_rotation(document: Any) -> None:
    furniture, sub, _, _ = meuble(document)
    memento = drag.begin_furniture_drag(sub)
    assert drag.rotate_furniture_by(memento, 2, 30.0)
    drag.end_furniture_drag(memento)
    document.recompute()
    assert_enveloppe(furniture)


def test_enveloppe_deja_juste_rien_n_est_ecrit(document: Any) -> None:
    furniture, _, _, _ = meuble(document)
    if envelope.reframe(furniture):  # première fois : recalage éventuel de la création
        document.recompute()
    assert envelope.reframe(furniture) is False


def test_sous_ensemble_n_est_jamais_recale(document: Any) -> None:
    _, sub, _, _ = meuble(document)
    assert envelope.reframe(sub) is False


def test_creation_autour_d_un_ensemble_tourne_l_englobe(document: Any) -> None:
    """Non-régression (jv, 2026-11-11) : un ensemble créé autour d'un ensemble tourné doit
    englober sa rotation dès la création."""
    bureau = build_parts(document)
    sub, _ = caisson(document)
    memento = drag.begin_furniture_drag(sub)
    assert drag.rotate_furniture_by(memento, 2, 45.0)
    drag.end_furniture_drag(memento)
    document.recompute()
    furniture, _ = api.make_furniture([bureau.parts["P"], sub], label="Meuble")
    document.recompute()
    assert_enveloppe(furniture)


def test_le_parent_retrecit_quand_on_ramene_le_sous_ensemble(document: Any) -> None:
    """jv, 2026-11-11 : « la boîte doit toujours être de la taille de l'ensemble », sans marge.
    Ramener le sous-ensemble rend au parent ses cotes de départ."""
    furniture, sub, _, _ = meuble(document)
    depart = sizes(furniture)
    assert api.move_furniture(sub, (900, 0, 0))
    document.recompute()
    assert sizes(furniture) != depart
    assert api.move_furniture(sub, (-900, 0, 0))
    document.recompute()
    assert sizes(furniture) == pytest.approx(depart, abs=1e-3)
    assert_enveloppe(furniture)


def test_repetition_qui_suit_le_parent_ne_bouge_pas(document: Any) -> None:
    """Revue B1 : une répétition « Suivre le redimensionnement » lit les cotes du parent ;
    le recaler redistribuerait ses copies. Le parent n'est donc pas recalé : rien ne bouge."""
    bureau = build_parts(document)
    sub, parts = caisson(document)
    furniture, _ = api.make_furniture(
        [*(bureau.parts[mark] for mark in ("P", "JG", "JD")), sub], label="Bureau"
    )
    rep = api.make_repeat(
        [bureau.parts["JG"]], api.RepeatParams(count=1, step=300.0, axis="X", follow_resize=True)
    )
    document.recompute()
    skip = caisson_names(parts)
    others = global_boxes(document, skip)
    avant = sizes(furniture)
    assert api.move_furniture(sub, (900, 0, 0))
    document.recompute()
    assert sizes(furniture) == avant
    assert global_boxes(document, skip) == others  # copies de la répétition comprises
    assert rep.Document is not None


def test_copies_d_un_sous_ensemble_repete_englobees(document: Any) -> None:
    """Revue M1 : les copies d'un sous-ensemble répété suivent leur source par expression ;
    l'enveloppe est calculée après leur recalcul, pas à leur ancienne place."""
    furniture, sub, _, _ = meuble(document)
    api.make_repeat([sub], api.RepeatParams(count=1, step=500.0, axis="X"))
    document.recompute()
    assert api.move_furniture(sub, (900, 0, 0))
    document.recompute()
    assert_enveloppe(furniture)
