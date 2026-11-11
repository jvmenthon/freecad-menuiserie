# SPDX-License-Identifier: LGPL-2.1-or-later
"""Écriture de la taille, du déplacement et de l'orientation d'un ensemble à la souris (EN-b,
ADR 0038, critères B1 à B5).

Un geste va de :func:`begin_furniture_drag` à :func:`end_furniture_drag` (ou :func:`restore`,
Échap). :class:`FurnitureMemento` garde l'état du début (Memento, comme ``part_drag.DragMemento``) ;
toutes les écritures sont **absolues** par rapport à lui, rien ne s'accumule.

- **Taille** (:func:`resize_furniture_to`) : ``Width``, ``Depth``, ``Height`` par le contrôle et
  l'écriture du panneau (``furniture_resize``) ; tirer la face avant, gauche ou basse décale le
  ``Placement`` du Std Part (et non ``Origin``) pour que la face opposée reste en place : les
  liaisons des pièces ne portent que sur ce qui change avec les cotes, une pièce sans liaison sur
  l'axe suit le Std Part. Pendant le geste seules les pièces
  **brutes** sont recalculées (pas les usinages) ; la cadence (10 Hz au plus) est l'affaire de
  l'appelant. Une cote refusée (:class:`LockedPiecesError`, pièce trop petite, formule) arrête le
  geste à la dernière valeur permise : le résultat (:class:`StepResult`) porte le message, rien
  n'est perdu en silence.
- **Déplacement et rotation** (:func:`move_furniture_by`, :func:`rotate_furniture_by`,
  :func:`rotate_furniture_to`) : écrivent le ``Placement`` du Std Part propre de l'ensemble
  (:func:`~furniture_container.own_std_part`), la rotation autour du centre de la boîte
  (``core/rotation``). Sans Std Part propre (ancien document, Std Part qui contient autre chose),
  ils renvoient faux sans rien écrire (:func:`turn_refusal` dit pourquoi).
- **Sous-ensemble** : taille, déplacement et rotation sont permis, par son propre Std Part. Ses
  liaisons de l'atelier (cotes et ``Placement.Base`` du Std Part) sont mises de côté au début et
  tout l'ensemble parent est relié au relâchement (ADR 0019, point 6). Une formule de
  l'utilisateur n'est jamais retirée : elle refuse le geste.

Aucun import de ``FreeCADGui`` ; la transaction et la vue rapport sont l'affaire de ``gui/``.
"""

from __future__ import annotations

import math
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.rotation import Angles, turned_about_point, turned_to
from freecad.menuiserie.core.vectors import is_finite
from freecad.menuiserie.features.freecad_types import DocumentObject, placement_expression
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_bindings import (
    bind_members,
    notice_messages,
    read_members,
)
from freecad.menuiserie.features.furniture_checks import quoted_label
from freecad.menuiserie.features.furniture_container import own_std_part
from freecad.menuiserie.features.furniture_drag_state import (
    DRIVEN_PLACEMENT,
    NO_OWN_STD_PART,
    FurnitureMemento,
    StepResult,
    begin_furniture_drag,
    changed_sizes,
    furniture_box,
    furniture_frame,
    furniture_placement,
    recompute_blanks,
    restore,
    turn_refusal,
    vector,
    write_sizes,
    write_std_placement,
)
from freecad.menuiserie.features.furniture_envelope import frame_of, reframe, restore_frame
from freecad.menuiserie.features.furniture_locks import refusal_of
from freecad.menuiserie.features.furniture_resize import planned_resize, resize, write_box
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.part_rotate import checked_rotation
from freecad.menuiserie.features.placement import to_placement
from freecad.menuiserie.features.solids import rigid_transform

__all__ = [
    "FurnitureMemento",
    "StepResult",
    "begin_furniture_drag",
    "end_furniture_drag",
    "furniture_box",
    "furniture_frame",
    "furniture_placement",
    "move_furniture_by",
    "recompute_blanks",
    "resize_furniture_to",
    "restore",
    "rotate_furniture_by",
    "rotate_furniture_to",
    "turn_refusal",
]

_BISECTIONS: Final = 8  # pas de dichotomie vers la dernière valeur permise (1/256 du geste)

# --- Taille -----------------------------------------------------------------------------------


def _shift_of(memento: FurnitureMemento, box: Box) -> Vec3:
    return box.min - memento.box.min


