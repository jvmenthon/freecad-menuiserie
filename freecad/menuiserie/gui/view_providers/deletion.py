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

from typing import Final

GROUP_DELETION: Final = "group_recursive_deletion"


def in_group_deletion(subelements: object) -> bool:
    """Vrai si ``onDelete`` est appelé pour la suppression du contenu d'un groupe."""
    return isinstance(subelements, (list, tuple)) and GROUP_DELETION in subelements
