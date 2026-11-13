# SPDX-License-Identifier: LGPL-2.1-or-later
"""Migration du lien ``Joints`` des pièces usinées vers un lien global (ADR 0054)."""

from __future__ import annotations

from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.schema import PropertySpec

__all__ = ["globalize_joints"]


def globalize_joints(obj: DocumentObject, specs: tuple[PropertySpec, ...]) -> None:
    """``Joints`` d'un document d'avant l'ADR 0054 (``App::PropertyLinkList``) recréée en
    ``App::PropertyLinkListGlobal`` : un assemblage peut être rangé dans un autre Std Part que la
    pièce usinée ; les assemblages cités sont gardés."""
    if obj.getTypeIdOfProperty("Joints") != "App::PropertyLinkList":
        return
    joints = list(obj.Joints)
    obj.setPropertyStatus("Joints", "-ReadOnly")
    obj.removeProperty("Joints")
    wanted = [spec for spec in specs if spec.name == "Joints"]
    schema.add_missing_properties(obj, wanted)
    obj.Joints = joints
    schema.apply_editor_modes(obj, wanted)
