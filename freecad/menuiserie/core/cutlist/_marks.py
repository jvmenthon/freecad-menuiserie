# SPDX-License-Identifier: LGPL-2.1-or-later
"""Numérotation automatique des repères, logique pure (J2e, critère N1).

Module privé : la façade ``core.cutlist`` ré-exporte l'API publique. Rien n'est modifié ici :
la fonction renvoie l'attribution (clé de regroupement → repère) que ``features/`` écrira dans le
document (J2f).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from itertools import count
from typing import Final

from freecad.menuiserie.core.cutlist._build import GroupKey, group_key, natural_key
from freecad.menuiserie.core.cutlist._model import CutEntry

DEFAULT_MARK_PREFIX: Final = "M"


def _used_numbers(marks: Iterable[str], prefix: str) -> set[int]:
    """Numéros ``n`` des repères de la forme ``<prefix><n>`` (chiffres seuls après le préfixe)."""
    pattern = re.compile(re.escape(prefix) + r"([0-9]+)")
    matches = (pattern.fullmatch(mark) for mark in marks)
    return {int(match.group(1)) for match in matches if match}


def _numbering_order(group: list[CutEntry]) -> tuple[object, ...]:
    """Ensemble (ordre naturel, sans ensemble en dernier), puis cotes finies décroissantes."""
    first = group[0].record
    furniture = sorted({entry.furniture for entry in group if entry.furniture}, key=natural_key)
    finished = (first.finished.length, first.finished.width, first.finished.thickness)
    return (
        not furniture,
        tuple(natural_key(name) for name in furniture),
        tuple(-size for size in finished),
        natural_key(first.material_name),
        first.material_id,
    )


def assign_marks(
    entries: Iterable[CutEntry],
    prefix: str = DEFAULT_MARK_PREFIX,
    used: Iterable[str] = (),
) -> Mapping[GroupKey, str]:
    """Repère ``<prefix><n>`` de chaque groupe de pièces sans repère (même clé que la liste de
    débit, C1') : un repère par groupe, le premier numéro libre. Sont sautés les repères de la
    forme ``<prefix><n>`` portés par ``entries`` ou donnés dans ``used``. Ordre d'attribution :
    ensemble, puis cotes finies décroissantes. Les pièces qui ont déjà un repère n'apparaissent
    pas dans le résultat. Ne modifie rien."""
    items = list(entries)
    groups: dict[GroupKey, list[CutEntry]] = {}
    for entry in items:
        if not entry.record.mark:
            groups.setdefault(group_key(entry), []).append(entry)
    taken = _used_numbers([*used, *(entry.record.mark for entry in items)], prefix)
    free = (number for number in count(1) if number not in taken)
    ordered = sorted(groups.items(), key=lambda item: _numbering_order(item[1]))
    return {key: f"{prefix}{next(free)}" for key, _ in ordered}
