# SPDX-License-Identifier: LGPL-2.1-or-later
"""Génère les icônes SVG de l'atelier dans ``freecad/menuiserie/resources/icons``.

Les pièces de bois sont décrites en volumes (boîtes, profils extrudés, cylindres) puis
projetées en isométrie, ce qui garde un style homogène : contour brun de 2 px, trois tons
par matière (dessus clair, faces latérales plus sombres) et veinage sur le dessus.

Usage : ``python tools/generer_icones.py [dossier_de_sortie]``
"""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

ICONS_DIR = Path(__file__).resolve().parents[1] / "freecad" / "menuiserie" / "resources" / "icons"

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]

C30 = math.cos(math.radians(30))

# Dégradés (début, fin) pour le dessus (z), la face avant gauche (y), la face avant droite (x),
# puis la couleur du contour.
MATIERES: dict[str, tuple[tuple[str, str], tuple[str, str], tuple[str, str], str]] = {
    "chene": (("#f6d7a3", "#e5b26e"), ("#d9a160", "#c4884a"), ("#b57a3c", "#99622b"), "#4e2f12"),
    "hetre": (("#fbe6c8", "#f0c99b"), ("#e8b98a", "#d9a277"), ("#c99068", "#b07a52"), "#5a3520"),
    "noyer": (("#a8774f", "#8a5a36"), ("#7a4c2b", "#6a3f22"), ("#5e381d", "#4b2b15"), "#2a170a"),
    "contreplaque": (
        ("#fbecc9", "#f1d8a2"),
        ("#e9cd94", "#dcbb7c"),
        ("#cfa96a", "#bb9455"),
        "#5c4220",
    ),
    "acier": (("#eeeeec", "#c8cbc5"), ("#babdb6", "#a3a69f"), ("#888a85", "#73766f"), "#2e3436"),
    "palissandre": (
        ("#5a3a2a", "#3f271b"),
        ("#3f271b", "#33201a"),
        ("#2c1a12", "#22140d"),
        "#140b06",
    ),
    "tourillon": (
        ("#fdf0d5", "#f3d8a6"),
        ("#ecca8d", "#dcb070"),
        ("#cfa262", "#b88b4c"),
        "#5c3a17",
    ),
}
VEINAGE = {"chene": "#b8823f", "hetre": "#d1a072", "noyer": "#5e381d"}
TROU = "#3b2410"


def iso(p: Point3) -> Point2:
    """Projection isométrique : x vers la droite, y vers la gauche, z vers le haut."""
    x, y, z = p
    return ((x - y) * C30, (x + y) * 0.5 - z)


def enveloppe_convexe(points: list[Point2]) -> list[Point2]:
    pts = sorted(set(points))

    def cross(o: Point2, a: Point2, b: Point2) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    bas: list[Point2] = []
    haut: list[Point2] = []
    for p in pts:
        while len(bas) >= 2 and cross(bas[-2], bas[-1], p) <= 0:
            bas.pop()
        bas.append(p)
    for p in reversed(pts):
        while len(haut) >= 2 and cross(haut[-2], haut[-1], p) <= 0:
            haut.pop()
        haut.append(p)
    return bas[:-1] + haut[:-1]


@dataclass
class Element:
    """Un élément dessiné : face, trou, bande colorée ou trait."""

    nature: str
    points: list[Point2]
    couleur: str = ""
    matiere: str = ""
    face: str = ""
    epaisseur: float = 1.2


