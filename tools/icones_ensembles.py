# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessins des icônes de l'atelier ajoutées après les assemblages : ensembles, distance,
rotations et pièce en bois à forme libre. Reliés à leur fichier par :data:`ICONES` dans
``tools/generer_icones.py`` (même moteur ``tools/icones_svg.py``)."""

from __future__ import annotations

import math
from itertools import pairwise

from icones_svg import Icone, Point3, document

# --- Ensembles (J4c) ------------------------------------------------------------------------


def _bureau(ic: Icone) -> None:
    """Bureau : deux joues, un voile et un plateau, du plus loin au plus proche."""
    ic.boite((0, 0, 0), (5, 34, 38), "chene")  # joue gauche
    ic.boite((5, 26, 14), (54, 4, 24), "chene")  # voile
    ic.boite((59, 0, 0), (5, 34, 38), "chene")  # joue droite
    ic.boite((-2, -2, 38), (68, 38, 5), "chene")  # plateau
    ic.veinage((2, 62), (8, 43), "chene", amplitude=0.7)
    ic.veinage((2, 62), (22, 43), "chene", amplitude=0.7, phase=0.5)


def pastille(couleur: str, bord: str, motif: str) -> str:
    """Pastille ronde en bas à droite, motif blanc (chemin SVG) par-dessus."""
    return (
        f'  <circle cx="49" cy="49" r="13" fill="{couleur}" stroke="{bord}" stroke-width="2"/>\n'
        f'  <path d="{motif}" fill="none" stroke="#ffffff" stroke-width="4" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )


def ensemble() -> str:
    ic = Icone("Ensemble : bureau dont les pièces suivent les cotes globales")
    _bureau(ic)
    cote = (
        '  <path d="M4,62 H40 M4,58 V62 M40,58 V62" fill="none" stroke="#204a87" '
        'stroke-width="2" stroke-linecap="round"/>'
    )
    return ic.svg(cadre=(3, 61, 3, 55), devant=cote)


def ensemble_ajouter() -> str:
    ic = Icone("Ajouter à l'ensemble : bureau et pastille « plus »")
    _bureau(ic)
    plus = pastille("#73d216", "#2c5e00", "M49,42 V56 M42,49 H56")
    return ic.svg(cadre=(2, 50, 2, 50), devant=plus)


def ensemble_retirer() -> str:
    ic = Icone("Retirer de l'ensemble : bureau et pastille « moins »")
    _bureau(ic)
    moins = pastille("#ef2929", "#a40000", "M42,49 H56")
    return ic.svg(cadre=(2, 50, 2, 50), devant=moins)


def ensemble_relier() -> str:
    ic = Icone("Relier les pièces : bureau et pastille de recalcul")
    _bureau(ic)
    fleches = pastille(
        "#3465a4",
        "#204a87",
        "M43,47 A6.5,6.5 0 0 1 55,46 M55,46 L56,41 M55,46 L50,45 "
        "M55,51 A6.5,6.5 0 0 1 43,52 M43,52 L42,57 M43,52 L48,53",
    )
    return ic.svg(cadre=(2, 50, 2, 50), devant=fleches)


# --- Définir une distance (DI-b) -------------------------------------------------------------


def distance() -> str:
    ic = Icone("Définir une distance : plateau, étagère et cote entre les deux")
    ic.boite((0, 0, 40), (70, 30, 6), "chene")  # plateau
    ic.boite((0, 0, 0), (70, 30, 6), "chene")  # étagère
    ic.veinage((4, 66), (10, 46), "chene", amplitude=0.7)
    ic.veinage((4, 66), (22, 46), "chene", amplitude=0.7, phase=0.5)
    cote = (
        '  <path d="M58,26 V49 M53,26 H63 M53,49 H63 M58,26 L55.5,31 M58,26 L60.5,31 '
        'M58,49 L55.5,44 M58,49 L60.5,44" fill="none" stroke="#204a87" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    return ic.svg(cadre=(3, 50, 3, 61), devant=cote)


def aligner_faces() -> str:
    """Aligner deux faces : une planche penchée revient dans le plan de la planche plate
    (faces orange, plan commun en pointillé, flèche de rotation) ; dessin à plat, proposition B."""
    bois = 'fill="#e5b26e" stroke="#99622b" stroke-width="2" stroke-linejoin="round"'
    face = 'stroke="#f57900" stroke-width="3.5" stroke-linecap="round"'
    bleu = 'stroke="#204a87"'
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">\n'
        "  <!-- Aligner deux faces : une planche penchée revient dans le plan de l'autre -->\n"
        f'  <polygon points="4,48 60,48 60,58 4,58" {bois}/>\n'
        f'  <polygon points="6,40 48,18 53,27 11,49" {bois}/>\n'
        f'  <line x1="6" y1="40" x2="48" y2="18" {face}/>\n'
        f'  <line x1="2" y1="48" x2="62" y2="48" {bleu} stroke-width="1.8" '
        'stroke-dasharray="3 2.5"/>\n'
        f'  <line x1="4" y1="48" x2="60" y2="48" {face}/>\n'
        '  <path d="M52,10 A18,18 0 0 1 60,26 M56.5,26 L60,27 L61.5,22.5" fill="none" '
        f'{bleu} stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>\n'
        "</svg>\n"
    )


# Centrer sur X, Y, Z du panneau « Aligner deux faces » (proposition C, choisie par jv) :
# angle de la ligne des centres à l'écran (perpendiculaire à l'axe : X à droite, Y en
# profondeur, Z vers le haut) et couleur de l'axe, celle des rotations.
CENTRAGES = {"X": (90.0, "#cc0000"), "Y": (-45.0, "#4e9a06"), "Z": (0.0, "#3465a4")}


# Lettre de l'axe tracée au trait (pas de texte : les icônes ne dépendent d'aucune police).
LETTRES = {
    "X": "M49,47 L60,60 M60,47 L49,60",
    "Y": "M49,47 L54.5,53.5 L60,47 M54.5,53.5 V60",
    "Z": "M49,47 H60 L49,60 H60",
}


def _centrer(axe: str) -> str:
    """Deux planches de longueurs différentes (la seconde, orange, est celle qui bouge) centrées
    sur une ligne en pointillé perpendiculaire à l'axe, et la lettre de l'axe dans sa couleur.
    Dessin à plat tourné de l'angle de la ligne des centres."""
    angle, couleur = CENTRAGES[axe]
    bois = 'fill="#e5b26e" stroke="#99622b" stroke-width="2" stroke-linejoin="round"'
    face = 'fill="#fcd9a8" stroke="#f57900" stroke-width="2.5" stroke-linejoin="round"'
    # Ligne des centres horizontale avant rotation, planches verticales de part et d'autre.
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">\n'
        f"  <!-- Centrer sur l'axe {axe} : deux planches centrées sur une ligne -->\n"
        f'  <g transform="translate(-3 -3) rotate({-angle:g} 28 28)">\n'
        f'    <line x1="4" y1="28" x2="52" y2="28" stroke="{couleur}" stroke-width="2.2" '
        'stroke-dasharray="4 3"/>\n'
        f'    <rect x="10" y="10" width="12" height="36" {bois}/>\n'
        f'    <rect x="32" y="19" width="12" height="18" {face}/>\n'
        "  </g>\n"
        f'  <path d="{LETTRES[axe]}" fill="none" stroke="#ffffff" stroke-width="5.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>\n'
        f'  <path d="{LETTRES[axe]}" fill="none" stroke="{couleur}" stroke-width="3" '
        'stroke-linecap="round" stroke-linejoin="round"/>\n'
        "</svg>\n"
    )


