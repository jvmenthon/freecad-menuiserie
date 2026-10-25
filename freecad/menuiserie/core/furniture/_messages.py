# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarits français des refus et des avertissements de l'ensemble (J4a).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. ``features/`` traduit
chaque gabarit avec ``translate(CONTEXT, gabarit).format(**params)``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

INVALID_BOX: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cote d'ensemble invalide : {field} = {value} mm (valeur finie, entre {min} et {max} mm "
    "attendue).",
)
BOX_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "width": QT_TRANSLATE_NOOP("Menuiserie", "largeur"),
        "depth": QT_TRANSLATE_NOOP("Menuiserie", "profondeur"),
        "height": QT_TRANSLATE_NOOP("Menuiserie", "hauteur"),
    }
)
INVALID_LABEL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Libellé d'ensemble inutilisable dans une expression : « {label} » (non vide, sans « > » "
    "ni « \\ » ni caractère invisible).",
)
TOO_SMALL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {member} » deviendrait trop petite : {property} = {value} mm."
)
TOO_LARGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {member} » deviendrait trop grande : {property} = {value} mm."
)
JOINT_LOST: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {host} » et « {guest} » ne seraient plus placées comme leur assemblage l'exige.",
)
BLOCKED_SIZE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Impossible de changer la {field} de l'ensemble à {value} mm : aucune pièce de la rangée "
    "({members}) ne peut s'adapter (cotes fixes : {locked}).",
)
BLOCKED_SIZE_FILLED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Impossible de changer la {field} de l'ensemble à {value} mm : aucune pièce de la rangée "
    "({members}) ne peut s'adapter (les épaisseurs la remplissent).",
)
BLOCKED_THICKNESS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Impossible de changer l'épaisseur de « {member} » à {value} mm : aucune pièce de la rangée "
    "({members}) ne peut s'adapter (cotes fixes : {locked}).",
)
BLOCKED_THICKNESS_FILLED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Impossible de changer l'épaisseur de « {member} » à {value} mm : aucune pièce de la rangée "
    "({members}) ne peut s'adapter (les épaisseurs la remplissent).",
)
FURNITURE_CYCLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {member} » ne peut pas entrer dans « {furniture} » : un ensemble ne peut pas être membre "
    "de lui-même ni d'un de ses membres.",
)

USER_FORMULA: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {member} » : {property} suit une formule ou une contrainte de l'utilisateur ; l'atelier "
    "ne la modifie pas.",
)
NOT_SQUARE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {member} » n'est pas d'équerre avec l'ensemble : il ne suit pas ses cotes."
)
THICKNESS_KEPT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {member} » : ses deux faces sont fixes sur l'axe de son épaisseur ; seule la plus proche "
    "de son bord est gardée, l'épaisseur ne change pas.",
)
OUTSIDE_BOX: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {member} » dépasserait de l'ensemble avec ces cotes."
)
GAP_SPLIT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {member} » : une autre face coupe l'intervalle entre ses deux pièces ; ses cotes sont "
    "figées et ne suivent plus sa valeur.",
)
