# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce en bois : liste de débit, assemblages et ensembles aux cas limites (relecture du jalon).

Deux solides identiques d'une forme importée, formes différentes de même encombrement, pièce
tournée de 30°, volume à acheter d'une forme ronde, annuler / rétablir et suppression de la source
d'une pièce assemblée, pièce en bois tournée dans un ensemble.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.pieces_galbees import (
    GUEST,
    curved_rail,
    expected_volume,
    machined_volume,
    placed,
    shaped,
    twin_gains,
    wood_at,
)
from tests.integration.test_piece_en_bois import TOLERANCE, box, imported

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")

SIZE = (200.0, 100.0, 50.0)
TURN_30 = App.Rotation(App.Vector(0, 0, 1), 30)


def drilled_box(doc: Any) -> Any:
    """Boîte de ``SIZE`` percée d'un trou rond de part en part : même encombrement, autre forme."""
    block = box(doc, SIZE, "Plein")
    tool = doc.addObject("Part::Cylinder", "Foret")
    tool.Radius, tool.Height = 10.0, SIZE[2]
    tool.Placement = App.Placement(App.Vector(100, 50, 0), App.Rotation())
    cut = doc.addObject("Part::Cut", "Perce")
    cut.Base, cut.Tool = block, tool
    doc.recompute()
    return cut


# --- C4 : regroupement -----------------------------------------------------------------------


def test_deux_solides_identiques_d_une_forme_importee_regroupes(document: Any) -> None:
    first, second = Part.makeBox(*SIZE), Part.makeBox(*SIZE)
    second.translate(App.Vector(400, 0, 0))
    source = imported(document, first, second)
    parts = api.make_shaped_parts(source)
    document.recompute()
    assert [part.SolidIndex for part in parts] == [0, 1]
    assert parts[0].SolidSignature == parts[1].SolidSignature
    [line] = api.cut_list_of(document).lines
    assert line.quantity == 2


def test_meme_encombrement_formes_differentes_non_regroupees(document: Any) -> None:
    plain = api.make_shaped_part(box(document, SIZE, "Boite"))
    drilled = api.make_shaped_part(drilled_box(document))
    document.recompute()
    assert (plain.Length.Value, plain.Width.Value, plain.Thickness.Value) == pytest.approx(
        (drilled.Length.Value, drilled.Width.Value, drilled.Thickness.Value)
    )
    lines = api.cut_list_of(document).lines
    assert sorted(line.quantity for line in lines) == [1, 1]


def test_jumelle_tournee_de_30_degres_regroupee(document: Any) -> None:
    first = api.make_shaped_part(box(document, SIZE, "A"))
    second = api.make_shaped_part(box(document, SIZE, "B"))
    second.Placement = App.Placement(App.Vector(500, 300, 0), TURN_30)
    document.recompute()
    [line] = api.cut_list_of(document).lines
    assert line.quantity == 2
    assert first.Shape.Volume == pytest.approx(second.Shape.Volume)


# --- C2 : volume à acheter -------------------------------------------------------------------


def test_volume_a_acheter_d_une_forme_ronde_est_celui_de_l_encombrement(document: Any) -> None:
    rod = document.addObject("Part::Cylinder", "Rond")
    rod.Radius, rod.Height = 20.0, 500.0
    document.recompute()
    part = api.make_shaped_part(rod, mark="R1")
    document.recompute()
    [line] = api.cut_list_of(document).lines
    assert (line.finished.length, line.finished.width, line.finished.thickness) == pytest.approx(
        (500.0, 40.0, 40.0), abs=0.01
    )
    assert line.volume_m3() == pytest.approx(500.0 * 40.0 * 40.0 / 1e9, rel=1e-6)
    assert part.Shape.Volume / 1e9 < line.volume_m3()  # on achète la planche, pas le rond


# --- E1, E2 : pièce en bois tournée de 30° assemblée ------------------------------------------


