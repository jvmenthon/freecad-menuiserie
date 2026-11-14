# SPDX-License-Identifier: LGPL-2.1-or-later
"""Génère les icônes SVG de l'atelier dans ``freecad/menuiserie/resources/icons``.

Chaque icône est dessinée par une fonction de ce module avec le moteur voisin
``tools/icones_svg.py`` (volumes projetés en isométrie, style commun) ; :data:`ICONES` relie
chaque fichier à sa fonction.

Usage : ``python tools/generer_icones.py [dossier_de_sortie]``
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from icones_ensembles import (
    autre_objet,
    distance,
    distance_gardee,
    ensemble,
    ensemble_ajouter,
    ensemble_relier,
    ensemble_retirer,
    piece_en_bois,
    piece_en_bois_objet,
    rotation_x,
    rotation_y,
    rotation_z,
    structure,
)
from icones_repetition import dissocier_la_copie, modifier_la_repetition, repeter, repetition
from icones_svg import Icone, angles, document, etiquette, feuille

ICONS_DIR = Path(__file__).resolve().parents[1] / "freecad" / "menuiserie" / "resources" / "icons"


def atelier() -> str:
    ic = Icone("Atelier Menuiserie : planche de chêne et équerre")
    ic.boite((0, 0, 0), (90, 32, 12), "chene")
    for y, phase in ((7, 0.0), (15, 0.35), (24, 0.7)):
        ic.veinage((4, 86), (y, 12), "chene", phase=phase)
    ic.prisme([(2, 12), (31, 12), (31, 14), (2, 14)], "x", 54, 66, "acier")  # lame
    for y in (6, 11, 16, 21, 26):  # graduations
        ic.trait([(54, y, 14), (58, y, 14)], "#555753", 1.0)
    ic.boite((46, 31, 3), (28, 7, 14), "palissandre")  # talon
    return ic.svg()


def piece_de_bois() -> str:
    ic = Icone("Pièce de bois massif : planche avec veinage et cernes")
    ic.boite((0, 0, 0), (100, 28, 12), "chene")
    for y, phase in ((6, 0.1), (14, 0.45), (22, 0.8)):
        ic.veinage((4, 96), (y, 12), "chene", phase=phase)
    for r in (7, 12, 17):  # cernes sur le bois de bout
        arc = [
            (100.0, 14 + r * math.cos(t), -8 + r * math.sin(t))
            for t in (i * math.pi / 60 for i in range(61))
        ]
        arc = [p for p in arc if 2 <= p[1] <= 26 and 1.5 <= p[2] <= 10.5]
        if len(arc) > 1:
            ic.trait(arc, "#8a5524", 1.0)
    return ic.svg()


def panneau() -> str:
    ic = Icone("Panneau : contreplaqué et ses plis")
    ic.boite((0, 0, 0), (64, 56, 12), "contreplaque")
    for z in (3, 9):  # plis croisés, plus sombres
        ic.bande(
            [(64, 0, z), (64, 56, z), (0, 56, z), (0, 56, z + 3), (64, 56, z + 3), (64, 0, z + 3)],
            "#9c6e32",
        )
    ic.trait([(64, 56, 0), (64, 56, 12)], "#5c4220", 2)
    return ic.svg()


def essences() -> str:
    ic = Icone("Bibliothèque d'essences : échantillons de noyer, chêne et hêtre")
    for i, matiere in enumerate(("noyer", "chene", "hetre")):
        ic.boite((i * 8, -i * 4, i * 10), (62, 22, 9), matiere)
        for y, phase in ((6 - i * 4, 0.2 * i), (14 - i * 4, 0.5 + 0.2 * i)):
            ic.veinage(
                (i * 8 + 4, i * 8 + 58), (y, i * 10 + 9), matiere, amplitude=0.9, phase=phase
            )
    return ic.svg()


def liste_de_debit() -> str:
    ic = Icone("Liste de débit : tableau des pièces")
    ic.boite((0, 0, 0), (60, 16, 7), "chene")
    ic.veinage((3, 57), (5, 7), "chene", amplitude=0.6)
    ic.veinage((3, 57), (11, 7), "chene", amplitude=0.6, phase=0.5)
    return ic.svg(cadre=(22, 62, 40, 62), fond=feuille(10))


def apercu_liste_de_debit() -> str:
    trait = 'stroke="#2e3436" stroke-width="2" stroke-linejoin="round"'
    contour = 'stroke="#4e2f12" stroke-width="1.2" stroke-linejoin="round"'
    manche = 'stroke="#2e3436" stroke-width="5" stroke-linecap="round"'
    lignes = [
        "  <!-- Aperçu de la liste de débit : la feuille vue à la loupe -->",
        feuille(6),
        f'  <circle cx="40" cy="42" r="14" fill="#eef3f8" fill-opacity="0.95" {trait}/>',
        f'  <path d="M50,52 L60,62" fill="none" {manche}/>',
        f'  <polygon points="40,32 51,38 40,44 29,38" fill="#f1c98f" {contour}/>',
        f'  <polygon points="29,38 40,44 40,52 29,46" fill="#c4884a" {contour}/>',
        f'  <polygon points="51,38 40,44 40,52 51,46" fill="#99622b" {contour}/>',
    ]
    return document(lignes)


def export_liste_de_debit() -> str:
    csv = etiquette("CSV", "#4e9a06", "#2c5e00")
    return document(["  <!-- Export de la liste de débit (CSV) -->", feuille(6), csv])


def export_liste_de_debit_pdf() -> str:
    pdf = etiquette("PDF", "#cc0000", "#7a0000")
    return document(["  <!-- Export de la liste de débit (PDF) -->", feuille(6), pdf])


def numeroter_les_reperes() -> str:
    trait = 'stroke="#2e3436" stroke-width="2" stroke-linejoin="round"'
    chiffre = 'fill="none" stroke="#2e3436" stroke-width="2.5" stroke-linecap="round"'
    veinage = 'fill="none" stroke="#8f5902" stroke-width="1.5" stroke-linecap="round"'
    lignes = [
        "  <!-- Numérotation des repères : deux planches portant les repères 1 et 2 -->",
        f'  <rect x="4" y="8" width="56" height="20" rx="2" fill="#c4884a" {trait}/>',
        f'  <rect x="4" y="36" width="56" height="20" rx="2" fill="#c4884a" {trait}/>',
        f'  <path d="M8,14 H34 M8,20 H46 M8,42 H30 M8,48 H44" {veinage}/>',
        f'  <rect x="38" y="11" width="18" height="14" rx="2" fill="#ffffff" {trait}/>',
        f'  <rect x="38" y="39" width="18" height="14" rx="2" fill="#ffffff" {trait}/>',
        f'  <path d="M45,16 L48,13.5 V22.5" {chiffre}/>',
        f'  <path d="M43.5,43.5 Q47,39 50.5,43.5 Q50.5,45.5 43.5,50 H51" {chiffre}/>',
    ]
    return document(lignes)


def tenon_mortaise() -> str:
    ic = Icone("Tenon-mortaise : une traverse et son tenon face à la mortaise d'un montant")
    ic.boite((0, 0, 0), (22, 22, 76), "chene")  # montant
    ic.veinage((3, 19), (6, 76), "chene", amplitude=0.5)
    ic.trou([(22, 7, 30), (22, 15, 30), (22, 15, 52), (22, 7, 52)])  # mortaise
    ic.boite((40, 7, 31), (12, 8, 20), "chene")  # tenon
    ic.boite((52, 2, 26), (32, 18, 30), "chene")  # traverse
    ic.veinage((55, 81), (6, 56), "chene", amplitude=0.6)
    ic.veinage((55, 81), (14, 56), "chene", amplitude=0.6, phase=0.5)
    return ic.svg()


def rainure_languette() -> str:
    ic = Icone("Rainure et languette : deux planches vues en bout")
    languette = [(0, 0), (24, 0), (24, 5), (32, 5), (32, 11), (24, 11), (24, 16), (0, 16)]
    ic.prisme(languette, "x", 0, 40, "chene")
    ic.veinage((3, 37), (7, 16), "chene", amplitude=0.7)
    ic.veinage((3, 37), (17, 16), "chene", amplitude=0.7, phase=0.5)
    rainure = [(44, 0), (68, 0), (68, 16), (44, 16), (44, 11), (52, 11), (52, 5), (44, 5)]
    ic.prisme(rainure, "x", 0, 40, "chene")
    ic.veinage((3, 37), (51, 16), "chene", amplitude=0.7, phase=0.3)
    ic.veinage((3, 37), (61, 16), "chene", amplitude=0.7, phase=0.8)
    return ic.svg()


def feuillure() -> str:
    ic = Icone("Feuillure : planche entaillée sur une arête")
    ic.prisme([(0, 0), (34, 0), (34, 8), (20, 8), (20, 16), (0, 16)], "x", 0, 84, "chene")
    ic.veinage((4, 80), (6, 16), "chene", amplitude=0.9)
    ic.veinage((4, 80), (14, 16), "chene", amplitude=0.9, phase=0.5)
    ic.veinage((4, 80), (27, 8), "chene", amplitude=0.9, phase=0.2)
    return ic.svg()


def tourillons() -> str:
    ic = Icone("Tourillons : deux tourillons plantés dans le chant d'une planche")
    ic.boite((0, 0, 0), (90, 26, 14), "chene")
    ic.veinage((4, 86), (5, 14), "chene", amplitude=0.8)
    ic.veinage((4, 86), (21, 14), "chene", amplitude=0.8, phase=0.6)
    ic.trou([(68 + 5 * math.cos(t), 13 + 5 * math.sin(t), 14) for t in angles(32)])
    for cx in (22, 45):
        ic.cylindre(cx, 13, 14, 34, 5, "tourillon")
    return ic.svg()


def _plat(x0: float, x1: float, y0: float, y1: float) -> list[tuple[float, float]]:
    """Contour d'un plat aux deux bouts arrondis (faux tenon), vu de dessus."""
    r = (y1 - y0) / 2
    cy = y0 + r
    pas = [math.pi * (i / 12 - 0.5) for i in range(13)]
    droite = [(x1 - r + r * math.cos(t), cy + r * math.sin(t)) for t in pas]
    gauche = [(x0 + r - r * math.cos(t), cy - r * math.sin(t)) for t in pas]
    return droite + gauche


