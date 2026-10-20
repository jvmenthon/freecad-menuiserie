# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fabriques des assemblages du document (``create_…``) et classes par type (``JOINT_CLASSES``).

Une fabrique valide tout avant de créer quoi que ce soit (deux pièces distinctes, pièces de
bois ou pièces usinées, même document, même conteneur, paramètres), crée l'assemblage entre
les deux brutes, puis la pièce usinée de chaque brute si besoin (une seule par brute). Ni
transaction ni recalcul : c'est à l'appelant de les faire.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Final, TypeVar

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointError, JointKind
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import templated_message, translated
from freecad.menuiserie.features.joints.base import JointFeature, write_params
from freecad.menuiserie.features.joints.mortise_tenon import MortiseTenonJoint
from freecad.menuiserie.features.machined_part import blank_of, ensure_machined_part

__all__ = ["JOINT_CLASSES", "create_joint", "create_mortise_tenon"]

P = TypeVar("P")

JOINT_CLASSES: Final[Mapping[JointKind, type[JointFeature]]] = MappingProxyType(
    {JointKind.MORTISE_TENON: MortiseTenonJoint}
)

_SAME_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Choisissez deux pièces différentes pour un assemblage."
)
_OTHER_DOCUMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » appartient à un autre document."
)
_OTHER_CONTAINER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les deux pièces doivent être dans le même conteneur (pièce ou corps)."
)


def _checked_blanks(
    doc: Document, host: DocumentObject, guest: DocumentObject
) -> tuple[DocumentObject, DocumentObject]:
    """Brutes de ``host`` et ``guest`` ; ``TypeError`` ou ``ValueError`` traduites si elles ne
    peuvent pas être assemblées."""
    host_blank, guest_blank = blank_of(host), blank_of(guest)
    if host_blank == guest_blank:
        raise ValueError(translated(_SAME_PART))
    for blank in (host_blank, guest_blank):
        if blank.Document != doc:
            raise ValueError(translated(_OTHER_DOCUMENT, {"label": str(blank.Label)}))
    if host_blank.getParentGeoFeatureGroup() != guest_blank.getParentGeoFeatureGroup():
        raise ValueError(translated(_OTHER_CONTAINER))
    return host_blank, guest_blank


def _validated(params_type: Callable[..., P], params: Mapping[str, object]) -> P:
    """Paramètres de ``core`` ; ``ValueError`` traduite si l'un est refusé, ``TypeError`` si
    un nom est inconnu."""
    try:
        return params_type(**params)
    except JointError as error:
        raise ValueError(templated_message(error)) from error


def create_joint(
    joint_class: type[JointFeature],
    doc: Document,
    host: DocumentObject,
    guest: DocumentObject,
    params: object,
) -> DocumentObject:
    """Crée un assemblage ``joint_class`` entre les brutes de ``host`` et ``guest`` avec les
    paramètres validés ``params``, puis les pièces usinées qui manquent ; rien n'est créé si
    les pièces sont refusées."""
    host_blank, guest_blank = _checked_blanks(doc, host, guest)
    obj = doc.addObject("Part::FeaturePython", joint_class.OBJECT_NAME)
    joint_class(obj)
    container = host_blank.getParentGeoFeatureGroup()
    if container is not None:
        container.addObject(obj)
    obj.Label = translated(joint_class.LABEL)
    obj.HostPart = host_blank
    obj.GuestPart = guest_blank
    write_params(obj, params)
    for blank in (host_blank, guest_blank):
        machined = ensure_machined_part(blank)
        machined.Joints = [*machined.Joints, obj]
    return obj


def create_mortise_tenon(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée un tenon-mortaise : mortaise dans ``host``, tenon au bout de ``guest`` (pièces de
    bois ou pièces usinées). Paramètres de ``MortiseTenonParams`` en mm, 0 = automatique."""
    values = _validated(MortiseTenonParams, params)
    return create_joint(MortiseTenonJoint, doc, host, guest, values)
