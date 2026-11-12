# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages de la façade publique (J3, J4).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.hardware import joint_params
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.drag_joints import JointChoice
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture_bindings import common_furniture
from freecad.menuiserie.features.hardware import get_catalog
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints import slide_room
from freecad.menuiserie.features.joints.factories import (
    create_biscuits,
    create_dovetail,
    create_dowels,
    create_drawer_slide,
    create_foot,
    create_half_lap,
    create_hinges,
    create_loose_tenons,
    create_miter,
    create_mortise_tenon,
    create_rabbet,
    create_shelf_pins,
    create_tongue_groove,
)
from freecad.menuiserie.features.joints.hardware_reference import HARDWARE_REFERENCE_PROPERTY
from freecad.menuiserie.features.machined_part import blank_of, machined_part_of
from freecad.menuiserie.features.near_gap import Closing
from freecad.menuiserie.features.near_gap import close_gap as _close_gap
from freecad.menuiserie.features.near_gap import closing_options as _closing_options

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
    ``host_depth``, ``count``, ``edge_distance``, ``thickness_offset``, ``hole_clearance`` ;
    ``reference`` : identifiant d'un tourillon du catalogue de quincaillerie (ADR 0033), qui fixe
    ``diameter`` et ``dowel_length`` sauf s'ils sont donnés.
    Mêmes validations et même absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_dowels, host, guest, _with_reference(JointKind.DOWELS, params), check)


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


