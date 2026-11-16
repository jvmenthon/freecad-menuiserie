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
from freecad.menuiserie.core.geometry import PlacedBlock
from tests.qtest.aides import bouton_ok, cliquer, lancer, selectionner

Axe = tuple[float, float, float]
AXE_Y: Axe = (0.0, 1.0, 0.0)
AXE_Z: Axe = (0.0, 0.0, 1.0)
DEPLACEMENT = "Déplacer une pièce"
TENON_MORTAISE = "Menuiserie_MortiseTenon"
ANGLE_NUL = 1e-6  # radians
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


def placement_de(bloc: PlacedBlock) -> App.Placement:
    """Placement FreeCAD d'un bloc posé du modèle ``core`` (aides des tests unitaires)."""
    lignes, base = bloc.placement.rotation, bloc.placement.translation
    matrice = App.Matrix(
        lignes[0][0], lignes[0][1], lignes[0][2], base.x,
        lignes[1][0], lignes[1][1], lignes[1][2], base.y,
        lignes[2][0], lignes[2][1], lignes[2][2], base.z,
        0, 0, 0, 1,
    )  # fmt: skip
    return App.Placement(matrice)


def deplacer(doc: Any, piece_deplacee: Any, placement: App.Placement) -> None:
    """Remplace un glissement ou une rotation à la souris : placement écrit dans une
    transaction, annulable comme le geste."""
    doc.openTransaction(DEPLACEMENT)
    piece_deplacee.Placement = placement
    doc.commitTransaction()
    doc.recompute()


def retablir_tout(doc: Any) -> None:
    """Ctrl+Y jusqu'au bout de l'historique, puis recalcul (FreeCAD laisse les objets rétablis
    « à recalculer »)."""
    for _ in doc.RedoNames:
        lancer("Std_Redo")
    doc.recompute()


def montant_et_traverse(doc: Any) -> tuple[Any, Any]:
    """« T » : la traverse arrive en bout contre le chant du montant."""
    montant = piece(doc, (600.0, *SECTION), repere="M")
    traverse = piece(doc, (280.0, *SECTION), (60.0, 60.0, 0.0), AXE_Z, 90.0, "T")
    doc.recompute()
    return montant, traverse


def tenon_mortaise(doc: Any) -> tuple[Any, Any]:
    """« T » assemblé : tenon-mortaise posé par la commande et son panneau, tout en
    automatique ; l'historique d'annulation repart de là."""
    montant, traverse = montant_et_traverse(doc)
    selectionner(traverse, montant)
    lancer(TENON_MORTAISE)
    cliquer(bouton_ok())
    doc.clearUndos()
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


def face_vers(piece_visee: Any, direction: Axe) -> str:
    """Nom (« FaceN ») de la face plane de la pièce dont la normale sortante, dans le repère du
    conteneur de la pièce, est ``direction``."""
    voulue = App.Vector(*direction)
    for rang, face in enumerate(piece_visee.Shape.Faces, start=1):
        if face.normalAt(0.5, 0.5).getAngle(voulue) < ANGLE_NUL:
            return f"Face{rang}"
    raise LookupError(f"aucune face de {piece_visee.Label} vers {direction}")


def boite_globale(*pieces: Any) -> App.BoundBox:
    """Boîte englobante de ``pieces`` dans le repère du document (les pièces d'un ensemble sont
    dans son Std Part, que la rotation de l'ensemble déplace)."""
    boite = App.BoundBox()
    for membre in pieces:
        forme = membre.Shape.copy()
        forme.Placement = membre.getGlobalPlacement()
        boite.add(forme.BoundBox)
    return boite


def du_type(doc: Any, nom: str) -> list[Any]:
    """Objets de l'atelier de type ``nom`` (« Menuiserie::… »), dans l'ordre de création."""
    return [obj for obj in doc.Objects if getattr(getattr(obj, "Proxy", None), "TYPE", "") == nom]


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
