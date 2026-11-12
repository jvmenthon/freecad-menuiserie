# SPDX-License-Identifier: LGPL-2.1-or-later
"""Validation d'un document JSON de catalogue de quincaillerie déjà décodé (format 1).

Une entrée invalide est ignorée avec une anomalie ; le reste du fichier est gardé.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from freecad.menuiserie.core._validation import (
    FrozenMapping,
    bounded_float,
    decimal_text,
    has_forbidden_character,
    nfc,
)
from freecad.menuiserie.core.hardware._families import MAX_PARAM_MM, MIN_PARAM_MM, family_of
from freecad.menuiserie.core.hardware._messages import (
    ENTRY_DUPLICATE_ID,
    ENTRY_DUPLICATE_KEY,
    ENTRY_INVALID_FIELD,
    ENTRY_INVALID_PARAM,
    ENTRY_NOT_OBJECT,
    ENTRY_UNKNOWN_FAMILY,
    ENTRY_UNKNOWN_PARAM,
    ROOT_FORMAT,
    ROOT_ITEMS_INVALID,
    ROOT_NOT_OBJECT,
    TOO_MANY_ITEMS,
)
from freecad.menuiserie.core.hardware._model import HardwareItem
from freecad.menuiserie.core.materials import (
    JsonObject,
    LibraryIssue,
    Severity,
    make_issue,
    normalized_id,
)
from freecad.menuiserie.core.text import quoted_value

FORMAT_VERSION: Final = 1
MAX_ITEMS: Final = 500
MAX_TEXT_LENGTH: Final = 80
MAX_SOURCE_LENGTH: Final = 300


def _text(value: object, *, required: bool, limit: int = MAX_TEXT_LENGTH) -> str | None:
    """Texte NFC de 1 à ``limit`` caractères permis ; chaîne vide si absent et facultatif ;
    ``None`` si invalide."""
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        return None
    text = nfc(value).strip()
    if not 1 <= len(text) <= limit or has_forbidden_character(text):
        return None
    return text


def _params(raw: object, family_key: str) -> FrozenMapping | tuple[str, str] | None:
    """Cotes de l'entrée, ou ``(gabarit, nom)`` de l'erreur ; ``None`` si ``raw`` n'est pas un
    objet. Les cotes d'une famille connue sont exactement celles de la famille."""
    if not isinstance(raw, Mapping):
        return None
    family = family_of(family_key)
    values: dict[str, str] = {}
    specs = {} if family is None else {spec.name: spec for spec in family.params}
    for name, value in raw.items():
        spec = specs.get(name)
        if family is not None and spec is None:
            return (ENTRY_UNKNOWN_PARAM, str(name))
        low, high = (spec.minimum, spec.maximum) if spec else (MIN_PARAM_MM, MAX_PARAM_MM)
        number = bounded_float(value, low, high)
        if number is None:
            return (ENTRY_INVALID_PARAM, str(name))
        values[str(name)] = repr(number)
    for name, spec in specs.items():
        if name not in values and not spec.optional:
            return (ENTRY_INVALID_PARAM, name)
    return FrozenMapping(values)


def _invalid(source: str, item_id: str, field: str) -> LibraryIssue:
    return make_issue(Severity.ERROR, source, ENTRY_INVALID_FIELD, item_id, id=item_id, field=field)


def _bad_param(source: str, item_id: str, template: str, name: str, family: str) -> LibraryIssue:
    known = family_of(family)
    specs = {} if known is None else {spec.name: spec for spec in known.params}
    spec = specs.get(name)
    low, high = (spec.minimum, spec.maximum) if spec else (MIN_PARAM_MM, MAX_PARAM_MM)
    return make_issue(
        Severity.ERROR,
        source,
        template,
        item_id,
        id=item_id,
        param=quoted_value(name),
        min=decimal_text(low),
        max=decimal_text(high),
    )


def parse_item(
    raw: Mapping[str, object], source: str
) -> tuple[HardwareItem | None, list[LibraryIssue]]:
    """Référence validée et anomalies (erreur : référence ignorée ; info : famille inconnue)."""
    item_id = normalized_id(raw.get("id"))
    shown = item_id or quoted_value(raw.get("id"))
    if item_id is None:
        return None, [_invalid(source, shown, "id")]
    if isinstance(raw, JsonObject):
        return None, [make_issue(Severity.ERROR, source, ENTRY_DUPLICATE_KEY, item_id, id=item_id)]
    texts = {
        "family": _text(raw.get("family"), required=True),
        "label": _text(raw.get("label"), required=True),
        "source": _text(raw.get("source"), required=True, limit=MAX_SOURCE_LENGTH),
        "manufacturer": _text(raw.get("manufacturer"), required=False),
        "reference": _text(raw.get("reference"), required=False),
        "distributor_reference": _text(raw.get("distributor_reference"), required=False),
    }
    for field, value in texts.items():
        if value is None:
            return None, [_invalid(source, item_id, field)]
    family = str(texts["family"])
    params = _params(raw.get("params"), family)
    if params is None:
        return None, [_invalid(source, item_id, "params")]
    if isinstance(params, tuple):
        return None, [_bad_param(source, item_id, params[0], params[1], family)]
    issues: list[LibraryIssue] = []
    if family_of(family) is None:
        issues.append(
            make_issue(
                Severity.INFO,
                source,
                ENTRY_UNKNOWN_FAMILY,
                item_id,
                id=item_id,
                family=quoted_value(family),
            )
        )
    item = HardwareItem(
        id=item_id,
        family=family,
        label=str(texts["label"]),
        params=params,
        source=str(texts["source"]),
        manufacturer=str(texts["manufacturer"]),
        reference=str(texts["reference"]),
        distributor_reference=str(texts["distributor_reference"]),
    )
    return item, issues


def parse_catalog(data: object, source: str) -> tuple[list[HardwareItem], list[LibraryIssue]]:
    """Références et anomalies d'un document déjà décodé (jamais d'exception)."""
    if not isinstance(data, Mapping):
        return [], [make_issue(Severity.ERROR, source, ROOT_NOT_OBJECT)]
    version = data.get("format")
    if isinstance(version, bool) or version != FORMAT_VERSION:
        params = {"supported": str(FORMAT_VERSION), "format": quoted_value(version)}
        return [], [make_issue(Severity.ERROR, source, ROOT_FORMAT, **params)]
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        return [], [make_issue(Severity.ERROR, source, ROOT_ITEMS_INVALID)]
    issues: list[LibraryIssue] = []
    if len(raw_items) > MAX_ITEMS:
        issues.append(make_issue(Severity.ERROR, source, TOO_MANY_ITEMS, max=str(MAX_ITEMS)))
    items: list[HardwareItem] = []
    seen: set[str] = set()
    for position, raw in enumerate(raw_items[:MAX_ITEMS], start=1):
        if not isinstance(raw, Mapping):
            params = {"position": str(position)}
            issues.append(make_issue(Severity.ERROR, source, ENTRY_NOT_OBJECT, **params))
            continue
        item, item_issues = parse_item(raw, source)
        issues += item_issues
        if item is None:
            continue
        if item.id in seen:
            issues.append(
                make_issue(Severity.WARNING, source, ENTRY_DUPLICATE_ID, item.id, id=item.id)
            )
            continue
        seen.add(item.id)
        items.append(item)
    return items, issues
