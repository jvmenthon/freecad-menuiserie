# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion du fichier utilisateur sur la bibliothèque intégrée, et chargement complet."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from freecad.menuiserie.core.materials._issues import LibraryIssue, Severity, capped, make_issue
from freecad.menuiserie.core.materials._messages import (
    BUILTIN_SOURCE,
    ENTRY_DUPLICATE_ID,
    FILE_BUILTIN_MISSING,
    MERGE_LABEL_TAKEN,
    MERGE_REPLACED,
)
from freecad.menuiserie.core.materials._model import Material, MaterialLibrary
from freecad.menuiserie.core.materials._reader import read_existing_file, read_materials_file


def _label(material: Material) -> str:
    """Libellé français (déjà en forme NFC) : clé d'unicité de la bibliothèque."""
    return material.name("fr")


def _rejected(source: str, material: Material, label_owner: str | None) -> LibraryIssue:
    """Erreur de fusion : identifiant en double, ou libellé porté par ``label_owner``."""
    if label_owner is None:
        return make_issue(
            Severity.ERROR, source, ENTRY_DUPLICATE_ID, material.id, id=material.id, field="id"
        )
    return make_issue(
        Severity.ERROR,
        source,
        MERGE_LABEL_TAKEN,
        material.id,
        id=material.id,
        field="name",
        label=_label(material),
        other=label_owner,
    )


def _merge_builtin(builtin: Sequence[Material]) -> tuple[dict[str, Material], list[LibraryIssue]]:
    """Matériaux intégrés uniques (identifiant puis libellé), dans l'ordre ; doublons rejetés."""
    by_id: dict[str, Material] = {}
    owner_of_label: dict[str, str] = {}
    issues: list[LibraryIssue] = []
    for material in builtin:
        owner = owner_of_label.get(_label(material))
        if material.id in by_id or owner is not None:
            shown_owner = None if material.id in by_id else owner
            issues.append(_rejected(BUILTIN_SOURCE, material, shown_owner))
            continue
        by_id[material.id] = material
        owner_of_label[_label(material)] = material.id
    return by_id, issues


@dataclass(frozen=True)
class _Candidate:
    """Entrée utilisateur retenue provisoirement, avec sa position dans le fichier."""

    position: int
    material: Material


def _label_losers(
    builtin: Mapping[str, Material], candidates: Mapping[str, _Candidate]
) -> list[str]:
    """Identifiants utilisateur qui perdent un libellé disputé, au vu de l'état courant.

    Un matériau intégré non remplacé garde toujours son libellé ; entre deux entrées
    utilisateur, la première du fichier le garde.
    """
    holders: dict[str, list[tuple[int, str]]] = {}
    for material in builtin.values():
        if material.id not in candidates:
            holders.setdefault(_label(material), []).append((-1, material.id))
    for candidate in candidates.values():
        holders.setdefault(_label(candidate.material), []).append(
            (candidate.position, candidate.material.id)
        )
    losers: list[str] = []
    for owners in holders.values():
        losers += [material_id for _, material_id in sorted(owners)[1:]]
    return losers


def _user_candidates(
    user: Sequence[Material], source: str
) -> tuple[dict[str, _Candidate], dict[int, LibraryIssue]]:
    """Première entrée de chaque identifiant ; les suivantes sont rejetées (erreur)."""
    candidates: dict[str, _Candidate] = {}
    issues: dict[int, LibraryIssue] = {}
    for position, material in enumerate(user):
        if material.id in candidates:
            issues[position] = _rejected(source, material, None)
        else:
            candidates[material.id] = _Candidate(position, material)
    return candidates, issues


def _merge_user(
    builtin: Mapping[str, Material], user: Sequence[Material], source: str
) -> tuple[list[Material], list[LibraryIssue]]:
    """Applique tous les remplacements et ajouts, puis rétablit l'unicité des libellés.

    Le résultat ne dépend pas de l'ordre des remplacements : deux matériaux intégrés peuvent
    échanger leurs libellés. Une entrée rejetée pour son libellé rend sa place au matériau
    intégré qu'elle remplaçait, ce qui peut à son tour rejeter une autre entrée.
    """
    candidates, issues = _user_candidates(user, source)
    label_rejected: list[_Candidate] = []
    while losers := _label_losers(builtin, candidates):
        label_rejected += [candidates.pop(material_id) for material_id in losers]
    merged = [candidates[i].material if i in candidates else m for i, m in builtin.items()]
    merged += [c.material for c in candidates.values() if c.material.id not in builtin]
    owner_of_label = {_label(material): material.id for material in merged}
    for rejected in label_rejected:
        owner = owner_of_label[_label(rejected.material)]
        issues[rejected.position] = _rejected(source, rejected.material, owner)
    for candidate in candidates.values():
        if candidate.material.id in builtin:
            material_id = candidate.material.id
            info = make_issue(Severity.INFO, source, MERGE_REPLACED, material_id, id=material_id)
            issues[candidate.position] = info
    return merged, [issues[position] for position in sorted(issues)]


def merge_materials(
    builtin: Sequence[Material], user: Sequence[Material], user_source: str
) -> tuple[MaterialLibrary, list[LibraryIssue]]:
    """Fusionne les matériaux de l'utilisateur sur la bibliothèque intégrée (par identifiant).

    Identifiant nouveau : ajouté à la fin. Identifiant existant : remplace entièrement le
    matériau intégré, à sa place (anomalie info). Une fois tous les remplacements appliqués,
    une entrée utilisateur dont le libellé français est porté par un autre matériau est
    rejetée (erreur) ; le résultat ne dépend pas de l'ordre des remplacements.
    """
    by_id, issues = _merge_builtin(builtin)
    merged, user_issues = _merge_user(by_id, user, user_source)
    return MaterialLibrary(merged), capped([*issues, *user_issues])


def load_library(
    builtin_path: Path, user_path: Path | None
) -> tuple[MaterialLibrary, list[LibraryIssue]]:
    """Charge la bibliothèque intégrée, puis la fusionne avec le fichier utilisateur s'il existe.

    Au plus ``MAX_ISSUES`` anomalies sont renvoyées, suivies d'une anomalie de synthèse.
    """
    result = read_existing_file(builtin_path, BUILTIN_SOURCE)
    if result is None:
        missing = make_issue(
            Severity.ERROR, BUILTIN_SOURCE, FILE_BUILTIN_MISSING, path=str(builtin_path)
        )
        result = [], [missing]
    builtin, issues = result
    user: list[Material] = []
    user_source = "" if user_path is None else str(user_path)
    if user_path is not None:
        user, user_issues = read_materials_file(user_path, user_source)
        issues += user_issues
    library, merge_issues = merge_materials(builtin, user, user_source)
    return library, capped([*issues, *merge_issues])
