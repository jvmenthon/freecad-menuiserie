# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages recopiés par une répétition (ADR 0043, lot R-b2, spécification § 3, Q4).

Quand ``CopyJoints`` est vrai, chaque assemblage « d'origine » dont une pièce est une source de la
répétition est recréé pour chaque copie :

- A : les deux pièces sont des sources (ou des membres d'un ensemble source) → assemblage entre
  les copies homologues, celles de la **même cellule** ``(i, j, k)`` de la grille ;
- B : une seule pièce est une source → assemblage entre la copie et l'autre pièce, rôles
  conservés (la traverse reçoit un tenon par copie) ;
- C : aucune pièce n'est une source → rien (l'assemblage n'est pas une origine) ;
- D : un assemblage **impossible** (copie hors de l'hôte, pièces qui ne se touchent pas…) n'est
  pas recopié (décision de jv). Sa faisabilité est vérifiée avant la création avec les calculs du
  recalcul (:func:`.joints.feasible.plan_error`), aux placements et cotes de la copie ; chaque
  édition de la répétition réévalue tout : un enfant devenu impossible est supprimé, un
  manquant devenu possible est créé, un enfant dissocié ne revient pas. Le nombre d'assemblages
  non recopiés est signalé (:func:`skipped_message`). Limite : un simple recalcul (source déplacée
  après coup) ne crée ni ne supprime rien (pas d'écriture de structure dans un recalcul) ; un
  enfant devenu impossible l'est alors signalé par l'état de l'assemblage jusqu'à la prochaine
  édition de la répétition.

Un assemblage enfant porte ``RepeatJoint`` (lien vers l'assemblage d'origine, lecture seule) et
**partage sa configuration** : chaque propriété de paramètre du type (``PARAMS``, noms de
:func:`.joints.base.property_name`) est une expression ``{origine}.{propriété}``, en lecture seule
dans l'éditeur. Changer l'origine change donc les enfants. Retrait (:func:`unlink_joint`) :
expressions retirées, valeurs gardées, propriété ``RepeatJoint`` retirée, modes d'édition rendus.

Les enfants se créent et se suppriment hors recalcul, dans la transaction de l'API. Contrat de
persistance (ADR 0003) : le nom de la propriété ``RepeatJoint`` ne change jamais.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import fields
from typing import Final, NamedTuple

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import Cell
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.drag_joints import remove_joints
from freecad.menuiserie.features.freecad_types import (
    READ_ONLY,
    DocumentObject,
    expressions_of,
    restoring_or_undoing,
)
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint, property_name
from freecad.menuiserie.features.joints.factories import create_joint
from freecad.menuiserie.features.joints.feasible import plan_error
from freecad.menuiserie.features.repeat import cell_of, copies_of
from freecad.menuiserie.features.repeat_members import original_parts
from freecad.menuiserie.features.schema import PropertySpec, set_editor_mode

__all__ = [
    "PROPERTY",
    "JointsUpdate",
    "children_of",
    "hand_joints_warning",
    "joint_removed",
    "joints_of_part",
    "not_copied_warning",
    "origin_of",
    "param_paths",
    "restored",
    "skipped_message",
    "unlink_joint",
    "unlink_part_joints",
    "update_joints",
]

PROPERTY: Final = "RepeatJoint"
_SPEC: Final = PropertySpec(
    PROPERTY,
    "App::PropertyLinkGlobal",
    "Répétition",
    QT_TRANSLATE_NOOP(
        "App::Property",
        "Assemblage d'origine dont celui-ci partage la configuration (répétition).",
    ),
    mode=READ_ONLY,
)
_SKIPPED_ONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "1 assemblage n'a pas été recopié : {reason}")
_SKIPPED_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{count} assemblages n'ont pas été recopiés : {reason}"
)
_HAND_ONE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "1 assemblage posé à la main sur une copie ne tient plus, la copie ayant bougé : {labels}. "
    "Assemblez plutôt la pièce d'origine : « Recopier les assemblages » le recrée sur chaque "
    "copie.",
)
_HAND_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{count} assemblages posés à la main sur une copie ne tiennent plus, la copie ayant bougé : "
    "{labels}. Assemblez plutôt la pièce d'origine : « Recopier les assemblages » les recrée sur "
    "chaque copie.",
)
_DERIVED: Final = "joint_derived"  # champ fourni par le document, pas par une propriété


