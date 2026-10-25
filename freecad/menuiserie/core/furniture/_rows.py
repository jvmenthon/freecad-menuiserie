# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rangées, cellules et partage de la différence (ADR 0019 ; spécification, § 1.1 à 1.6).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Sur un axe, un membre ne
se règle que sur les pièces en vis-à-vis (**rangée**). Les faces de la rangée découpent l'axe en
**cellules** : rigides (épaisseurs, pièces verrouillées, écarts à distance fixe), libres ou
absorbantes. La différence de cote se répartit entre les cellules non rigides ; chaque point de
coupe devient une fonction affine (:class:`Linear`) de la cote de l'ensemble et des épaisseurs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from freecad.menuiserie.core.furniture._gaps import face_of, partners
from freecad.menuiserie.core.furniture._linear import Linear
from freecad.menuiserie.core.furniture._model import (
    THICKNESS,
    Edge,
    FurnitureAxis,
    InteriorMode,
    KeptGap,
    Member,
    gap_term,
)
from freecad.menuiserie.core.furniture._spans import Span, Spans
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM


@dataclass(frozen=True)
class Row:
    """Rangée d'un membre sur un axe : clés de ses membres (lui compris, dans l'ordre des
    membres), clés des membres verrouillés, et vrai si la rangée est bloquée (aucune cellule
    ne peut absorber un changement)."""

    axis: FurnitureAxis
    keys: tuple[str, ...]
    locked: tuple[str, ...]
    blocked: bool = False


@dataclass(frozen=True)
class SolvedRow:
    """Rangée résolue : une fonction affine par point de coupe, ``points`` triés (mm).

    ``kept`` : un écart fixe a dû absorber la différence d'un membre seul sur l'axe de son
    épaisseur (avertissement ``ThicknessKept``) ; ``split`` : clés des Distances gardées
    coupées par une autre face, figées en constantes (avertissement ``GapSplit``)."""

    row: Row
    points: tuple[float, ...]
    coordinates: tuple[Linear, ...]
    kept: bool = False
    split: tuple[str, ...] = ()

    def coordinate(self, value: float) -> Linear:
        """Fonction affine du point de coupe qui vaut ``value`` (à la tolérance près)."""
        return self.coordinates[_index(self.points, value)]


class _Kind(Enum):
    RIGID = "rigid"
    FREE = "free"
    ABSORBING = "absorbing"
    GAP = "gap"  # écart non couvert, pas encore classé


@dataclass
class _Cell:
    start: float
    end: float
    kind: _Kind = _Kind.GAP
    value: Linear | None = None
    covered: bool = False
    edge_gap: bool = False  # écart au bord rigide (distance fixe)

    @property
    def length(self) -> float:
        return self.end - self.start

    def make_rigid(self, value: Linear | None = None) -> None:
        self.kind = _Kind.RIGID
        self.value = value if value is not None else Linear.of(0.0, self.length)


@dataclass(frozen=True)
class _Entry:
    member: Member
    span: Span
    lo: int  # indice du point de coupe de la face de début
    hi: int

    def covers(self, cell: int) -> bool:
        return self.lo <= cell < self.hi

    @property
    def thin(self) -> bool:
        """Vrai si l'axe est celui de l'épaisseur de la pièce."""
        return self.span.local == THICKNESS

    @property
    def rigid(self) -> bool:
        return self.thin or self.member.locked


def _index(points: Sequence[float], value: float) -> int:
    return min(range(len(points)), key=lambda i: abs(points[i] - value))


def _overlap(first: Span, second: Span) -> bool:
    return min(first.hi, second.hi) - max(first.lo, second.lo) > CONTACT_TOLERANCE_MM


def row_keys(
    key: str, axis: FurnitureAxis, spans: Mapping[str, Spans], gaps: Sequence[KeptGap] = ()
) -> list[str]:
    """Clés du membre ``key`` et de ses vis-à-vis sur ``axis`` (étendues qui se recouvrent de
    plus de la tolérance sur chacun des deux autres axes, ou reliées à lui par une Distance
    gardée sur cet axe : règle 1 bis), dans l'ordre de ``spans``."""
    others = [other for other in FurnitureAxis if other is not axis]
    centre = spans[key]
    linked = partners(key, axis, gaps)
    return [
        found
        for found, found_spans in spans.items()
        if found == key
        or found in linked
        or all(_overlap(centre[o], found_spans[o]) for o in others)
    ]