def faux_tenons() -> str:
    ic = Icone("Faux tenon : section en stade (bouts demi-ronds) étirée sur sa longueur")
    ic.prisme(_plat(0, 34, 0, 10), "x", 0, 56, "chene")  # comme la forme générée
    ic.veinage((4, 52), (17, 10), "chene", amplitude=0.8)
    return ic.svg()


def biscuits() -> str:
    ic = Icone("Biscuit : lamelle ovale")
    haut = [(40 + 40 * u, 20 + 18 * (1 - u * u) ** 0.5) for u in (i / 10 - 1 for i in range(1, 20))]
    bas = [(40 + 40 * u, 20 - 18 * (1 - u * u) ** 0.5) for u in (1 - i / 10 for i in range(1, 20))]
    lamelle = [(0, 20), *haut, (80, 20), *bas]
    ic.prisme(lamelle, "z", 0, 4, "hetre")
    ic.veinage((8, 72), (20, 4), "hetre", amplitude=0.8)
    return ic.svg()


def pieds() -> str:
    ic = Icone("Pieds de caisson : quatre pieds réglables sous un panneau en transparence")
    coins = sorted(((12, 12), (78, 12), (12, 52), (78, 52)), key=sum)  # du fond vers l'avant
    for cx, cy in coins:
        ic.cylindre(cx, cy, 0, 4, 8, "acier")  # embase réglable
        ic.cylindre(cx, cy, 4, 32, 4.5, "acier")  # tige
    ic.boite((0, 0, 32), (90, 64, 9), "chene", opacite=0.4)
    return ic.svg()


