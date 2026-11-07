# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture des fichiers de catalogue et fusion des sources par identifiant (ADR 0033)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from freecad.menuiserie.core.hardware._messages import (
    FILE_BUILTIN_MISSING,
    MERGE_REPLACED,
)
from freecad.menuiserie.core.hardware._model import Catalog, HardwareItem
from freecad.menuiserie.core.hardware._parser import parse_catalog
from freecad.menuiserie.core.materials import (
    BUILTIN_SOURCE,
    LibraryFormatError,
    LibraryIssue,
    Severity,
    capped,
    make_issue,
    read_json_file,
)


@dataclass(frozen=True)
class CatalogSource:
    """Un fichier de catalogue et le nom sous lequel il est cité dans les anomalies."""

    path: Path
    label: str


def read_catalog_file(
    source: CatalogSource,
) -> tuple[list[HardwareItem], list[LibraryIssue]] | None:
    """Références et anomalies d'un fichier ; ``None`` si le fichier est absent."""
    try:
        data = read_json_file(source.path, source.label)
    except FileNotFoundError:
        return None
    except LibraryFormatError as error:
        return [], [error.issue]
    return parse_catalog(data, source.label)


def merge_catalogs(
    layers: Sequence[tuple[str, Sequence[HardwareItem]]],
) -> tuple[Catalog, list[LibraryIssue]]:
    """Fusionne des sources par ``id`` ; ``layers`` va de la plus proche de l'utilisateur à la
    plus lointaine (personnel, paquets, intégré). La première source qui porte un ``id`` l'emporte
    et garde la place de la plus lointaine : une info signale le remplacement."""
    merged: dict[str, HardwareItem] = {}
    issues: list[LibraryIssue] = []
    for label, items in reversed(layers):
        for item in items:
            if item.id in merged:
                params = {"id": item.id}
                issues.append(make_issue(Severity.INFO, label, MERGE_REPLACED, item.id, **params))
            merged[item.id] = item
    return Catalog(tuple(merged.values())), issues


def load_catalog(
    builtin: Path, user_sources: Sequence[CatalogSource] = ()
) -> tuple[Catalog, list[LibraryIssue]]:
    """Charge le catalogue intégré, puis le fusionne avec les sources de l'utilisateur.

    ``user_sources`` va de la plus proche de l'utilisateur à la plus lointaine ; une source absente
    est ignorée sans anomalie. Au plus ``MAX_ISSUES`` anomalies sont renvoyées.
    """
    issues: list[LibraryIssue] = []
    layers: list[tuple[str, Sequence[HardwareItem]]] = []
    for source in user_sources:
        result = read_catalog_file(source)
        if result is not None:
            layers.append((source.label, result[0]))
            issues += result[1]
    builtin_result = read_catalog_file(CatalogSource(builtin, BUILTIN_SOURCE))
    if builtin_result is None:
        missing = make_issue(
            Severity.ERROR, BUILTIN_SOURCE, FILE_BUILTIN_MISSING, path=str(builtin)
        )
        builtin_result = [], [missing]
    layers.append((BUILTIN_SOURCE, builtin_result[0]))
    issues += builtin_result[1]
    catalog, merge_issues = merge_catalogs(layers)
    return catalog, capped([*issues, *merge_issues])
