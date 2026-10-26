# SPDX-License-Identifier: LGPL-2.1-or-later
"""Façade publique de l'atelier pour les scripts et la console Python de FreeCAD.

Exemple (console) ::

    from freecad.menuiserie.api import make_wood_part

    planche = make_wood_part(800, 200, 22, "chene")
    planche.Length = 1000

Pièce en bois, forme dessinée avec Sketcher / PartDesign (PD-b) ::

    from freecad.menuiserie.api import make_shaped_part, reset_shaped_axes

    pied = make_shaped_part(corps, "chene", mark="P1")  # corps : PartDesign::Body
    pied.Length  # cotes d'encombrement, en lecture seule, qui suivent le dessin

Assemblage (J3) ::

    from freecad.menuiserie.api import make_mortise_tenon

    assemblage = make_mortise_tenon(montant, traverse, tenon_thickness=8)

Ensemble (J4) ::

    from freecad.menuiserie.api import make_furniture, resize_furniture

    bureau, avertissements = make_furniture([plateau, joue_g, joue_d, voile], label="Bureau")
    avertissements = resize_furniture(bureau, depth=800)

Liste de débit (J2) ::

    from freecad.menuiserie.api import export_cut_list_csv, make_cut_list

    feuille = make_cut_list(doc)  # feuille « Liste de débit », réécrite à chaque recalcul
    export_cut_list_csv(doc, "/chemin/debit.csv", objects=[caisson])

C'est le seul module hors de ``gui/`` autorisé à importer ``gui/``, et seulement quand
l'interface est chargée (``App.GuiUp``) : il fonctionne aussi dans ``freecadcmd``.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import FreeCAD as App

from freecad.menuiserie.core.cutlist import FRENCH_CSV, INTERNATIONAL_CSV, CsvDialect, CutList
from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.templates.carcass import CarcassJoinery, CarcassParams
from freecad.menuiserie.features import (
    cutlist_collect,
    cutlist_export,
    cutlist_marks,
    cutlist_object,
    cutlist_thumbnail,
    distance_move,
    furniture_edges,
    furniture_locks,
    furniture_members,
    templates,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import furniture_of as _member_furniture
from freecad.menuiserie.features.furniture_bindings import (
    LockedPiecesError,
    notice_messages,
    report,
)
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.factories import (
    create_dovetail,
    create_dowels,
    create_half_lap,
    create_miter,
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
from freecad.menuiserie.features.picked import PickedElement
from freecad.menuiserie.features.shaped_create import (
    create_shaped_part,
    create_shaped_parts,
    reset_axes,
)
from freecad.menuiserie.features.shaped_part import is_shaped_part, is_timber
from freecad.menuiserie.features.shaped_part_schema import DEFAULT_PROFILE_THICKNESS
from freecad.menuiserie.features.wood_part import create_wood_part, validated_arguments

__all__ = [
    "FRENCH_CSV",
    "INTERNATIONAL_CSV",
    "CarcassJoinery",
    "CarcassParams",
    "LockedPiecesError",
    "PickedElement",
    "add_to_furniture",
    "blank_of",
    "cut_list_html",
    "cut_list_of",
    "export_cut_list_csv",
    "export_cut_list_pdf",
    "furniture_of",
    "is_machined_part",
    "is_shaped_part",
    "is_timber",
    "machined_part_of",
    "make_carcass",
    "make_cut_list",
    "make_dovetail",
    "make_dowels",
    "make_furniture",
    "make_half_lap",
    "make_miter",
    "make_mortise_tenon",
    "make_rabbet",
    "make_shaped_part",
    "make_shaped_parts",
    "make_tongue_groove",
    "make_wood_part",
    "number_marks",
    "rebind_furniture",
    "remove_from_furniture",
    "remove_machined_part",
    "reset_shaped_axes",
    "resize_furniture",
    "set_distance",
    "set_edge_distance",
    "set_member_options",
    "unlock_and_resize",
    "unlock_and_set_thickness",
]


# --- Pièce de bois (J1) -------------------------------------------------------------------


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


# --- Pièce en bois (PD-b) -----------------------------------------------------------------

_NOT_A_SHAPED_PART = QT_TRANSLATE_NOOP("Menuiserie", "« {label} » n'est pas une pièce en bois.")
_SHAPED_VIEW_PROVIDER = (
    "freecad.menuiserie.gui.view_providers.shaped_part",
    "ViewProviderShapedPart",
)


def make_shaped_part(
    source: DocumentObject,
    material: str | None = None,
    mark: str = "",
    *,
    profile_thickness: float = DEFAULT_PROFILE_THICKNESS,
) -> DocumentObject:
    """Crée la pièce en bois de ``source`` (ADR 0020) et recalcule le document.

    ``source`` : corps ``PartDesign::Body`` (forme de son ``Tip``), fonction PartDesign (ramenée à
    son corps), forme ``Part::Feature`` à un seul solide valide, ou esquisse plane et fermée
    (extrudée de ``profile_thickness`` mm le long de sa normale). ``material`` : identifiant du
    matériau (défaut : celui de la bibliothèque) ; ``mark`` : repère de la pièce.

    La pièce est rangée dans le conteneur de la source (``App::Part``, groupe), exactement à sa
    place ; la source n'est jamais modifiée, seulement masquée une fois liée. Une forme importée à
    plusieurs solides se convertit avec :func:`make_shaped_parts` (une pièce par solide). Refus
    traduits avant toute création : ``TypeError`` (objet de l'atelier, type non pris en charge),
    ``ValueError`` (forme vide ou invalide, plusieurs solides, esquisse ouverte, cote hors bornes,
    source déjà convertie), ``KeyError`` (matériau inconnu). Aucune transaction n'est ouverte :
    c'est à l'appelant de le faire pour pouvoir annuler.
    """
    part = create_shaped_part(
        source, material_id=material, mark=mark, profile_thickness=profile_thickness
    )
    _show_shaped([part])
    part.Document.recompute()
    return part


def make_shaped_parts(
    source: DocumentObject,
    material: str | None = None,
    mark: str = "",
    *,
    profile_thickness: float = DEFAULT_PROFILE_THICKNESS,
) -> list[DocumentObject]:
    """Crée une pièce en bois par solide de ``source`` et recalcule le document (B11).

    Pour une forme importée (type exactement ``Part::Feature``, sans dépendance : STEP, IGES,
    copie simple) à plusieurs solides : une pièce par solide, liée à la même source avec son rang
    (``SolidIndex``) et son empreinte (``SolidSignature``), dans la transaction de l'appelant.
    Pour toute autre source, une liste d'une pièce, comme :func:`make_shaped_part` (mêmes
    arguments, mêmes refus)."""
    parts = create_shaped_parts(
        source, material_id=material, mark=mark, profile_thickness=profile_thickness
    )
    _show_shaped(parts)
    source.Document.recompute()
    return parts


def reset_shaped_axes(part: DocumentObject) -> None:
    """Repère automatique de la pièce en bois ``part`` : recalcule ses axes d'après la forme
    actuelle de sa source (``SourceAxes``) sans que la pièce bouge, puis recalcule le document.

    C'est, avec les quarts de tour du repère, le seul moyen de changer ``SourceAxes`` : un
    recalcul ordinaire le garde. ``TypeError`` traduite si ``part`` n'est pas une pièce en bois.
    """
    if not is_shaped_part(part):
        raise TypeError(translated(_NOT_A_SHAPED_PART, {"label": str(part.Label)}))
    reset_axes(part)
    part.Document.recompute()


def _show_shaped(parts: Sequence[DocumentObject]) -> None:
    """Pose le ViewProvider des pièces en bois si l'interface est chargée. Le module du
    ViewProvider (PD-d) est cherché à l'exécution : tant qu'il n'existe pas, les pièces gardent
    la vue Part par défaut."""
    if not App.GuiUp:
        return
    module_name, class_name = _SHAPED_VIEW_PROVIDER
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name != module_name:
            raise
        return
    for part in parts:
        getattr(module, class_name)(part.ViewObject)


# --- Assemblages (J3, J4) -----------------------------------------------------------------


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


def make_half_lap(host: DocumentObject, guest: DocumentObject, **params: object) -> DocumentObject:
    """Relie à mi-bois deux pièces de même épaisseur, à fleur, qui se chevauchent (croix, T ou
    angle) et recalcule le document : ``host`` est entaillée par-dessus, ``guest`` par-dessous.

    Paramètres facultatifs : ``depth`` (profondeur de l'entaille de ``host`` en mm, 0 = moitié
    de l'épaisseur), ``flip_side`` (entaille de ``host`` par-dessous). Mêmes validations et même
    absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_half_lap, host, guest, params)