def centrer_x() -> str:
    """Centrer sur l'axe X (panneau « Aligner deux faces »)."""
    return _centrer("X")


def centrer_y() -> str:
    """Centrer sur l'axe Y (panneau « Aligner deux faces »)."""
    return _centrer("Y")


def centrer_z() -> str:
    """Centrer sur l'axe Z (panneau « Aligner deux faces »)."""
    return _centrer("Z")


def distance_gardee() -> str:
    ic = Icone("Distance gardée : plateau, étagère et cote verrouillée entre les deux")
    ic.boite((0, 0, 40), (70, 30, 6), "chene")  # plateau
    ic.boite((0, 0, 0), (70, 30, 6), "chene")  # étagère
    ic.veinage((4, 66), (10, 46), "chene", amplitude=0.7)
    ic.veinage((4, 66), (22, 46), "chene", amplitude=0.7, phase=0.5)
    cote = (
        '  <path d="M58,26 V49 M53,26 H63 M53,49 H63 M58,26 L55.5,31 M58,26 L60.5,31 '
        'M58,49 L55.5,44 M58,49 L60.5,44" fill="none" stroke="#204a87" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/>\n'
        '  <rect x="54" y="35" width="8" height="7" rx="1" fill="#f57900" stroke="#204a87" '
        'stroke-width="1.2"/>\n'  # cadenas : la distance est gardée
        '  <path d="M56,35 V32.5 a2,2 0 0 1 4,0 V35" fill="none" stroke="#204a87" '
        'stroke-width="1.2"/>'
    )
    return ic.svg(cadre=(3, 50, 3, 61), devant=cote)