def quincaillerie() -> str:
    ic = Icone("Quincaillerie : vis, tourillon et pied d'acier posés ensemble")
    ic.cylindre(14, 40, 0, 4, 8, "acier")  # embase du pied
    ic.cylindre(14, 40, 4, 30, 4.5, "acier")  # tige du pied
    ic.prisme(_plat(0, 34, 0, 10), "x", 34, 88, "hetre")  # tourillon couché
    ic.cylindre(60, 10, 0, 6, 8, "acier")  # tête de vis
    ic.cylindre(60, 10, 6, 40, 3.2, "acier")  # corps de vis
    return ic.svg()


def percage_lr32() -> str:
    ic = Icone("Perçage LR32 : côté debout percé de deux colonnes de trous, taquets dans un rang")
    ic.boite((0, 0, 0), (8, 46, 92), "chene")
    fil = [(8, 23 + 0.8 * math.sin(2 * math.pi * k / 10), 4 + 84 * k / 16) for k in range(17)]
    ic.trait(fil, "#8a5524", 1.0)  # fil du bois, vertical
    for cy in (10, 36):
        for i in range(6):
            cz = 12 + 14 * i
            if i == 2:
                continue
            ic.trou([(8, cy + 2.6 * math.cos(t), cz + 2.6 * math.sin(t)) for t in angles()])
    for cy in (10, 36):
        rond = [(cy + 2.8 * math.cos(t), 40 + 2.8 * math.sin(t)) for t in angles(24)]
        ic.prisme(rond, "x", 8, 20, "acier")  # taquet rond sorti de la face
    return ic.svg()


