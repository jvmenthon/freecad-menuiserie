# SPDX-License-Identifier: LGPL-2.1-or-later
"""Logique de la page de préférences, sans Qt : filtre, comptes et affichage des valeurs (ADR 0069).

Python pur, donc testé seul. La page Qt (:mod:`.page`) n'en est que l'habillage. Les textes
passent par une fonction de traduction injectée ; ``PAGE_TEXTS`` liste ceux de la page, que
l'atelier doit déclarer à la traduction.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from .catalog import Catalog, Kind, Setting, Value

__all__ = [
    "PAGE_TEXTS",
    "Choices",
    "Translate",
    "Widget",
    "count_modified",
    "format_text",
    "format_value",
    "group_summary",
    "identity",
    "is_shown",
    "matches",
    "normalize",
    "shown_keys",
]

Translate = Callable[[str], str]
Widget = Any  # widget Qt, sans importer Qt ici
Choices = Mapping[str, Sequence[tuple[Value, str]]]  # clé → (valeur enregistrée, libellé traduit)

SEARCH: Final = "Rechercher un réglage"
ADVANCED: Final = "Afficher les réglages avancés"
LAST_USED: Final = "Dernier utilisé"
LAST_USED_TIP: Final = "Retient la valeur utilisée lors de la dernière création."
RESET: Final = "Rétablir"
RESET_TIP: Final = "Rétablir la valeur par défaut"
RESET_ALL: Final = "Rétablir tout"
RESET_ALL_TIP: Final = "Rétablit tous les réglages à leur valeur par défaut (à valider par OK)."
BROWSE: Final = "…"
BROWSE_TIP: Final = "Choisir un dossier"
NOTHING_FOUND: Final = "Aucun réglage ne correspond à la recherche."
DEFAULT_VALUE: Final = "Par défaut : {value}"
ABSENT_VALUE: Final = "{value} (absente)"
EMPTY: Final = "vide"
YES: Final = "oui"
NO: Final = "non"
ONE_SETTING: Final = "{count} réglage"
MANY_SETTINGS: Final = "{count} réglages"
ONE_MODIFIED: Final = "{count} modifié"
MANY_MODIFIED: Final = "{count} modifiés"

PAGE_TEXTS: Final = (
    SEARCH,
    ADVANCED,
    LAST_USED,
    LAST_USED_TIP,
    RESET,
    RESET_TIP,
    RESET_ALL,
    RESET_ALL_TIP,
    BROWSE_TIP,
    NOTHING_FOUND,
    DEFAULT_VALUE,
    ABSENT_VALUE,
    EMPTY,
    YES,
    NO,
    ONE_SETTING,
    MANY_SETTINGS,
    ONE_MODIFIED,
    MANY_MODIFIED,
)


def identity(text: str) -> str:
    """Traduction neutre : le texte français d'origine."""
    return text


def normalize(text: str) -> str:
    """Texte sans accents ni majuscules, pour comparer ``Épaisseur`` à ``epaisseur``."""
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def matches(setting: Setting, query: str, translate: Translate = identity) -> bool:
    """Vrai si tous les mots de ``query`` figurent dans le libellé ou l'infobulle traduits
    (une recherche vide retient tout)."""
    words = normalize(query).split()
    haystack = normalize(f"{translate(setting.label)} {translate(setting.tooltip)}")
    return all(word in haystack for word in words)


def is_shown(setting: Setting, query: str, advanced: bool, translate: Translate = identity) -> bool:
    """Vrai si le réglage est affiché : avancé seulement si on le demande, et trouvé."""
    return (advanced or not setting.advanced) and matches(setting, query, translate)


def format_text(text: str, **values: object) -> str:
    """``text`` dont chaque ``{nom}`` est remplacé par ``values["nom"]`` (pas ``str.format`` : un
    texte traduit ne doit pas pouvoir lever d'erreur de format)."""
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def shown_keys(
    catalog: Catalog, query: str, advanced: bool, translate: Translate = identity
) -> list[str]:
    """Clés des réglages affichés, dans l'ordre du catalogue."""
    return [s.key for s in catalog if is_shown(s, query, advanced, translate)]


def count_modified(catalog: Catalog, values: Mapping[str, Value], keys: Sequence[str]) -> int:
    """Nombre de réglages de ``keys`` dont la valeur de ``values`` diffère du défaut."""
    return sum(1 for key in keys if values[key] != catalog.get(key).default)


def group_summary(total: int, modified: int, translate: Translate = identity) -> str:
    """« (N réglages, M modifiés) » d'un groupe replié ; les modifiés sont omis s'il n'y en a pas
    (pluriel à partir de 2, comme en français)."""
    count = format_text(translate(ONE_SETTING if total < 2 else MANY_SETTINGS), count=total)
    if not modified:
        return f"({count})"
    changed = format_text(
        translate(ONE_MODIFIED if modified < 2 else MANY_MODIFIED), count=modified
    )
    return f"({count}, {changed})"


def format_value(
    setting: Setting,
    value: Value,
    translate: Translate = identity,
    choices: Sequence[tuple[Value, str]] = (),
) -> str:
    """Valeur écrite pour l'utilisateur : oui / non, libellé d'un choix, nombre et unité,
    « vide » pour un texte vide."""
    for stored, label in choices:
        if stored == value:
            return label
    if setting.kind is Kind.BOOL:
        return translate(YES if value else NO)
    if value == "":
        return translate(EMPTY)
    unit = translate(setting.unit) if setting.unit else ""
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return f"{text} {unit}".rstrip() if unit else text
