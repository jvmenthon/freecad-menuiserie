# SPDX-License-Identifier: LGPL-2.1-or-later
"""Essai d'un assemblage qui vient d'être créé, avant son premier recalcul (ADR 0026).

Un assemblage impossible (pièces qui ne sont pas d'équerre, qui ne se touchent pas…) lève
``ValueError`` dans ``execute()`` ; FreeCAD en imprime la trace, puis le message de l'assemblage
et celui de ses pièces usinées. La commande d'assemblage passe donc :func:`feasible_joint` à la
fabrique de l'api (mot-clé ``check``), qui l'appelle sans recalcul : le plan est calculé dans un
``try`` et, s'il est impossible, rien n'est recalculé ni créé (la transaction est abandonnée).
"""

from __future__ import annotations

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joint_names import joint_label
from freecad.menuiserie.features.joints.base import plan_for

__all__ = ["feasible_joint"]


def feasible_joint(joint: DocumentObject) -> DocumentObject:
    """``joint`` s'il est réalisable entre ses pièces, au besoin rôles inversés (rôles mal
    devinés) ; sinon ``ValueError`` traduite qui explique pourquoi, rôles d'origine. Aucun
    recalcul."""
    try:
        plan_for(joint)
    except ValueError as error:
        joint.HostPart, joint.GuestPart = joint.GuestPart, joint.HostPart
        try:
            plan_for(joint)
        except ValueError:
            joint.HostPart, joint.GuestPart = joint.GuestPart, joint.HostPart
            raise error from None
        joint.Label = joint_label(joint)
    return joint
