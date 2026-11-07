# SPDX-License-Identifier: LGPL-2.1-or-later
"""Données et aides de la session de glissement (SM-c, ADR 0021 ; anneaux : ADR 0025).

:class:`PanelContext` (panneau ouvert), :class:`Grab` et :class:`Turn` (ce qu'il faut pour tirer une
flèche, une poignée ou un anneau) et les aides qui lisent la pièce (repère, boîte, anneaux).
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import FreeCAD as App

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.magnet import Guide, Ray
from freecad.menuiserie.core.rotation import Ring
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.features.freecad_types import DocumentObject, placement_expression
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.snap_geometry import to_vec3
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.gui.drag.rings import build_rings
from freecad.menuiserie.gui.drag.view import Point

if TYPE_CHECKING:
    from freecad.menuiserie.gui.drag.target import Memento, Target

__all__ = [
    "Grab",
    "PanelContext",
    "Turn",
    "box_of",
    "frame_of",
    "give_up",
    "open_transaction",
    "rings_of",
]


@dataclass(frozen=True)
class PanelContext:
    """Panneau de tâche de la pièce ``part`` : ``refresh`` relit ses champs, ``is_open`` dit s'il
    est encore ouvert. Aucun widget n'est gardé ici."""

    part: DocumentObject
    refresh: Callable[[], None]
    is_open: Callable[[], bool]


def frame_of(placement: App.Placement) -> Frame:
    rotation = placement.Rotation
    axes = [to_vec3(rotation.multVec(App.Vector(*v))) for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    return Frame(to_vec3(placement.Base), *axes)


def rings_of(part: DocumentObject, box: Box) -> tuple[Ring, ...]:
    """Anneaux de rotation de la brute ``part`` ; aucun si une expression pilote son ``Placement``
    (membre d'ensemble, formule : D6). Ils suivent les axes de son conteneur (B5)."""
    if placement_expression(part) is not None:
        return ()
    container = part.getGlobalPlacement() * part.Placement.inverse()
    return build_rings(box, rigid_transform(part.Placement), rigid_transform(container))


def box_of(part: DocumentObject) -> Box:
    return Box(
        Vec3(0.0, 0.0, 0.0),
        Vec3(part.Length.Value, part.Width.Value, part.Thickness.Value),
    )


@dataclass(frozen=True)
class Grab:
    """Ce qu'il faut pour tirer une cible : clé de la flèche ou de la poignée, pixel de départ,
    paramètre de l'axe sous le curseur, début de l'écriture (Memento), guides, tolérance de
    l'aimant (mm), transaction ouverte par le glissement (``own``) et cible (pièce ou ensemble)."""

    key: str
    start: Point
    line: Ray
    origin: float
    memento: Memento
    guides: tuple[Guide, ...]
    tolerance: float
    own: bool
    target: Target


@dataclass(frozen=True)
class Turn:
    """Ce qu'il faut pour tourner une pièce par un anneau : l'anneau (axe, centre, rayon), le rayon
    de la souris au départ (reculé devant le plan de l'anneau), le vecteur du centre au point
    saisi, pixel de départ, début de l'écriture (Memento), transaction ouverte (``own``) et cible
    (pièce ou ensemble)."""

    ring: Ring
    first: Ray
    from_center: Vec3
    start: Point
    memento: Memento
    own: bool
    target: Target


def open_transaction(part: DocumentObject, name: str) -> bool:
    """Ouvre la transaction ``name`` si aucune n'est en cours (celle du panneau, sinon) ; vrai si
    c'est le geste qui l'a ouverte."""
    own = App.getActiveTransaction() is None
    if own:
        part.Document.openTransaction(translated(name))
    return own


def give_up(part: DocumentObject, own: bool) -> None:
    """Début de geste raté : transaction du geste abandonnée, erreur dans la vue rapport."""
    if own:
        part.Document.abortTransaction()
    App.Console.PrintError(traceback.format_exc())