def make_dovetail(host: DocumentObject, guest: DocumentObject, **params: object) -> DocumentObject:
    """Relie à queue d'aronde traversante ``guest`` (pièce à queues, en contact par son bout,
    dessinée à sa longueur visible) et ``host`` (pièce à griffes, hors tout, son bout à fleur
    de la face extérieure de ``guest``), puis recalcule le document.

    Paramètres facultatifs, 0 = automatique : ``tail_count`` (nombre de queues),
    ``pin_width`` (largeur des griffes au plus étroit, en mm, le tiers de l'épaisseur de
    ``host``), ``angle`` (angle des flancs en degrés, 10° ; au plus 30°). Mêmes validations et
    même absence de transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_dovetail, host, guest, params)


def make_miter(host: DocumentObject, guest: DocumentObject, **params: object) -> DocumentObject:
    """Relie à onglet ``host`` et ``guest``, dessinées à leur longueur hors tout (de pointe
    longue à pointe longue) et qui se chevauchent au coin, puis recalcule le document. La coupe
    passe par le coin extérieur et le coin intérieur : 45° pour deux largeurs égales. Aucun
    paramètre en J4 (un nom inconnu lève ``TypeError``) ; mêmes validations et même absence de
    transaction que :func:`make_mortise_tenon`.
    """
    return _make_joint(create_miter, host, guest, params)


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


# --- Ensembles (J4) -----------------------------------------------------------------------


_Notices = tuple[str, ...]


def _reported(notices: Sequence[Notice], doc: Document) -> _Notices:
    """Avertissements traduits, écrits dans la vue rapport, puis document recalculé."""
    messages = notice_messages(notices)
    report(messages)
    doc.recompute()
    return messages


def make_furniture(
    objects: Sequence[DocumentObject], label: str = ""
) -> tuple[DocumentObject, _Notices]:
    """Crée un ensemble (« Ensemble » par défaut) autour de ``objects`` (pièces de bois, pièces
    usinées ou ensembles), le relie à eux par des expressions et recalcule le document.

    Cotes et ``Origin`` = boîte qui contient les membres ; options « fixe » par défaut (toute
    distance fixe, Q7). Renvoie l'ensemble et les avertissements traduits (aussi dans la vue
    rapport). Refus avant toute création (``TypeError`` ou ``ValueError`` traduites). Aucune
    transaction n'est ouverte : c'est à l'appelant de le faire pour pouvoir annuler.
    """
    furniture, notices = furniture_members.build_furniture(objects, label)
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.furniture import ViewProviderFurniture

        ViewProviderFurniture(furniture.ViewObject)
    return furniture, _reported(notices, furniture.Document)


def add_to_furniture(furniture: DocumentObject, objects: Sequence[DocumentObject]) -> _Notices:
    """Fait entrer ``objects`` dans ``furniture`` (options par défaut, liaisons d'après la
    géométrie actuelle) sans toucher aux membres présents, puis recalcule. Mêmes refus et même
    absence de transaction que :func:`make_furniture`."""
    notices = furniture_members.add_members(furniture, objects)
    return _reported(notices, furniture.Document)


def remove_from_furniture(objects: Sequence[DocumentObject]) -> _Notices:
    """Retire ``objects`` de leur ensemble : seules les liaisons de l'atelier et les propriétés
    de membre sont supprimées, la géométrie ne change pas. ``ValueError`` traduite, avant toute
    modification, pour un objet qui n'est membre d'aucun ensemble. Renvoie les avertissements
    traduits, comme toute fonction de l'ensemble (ADR 0017) : aucun aujourd'hui."""
    furniture_members.remove_members(objects)
    if objects:
        objects[0].Document.recompute()
    return ()


def set_member_options(
    obj: DocumentObject,
    *,
    mode: str | None = None,
    fixed: Mapping[str, bool] | None = None,
    locked: bool | None = None,
) -> _Notices:
    """Change le mode (``Stay``, ``Proportional``), les options « fixe » (``fixed={"Back":
    False}``) et le verrou « cotes fixes » (``locked``) d'un membre, relie **tout** l'ensemble
    (un réglage peut changer la rangée des autres pièces) et recalcule."""
    notices = furniture_members.set_options(obj, mode, fixed, locked)
    return _reported(notices, obj.Document)


def set_edge_distance(obj: DocumentObject, edge: str, distance: float) -> _Notices:
    """Règle à ``distance`` mm l'écart entre une face d'un membre et le bord ``edge``
    (``Left``, ``Right``, ``Front``, ``Back``, ``Bottom``, ``Top``) de son ensemble : la pièce
    est déplacée, ou sa cote change si la distance opposée est fixe. Options inchangées ; ce
    ensemble est relié, puis le document recalculé. Refus avant modification (face pilotée
    par une formule, pièce qui n'est pas d'équerre, cote hors bornes)."""
    notices = furniture_edges.set_edge_distance(obj, edge, distance)
    return _reported(notices, obj.Document)


def rebind_furniture(furniture: DocumentObject) -> _Notices:
    """« Relier les pièces » : recalcule toutes les liaisons de l'atelier (sous-ensembles
    compris) d'après la géométrie actuelle et les options enregistrées, puis recalcule."""
    notices = furniture_members.relink(furniture)
    return _reported(notices, furniture.Document)


