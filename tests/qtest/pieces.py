# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces et dispositions de départ des scénarios QTest dont le sujet n'est pas la création
d'une pièce.

Le panneau « Pièce en bois » est joué au clavier par ``angle_a_queues.py`` (scénarios de
priorité 1). Ici les pièces sont posées par l'API publique, pour que chaque scénario passe son
temps sur les gestes qu'il vérifie : commandes, panneaux, boutons, annulation.
"""

from __future__ import annotations

from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api

Axe = tuple[float, float, float]
AXE_Y: Axe = (0.0, 1.0, 0.0)
AXE_Z: Axe = (0.0, 0.0, 1.0)
SECTION = (60.0, 22.0)  # largeur et épaisseur des pièces de cadre
ERREURS_PYTHON = ("TypeError", "AttributeError", "RuntimeError", "NameError", "KeyError")


def piece(
    doc: Any,
    cotes: tuple[float, float, float],
    base: tuple[float, float, float] = (0.0, 0.0, 0.0),
    axe: Axe | None = None,
    angle: float = 0.0,
    repere: str = "",
) -> Any:
    """Pièce de chêne ``cotes`` (longueur, largeur, épaisseur) posée en ``base``, tournée de
    ``angle`` degrés autour de ``axe`` ; ``repere`` est aussi son nom dans l'arbre."""
    longueur, largeur, epaisseur = cotes
    creee = api.make_wood_part(longueur, largeur, epaisseur, "chene", mark=repere, doc=doc)
    if repere:
        creee.Label = repere
    rotation = App.Rotation(App.Vector(*axe), angle) if axe else App.Rotation()
    creee.Placement = App.Placement(App.Vector(*base), rotation)
    return creee


def montant_et_traverse(doc: Any) -> tuple[Any, Any]:
    """« T » : la traverse arrive en bout contre le chant du montant."""
    montant = piece(doc, (600.0, *SECTION), repere="M")
    traverse = piece(doc, (280.0, *SECTION), (60.0, 60.0, 0.0), AXE_Z, 90.0, "T")
    doc.recompute()
    return montant, traverse


def angle_debout(doc: Any) -> tuple[Any, Any]:
    """Angle de caisse : la seconde pièce debout sur le bout de la première, à fleur."""
    a_plat = piece(doc, (500.0, 200.0, 22.0), repere="A")
    debout = piece(doc, (500.0, 200.0, 22.0), (478.0, 0.0, 522.0), AXE_Y, 90.0, "B")
    doc.recompute()
    return a_plat, debout


def cadre(doc: Any) -> dict[str, Any]:
    """Cadre de quatre pièces : deux montants M1, M2 et deux traverses T1, T2 entre eux."""
    pieces = {
        "M1": piece(doc, (600.0, *SECTION), repere="M1"),
        "M2": piece(doc, (600.0, *SECTION), (0.0, 340.0, 0.0), repere="M2"),
        "T1": piece(doc, (280.0, *SECTION), (60.0, 60.0, 0.0), AXE_Z, 90.0, "T1"),
        "T2": piece(doc, (280.0, *SECTION), (600.0, 60.0, 0.0), AXE_Z, 90.0, "T2"),
    }
    doc.recompute()
    return pieces


def assemblages(doc: Any) -> list[Any]:
    """Les assemblages du document, dans l'ordre de création."""
    return [obj for obj in doc.Objects if hasattr(obj, "HostPart")]


def erreurs_python(rapport: str) -> list[str]:
    """Types d'erreur Python présents dans le texte de la vue rapport. ``ValueError`` n'en
    fait pas partie : c'est le refus normal d'un assemblage impossible, expliqué à
    l'utilisateur."""
    return [erreur for erreur in ERREURS_PYTHON if erreur in rapport]


def commande_active(commande: str) -> bool:
    return bool(Gui.Command.get(commande).isActive())
