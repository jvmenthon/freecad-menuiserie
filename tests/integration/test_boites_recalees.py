# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boîtes toujours recalées sur leurs membres, sous-ensembles compris (ADR 0065) : pièce
déplacée dans un sous-ensemble, sous-ensemble imbriqué déplacé, retour arrière si l'ensemble ne
peut pas être relié."""

from __future__ import annotations

from typing import Any

import pytest

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
envelope = pytest.importorskip("freecad.menuiserie.features.furniture_envelope")
part_drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
reframe = pytest.importorskip("freecad.menuiserie.features.furniture_reframe")
bindings = pytest.importorskip("freecad.menuiserie.features.furniture_bindings")
geometry = pytest.importorskip("freecad.menuiserie.core.geometry")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")

pytestmark = pytest.mark.integration


def _meuble(document: Any) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Bureau ⊃ Caisson ⊃ Fond (le dessous seul) : (bureau, caisson, fond, pièces du caisson)."""
    from tests.integration.bureau import build_parts
    from tests.integration.test_ensemble_membres import caisson

    desk = build_parts(document)
    sub, parts = caisson(document)
    inner, _ = api.make_furniture([parts["CB"]], label="Fond")
    document.recompute()
    bureau, _ = api.make_furniture(
        [*(desk.parts[mark] for mark in ("P", "JG", "JD")), sub], label="Bureau"
    )
    document.recompute()
    return bureau, sub, inner, parts


def _ajustee(furniture: Any) -> None:
    """Boîte = enveloppe des membres ; ``Origin`` nul pour un sous-ensemble."""
    assert envelope.frame_of(furniture) == envelope.member_envelope(furniture)
    if api.furniture_of(furniture) is not None:
        assert envelope.frame_of(furniture).min == geometry.Vec3(0.0, 0.0, 0.0)


def _globaux(parts: dict[str, Any]) -> dict[str, Any]:
    return {mark: App.Placement(part.getGlobalPlacement()) for mark, part in parts.items()}


def _memes(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return all(first[mark].isSame(second[mark], 1e-6) for mark in first)


def test_meuble_imbrique_ajuste_au_depart(document: Any) -> None:
    bureau, sub, inner, _ = _meuble(document)
    for level in (inner, sub, bureau):
        _ajustee(level)


def test_piece_deplacee_hors_du_sous_ensemble_recale_toute_la_chaine(document: Any) -> None:
    bureau, sub, inner, parts = _meuble(document)
    hauteur = sub.Height.Value
    memento = part_drag.begin_drag(parts["CB"])
    part_drag.move_part(memento, geometry.Vec3(0.0, 0.0, -100.0))
    part_drag.end_drag(memento)
    document.recompute()
    vus = _globaux(parts)
    assert sub.Height.Value == pytest.approx(hauteur + 100.0)
    for level in (inner, sub, bureau):
        _ajustee(level)
    document.recompute()  # rien ne bouge au recalcul : les liaisons suivent la géométrie
    assert _memes(vus, _globaux(parts))


def test_sous_ensemble_imbrique_deplace_recale_ses_parents(document: Any) -> None:
    bureau, sub, inner, parts = _meuble(document)
    assert api.move_furniture(inner, (0, 0, -100))
    document.recompute()
    vus = _globaux(parts)
    assert vus["CB"].Base.z == pytest.approx(300.0)
    for level in (inner, sub, bureau):
        _ajustee(level)
    assert api.move_furniture(inner, (0, 0, 100))  # ramené : le caisson retrouve sa taille
    document.recompute()
    assert sub.Height.Value == pytest.approx(300.0)
    for level in (inner, sub, bureau):
        _ajustee(level)


def test_liaison_impossible_rend_boites_positions_et_liaisons(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bureau, sub, inner, parts = _meuble(document)
    memento = part_drag.begin_drag(parts["CB"])
    part_drag.move_part(memento, geometry.Vec3(0.0, 0.0, -100.0))
    chain = (inner, sub, bureau)
    boites = [envelope.frame_of(level) for level in chain]
    liaisons = [dict(bindings.workshop_expressions(obj)) for obj in (*parts.values(), *chain)]
    vus = _globaux(parts)
    std = [App.Placement(container.std_part_of(level).Placement) for level in chain]
    appels = []
    vraie = reframe.bind_furniture

    def echoue_au_parent(furniture: Any) -> Any:
        appels.append(furniture.Label)
        if furniture is bureau:
            raise ValueError("cycle")
        return vraie(furniture)

    monkeypatch.setattr(reframe, "bind_furniture", echoue_au_parent)
    with pytest.raises(ValueError):
        reframe.relink_framed(inner)
    assert appels == ["Fond", "Caisson", "Bureau"]
    assert [envelope.frame_of(level) for level in chain] == boites
    assert [dict(bindings.workshop_expressions(o)) for o in (*parts.values(), *chain)] == liaisons
    assert _memes(vus, _globaux(parts))
    assert all(
        container.std_part_of(level).Placement.isSame(placement, 1e-9)
        for level, placement in zip(chain, std, strict=True)
    )
    part_drag.restore(memento)
