# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensemble relié en entier quand sa composition change (ADR 0019, point 6) : réglage d'un
membre, épaisseur, suppression ou retrait d'une pièce ; cycle avec une formule de l'utilisateur."""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import pytest

from tests.integration.bureau import build_parts
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
furniture_locks = pytest.importorskip("freecad.menuiserie.features.furniture_locks")

Y_AXIS = App.Vector(0, 1, 0)
TOLERANCE = 1e-6


def row(
    doc: Any, label: str, uprights: tuple[float, ...], shelves: tuple[float, ...]
) -> tuple[dict[str, Any], Any]:
    """Rangée ``joue | étagère | montant | étagère | ... | joue`` (22 / 18 mm) : pièces par repère
    et ensemble ``label``. ``uprights`` : épaisseurs des montants, ``shelves`` : longueurs."""
    turn = App.Rotation(Y_AXIS, -90)
    parts: dict[str, Any] = {}

    def make(key: str, size: tuple[float, float, float], base: tuple[float, float, float]) -> None:
        part = api.make_wood_part(*size, "chene", mark=key, doc=doc)
        rotation = turn if key.startswith(("J", "D")) else App.Rotation()
        part.Placement = App.Placement(App.Vector(*base), rotation)
        parts[key] = part

    x = 22.0
    make("JG", (720, 500, 22), (x, 0, 0))
    for index, length in enumerate(shelves):
        make(f"S{index + 1}", (length, 500, 18), (x, 0, 300))
        x += length
        if index < len(uprights):
            x += uprights[index]
            make(f"D{index + 1}", (720, 500, uprights[index]), (x, 0, 0))
    make("JD", (720, 500, 22), (x + 22, 0, 0))
    doc.recompute()
    furniture, _ = api.make_furniture(list(parts.values()), label=label)
    return parts, furniture


def spans(parts: dict[str, Any]) -> list[tuple[str, float, float]]:
    """Étendues en X des pièces, de gauche à droite."""
    found = [(k, p.Shape.BoundBox.XMin, p.Shape.BoundBox.XMax) for k, p in parts.items()]
    return sorted(found, key=lambda item: item[1])


def assert_side_by_side(parts: dict[str, Any]) -> None:
    ordered = spans(parts)
    for (first, _, high), (second, low, _) in pairwise(ordered):
        assert high <= low + TOLERANCE, f"{first} chevauche {second}"


# --- B1 : un réglage relie tout l'ensemble, sans cycle -------------------------------------


@pytest.mark.parametrize("label", ["Fond", "Étagère"])
def test_caisson_verrouille_une_piece_puis_relie(document: Any, label: str) -> None:
    furniture, _ = api.make_carcass(document)
    document.recompute()
    piece = next(
        o
        for o in furniture.InList
        if getattr(o, "Furniture", None) == furniture and o.Label == label
    )
    api.set_member_options(piece, locked=True)
    assert stale_or_invalid(document) == []
    api.set_member_options(piece, locked=False)
    piece.Locked = True  # éditeur de propriétés
    document.recompute()
    assert stale_or_invalid(document) == []
    api.rebind_furniture(furniture)
    document.recompute()
    assert stale_or_invalid(document) == []


def test_cycle_avec_une_formule_de_l_utilisateur_est_une_value_error(document: Any) -> None:
    """La joue dépend du voile (formule) : la liaison du voile, qui cite l'épaisseur de la joue,
    fermerait un cycle. Message traduit au lieu d'un ``RuntimeError`` ; liaisons rétablies."""
    bureau = build_parts(document)
    bureau.parts["JG"].setExpression("Length", "<<Voile>>.Length")
    with pytest.raises(ValueError, match="cycle") as error:
        api.make_furniture(list(bureau.parts.values()), label="Bureau")
    assert not isinstance(error.value, RuntimeError)
    assert all(bureau.expressions(mark).get("Length") != "" for mark in bureau.parts)
    assert bureau.expressions("V") == {}


# --- B2 : une épaisseur change, les voisines suivent ---------------------------------------


def two_dividers(doc: Any) -> tuple[dict[str, Any], Any]:
    return row(doc, "Lib", (18.0, 18.0), (300.0, 300.0, 300.0))


def test_epaisseur_d_un_montant_par_l_api(document: Any) -> None:
    parts, _ = two_dividers(document)
    furniture_locks.set_member_thickness(parts["D1"], 25)
    document.recompute()
    assert parts["D1"].Thickness.Value == 25
    assert_side_by_side(parts)
    assert stale_or_invalid(document) == []
    assert spans(parts)[-1][2] == pytest.approx(980)


def test_epaisseur_d_un_montant_dans_l_editeur(document: Any) -> None:
    parts, _ = two_dividers(document)
    parts["D1"].Thickness = 25
    document.recompute()
    assert_side_by_side(parts)
    assert stale_or_invalid(document) == []
    assert spans(parts)[-1][2] == pytest.approx(980)


def test_epaisseur_en_deverrouillant(document: Any) -> None:
    parts, _ = two_dividers(document)
    api.set_member_options(parts["S2"], locked=True)
    api.unlock_and_set_thickness(parts["D1"], 25, [parts["S2"]])
    document.recompute()
    assert_side_by_side(parts)
    assert stale_or_invalid(document) == []


# --- B3 : une pièce disparaît, les voisines ne la citent plus ------------------------------


def test_suppression_d_une_piece_membre(document: Any) -> None:
    parts, furniture = row(document, "Cais", (18.0,), (400.0, 600.0))
    name = parts["D1"].Name
    document.removeObject(name)
    document.recompute()
    assert stale_or_invalid(document) == []
    for key in ("JG", "S1", "S2", "JD"):
        assert all(name not in text for _, text in parts[key].ExpressionEngine), key
    furniture.Width = 1162
    document.recompute()
    assert stale_or_invalid(document) == []


def test_retrait_d_une_piece_de_l_ensemble(document: Any) -> None:
    parts, furniture = row(document, "Cais", (18.0,), (400.0, 600.0))
    api.remove_from_furniture([parts["D1"]])
    document.recompute()
    for key in ("JG", "S1", "S2", "JD"):
        assert all(parts["D1"].Name not in text for _, text in parts[key].ExpressionEngine), key
    api.resize_furniture(furniture, width=1162)
    remaining = {k: p for k, p in parts.items() if k != "D1"}
    assert_side_by_side(remaining)
    assert stale_or_invalid(document) == []
    assert spans(remaining)[-1][2] == pytest.approx(1162)
