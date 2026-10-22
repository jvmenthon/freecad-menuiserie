# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nom d'un assemblage : « {type} : {pièce hôte} {pièce invitée} » (J6, demande de jv), tenu à
jour quand une des deux pièces est renommée. Le libellé reste unique dans le document (suffixe
« (n) » de :mod:`freecad.menuiserie.core.naming`)."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.naming import label_for_mark
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.part_names import other_labels

__all__ = ["JOINT_LABEL", "joint_label", "sync_joint_labels"]

JOINT_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "{kind} : {host} {guest}")


def joint_label(joint: DocumentObject) -> str:
    """Libellé de l'assemblage ``joint`` d'après son type et les libellés de ses deux pièces."""
    text = translated(
        JOINT_LABEL,
        {
            "kind": translated(joint.Proxy.LABEL),
            "host": str(joint.HostPart.Label),
            "guest": str(joint.GuestPart.Label),
        },
    )
    return label_for_mark(text, text, other_labels(joint))


def _is_joint_of(obj: DocumentObject, blank: DocumentObject) -> bool:
    proxy = getattr(obj, "Proxy", None)
    return isinstance(getattr(proxy, "LABEL", None), str) and blank in (
        getattr(obj, "HostPart", None),
        getattr(obj, "GuestPart", None),
    )


def sync_joint_labels(blank: DocumentObject) -> None:
    """Libellés des assemblages de la pièce brute ``blank`` d'après son libellé ; sans effet si
    elle n'en a pas."""
    for joint in blank.InList:
        if _is_joint_of(joint, blank):
            label = joint_label(joint)
            if joint.Label != label:
                joint.Label = label