@dataclass
class Icone:
    commentaire: str
    elements: list[Element] = field(default_factory=list)

    def face(self, pts: Sequence[Point3], matiere: str, face: str) -> None:
        self.elements.append(Element("face", [iso(p) for p in pts], matiere=matiere, face=face))

    def prisme(
        self, profil: Sequence[Point2], axe: str, a0: float, a1: float, matiere: str
    ) -> None:
        """Extrude un profil 2D le long de l'axe ``x``, ``y`` ou ``z``, de a0 à a1."""

        def en_3d(u: float, v: float, a: float) -> Point3:
            return {"x": (a, u, v), "y": (u, a, v), "z": (u, v, a)}[axe]

        n = len(profil)
        aire = sum(
            profil[i][0] * profil[(i + 1) % n][1] - profil[(i + 1) % n][0] * profil[i][1]
            for i in range(n)
        )
        signe = 1 if aire > 0 else -1
        faces: list[tuple[list[Point3], Point3]] = []
        for i in range(n):
            (u0, v0), (u1, v1) = profil[i], profil[(i + 1) % n]
            normale = en_3d((v1 - v0) * signe, -(u1 - u0) * signe, 0)
            if sum(normale) > 1e-9:  # face tournée vers l'observateur
                pts = [en_3d(u0, v0, a0), en_3d(u1, v1, a0), en_3d(u1, v1, a1), en_3d(u0, v0, a1)]
                faces.append((pts, normale))
        faces.append(([en_3d(u, v, a1) for u, v in profil], en_3d(0, 0, 1)))
        # Peintre : les faces les plus éloignées d'abord.
        faces.sort(key=lambda f: sum(sum(p) for p in f[0]) / len(f[0]))
        for pts, normale in faces:
            axe_dominant = max(range(3), key=lambda k: abs(normale[k]))
            self.face(pts, matiere, "xyz"[axe_dominant])

    def boite(self, origine: Point3, taille: Point3, matiere: str) -> None:
        """Parallélépipède d'angle ``origine`` et de dimensions ``taille`` (x, y, z)."""
        (x, y, z), (dx, dy, dz) = origine, taille
        profil = [(y, z), (y + dy, z), (y + dy, z + dz), (y, z + dz)]
        self.prisme(profil, "x", x, x + dx, matiere)

    def cylindre(self, cx: float, cy: float, z0: float, z1: float, r: float, matiere: str) -> None:
        bas = [iso((cx + r * math.cos(t), cy + r * math.sin(t), z0)) for t in _angles()]
        haut = [iso((cx + r * math.cos(t), cy + r * math.sin(t), z1)) for t in _angles()]
        self.elements.append(
            Element("face", enveloppe_convexe(bas + haut), matiere=matiere, face="y")
        )
        self.elements.append(Element("face", haut, matiere=matiere, face="z"))

    def trou(self, pts: Sequence[Point3]) -> None:
        self.elements.append(Element("trou", [iso(p) for p in pts], couleur=TROU))

    def bande(self, pts: Sequence[Point3], couleur: str) -> None:
        self.elements.append(Element("bande", [iso(p) for p in pts], couleur=couleur))

    def trait(self, pts: Sequence[Point3], couleur: str, epaisseur: float = 1.2) -> None:
        self.elements.append(Element("trait", [iso(p) for p in pts], couleur, epaisseur=epaisseur))

    def veinage(
        self,
        plage: tuple[float, float],
        ancrage: tuple[float, float],
        matiere: str,
        *,
        amplitude: float = 1.2,
        phase: float = 0.0,
        axe: str = "x",
    ) -> None:
        """Ligne de veinage ondulée sur un dessus, parallèle à l'axe ``x`` ou ``y``.

        ``plage`` = (début, fin) le long de l'axe ; ``ancrage`` = (position transverse, hauteur z).
        """
        (a0, a1), (pos, z) = plage, ancrage
        pts: list[Point3] = []
        for i in range(17):
            t = i / 16
            a = a0 + (a1 - a0) * t
            ecart = pos + amplitude * math.sin(2 * math.pi * (t * 1.3 + phase))
            pts.append((a, ecart, z) if axe == "x" else (ecart, a, z))
        self.trait(pts, VEINAGE[matiere])

    def svg(
        self,
        cadre: tuple[float, float, float, float] = (3, 61, 3, 61),
        fond: str = "",
        devant: str = "",
    ) -> str:
        """Rend l'icône en 64 x 64, le dessin centré et mis à l'échelle dans ``cadre`` ;
        ``fond`` est dessiné dessous, ``devant`` par-dessus (pastille)."""
        xs = [p[0] for e in self.elements for p in e.points]
        ys = [p[1] for e in self.elements for p in e.points]
        x0, x1, y0, y1 = cadre
        s = min((x1 - x0) / (max(xs) - min(xs)), (y1 - y0) / (max(ys) - min(ys)))
        ox = (x0 + x1) / 2 - s * (max(xs) + min(xs)) / 2
        oy = (y0 + y1) / 2 - s * (max(ys) + min(ys)) / 2

        def coords(pts: list[Point2]) -> str:
            return " ".join(f"{ox + s * x:.2f},{oy + s * y:.2f}" for x, y in pts)

        lignes = [f"  <!-- {self.commentaire} -->", "  <defs>"]
        for matiere in sorted({e.matiere for e in self.elements if e.matiere}):
            for face, (c0, c1) in zip("zyx", MATIERES[matiere][:3], strict=True):
                lignes.append(
                    f'    <linearGradient id="{matiere}-{face}" x1="0" y1="0" x2="1" y2="1">'
                    f'<stop offset="0" stop-color="{c0}"/><stop offset="1" stop-color="{c1}"/>'
                    "</linearGradient>"
                )
        lignes.append("  </defs>")
        if fond:
            lignes.append(fond)
        for e in self.elements:
            pts = coords(e.points)
            if e.nature == "face":
                lignes.append(
                    f'  <polygon points="{pts}" fill="url(#{e.matiere}-{e.face})" '
                    f'stroke="{MATIERES[e.matiere][3]}" stroke-width="2" stroke-linejoin="round"/>'
                )
            elif e.nature == "trou":
                lignes.append(
                    f'  <polygon points="{pts}" fill="{e.couleur}" stroke="{e.couleur}" '
                    'stroke-width="1" stroke-linejoin="round"/>'
                )
            elif e.nature == "bande":
                lignes.append(f'  <polygon points="{pts}" fill="{e.couleur}" fill-opacity="0.9"/>')
            else:
                lignes.append(
                    f'  <polyline points="{pts}" fill="none" stroke="{e.couleur}" '
                    f'stroke-width="{e.epaisseur}" stroke-linecap="round" stroke-linejoin="round"/>'
                )
        if devant:
            lignes.append(devant)
        return _document(lignes)


