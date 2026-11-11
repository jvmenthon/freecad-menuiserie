# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ce qu'il faut sélectionner avant de lancer chaque commande de l'atelier (issue #221).

Une commande lancée sans la bonne sélection affiche « libellé de la commande : » suivi d'une de
ces phrases (``explain_selection`` de :mod:`freecad.menuiserie.gui.commands.base`). Elles citent
Ctrl+clic, qui garde la sélection native de FreeCAD pièce par pièce (ADR 0048 : un clic simple
sur une pièce d'un ensemble sélectionne l'ensemble).
"""

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

PAIR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord deux pièces (Ctrl+clic sur chacune, dans la vue 3D ou le panneau "
    "« Structure »), puis relancez la commande.",
)
SINGLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "sélectionnez d'abord une seule pièce, puis relancez la commande."
)
SLIDE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord le côté du caisson, puis le côté du tiroir (Ctrl+clic sur chacun), "
    "puis relancez la commande.",
)
FURNITURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord les pièces ou les ensembles à regrouper (Ctrl+clic sur chacun), puis "
    "relancez la commande.",
)
FURNITURE_ADD: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord un ensemble et les pièces à y ajouter (Ctrl+clic sur chacun), puis "
    "relancez la commande.",
)
FURNITURE_REMOVE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord une ou plusieurs pièces rangées dans un ensemble (Ctrl+clic), puis "
    "relancez la commande.",
)
FURNITURE_REBIND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "sélectionnez d'abord un seul ensemble, puis relancez la commande."
)
REPEAT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord les pièces ou l'ensemble à répéter (Ctrl+clic pour une pièce d'un "
    "ensemble), puis relancez la commande.",
)
REPEAT_EDIT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord une répétition ou l'une de ses copies, puis relancez la commande.",
)
REPEAT_DISSOCIATE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord une ou plusieurs copies d'une répétition (Ctrl+clic), puis relancez "
    "la commande.",
)
DISTANCE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord deux éléments (face, arête ou sommet) de deux objets différents, avec "
    "Ctrl+clic sur chacun dans la vue 3D, puis relancez la commande.",
)
SHAPED_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "sélectionnez d'abord un corps PartDesign, une forme Part ou une esquisse fermée qui n'est "
    "pas déjà une pièce en bois, puis relancez la commande.",
)