def resize_furniture(
    furniture: DocumentObject,
    *,
    width: float | None = None,
    depth: float | None = None,
    height: float | None = None,
) -> _Notices:
    """Change les cotes de l'ensemble (mm, ``None`` = inchangée) puis recalcule ; refusé
    d'avance (``ValueError`` traduite, rien n'est modifié) si une pièce deviendrait trop petite
    ou trop grande ou si un assemblage perdrait sa position. Une rangée bloquée par des pièces
    verrouillées lève :class:`LockedPiecesError` (``members`` : ces pièces ;
    :func:`unlock_and_resize` les déverrouille). Renvoie les avertissements traduits (aussi
    dans la vue rapport, ADR 0017)."""
    sizes = {"Width": width, "Depth": depth, "Height": height}
    notices = furniture_members.resize(furniture, sizes)
    return _reported(notices, furniture.Document)


def unlock_and_resize(
    furniture: DocumentObject,
    pieces: Sequence[DocumentObject],
    *,
    width: float | None = None,
    depth: float | None = None,
    height: float | None = None,
) -> _Notices:
    """Déverrouille ``pieces`` (celles de ``LockedPiecesError.members``), relie tout l'ensemble
    puis change ses cotes, comme :func:`resize_furniture`. Contrôlé d'abord pièces
    déverrouillées : si la cote reste refusée, rien n'est modifié. Aucune transaction n'est
    ouverte : l'appelant en ouvre une pour que le tout s'annule d'un coup."""
    sizes = {"Width": width, "Depth": depth, "Height": height}
    notices = furniture_locks.unlock_and_resize(furniture, pieces, sizes)
    return _reported(notices, furniture.Document)