def _check_position(memento: FurnitureMemento, box: Box) -> None:
    """``ValueError`` traduite si la face tirée décalerait un Std Part qui n'est pas propre à
    l'ensemble ou dont une formule de l'utilisateur pilote le ``Placement``."""
    shift = _shift_of(memento, box)
    if not any(abs(shift.component(i)) > 0.0 for i in range(3)):
        return
    part = memento.std_part
    if not memento.owned or part is None:
        raise ValueError(translated(NO_OWN_STD_PART, quoted_label(memento.furniture)))
    if placement_expression(part) is not None:
        raise ValueError(translated(DRIVEN_PLACEMENT, quoted_label(memento.furniture)))


def _check(memento: FurnitureMemento, box: Box) -> ValueError | None:
    """Refus (sans rien écrire) du passage du document à ``box``, ``None`` s'il est permis."""
    try:
        _check_position(memento, box)
        planned_resize(memento.furniture, changed_sizes(memento.furniture, box))
    except ValueError as error:  # LockedPiecesError comprise
        return error
    return None


def _write_position(memento: FurnitureMemento, box: Box) -> None:
    """Décalage de ``box`` écrit dans le ``Placement`` du Std Part (le décalage est tourné par son
    placement du début) : écriture absolue d'après le début. ``Origin`` ne bouge jamais."""
    part = memento.std_part
    if part is None:
        return
    start = memento.placement
    moved = start.Rotation.multVec(vector(_shift_of(memento, box)))
    write_std_placement(part, App.Placement(start.Base + moved, start.Rotation))


def _write(memento: FurnitureMemento, box: Box) -> list[Notice]:
    """Contrôle, puis écrit ``box`` (cotes et position) et recalcule les brutes. Renvoie les
    avertissements du contrôle ; ``ValueError`` (rien n'est écrit) si le passage est refusé."""
    sizes = changed_sizes(memento.furniture, box)
    _check_position(memento, box)
    new, notices = planned_resize(memento.furniture, sizes)
    write_box(memento.furniture, new, sizes)
    _write_position(memento, box)
    recompute_blanks(memento.furniture)
    memento.applied = box
    return notices


def _between(start: Box, end: Box, ratio: float) -> Box:
    ranges = [
        (a0 + (b0 - a0) * ratio, a1 + (b1 - a1) * ratio)
        for (a0, a1), (b0, b1) in zip(start.ranges(), end.ranges(), strict=True)
    ]
    return Box.from_ranges(ranges)


def _largest_allowed(memento: FurnitureMemento, target: Box) -> Box:
    """Boîte permise la plus proche de ``target`` sur le segment qui y mène depuis la boîte
    écrite (dichotomie : chaque pas coûte un contrôle, jamais une écriture)."""
    low, high = 0.0, 1.0
    for _ in range(_BISECTIONS):
        middle = (low + high) / 2
        if _check(memento, _between(memento.applied, target, middle)) is None:
            low = middle
        else:
            high = middle
    return _between(memento.applied, target, low)


def resize_furniture_to(memento: FurnitureMemento, box: Box) -> StepResult:
    """Donne à l'ensemble la boîte ``box`` (repère du Std Part, valeurs **absolues** : ``Width``,
    ``Depth``, ``Height`` et le Std Part pour les faces avant, gauche et basse) (B1) ; les pièces
    suivent par leurs liaisons, seules les brutes sont recalculées (B2). Pas de transaction ni de
    recalcul du document.

    Si le passage est refusé (rangée bloquée, pièce trop petite, formule), rien d'invalide n'est
    écrit : la boîte va à la dernière valeur permise sur le chemin de la souris et le résultat
    porte le message (B3). ``ValueError`` si ``box`` n'a pas de volume."""
    if not all(box.size(i) > 0.0 for i in range(3)):
        raise ValueError("resize_furniture_to.box : boîte avec un volume attendue")
    try:
        _write(memento, box)
    except ValueError as error:  # LockedPiecesError comprise
        message, locked = refusal_of(error)
        best = _largest_allowed(memento, box)
        if best != memento.applied:
            _write(memento, best)
        return StepResult(memento.applied, False, message, locked)
    return StepResult(box)


# --- Déplacement et rotation ------------------------------------------------------------------


def _free_to_turn(memento: FurnitureMemento) -> bool:
    """Vrai si le Std Part du geste est propre à l'ensemble et qu'aucune formule de l'utilisateur
    ne pilote son ``Placement`` (les liaisons de l'atelier sont déjà mises de côté)."""
    part = memento.std_part
    return memento.owned and part is not None and placement_expression(part) is None


def _centre(box: Box) -> Vec3:
    return Vec3(box.center(0), box.center(1), box.center(2))


