# SPDX-License-Identifier: LGPL-2.1-or-later
"""Façade publique de l'atelier pour les scripts et la console Python de FreeCAD.

Exemple (console) ::

    from freecad.menuiserie.api import make_wood_part

    planche = make_wood_part(800, 200, 22, "chene")
    planche.Length = 1000

Pièce en bois, forme dessinée avec Sketcher / PartDesign (PD-b) ::

    from freecad.menuiserie.api import make_shaped_part, reset_shaped_axes

    pied = make_shaped_part(corps, "chene", mark="P1")  # corps : PartDesign::Body
    pied.Length  # cotes d'encombrement, en lecture seule, qui suivent le dessin

Assemblage (J3) ::

    from freecad.menuiserie.api import make_mortise_tenon

    assemblage = make_mortise_tenon(montant, traverse, tenon_thickness=8)

Ensemble (J4) ::

    from freecad.menuiserie.api import make_furniture, resize_furniture

    bureau, avertissements = make_furniture([plateau, joue_g, joue_d, voile], label="Bureau")
    avertissements = resize_furniture(bureau, depth=800)

Répétition (R-b1) ::

    from freecad.menuiserie.api import RepeatParams, dissociate, edit_repeat, make_repeat

    lames = make_repeat([lame], RepeatParams(count=9, step=120, axis="Y"))
    edit_repeat(lames, RepeatParams(count=12, step=100, axis="Y"))
    dissociate(copie)  # la copie devient une pièce libre

Liste de débit (J2) ::

    from freecad.menuiserie.api import export_cut_list_csv, make_cut_list

    feuille = make_cut_list(doc)  # feuille « Liste de débit », réécrite à chaque recalcul
    export_cut_list_csv(doc, "/chemin/debit.csv", objects=[caisson])

Façade seule : le code est dans le paquet privé ``_api/`` (``wood``, ``joints``, ``furniture``,
``cutlist``), les seuls modules hors de ``gui/`` autorisés à importer ``gui/``, et seulement quand
l'interface est chargée (``App.GuiUp``) : ils fonctionnent aussi dans ``freecadcmd``.
"""

from __future__ import annotations

from freecad.menuiserie._api.cutlist import (
    cut_list_html,
    cut_list_of,
    export_cut_list_csv,
    export_cut_list_pdf,
    make_cut_list,
    number_marks,
)
from freecad.menuiserie._api.furniture import (
    add_to_furniture,
    furniture_of,
    make_carcass,
    make_furniture,
    rebind_furniture,
    remove_from_furniture,
    resize_furniture,
    set_distance,
    set_edge_distance,
    set_furniture_material,
    set_member_options,
    unlock_and_resize,
    unlock_and_set_thickness,
)
from freecad.menuiserie._api.joints import (
    close_gap,
    closing_options,
    make_biscuits,
    make_dovetail,
    make_dowels,
    make_drawer_slide,
    make_foot,
    make_half_lap,
    make_loose_tenons,
    make_miter,
    make_mortise_tenon,
    make_rabbet,
    make_room_for_slide,
    make_shelf_pins,
    make_tongue_groove,
    slide_shortfall,
)
from freecad.menuiserie._api.repeat import dissociate, edit_repeat, make_repeat, repeat_of
from freecad.menuiserie._api.wood import (
    make_shaped_part,
    make_shaped_parts,
    make_wood_part,
    reset_shaped_axes,
)
from freecad.menuiserie.core.cutlist import FRENCH_CSV, INTERNATIONAL_CSV
from freecad.menuiserie.core.repeat import RepeatAxis, RepeatMode, RepeatParams, SpacingMode
from freecad.menuiserie.core.templates.carcass import CarcassJoinery, CarcassParams
from freecad.menuiserie.features.furniture_bindings import LockedPiecesError
from freecad.menuiserie.features.machined_part import (
    blank_of,
    is_machined_part,
    machined_part_of,
    remove_machined_part,
)
from freecad.menuiserie.features.picked import PickedElement
from freecad.menuiserie.features.shaped_part import is_shaped_part, is_timber

__all__ = [
    "FRENCH_CSV",
    "INTERNATIONAL_CSV",
    "CarcassJoinery",
    "CarcassParams",
    "LockedPiecesError",
    "PickedElement",
    "RepeatAxis",
    "RepeatMode",
    "RepeatParams",
    "SpacingMode",
    "add_to_furniture",
    "blank_of",
    "close_gap",
    "closing_options",
    "cut_list_html",
    "cut_list_of",
    "dissociate",
    "edit_repeat",
    "export_cut_list_csv",
    "export_cut_list_pdf",
    "furniture_of",
    "is_machined_part",
    "is_shaped_part",
    "is_timber",
    "machined_part_of",
    "make_biscuits",
    "make_carcass",
    "make_cut_list",
    "make_dovetail",
    "make_dowels",
    "make_drawer_slide",
    "make_foot",
    "make_furniture",
    "make_half_lap",
    "make_loose_tenons",
    "make_miter",
    "make_mortise_tenon",
    "make_rabbet",
    "make_repeat",
    "make_room_for_slide",
    "make_shaped_part",
    "make_shaped_parts",
    "make_shelf_pins",
    "make_tongue_groove",
    "make_wood_part",
    "number_marks",
    "rebind_furniture",
    "remove_from_furniture",
    "remove_machined_part",
    "repeat_of",
    "reset_shaped_axes",
    "resize_furniture",
    "set_distance",
    "set_edge_distance",
    "set_furniture_material",
    "set_member_options",
    "slide_shortfall",
    "unlock_and_resize",
    "unlock_and_set_thickness",
]