def unlock_and_set_thickness(
    part: DocumentObject, thickness: float, pieces: Sequence[DocumentObject]
) -> _Notices:
    """Déverrouille ``pieces``, relie tout l'ensemble de la pièce ``part`` puis fixe son
    épaisseur (mm). Mêmes contrôle préalable et absence de transaction que
    :func:`unlock_and_resize`."""
    notices = furniture_locks.unlock_and_set_thickness(part, thickness, pieces)
    return _reported(notices, part.Document)


def furniture_of(obj: DocumentObject) -> DocumentObject | None:
    """Ensemble dont ``obj`` (pièce de bois, pièce usinée ou ensemble) est membre, ``None``
    sinon."""
    try:
        member = furniture_members.member_object(obj)
    except TypeError:
        return None
    return _member_furniture(member)


# --- Distance entre deux pièces (DI-b) ---------------------------------------------------


def _show_distance(distance: DocumentObject) -> None:
    """ViewProvider de la Distance créée, quand l'interface est chargée."""
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.distance import ViewProviderDistance

        ViewProviderDistance(distance.ViewObject)


def set_distance(
    first: PickedElement,
    second: PickedElement,
    value: float,
    *,
    moving: PickedElement | None = None,
    axis: str | None = None,
    keep: bool = False,
) -> _Notices:
    """Amène à ``value`` mm la distance entre deux éléments (face, arête, sommet) de deux objets
    en déplaçant **une pièce de l'atelier** une fois, puis recalcule le document.

    ``first`` et ``second`` : :class:`PickedElement` (objet racine, chemin de l'élément
    ``"Face3"``). Pièce déplacée : ``moving`` (l'un des deux éléments), sinon celle du second
    élément si elle est à l'atelier, sinon celle du premier ; une pièce usinée ou un assemblage
    déplace sa brute, un objet d'un autre atelier ne bouge jamais. ``axis`` (``"X"``, ``"Y"``,
    ``"Z"`` du conteneur) mesure deux sommets sur cet axe seul ; il est ignoré pour les autres
    paires. Membre d'un ensemble : l'ensemble est relié ensuite. ``keep`` : la distance est
    **gardée** par un objet ``Distance`` (DI-c, ADR 0022) ; il faut que les deux pièces soient
    membres du même ensemble, que la direction soit parallèle à un axe de l'ensemble, que chaque
    élément soit sur une face de sa pièce et que la valeur ne soit pas nulle. Refus avant toute
    modification (``ValueError`` traduite) : aucune pièce de l'atelier, éléments non parallèles,
    arête courbe, axe piloté par une formule, rangée bloquée, distance impossible à garder.
    Renvoie les avertissements traduits (aussi dans la vue rapport). Aucune transaction n'est
    ouverte : c'est à l'appelant de le faire pour pouvoir annuler."""
    mover = distance_move.DistanceMove(first, second, moving)
    messages = tuple(mover.apply(value, axis, keep=keep))
    if mover.created is not None:
        _show_distance(mover.created)
    report(messages)
    return messages


