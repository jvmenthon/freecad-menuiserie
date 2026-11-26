# SPDX-License-Identifier: LGPL-2.1-or-later
"""Taille et orientation d'un ensemble à la souris, partie pure du dessin (EN-c, ADR 0038,
``gui/drag/drawing.py``) : boîte en transparence, étiquettes de face (ADR 0068), message près de
la souris, cadence de 10 Hz ; et garde-fous de structure (``Target`` sans pivy)."""

from __future__ import annotations

import re

import pytest

from freecad.menuiserie.core.furniture import furniture_layout
from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.magnet import Handle
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.gui.drag.drawing import (
    AXIS_COLORS,
    BOX_COLOR,
    BOX_TRANSPARENCY,
    REFUSAL_COLOR,
    BadgeState,
    Cues,
    Label,
    Layout,
    Throttle,
    build_drawing,
    handle_key,
    pixel_targets,
)
from tests.unit.aides import ROOT, imported_modules

FRAME = Frame(Vec3(10, 20, 30), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
BOX = Box.from_ranges([(0, 1200), (0, 600), (0, 750)])
DRAG = ROOT / "freecad" / "menuiserie" / "gui" / "drag"


def ensemble_layout(*, with_box: bool = True) -> Layout:
    """Mise en page d'un ensemble, comme ``FurnitureTarget.layout`` la construit."""
    found = furniture_layout(BOX, FRAME, 80.0)
    return Layout(
        FRAME,
        BOX,
        found.arrows,
        tuple((h.handle, h.point) for h in found.handles),
        24.0,
        found.rings,
        shows_box=with_box,
    )


def test_boite_en_transparence() -> None:
    drawing = build_drawing(ensemble_layout())
    box = [s for s in drawing.solids if s.color == BOX_COLOR]
    assert len(box) == 1 and len(box[0].faces) == 6
    assert box[0].transparency == BOX_TRANSPARENCY
    assert all(len(face) == 4 for face in box[0].faces)
    edges = next(s for s in drawing.strokes if s.color == BOX_COLOR)
    assert len(edges.lines) == 12
    corners = {p for line in edges.lines for p in line}
    assert len(corners) == 8
    # repère global : le coin bas, avant, gauche est l'origine du repère
    assert Vec3(10, 20, 30) in corners and Vec3(1210, 620, 780) in corners


def test_pas_de_boite_pour_une_piece() -> None:
    drawing = build_drawing(ensemble_layout(with_box=False))
    assert not [s for s in drawing.solids if s.color == BOX_COLOR]
    assert not [s for s in drawing.strokes if s.color == BOX_COLOR]


def test_etiquettes_de_face() -> None:
    """Une étiquette par cote (largeur, profondeur, hauteur de l'ensemble), comme une pièce, et
    un rond sur chacune des six faces ; seule la boîte est pleine."""
    drawing = build_drawing(ensemble_layout())
    assert [b.text for b in drawing.badges] == ["1200", "600", "750"]
    assert [b.axis for b in drawing.badges] == [0, 1, 2]
    assert {b.state for b in drawing.badges} == {BadgeState.NORMAL}
    assert len(drawing.knobs) == 6
    assert [s.color for s in drawing.solids] == [BOX_COLOR]


def test_etiquette_devant_sa_face() -> None:
    layout = ensemble_layout()
    handle = Handle(0, True)
    point = dict(layout.handles)[handle]
    badge = build_drawing(layout).badges[0]  # hors de la vue : étiquette sur la face de fin
    assert badge.position.x - point.x == pytest.approx(1.9 * 24.0)
    assert (badge.position.y, badge.position.z) == (point.y, point.z)


def test_survol_d_une_poignee_en_surbrillance() -> None:
    drawing = build_drawing(ensemble_layout(), handle_key(Handle(1, True)))
    assert [b.state for b in drawing.badges].count(BadgeState.HOVER) == 1
    lit = [s for s in drawing.solids if s.color == AXIS_COLORS[1]]  # face qui bouge allumée
    assert len(lit) == 1 and {p.y for p in lit[0].faces[0]} == {620.0}


def test_poignees_saisissables_a_chaque_face() -> None:
    layout = ensemble_layout()
    targets = pixel_targets(layout, lambda p: (p.x, p.y))
    assert {t.key for t in targets} >= {
        handle_key(Handle(a, e)) for a in range(3) for e in (False, True)
    }


def test_cote_et_message_pres_de_la_souris() -> None:
    note = Label(REFUSAL_COLOR, "1300.0 mm\nrefus", Vec3(1, 2, 3))
    drawing = build_drawing(ensemble_layout(), cues=Cues(note=note))
    assert drawing.labels == (note,)
    assert build_drawing(ensemble_layout()).labels == ()


def test_cadence_de_dix_hertz() -> None:
    cadence = Throttle(10)
    assert cadence.ready(0.0)
    assert not cadence.ready(0.05)
    assert cadence.wait(0.05) == pytest.approx(0.05)
    assert cadence.ready(0.1)


def test_structure_de_la_cible() -> None:
    """``target.py`` et ``furniture_target.py`` ne touchent ni pivy ni Qt (seul ``overlay.py``
    dessine) ; les états ne citent plus l'écriture d'une pièce ou d'un ensemble : tout passe par
    la cible."""
    for name in ("target.py", "furniture_target.py"):
        modules = imported_modules(DRAG / name)
        assert not {m for m in modules if m.split(".")[0] in {"pivy", "PySide"}}
    states = imported_modules(DRAG / "states.py")
    assert not {m for m in states if m.endswith((".part_rotate", ".furniture_drag"))}
    assert "freecad.menuiserie.features.part_drag.move_part" not in states


def test_noms_courts_des_cotes_dans_les_sources() -> None:
    """Pièce : Long./Larg./Ép. ; ensemble : Larg./Prof./Haut. (lus dans les sources : ces
    modules importent FreeCAD)."""
    drag = ROOT / "freecad" / "menuiserie" / "gui" / "drag"

    def names(file: str, constant: str) -> list[str]:
        text = (drag / file).read_text(encoding="utf-8")
        block = text.split(f"{constant}: Final = (", 1)[1].split(")\n", 1)[0]
        return re.findall(r'"Menuiserie", "([^"]+)"', block)

    assert names("target.py", "PART_AXIS_NAMES") == ["Long.", "Larg.", "Ép."]
    assert names("furniture_target.py", "FURNITURE_AXIS_NAMES") == ["Larg.", "Prof.", "Haut."]
