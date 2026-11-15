# SPDX-License-Identifier: LGPL-2.1-or-later
"""Suppression à la main d'un Std Part d'ensemble (revue de fin de jalon, ADR 0038).

FreeCAD range les objets d'un Std Part supprimé à la racine **sans** compenser son ``Placement`` :
les pièces sautent. L'atelier ne modifie pas FreeCAD (ADR 0007, point 3) : l'observateur de
documents que ``gui/drag/events.py`` pose seulement tant que l'atelier est actif appelle
:func:`std_part_deleted` quand un Std Part qui contient un ensemble est supprimé (ses membres y
sont encore rangés à ce moment-là) :

- Std Part seulement déplacé : le décalage passe dans les ``Placement`` de ses objets et dans
  l'``Origin`` de l'ensemble, dont les liaisons suivent ; rien ne bouge à l'écran ;
- Std Part tourné : l'``Origin`` ne sait pas porter une rotation. Les pièces gardent leur place
  globale, mais l'ensemble ne les pilote plus (liaisons retirées) ; « Relier les pièces » les
  relie à nouveau.

Un sous-ensemble dont le Std Part disparaît sort de son ensemble parent (le parent ne le pilote
plus par ce Std Part). Ni transaction ni recalcul : ceux de la suppression en cours.

Contenu gardé (réponse « Non » de FreeCAD) : l'objet ensemble ne reste pas seul dans le document
(ADR 0061, qui remplace sur ce point l'ADR 0038). Rien n'est supprimé pendant la suppression de
FreeCAD (pointeurs morts, PR #204) : :func:`left_furnitures` note les ensembles rangés dans le
Std Part, puis l'interface appelle :func:`remove_left_furnitures` une fois la suppression finie,
dans sa propre transaction « Supprimer l'ensemble » (deux entrées d'annulation). Un ensemble déjà
supprimé avec le contenu (réponse « Oui ») est ignoré.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import (
    Document,
    DocumentObject,
    restoring_or_undoing,
)
from freecad.menuiserie.features.furniture import furniture_of, is_furniture, writing
from freecad.menuiserie.features.furniture_bindings import release_members
from freecad.menuiserie.features.furniture_container import is_std_part, std_part_of
from freecad.menuiserie.features.furniture_detach import release_furniture
from freecad.menuiserie.features.furniture_entry import positioned, write_placement
from freecad.menuiserie.features.furniture_members import detach_members
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.repeat_links import detach_copies

__all__ = ["left_furnitures", "remove_left_furnitures", "std_part_deleted"]

_TURNED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le Std Part « {part} » était tourné : « {furniture} » ne pilote plus ses pièces, qui "
    "gardent leur place (« Relier les pièces » les relie à nouveau).",
)
_EPSILON: Final = 1e-9
REMOVE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Supprimer l'ensemble")


def _shift(furniture: DocumentObject, shift: App.Vector) -> None:
    with writing(furniture):
        furniture.Origin = furniture.Origin + shift


def std_part_deleted(part: DocumentObject) -> list[str]:
    """Compense la suppression du Std Part ``part`` (ses objets y sont encore rangés) ; renvoie
    les avertissements traduits. Sans effet si ``part`` n'est pas un Std Part qui contient un
    ensemble et d'autres objets."""
    if not is_std_part(part):
        return []
    furnitures = [obj for obj in part.Group if is_furniture(obj)]
    objects = [obj for obj in part.Group if positioned(obj)]
    if not furnitures or not objects:
        return []
    where = part.getGlobalPlacement()
    messages: list[str] = []
    turned = where.Rotation.Angle > _EPSILON
    for furniture in furnitures:
        detach_copies(furniture)  # les copies citent ce Std Part (ADR 0044)
        if furniture_of(furniture) is not None:  # sous-ensemble : il quitte son parent
            detach_members([furniture])
        if turned:
            release_members(furniture)
            params = {"part": str(part.Label), "furniture": str(furniture.Label)}
            messages.append(translated(_TURNED, params))
        else:
            _shift(furniture, where.Base)
    for obj in objects:
        moved = where.multiply(obj.Placement) if turned else obj.Placement
        if not turned:
            moved = App.Placement(moved.Base + where.Base, moved.Rotation)
        write_placement(obj, moved)
    return messages


def left_furnitures(part: DocumentObject) -> tuple[str, ...]:
    """Noms des ensembles rangés directement dans le Std Part ``part`` en cours de suppression,
    à supprimer une fois la suppression finie (:func:`remove_left_furnitures`) ; vide si ``part``
    n'est pas un Std Part, ou pendant une annulation, un rétablissement ou une restauration (la
    suppression de l'ensemble a sa propre entrée d'annulation)."""
    if not is_std_part(part) or restoring_or_undoing(part):
        return ()
    return tuple(obj.Name for obj in part.Group if is_furniture(obj))


def remove_left_furnitures(doc: Document, names: Sequence[str]) -> list[str]:
    """Supprime les ensembles ``names`` de ``doc`` restés sans Std Part (contenu gardé), comme la
    suppression d'un ensemble par l'interface : ses membres perdent leurs liaisons et gardent leur
    place (:func:`release_furniture`). Une transaction « Supprimer l'ensemble » pour le tout,
    abandonnée en cas d'erreur (relancée). Un ensemble absent (supprimé avec le contenu) ou de
    nouveau rangé dans un Std Part est ignoré. Renvoie les avertissements traduits."""
    left = [doc.getObject(name) for name in names]
    furnitures = [obj for obj in left if is_furniture(obj) and std_part_of(obj) is None]
    if not furnitures:
        return []
    messages: list[str] = []
    doc.openTransaction(translated(REMOVE_TRANSACTION))
    try:
        for furniture in furnitures:
            messages += release_furniture(furniture)
            doc.removeObject(furniture.Name)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    doc.recompute()
    return messages