def move_furniture_by(memento: FurnitureMemento, delta: Vec3) -> bool:
    """Déplace l'ensemble de ``delta`` mm (repère du Std Part au début du geste) depuis sa position
    du début : écrit le ``Placement`` de son Std Part (écriture absolue, Q5). Faux, sans rien
    écrire, si l'ensemble n'a pas de Std Part propre ou si une formule pilote son ``Placement``.
    ``ValueError`` si ``delta`` n'est pas fini."""
    if not is_finite(delta):
        raise ValueError("move_furniture_by.delta : coordonnées finies attendues")
    part = memento.std_part
    if part is None or not _free_to_turn(memento):
        return False
    start = memento.placement
    moved = start.Rotation.multVec(vector(delta))
    write_std_placement(part, App.Placement(start.Base + moved, start.Rotation))
    return True


def rotate_furniture_by(memento: FurnitureMemento, axis: int, angle: float) -> bool:
    """Tourne l'ensemble de ``angle`` degrés autour de l'axe fixe ``axis`` (0 = X, 1 = Y, 2 = Z) du
    conteneur de son Std Part, passant par le centre de sa boîte, **depuis son orientation du
    début** (deux appels ne s'ajoutent pas) (B4, B5). Faux, sans rien écrire, sans Std Part propre
    ou si une formule pilote son ``Placement``. ``ValueError`` si ``axis`` ou ``angle`` est
    invalide."""
    if not math.isfinite(angle):
        raise ValueError("rotate_furniture_by.angle : angle fini attendu")
    part = memento.std_part
    if part is None or not _free_to_turn(memento):
        return False
    start = rigid_transform(memento.placement)
    turned = turned_about_point(start, _centre(memento.box), axis, angle)
    write_std_placement(part, to_placement(turned))
    return True


def rotate_furniture_to(furniture: DocumentObject, angles: Angles) -> bool:
    """Donne au Std Part de ``furniture`` les angles absolus ``angles`` (X, Y, Z de son
    ``Placement``, degrés), le centre de la boîte restant fixe. Faux, sans rien écrire, sans Std
    Part propre ou si une expression (formule, liaison du parent) pilote son ``Placement``.
    ``ValueError`` si un angle n'est pas fini ou sort de [-360, 360]."""
    rotation = checked_rotation(angles)
    part = own_std_part(furniture)
    if part is None or placement_expression(part) is not None:
        return False
    start = rigid_transform(part.Placement)
    turned = turned_to(start, _centre(furniture_box(furniture)), rotation)
    write_std_placement(part, to_placement(turned))
    return True


# --- Relâchement ------------------------------------------------------------------------------


def _resized(memento: FurnitureMemento) -> bool:
    return any(abs(memento.applied.size(i) - memento.box.size(i)) > 0.0 for i in range(3))


def _full_notices(memento: FurnitureMemento) -> list[Notice]:
    """Avertissements du changement de cotes du début à la boîte écrite : le document revient à
    la boîte du début, puis passe par le chemin du panneau (``furniture_resize.resize``). Rien
    n'est écrit si le passage est refusé (la boîte écrite reste)."""
    final = memento.applied
    furniture = memento.furniture
    with writing(furniture):
        write_sizes(furniture, memento.box)
    _write_position(memento, memento.box)
    recompute_blanks(furniture)
    sizes = changed_sizes(furniture, final)
    notices = resize(furniture, sizes)
    _write_position(memento, final)
    recompute_blanks(furniture)
    return notices


def _relink(memento: FurnitureMemento) -> list[Notice]:
    """Relie l'ensemble parent d'un sous-ensemble d'après sa géométrie nouvelle, après avoir recalé
    ses cotes sur l'enveloppe de ses membres (ADR 0049) ; en cas d'erreur, le parent et l'ensemble
    reviennent (:func:`restore`) et l'erreur est relancée."""
    parent = furniture_of(memento.furniture)
    if parent is None:
        return []
    frame = frame_of(parent)
    try:
        reframe(parent)
        members = read_members(parent)
        return bind_members(members, members.objects)
    except ValueError:
        restore_frame(parent, frame)
        restore(memento)
        raise


def end_furniture_drag(memento: FurnitureMemento) -> list[str]:
    """Relâchement : un contrôle complet des cotes (avertissements de l'ADR 0017), pour un
    sous-ensemble la liaison de tout l'ensemble parent (ADR 0019, point 6), un recalcul complet du
    document ; renvoie les avertissements traduits pour la vue rapport. Rangée bloquée ou liaison
    impossible : l'ensemble revient à son état du début (:func:`restore`) et l'erreur
    (:class:`~freecad.menuiserie.features.furniture_bindings.LockedPiecesError` ou ``ValueError``)
    est relancée, pour proposer « Déverrouiller et appliquer »."""
    try:
        notices = _full_notices(memento) if _resized(memento) else []
    except ValueError:
        restore(memento)
        raise
    notices += _relink(memento)
    memento.furniture.Document.recompute()
    return list(notice_messages(notices))
