# SPDX-License-Identifier: LGPL-2.1-or-later
"""Façade publique de l'atelier pour les scripts et la console Python de FreeCAD.

Exemple (console) ::

    from freecad.menuiserie.api import make_wood_part

    planche = make_wood_part(800, 200, 22, "chene")
    planche.Length = 1000

Assemblage (J3) ::

    from freecad.menuiserie.api import make_mortise_tenon

    assemblage = make_mortise_tenon(montant, traverse, tenon_thickness=8)

C'est le seul module hors de ``gui/`` autorisé à importer ``gui/``, et seulement quand
l'interface est chargée (``App.GuiUp``) : il fonctionne aussi dans ``freecadcmd``.
"""

from __future__ import annotations

from collections.abc import Callable

import FreeCAD as App

from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.joints.factories import (
    create_dowels,
    create_mortise_tenon,
    create_rabbet,
    create_tongue_groove,
)
from freecad.menuiserie.features.machined_part import (
    blank_of,
    is_machined_part,
    machined_part_of,
    remove_machined_part,
)
from freecad.menuiserie.features.wood_part import create_wood_part, validated_arguments

__all__ = [
    "blank_of",
    "is_machined_part",
    "machined_part_of",
    "make_dowels",
    "make_mortise_tenon",
    "make_rabbet",
    "make_tongue_groove",
    "make_wood_part",
    "remove_machined_part",
]


def make_wood_part(
    length: float = 800.0,
    width: float = 200.0,
    thickness: float = 22.0,
    material_id: str | None = None,
    *,
    mark: str = "",
    doc: Document | None = None,
) -> DocumentObject:
    """Crée une pièce de bois (cotes finies en mm), l'affiche si l'interface est chargée et
    recalcule le document.

    ``doc`` vaut par défaut le document actif, ou un nouveau document s'il n'y en a pas : les
    cotes et le matériau sont validés avant, si bien qu'une erreur ne crée aucun document. Aucune
    transaction n'est ouverte : c'est à l'appelant de le faire pour pouvoir annuler.
    """
    validated_arguments(length, width, thickness, material_id)
    document = doc if doc is not None else App.ActiveDocument or App.newDocument()
    obj = create_wood_part(
        document,
        length=length,
        width=width,
        thickness=thickness,
        material_id=material_id,
        mark=mark,
    )
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.wood_part import (
            ViewProviderWoodPart,
        )

        ViewProviderWoodPart(obj.ViewObject)
    document.recompute()
    return obj


def make_mortise_tenon(
    host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Relie deux pièces (pièces de bois ou pièces usinées) par un tenon-mortaise et recalcule
    le document : mortaise dans ``host``, tenon au bout de ``guest``.

    Paramètres facultatifs en mm (0 = automatique) : ``tenon_thickness``, ``tenon_width``,
    ``tenon_length``, ``width_offset``, ``thickness_offset``, ``through``,
    ``mortise_clearance``. Pièces et paramètres sont validés avant toute création
    (``TypeError`` ou ``ValueError`` traduites). Aucune transaction n'est ouverte : c'est à
    l'appelant de le faire pour pouvoir annuler.
    """
    return _make_joint(create_mortise_tenon, host, guest, params)


def make_tongue_groove(
    host: DocumentObject, guest: DocumentObject, **params: object
) -> DocumentObject:
    """Relie deux pièces par une rainure-languette et recalcule le document : rainure dans
    ``host``, languette au chant ou au bout de ``guest``.

    Paramètres facultatifs en mm : ``tongue_thickness`` (0 = automatique), ``tongue_length``,
    ``thickness_offset``, ``groove_clearance``, ``through_groove``. Mêmes validations et même
    absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_tongue_groove, host, guest, params)


def make_rabbet(host: DocumentObject, guest: DocumentObject, **params: object) -> DocumentObject:
    """Loge ``guest`` dans une feuillure de ``host`` (les deux pièces doivent se chevaucher) et
    recalcule le document. Paramètre facultatif : ``through`` (feuillure filante, vrai par
    défaut). Mêmes validations et même absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_rabbet, host, guest, params)


def make_dowels(host: DocumentObject, guest: DocumentObject, **params: object) -> DocumentObject:
    """Relie deux pièces par des tourillons percés à travers leur contact et recalcule le
    document.

    Paramètres facultatifs en mm (0 = automatique) : ``diameter``, ``dowel_length``,
    ``host_depth``, ``count``, ``edge_distance``, ``thickness_offset``, ``hole_clearance``.
    Mêmes validations et même absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_dowels, host, guest, params)


_JointFactory = Callable[..., DocumentObject]


def _make_joint(
    factory: _JointFactory, host: DocumentObject, guest: DocumentObject, params: dict[str, object]
) -> DocumentObject:
    """Crée l'assemblage par ``factory`` dans le document des pièces, pose les ViewProviders
    si l'interface est chargée, puis recalcule (:func:`_shown_and_recomputed`)."""
    document = blank_of(host).Document
    joint = factory(document, host, guest, **params)
    return _shown_and_recomputed(joint)


def _shown_and_recomputed(joint: DocumentObject) -> DocumentObject:
    """Pose les ViewProviders de l'assemblage et des pièces usinées de ses deux brutes (si
    l'interface est chargée), puis recalcule le document. Commun à toutes les fabriques
    d'assemblage."""
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.joint import ViewProviderJoint
        from freecad.menuiserie.gui.view_providers.machined_part import (
            ViewProviderMachinedPart,
        )

        ViewProviderJoint(joint.ViewObject)
        for blank in (joint.HostPart, joint.GuestPart):
            machined = machined_part_of(blank)
            if machined is not None and not isinstance(
                machined.ViewObject.Proxy, ViewProviderMachinedPart
            ):
                ViewProviderMachinedPart(machined.ViewObject)
    joint.Document.recompute()
    return joint