# --- Rotations X, Y, Z du panneau de la pièce de bois (J6c) ---------------------------------

# Axe tourné : (vecteur de l'axe, deux vecteurs du plan de la flèche, rayon, couleur de l'axe).
ROTATIONS = {
    "X": ((1, 0, 0), (0, 1, 0), (0, 0, 1), 15.0, "#cc0000"),
    "Y": ((0, 1, 0), (0, 0, 1), (1, 0, 0), 25.0, "#4e9a06"),
    "Z": ((0, 0, 1), (1, 0, 0), (0, 1, 0), 25.0, "#3465a4"),
}


def _autour(centre: Point3, u: Point3, v: Point3, rayon: float, angle: float) -> Point3:
    """Point du cercle de centre ``centre`` dans le plan (u, v), à l'angle ``angle`` (rad)."""
    c, s = math.cos(angle), math.sin(angle)
    return (
        centre[0] + rayon * (c * u[0] + s * v[0]),
        centre[1] + rayon * (c * u[1] + s * v[1]),
        centre[2] + rayon * (c * u[2] + s * v[2]),
    )


def _rotation(axe: str) -> str:
    """Planche avec l'axe X, Y ou Z qui la traverse et une flèche courbe autour de cet axe."""
    direction, u, v, rayon, couleur = ROTATIONS[axe]
    ic = Icone(f"Quart de tour autour de l'axe {axe} : planche, axe et flèche courbe")
    taille = (44.0, 16.0, 8.0)
    ic.boite((0, 0, 0), taille, "chene")
    centre = (taille[0] / 2, taille[1] / 2, taille[2] / 2)
    longueur = 30.0
    ic.trait(
        [
            tuple(c - longueur * d for c, d in zip(centre, direction, strict=True)),
            tuple(c + longueur * d for c, d in zip(centre, direction, strict=True)),
        ],
        couleur,
        1.5,
    )
    debut, fin = math.radians(40), math.radians(310)
    arc = [_autour(centre, u, v, rayon, debut + (fin - debut) * i / 24) for i in range(25)]
    ic.trait(arc, couleur, 3.0)
    pointe = _autour(centre, u, v, rayon, fin)
    tangente = _autour((0, 0, 0), u, v, 1.0, fin + math.pi / 2)
    radiale = _autour((0, 0, 0), u, v, 1.0, fin)
    ic.bande(
        [
            tuple(c + 8 * t for c, t in zip(pointe, tangente, strict=True)),
            tuple(c + 5 * r for c, r in zip(pointe, radiale, strict=True)),
            tuple(c - 5 * r for c, r in zip(pointe, radiale, strict=True)),
        ],
        couleur,
    )
    return ic.svg()


def rotation_x() -> str:
    return _rotation("X")


def rotation_y() -> str:
    return _rotation("Y")


def rotation_z() -> str:
    return _rotation("Z")


# --- Pièce en bois à forme libre (PD-d) ------------------------------------------------------


def _bord(bord: list[tuple[float, float]], z: float) -> float:
    """Abscisse du bord (suite de points x, z croissants en z) à la hauteur ``z``."""
    for (x0, z0), (x1, z1) in pairwise(bord):
        if z0 <= z <= z1:
            return x0 + (x1 - x0) * (z - z0) / (z1 - z0)
    return bord[-1][0]


