# SPDX-License-Identifier: LGPL-2.1-or-later
"""Erreurs imprévues pendant un geste sur un membre assemblé, et objets figés gardés dans le Std
Part d'un sous-ensemble (revue de sécurité de la PR #264, ADR 0060 point 6, ADR 0065)."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
member = pytest.importorskip("freecad.menuiserie.features.thickness_member")
furniture_container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
furniture_envelope = pytest.importorskip("freecad.menuiserie.features.furniture_envelope")
furniture_bindings = pytest.importorskip("freecad.menuiserie.features.furniture_bindings")
Vec3 = pytest.importorskip("freecad.menuiserie.core.geometry").Vec3


def _cote_tire(document: Any) -> tuple[Any, Any, Any, dict[str, dict[str, str]]]:
    """Caisson (sous-ensemble du bureau) dont le côté gauche, assemblé en queue d'aronde au
    dessous, est épaissi vers l'extérieur : (caisson, côté, mémento, liaisons d'avant)."""
    from tests.integration.bureau import build_parts
    from tests.integration.test_ensemble_membres import caisson

    desk = build_parts(document)
    box, pieces = caisson(document)
    api.make_furniture([desk.parts["P"], desk.parts["JG"], desk.parts["JD"], box], label="B")
    api.make_dovetail(pieces["CG"], pieces["CB"])
    document.recompute()
    side = pieces["CG"]
    before = {p.Name: dict(furniture_bindings.workshop_expressions(p)) for p in pieces.values()}
    memento = drag.begin_drag(side)
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, -12), lowered=True)
    return box, side, memento, before


def _boom(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("panne simulée")


def test_erreur_imprevue_au_relachement_rend_la_piece_et_les_liaisons(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    box, side, memento, before = _cote_tire(document)
    monkeypatch.setattr(drag, "follow_distances", _boom)
    with pytest.raises(RuntimeError, match="panne simulée"):
        drag.end_drag(memento)
    assert side.Thickness.Value == pytest.approx(18.0)
    pieces = [document.getObject(name) for name in before]
    assert {p.Name: dict(furniture_bindings.workshop_expressions(p)) for p in pieces} == before
    assert furniture_bindings.members_of(box)


def test_echap_rend_la_brute_meme_si_les_liaisons_echouent(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _box, side, memento, _before = _cote_tire(document)
    assert memento.freedom  # liaisons de l'ensemble mises de côté
    monkeypatch.setattr(member.MemberFreedom, "cancel", _boom)
    with pytest.raises(RuntimeError, match="panne simulée"):
        drag.restore(memento)
    assert side.Thickness.Value == pytest.approx(18.0)
    assert side.Placement.isSame(memento.placement, 1e-9)


def test_objet_fige_dans_le_std_part_le_sous_ensemble_n_est_pas_recale(document: Any) -> None:
    box, side, memento, _before = _cote_tire(document)
    drag.restore(memento)
    document.recompute()
    figee = document.addObject("Part::Box", "BoiteFigee")
    furniture_container.std_part_of(box).addObject(figee)
    figee.setPropertyStatus("Placement", "ReadOnly")
    document.recompute()
    assert figee in furniture_envelope.kept_inside(box)
    vue = App.Placement(figee.getGlobalPlacement())
    memento = drag.begin_drag(side)
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, -12), lowered=True)
    drag.end_drag(memento)
    document.recompute()
    assert figee.getGlobalPlacement().isSame(vue, 1e-9)
