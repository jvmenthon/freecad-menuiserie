# SPDX-License-Identifier: LGPL-2.1-or-later
"""Anomalies de la bibliothèque : gravité, création et plafonnement."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

from freecad.menuiserie.core._validation import FrozenMapping
from freecad.menuiserie.core.materials._messages import (
    TOO_MANY_ISSUES,
    TOO_MANY_ISSUES_SEVERAL_SOURCES,
)

MAX_ISSUES: Final = 200
MAX_LISTED_KEYS: Final = 5


class Severity(Enum):
    """Gravité d'une anomalie de la bibliothèque."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


_SEVERITY_RANK: Final = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}


@dataclass(frozen=True)
class LibraryIssue:
    """Anomalie rencontrée en lisant ou en fusionnant une bibliothèque.

    ``template`` est un gabarit français marqué pour la traduction ; ``params``
    contient toujours ``source`` et sert à le remplir (``template.format(**params)``).
    """

    severity: Severity
    source: str
    template: str
    params: Mapping[str, str]
    material_id: str | None = None

    def __post_init__(self) -> None:
        params = FrozenMapping({"source": self.source, **self.params})
        object.__setattr__(self, "params", params)

    def format(self) -> str:
        """Gabarit non traduit, rempli avec ses paramètres (tests, journaux)."""
        return self.template.format_map(self.params)


class LibraryFormatError(ValueError):
    """Anomalie bloquante d'un fichier ou d'une entrée ; usage interne, convertie en anomalie."""

    def __init__(self, issue: LibraryIssue) -> None:
        super().__init__(issue.format())
        self.issue = issue


def make_issue(
    severity: Severity,
    source: str,
    template: str,
    material_id: str | None = None,
    **params: str,
) -> LibraryIssue:
    """Anomalie de gabarit ``template`` ; ``params`` le remplissent avec ``source``."""
    return LibraryIssue(severity, source, template, params, material_id)


def file_error(source: str, template: str, **params: str) -> LibraryFormatError:
    """Erreur qui fait ignorer tout le fichier ``source``."""
    return LibraryFormatError(make_issue(Severity.ERROR, source, template, **params))


def capped(issues: list[LibraryIssue]) -> list[LibraryIssue]:
    """Au plus ``MAX_ISSUES`` anomalies, plus une anomalie de synthèse pour les suivantes."""
    if len(issues) <= MAX_ISSUES:
        return issues
    omitted = issues[MAX_ISSUES:]
    severity = max((issue.severity for issue in omitted), key=_SEVERITY_RANK.__getitem__)
    count = str(sum(_represented_count(issue) for issue in omitted))
    sources = {issue.source for issue in omitted}
    if len(sources) == 1:
        summary = make_issue(severity, sources.pop(), TOO_MANY_ISSUES, count=count)
    else:
        summary = make_issue(severity, "", TOO_MANY_ISSUES_SEVERAL_SOURCES, count=count)
    return [*issues[:MAX_ISSUES], summary]


def _represented_count(issue: LibraryIssue) -> int:
    """Nombre d'anomalies que ``issue`` représente : une synthèse compte ses omissions."""
    if issue.template in (TOO_MANY_ISSUES, TOO_MANY_ISSUES_SEVERAL_SOURCES):
        return int(issue.params["count"])
    return 1


def unknown_keys_params(keys: Sequence[str]) -> dict[str, str]:
    """Paramètres ``keys`` (au plus ``MAX_LISTED_KEYS`` clés déjà échappées) et ``more``."""
    listed = ", ".join(f"« {key} »" for key in keys[:MAX_LISTED_KEYS])
    return {"keys": listed, "more": str(max(len(keys) - MAX_LISTED_KEYS, 0))}