# --- Gabarits (J4) ------------------------------------------------------------------------


_CARCASS_ARGUMENTS = QT_TRANSLATE_NOOP(
    "Menuiserie", "make_carcass : params ou champs en mots-clés, pas les deux"
)


def make_carcass(
    doc: Document | None = None,
    params: CarcassParams | None = None,
    *,
    furniture: DocumentObject | None = None,
    **values: Any,
) -> tuple[DocumentObject, _Notices]:
    """Crée un caisson par le gabarit « Caisson » (ADR 0010) et recalcule le document une fois :
    côtés, dessus, dessous, fond en feuillure, étagères, tourillons, et un ensemble « Caisson »
    (``Template`` = ``Carcass``) dont les pièces suivent les cotes. Rien d'autre n'est gardé :
    le caisson se modifie ensuite comme tout ensemble.

    Paramètres : ``params`` (:class:`CarcassParams`) ou ses champs en mots-clés
    (``width=800, shelf_count=2``…, mm). ``furniture`` : ensemble dont le caisson devient un
    sous-ensemble (options par défaut vis-à-vis de lui). ``doc`` vaut par défaut le document
    actif, ou un nouveau document. Renvoie l'ensemble et les avertissements traduits. Refus
    avant toute création (``TypeError`` ou ``ValueError`` traduites). Aucune transaction n'est
    ouverte : c'est à l'appelant de le faire pour pouvoir annuler.
    """
    if params is not None and values:
        raise TypeError(translated(_CARCASS_ARGUMENTS))
    with translated_errors():
        chosen = params if params is not None else CarcassParams(**values)
    document = doc if doc is not None else App.ActiveDocument or App.newDocument()
    built = templates.build_carcass(document, chosen, furniture)
    if App.GuiUp:  # ViewProviders des pièces, des pièces usinées, des assemblages, de l'ensemble
        from freecad.menuiserie.gui.view_providers.furniture import ViewProviderFurniture
        from freecad.menuiserie.gui.view_providers.joint import ViewProviderJoint
        from freecad.menuiserie.gui.view_providers.machined_part import ViewProviderMachinedPart
        from freecad.menuiserie.gui.view_providers.wood_part import ViewProviderWoodPart

        for group, provider in (
            (built.parts, ViewProviderWoodPart),
            (built.machined, ViewProviderMachinedPart),
            (built.joints, ViewProviderJoint),
            ((built.furniture,), ViewProviderFurniture),
        ):
            for obj in group:
                provider(obj.ViewObject)
    return built.furniture, _reported(built.notices, document)