def make_loose_tenons(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Relie deux pièces par des faux tenons logés dans une mortaise plate de
    chaque pièce, et recalcule le document.

    ``size`` : taille de la liste standard (``"auto"``, la plus grande qui tient, par défaut ;
    ``"8x50"``…) ; ``reference`` : identifiant d'un faux tenon du catalogue de quincaillerie
    (ADR 0033), qui fixe cette taille. Des cotes données en mm (``thickness``, ``along``,
    ``total_depth``, 0 = automatique) passent en taille personnalisée (``custom_size``).
    Autres paramètres : ``count``, ``edge_distance``, ``thickness_offset``, ``hole_clearance``.
    Mêmes validations et même absence de transaction que :func:`make_mortise_tenon`.
    """
    kind = JointKind.LOOSE_TENON
    fixed = _with_reference(kind, params)
    if any(name in fixed for name in ("thickness", "along", "total_depth")):
        fixed = {"custom_size": True, **fixed}  # cotes saisies : taille personnalisée
    return _make_joint(create_loose_tenons, host, guest, fixed, check)


def make_biscuits(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Relie deux pièces par des biscuits (lamelles) logés dans une fente de chaque pièce, et
    recalcule le document. ``size`` : lamelle Lamello (``"auto"``, la plus grande qui tient, par
    défaut ; ``"0"``, ``"10"``, ``"20"``) ; ``reference`` désigne un biscuit du catalogue ; pas
    de taille personnalisée. Autres paramètres comme :func:`make_loose_tenons`."""
    return _make_joint(
        create_biscuits, host, guest, _with_reference(JointKind.BISCUIT, params), check
    )


def make_drawer_slide(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Pose une coulisse de tiroir entre le côté de caisson ``host`` et le côté de tiroir
    ``guest``, face à face avec un jeu, et recalcule le document. Paramètres de ``SlideParams`` en
    mm, 0 = automatique ; ``reference`` désigne une coulisse du catalogue."""
    return _make_joint(
        create_drawer_slide, host, guest, _with_reference(JointKind.DRAWER_SLIDE, params), check
    )


def make_hinges(
    host: DocumentObject, guest: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Pose des charnières à cuvette entre le côté de caisson ``host`` (avant-trous de platine) et
    la porte ``guest`` (cuvettes, posée devant le chant avant du côté ou insérée), et recalcule le
    document. ``count`` : nombre de charnières (0 = automatique, 2 jusqu'à 900 mm de hauteur, 3
    jusqu'à 1 600 mm, puis 4) ; les autres paramètres de ``HingeParams`` sont en mm ;
    ``reference`` désigne une charnière du catalogue. Mêmes validations et même absence de
    transaction que :func:`make_mortise_tenon`."""
    return _make_joint(create_hinges, host, guest, _with_reference(JointKind.HINGE, params), check)


def slide_shortfall(joint: DocumentObject) -> float:
    """Jeu qui manque (mm) entre les côtés d'une coulisse de tiroir pour la loger : 0 si les côtés
    sont assez écartés, l'épaisseur de la coulisse moins l'écart s'ils se touchent."""
    return slide_room.slide_shortfall(joint)


def make_room_for_slide(joint: DocumentObject, move: str) -> list[str]:
    """Écarte les côtés d'une coulisse du jeu qui manque : ``move`` = ``"drawer"`` éloigne le côté
    du tiroir (réduire le tiroir), ``"cabinet"`` celui du caisson (élargir le meuble). Recalcule le
    document ; renvoie les avertissements à afficher."""
    return slide_room.make_room_for_slide(joint, move)


def _foot_factory(
    document: App.Document, part: DocumentObject, _guest: DocumentObject, **params: object
) -> DocumentObject:
    return create_foot(document, part, **params)


def make_foot(
    part: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Pose des pieds de caisson réglables sous le panneau ``part`` (pièce de bois ou pièce
    usinée couchée) et recalcule le document. Paramètres de ``FootParams`` en mm ; ``columns`` et
    ``rows`` donnent la grille (2 x 2 par défaut) ; ``reference`` désigne un pied du catalogue."""
    return _make_joint(_foot_factory, part, part, _with_reference(JointKind.FOOT, params), check)


def _shelf_pins_factory(
    document: App.Document, part: DocumentObject, _guest: DocumentObject, **params: object
) -> DocumentObject:
    return create_shelf_pins(document, part, **params)


def make_shelf_pins(
    part: DocumentObject, *, check: _Check | None = None, **params: object
) -> DocumentObject:
    """Perce le côté debout ``part`` (pièce de bois ou pièce usinée) de deux colonnes de trous au
    pas de 32 mm (système LR32) et pose les taquets de la tablette, puis recalcule le document.
    Le montant opposé est percé en miroir par le même objet, sauf ``both_sides=False``.
    Paramètres de ``ShelfPinsParams`` en mm, 0 = automatique ; ``reference`` désigne un taquet du
    catalogue."""
    fixed = _with_reference(JointKind.SHELF_PINS, params)
    return _make_joint(_shelf_pins_factory, part, part, fixed, check)


_UNKNOWN_REFERENCE = QT_TRANSLATE_NOOP(
    "Menuiserie", "Référence de quincaillerie inconnue : « {id} »."
)


def _with_reference(kind: JointKind, params: dict[str, object]) -> dict[str, object]:
    """``params`` sans ``reference`` (identifiant du catalogue de quincaillerie, ADR 0033), mais
    avec les cotes du commerce de cette référence, sauf celles déjà données ; ``ValueError``
    traduite si la référence est inconnue ou d'une autre famille."""
    if "reference" not in params:
        return params
    rest = {name: value for name, value in params.items() if name != "reference"}
    reference = str(params["reference"])
    item = get_catalog().find(reference)
    if item is None:
        raise ValueError(translated(_UNKNOWN_REFERENCE, {"id": quoted_value(reference)}))
    with translated_errors():
        fixed = joint_params(item, kind)
    return {**fixed, **rest, _TAG: item.id}


_TAG: Final = "_hardware_reference"  # identifiant retenu par ``_make_joint``, pas un paramètre

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
    reference = str(params.get(_TAG, ""))
    joint = factory(document, host, guest, **{k: v for k, v in params.items() if k != _TAG})
    if reference:
        setattr(joint, HARDWARE_REFERENCE_PROPERTY, reference)
    if check is not None:
        joint = check(joint)
    return _shown_and_recomputed(joint)


def show_joint(joint: DocumentObject) -> None:
    """Pose les ViewProviders de l'assemblage et des pièces usinées de ses deux brutes, si
    l'interface est chargée. Sans recalcul."""
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


def _shown_and_recomputed(joint: DocumentObject) -> DocumentObject:
    """Pose les ViewProviders (:func:`show_joint`), puis recalcule le document. Commun à toutes
    les fabriques d'assemblage."""
    show_joint(joint)
    # L'assemblage de deux pièces d'un même ensemble se range sous lui dans l'arbre : l'ensemble
    # est marqué modifié pour que l'arbre relise ses enfants (``claimChildren``).
    ensemble = common_furniture(joint.HostPart, joint.GuestPart)
    if ensemble is not None:
        ensemble.touch()
    joint.Document.recompute()
    return joint


# --- Pièces proches qui ne se touchent pas (ADR 0039) ---------------------------------------


def closing_options(host: DocumentObject, guest: DocumentObject) -> Closing | None:
    """Écart (mm) et façons de le combler (``"move"`` : une pièce se déplace jusqu'au contact,
    ``"grow"`` : une pièce s'agrandit jusqu'au contact, avec le nom de la pièce) si les deux
    pièces d'équerre ne sont écartées que de 20 mm au plus sur un seul axe ; ``None`` sinon
    (déjà en contact, chevauchées, éloignées, en biais)."""
    return _closing_options(host, guest)


def close_gap(
    host: DocumentObject, guest: DocumentObject, how: str, choose: JointChoice | None = None
) -> list[str]:
    """Comble l'écart entre deux pièces proches (``how`` : ``"move"`` ou ``"grow"``), l'invitée
    de préférence, et recalcule le document. Renvoie les avertissements (membre d'ensemble relié,
    assemblage qui ne touche plus…) ; ``ValueError`` traduite si l'option n'est pas permise.
    ``choose`` (facultatif) décide du sort des assemblages que le déplacement défait, comme pour
    un glissement à la souris : sans lui, on prévient seulement.
    Aucune transaction n'est ouverte : c'est à l'appelant de le faire pour pouvoir annuler."""
    return _close_gap(host, guest, how, choose)