def coulisse() -> str:
    ic = Icone("Coulisse de tiroir : deux rails d'acier emboîtés, vis de fixation")
    ic.boite((0, 0, 0), (90, 4, 12), "acier")
    ic.boite((12, 4, 2), (78, 3, 9), "acier")
    for x in (12, 45, 78):
        ic.trou([(x + 2.5 * math.cos(t), 0, 6 + 2.5 * math.sin(t)) for t in angles(12)])
    return ic.svg()


def mi_bois() -> str:
    ic = Icone("Entaille à mi-bois : deux pièces croisées, entaillées à mi-épaisseur")
    profil_bas = [(0, 0), (80, 0), (80, 12), (50, 12), (50, 6), (30, 6), (30, 12), (0, 12)]
    ic.prisme(profil_bas, "y", 0, 20, "chene")
    ic.veinage((3, 27), (10, 12), "chene", amplitude=0.6)
    ic.veinage((53, 77), (10, 12), "chene", amplitude=0.6, phase=0.4)
    profil_haut = [(-20, 26), (0, 26), (0, 32), (20, 32), (20, 26), (40, 26), (40, 38), (-20, 38)]
    ic.prisme(profil_haut, "x", 30, 50, "chene")
    ic.veinage((-17, 37), (40, 38), "chene", amplitude=0.6, axe="y")
    return ic.svg()


def queue_d_aronde() -> str:
    ic = Icone("Queue d'aronde : queues taillées au bout d'une planche")
    profil = [
        (0, 0), (30, 0), (30, 8), (50, 3), (50, 19), (30, 14),
        (30, 26), (50, 21), (50, 37), (30, 32), (30, 40), (0, 40),
    ]  # fmt: skip
    ic.prisme(profil, "z", 0, 16, "chene")
    for y, phase in ((10, 0.0), (20, 0.4), (30, 0.8)):
        ic.veinage((3, 27), (y, 16), "chene", amplitude=0.7, phase=phase)
    return ic.svg()


def onglet() -> str:
    ic = Icone("Onglet : angle de cadre, deux traverses coupées à 45°")
    ic.prisme([(0, 0), (16, 16), (16, 72), (0, 72)], "z", 0, 12, "chene")  # traverse selon y
    ic.veinage((22, 68), (5, 12), "chene", amplitude=0.6, axe="y")
    ic.veinage((22, 68), (11, 12), "chene", amplitude=0.6, phase=0.5, axe="y")
    ic.prisme([(0, 0), (72, 0), (72, 16), (16, 16)], "z", 0, 12, "chene")  # traverse selon x
    ic.veinage((22, 68), (5, 12), "chene", amplitude=0.6)
    ic.veinage((22, 68), (11, 12), "chene", amplitude=0.6, phase=0.5)
    return ic.svg()


def caisson() -> str:
    ic = Icone("Caisson : côtés, fond, tablette, dessus et dos")
    ic.boite((4, 0, 4), (42, 3, 52), "contreplaque")  # dos
    ic.boite((0, 0, 0), (4, 40, 60), "contreplaque")  # côté gauche
    ic.boite((4, 0, 0), (42, 40, 4), "contreplaque")  # fond
    ic.boite((4, 0, 28), (42, 38, 3), "contreplaque")  # tablette
    ic.boite((4, 0, 56), (42, 40, 4), "contreplaque")  # dessus
    ic.boite((46, 0, 0), (4, 40, 60), "contreplaque")  # côté droit
    return ic.svg()


