# SPDX-License-Identifier: LGPL-2.1-or-later
"""Moteur des icônes SVG de l'atelier, utilisé par ``tools/generer_icones.py``.

Les pièces de bois sont décrites en volumes (boîtes, profils extrudés, cylindres) puis
projetées en isométrie, ce qui garde un style homogène : contour brun de 2 px, trois tons
par matière (dessus clair, faces latérales plus sombres) et veinage sur le dessus. Le module
fournit aussi les éléments plats communs (feuille de tableau, lettres tracées, étiquette).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

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
        bas = [iso((cx + r * math.cos(t), cy + r * math.sin(t), z0)) for t in angles()]
        haut = [iso((cx + r * math.cos(t), cy + r * math.sin(t), z1)) for t in angles()]
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
        return document(lignes)


def angles(n: int = 40) -> list[float]:
    return [2 * math.pi * i / n for i in range(n)]


def document(lignes: list[str]) -> str:
    entete = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">',
    ]
    return "\n".join([*entete, *lignes, "</svg>"]) + "\n"


def feuille(x: float) -> str:
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


# Lettres tracées (cadre 10 x 14) : une icône ne dépend d'aucune police (pas de <text>).
LETTRES: Final = {
    "C": "M10,2 Q8,0 5,0 Q0,0 0,7 Q0,14 5,14 Q8,14 10,12",
    "D": "M0,0 V14 H4 Q10,14 10,7 Q10,0 4,0 Z",
    "F": "M10,0 H0 V14 M0,7 H7",
    "P": "M0,14 V0 H6 Q10,0 10,3.75 Q10,7.5 6,7.5 H0",
    "S": "M10,2 Q8,0 5,0 Q0,0 0,3.5 Q0,7 5,7 Q10,7 10,10.5 Q10,14 5,14 Q2,14 0,12",
    "V": "M0,0 L5,14 L10,0",
}


def etiquette(texte: str, fond: str, bord: str) -> str:
    """Étiquette d'extension de fichier (« CSV », « PDF ») posée en bas à droite de la feuille."""
    cadre = f'  <rect x="20" y="38" width="42" height="22" rx="3" fill="{fond}" stroke="{bord}"'
    trace = 'fill="none" stroke="#ffffff" stroke-width="2.6" stroke-linecap="round"'
    lettres = [
        f'  <path transform="translate({23 + 13 * rang},42)" d="{LETTRES[lettre]}" {trace}/>'
        for rang, lettre in enumerate(texte)
    ]
    return "\n".join([f'{cadre} stroke-width="2"/>', *lettres])