def origin_of(joint: DocumentObject) -> DocumentObject | None:
    """Assemblage d'origine de ``joint`` s'il est un enfant d'une répétition, ``None`` sinon."""
    origin: DocumentObject | None = getattr(joint, PROPERTY, None)
    return origin


def param_paths(joint: DocumentObject) -> list[str]:
    """Propriétés de paramètres du type de ``joint`` (``PARAMS``), celles que l'enfant partage."""
    names = (
        property_name(item.name)
        for item in fields(joint.Proxy.PARAMS)
        if not item.metadata.get(_DERIVED)
    )
    return [name for name in names if name in joint.PropertiesList]


def _unique(objects: Iterable[DocumentObject]) -> list[DocumentObject]:
    """Les objets sans doublon (un objet figure autant de fois dans ``InList`` qu'il cite), triés
    par nom : ordre stable d'un recalcul à l'autre."""
    return sorted({obj.Name: obj for obj in objects}.values(), key=lambda obj: obj.Name)


def joints_of_part(part: DocumentObject) -> list[DocumentObject]:
    """Assemblages dont ``part`` (pièce brute) est l'hôte ou l'invitée."""
    return _unique(
        joint
        for joint in part.InList
        if is_joint(joint) and part in (joint.HostPart, joint.GuestPart)
    )


def children_of(origin: DocumentObject) -> list[DocumentObject]:
    """Assemblages enfants de l'assemblage d'origine ``origin``."""
    return _unique(
        joint for joint in origin.InList if is_joint(joint) and origin_of(joint) == origin
    )


def _bind(child: DocumentObject, origin: DocumentObject) -> None:
    """Lie ``child`` à ``origin`` : lien, expressions de tous les paramètres, lecture seule."""
    schema.add_missing_properties(child, (_SPEC,))
    setattr(child, PROPERTY, origin)
    schema.apply_editor_modes(child, (_SPEC,))
    for path in param_paths(child):
        child.setExpression(path, f"{origin.Name}.{path}")
        set_editor_mode(child, path, READ_ONLY)


def restored(joint: DocumentObject) -> None:
    """Assemblage rouvert : les paramètres d'un enfant redeviennent en lecture seule (les modes
    du schéma du type les ont rendus modifiables)."""
    if origin_of(joint) is None:
        return
    schema.apply_editor_modes(joint, (_SPEC,))
    for path in param_paths(joint):
        set_editor_mode(joint, path, READ_ONLY)


def unlink_joint(joint: DocumentObject) -> None:
    """Dissocie l'assemblage enfant ``joint`` : expressions retirées (valeurs gardées), lien
    ``RepeatJoint`` retiré, paramètres de nouveau modifiables. Sans effet sur un autre
    assemblage."""
    origin = origin_of(joint)
    if origin is None:
        return
    for path, text in expressions_of(joint).items():
        if path in param_paths(joint) and text.startswith(f"{origin.Name}."):
            joint.setExpression(path, None)
    joint.removeProperty(PROPERTY)
    schema.apply_editor_modes(joint, joint.Proxy.specs())


def unlink_part_joints(part: DocumentObject) -> None:
    """Dissocie les assemblages enfants qui touchent la copie ``part`` (copie dissociée)."""
    for joint in joints_of_part(part):
        unlink_joint(joint)


def joint_removed(origin: DocumentObject) -> None:
    """Assemblage d'origine supprimé (``unsetupObject``) : ses enfants sont dissociés, ils
    gardent leurs valeurs et aucune expression ne vise un objet absent. Rien pendant une
    annulation, un rétablissement ou une restauration."""
    if restoring_or_undoing(origin):
        return
    for child in children_of(origin):
        unlink_joint(child)


