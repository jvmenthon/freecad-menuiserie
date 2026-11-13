# SPDX-License-Identifier: LGPL-2.1-or-later
"""Prérequis de chaque commande de l'atelier qui attend une sélection (issue #221, ADR 0052).

Une telle commande reste grisée tant que la sélection ne convient pas ; son infobulle se termine
par « Prérequis : » suivi d'une de ces phrases (``tool_tip`` de
:mod:`freecad.menuiserie.gui.commands.base`), la même que le bouton soit grisé ou non. Elles
citent Ctrl+clic, qui garde la sélection native de FreeCAD pièce par pièce (ADR 0048 : un clic
simple sur une pièce d'un ensemble sélectionne l'ensemble).
"""

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

PAIR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "deux pièces sélectionnées (Ctrl+clic sur chacune, dans la vue 3D ou le panneau "
    "« Structure »).",
)
SINGLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "une seule pièce sélectionnée.")
SLIDE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "le côté du caisson puis le côté du tiroir sélectionnés (Ctrl+clic sur chacun).",
)
FURNITURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "les pièces ou les ensembles à regrouper sélectionnés (Ctrl+clic sur chacun).",
)
FURNITURE_ADD: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "un ensemble et les pièces à y ajouter sélectionnés (Ctrl+clic sur chacun).",
)
FURNITURE_REMOVE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "une ou plusieurs pièces rangées dans un ensemble sélectionnées (Ctrl+clic).",
)
FURNITURE_REBIND: Final = QT_TRANSLATE_NOOP("Menuiserie", "un seul ensemble sélectionné.")
REPEAT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "les pièces ou l'ensemble à répéter sélectionnés (Ctrl+clic pour une pièce d'un ensemble).",
)
REPEAT_EDIT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "une répétition ou l'une de ses copies sélectionnée."
)
REPEAT_DISSOCIATE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "une ou plusieurs copies d'une répétition sélectionnées (Ctrl+clic)."
)
DISTANCE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "deux éléments (face, arête ou sommet) de deux objets différents sélectionnés (Ctrl+clic "
    "sur chacun dans la vue 3D).",
)
ALIGN_FACES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "deux faces planes de deux objets différents sélectionnées (Ctrl+clic sur chacune dans la "
    "vue 3D).",
)
SHAPED_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "un corps PartDesign, une forme Part ou une esquisse fermée sélectionné, qui n'est pas déjà "
    "une pièce en bois.",
)
