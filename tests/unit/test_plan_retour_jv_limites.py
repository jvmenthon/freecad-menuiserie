# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans cotés, retour de jv du 2026-11-13 : cas limites des noms d'usinage, des lignes propres
aux assemblages, des chaînes de cotes de détail et de la bande des cotes (revue testeur de la
PR #247, issue #153, ADR 0053)."""

from __future__ import annotations

import itertools
import math

import pytest

from freecad.menuiserie.core.drawing import (
    NAMES,
    MachiningKind,
    Orientation,
    PageSize,
    bevel_line,
    capped,
    chain_segments,
    joint_note_lines,
    machining_lines,
    machining_name,
    machinings,
    notes_layout,
    overall_layout,
    page_size,
    slant_angle,
)
from freecad.menuiserie.core.drawing._layout import MARGIN_MM
from freecad.menuiserie.core.geometry import Axis, Box, Cylinder, Vec3
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.dovetail import DovetailParams, DovetailValues
from freecad.menuiserie.core.joints.dowels import DowelValues
from tests.unit.aides_assemblages import dovetail_corner

NOTE_SIZE = 3.5  # hauteur du texte du tableau (features/drawing_views.NOTE_SIZE_MM)
PAGES = (
    page_size("A3"),
    page_size("A3", Orientation.PORTRAIT),
    page_size("A4"),
    page_size("A4", Orientation.PORTRAIT),
)
GROUPS = ("host_cuts", "host_additions", "guest_cuts", "guest_trims", "guest_additions")


def _text(template: str, values: dict[str, str]) -> str:
    """Ligne écrite comme le fait ``translated`` (sans traduction)."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def _dovetail(count: int = 3, angle: float = 10.0) -> DovetailValues:
    return DovetailValues(count, 6.0, angle, 42.0, 36.7, ())


# --- Noms d'usinage ------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(JointKind))
@pytest.mark.parametrize("group", GROUPS)
def test_nom_connu_ou_generique_pour_chaque_type_et_groupe(kind: JointKind, group: str) -> None:
    name = machining_name(kind, group)
    assert name == "" or name in NAMES


def test_noms_au_singulier_et_au_pluriel_differents() -> None:
    for key, (one, many) in NAMES.items():
        assert one and many and one != many, key


def test_mi_bois_des_deux_pieces() -> None:
    size = (600.0, 80.0, 22.0)
    cut = Box(Vec3(100, 0, 11), Vec3(180, 80, 22))
    for group in ("host_cuts", "guest_cuts"):
        name = machining_name(JointKind.HALF_LAP, group)
        (item,) = machinings([("Mi-bois", cut, MachiningKind.CUT, name)], size)
        ((_, values),) = machining_lines([item])
        assert values["name"] == "entaille à mi-bois"
        assert values["depth"] == "11"


def test_feuillure_nommee() -> None:
    size = (600.0, 300.0, 18.0)
    rabbet = Box(Vec3(0, 290, 9), Vec3(600, 300, 18))
    name = machining_name(JointKind.RABBET, "host_cuts")
    (item,) = machinings([("Feuillure", rabbet, MachiningKind.CUT, name)], size)
    ((_, values),) = machining_lines([item])
    assert values["name"] == "feuillure"


def test_percages_de_taquets_au_pluriel() -> None:
    size = (1800.0, 300.0, 18.0)
    holes = [
        Cylinder(Vec3(x, 37, 18), Axis.Z_NEG, 2.5, 10.0)
        for x in (100.0, 132.0, 164.0, 196.0, 228.0)
    ]
    name = machining_name(JointKind.SHELF_PINS, "host_cuts")
    items = machinings([("Taquets", hole, MachiningKind.CUT, name) for hole in holes], size)
    ((template, values),) = machining_lines(items)
    assert "Ø" in template
    assert values["name"] == "perçages de taquet"
    assert values["count"] == "5"
    assert values["positions"].endswith("; …")  # plus de quatre positions


def test_forme_non_cylindrique_garde_son_nom_de_percage() -> None:
    """Un logement de taquet carré reste un enlèvement nommé, pas un perçage sans diamètre."""
    box = Box(Vec3(10, 10, 8), Vec3(15, 15, 18))
    (item,) = machinings([("T", box, MachiningKind.CUT, "pin_hole")], (600.0, 80.0, 18.0))
    assert item.kind is MachiningKind.CUT and item.name == "pin_hole"


def test_cylindre_nomme_autrement_reste_un_percage() -> None:
    hole = Cylinder(Vec3(50, 40, 22), Axis.Z_NEG, 4.0, 12.0)
    (item,) = machinings([("T", hole, MachiningKind.CUT, "mortise")], (600.0, 80.0, 22.0))
    assert item.name == "hole"


def test_piece_sans_assemblage() -> None:
    assert machining_lines(machinings([], (600.0, 80.0, 22.0))) == []


def test_queues_sur_l_hote_l_invitee_porte_des_griffes() -> None:
    """DÉFAUT (majeur) : avec « queues sur l'hôte », le plan ajoute des griffes à l'invitée et
    taille leurs logements dans l'hôte. Le tableau ne doit pas les appeler « queues » ni
    « logements de queue » : le menuisier couperait les queues sur la mauvaise pièce."""
    host, guest = dovetail_corner()
    plan = strategy_for(JointKind.DOVETAIL).plan(host, guest, DovetailParams(tails_on_host=True))
    assert plan.guest_additions  # des griffes, ajoutées à l'invitée
    guest_name = machining_name(JointKind.DOVETAIL, "guest_additions")
    host_name = machining_name(JointKind.DOVETAIL, "host_cuts")
    assert guest_name != "tail", "les griffes de l'invitée sont appelées « queues »"
    assert host_name != "socket", "les logements de griffe sont appelés « logements de queue »"


def test_positions_dans_l_ordre_des_cotes() -> None:
    """DÉFAUT (mineur, déjà présent avant la PR, plus visible depuis le repérage le long du
    bout) : les positions sont triées comme des textes, « y 102; y 54; y 6 »."""
    tails = [Box(Vec3(450, y, 0), Vec3(465, y + 42, 15)) for y in (6.0, 54.0, 102.0)]
    items = machinings(
        [("Q", tail, MachiningKind.ADDED, "tail") for tail in tails], (450.0, 150.0, 15.0)
    )
    ((_, values),) = machining_lines(items)
    assert values["positions"] == "y 6; y 54; y 102"


# --- Lignes propres aux assemblages -------------------------------------------------------------


def test_queue_d_aronde_sans_angle_sans_ligne() -> None:
    assert joint_note_lines("Q", _dovetail(angle=0.0), is_host=False) == []


@pytest.mark.parametrize(("angle", "ratio"), [(14.04, "4"), (7.13, "8"), (9.46, "6")])
def test_pente_usuelle_des_queues(angle: float, ratio: str) -> None:
    ((_, line),) = joint_note_lines("Q", _dovetail(angle=angle), is_host=False)
    assert line["ratio"] == ratio


def test_ligne_de_la_queue_identique_pour_l_hote_et_l_invitee() -> None:
    host = joint_note_lines("Q", _dovetail(), is_host=True)
    guest = joint_note_lines("Q", _dovetail(), is_host=False)
    assert host == guest


def test_une_seule_queue_au_singulier() -> None:
    """DÉFAUT (mineur) : « 1 queues de 42 en pointe »."""
    ((template, line),) = joint_note_lines("Q", _dovetail(count=1), is_host=False)
    assert "1 queues" not in _text(template, line)


def test_un_seul_tourillon_au_singulier() -> None:
    """DÉFAUT (mineur) : « 1 tourillons Ø 8 »."""
    values = DowelValues(8.0, 35.0, 20.0, 1, 40.0, 11.0, 1.0, (40.0,))
    ((template, line),) = joint_note_lines("T", values, is_host=True)
    assert "1 tourillons" not in _text(template, line)


def test_bout_en_biais_lame_inclinee_seulement() -> None:
    line = bevel_line("T", (0, -1), (0.0, 15.0))
    assert line is not None
    assert (line[1]["end"], line[1]["cut"], line[1]["tilt"]) == ("bout gauche", "0", "15")


def test_bout_presque_d_equerre_sans_ligne() -> None:
    assert bevel_line("T", (0, 1), (0.04, -0.0)) is None


def test_lignes_d_angle_gardees_dans_le_tableau_d_un_cote_de_tiroir() -> None:
    """DÉFAUT (majeur) : côté de tiroir à queues aux deux bouts et rainure de fond. Les lignes
    propres aux assemblages viennent après les usinages et sont les premières coupées par la
    limite du tableau : l'angle des queues, demandé par jv, disparaît (A3 : une des deux lignes,
    A4 portrait : les deux), remplacé par « … et 1 autres usinages »."""
    size = (450.0, 150.0, 15.0)
    items = []
    for label, low, high in (("Q avec « Façade »", -15.0, 0.0), ("Q avec « Dos »", 450.0, 465.0)):
        for y in (6.0, 54.0, 102.0):
            tail = Box(Vec3(low, y, 0), Vec3(high, y + 42, 15))
            items.append((label, tail, MachiningKind.ADDED, "tail"))
    groove = Box(Vec3(0, 10, 0), Vec3(450, 16, 8))
    items.append(("Rainure avec « Fond »", groove, MachiningKind.CUT, "groove"))
    notes = [
        *joint_note_lines("Q avec « Façade »", _dovetail(), is_host=False),
        *joint_note_lines("Q avec « Dos »", _dovetail(), is_host=False),
    ]
    rows = [*machining_lines(machinings(items, size)), *notes]
    lines = ["Usinages :"] + [_text(template, values) for template, values in rows]
    for page in PAGES:
        wrapped, _ = notes_layout(page, lines, NOTE_SIZE)
        kept = capped(wrapped, "… et {count} autres usinages")
        angles = [line for line in kept if "°" in line]
        assert len(angles) == 2, (page, kept)


# --- Chaînes de cotes de détail ------------------------------------------------------------------


def test_chaine_points_confondus() -> None:
    """DÉFAUT (mineur) : un segment de moins de 0,05 mm retiré en tête de chaîne la fait
    commencer à 0,02 au lieu de 0 (écart minimal nul ou très petit)."""
    assert chain_segments([0, 0, 0.0001, 1000, 1000.0004], min_gap=10) == []
    assert chain_segments([5, 5, 5], min_gap=10) == []
    assert chain_segments([0, 0.02, 500, 1000], min_gap=0) == [(0, 500), (500, 1000)]


def test_chaine_ecart_minimal_plus_grand_que_l_ouvrage() -> None:
    assert chain_segments([0, 100, 200, 300], min_gap=1000) == []


def test_chaine_point_proche_de_l_extremite_fusionne() -> None:
    assert chain_segments([0, 500, 995, 1000], min_gap=10) == [(0, 500), (500, 1000)]


def test_chaine_ouvrage_hors_de_l_origine() -> None:
    assert chain_segments([-600, -578, 600, 578], min_gap=10) == [
        (-600, -578),
        (-578, 578),
        (578, 600),
    ]


def test_chaine_beaucoup_de_pieces() -> None:
    """Étagère à 200 lames de 18 mm espacées de 2 mm : la chaîne reste lisible (segments au
    moins de l'écart minimal, sauf le dernier), continue et de bout en bout."""
    points = [value for i in range(200) for value in (i * 20.0, i * 20.0 + 18.0)]
    segments = chain_segments(points, min_gap=15)
    assert segments[0][0] == 0 and segments[-1][1] == pytest.approx(199 * 20 + 18)
    assert all(a[1] == b[0] for a, b in itertools.pairwise(segments))
    assert all(high - low >= 15 for low, high in segments[:-1])


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_chaine_ignore_les_points_non_finis(bad: float) -> None:
    """DÉFAUT (mineur) : une valeur infinie (boîte englobante vide ou abîmée) donne une cote
    infinie au lieu d'être ignorée."""
    assert chain_segments([0, 22, bad, 700, 722], min_gap=10) == [
        (0, 22),
        (22, 700),
        (700, 722),
    ]


@pytest.mark.parametrize(
    ("horizontal", "vertical", "expected"),
    [
        (1.0, math.tan(math.radians(0.4)), None),
        (1.0, math.tan(math.radians(0.6)), 0.6),
        (math.tan(math.radians(0.4)), 1.0, None),
        (-1.0, -1.0, 45.0),
        (1e-9, 0.0, None),
    ],
)
def test_angle_aux_seuils(horizontal: float, vertical: float, expected: float | None) -> None:
    angle = slant_angle(horizontal, vertical)
    if expected is None:
        assert angle is None
    else:
        assert angle == pytest.approx(expected)


# --- Bande des cotes -----------------------------------------------------------------------------


def test_bande_nulle_inchangee() -> None:
    page = page_size("A3")
    assert overall_layout((1200, 600, 750), page) == overall_layout(
        (1200, 600, 750), page, band=0.0
    )


@pytest.mark.parametrize("page", PAGES, ids=lambda page: f"{page.width:g}x{page.height:g}")
@pytest.mark.parametrize(
    "sizes", [(1200, 600, 750), (600, 600, 2000), (3000, 300, 200), (40, 20, 30)]
)
@pytest.mark.parametrize("band", [20.0, 32.5, 60.0])
def test_bande_des_cotes_dans_la_feuille(
    page: PageSize, sizes: tuple[float, float, float], band: float
) -> None:
    layout = overall_layout(sizes, page, band=band)
    if not layout.fits:
        return
    width, depth, height = (value * layout.scale for value in sizes)
    assert layout.front.x - width / 2 - band >= MARGIN_MM - 1e-9
    assert layout.front.y + height / 2 + band <= page.height - MARGIN_MM + 1e-9
    assert layout.side.x + depth / 2 <= page.width - MARGIN_MM + 1e-9
    assert layout.top.y - depth / 2 >= MARGIN_MM - 1e-9
    plain = overall_layout(sizes, page)
    assert layout.scale <= plain.scale
