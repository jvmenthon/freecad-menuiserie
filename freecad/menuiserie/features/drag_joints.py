# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages défaits par un déplacement, au relâchement (ADR 0026, qui modifie B7 de l'ADR 0021).

Un glissement (souris) ou une distance définie déplace la brute sans recalcul. Au relâchement,
avant tout recalcul, :func:`settle_joints` essaie le plan de chaque assemblage lié à la pièce
(``plan_for``, dans un ``try``, sans recalcul) : un recalcul qui lèverait ``ValueError`` ferait
imprimer la trace Python par FreeCAD. Pour les assemblages qui ne tiennent plus, la fonction de
choix ``choose`` (injectée : la fenêtre est dans ``gui/``, rien d'interactif ici) décide :

- ``True`` : les assemblages sont supprimés (:func:`remove_joints`), avec leurs pièces usinées
  devenues sans assemblage, et le déplacement est gardé ;
- ``False`` : :class:`DragCancelledError`, l'appelant remet la pièce où elle était.

Le contrôle est commun à tout changement de ``Placement`` fait par les outils de l'atelier :
glissement et « Définir une distance » (``part_drag.end_drag``), rotation du panneau de la pièce
(:func:`rotate_checked`).

Sans fonction de choix (script, API), rien n'est décidé : B7 d'origine (déplacement gardé,
avertissement).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.snap import Turn
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.joints.base import is_joint, plan_for
from freecad.menuiserie.features.machined_part import machined_part_of, remove_machined_part
from freecad.menuiserie.features.placement import SnapSession, rotate_part

__all__ = [
    "DragCancelledError",
    "JointChoice",
    "broken_joints",
    "invalid_joints",
    "remove_joints",
    "rotate_checked",
    "settle_joints",
]

# Fonction de choix : reçoit les libellés (entre guillemets) des assemblages défaits ; vrai =
# supprimer les assemblages et garder le déplacement, faux = annuler le déplacement.
JointChoice = Callable[[Sequence[str]], bool]

_REMOVED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'assemblage {labels} a été supprimé : le déplacement le défaisait."
)
_REMOVED_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les assemblages {labels} ont été supprimés : le déplacement les défaisait."
)


class DragCancelledError(Exception):
    """Le déplacement est annulé au relâchement (choix « Annuler le déplacement », Échap ou
    fenêtre fermée) : la pièce est revenue où elle était, rien n'est à signaler."""


def invalid_joints(part: DocumentObject) -> frozenset[str]:
    """Noms des assemblages de la brute ``part`` déjà en erreur avant un changement de position :
    ils ne sont pas défaits par lui."""
    return frozenset(
        joint.Name for joint in part.InList if is_joint(joint) and "Invalid" in joint.State
    )


def broken_joints(
    part: DocumentObject, already_invalid: frozenset[str] = frozenset()
) -> list[DocumentObject]:
    """Assemblages liés à la brute ``part`` dont le plan d'usinage est impossible maintenant
    (``ValueError`` traduite de ``plan_for``), sans recalcul ; ceux de ``already_invalid`` (noms),
    déjà défaits avant le déplacement, ne comptent pas."""
    broken = []
    for joint in part.InList:
        if not is_joint(joint) or joint.Name in already_invalid:
            continue
        try:
            plan_for(joint)
        except ValueError:
            broken.append(joint)
    return broken


def remove_joints(joints: Sequence[DocumentObject]) -> None:
    """Supprime ``joints`` (logique existante : la pièce usinée est recalculée sans eux) puis
    chaque pièce usinée de leurs pièces qui n'a plus d'assemblage (:func:`remove_machined_part`,
    la brute est réaffichée). Sans recalcul ni transaction : à l'appelant."""
    if not joints:
        return
    document = joints[0].Document
    machined: list[DocumentObject] = []
    for joint in joints:
        for part in (joint.HostPart, joint.GuestPart):
            found = None if part is None else machined_part_of(part)
            if found is not None and found not in machined:
                machined.append(found)
    for joint in joints:
        document.removeObject(joint.Name)
    for found in machined:
        if not found.Joints:
            remove_machined_part(found)


def settle_joints(
    part: DocumentObject, already_invalid: frozenset[str], choose: JointChoice | None
) -> list[str]:
    """Avant le recalcul : teste les assemblages de ``part`` (:func:`broken_joints`) et, s'il y en
    a, demande à ``choose``. Renvoie le message (vue rapport) des assemblages supprimés, vide si
    rien n'est défait ou sans ``choose``. ``DragCancelledError`` si ``choose`` renvoie faux ;
    l'appelant remet la pièce."""
    if choose is None:
        return []
    broken = broken_joints(part, already_invalid)
    if not broken:
        return []
    labels = [f"« {quoted_value(joint.Label)} »" for joint in broken]
    if not choose(labels):
        raise DragCancelledError
    remove_joints(broken)
    template = _REMOVED if len(labels) == 1 else _REMOVED_MANY
    return [translated(template, {"labels": ", ".join(labels)})]


def rotate_checked(
    part: DocumentObject,
    turn: Turn,
    session: SnapSession | None = None,
    choose: JointChoice | None = None,
) -> bool:
    """:func:`~freecad.menuiserie.features.placement.rotate_part` avec le contrôle des assemblages
    (ADR 0026) : en modification (sans ``session``), le quart de tour est écrit sans recalcul,
    puis les assemblages de ``part`` sont essayés (:func:`settle_joints`). Supprimés au choix de
    ``choose`` (avertissement dans la vue rapport, rotation gardée), ou rotation annulée :
    ``Placement`` redevient celui d'avant, celui de la pièce usinée aussi, et le résultat est
    faux. Faux aussi si une expression pilote le ``Placement`` (comme ``rotate_part``)."""
    if session is not None or choose is None:
        return rotate_part(part, turn, session)
    previous, invalid = App.Placement(part.Placement), invalid_joints(part)
    if not rotate_part(part, turn):
        return False
    try:
        messages = settle_joints(part, invalid, choose)
    except DragCancelledError:
        part.Placement = previous
        machined = machined_part_of(part)
        if machined is not None:
            machined.Placement = previous
        return False
    for message in messages:
        report_warning(message)
    return True
