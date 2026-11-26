# SPDX-License-Identifier: LGPL-2.1-or-later
"""Écriture d'un glissement à la souris : déplacer, redimensionner, annuler, relier (SM-b).

Un glissement va de :func:`begin_drag` à :func:`end_drag` (ou :func:`restore`, Échap). Pendant le
glissement, seules les propriétés de la **brute** sont écrites (``Placement``, ``Length``,
``Width``, ``Thickness``), sans recalcul du document ; ``DragMemento`` garde l'état du début
(Memento) et sert de référence : les écritures sont absolues par rapport à lui, rien ne
s'accumule. Pour un membre d'ensemble, les liaisons **de l'atelier** sur ces propriétés sont
mises de côté au début ; au relâchement tout l'ensemble est relié (ADR 0019, point 6). Une
formule de l'utilisateur n'est jamais retirée : elle rend l'axe non glissable
(:class:`DragLimits`). L'épaisseur du massif se tire librement (Q4, amendée le 2026-10-26), celle
d'un panneau par crans d'épaisseur standard (:func:`stepped_size`, 2026-11-26) ; pour un membre
d'ensemble elle est traitée comme une épaisseur saisie dans le panneau
(:func:`_relink_thickness`). Aucun import de ``FreeCADGui`` ; la transaction et la vue rapport
sont l'affaire de ``gui/``.

Points d'extension :

- pièce en bois (``ShapedPart``, #87) : ses cotes sont celles du dessin (sorties), donc pas de
  poignée (:func:`can_resize`, seul endroit qui décide des poignées d'une pièce) ; elle se
  déplace comme une pièce de bois, par ``Placement`` ; la famille (massif ou panneau) ne décide
  que de l'épaisseur (module ``drag_limits``) ;
- Distance gardée (DI-c, B6) : au relâchement, la ``Value`` des Distances de la pièce prend la
  distance nouvelle (:func:`end_drag`, avant la liaison de l'ensemble) ; Échap la rétablit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.thickness_steps import snap_thickness
from freecad.menuiserie.features.blank_preview import preview_blanks, recompute_blank
from freecad.menuiserie.features.distance import distances_touching
from freecad.menuiserie.features.drag_joints import (
    DragCancelledError,
    JointChoice,
    invalid_joints,
    new_joint_warnings,
    settle_joints,
)
from freecad.menuiserie.features.drag_limits import (
    PLACEMENT_BASE,
    DragLimits,
    can_resize,
    drag_limits,
    panel_steps,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_bindings import (
    notice_messages,
    workshop_expressions,
)
from freecad.menuiserie.features.furniture_edits import thickness_notices
from freecad.menuiserie.features.furniture_envelope import would_reframe
from freecad.menuiserie.features.furniture_reframe import relink_framed
from freecad.menuiserie.features.furniture_relink import relink_thickness
from freecad.menuiserie.features.furniture_variants import follow_distances
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import blank_of
from freecad.menuiserie.features.raw_placement import write_placement
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.features.thickness_common import (
    SIZE_PROPS,
    offers_thickness_choice,
    restore_state,
)
from freecad.menuiserie.features.thickness_drag import FaceFollows
from freecad.menuiserie.features.thickness_member import MemberFreedom

__all__ = [
    "DragCancelledError",
    "DragLimits",
    "DragMemento",
    "begin_drag",
    "can_resize",
    "drag_limits",
    "end_drag",
    "move_part",
    "panel_steps",
    "raw_part",
    "recompute_blank",
    "resize_part",
    "restore",
    "stepped_size",
    "write_placement",
]

_TOUCHED: Final = (*PLACEMENT_BASE, *SIZE_PROPS)
_FIXED_AXIS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » : l'axe {axis} est piloté par une formule, il ne peut pas bouger."
)
_FIXED_SIZE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » : cette cote ne peut pas être tirée à la souris."
)


@dataclass(frozen=True)
class DragMemento:
    """État d'une brute au début d'un glissement : placement, cotes, liaisons mises de côté
    (propriété → expression), liaisons enregistrées (``FurnitureBindings``), assemblages déjà
    invalides (pour n'avertir que des nouveaux) et ``Value`` des Distances gardées de la pièce."""

    part: DocumentObject
    placement: App.Placement
    length: float
    width: float
    thickness: float
    aside: dict[str, str]
    recorded: dict[str, str]
    invalid_joints: frozenset[str]
    distances: dict[str, float] = field(default_factory=dict)
    # Pièces qui suivent l'épaisseur tirée (ADR 0060), choisies au premier pas : clé = face basse
    follows: FaceFollows = field(default_factory=FaceFollows)
    # Membre assemblé : liaisons de son ensemble mises de côté à la première épaisseur tirée
    # (une au plus ; liste car le mémento est figé)
    freedom: list[MemberFreedom] = field(default_factory=list)
    # Panneau : crans de l'épaisseur tirée (épaisseurs standard, lues une fois au début)
    steps: tuple[float, ...] = ()


def raw_part(obj: DocumentObject) -> DocumentObject:
    """Brute que glisser ``obj`` déplace : la brute elle-même, la ``Base`` d'une pièce usinée,
    la pièce invitée d'un assemblage (ADR 0006). ``TypeError`` traduite pour tout autre objet."""
    if is_joint(obj) and is_timber(obj.GuestPart):
        return obj.GuestPart
    return blank_of(obj)


def begin_drag(part: DocumentObject) -> DragMemento:
    """Début d'un glissement : mémorise la brute de ``part`` et, pour un membre d'ensemble,
    met de côté les liaisons de l'atelier sur ``Placement.Base.x/y/z``, ``Length``, ``Width`` et
    ``Thickness`` (B3). Une formule de l'utilisateur n'est jamais retirée (B4)."""
    raw = raw_part(part)
    recorded = dict(raw.FurnitureBindings) if "FurnitureBindings" in raw.PropertiesList else {}
    aside = {} if furniture_of(raw) is None else dict(workshop_expressions(raw))
    aside = {prop: text for prop, text in aside.items() if prop in _TOUCHED}
    with writing(raw):
        for prop in aside:
            raw.setExpression(prop, None)
    return DragMemento(
        raw,
        App.Placement(raw.Placement),
        raw.Length.Value,
        raw.Width.Value,
        raw.Thickness.Value,
        aside,
        recorded,
        invalid_joints(raw),
        {d.Name: d.Value.Value for d in distances_touching(raw.Document, {raw.Name})},
        steps=panel_steps(raw),
    )


def _shifted(memento: DragMemento, shift: Vec3) -> App.Placement:
    """Placement du début décalé de ``shift`` (mm, repère de la pièce)."""
    start = memento.placement
    offset = start.Rotation.multVec(App.Vector(shift.x, shift.y, shift.z))
    return App.Placement(start.Base + offset, start.Rotation)


def _check_axes(memento: DragMemento, shift: Vec3) -> None:
    fixed = drag_limits(memento.part).fixed_axes
    for axis in fixed:
        if abs(shift.component(axis)) > ANGLE_TOLERANCE:
            params = {"label": str(memento.part.Label), "axis": "XYZ"[axis]}
            raise ValueError(translated(_FIXED_AXIS, params))


def move_part(memento: DragMemento, delta: Vec3) -> None:
    """Place la brute à ``delta`` mm (repère de la pièce) de sa position du début (B2) ; sans
    recalcul du document. ``ValueError`` traduite si ``delta`` bouge un axe fixé par une formule
    de l'utilisateur."""
    _check_axes(memento, delta)
    write_placement(memento.part, _shifted(memento, delta))


def _write_size(memento: DragMemento, prop: str, value: float, shift: Vec3) -> None:
    with writing(memento.part):
        setattr(memento.part, prop, value)
    write_placement(memento.part, _shifted(memento, shift))


def _assembled_member(memento: DragMemento) -> DocumentObject | None:
    """Ensemble d'un membre assemblé tiré (ses liaisons mises de côté une fois, comme dans le
    panneau, ADR 0060 point 5) ; ``None`` hors ensemble ou pour un membre à cotes fixes."""
    furniture = furniture_of(memento.part)
    if furniture is None or not offers_thickness_choice(memento.part):
        return None
    if not memento.freedom:
        memento.freedom.append(MemberFreedom(memento.part))
    return furniture


def _resize_thickness(memento: DragMemento, value: float, shift: Vec3, lowered: bool) -> str:
    """Épaisseur tirée : les pièces à fleur suivent ; butée (raison renvoyée) : état du début.
    Membre assemblé dont la boîte ne changerait pas (face intérieure) : rien ne suit, la rangée
    absorbe au relâchement (ADR 0019) ; sinon la face tirée décide (ADR 0060 point 6)."""
    member = _assembled_member(memento)
    memento.follows.prepare(memento.part, lowered)  # sur la pièce encore à son épaisseur
    _write_size(memento, "Thickness", value, shift)
    if member is not None and not would_reframe(member):
        memento.follows.restore(recompute_blank)
        return ""
    delta, follows = value - memento.thickness, memento.follows
    if stop := follows.follow_dragged_face(memento.part, delta, lowered, recompute_blank):
        _write_size(memento, "Thickness", memento.thickness, Vec3(0, 0, 0))
    return stop


def stepped_size(memento: DragMemento, prop: str, value: float) -> float:
    """Cote (mm) que :func:`resize_part` écrit pour ``value`` : l'épaisseur d'un panneau saute à
    l'épaisseur standard la plus proche, entre la plus petite et la plus grande (jv,
    2026-11-26) ; toute autre cote est écrite telle quelle."""
    if prop != "Thickness" or not memento.steps:
        return value
    return snap_thickness(value, memento.steps)


def _on_step(memento: DragMemento, value: float, shift: Vec3, lowered: bool) -> tuple[float, Vec3]:
    """Épaisseur ``value`` mise au cran et décalage de l'origine qui garde l'autre face en place
    (poignée de début : l'origine recule de ce que l'épaisseur gagne)."""
    snapped = stepped_size(memento, "Thickness", value)
    if snapped == value:
        return value, shift
    z = memento.thickness - snapped if lowered else 0.0
    return snapped, Vec3(shift.x, shift.y, z)


def resize_part(
    memento: DragMemento, prop: str, value: float, origin_shift: Vec3, *, lowered: bool = False
) -> str:
    """Fixe ``Length``, ``Width`` ou ``Thickness`` (``prop``) de la brute à ``value`` mm et décale
    son origine de ``origin_shift`` (repère de la pièce, d'après le début ; poignée de début) (B2).
    Seule la brute et sa pièce usinée sont recalculées, pas le document. ``ValueError`` traduite
    si la cote ne peut pas être tirée (:func:`drag_limits`). Épaisseur (``lowered`` : poignée de
    début) : les pièces à fleur suivent ; sinon butée, raison traduite renvoyée (ADR 0060)."""
    allowed = drag_limits(memento.part).resizable_axes
    if prop not in SIZE_PROPS or SIZE_PROPS.index(prop) not in allowed:
        raise ValueError(translated(_FIXED_SIZE, {"label": str(memento.part.Label)}))
    if prop == "Thickness":
        value, origin_shift = _on_step(memento, value, origin_shift, lowered)
        stop = _resize_thickness(memento, value, origin_shift, lowered)
    else:
        stop = ""
        _write_size(memento, prop, value, origin_shift)
    preview_blanks((memento.part, *memento.follows.parts()))  # pièces suivies : ADR 0060
    return stop


def restore(memento: DragMemento) -> None:
    """Échap : ramène la brute à son état du début (placement, cotes, liaisons mises de côté).
    Le document n'est pas recalculé ; la pièce usinée reprend le placement."""
    try:  # liaisons de l'ensemble d'abord, celles de la brute ensuite, même si elles échouent
        for freedom in memento.freedom:
            freedom.cancel()
    finally:
        _restore_raw(memento)


def _restore_raw(memento: DragMemento) -> None:
    raw = memento.part
    restore_state(raw, (memento.length, memento.width, memento.thickness), memento.placement)
    with writing(raw):
        for prop, text in memento.aside.items():
            raw.setExpression(prop, text)
        if "FurnitureBindings" in raw.PropertiesList:
            raw.FurnitureBindings = memento.recorded
    for name, value in memento.distances.items():
        distance = raw.Document.getObject(name)
        if distance is not None and distance.Value.Value != value:
            distance.Value = value
    try:  # pièces suivies d'abord : l'aperçu de la brute retrouve leurs assemblages (ADR 0060)
        memento.follows.restore(recompute_blank)
    finally:
        recompute_blank(raw)


def _relink_thickness(memento: DragMemento, furniture: DocumentObject) -> list[str]:
    """Épaisseur tirée d'un membre d'ensemble : traitée comme une épaisseur saisie dans le panneau
    (ADR 0019, points 5 et 6). L'épaisseur est contrôlée (rangée bloquée : ``ValueError``
    traduite) sur la géométrie d'avant, cohérente ; puis tout l'ensemble est relié : l'épaisseur
    est gardée, la rangée des autres membres se recalcule."""
    raw = memento.part
    new = raw.Thickness.Value
    with translated_errors():
        notices = thickness_notices(furniture, raw, new, previous=memento.thickness)
    relinked = relink_thickness(furniture, raw, new, memento.thickness)
    return list(notice_messages([*relinked, *notices]))


def _relink(memento: DragMemento) -> list[str]:
    """Relie tout l'ensemble de la brute d'après sa position nouvelle ; en cas d'erreur, la brute
    revient (:func:`restore`) et l'erreur est relancée. Épaisseur tirée par la face intérieure :
    la brute reprend son placement du début et la rangée absorbe (:func:`_relink_thickness`,
    ADR 0019). Membre assemblé dont la boîte change (face extérieure) : la face tirée décide,
    l'ensemble est relié d'après le résultat, boîtes recalées (ADR 0060 point 6, ADR 0065)."""
    furniture = furniture_of(memento.part)
    if furniture is None:
        return []
    thicker = memento.part.Thickness.Value != memento.thickness
    freedom = memento.freedom[0] if memento.freedom else None
    try:
        if freedom is not None and thicker and would_reframe(furniture):
            follow_distances(furniture, memento.distances.keys())
            return freedom.finish()
        if freedom is not None:  # rien à recaler : liaisons rendues, chemin habituel
            freedom.cancel()
            memento.follows.restore(recompute_blank)
        if thicker:
            write_placement(memento.part, memento.placement)
        follow_distances(furniture, memento.distances.keys())
        if thicker:
            return _relink_thickness(memento, furniture)
        return list(notice_messages(relink_framed(furniture)))  # boîtes recalées (ADR 0065)
    except Exception:  # toute erreur : brute, voisines et liaisons rendues, puis relancée
        restore(memento)
        raise


def _settle(memento: DragMemento, choose: JointChoice | None) -> list[str]:
    """Assemblages défaits par le déplacement, essayés avant tout recalcul (ADR 0026) ; si le
    déplacement est annulé, la brute revient (:func:`restore`) et ``DragCancelledError`` passe.
    Une épaisseur tirée n'est pas un déplacement : les assemblages sont seulement recalculés (un
    qui devient impossible est signalé par :func:`.new_joint_warnings`), jamais proposés à la
    suppression."""
    if memento.part.Thickness.Value != memento.thickness:
        return []
    try:
        return settle_joints(memento.part, memento.invalid_joints, choose)
    except DragCancelledError:
        restore(memento)
        raise


def end_drag(memento: DragMemento, choose: JointChoice | None = None) -> list[str]:
    """Relâchement : relie tout l'ensemble de la brute (membre d'ensemble, B3), recalcule le
    document une fois et renvoie les avertissements à mettre dans la vue rapport (liaisons,
    assemblage qui ne touche plus : B7).

    ``choose`` (ADR 0026) : si le déplacement défait des assemblages, il décide avant tout
    recalcul de les supprimer (déplacement gardé) ou d'annuler (``DragCancelledError``, la brute est
    revenue). Sans ``choose`` (script, API), le déplacement est gardé et l'on prévient seulement.
    Rangée bloquée : la brute revient à son état du début et
    :class:`~freecad.menuiserie.features.furniture_bindings.LockedPiecesError` (ou ``ValueError``)
    est levée, pour proposer « Déverrouiller et appliquer » (ADR 0019)."""
    removed = _settle(memento, choose)
    messages = _relink(memento)
    removed += _settle(memento, choose)  # la liaison peut avoir changé la géométrie
    memento.part.Document.recompute()
    followed = memento.follows.messages()
    return [
        *removed,
        *messages,
        *followed,
        *new_joint_warnings(memento.part, memento.invalid_joints),
    ]