def _angles(n: int = 40) -> list[float]:
    return [2 * math.pi * i / n for i in range(n)]


def _document(lignes: list[str]) -> str:
    entete = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">',
    ]
    return "\n".join([*entete, *lignes, "</svg>"]) + "\n"


def _feuille(x: float) -> str:
    """Feuille de tableau (liste de débit) dont le bord gauche est en ``x``."""
    lignes_tableau = " ".join(f"M{x + 5},{y} H{x + 35}" for y in (30, 36, 42, 48))
    trait = 'stroke="#2e3436" stroke-width="2" stroke-linejoin="round"'
    return (
        f'  <path d="M{x},4 H{x + 30} L{x + 40},14 V60 H{x} Z" fill="#ffffff" {trait}/>\n'
        f'  <path d="M{x + 30},4 V14 H{x + 40}" fill="#d3d7cf" {trait}/>\n'
        f'  <rect x="{x + 5}" y="18" width="30" height="6" fill="#c4884a" stroke="#4e2f12" '
        'stroke-width="1"/>\n'
        f'  <path d="{lignes_tableau} M{x + 17},24 V52" fill="none" stroke="#888a85" '
        'stroke-width="1.5"/>'
    )


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
    return ic.svg(cadre=(22, 62, 40, 62), fond=_feuille(10))


def export_liste_de_debit() -> str:
    fleche = (
        '  <path d="M30,44 H44 V36 L60,49 L44,62 V54 H30 Z" fill="#73d216" '
        'stroke="#2c5e00" stroke-width="2" stroke-linejoin="round"/>'
    )
    return _document(["  <!-- Export de la liste de débit (CSV) -->", _feuille(6), fleche])


def export_liste_de_debit_pdf() -> str:
    fleche = (
        '  <path d="M30,44 H44 V36 L60,49 L44,62 V54 H30 Z" fill="#ef2929" '
        'stroke="#7a0000" stroke-width="2" stroke-linejoin="round"/>'
    )
    return _document(["  <!-- Export de la liste de débit (PDF) -->", _feuille(6), fleche])


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
    return _document(lignes)


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
    ic.trou([(68 + 5 * math.cos(t), 13 + 5 * math.sin(t), 14) for t in _angles(32)])
    for cx in (22, 45):
        ic.cylindre(cx, 13, 14, 34, 5, "tourillon")
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


# --- Ensembles (J4c) ------------------------------------------------------------------------


def _bureau(ic: Icone) -> None:
    """Bureau : deux joues, un voile et un plateau, du plus loin au plus proche."""
    ic.boite((0, 0, 0), (5, 34, 38), "chene")  # joue gauche
    ic.boite((5, 26, 14), (54, 4, 24), "chene")  # voile
    ic.boite((59, 0, 0), (5, 34, 38), "chene")  # joue droite
    ic.boite((-2, -2, 38), (68, 38, 5), "chene")  # plateau
    ic.veinage((2, 62), (8, 43), "chene", amplitude=0.7)
    ic.veinage((2, 62), (22, 43), "chene", amplitude=0.7, phase=0.5)


def _pastille(couleur: str, bord: str, motif: str) -> str:
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
    plus = _pastille("#73d216", "#2c5e00", "M49,42 V56 M42,49 H56")
    return ic.svg(cadre=(2, 50, 2, 50), devant=plus)


def ensemble_retirer() -> str:
    ic = Icone("Retirer de l'ensemble : bureau et pastille « moins »")
    _bureau(ic)
    moins = _pastille("#ef2929", "#a40000", "M42,49 H56")
    return ic.svg(cadre=(2, 50, 2, 50), devant=moins)


def ensemble_relier() -> str:
    ic = Icone("Relier les pièces : bureau et pastille de recalcul")
    _bureau(ic)
    fleches = _pastille(
        "#3465a4",
        "#204a87",
        "M43,47 A6.5,6.5 0 0 1 55,46 M55,46 L56,41 M55,46 L50,45 "
        "M55,51 A6.5,6.5 0 0 1 43,52 M43,52 L42,57 M43,52 L48,53",
    )
    return ic.svg(cadre=(2, 50, 2, 50), devant=fleches)


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


ICONES = {
    "menuiserie.svg": atelier,
    "Menuiserie_WoodPart.svg": piece_de_bois,
    "Menuiserie_Panel.svg": panneau,
    "Menuiserie_Species.svg": essences,
    "Menuiserie_CutList.svg": liste_de_debit,
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
    "Menuiserie_Carcass.svg": caisson,
    # Ensembles (J4c)
    "Menuiserie_Furniture.svg": ensemble,
    "Menuiserie_FurnitureAdd.svg": ensemble_ajouter,
    "Menuiserie_FurnitureRemove.svg": ensemble_retirer,
    "Menuiserie_FurnitureRebind.svg": ensemble_relier,
    # Rotations du panneau de la pièce de bois (J6c)
    "Menuiserie_RotateX.svg": rotation_x,
    "Menuiserie_RotateY.svg": rotation_y,
    "Menuiserie_RotateZ.svg": rotation_z,
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
