# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarits français des anomalies du catalogue de quincaillerie, marqués pour la traduction."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

# « source » est toujours fourni dans les paramètres.
ROOT_NOT_OBJECT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : la racine du catalogue doit être un objet JSON."
)
ROOT_FORMAT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : « format » doit valoir {supported} (valeur lue : {format})."
)
ROOT_ITEMS_INVALID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clé « items » absente ou qui n'est pas une liste."
)
TOO_MANY_ITEMS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : trop de références ({max} au plus), les suivantes sont ignorées."
)
ENTRY_NOT_OBJECT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : référence n° {position} ignorée (ce n'est pas un objet JSON)."
)
ENTRY_DUPLICATE_KEY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : référence « {id} » ignorée (clé en double)."
)
ENTRY_INVALID_FIELD: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : référence « {id} » ignorée (champ « {field} » absent ou invalide)."
)
ENTRY_INVALID_PARAM: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : référence « {id} » ignorée (cote « {param} » absente ou hors de {min} à {max} mm).",
)
ENTRY_UNKNOWN_PARAM: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : référence « {id} » ignorée (cote « {param} » inconnue)."
)
ENTRY_DUPLICATE_ID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : référence « {id} » en double, la première est gardée."
)
ENTRY_UNKNOWN_FAMILY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : référence « {id} » de famille inconnue « {family} » : comptée sans forme.",
)
MERGE_REPLACED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : la référence « {id} » remplace celle d'une source plus lointaine."
)
FILE_BUILTIN_MISSING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : catalogue de quincaillerie introuvable ({path})."
)
