# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarits français des anomalies de la bibliothèque, marqués pour la traduction."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

BUILTIN_SOURCE: Final = QT_TRANSLATE_NOOP("Menuiserie", "intégrée")
"""Source citée dans les anomalies de la bibliothèque intégrée."""

# Gabarits des anomalies : « source » est toujours fourni dans les paramètres.
FILE_UNREADABLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "{source} : fichier illisible ({error}).")
FILE_NOT_REGULAR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : ce chemin ne désigne pas un fichier ordinaire."
)
FILE_TOO_LARGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : fichier trop volumineux ({size} octets, maximum {max} octets)."
)
FILE_NOT_UTF8: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : le fichier n'est pas encodé en UTF-8."
)
FILE_INVALID_JSON: Final = QT_TRANSLATE_NOOP("Menuiserie", "{source} : JSON invalide ({error}).")
FILE_NON_FINITE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : valeur « {value} » refusée (NaN et Infinity sont interdits)."
)
FILE_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : JSON trop profondément imbriqué."
)
FILE_BUILTIN_MISSING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : bibliothèque de matériaux introuvable ({path})."
)
ROOT_NOT_OBJECT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : la racine du fichier doit être un objet JSON."
)
ROOT_FORMAT_INVALID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clé « format » absente ou non entière."
)
ROOT_FORMAT_NEWER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : fichier créé par une version plus récente de l'atelier "
    "(format {format}, format pris en charge : {supported}).",
)
ROOT_FORMAT_UNSUPPORTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : format {format} non pris en charge (format attendu : {supported})."
)
ROOT_MATERIALS_INVALID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clé « materials » absente ou qui n'est pas une liste."
)
ROOT_DUPLICATE_KEY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clé « {field} » en double à la racine du fichier."
)
ROOT_UNKNOWN_KEYS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clés inconnues à la racine, ignorées : {keys}."
)
ROOT_UNKNOWN_KEYS_MORE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clés inconnues à la racine, ignorées : {keys} … et {more} autres."
)
TOO_MANY_MATERIALS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : {count} matériaux, seuls les {max} premiers sont lus."
)
ENTRIES_NOT_OBJECTS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : entrées n° {positions} ignorées, chaque matériau doit être un objet JSON.",
)
ENTRY_MISSING_FIELD: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : matériau « {id} », champ « {field} » : champ obligatoire absent."
)
ENTRY_UNKNOWN_KEYS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : matériau « {id} », clés inconnues ignorées : {keys}."
)
ENTRY_UNKNOWN_KEYS_MORE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », clés inconnues ignorées : {keys} … et {more} autres.",
)
ENTRY_DUPLICATE_KEY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : clé en double, entrée ignorée.",
)
ENTRY_INVALID_ID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : identifiant de 1 à {max} caractères "
    "attendu (lettres minuscules sans accent, chiffres et tirets, ex. « cp-bouleau »).",
)
ENTRY_DUPLICATE_ID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : identifiant déjà utilisé "
    "dans ce fichier, entrée ignorée.",
)
ENTRY_INVALID_KIND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : matériau « {id} », champ « {field} » : type attendu parmi {allowed}."
)
ENTRY_INVALID_NAME: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : texte ou objet "
    "{{langue: libellé}} non vide attendu.",
)
ENTRY_INVALID_LANGUAGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : code de langue « {language} » "
    "invalide (deux lettres minuscules attendues, ex. « fr »).",
)
ENTRY_INVALID_LABEL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : libellé de 1 à {max} caractères "
    "sans caractère de contrôle ni caractère invisible attendu.",
)
ENTRY_INVALID_DENSITY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : masse volumique entre {min} et {max} "
    "kg/m³ attendue.",
)
ENTRY_INVALID_THICKNESSES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : liste de 1 à {count} épaisseurs "
    "attendue, chacune supérieure à 0 et au plus {max} mm.",
)
ENTRY_INVALID_COLOR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : couleur au format « #RRGGBB » attendue.",
)
ENTRY_INVALID_GRAIN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : valeur true ou false attendue.",
)
TOO_MANY_ISSUES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : {count} autres anomalies non affichées."
)
TOO_MANY_ISSUES_SEVERAL_SOURCES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{count} autres anomalies non affichées, dans plusieurs fichiers."
)
ENTRY_INVALID_TEXTURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : objet avec les clés « image » et "
    "« size » attendu.",
)
ENTRY_INVALID_TEXTURE_IMAGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : chemin relatif de 1 à {max} caractères "
    "vers une image {extensions} attendu (séparateur « / », sans « .. », « \\ » ni « : »).",
)
ENTRY_TEXTURE_OUTSIDE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : l'image doit se trouver dans le dossier "
    "du fichier de bibliothèque (lien symbolique vers l'extérieur refusé).",
)
ENTRY_TEXTURE_NO_FOLDER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : dossier du fichier de bibliothèque "
    "inconnu, chemin de l'image impossible à résoudre.",
)
ENTRY_INVALID_TEXTURE_SIZE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : deux nombres entre {min} et {max} mm "
    "attendus (largeur et hauteur réelles couvertes par l'image).",
)
MERGE_REPLACED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : le matériau « {id} » remplace le matériau intégré de même identifiant.",
)
MERGE_LABEL_TAKEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : libellé « {label} » déjà utilisé "
    "par le matériau « {other} », entrée ignorée.",
)