def _origins(repeat: DocumentObject) -> list[DocumentObject]:
    """Assemblages d'origine : ceux d'une pièce copiée par ``repeat`` (source, ou membre d'un
    ensemble source) qui ne sont pas déjà des enfants."""
    found: list[DocumentObject] = []
    for source in original_parts(repeat):
        found.extend(joint for joint in joints_of_part(source) if origin_of(joint) is None)
    return _unique(found)


def _repeat_children(repeat: DocumentObject) -> list[DocumentObject]:
    """Assemblages enfants qui touchent une copie liée de ``repeat``."""
    found: list[DocumentObject] = []
    for copy in copies_of(repeat):
        found.extend(joint for joint in joints_of_part(copy) if origin_of(joint) is not None)
    return _unique(found)


def _counterpart(
    part: DocumentObject | None,
    cell: Cell,
    by_cell: dict[tuple[str, Cell], DocumentObject],
    sources: set[str],
) -> DocumentObject | None:
    """Pièce qui remplace ``part`` dans l'assemblage de la cellule ``cell`` : sa copie si c'est une
    source (``None`` si elle n'existe pas ou plus), elle-même sinon (pièce fixe : elle reçoit un
    assemblage par copie)."""
    if part is None or part.Name not in sources:
        return part
    return by_cell.get((part.Name, cell))


def _existing(
    origin: DocumentObject, host: DocumentObject, guest: DocumentObject
) -> DocumentObject | None:
    """Assemblage du type de ``origin`` entre ``host`` et ``guest`` (enfant, ou enfant dissocié :
    il ne revient pas), ``None`` s'il n'y en a pas."""
    kind = type(origin.Proxy)
    for joint in joints_of_part(host):
        if type(joint.Proxy) is kind and (joint.HostPart, joint.GuestPart) == (host, guest):
            return joint
    return None


def _create_child(
    origin: DocumentObject, host: DocumentObject, guest: DocumentObject
) -> DocumentObject:
    """Assemblage enfant de ``origin`` entre ``host`` et ``guest``, lié à son origine."""
    child = create_joint(
        type(origin.Proxy),
        origin.Document,
        host,
        guest,
        origin.Proxy.params(origin),
        same_part=host == guest,
    )
    _bind(child, origin)
    return child


def _is_child_of(joint: DocumentObject | None, origin: DocumentObject) -> bool:
    """Vrai si ``joint`` est un enfant (non dissocié) de ``origin``."""
    return joint is not None and origin_of(joint) == origin


class JointsUpdate(NamedTuple):
    """Résultat de :func:`update_joints` : assemblages créés, nombre d'assemblages impossibles
    donc non recopiés (supprimés ou jamais créés) et motif du premier."""

    created: list[DocumentObject]
    skipped: int = 0
    reason: str = ""


def skipped_message(update: JointsUpdate) -> tuple[str, ...]:
    """Avertissement traduit des assemblages non recopiés (vide s'il n'y en a aucun)."""
    if not update.skipped:
        return ()
    template = _SKIPPED_ONE if update.skipped == 1 else _SKIPPED_MANY
    return (translated(template, {"count": str(update.skipped), "reason": update.reason}),)


def _refresh_placements(repeat: DocumentObject) -> None:
    """Calcule le placement et les cotes des copies de pièces (expressions déjà réécrites) pour
    juger les assemblages sur leur état définitif, avant le recalcul du document."""
    for copy in copies_of(repeat):
        if not is_furniture(copy):
            copy.recompute()


class _Decision(NamedTuple):
    """Ce que la répétition doit faire d'un assemblage d'origine pour une cellule."""

    origin: DocumentObject
    host: DocumentObject
    guest: DocumentObject
    error: str | None
    existing: DocumentObject | None


