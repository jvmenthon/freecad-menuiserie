# SPDX-License-Identifier: LGPL-2.1-or-later
"""Suppression à la main d'un Std Part d'ensemble (revue de fin de jalon, ADR 0038).

FreeCAD range les objets d'un Std Part supprimé à la racine **sans** compenser son ``Placement`` :
les pièces sautent. L'atelier ne modifie pas FreeCAD (ADR 0007, point 3) : un observateur de
documents, posé par ``gui/`` seulement tant que l'atelier est actif, appelle
:func:`std_part_deleted` quand un Std Part qui contient un ensemble est supprimé (ses membres y
sont encore rangés à ce moment-là) :

- Std Part seulement déplacé : le décalage passe dans les ``Placement`` de ses objets et dans
  l'``Origin`` de l'ensemble, dont les liaisons suivent ; rien ne bouge à l'écran ;
- Std Part tourné : l'``Origin`` ne sait pas porter une rotation. Les pièces gardent leur place
  globale, mais l'ensemble ne les pilote plus (liaisons retirées) ; « Relier les pièces » les
  relie à nouveau.

Un sous-ensemble dont le Std Part disparaît sort de son ensemble parent (le parent ne le pilote
plus par ce Std Part). Ni transaction ni recalcul : ceux de la suppression en cours.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.distance import is_distance
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture, writing
from freecad.menuiserie.features.furniture_bindings import release_members
from freecad.menuiserie.features.furniture_container import is_std_part
from freecad.menuiserie.features.furniture_members import detach_members
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import is_machined_part

__all__ = ["StdPartObserver", "std_part_deleted"]

_TURNED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le Std Part « {part} » était tourné : « {furniture} » ne pilote plus ses pièces, qui "
    "gardent leur place (« Relier les pièces » les relie à nouveau).",
)
_EPSILON: Final = 1e-9


def _placed(obj: DocumentObject) -> bool:
    """Objet géométrique rangé dans le Std Part, qui a un ``Placement`` à compenser : ni l'ensemble,
    ni une pièce usinée, un assemblage ou une Distance (leur position suit leur brute)."""
    return (
        obj.TypeId != "App::Origin"
        and not (is_furniture(obj) or is_machined_part(obj) or is_joint(obj) or is_distance(obj))
        and "Placement" in obj.PropertiesList
        and obj.isDerivedFrom("App::GeoFeature")
    )


def _write_placement(obj: DocumentObject, placement: App.Placement) -> None:
    if getattr(obj, "Proxy", None) is not None:
        with writing(obj):
            obj.Placement = placement
    else:
        obj.Placement = placement


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
    objects = [obj for obj in part.Group if _placed(obj)]
    if not furnitures or not objects:
        return []
    where = part.getGlobalPlacement()
    messages: list[str] = []
    turned = where.Rotation.Angle > _EPSILON
    for furniture in furnitures:
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
        _write_placement(obj, moved)
    return messages


class StdPartObserver:
    """Observateur de documents (:func:`App.addDocumentObserver`) : une fois un Std Part supprimé,
    ses objets gardent leur place. Posé et retiré par ``gui/`` ; les messages vont dans la vue
    rapport."""

    def slotDeletedObject(self, obj: DocumentObject) -> None:
        """Std Part supprimé : voir :func:`std_part_deleted`."""
        for message in std_part_deleted(obj):
            report_warning(message)