# --- Liste de débit (J2) ------------------------------------------------------------------


def cut_list_of(doc: Document, objects: Sequence[DocumentObject] | None = None) -> CutList:
    """Liste de débit (:class:`~freecad.menuiserie.core.cutlist.CutList`) du document ``doc`` ou,
    si ``objects`` est donné et non vide, de ces objets : pièces de bois ou usinées, ensembles,
    Std Part, groupes et liens (une pièce vue par un lien compte une fois de plus, fois
    ``ElementCount``). Longueurs de débit tenons compris, tourillons en fournitures. Lecture
    seule : le document n'est pas modifié. ``ValueError`` traduite pour un objet d'un autre
    document."""
    return cutlist_collect.cut_list_of(doc, objects)


def make_cut_list(doc: Document, objects: Sequence[DocumentObject] | None = None) -> DocumentObject:
    """Crée ou met à jour la liste de débit **vivante** de ``doc`` et renvoie sa feuille de
    calcul « Liste de débit » (nom interne ``MenuiserieCutList``, retrouvée par sa marque même
    renommée). Deux objets : la feuille, ``Spreadsheet::Sheet`` ordinaire, et l'objet
    ``Menuiserie::CutList`` qui la réécrit à chaque recalcul du document (cote modifiée, pièce
    ajoutée ou supprimée) ; relancer cette fonction les retrouve, change la portée (``objects``,
    sinon tout le document) et réécrit tout de suite. Colonnes A à O réécrites, celles de P et
    au-delà conservées ; avertissements en bas de la feuille et dans la vue rapport. Une seule
    transaction « Liste de débit » (Annuler restaure la feuille). Supprimer l'objet ou la feuille
    arrête la mise à jour ; un nouvel appel la rétablit."""
    sheet, messages = cutlist_object.ensure_cut_list(doc, objects)
    _shown_cut_list(doc)
    report(messages)
    return sheet


def _shown_cut_list(doc: Document) -> None:
    """Pose le ViewProvider de la liste vivante (si l'interface est chargée et qu'il manque)."""
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.cutlist import ViewProviderCutList

        cut_list = cutlist_object.find_cut_list(doc)
        if cut_list is not None and not isinstance(cut_list.ViewObject.Proxy, ViewProviderCutList):
            ViewProviderCutList(cut_list.ViewObject)