def _decisions(repeat: DocumentObject, cells: Iterable[Cell]) -> list[_Decision]:
    """Un jugement par assemblage d'origine et par cellule dont les deux pièces existent."""
    by_cell = {(copy.RepeatSource.Name, cell_of(copy)): copy for copy in copies_of(repeat)}
    sources = {source.Name for source in original_parts(repeat)}
    origins = _origins(repeat)
    found: list[_Decision] = []
    for cell in cells:
        for origin in origins:
            host = _counterpart(origin.HostPart, cell, by_cell, sources)
            guest = _counterpart(origin.GuestPart, cell, by_cell, sources)
            if host is not None and guest is not None:
                found.append(
                    _Decision(
                        origin,
                        host,
                        guest,
                        plan_error(origin, host, guest),
                        _existing(origin, host, guest),
                    )
                )
    return found


def update_joints(repeat: DocumentObject, *, enabled: bool, cells: Iterable[Cell]) -> JointsUpdate:
    """Met les assemblages enfants de ``repeat`` au réglage ``CopyJoints`` = ``enabled`` : faux,
    tous sont supprimés (avec leurs pièces usinées devenues sans assemblage) ; vrai, ils sont
    réévalués pour les copies des cellules ``cells`` : un assemblage impossible n'est pas créé,
    un enfant devenu impossible est supprimé, un enfant manquant devenu possible est créé (une
    copie dissociée ou supprimée n'en reçoit pas ; un enfant dissocié ne revient pas ; un enfant
    supprimé à la main revient). Renvoie les assemblages créés et le nombre de non recopiés.
    Ni transaction ni recalcul."""
    if not enabled:
        remove_joints(_repeat_children(repeat))
        return JointsUpdate([])
    _refresh_placements(repeat)
    decisions = _decisions(repeat, cells)
    skipped = _skipped(decisions)
    remove_joints(
        [
            item.existing
            for item in decisions
            if item.error is not None and _is_child_of(item.existing, item.origin)
        ]
    )
    created = [
        _create_child(item.origin, item.host, item.guest)
        for item in decisions
        if item.error is None and item.existing is None
    ]
    return JointsUpdate(created, *skipped)


def _skipped(decisions: Sequence[_Decision]) -> tuple[int, str]:
    """Nombre d'assemblages impossibles non recopiés (supprimés ou jamais créés ; un assemblage
    dissocié n'en fait pas partie) et motif du premier."""
    missing = [
        item
        for item in decisions
        if item.error is not None
        and (item.existing is None or _is_child_of(item.existing, item.origin))
    ]
    return len(missing), (missing[0].error or "") if missing else ""


def not_copied_warning(repeat: DocumentObject) -> str:
    """Avertissement traduit des assemblages de ``repeat`` impossibles donc non recopiés, vide
    s'il n'y en a aucun ou si ``CopyJoints`` est faux. Lecture seule, pour le panneau : à appeler
    après le recalcul qui a suivi :func:`update_joints`."""
    if not repeat.CopyJoints:
        return ""
    cells = {cell_of(copy) for copy in copies_of(repeat)}
    messages = skipped_message(JointsUpdate([], *_skipped(_decisions(repeat, cells))))
    return "".join(messages)


def hand_joints_warning(repeat: DocumentObject) -> str:
    """Avertissement traduit des assemblages posés **à la main** sur une copie de ``repeat`` (ni
    enfants d'une répétition, ni dissociés d'un enfant) devenus impossibles, vide s'il n'y en a
    aucun. Une copie qui change de rang ou de pas bouge, et ces assemblages ne la suivent pas :
    ils restent en erreur (ils ne sont jamais supprimés : ils sont à l'utilisateur). Lecture
    seule, à appeler après le recalcul."""
    broken = _unique(
        joint
        for copy in copies_of(repeat)
        for joint in joints_of_part(copy)
        if origin_of(joint) is None and "Invalid" in joint.State
    )
    if not broken:
        return ""
    template = _HAND_ONE if len(broken) == 1 else _HAND_MANY
    labels = ", ".join(f"« {joint.Label} »" for joint in broken)  # entiers : ils se ressemblent
    return translated(template, {"count": str(len(broken)), "labels": labels})
