# SPDX-License-Identifier: LGPL-2.1-or-later
"""« Fermer le caisson » (ADR 0064) : passe du testeur, valeurs limites et propriétés du noyau.

Tout paramètre accepté doit donner un gabarit constructible (jamais une ``InvalidDimensionsError``
tardive que le panneau ne sait pas afficher) ; les épaisseurs minuscules sont refusées d'avance ;
les pièces ne se recouvrent pas, quel que soit l'avant ou le sens du caisson.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from freecad.menuiserie.core.i18n import TemplatedError
from freecad.menuiserie.core.part_model import MIN_DIMENSION_MM, Dimensions
from freecad.menuiserie.core.templates.closing import check_feasible, closing_layout, wanted_extents
from freecad.menuiserie.core.templates.closing_params import (
    BackJoinery,
    ClosingError,
    ClosingJoinery,
    ClosingParams,
    ClosingRole,
    Element,
)
from tests.unit.aides_fermeture import ANCHOR, layout, params

Span = tuple[float, float]


@pytest.mark.parametrize("name", ["thickness", "opposite_thickness", "back_thickness"])
@pytest.mark.parametrize("value", [0.01, 0.05, 0.099, 1e-9])
def test_epaisseur_sous_la_cote_minimale_refusee_en_citant_le_champ(
    name: str, value: float
) -> None:
    """Sans ce refus, ``closing_layout`` levait une ``InvalidDimensionsError`` que le panneau,
    qui l'appelle pour dessiner le schéma, ne rattrapait pas (aperçu figé, bouton OK périmé)."""
    with pytest.raises(ClosingError) as refused:
        params(**{name: value})
    fields = {"thickness": "côtés", "opposite_thickness": "opposée", "back_thickness": "fond"}
    assert fields[name] in str(refused.value)
    assert "au moins 0,1 mm" in str(refused.value)


@pytest.mark.parametrize("name", ["thickness", "opposite_thickness", "back_thickness"])
def test_epaisseur_de_la_cote_minimale_acceptee_et_constructible(name: str) -> None:
    result = layout(**{name: MIN_DIMENSION_MM, "joinery": ClosingJoinery.NONE})
    assert result.piece("anchor").block.dimensions == ANCHOR


def test_flottants_aux_limites_ne_font_pas_de_cote_invalide() -> None:
    """19999 - 0,1 n'est pas exact en flottant : la cote de la pièce reste valide."""
    result = layout(height=19999, opposite_thickness=0.1, joinery=ClosingJoinery.NONE)
    assert result.piece("opposite").block.dimensions.thickness == pytest.approx(0.1)


GRID_DIMS = ((600, 400, 18), (600, 400, 0.1), (100, 60, 18), (1, 1, 0.5), (19000, 300, 19))
GRID_HEIGHTS = (0.3, 1.5, 37, 720, 19999, 20000, 30000)
GRID_THICKNESSES = (None, 0.01, 0.1, 0.15, 3, 150, 9999)


def test_tout_parametre_accepte_donne_un_gabarit_constructible() -> None:
    """Balayage de cotes limites : refusé par ``ClosingError`` ou entièrement constructible
    (gabarit, puis assemblages : seule une ``TemplatedError`` de J3 est admise)."""
    built = 0
    for dims, height, thick, other, joinery, elements in itertools.product(
        GRID_DIMS,
        GRID_HEIGHTS,
        GRID_THICKNESSES,
        GRID_THICKNESSES[:5],
        (ClosingJoinery.NONE, ClosingJoinery.MITER, ClosingJoinery.RABBET),
        (frozenset(Element), frozenset({Element.OPPOSITE, Element.BACK}), frozenset()),
    ):
        try:
            chosen = ClosingParams(
                Dimensions(*dims),
                "m",
                height=height,
                thickness=thick,
                opposite_thickness=other,
                joinery=joinery,
                elements=elements,
            )
        except ClosingError:
            continue
        result = closing_layout(chosen)  # ne lève jamais pour des paramètres acceptés
        try:
            check_feasible(result)
        except TemplatedError:
            continue
        built += 1
    assert built > 100


def volume(first: tuple[Span, ...], second: tuple[Span, ...]) -> float:
    """Volume commun de deux étendues (X, Y, Z)."""
    total = 1.0
    for (low_a, high_a), (low_b, high_b) in zip(first, second, strict=True):
        total *= max(0.0, min(high_a, high_b) - max(low_a, low_b))
    return total


@pytest.mark.parametrize("role", list(ClosingRole))
@pytest.mark.parametrize("turns", range(4))
@pytest.mark.parametrize("thick_back", [False, True])
@pytest.mark.parametrize("back_joinery", list(BackJoinery))
@pytest.mark.parametrize("joinery", list(ClosingJoinery))
def test_les_pieces_ne_se_recouvrent_jamais_sauf_l_onglet_et_la_feuillure(
    role: ClosingRole,
    turns: int,
    thick_back: bool,
    back_joinery: BackJoinery,
    joinery: ClosingJoinery,
) -> None:
    """Tous éléments créés, quel que soit l'avant (ancre tournée) ou le sens du caisson."""
    result = layout(
        role=role,
        front_turns=turns,
        thick_back=thick_back,
        back_joinery=back_joinery,
        joinery=joinery,
        elements=frozenset(Element),
        height=500,
    )
    extents: dict[str, Any] = {
        piece.key: wanted_extents(result, piece.key) for piece in result.pieces
    }
    for first, second in itertools.combinations(extents, 2):
        common = volume(extents[first], extents[second])
        if common <= 1e-6:
            continue
        mitred = joinery is ClosingJoinery.MITER and {"left", "right"} & {first, second}
        rabbeted = (
            "back" in (first, second) and not thick_back and back_joinery is BackJoinery.RABBET
        )
        assert mitred or rabbeted, (first, second, common)


@pytest.mark.parametrize("turns", range(4))
def test_toutes_les_pieces_restent_dans_l_emprise_de_l_ancre(turns: int) -> None:
    """Largeur et profondeur du caisson sont celles de l'ancre tournée ; rien ne dépasse."""
    result = layout(front_turns=turns, elements=frozenset(Element), height=500)
    width, depth = (600, 400) if turns % 2 == 0 else (400, 600)
    for piece in result.pieces:
        (x_low, x_high), (y_low, y_high), _z = wanted_extents(result, piece.key)
        assert x_low >= -1e-6 and y_low >= -1e-6, piece.key
        assert x_high <= width + 1e-6 and y_high <= depth + 1e-6, piece.key


def test_hauteur_minimale_exacte_acceptee_et_un_micron_en_dessous_refusee() -> None:
    assert layout(height=37, joinery=ClosingJoinery.NONE).piece("left").block.dimensions.length == 1
    with pytest.raises(ClosingError, match="hauteur hors tout"):
        params(height=36.999999)


def test_epaisseur_des_cotes_juste_sous_la_moitie_de_la_plus_petite_cote() -> None:
    result = layout(thickness=199.999, joinery=ClosingJoinery.NONE, height=1000)
    assert result.piece("left").block.dimensions.thickness == pytest.approx(199.999)
    with pytest.raises(ClosingError):
        params(thickness=200)
