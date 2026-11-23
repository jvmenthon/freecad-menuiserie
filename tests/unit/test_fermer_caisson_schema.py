# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schéma isométrique du panneau « Fermer le caisson » (maquette B, ADR 0064) : projection et clic,
sans Qt."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.templates.closing_params import ClosingRole, Element
from freecad.menuiserie.core.templates.closing_schema import (
    Face,
    centroid,
    click_point,
    fit,
    hit_test,
    project,
    schema_faces,
)
from tests.unit.aides_fermeture import layout

KEYS = ["anchor", "left", "right", "back", "front", "opposite"]
EVERYTHING = frozenset(Element)
SIZE = (420.0, 320.0)


def faces(role: ClosingRole = ClosingRole.BOTTOM) -> tuple[Face, ...]:
    """Faces ajustées à ``SIZE`` de tous les éléments (l'avant compris)."""
    return fit(schema_faces(layout(role=role, elements=EVERYTHING)), *SIZE)


def enabled(*extra: str) -> set[str]:
    """Éléments activés par défaut (ancre, côtés, fond, pièce opposée) et ``extra``."""
    return {"anchor", "left", "right", "back", "opposite", *extra}


def test_projection_isometrique() -> None:
    origin = project(Vec3(0, 0, 0))
    assert origin == (0.0, 0.0)
    x, y, z = project(Vec3(1, 0, 0)), project(Vec3(0, 1, 0)), project(Vec3(0, 0, 1))
    assert x[0] > 0 and x[1] > 0
    assert y[0] > 0 and y[1] < 0  # Y (profondeur) : à droite et vers le haut
    assert z[0] == 0 and z[1] < 0  # Z : vers le haut
    assert math.hypot(*x) == pytest.approx(math.hypot(*y))  # axes de même longueur à l'écran


def test_trois_faces_par_element_dans_l_ordre_de_l_arriere_vers_l_avant() -> None:
    result = schema_faces(layout(elements=EVERYTHING))
    assert sorted({f.element for f in result}) == sorted(KEYS)
    assert all(sum(1 for f in result if f.element == key) == 3 for key in KEYS)
    assert {f.side for f in result} == {"top", "front", "right"}
    depths = [f.depth for f in result]
    assert depths == sorted(depths)
    assert result[-1].element in {"opposite", "right", "front"}  # le plus proche de l'observateur
    assert result[0].element in {"left", "back", "anchor"}


def test_les_polygones_ont_une_aire() -> None:
    assert all(f.area() > 0 for f in schema_faces(layout(elements=EVERYTHING)))


def test_ajustement_garde_le_dessin_dans_le_cadre_et_les_proportions() -> None:
    raw = schema_faces(layout(elements=EVERYTHING))
    placed = fit(raw, *SIZE, margin=10.0)
    points = [p for f in placed for p in f.points]
    assert min(p[0] for p in points) >= 10.0 - 1e-9
    assert max(p[0] for p in points) <= SIZE[0] - 10.0 + 1e-9
    assert min(p[1] for p in points) >= 10.0 - 1e-9
    assert max(p[1] for p in points) <= SIZE[1] - 10.0 + 1e-9
    ratio = [a.area() / b.area() for a, b in zip(placed, raw, strict=True)]
    assert max(ratio) == pytest.approx(min(ratio))  # même échelle partout


def test_ajustement_d_un_cadre_minuscule_ou_d_un_dessin_vide() -> None:
    assert fit((), 100, 100) == ()
    tiny = fit(schema_faces(layout()), 0.0, -5.0)  # cadre nul : ne plante pas, reste fini
    assert all(math.isfinite(c) for f in tiny for p in f.points for c in p)


@pytest.mark.parametrize("role", list(ClosingRole))
@pytest.mark.parametrize("element", ["anchor", "left", "right", "opposite", "back"])
def test_un_clic_sur_un_element_active_le_designe(role: ClosingRole, element: str) -> None:
    shown = faces(role)
    point = click_point(shown, enabled(), element)
    assert point is not None
    assert hit_test(shown, enabled(), point) == element


def test_clic_hors_du_dessin() -> None:
    assert hit_test(faces(), enabled(), (1.0, 1.0)) is None
    assert hit_test(faces(), enabled(), (SIZE[0] - 1.0, SIZE[1] - 1.0)) is None
    assert hit_test((), enabled(), (10.0, 10.0)) is None


def test_un_element_desactive_ne_cache_pas_les_autres() -> None:
    shown = faces()
    # Avant désactivé : il couvre toute la façade, mais un clic y désigne l'élément activé derrière.
    centre = centroid(max((f for f in shown if f.element == "front"), key=Face.area))
    assert hit_test(shown, enabled(), centre) != "front"
    assert hit_test(shown, enabled(), centre) in enabled()
    # Sans rien d'activé derrière, c'est lui que l'on touche.
    assert hit_test(shown, {"front"}, centre) == "front"


def test_l_avant_desactive_n_a_aucun_point_cliquable_sur_le_dessin() -> None:
    # Il se réactive par sa case de la légende ou par son étiquette (voir le widget).
    assert click_point(faces(), enabled(), "front") is None
    assert click_point(faces(), enabled("front"), "front") is not None


def test_element_inconnu() -> None:
    assert click_point(faces(), enabled(), "toit") is None


def test_l_avant_actif_passe_devant() -> None:
    shown = faces()
    centre = centroid(max((f for f in shown if f.element == "front"), key=Face.area))
    assert hit_test(shown, enabled("front"), centre) == "front"


def test_cliquer_deux_fois_au_meme_point_est_deterministe() -> None:
    shown = faces()
    point = click_point(shown, enabled(), "left")
    assert point is not None
    assert {hit_test(shown, enabled(), point) for _ in range(5)} == {"left"}
