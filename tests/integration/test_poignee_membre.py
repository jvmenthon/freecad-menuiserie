# SPDX-License-Identifier: LGPL-2.1-or-later
"""Poignée d'épaisseur d'un membre d'ensemble assemblé (jv, 2026-11-23 ; ADR 0060 point 6) :
tirée vers l'extérieur, la face tirée décide, les voisines liées suivent en direct et la boîte
est recalée ; tirée vers l'intérieur, la rangée absorbe (ADR 0019)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid

App = pytest.importorskip("FreeCAD")
geometry = pytest.importorskip("freecad.menuiserie.core.geometry")
api = pytest.importorskip("freecad.menuiserie.api")
bindings = pytest.importorskip("freecad.menuiserie.features.furniture_bindings")
envelope = pytest.importorskip("freecad.menuiserie.features.furniture_envelope")
reframe = pytest.importorskip("freecad.menuiserie.features.furniture_reframe")
part_drag = pytest.importorskip("freecad.menuiserie.features.part_drag")

pytestmark = pytest.mark.integration

OUTWARD = geometry.Vec3(0, 0, -12)  # côté gauche : axe d'épaisseur vers +X, face basse dehors


def _caisson_a_queues(document: Any) -> tuple[Any, Any, dict[str, Any]]:
    """Bureau ⊃ Caisson ; le dessous (queues) est assemblé au côté gauche (griffes), son bout à
    fleur de la face extérieure du côté : le cas de jv."""
    from tests.integration.bureau import build_parts
    from tests.integration.test_ensemble_membres import caisson

    desk = build_parts(document)
    sub, parts = caisson(document)
    bureau, _ = api.make_furniture(
        [*(desk.parts[m] for m in ("P", "JG", "JD")), sub], label="Bureau"
    )
    document.recompute()
    return bureau, sub, parts


def _globale(part: Any) -> Any:
    """Boîte de ``part`` dans le repère du document (Std Parts compris)."""
    shape = part.Shape.copy()
    shape.Placement = part.getGlobalPlacement()
    return shape.BoundBox


def _liaisons(parts: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {mark: dict(bindings.workshop_expressions(p)) for mark, p in parts.items()}


def test_vers_l_exterieur_la_face_tiree_decide(document: Any) -> None:
    """Le cas de jv : côté du caisson à griffes, dessous à queues traversantes ; tiré vers
    l'extérieur, le côté grandit vers l'extérieur, les queues suivent l'épaisseur (le dessous
    garde sa longueur visible), la boîte du caisson est recalée."""
    _bureau, sub, parts = _caisson_a_queues(document)
    joint = api.make_dovetail(parts["CG"], parts["CB"])
    document.recompute()
    side = parts["CG"]
    inner = _globale(side).XMax
    longueur = parts["CB"].Length.Value
    memento = part_drag.begin_drag(side)
    assert part_drag.resize_part(memento, "Thickness", 30, OUTWARD, lowered=True) == ""
    part_drag.end_drag(memento)
    document.recompute()
    assert side.Thickness.Value == pytest.approx(30.0)
    assert _globale(side).XMax == pytest.approx(inner, abs=1e-6)  # face intérieure immobile
    assert _globale(side).XLength == pytest.approx(30.0, abs=1e-6)
    assert parts["CB"].Length.Value == pytest.approx(longueur)
    assert envelope.frame_of(sub) == envelope.member_envelope(sub)
    assert bindings.workshop_expressions(parts["CB"])  # liaisons reposées
    assert "Invalid" not in joint.State
    assert not stale_or_invalid(document)


def test_voisine_liee_suit_en_direct(document: Any) -> None:
    """Coin à queue d'aronde dans un ensemble : la pièce à griffes, liée par l'atelier, s'allonge
    pendant le geste (aperçu), comme hors ensemble (ADR 0060 point 4), et la boîte suit."""
    from tests.integration.test_epaisseur_cote import corner, holds

    host, guest, joint = corner(document)
    meuble, _ = api.make_furniture([host, guest], "Meuble")
    document.recompute()
    assert bindings.workshop_expressions(host)
    memento = part_drag.begin_drag(guest)
    assert part_drag.resize_part(memento, "Thickness", 30, geometry.Vec3(0, 0, 0)) == ""
    assert host.Length.Value == pytest.approx(412)  # aperçu : suit en direct
    part_drag.end_drag(memento)
    document.recompute()
    assert host.Length.Value == pytest.approx(412)
    assert envelope.frame_of(meuble) == envelope.member_envelope(meuble)
    assert bindings.workshop_expressions(host)
    assert holds(document, joint)


def test_echap_rend_voisines_et_liaisons(document: Any) -> None:
    _bureau, sub, parts = _caisson_a_queues(document)
    api.make_dovetail(parts["CG"], parts["CB"])
    document.recompute()
    avant = _liaisons(parts)
    places = {m: App.Placement(p.Placement) for m, p in parts.items()}
    boite = envelope.frame_of(sub)
    memento = part_drag.begin_drag(parts["CG"])
    part_drag.resize_part(memento, "Thickness", 30, OUTWARD, lowered=True)
    part_drag.restore(memento)
    document.recompute()
    assert _liaisons(parts) == avant
    assert all(p.Placement.isSame(places[m], 1e-9) for m, p in parts.items())
    assert parts["CG"].Thickness.Value == pytest.approx(18.0)
    assert envelope.frame_of(sub) == boite
    assert not stale_or_invalid(document)


def test_relink_refuse_tout_revient(document: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _bureau, sub, parts = _caisson_a_queues(document)
    api.make_dovetail(parts["CG"], parts["CB"])
    document.recompute()
    avant = _liaisons(parts)
    boite = envelope.frame_of(sub)

    def refuse(_furniture: Any) -> Any:
        raise ValueError("cycle simulé")

    monkeypatch.setattr(reframe, "bind_furniture", refuse)
    memento = part_drag.begin_drag(parts["CG"])
    part_drag.resize_part(memento, "Thickness", 30, OUTWARD, lowered=True)
    with pytest.raises(ValueError, match="cycle simulé"):
        part_drag.end_drag(memento)
    document.recompute()
    assert _liaisons(parts) == avant
    assert parts["CG"].Thickness.Value == pytest.approx(18.0)
    assert envelope.frame_of(sub) == boite


def test_vers_l_interieur_la_rangee_absorbe(document: Any) -> None:
    """Face intérieure du côté tirée : la boîte du caisson ne change pas, la face extérieure
    reste en place (ADR 0019)."""
    _bureau, sub, parts = _caisson_a_queues(document)
    side = parts["CG"]
    outer = _globale(side).XMin
    boite = envelope.frame_of(sub)
    memento = part_drag.begin_drag(side)
    assert part_drag.resize_part(memento, "Thickness", 30, geometry.Vec3(0, 0, 0)) == ""
    part_drag.end_drag(memento)
    document.recompute()
    assert side.Thickness.Value == pytest.approx(30.0)
    assert _globale(side).XMin == pytest.approx(outer, abs=1e-6)
    assert envelope.frame_of(sub) == boite
    assert not stale_or_invalid(document)
