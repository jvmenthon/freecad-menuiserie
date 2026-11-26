# SPDX-License-Identifier: LGPL-2.1-or-later
"""« Dernier utilisé » : retient les valeurs d'un objet qui vient d'être créé (ADR 0069).

Appelé par les panneaux de tâche à la validation d'une création. Chaque réglage n'est retenu que
si sa case « Dernier utilisé » est cochée ; un objet d'un autre type est ignoré.
"""

from __future__ import annotations

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joint_settings import record_joint_used
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.new_part_settings import record_part_used
from freecad.menuiserie.features.wood_material_proxy import MaterialProxy

__all__ = ["record_created"]


def record_created(obj: DocumentObject) -> None:
    """Retient les valeurs de la pièce ou de l'assemblage ``obj`` pour les réglages concernés."""
    proxy = getattr(obj, "Proxy", None)
    if isinstance(proxy, JointFeature):
        record_joint_used(obj)
    elif isinstance(proxy, MaterialProxy):
        record_part_used(obj)