def test_hote_tourne_de_30_degres(document: Any, vue_rapport: Any) -> None:
    host = shaped(curved_rail(document), "G")
    host.Placement = App.Placement(App.Vector(100, 50, 0), TURN_30)
    document.recompute()
    guest = wood_at(document, GUEST, placed(host.Placement, 300, 0, 10, -90), "T")
    api.make_mortise_tenon(host, guest)
    gains = twin_gains(document, host, guest)
    document.recompute()
    machined = api.machined_part_of(host)
    assert machined.Placement.isSame(host.Placement, 1e-6)
    assert machined_volume(host) == pytest.approx(expected_volume(host, gains[0]), rel=1e-6)
    assert vue_rapport.de_niveau("Warning") == []
    assert stale_or_invalid(document) == []


def host_and_guest(document: Any) -> tuple[Any, Any]:
    """Hôte (pièce en bois d'une boîte) et invitée (pièce de bois) en bout contre le chant."""
    host = api.make_shaped_part(box(document, (720.0, 95.0, 45.0), "SourceHote"), mark="H")
    guest = wood_at(document, GUEST, placed(host.Placement, 300, 0, 10, -90), "T")
    return host, guest


def test_annuler_retablir_l_assemblage(document: Any) -> None:
    document.UndoMode = 1
    host, guest = host_and_guest(document)
    count = len(document.Objects)
    document.openTransaction("Assembler")
    joint = api.make_mortise_tenon(host, guest)
    document.commitTransaction()
    name, volume = joint.Name, machined_volume(host)
    document.undo()
    document.recompute()
    assert document.getObject(name) is None
    assert api.machined_part_of(host) is None
    assert len(document.Objects) == count
    document.redo()
    document.recompute()
    assert document.getObject(name) is not None
    assert machined_volume(host) == pytest.approx(volume, rel=1e-6)
    assert stale_or_invalid(document) == []


def test_source_supprimee_d_une_piece_assemblee_puis_annulation(document: Any) -> None:
    document.UndoMode = 1
    host, guest = host_and_guest(document)
    api.make_mortise_tenon(host, guest)
    document.recompute()
    source_name, volume = host.Source.Name, machined_volume(host)
    document.openTransaction("Supprimer la source")
    document.removeObject(source_name)
    document.commitTransaction()
    document.recompute()  # aucune exception Python : la pièce et son assemblage sont en erreur
    assert "Invalid" in host.State
    document.undo()
    document.recompute()
    assert stale_or_invalid(document) == []
    assert machined_volume(host) == pytest.approx(volume, rel=1e-6)


# --- F1 : pièce en bois tournée dans un ensemble -----------------------------------------------


def test_piece_en_bois_tournee_dans_un_ensemble(document: Any) -> None:
    top = api.make_wood_part(1200, 600, 30, "chene", mark="Plateau", doc=document)
    top.Placement = App.Placement(App.Vector(0, 0, 720), App.Rotation())
    source = box(document, (45.0, 95.0, 720.0), "SourcePied")
    source.Placement = App.Placement(App.Vector(100, 400, 0), TURN_30)
    document.recompute()
    leg = api.make_shaped_part(source, mark="Pied")
    furniture, _notices = api.make_furniture([top, leg], label="Table")
    sizes = (leg.Length.Value, leg.Width.Value, leg.Thickness.Value)
    rotation = leg.Placement.Rotation
    api.resize_furniture(furniture, depth=800)
    document.recompute()
    assert (leg.Length.Value, leg.Width.Value, leg.Thickness.Value) == pytest.approx(sizes)
    assert leg.Placement.Rotation.isSame(rotation, 1e-9)  # déplacée, jamais tournée ni étirée
    assert source.ExpressionEngine == []
    assert {path.lstrip(".") for path, _text in leg.ExpressionEngine} <= {
        "Placement.Base.x",
        "Placement.Base.y",
        "Placement.Base.z",
    }
    assert stale_or_invalid(document) == []
    assert leg.Shape.Volume == pytest.approx(45.0 * 95.0 * 720.0, rel=TOLERANCE)
