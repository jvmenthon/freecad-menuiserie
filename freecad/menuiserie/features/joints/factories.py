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
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dowels import DowelParams
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.core.joints.rabbet import RabbetParams
from freecad.menuiserie.core.joints.tongue_groove import TongueGrooveParams
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import JointFeature, write_params
from freecad.menuiserie.features.joints.dowels import DowelJoint
from freecad.menuiserie.features.joints.mortise_tenon import MortiseTenonJoint
from freecad.menuiserie.features.joints.rabbet import RabbetJoint
from freecad.menuiserie.features.joints.tongue_groove import TongueGrooveJoint
from freecad.menuiserie.features.machined_part import blank_of, ensure_machined_part

__all__ = [
    "JOINT_CLASSES",
    "create_dowels",
    "create_joint",
    "create_mortise_tenon",
    "create_rabbet",
    "create_tongue_groove",
]

P = TypeVar("P")

JOINT_CLASSES: Final[Mapping[JointKind, type[JointFeature]]] = MappingProxyType(
    {
        JointKind.MORTISE_TENON: MortiseTenonJoint,
        JointKind.TONGUE_GROOVE: TongueGrooveJoint,
        JointKind.RABBET: RabbetJoint,
        JointKind.DOWELS: DowelJoint,
    }
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
            raise ValueError(translated(_OTHER_DOCUMENT, {"label": quoted_value(blank.Label)}))
    if host_blank.getParentGeoFeatureGroup() != guest_blank.getParentGeoFeatureGroup():
        raise ValueError(translated(_OTHER_CONTAINER))
    return host_blank, guest_blank


def _validated(params_type: Callable[..., P], params: Mapping[str, object]) -> P:
    """Paramètres de ``core`` ; ``ValueError`` traduite si l'un est refusé, ``TypeError`` si
    un nom est inconnu."""
    with translated_errors():
        values = params_type(**params)
    return values


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


def create_tongue_groove(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée une rainure-languette : rainure dans ``host``, languette au chant ou au bout de
    ``guest``. Paramètres de ``TongueGrooveParams`` en mm, 0 = automatique."""
    values = _validated(TongueGrooveParams, params)
    return create_joint(TongueGrooveJoint, doc, host, guest, values)


def create_rabbet(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée une feuillure (ou un logement) dans ``host`` à la place occupée par ``guest``.
    Paramètre de ``RabbetParams`` : ``through`` (filante, vrai par défaut)."""
    values = _validated(RabbetParams, params)
    return create_joint(RabbetJoint, doc, host, guest, values)


def create_dowels(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée des tourillons percés dans ``host`` et ``guest`` à travers leur contact.
    Paramètres de ``DowelParams`` en mm, 0 = automatique."""
    values = _validated(DowelParams, params)
    return create_joint(DowelJoint, doc, host, guest, values)