def _pied_galbe(ic: Icone) -> None:
    """Pied galbé : profil en S dessiné dans le plan (x, z), extrudé selon y."""
    droite = [(14, 0), (16, 14), (22, 28), (26, 44), (26, 60)]
    gauche = [(0, 0), (-2, 14), (2, 30), (6, 46), (8, 60)]
    ic.prisme([*droite, *reversed(gauche)], "y", 0, 18, "chene")
    for t in (0.25, 0.5, 0.75):  # veinage de la face avant, entre les deux bords du galbe
        ligne = [
            (_bord(gauche, z) + t * (_bord(droite, z) - _bord(gauche, z)), z)
            for z in (2, 14, 30, 46, 58)
        ]
        ic.trait([(x, 18.0, z) for x, z in ligne], "#b8823f", 1.0)


def piece_en_bois_objet() -> str:
    ic = Icone("Pièce en bois : pied galbé dessiné avec Sketcher et PartDesign")
    _pied_galbe(ic)
    return ic.svg()


def _corps_bleu() -> str:
    """Corps (« Body » de PartDesign) : bloc bleu en perspective isométrique, creusé d'une
    poche sur le dessus ; dessin propre à l'atelier, placé à gauche de l'icône."""
    contour = 'stroke="#0b2a52" stroke-width="2" stroke-linejoin="round"'
    return "\n".join(
        (
            f'  <polygon points="13,14 25,21 13,28 1,21" fill="#8bb4e0" {contour}/>',
            f'  <polygon points="1,21 13,28 13,44 1,37" fill="#3465a4" {contour}/>',
            f'  <polygon points="13,28 25,21 25,37 13,44" fill="#204a87" {contour}/>',
            '  <polygon points="13,18 19,21.5 13,25 7,21.5" fill="#204a87" '
            'stroke="#0b2a52" stroke-width="1.2" stroke-linejoin="round"/>',
        )
    )


def piece_en_bois() -> str:
    ic = Icone("Convertir en pièce en bois : corps PartDesign, flèche, planche")
    ic.boite((0, 0, 0), (50, 22, 12), "chene")
    for y, phase in ((6, 0.1), (15, 0.6)):
        ic.veinage((3, 47), (y, 12), "chene", amplitude=0.8, phase=phase)
    fleche = (
        '  <path d="M27,31 H37 M32,25 L38,31 L32,37" fill="none" stroke="#4e9a06" '
        'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    return ic.svg(cadre=(38, 63, 26, 50), fond=_corps_bleu(), devant=fleche)


# --- Panneau « Structure » (ADR 0046) -----------------------------------------------------


def structure() -> str:
    """Arbre simplifié : un ensemble, deux pièces et un groupe replié."""
    trait = 'stroke="#2e3436" stroke-width="2" stroke-linejoin="round"'
    lien = 'fill="none" stroke="#2e3436" stroke-width="2" stroke-linecap="round"'
    lignes = [
        "  <!-- Structure : un ensemble, ses pièces et un groupe replié -->",
        f'  <path d="M12,20 V32 H22 M12,32 V50 H22" {lien}/>',
        f'  <rect x="4" y="6" width="34" height="14" rx="2" fill="#729fcf" {trait}/>',
        f'  <rect x="22" y="26" width="38" height="12" rx="2" fill="#c4884a" {trait}/>',
        f'  <rect x="22" y="44" width="38" height="12" rx="2" fill="#eeeeec" {trait}/>',
        f'  <path d="M28,50 H44" {lien}/>',
    ]
    return document(lignes)


def autre_objet() -> str:
    """Objet d'un autre atelier : un volume gris en pointillés (lecture seule)."""
    trait = 'stroke="#555753" stroke-width="2" stroke-linejoin="round" stroke-dasharray="4 3"'
    contour = "M10,22 L22,10 H58 L46,22 M46,22 V52 M46,52 L58,40 V10"
    lignes = [
        "  <!-- Autre objet : volume d'un autre atelier -->",
        f'  <rect x="10" y="22" width="36" height="30" rx="2" fill="#d3d7cf" {trait}/>',
        f'  <path d="{contour}" fill="#babdb6" {trait}/>',
    ]
    return document(lignes)
