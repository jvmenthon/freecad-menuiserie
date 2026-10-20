# SPDX-License-Identifier: LGPL-2.1-or-later
"""Façade publique de l'atelier pour les scripts et la console Python de FreeCAD.

Exemple (console) ::

    from freecad.menuiserie.api import make_wood_part

    planche = make_wood_part(800, 200, 22, "chene")
    planche.Length = 1000

C'est le seul module hors de ``gui/`` autorisé à importer ``gui/``, et seulement quand
l'interface est chargée (``App.GuiUp``) : il fonctionne aussi dans ``freecadcmd``.
"""

from __future__ import annotations

from typing import Any

import FreeCAD as App

from freecad.menuiserie.features.wood_part import create_wood_part

DocumentObject = Any  # objets FreeCAD, sans annotations de type
Document = Any


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

    ``doc`` vaut par défaut le document actif, ou un nouveau document s'il n'y en a pas. Aucune
    transaction n'est ouverte : c'est à l'appelant de le faire pour pouvoir annuler.
    """
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