def _cut_points(spans: Sequence[Span], size: float) -> list[float]:
    values = sorted([0.0, size, *(v for span in spans for v in (span.lo, span.hi))])
    points: list[float] = []
    for value in values:
        if not points or value - points[-1] > CONTACT_TOLERANCE_MM:
            points.append(value)
    return points


def _thickness_value(cell: _Cell, index: int, covering: Sequence[_Entry]) -> Linear:
    """Épaisseur vivante si la cellule est exactement celle d'une pièce, sinon sa longueur."""
    for entry in sorted(covering, key=lambda found: found.member.key):
        if entry.thin and (entry.lo, entry.hi) == (index, index + 1):
            return Linear.of(0.0, 0.0, {entry.member.key: 1.0})
    return Linear.of(0.0, cell.length)


def _first_pass(entries: Sequence[_Entry], points: Sequence[float], inside: range) -> list[_Cell]:
    """Cellules hors de l'ensemble ou couvertes : rigides (épaisseur, pièce verrouillée) ou
    libres ; les autres restent des écarts à classer."""
    cells = [_Cell(points[i], points[i + 1]) for i in range(len(points) - 1)]
    for index, cell in enumerate(cells):
        covering = [entry for entry in entries if entry.covers(index)]
        cell.covered = bool(covering)
        if index not in inside:
            cell.make_rigid()
        elif any(entry.rigid for entry in covering):
            cell.make_rigid(_thickness_value(cell, index, covering))
        elif covering:
            cell.kind = _Kind.FREE
    return cells


def _apply_gaps(
    cells: Sequence[_Cell],
    points: Sequence[float],
    gaps: Sequence[KeptGap],
    spans: Mapping[str, Spans],
    inside: range,
) -> list[str]:
    """Règle 4.2 bis : l'intervalle entre les deux faces de chaque Distance gardée est un bloc
    rigide virtuel. Une seule cellule : ``Name.Value`` ; plusieurs (coupé par une autre face) :
    constantes figées, renvoie leurs clés. Un intervalle nul ne change rien."""
    split: list[str] = []
    for gap in gaps:
        ends = sorted(
            _index(points, face_of(spans[name][gap.axis], at_end))
            for name, at_end in ((gap.a, gap.a_end), (gap.b, gap.b_end))
        )
        covered = [i for i in range(ends[0], ends[1]) if i in inside]
        if len(covered) == 1:
            cells[covered[0]].make_rigid(Linear.of(0.0, 0.0, {gap_term(gap.key): 1.0}))
        elif covered:
            split.append(gap.key)
            for index in covered:
                cells[index].make_rigid()
    return split


def _owners(entries: Sequence[_Entry], index: int, at_end: bool) -> list[_Entry]:
    """Membres dont une face borne l'écart au bord de la cellule ``index``."""
    return [e for e in entries if (e.hi == index if at_end else e.lo == index + 1)]


def _settle_border(
    cell: _Cell, entries: Sequence[_Entry], axis: FurnitureAxis, index: int, at_end: bool
) -> None:
    """Écart au bord : distance fixe d'un propriétaire → rigide ; mode ``Stay`` pour tous →
    absorbant ; sinon libre."""
    owners = _owners(entries, index, at_end)
    edge = Edge.of(axis, at_end)
    if any(edge in (owner.member.fixed or frozenset()) for owner in owners):
        cell.make_rigid()
        cell.edge_gap = True
    elif owners and all(owner.member.mode is InteriorMode.STAY for owner in owners):
        cell.kind = _Kind.ABSORBING
    else:
        cell.kind = _Kind.FREE


def _settle_gaps(
    cells: Sequence[_Cell], entries: Sequence[_Entry], axis: FurnitureAxis, inside: range
) -> None:
    """Écarts non couverts. Entre deux cellules couvertes (écart entre pièces) : rigide s'il y
    a une cellule libre de pièce dans la rangée (seules les pièces changent de cote), sinon
    libre. Au bord : distance fixe → rigide, mode ``Stay`` → absorbant, sinon libre."""
    has_piece = any(cells[i].kind is _Kind.FREE for i in inside)
    for index in inside:
        cell = cells[index]
        if cell.kind is not _Kind.GAP:
            continue
        before = any(cells[i].covered for i in range(inside.start, index))
        after = any(cells[i].covered for i in range(index + 1, inside.stop))
        if before and after and has_piece:
            cell.make_rigid()
        elif before and after:
            cell.kind = _Kind.FREE
        elif before or after:
            _settle_border(cell, entries, axis, index, at_end=before)
        else:
            cell.make_rigid()


