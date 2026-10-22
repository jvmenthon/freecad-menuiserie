# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fabriques des assemblages du document (``create_…``).

Une fabrique valide tout avant de créer quoi que ce soit (deux pièces distinctes, pièces de
bois ou pièces usinées, même document, même conteneur, paramètres), crée l'assemblage entre
les deux brutes, puis la pièce usinée de chaque brute si besoin (une seule par brute). Ni
transaction ni recalcul : c'est à l'appelant de les faire.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final, TypeVar

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joint_names import joint_label
from freecad.menuiserie.features.joints.base import JointFeature, write_params
from freecad.menuiserie.features.joints.dovetail import DovetailJoint
from freecad.menuiserie.features.joints.dowels import DowelJoint
from freecad.menuiserie.features.joints.half_lap import HalfLapJoint
from freecad.menuiserie.features.joints.miter import MiterJoint
from freecad.menuiserie.features.joints.mortise_tenon import MortiseTenonJoint
from freecad.menuiserie.features.joints.rabbet import RabbetJoint
from freecad.menuiserie.features.joints.tongue_groove import TongueGrooveJoint
from freecad.menuiserie.features.machined_part import blank_of, ensure_machined_part

__all__ = [
    "create_dovetail",
    "create_dowels",
    "create_half_lap",
    "create_joint",
    "create_miter",
    "create_mortise_tenon",
    "create_rabbet",
    "create_tongue_groove",
]

P = TypeVar("P")

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
    obj.HostPart = host_blank
    obj.GuestPart = guest_blank
    obj.Label = joint_label(obj)
    write_params(obj, params)
    for blank in (host_blank, guest_blank):
        machined = ensure_machined_part(blank)
        machined.Joints = [*machined.Joints, obj]
    return obj


def _create(
    joint_class: type[JointFeature],
    doc: Document,
    host: DocumentObject,
    guest: DocumentObject,
    params: Mapping[str, object],
) -> DocumentObject:
    """Paramètres validés (objet valeur ``joint_class.PARAMS``), puis assemblage créé par
    :func:`create_joint`."""
    return create_joint(joint_class, doc, host, guest, _validated(joint_class.PARAMS, params))


def create_mortise_tenon(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée un tenon-mortaise : mortaise dans ``host``, tenon au bout de ``guest`` (pièces de
    bois ou pièces usinées). Paramètres de ``MortiseTenonParams`` en mm, 0 = automatique."""
    return _create(MortiseTenonJoint, doc, host, guest, params)


def create_tongue_groove(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée une rainure-languette : rainure dans ``host``, languette au chant ou au bout de
    ``guest``. Paramètres de ``TongueGrooveParams`` en mm, 0 = automatique."""
    return _create(TongueGrooveJoint, doc, host, guest, params)


def create_rabbet(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée une feuillure (ou un logement) dans ``host`` à la place occupée par ``guest``.
    Paramètre de ``RabbetParams`` : ``through`` (filante, vrai par défaut)."""
    return _create(RabbetJoint, doc, host, guest, params)


def create_dowels(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée des tourillons percés dans ``host`` et ``guest`` à travers leur contact.
    Paramètres de ``DowelParams`` en mm, 0 = automatique."""
    return _create(DowelJoint, doc, host, guest, params)


def create_half_lap(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée un mi-bois : ``host`` et ``guest``, de même épaisseur et à fleur, se chevauchent ;
    chacune est entaillée dans leur boîte commune. Paramètres de ``HalfLapParams`` : ``depth``
    en mm (0 = moitié de l'épaisseur), ``flip_side``."""
    return _create(HalfLapJoint, doc, host, guest, params)


def create_dovetail(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée une queue d'aronde traversante : ``guest`` (pièce à queues) touche ``host`` (pièce à
    griffes) par son bout, le bout de ``host`` à fleur de la face extérieure de ``guest``.
    Paramètres de ``DovetailParams`` (0 = automatique) : ``tail_count``, ``pin_width`` en mm,
    ``slope`` (pente 1:n)."""
    return _create(DovetailJoint, doc, host, guest, params)


def create_miter(
    doc: Document, host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Crée un onglet : ``host`` et ``guest``, dessinées à leur longueur hors tout, se
    chevauchent au coin ; chacune perd le prisme triangulaire de leur boîte commune situé du
    côté de l'autre. Aucun paramètre (``MiterParams`` est vide)."""
    return _create(MiterJoint, doc, host, guest, params)
