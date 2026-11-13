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

Répétition en grille X x Y x Z (ADR 0045) : un seul mode de saisie, une ligne par axe ; le nombre
d'un axe est celui de ses éléments, original compris (1 : axe inactif) ::

    from freecad.menuiserie.api import AxisRepeat, RepeatAxis, RepeatParams, make_repeat

    grille = RepeatParams(
        grid=(AxisRepeat(RepeatAxis.X, 4, 100.0), AxisRepeat(RepeatAxis.Y, 3, 150.0))
    )
    make_repeat([barreau], grille)  # 4 x 3 = 11 copies en plus de l'original

Répétition jusqu'à une butée (ADR 0047) : en « nombre sur une longueur » ou « pas sur une
longueur », la longueur de l'axe est la distance à une face (``Stop(piece, "Face3")``), un sommet
(``"Vertex2"``) ou une pièce entière (``Stop(piece)``) ; elle suit la butée. ``deduct_thickness``
faux : la dernière copie commence à la butée au lieu de s'y arrêter ::

    from freecad.menuiserie.api import SpacingMode, Stop

    params = RepeatParams(
        spacing=SpacingMode.COUNT_ON_SPAN, grid=(AxisRepeat(RepeatAxis.X, 5, span=1.0),)
    )
    make_repeat([barreau], params, stops={RepeatAxis.X: Stop(montant, "Face3")})

Liste de débit (J2) ::

    from freecad.menuiserie.api import export_cut_list_csv, make_cut_list

    feuille = make_cut_list(doc)  # feuille « Liste de débit », réécrite à chaque recalcul
    export_cut_list_csv(doc, "/chemin/debit.csv", objects=[caisson])

Plan de l'ouvrage (issue #153, ADR 0053) : page TechDraw standard, quatre vues et cotes hors tout ::

    from freecad.menuiserie.api import DrawingOptions, make_overall_drawing

    page = make_overall_drawing(doc, [bureau])  # format de la configuration (A3 paysage)
    make_overall_drawing(doc, [bureau], DrawingOptions(page_format="A4", client="Dupont"))

Façade seule : le code est dans le paquet privé ``_api/`` (``wood``, ``joints``, ``furniture``,
``cutlist``, ``drawing``), les seuls modules hors de ``gui/`` autorisés à importer ``gui/``, et
seulement quand l'interface est chargée (``App.GuiUp``) : ils fonctionnent aussi dans
``freecadcmd``.
"""

from __future__ import annotations

from freecad.menuiserie._api.cutlist import (
    count_unmarked_parts,
    cut_list_html,
    cut_list_of,
    export_cut_list_csv,
    export_cut_list_pdf,
    make_cut_list,
    number_marks,
)
from freecad.menuiserie._api.drawing import (
    DrawingOptions,
    make_exploded_drawing,
    make_overall_drawing,
    make_part_drawings,
)
from freecad.menuiserie._api.furniture import (
    add_to_furniture,
    furniture_of,
    make_carcass,
    make_furniture,
    move_furniture,
    rebind_furniture,
    remove_from_furniture,
    rename,
    resize_furniture,
    rotate_furniture,
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
from freecad.menuiserie.core.drawing import Orientation
from freecad.menuiserie.core.repeat import (
    AxisRepeat,
    RepeatAxis,
    RepeatMode,
    RepeatParams,
    SpacingMode,
)
from freecad.menuiserie.core.templates.carcass import CarcassJoinery, CarcassParams
from freecad.menuiserie.features.furniture_bindings import LockedPiecesError
from freecad.menuiserie.features.machined_part import (
    blank_of,
    is_machined_part,
    machined_part_of,
    remove_machined_part,
)
from freecad.menuiserie.features.picked import PickedElement
from freecad.menuiserie.features.repeat_stop import Stop
from freecad.menuiserie.features.shaped_part import is_shaped_part, is_timber

__all__ = [
    "FRENCH_CSV",
    "INTERNATIONAL_CSV",
    "AxisRepeat",
    "CarcassJoinery",
    "CarcassParams",
    "DrawingOptions",
    "LockedPiecesError",
    "Orientation",
    "PickedElement",
    "RepeatAxis",
    "RepeatMode",
    "RepeatParams",
    "SpacingMode",
    "Stop",
    "add_to_furniture",
    "blank_of",
    "close_gap",
    "closing_options",
    "count_unmarked_parts",
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
    "make_exploded_drawing",
    "make_foot",
    "make_furniture",
    "make_half_lap",
    "make_loose_tenons",
    "make_miter",
    "make_mortise_tenon",
    "make_overall_drawing",
    "make_part_drawings",
    "make_rabbet",
    "make_repeat",
    "make_room_for_slide",
    "make_shaped_part",
    "make_shaped_parts",
    "make_shelf_pins",
    "make_tongue_groove",
    "make_wood_part",
    "move_furniture",
    "number_marks",
    "rebind_furniture",
    "remove_from_furniture",
    "remove_machined_part",
    "rename",
    "repeat_of",
    "reset_shaped_axes",
    "resize_furniture",
    "rotate_furniture",
    "set_distance",
    "set_edge_distance",
    "set_furniture_material",
    "set_member_options",
    "slide_shortfall",
    "unlock_and_resize",
    "unlock_and_set_thickness",
]