def _longest_gap(gaps: Sequence[_Cell]) -> _Cell:
    chosen = gaps[0]
    for gap in gaps[1:]:
        if gap.length >= chosen.length - CONTACT_TOLERANCE_MM:  # égalité : le dernier (fin)
            chosen = gap
    return chosen


def _rigid_sum(inside: Sequence[_Cell]) -> Linear:
    total = Linear.of(0.0, 0.0)
    for cell in inside:
        if cell.kind is _Kind.RIGID and cell.value is not None:
            total = total.plus(cell.value)
    return total


def _share(inside: Sequence[_Cell]) -> None:
    """Répartit la différence : les cellules absorbantes la prennent (les libres gardent leur
    longueur), sinon les libres se la partagent au prorata de leur longueur actuelle."""
    absorbing = [cell for cell in inside if cell.kind is _Kind.ABSORBING]
    free = [cell for cell in inside if cell.kind is _Kind.FREE]
    if len(absorbing) > 1:  # les deux bords absorbent : la pièce ne bouge pas
        absorbing[0].make_rigid()
        absorbing = absorbing[1:]
    spare = Linear.of(1.0, 0.0).minus(_rigid_sum(inside))
    if absorbing:
        for cell in free:
            cell.value = Linear.of(0.0, cell.length)
        spare = spare.plus(Linear.of(0.0, -sum(cell.length for cell in free)))
        total = sum(cell.length for cell in absorbing)
        for cell in absorbing:
            cell.value = spare.scaled(cell.length / total)
        return
    total = sum(cell.length for cell in free)
    for cell in free:
        cell.value = spare.scaled(cell.length / total)


def _distribute(inside: Sequence[_Cell]) -> tuple[bool, bool]:
    """Partage la différence entre les cellules de l'ensemble ; renvoie (rangée bloquée, écart
    fixe devenu absorbant)."""
    adaptable = any(cell.kind in (_Kind.FREE, _Kind.ABSORBING) for cell in inside)
    gaps = [cell for cell in inside if cell.edge_gap]
    converted = not adaptable and bool(gaps)
    if converted:
        _longest_gap(gaps).kind = _Kind.ABSORBING
    if not (adaptable or converted):
        return True, False
    _share(inside)
    return False, converted


def _coordinates(cells: Sequence[_Cell], points: Sequence[float], zero: int) -> list[Linear]:
    """Somme des cellules qui précèdent chaque point depuis 0 ; constante avant 0."""
    result = [Linear.of(0.0, point) for point in points[:zero]]
    total = Linear.of(0.0, 0.0)
    result.append(total)
    for cell in cells[zero:]:
        total = total.plus(cell.value if cell.value is not None else Linear.of(0.0, cell.length))
        result.append(total)
    return result


def solve_row(
    key: str,
    axis: FurnitureAxis,
    members: Mapping[str, Member],
    spans: Mapping[str, Spans],
    size: float,
    gaps: Sequence[KeptGap] = (),
) -> SolvedRow:
    """Rangée du membre ``key`` sur ``axis``, résolue pour la cote ``size`` de l'ensemble.

    ``members`` et ``spans`` : les membres d'équerre (clé → membre, étendues), options
    renseignées ; ``gaps`` : les Distances gardées de l'ensemble (ADR 0022)."""
    keys = row_keys(key, axis, spans, gaps)
    active = [g for g in gaps if g.axis is axis and g.a in keys and g.b in keys]
    points = _cut_points([spans[found][axis] for found in keys], size)
    zero, end = _index(points, 0.0), _index(points, size)
    entries = [
        _Entry(
            members[found],
            spans[found][axis],
            _index(points, spans[found][axis].lo),
            _index(points, spans[found][axis].hi),
        )
        for found in keys
    ]
    cells = _first_pass(entries, points, range(zero, end))
    split = _apply_gaps(cells, points, active, spans, range(zero, end))
    _settle_gaps(cells, entries, axis, range(zero, end))
    blocked, converted = _distribute(cells[zero:end])
    locked = tuple(found for found in keys if members[found].locked)
    locked += tuple(gap.key for gap in active)  # une Distance compte comme une pièce verrouillée
    kept = converted and len(entries) == 1 and entries[0].thin
    return SolvedRow(
        Row(axis, tuple(keys), locked, blocked),
        tuple(points),
        tuple(_coordinates(cells, points, zero)),
        kept,
        tuple(split),
    )
