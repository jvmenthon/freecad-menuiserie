# SPDX-License-Identifier: LGPL-2.1-or-later
"""Suppression d'un groupe avec son contenu (Std Part d'ensemble, « Supprimer » puis « Oui » à
« Supprimer le contenu du groupe ? »).

FreeCAD 1.1 (``ViewProviderGroupExtension``, ``deleteGroupContentsRecursively``) appelle alors
``onDelete`` de chaque objet du groupe avec le marqueur ``group_recursive_deletion``, sur une
liste d'objets lue **avant** la boucle : un ``onDelete`` qui supprime lui-même d'autres objets du
groupe laisse des pointeurs morts (« Access violation »), et un ``onDelete`` faux arrête la
suppression à mi-chemin. Tout le contenu disparaît : aucun lien ne sort de la suppression, les
ViewProviders de l'atelier n'ouvrent aucune fenêtre et laissent FreeCAD supprimer l'objet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pas d'import de ``features`` au chargement : testable sans FreeCAD
    from freecad.menuiserie.features.freecad_types import DocumentObject

GROUP_DELETION: Final = "group_recursive_deletion"


def in_group_deletion(subelements: object) -> bool:
    """Vrai si ``onDelete`` est appelé pour la suppression du contenu d'un groupe."""
    return isinstance(subelements, (list, tuple)) and GROUP_DELETION in subelements


def inside_group(obj: DocumentObject, group: DocumentObject | None) -> bool:
    """Vrai si ``obj`` est rangé, même indirectement, dans ``group``."""
    parent = obj.getParentGroup()
    while parent is not None:
        if parent == group:
            return True
        parent = parent.getParentGroup()
    return False


def drop_outside_joints(machined: DocumentObject) -> None:
    """Pièce usinée supprimée avec le contenu de son groupe : ses assemblages rangés **hors** du
    groupe (autre pièce dehors) sont supprimés, et la pièce usinée de l'autre pièce aussi si elle
    n'a plus d'assemblage. Ces objets ne sont pas dans la liste de FreeCAD : les supprimer ne
    laisse aucun pointeur mort. Rien n'est touché à l'intérieur du groupe."""
    from freecad.menuiserie.features.machined_part import (  # FreeCAD chargé ici seulement
        machined_part_of,
        remove_machined_part,
    )

    group = machined.getParentGroup()
    for joint in list(machined.Joints):
        if inside_group(joint, group):
            continue
        others = [
            found
            for part in (joint.HostPart, joint.GuestPart)
            if part is not None
            and not inside_group(part, group)
            and (found := machined_part_of(part)) is not None
        ]
        joint.Document.removeObject(joint.Name)
        for other in others:
            if not other.Joints:
                remove_machined_part(other)
