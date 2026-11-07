# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aimantation d'une pièce membre d'un ensemble (EN-e, E6).

Bogue signalé par jv : « quand je modifie une pièce qui est dans un ensemble, je n'ai pas
d'aimantation ». Cause : les guides d'une pièce hors Std Part étaient lus dans
``Document.RootObjects``, c'est-à-dire les objets que rien ne cite. Les membres d'un ensemble se
citent par leurs expressions (épaisseurs) et par leur lien ``Furniture`` : ils disparaissaient des
guides. Flèche (``magnet``) et poignée de taille (``resize``) lisent les mêmes guides.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import LAYOUT, build_parts

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
magnet = pytest.importorskip("freecad.menuiserie.core.magnet")
guides_module = pytest.importorskip("freecad.menuiserie.features.magnet_guides")
container_module = pytest.importorskip("freecad.menuiserie.features.furniture_container")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
geometry = pytest.importorskip("freecad.menuiserie.core.geometry")

Vec3 = geometry.Vec3
TOLERANCE_MM = 10.0
PER_BOX = 26  # 6 plans, 12 droites, 8 points


def plateau_box(part: Any) -> Any:
    return geometry.Box(
        Vec3(0, 0, 0), Vec3(part.Length.Value, part.Width.Value, part.Thickness.Value)
    )


def hide_all_but_joues(parts: dict[str, Any]) -> None:
    """Seules les joues (citées par les expressions du voile) restent visibles."""
    for mark in ("P", "V"):
        parts[mark].Visibility = False


def test_une_piece_membre_garde_les_guides_de_ses_voisines(document: Any) -> None:
    bureau = build_parts(document)
    plateau = bureau.parts["P"]
    alone = guides_module.collect_guides(plateau, container_module.guide_container(plateau))
    assert len(alone) == 3 * PER_BOX
    api.make_furniture(list(bureau.parts.values()), label="Bureau")
    member = guides_module.collect_guides(plateau, container_module.guide_container(plateau))
    assert member == alone


def test_fleche_aimantee_sur_une_voisine_citee(document: Any) -> None:
    bureau = build_parts(document)
    api.make_furniture(list(bureau.parts.values()), label="Bureau")
    plateau = bureau.parts["P"]
    hide_all_but_joues(bureau.parts)
    memento = drag.begin_drag(plateau)  # met de côté les liaisons de l'atelier
    guides = guides_module.collect_guides(plateau, container_module.guide_container(plateau))
    assert guides, "aucun guide : les joues, citées par le voile, doivent guider le plateau"
    wanted = Vec3(0, 0, 0).with_component(2, 4.0)  # 4 mm au-dessus du contact avec les joues
    result = magnet.magnet(plateau_box(plateau), guides, wanted, TOLERANCE_MM, [2])
    assert result.hits
    assert result.delta.z == pytest.approx(0.0, abs=1e-9)
    drag.move_part(memento, result.delta)
    assert plateau.Placement.Base.z == pytest.approx(720)
    drag.restore(memento)


def test_poignee_de_taille_aimantee_sur_une_voisine_citee(document: Any) -> None:
    bureau = build_parts(document)
    api.make_furniture(list(bureau.parts.values()), label="Bureau")
    plateau = bureau.parts["P"]
    hide_all_but_joues(bureau.parts)
    memento = drag.begin_drag(plateau)
    guides = guides_module.collect_guides(plateau, container_module.guide_container(plateau))
    handle = magnet.Handle(axis=2, at_end=False)  # face du dessous, posée sur les joues
    result = magnet.resize(plateau_box(plateau), handle, 4.0, guides, TOLERANCE_MM)
    assert result.hit is not None
    assert result.size == pytest.approx(30.0)
    assert result.origin_shift.z == pytest.approx(0.0, abs=1e-9)
    drag.resize_part(memento, "Thickness", result.size, result.origin_shift)
    assert plateau.Thickness.Value == pytest.approx(30.0)
    drag.restore(memento)


def test_les_voisines_hors_ensemble_guident_aussi_un_membre(document: Any) -> None:
    bureau = build_parts(document)
    api.make_furniture(list(bureau.parts.values()), label="Bureau")
    sol = document.addObject("Part::Box", "Sol")
    sol.Length, sol.Width, sol.Height = 3000, 3000, 10
    sol.Placement = App.Placement(App.Vector(-1000, -1000, -10), App.Rotation())
    document.recompute()
    joue = bureau.parts["JG"]
    found = guides_module.collect_guides(joue, container_module.guide_container(joue))
    assert any(g.kind is magnet.GuideKind.PLANE and g.axis == 2 for g in found)
    assert set(LAYOUT) == set(bureau.parts)
    assert len(found) >= 4 * PER_BOX
