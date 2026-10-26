# SPDX-License-Identifier: LGPL-2.1-or-later
"""Regroupement des pièces identiques, totaux et fournitures (J2b, J2e : C1' et C2', C3 à C6).

Module privé : la façade ``core.cutlist`` ré-exporte l'API publique.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from freecad.menuiserie.core._validation import decimal_text
from freecad.menuiserie.core.cutlist._model import (
    CutEntry,
    CutLine,
    CutNoticeKind,
    Hardware,
    MaterialTotal,
)
from freecad.menuiserie.core.notice import Notice

_KEY_DECIMALS: Final = 2  # cotes comparées au centième de mm
_DIGITS: Final = re.compile(r"(\d+)")

GroupKey = tuple[object, ...]  # clé de regroupement d'une pièce (C1')


@dataclass(frozen=True)
class CutList:
    """Liste de débit : lignes triées, totaux par matériau, fournitures, avertissements."""

    lines: tuple[CutLine, ...]
    totals: tuple[MaterialTotal, ...]
    hardware: tuple[Hardware, ...]
    warnings: tuple[Notice, ...]

    @property
    def total_mass_kg(self) -> float:
        """Masse de débit de toutes les pièces, en kg."""
        return math.fsum(total.mass_kg for total in self.totals)


def _rounded(*values: float) -> tuple[float, ...]:
    return tuple(round(value, _KEY_DECIMALS) for value in values)


def group_key(entry: CutEntry) -> GroupKey:
    """Clé de regroupement (C1', C4) : matériau, cotes finies, ajouts, surcotes, fil, épaisseurs
    de brut et empreinte de forme (sans repère) ; une pièce en bois n'est jamais groupée avec une
    pièce de bois."""
    record = entry.record
    shape = entry.shape
    finished, allowances, additions = record.finished, record.allowances, entry.additions
    return (
        record.material_id,
        _rounded(finished.length, finished.width, finished.thickness),
        _rounded(additions.length, additions.width, additions.thickness),
        _rounded(allowances.length, allowances.width, allowances.thickness),
        record.grain,
        _rounded(*entry.rough_thicknesses),
        None if shape is None else (shape.volume, shape.area, shape.faces),
    )


def natural_key(text: str) -> tuple[tuple[int, int, str], ...]:
    """Clé d'ordre naturel : « M2 » avant « M10 », sans tenir compte de la casse."""
    parts = _DIGITS.split(text.casefold())
    return tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in parts if part)


def _line_order(line: CutLine) -> tuple[Any, ...]:
    """Premier repère (naturel, sans repère en dernier), matériau, puis cotes décroissantes."""
    sizes = (line.finished.length, line.finished.width, line.finished.thickness)
    return (
        not line.marks,
        tuple(natural_key(mark) for mark in line.marks),
        line.marks,
        natural_key(line.material_name),
        line.material_id,
        tuple(-size for size in sizes),
        tuple(-size for size in (line.rough.length, line.rough.width, line.rough.thickness)),
        line.grain.value,
    )


def _mark_order(mark: str) -> tuple[tuple[tuple[int, int, str], ...], str]:
    return natural_key(mark), mark


def _make_line(entries: Sequence[CutEntry]) -> CutLine:
    first = entries[0]
    record = first.record
    furniture = sorted({entry.furniture for entry in entries if entry.furniture}, key=natural_key)
    marks = sorted({entry.record.mark for entry in entries if entry.record.mark}, key=_mark_order)
    return CutLine(
        marks=tuple(marks),
        quantity=sum(entry.quantity for entry in entries),
        material_id=record.material_id,
        material_name=record.material_name,
        kind=record.kind,
        finished=record.finished,
        rough=first.rough,
        grain=record.grain,
        density=record.density,
        additions=first.additions,
        allowances=record.allowances,
        furniture=tuple(furniture),
        source=first.source,
        over_standard=first.over_standard,
        shape=first.shape,
    )


_THICKNESS_DECIMALS: Final = 1  # épaisseurs regroupées au dixième de millimètre, comme affichées


def _totals(lines: Iterable[CutLine]) -> tuple[MaterialTotal, ...]:
    """Totaux par matériau et par épaisseur de débit (on achète le bois par épaisseur)."""
    by_material: dict[tuple[str, float], list[CutLine]] = defaultdict(list)
    for line in lines:
        by_material[line.material_id, round(line.rough.thickness, _THICKNESS_DECIMALS)].append(line)
    totals = []
    for (_material, thickness), group in by_material.items():
        first = group[0]
        totals.append(
            MaterialTotal(
                material_id=first.material_id,
                material_name=first.material_name,
                kind=first.kind,
                thickness=thickness,
                quantity=sum(line.quantity for line in group),
                volume_m3=math.fsum(line.volume_m3(rough=True) for line in group),
                mass_kg=math.fsum(line.mass_kg(rough=True) for line in group),
                area_m2=math.fsum(line.area_m2() for line in group),
            )
        )
    return tuple(
        sorted(totals, key=lambda t: (natural_key(t.material_name), t.material_id, t.thickness))
    )


def _grouped_hardware(items: Iterable[Hardware]) -> tuple[Hardware, ...]:
    """Fournitures regroupées par (nature, diamètre, longueur), triées."""
    quantities: dict[tuple[object, ...], int] = defaultdict(int)
    first: dict[tuple[object, ...], Hardware] = {}
    for item in items:
        key = (item.kind, *_rounded(item.diameter, item.length))
        first.setdefault(key, item)
        quantities[key] += item.quantity
    grouped = (
        Hardware(item.kind, item.diameter, item.length, quantities[key])
        for key, item in first.items()
    )
    return tuple(sorted(grouped, key=lambda h: (h.kind.value, h.diameter, h.length)))


def _over_standard_notice(line: CutLine) -> Notice:
    params = {"thickness": decimal_text(line.rough.thickness), "material": line.material_name}
    return Notice(CutNoticeKind.ROUGH_THICKNESS_OVER_STANDARD, params)


def _warnings(lines: Sequence[CutLine], unmarked: int) -> tuple[Notice, ...]:
    """Repère porté par plusieurs lignes (C2') ; pièces sans repère (Q5) ; épaisseur de débit
    au-delà des épaisseurs de brut, une fois par ligne (B2)."""
    counts: dict[str, int] = defaultdict(int)
    for line in lines:
        for mark in line.marks:
            counts[mark] += 1
    notices = [
        Notice(CutNoticeKind.REPEATED_MARK, {"mark": mark})
        for mark in sorted(counts, key=_mark_order)
        if counts[mark] > 1
    ]
    if unmarked:
        notices.append(Notice(CutNoticeKind.MISSING_MARK, {"count": str(unmarked)}))
    notices.extend(_over_standard_notice(line) for line in lines if line.over_standard)
    return tuple(notices)


def build_cut_list(entries: Iterable[CutEntry], hardware: Iterable[Hardware] = ()) -> CutList:
    """Liste de débit : regroupe les entrées de même clé, trie, totalise par matériau et
    regroupe les fournitures. Les avertissements ne bloquent jamais."""
    groups: dict[GroupKey, list[CutEntry]] = {}
    unmarked = 0
    for entry in entries:
        groups.setdefault(group_key(entry), []).append(entry)
        if not entry.record.mark:
            unmarked += entry.quantity
    lines = tuple(sorted((_make_line(group) for group in groups.values()), key=_line_order))
    warnings = _warnings(lines, unmarked)
    return CutList(lines, _totals(lines), _grouped_hardware(hardware), warnings)
