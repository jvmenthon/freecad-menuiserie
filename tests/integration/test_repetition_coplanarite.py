# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faces des copies d'une répétition au ras d'une face voisine (jv, 2026-11-14, ADR 0058)."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")
coplanar = pytest.importorskip("freecad.menuiserie.features.repeat_coplanar")
guides_module = pytest.importorskip("freecad.menuiserie.features.magnet_guides")


def shelf(doc: Any) -> Any:
    """Tablette de 300 x 40 x 22 à l'origine."""
    part = api.make_wood_part(300, 40, 22, "chene", doc=doc)
    doc.recompute()
    return part


def neighbour(doc: Any, z: float) -> Any:
    """Cube de 100 mm (autre atelier) loin sur Y, dessous à ``z`` : dessus à ``z + 100``."""
    box = doc.addObject("Part::Box", "Voisin")
    box.Length = box.Width = box.Height = 100
    box.Placement = App.Placement(App.Vector(500, 1000, z), App.Rotation())
    doc.recompute()
    return box


def repeated(doc: Any, part: Any, step: float, axis: str = "Z") -> Any:
    rep = api.make_repeat([part], api.RepeatParams(count=2, step=step, axis=axis))
    doc.recompute()
    return rep


def shown(found: Any, axis: int = 2) -> list[tuple[float, int]]:
    return sorted((round(g.position(axis), 6), g.sign) for g in found)


def test_dessus_de_la_copie_au_ras_du_dessus_voisin(document: Any) -> None:
    part = shelf(document)
    neighbour(document, 100)  # dessus à 200
    rep = repeated(document, part, 178.0)  # copie de z = 178 à 200
    copies = repeat.copies_of(rep)
    planes = coplanar.RepeatPlanes([part], copies)
    assert shown(planes.coplanar(copies, (2,))) == [(200.0, 1), (200.0, 1)]
    assert planes.coplanar(copies, (0, 1)) == ()  # ni X ni Y au ras


def test_pas_qui_ne_tombe_pas_au_ras(document: Any) -> None:
    part = shelf(document)
    neighbour(document, 100)
    rep = repeated(document, part, 150.0)
    copies = repeat.copies_of(rep)
    assert coplanar.RepeatPlanes([part], copies).coplanar(copies, (2,)) == ()


def test_sources_et_copies_ne_sont_pas_des_voisines(document: Any) -> None:
    """Copie posée sur la source (pas de 22 : dessous de la 1re copie = dessus de la source) : ni la
    source ni l'autre copie ne comptent."""
    part = shelf(document)
    rep = repeated(document, part, 22.0)
    copies = repeat.copies_of(rep)
    assert coplanar.RepeatPlanes([part], copies).coplanar(copies, (2,)) == ()


def test_voisine_cachee_ignoree(document: Any) -> None:
    part = shelf(document)
    neighbour(document, 100).Visibility = False
    rep = repeated(document, part, 178.0)
    copies = repeat.copies_of(rep)
    assert coplanar.RepeatPlanes([part], copies).coplanar(copies, (2,)) == ()


def test_dans_un_std_part_tourne(document: Any) -> None:
    """Axes de la répétition : ceux du Std Part de la source, tourné autour de X (son Z est le
    -Y du document)."""
    container = document.addObject("App::Part", "Meuble")
    container.Placement = App.Placement(
        App.Vector(1000, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90)
    )
    part = shelf(document)
    container.addObject(part)
    box = neighbour(document, 100)
    container.addObject(box)
    document.recompute()
    rep = repeated(document, part, 178.0)
    copies = repeat.copies_of(rep)
    planes = coplanar.RepeatPlanes([part], copies)
    assert shown(planes.coplanar(copies, (2,))) == [(200.0, 1), (200.0, 1)]


def test_axes_repetes() -> None:
    axis = pytest.importorskip("freecad.menuiserie.core.repeat").RepeatAxis
    axes = [axis.Z, axis.X, axis.Z]
    assert coplanar.axis_indices(axes) == (2, 0)


def test_sans_source_refuse() -> None:
    with pytest.raises(ValueError):
        coplanar.RepeatPlanes([], [])


def test_faces_planes_dans_un_repere(document: Any) -> None:
    part = shelf(document)
    found = guides_module.plane_guides([part], App.Placement())
    assert shown([g for g in found if g.axis == 2]) == [(0.0, -1), (22.0, 1)]
    assert len(found) == 6
