# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglage d'une répétition : copies créées, retirées et liées (ADR 0043).

Les copies sont de vraies pièces de bois, ou des ensembles copie qui reçoivent une copie de chaque
membre de l'ensemble source (:mod:`.repeat_new`), au libellé « {libellé source} {k+1} », rangées
dans le conteneur de la source et, si la source est membre d'un ensemble, dans cet ensemble avec
les mêmes options. Leurs expressions sont écrites par :mod:`.repeat_links` et
:mod:`.repeat_furniture_links`, leurs assemblages par :mod:`.repeat_joints`, le suivi du
redimensionnement de l'ensemble par :mod:`.repeat_follow`. Les autres types de pièces sont
refusés pour l'instant (pièce en bois à forme libre).

Source = pièce usinée (R-b2) : la sélection naturelle est la pièce visible, donc la pièce usinée.
La répétition porte sur sa **pièce brute** (ADR 0006 : les cotes, le matériau et le placement sont
dans la brute ; la forme usinée dépend de ses assemblages et ne se copie pas). La copie est une
brute neuve qui reçoit sa propre pièce usinée par ses assemblages recopiés ; sans assemblage
recopié, elle reste une pièce brute simple.

Rien ici n'ouvre de transaction ni ne recalcule : c'est le rôle de ``_api/repeat.py``.
Les copies ne se créent et ne se suppriment jamais pendant un recalcul.

Les sources sont contrôlées par :mod:`.repeat_sources` (et ses noms réexportés ici).

Grille (ADR 0045) : chaque copie est repérée par sa **cellule** ``(i, j, k)`` (``RepeatCell``),
non par son rang. Modifier la grille garde les copies des cellules conservées (et leurs assemblages
enfants), crée celles des cellules nouvelles, supprime celles des cellules qui sortent ; le rang
linéaire ``RepeatIndex`` n'est qu'un ordre d'affichage, remis à jour. Une cellule qui avait une
copie avant la modification et n'en a plus (supprimée ou dissociée à la main) n'est pas recréée.
Quand la répétition passe d'un seul axe à un autre axe, les copies suivent sur le nouvel axe.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import FreeCAD as App

