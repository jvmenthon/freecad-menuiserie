# SPDX-License-Identifier: LGPL-2.1-or-later
"""Logique de l'aperçu d'un import de réglages, sans Qt : lignes du tableau et sélection (ADR 0069).

Python pur, donc testé seul ; la fenêtre (:mod:`.page_import`) n'en est que l'habillage. Les
textes passent par une fonction de traduction injectée ; ``IMPORT_TEXTS`` liste ceux de l'aperçu
et de l'échange, que l'atelier doit déclarer à la traduction.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from .catalog import REMEMBER_SUFFIX, Catalog
from .exchange import Change
from .page_model import (
    LAST_USED,
    NO,
    YES,
    Choices,
    Translate,
    format_text,
    format_value,
    identity,
)

__all__ = [
    "IMPORT_TEXTS",
    "MAX_NAMES_SHOWN",
    "ImportOffer",
    "ImportRow",
    "build_rows",
    "changes_header",
    "chosen",
    "chosen_values",
    "ignored_text",
]

MAX_NAMES_SHOWN: Final = 5  # clés inconnues citées dans le bandeau, les autres sont comptées

TITLE: Final = "Importer les réglages de l'atelier"
EXCHANGE_LABEL: Final = "Réglages de l'atelier"
EXCHANGE_TIP: Final = "Exporte ou importe les réglages dans un fichier JSON."
EXPORT: Final = "Exporter…"
IMPORT: Final = "Importer…"
EXPORT_TITLE: Final = "Exporter les réglages de l'atelier"
IMPORT_FILE_TITLE: Final = "Choisir le fichier des réglages à importer"
JSON_FILTER: Final = "Fichiers JSON (*.json)"
EXPORTED: Final = "Réglages exportés dans {path}."
UNSAVED: Final = "Les modifications non enregistrées ne sont pas exportées."
NO_CHANGE: Final = "Aucun réglage à changer."
CHANGES_ONE: Final = "Fichier : {path} · {count} réglage changé"
CHANGES_MANY: Final = "Fichier : {path} · {count} réglages changés"
IGNORED_ONE: Final = "{count} réglage inconnu ignoré : {names}."
IGNORED_MANY: Final = "{count} réglages inconnus ignorés : {names}."
NOTE: Final = (
    "Les réglages cochés sont repris dans la page. Ils sont enregistrés avec OK ou Appliquer."
)
TAKE: Final = "Reprendre la sélection"
CANCEL: Final = "Annuler"
COLUMN_GROUP: Final = "Groupe"
COLUMN_SETTING: Final = "Réglage"
COLUMN_CURRENT: Final = "Actuel"
COLUMN_IMPORTED: Final = "Importé"
SELECT_TIP: Final = "Reprendre ce réglage"

IMPORT_TEXTS: Final = (
    TITLE,
    EXCHANGE_LABEL,
    EXCHANGE_TIP,
    EXPORT,
    IMPORT,
    EXPORT_TITLE,
    IMPORT_FILE_TITLE,
    JSON_FILTER,
    EXPORTED,
    UNSAVED,
    NO_CHANGE,
    CHANGES_ONE,
    CHANGES_MANY,
    IGNORED_ONE,
    IGNORED_MANY,
    NOTE,
    TAKE,
    CANCEL,
    COLUMN_GROUP,
    COLUMN_SETTING,
    COLUMN_CURRENT,
    COLUMN_IMPORTED,
    SELECT_TIP,
)


@dataclass(frozen=True)
class ImportRow:
    """Ligne de l'aperçu : ``key`` identifie le réglage (clé du fichier d'échange), ``current``
    et ``imported`` sont les valeurs lisibles, ``value`` la valeur à reprendre."""

    key: str
    group: str
    label: str
    current: str
    imported: str
    value: Any


@dataclass(frozen=True)
class ImportOffer:
    """Ce qu'un fichier propose : lignes de l'aperçu et éléments ignorés (clés inconnues)."""

    rows: tuple[ImportRow, ...] = ()
    ignored: tuple[str, ...] = ()


def _row(catalog: Catalog, change: Change, translate: Translate, choices: Choices) -> ImportRow:
    """Ligne d'un changement ; la case « Dernier utilisé » d'un réglage est une ligne à part."""
    remember = change.key.endswith(REMEMBER_SUFFIX)
    setting = catalog.get(change.key.removesuffix(REMEMBER_SUFFIX))
    label = translate(setting.label)
    if remember:
        label = f"{label} ({translate(LAST_USED)})"
        old, new = (translate(YES if value else NO) for value in (change.old, change.new))
    else:
        options = choices.get(setting.key, ())
        old, new = (
            format_value(setting, value, translate, options) for value in (change.old, change.new)
        )
    return ImportRow(change.key, translate(setting.group), label, old, new, change.new)


def build_rows(
    catalog: Catalog,
    changes: Sequence[Change],
    translate: Translate = identity,
    choices: Choices | None = None,
) -> list[ImportRow]:
    """Lignes de l'aperçu pour les ``changes`` d'un import, dans leur ordre."""
    return [_row(catalog, change, translate, choices or {}) for change in changes]


def changes_header(path: str, count: int, translate: Translate = identity) -> str:
    """« Fichier : <chemin> · N réglages changés » (pluriel à partir de 2, comme en français)."""
    text = translate(CHANGES_ONE if count < 2 else CHANGES_MANY)
    return format_text(text, path=path, count=count)


def ignored_text(ignored: Sequence[str], translate: Translate = identity) -> str:
    """Bandeau des éléments ignorés ; vide s'il n'y en a pas. Au plus ``MAX_NAMES_SHOWN`` noms
    sont cités, suivis de « … » s'il y en a d'autres."""
    if not ignored:
        return ""
    names = ", ".join(f"« {name} »" for name in ignored[:MAX_NAMES_SHOWN])
    if len(ignored) > MAX_NAMES_SHOWN:
        names += ", …"
    text = translate(IGNORED_ONE if len(ignored) < 2 else IGNORED_MANY)
    return format_text(text, count=len(ignored), names=names)


def chosen(rows: Sequence[ImportRow], keys: Collection[str]) -> list[ImportRow]:
    """Lignes dont la clé est dans ``keys`` (cases cochées), dans l'ordre de l'aperçu."""
    return [row for row in rows if row.key in keys]


def chosen_values(rows: Sequence[ImportRow], keys: Collection[str]) -> Mapping[str, Any]:
    """Clé → valeur à reprendre, pour les lignes cochées."""
    return {row.key: row.value for row in chosen(rows, keys)}
