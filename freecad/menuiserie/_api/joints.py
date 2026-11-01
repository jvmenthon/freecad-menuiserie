# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages de la façade publique (J3, J4).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Callable

import FreeCAD as App

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture_bindings import common_furniture
from freecad.menuiserie.features.joints.factories import (
    create_dovetail,
    create_dowels,
    create_half_lap,
    create_miter,
    create_mortise_tenon,
    create_rabbet,
    create_tongue_groove,
)
from freecad.menuiserie.features.machined_part import blank_of, machined_part_of

# --- Assemblages (J3, J4) -----------------------------------------------------------------


def make_mortise_tenon(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Relie deux pièces (pièces de bois ou pièces usinées) par un tenon-mortaise et recalcule
    le document : mortaise dans ``host``, tenon au bout de ``guest``.

    Paramètres facultatifs en mm (0 = automatique) : ``tenon_thickness``, ``tenon_width``,
    ``tenon_length``, ``width_offset``, ``thickness_offset``, ``through``,
    ``mortise_clearance`` ; entre pièces en biais, ``oblique_reference`` (« TenonPiece » par
    défaut, « MortisedPiece », « HalfAngle »). Pièces et paramètres sont validés avant toute
    création (``TypeError`` ou ``ValueError`` traduites). Aucune transaction n'est ouverte : c'est à
    l'appelant de le faire pour pouvoir annuler.

    Toutes les fonctions ``make_…`` d'assemblage acceptent le mot-clé ``check`` : fonction
    appelée sur l'assemblage créé **avant le premier recalcul**, qui le renvoie (rôles inversés
    au besoin) ou lève ``ValueError`` ; la commande de l'interface y passe
    ``features.joints.feasible.feasible_joint``, pour qu'un assemblage impossible ne soit jamais
    recalculé (ADR 0026). Sans ``check``, l'assemblage impossible est créé en erreur.
    """
    return _make_joint(create_mortise_tenon, host, guest, params, check)


def make_tongue_groove(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Relie deux pièces par une rainure-languette et recalcule le document : rainure dans
    ``host``, languette au chant ou au bout de ``guest``.

    Paramètres facultatifs en mm : ``tongue_thickness`` (0 = automatique), ``tongue_length``,
    ``thickness_offset``, ``groove_clearance``, ``through_groove``. Mêmes validations et même
    absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_tongue_groove, host, guest, params, check)


def make_rabbet(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Loge ``guest`` dans une feuillure de ``host`` (les deux pièces doivent se chevaucher) et
    recalcule le document. Paramètre facultatif : ``through`` (feuillure filante, vrai par
    défaut). Mêmes validations et même absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_rabbet, host, guest, params, check)


def make_dowels(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Relie deux pièces par des tourillons percés à travers leur contact et recalcule le
    document.

    Paramètres facultatifs en mm (0 = automatique) : ``diameter``, ``dowel_length``,
    ``host_depth``, ``count``, ``edge_distance``, ``thickness_offset``, ``hole_clearance``.
    Mêmes validations et même absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_dowels, host, guest, params, check)


def make_half_lap(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Relie à mi-bois deux pièces de même épaisseur, à fleur, qui se chevauchent (croix, T ou
    angle) et recalcule le document : ``host`` est entaillée par-dessus, ``guest`` par-dessous.

    Paramètres facultatifs : ``depth`` (profondeur de l'entaille de ``host`` en mm, 0 = moitié
    de l'épaisseur), ``flip_side`` (entaille de ``host`` par-dessous). Mêmes validations et même
    absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_half_lap, host, guest, params, check)


def make_dovetail(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Relie à queue d'aronde traversante ``guest`` (pièce à queues, en contact par son bout,
    dessinée à sa longueur visible) et ``host`` (pièce à griffes, hors tout, son bout à fleur
    de la face extérieure de ``guest``), puis recalcule le document.

    Paramètres facultatifs, 0 = automatique : ``tail_count`` (nombre de queues),
    ``pin_width`` (largeur des griffes au plus étroit, en mm, le tiers de l'épaisseur de
    ``host``), ``angle`` (angle des flancs en degrés, 10° ; au plus 30°). Mêmes validations et
    même absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_dovetail, host, guest, params, check)


def make_miter(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Relie à onglet ``host`` et ``guest``, dessinées à leur longueur hors tout (de pointe
    longue à pointe longue) et qui se chevauchent au coin, puis recalcule le document. La coupe
    passe par le coin extérieur et le coin intérieur : 45° pour deux largeurs égales. Aucun
    paramètre en J4 (un nom inconnu lève ``TypeError``) ; mêmes validations et même absence de
    transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_miter, host, guest, params, check)


_JointFactory = Callable[..., DocumentObject]
_Check = Callable[[DocumentObject], DocumentObject]


def _make_joint(
    factory: _JointFactory,
    host: DocumentObject,
    guest: DocumentObject,
    params: dict[str, object],
    check: _Check | None = None,
) -> DocumentObject:
    """Crée l'assemblage par ``factory`` dans le document des pièces, le fait contrôler par
    ``check`` s'il est donné, pose les ViewProviders si l'interface est chargée, puis recalcule
    (:func:`_shown_and_recomputed`). ``check`` passe **avant le premier recalcul** : un assemblage
    impossible ferait imprimer sa trace par FreeCAD ; il renvoie l'assemblage (rôles inversés au
    besoin) ou lève ``ValueError``, et c'est à l'appelant d'annuler sa transaction."""
    document = blank_of(host).Document
    joint = factory(document, host, guest, **params)
    if check is not None:
        joint = check(joint)
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
    # L'assemblage de deux pièces d'un même ensemble se range sous lui dans l'arbre : l'ensemble
    # est marqué modifié pour que l'arbre relise ses enfants (``claimChildren``).
    ensemble = common_furniture(joint.HostPart, joint.GuestPart)
    if ensemble is not None:
        ensemble.touch()
    joint.Document.recompute()
    return joint