def finition_des_chants() -> str:
    ic = Icone("Finition des chants : planche dont les chants (faces étroites) sont surlignés")
    ic.boite((0, 0, 0), (90, 32, 12), "chene")
    for y, phase in ((7, 0.0), (15, 0.35), (24, 0.7)):
        ic.veinage((4, 86), (y, 12), "chene", phase=phase)
    orange = "#f57900"
    ic.bande([(0, 32, 0), (90, 32, 0), (90, 32, 12), (0, 32, 12)], orange)  # chant avant
    ic.bande([(90, 0, 0), (90, 32, 0), (90, 32, 12), (90, 0, 12)], orange)  # bois de bout
    ic.trait([(0, 32, 0), (90, 32, 0), (90, 0, 0)], "#4e2f12", 1.6)
    ic.trait([(0, 32, 12), (90, 32, 12), (90, 0, 12)], "#4e2f12", 1.6)
    return ic.svg()


ICONES = {
    "menuiserie.svg": atelier,
    "Menuiserie_WoodPart.svg": piece_de_bois,
    "Menuiserie_Panel.svg": panneau,
    "Menuiserie_Species.svg": essences,
    "Menuiserie_CutList.svg": liste_de_debit,
    "Menuiserie_CutListPreview.svg": apercu_liste_de_debit,
    "Menuiserie_CutListExport.svg": export_liste_de_debit,
    "Menuiserie_CutListPdf.svg": export_liste_de_debit_pdf,
    "Menuiserie_NumberMarks.svg": numeroter_les_reperes,
    "Menuiserie_MortiseTenon.svg": tenon_mortaise,
    "Menuiserie_TongueGroove.svg": rainure_languette,
    "Menuiserie_Rabbet.svg": feuillure,
    "Menuiserie_Dowels.svg": tourillons,
    "Menuiserie_HalfLap.svg": mi_bois,
    "Menuiserie_Dovetail.svg": queue_d_aronde,
    "Menuiserie_Miter.svg": onglet,
    "Menuiserie_LooseTenon.svg": faux_tenons,
    "Menuiserie_Biscuit.svg": biscuits,
    "Menuiserie_Foot.svg": pieds,
    "Menuiserie_ShelfPins.svg": percage_lr32,
    "Menuiserie_DrawerSlide.svg": coulisse,
    "Menuiserie_Carcass.svg": caisson,
    # Finition des chants (issue #5)
    "Menuiserie_FinitionChants.svg": finition_des_chants,
    # Ensembles (J4c)
    "Menuiserie_Furniture.svg": ensemble,
    "Menuiserie_FurnitureAdd.svg": ensemble_ajouter,
    "Menuiserie_FurnitureRemove.svg": ensemble_retirer,
    "Menuiserie_FurnitureRebind.svg": ensemble_relier,
    # Panneau « Structure » (ADR 0046)
    "Menuiserie_Hardware.svg": quincaillerie,
    "Menuiserie_Structure.svg": structure,
    "Menuiserie_Other.svg": autre_objet,
    # Distance entre deux pièces (DI-b)
    "Menuiserie_SetDistance.svg": distance,
    "Menuiserie_Distance.svg": distance_gardee,
    # Rotations du panneau de la pièce de bois (J6c)
    "Menuiserie_RotateX.svg": rotation_x,
    "Menuiserie_RotateY.svg": rotation_y,
    "Menuiserie_RotateZ.svg": rotation_z,
    # Pièce en bois à forme libre (PD-d)
    "Menuiserie_ShapedPart.svg": piece_en_bois,
    "Menuiserie_ShapedPartObject.svg": piece_en_bois_objet,
    # Répétition (R-c)
    "Menuiserie_Repeat.svg": repeter,
    "Menuiserie_RepeatEdit.svg": modifier_la_repetition,
    "Menuiserie_RepeatDissociate.svg": dissocier_la_copie,
    "Menuiserie_RepeatObject.svg": repetition,
}


def generer(dossier: Path = ICONS_DIR) -> list[Path]:
    """Écrit toutes les icônes dans ``dossier`` et retourne les chemins écrits."""
    dossier.mkdir(parents=True, exist_ok=True)
    ecrits = []
    for nom, dessin in ICONES.items():
        chemin = dossier / nom
        chemin.write_text(dessin(), encoding="utf-8")
        ecrits.append(chemin)
    return ecrits


if __name__ == "__main__":
    for chemin in generer(Path(sys.argv[1]) if len(sys.argv) > 1 else ICONS_DIR):
        print(chemin)