from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.repeat import (
    Cell,
    RepeatParams,
    ResolvedGrid,
    axis_index,
    cells_of,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import notice_messages, rebind
from freecad.menuiserie.features.furniture_relink import bind_furniture
from freecad.menuiserie.features.repeat import (
    cell_of,
    copies_of,
    is_inner_copy,
    sources_of,
    stored_dims,
    stored_lines,
    write_cell,
    write_params,
)
from freecad.menuiserie.features.repeat_follow import (
    bind_follow_grid,
    follow_furniture,
    follow_grid_params,
    unbind_follow,
)
from freecad.menuiserie.features.repeat_joints import skipped_message, update_joints
from freecad.menuiserie.features.repeat_links import link_copy, link_inner
from freecad.menuiserie.features.repeat_new import (
    Place,
    add_missing_members,
    drop_copy,
    new_copies,
)
from freecad.menuiserie.features.repeat_sources import (
    checked_sources,
    common_container,
    resolve_for,
    source_extent,
    source_extents,
)
from freecad.menuiserie.features.repeat_stop import Stops, write_stops

__all__ = [
    "Created",
    "apply_repeat",
    "checked_sources",
    "common_container",
    "resolve_for",
    "source_extent",
    "source_extents",
]


class Created(NamedTuple):
    """Objets créés par :func:`apply_repeat` : copies (pièces et ensembles), assemblages, et
    avertissements traduits des liaisons des ensembles."""

    copies: list[DocumentObject]
    joints: list[DocumentObject]
    notices: tuple[str, ...] = ()


class _Plan(NamedTuple):
    """Ce que :func:`apply_repeat` doit obtenir : la grille, les cellules qui avaient une copie
    avant la modification (``previous``), le décalage et le rang de chaque cellule."""

    grid: ResolvedGrid
    previous: frozenset[Cell]
    shifts: dict[Cell, Vec3]
    ranks: dict[Cell, int]


def _plan(grid: ResolvedGrid, previous_dims: Cell) -> _Plan:
    cells = grid.cells()
    return _Plan(
        grid,
        frozenset(cells_of(previous_dims)),
        {cell: grid.offset(cell) for cell in cells},
        {cell: rank for rank, cell in enumerate(cells, start=1)},
    )


def _vector(shift: Vec3) -> App.Vector:
    return App.Vector(shift.x, shift.y, shift.z)


def _complete_furniture_copies(
    repeat: DocumentObject,
    source: DocumentObject,
    shifts: dict[Cell, Vec3],
    created: list[DocumentObject],
) -> None:
    """Chaque copie de l'ensemble ``source`` reçoit les membres que la source a gagnés depuis (ils
    sont ajoutés à ``created``, liés comme les autres copies de membres)."""
    if not is_furniture(source):
        return
    known = {copy.RepeatSource.Name for copy in copies_of(repeat)}
    for copy in copies_of(repeat, source):
        added: list[DocumentObject] = []
        add_missing_members(source, copy, known, _vector(shifts[cell_of(copy)]), added)
        for member in added:
            if is_inner_copy(member):
                link_inner(member)
        created.extend(added)


def _sync_copies(
    repeat: DocumentObject, source: DocumentObject, plan: _Plan
) -> list[DocumentObject]:
    """Copies de ``source`` : celles des cellules nouvelles sont créées (une cellule qui avait déjà
    sa copie, même disparue depuis, non), puis les expressions de toutes réécrites. Renvoie les
    objets créés (copie d'un ensemble et copies de ses membres comprises)."""
    created: list[DocumentObject] = []
    _complete_furniture_copies(repeat, source, plan.shifts, created)
    present = {cell_of(copy) for copy in copies_of(repeat, source)}
    for cell, rank in plan.ranks.items():
        if cell in present or cell in plan.previous:
            continue
        made = new_copies(source, repeat, Place(cell, rank, _vector(plan.shifts[cell])))
        for copy in made:
            if is_inner_copy(copy):
                link_inner(copy)
        created.extend(made)
    for copy in copies_of(repeat, source):
        link_copy(copy, source, repeat)
    return created


def _drop_outside(repeat: DocumentObject, source: DocumentObject, plan: _Plan) -> None:
    """Supprime les copies de ``source`` dont la cellule sort de la grille."""
    for copy in copies_of(repeat, source):
        if cell_of(copy) not in plan.ranks:
            drop_copy(copy)


def _renumber(repeat: DocumentObject, ranks: dict[Cell, int]) -> None:
    """Rang linéaire (``RepeatIndex``) de chaque copie, d'après sa cellule : ordre d'affichage.
    Un libellé automatique (« {source} {rang + 1} ») suit le nouveau rang ; un libellé que
    l'utilisateur a changé reste. Les libellés sont libérés d'abord, pour que deux copies ne se
    les disputent pas."""
    changes = []
    for copy in copies_of(repeat):
        rank = ranks.get(cell_of(copy))
        if rank is not None and copy.RepeatIndex != rank:
            label = f"{copy.RepeatSource.Label} {copy.RepeatIndex + 1}"
            changes.append(
                (copy, rank, f"{copy.RepeatSource.Label} {rank + 1}", copy.Label == label)
            )
    for copy, _rank, _label, automatic in changes:
        if automatic:
            copy.Label = copy.Name
    for copy, rank, label, automatic in changes:
        copy.RepeatIndex = rank
        if automatic:
            copy.Label = label


def _previous_dims(repeat: DocumentObject, grid: ResolvedGrid) -> Cell:
    """Nombre d'éléments par axe de la grille actuelle de ``repeat`` (avant modification), après
    avoir écrit la cellule de chaque copie (``RepeatCell`` : absente d'une copie d'avant la grille).
    Si la répétition passe d'un seul axe à un seul autre axe, les copies suivent : leur cellule
    passe sur le nouvel axe et le nombre précédent est reporté sur lui."""
    for copy in copies_of(repeat):
        write_cell(copy, cell_of(copy))
    dims = stored_dims(repeat)
    old, new = stored_lines(repeat), grid.axes
    if len(old) == len(new) == 1 and old[0].axis is not new[0].axis:
        source, target = axis_index(old[0].axis), axis_index(new[0].axis)
        for copy in copies_of(repeat):
            cell = list(cell_of(copy))
            cell[target], cell[source] = cell[source], 0
            write_cell(copy, (cell[0], cell[1], cell[2]))
        moved = [1, 1, 1]
        moved[target] = dims[source]
        dims = (moved[0], moved[1], moved[2])
    return dims


def _top_copies(created: Sequence[DocumentObject]) -> list[DocumentObject]:
    """Ensembles copie (hors copies de membres) à relier : ceux qui ont été créés, et ceux qui
    ont reçu une copie de membre."""
    found: dict[str, DocumentObject] = {}
    for copy in created:
        top = copy
        while is_inner_copy(top) and (parent := furniture_of(top)) is not None:
            top = parent
        if is_furniture(top):
            found[top.Name] = top
    return list(found.values())


def _bind_furnitures(
    sources: Sequence[DocumentObject], created: Sequence[DocumentObject]
) -> list[Notice]:
    """Liaisons des ensembles touchés : chaque ensemble copie créé (membres et sous-ensembles
    compris), puis l'ensemble de chaque source, dont les copies comptent désormais comme membres."""
    notices: list[Notice] = []
    for copy in _top_copies(created):
        notices.extend(rebind(copy))
    parents = {parent.Name: parent for parent in map(furniture_of, sources) if parent is not None}
    for parent in parents.values():
        notices.extend(bind_furniture(parent))
    return notices


def apply_repeat(
    repeat: DocumentObject, params: RepeatParams, stops: Stops | None = None
) -> Created:
    """Met la répétition au réglage ``params`` : écrit ses propriétés, supprime les copies dont la
    cellule sort de la grille, crée celles des cellules nouvelles (une copie dissociée ou supprimée
    à la main ne revient pas), réécrit les expressions de toutes, puis recopie les assemblages
    (``CopyJoints`` vrai : ceux des nouvelles copies, ou de toutes si la case vient d'être cochée ;
    faux : les assemblages enfants sont supprimés) et relie les ensembles touchés. ``FollowResize``
    vrai : le pas de chaque axe devient une expression sur la cote de l'ensemble
    (:mod:`.repeat_follow`). Renvoie les copies, les assemblages créés et les avertissements.
    ``stops`` : butée de chaque axe (ADR 0047) ; ``params`` porte déjà les longueurs qu'elles
    donnent (:func:`.repeat_stop.bounded_params`). Aucune transaction ni recalcul."""
    sources = sources_of(repeat)
    grid = resolve_for(sources, params)
    extents = source_extents(sources, [line.axis for line in grid.axes])
    plan = _plan(grid, _previous_dims(repeat, grid))
    unbind_follow(repeat)
    # Suivi : la longueur suivie comprend la cote des sources seulement si elle est déduite.
    deducted = params.deduct_thickness and not params.end_gap
    followed = extents if deducted else dict.fromkeys(extents, 0.0)
    gap = params.end_gap
    written = (
        follow_grid_params(params, grid, followed, gap=gap) if params.follow_resize else params
    )
    write_params(repeat, written, grid)
    write_stops(repeat, [line.axis for line in grid.axes], stops or {})
    if params.follow_resize:
        bind_follow_grid(repeat, follow_furniture(sources), grid, followed, gap=gap)
    for source in sources:
        _drop_outside(repeat, source, plan)
    _renumber(repeat, plan.ranks)
    created: list[DocumentObject] = []
    for source in sources:
        created.extend(_sync_copies(repeat, source, plan))
    joints = update_joints(repeat, enabled=params.copy_joints, cells=plan.ranks)
    notices = _bind_furnitures(sources, created)
    messages = (*notice_messages(notices), *skipped_message(joints))
    return Created(created, joints.created, messages)
