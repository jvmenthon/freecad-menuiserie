# SPDX-License-Identifier: LGPL-2.1-or-later
"""Façade publique de l'atelier pour les scripts et la console Python de FreeCAD.

Exemple (console) ::

    from freecad.menuiserie.api import make_wood_part

    planche = make_wood_part(800, 200, 22, "chene")
    planche.Length = 1000

Assemblage (J3) ::

    from freecad.menuiserie.api import make_mortise_tenon

    assemblage = make_mortise_tenon(montant, traverse, tenon_thickness=8)

C'est le seul module hors de ``gui/`` autorisé à importer ``gui/``, et seulement quand
l'interface est chargée (``App.GuiUp``) : il fonctionne aussi dans ``freecadcmd``.
"""

from __future__ import annotations

import FreeCAD as App

from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.joints.factories import create_mortise_tenon
from freecad.menuiserie.features.machined_part import (
    blank_of,
    is_machined_part,
    machined_part_of,
    remove_machined_part,
)
from freecad.menuiserie.features.wood_part import create_wood_part, validated_arguments


def make_wood_part(
    length: float = 800.0,
    width: float = 200.0,
    thickness: float = 22.0,
    material_id: str | None = None,
    *,
    mark: str = "",
    doc: Document | None = None,
) -> DocumentObject:
    """Crée une pièce de bois (cotes finies en mm), l'affiche si l'interface est chargée et
    recalcule le document.

    ``doc`` vaut par défaut le document actif, ou un nouveau document s'il n'y en a pas : les
    cotes et le matériau sont validés avant, si bien qu'une erreur ne crée aucun document. Aucune
    transaction n'est ouverte : c'est à l'appelant de le faire pour pouvoir annuler.
    """
    validated_arguments(length, width, thickness, material_id)
    document = doc if doc is not None else App.ActiveDocument or App.newDocument()
    obj = create_wood_part(
        document,
        length=length,
        width=width,
        thickness=thickness,
        material_id=material_id,
        mark=mark,
    )
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.wood_part import (
            ViewProviderWoodPart,
        )

        ViewProviderWoodPart(obj.ViewObject)
    document.recompute()
    return obj


def make_mortise_tenon(
    host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Relie deux pièces (pièces de bois ou pièces usinées) par un tenon-mortaise et recalcule
    le document : mortaise dans ``host``, tenon au bout de ``guest``.

    Paramètres facultatifs en mm (0 = automatique) : ``tenon_thickness``, ``tenon_width``,
    ``tenon_length``, ``width_offset``, ``thickness_offset``, ``through``,
    ``mortise_clearance``. Pièces et paramètres sont validés avant toute création
    (``TypeError`` ou ``ValueError`` traduites). Aucune transaction n'est ouverte : c'est à
    l'appelant de le faire pour pouvoir annuler.
    """
    document = blank_of(host).Document
    joint = create_mortise_tenon(document, host, guest, **params)
    document.recompute()
    return joint


__all__ = [
    "blank_of",
    "is_machined_part",
    "machined_part_of",
    "make_mortise_tenon",
    "make_wood_part",
    "remove_machined_part",
]