def number_marks(
    doc: Document,
    objects: Sequence[DocumentObject] | None = None,
    prefix: str = "M",
) -> dict[str, str]:
    """Numérote les pièces sans repère de ``doc`` (ou de ``objects``) : un repère ``<prefix><n>``
    par groupe de pièces identiques (mêmes cotes, matériau, fil, surcotes et ajouts), au premier
    numéro libre, ensemble puis cotes décroissantes. Les pièces qui ont déjà un repère ne
    changent pas ; le libellé suit le repère. Renvoie le repère écrit pour chaque pièce (nom
    interne → repère). Une seule transaction « Numéroter les repères », document recalculé (la
    liste de débit vivante suit). ``ValueError`` traduite pour un préfixe vide ou un objet d'un
    autre document."""
    return cutlist_marks.number_marks(doc, objects, prefix)


def export_cut_list_csv(
    doc: Document,
    path: str | os.PathLike[str],
    objects: Sequence[DocumentObject] | None = None,
    dialect: CsvDialect = INTERNATIONAL_CSV,
) -> Path:
    """Exporte la liste de débit de ``doc`` (ou de ``objects``) en CSV dans ``path`` et renvoie le
    chemin. Dialecte par défaut ``INTERNATIONAL_CSV`` (``,``, point décimal, UTF-8 avec BOM, CRLF) ;
    ``FRENCH_CSV`` (``;``, virgule décimale) est disponible. ``ValueError`` traduite, avant
    toute écriture, si le chemin n'a pas l'extension ``.csv``, désigne un dossier, est dans un
    dossier absent ou non accessible en écriture. Écriture atomique ; le document n'est pas
    modifié."""
    target = cutlist_export.validated_path(path)
    cut_list = cut_list_of(doc, objects)
    written = cutlist_export.export_csv(cut_list, target, dialect)
    report(notice_messages(cut_list.warnings))
    return written


_PDF_NEEDS_GUI = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export PDF impossible : il demande l'interface de FreeCAD."
)


def export_cut_list_pdf(
    doc: Document,
    path: str | os.PathLike[str],
    objects: Sequence[DocumentObject] | None = None,
) -> Path:
    """Exporte la liste de débit de ``doc`` (ou de ``objects``) en PDF (A4 paysage, marges 10 mm)
    dans ``path`` et renvoie le chemin. **Demande l'interface de FreeCAD** (Qt dessine les
    polices) : sans elle, ``ValueError`` traduite. Mêmes refus que le CSV avec l'extension
    ``.pdf`` imposée, avant toute écriture ; écriture atomique ; le document n'est pas
    modifié."""
    target = cutlist_export.validated_path(path, cutlist_export.PDF_SUFFIX)
    if App.GuiUp:
        from freecad.menuiserie.gui import cutlist_pdf

        cut_list, html = _cut_list_and_html(doc, objects)
        written = cutlist_pdf.write_pdf(html, target)
        report(notice_messages(cut_list.warnings))
        return written
    raise ValueError(translated(_PDF_NEEDS_GUI))


def _cut_list_and_html(
    doc: Document, objects: Sequence[DocumentObject] | None
) -> tuple[CutList, str]:
    """Liste de débit et son HTML avec miniatures (celui du PDF et de l'aperçu)."""
    cut_list = cut_list_of(doc, objects)
    html = cutlist_export.pdf_html(
        cut_list,
        doc.Label,
        len(objects) if objects else None,
        thumbnails=cutlist_thumbnail.thumbnails_of(doc, cut_list),
    )
    return cut_list, html


def cut_list_html(doc: Document, objects: Sequence[DocumentObject] | None = None) -> str:
    """Document HTML autonome de la liste de débit de ``doc`` (ou de ``objects``), tel que
    l'aperçu l'affiche et que le PDF l'imprime : tableau, totaux, fournitures, avertissements
    et, en tête de chaque ligne, la miniature isométrique de la forme **usinée** de la première
    pièce du groupe (boîte de débit si elle n'est pas utilisable). Images incluses en ``data:``
    (SVG), aucune ressource externe. Lecture seule, sans interface ; ``ValueError`` traduite
    pour un objet d'un autre document."""
    return _cut_list_and_html(doc, objects)[1]
