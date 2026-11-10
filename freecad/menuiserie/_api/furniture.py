# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensembles, Distance et gabarit « Caisson » de la façade publique (J4, DI-b).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import FreeCAD as App

from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.structure_rename import cleaned_name, decide_rename
from freecad.menuiserie.core.templates.carcass import CarcassParams
from freecad.menuiserie.features import (
    distance_move,
    furniture_drag,
    furniture_edges,
    furniture_locks,
    furniture_material,
    furniture_members,
    furniture_resize,
    templates,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import furniture_of as _member_furniture
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import notice_messages, report
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.picked import PickedElement

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
    """Crée un ensemble (« Ensemble » par défaut) autour de ``objects`` (pièces de bois, pièces en
    bois, pièces usinées ou ensembles), le relie à eux par des expressions et recalcule le
    document. Une pièce en bois suit l'ensemble par son ``Placement`` seulement : ses cotes
    viennent du dessin, toujours fixes (ADR 0020), et une règle qui voudrait l'étirer la déplace
    en avertissant « cote dessinée : modifiez le dessin ».

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


def add_to_furniture(
    furniture: DocumentObject, objects: Sequence[DocumentObject], *, move: bool = False
) -> _Notices:
    """Fait entrer ``objects`` dans ``furniture`` (options par défaut, liaisons d'après la
    géométrie actuelle) sans toucher aux membres présents, puis recalcule. Mêmes refus et même
    absence de transaction que :func:`make_furniture`. Avec ``move``, des objets déjà membres
    d'un autre ensemble en sortent pour entrer ici (leurs propriétés de membre sont gardées, ce
    qui s'annule d'un Ctrl+Z)."""
    notices = furniture_members.add_members(furniture, objects, move=move)
    return _reported(notices, furniture.Document)


def remove_from_furniture(
    objects: Sequence[DocumentObject], *, keep_properties: bool = False
) -> _Notices:
    """Retire ``objects`` de leur ensemble : seules les liaisons de l'atelier et les propriétés
    de membre sont supprimées, la géométrie ne change pas. ``ValueError`` traduite, avant toute
    modification, pour un objet qui n'est membre d'aucun ensemble. Renvoie les avertissements
    traduits, aussi écrits dans la vue rapport (ADR 0017) : une pièce assemblée à une pièce qui
    reste dans l'ensemble reste dans son Std Part (elle n'est plus membre). Avec
    ``keep_properties``, les propriétés de membre restent sur la pièce (état d'orphelin) : seuls
    le lien et les liaisons sont retirés, ce qui s'annule d'un Ctrl+Z (FreeCAD 1.1 ne rétablit pas
    une propriété dynamique retirée puis recréée dans la même transaction)."""
    messages = tuple(furniture_members.remove_members(objects, keep_properties=keep_properties))
    report(messages)
    if objects:
        objects[0].Document.recompute()
    return messages


def rename(obj: DocumentObject, name: str) -> str:
    """Renomme une pièce de bois, une pièce en bois ou un ensemble ; pour une pièce usinée, c'est
    le libellé de sa brute qui change (celui que montre le panneau « Structure »). ``name`` est
    débarrassé des espaces qui l'entourent. ``TypeError`` ou ``ValueError`` traduite, avant toute
    modification, pour un autre objet, un nom vide, trop long, avec un caractère de contrôle ou
    (ensemble) inutilisable dans une expression. Un nom inchangé ne fait rien. Renvoie le
    libellé de l'objet renommé. Aucune transaction n'est ouverte : c'est à l'appelant de le
    faire pour pouvoir annuler."""
    target = furniture_members.member_object(obj)
    old = str(target.Label)
    decision = decide_rename(old, name, furniture=is_furniture(target))
    if not decision.allowed:
        if decision.silent:
            return old
        raise ValueError(translated(decision.template, decision.params))
    target.Label = cleaned_name(name)
    target.Document.recompute()
    return str(target.Label)


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


def set_furniture_material(furniture: DocumentObject, material_id: str) -> _Notices:
    """Donne le matériau ``material_id`` à toutes les pièces de ``furniture``, sous-ensembles
    compris, et recalcule. Une pièce dont le matériau suit une expression, ou qui vient d'un
    document plus récent, est laissée telle quelle avec un avertissement (renvoyé et écrit dans la
    vue rapport). ``TypeError`` traduite si ``furniture`` n'est pas un ensemble,
    ``UnknownMaterialError`` si le matériau est inconnu : rien n'est écrit. Aucune transaction."""
    messages = furniture_material.set_furniture_material(furniture, material_id)
    report(messages)
    furniture.Document.recompute()
    return messages


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
    notices = furniture_resize.resize(furniture, sizes)
    return _reported(notices, furniture.Document)


def move_furniture(furniture: DocumentObject, delta: tuple[float, float, float]) -> bool:
    """Déplace l'ensemble de ``delta`` (dx, dy, dz en mm, repère de son Std Part) en écrivant le
    ``Placement`` de son Std Part, comme les flèches de la vue 3D, puis recalcule. Faux, sans
    rien écrire, si l'ensemble n'a pas de Std Part propre (ancien document) ou si une expression
    pilote ce ``Placement``. Un sous-ensemble est relié à son parent (ADR 0019). Aucune
    transaction n'est ouverte."""
    memento = furniture_drag.begin_furniture_drag(furniture)
    if not furniture_drag.move_furniture_by(memento, Vec3(*delta)):
        furniture_drag.restore(memento)
        return False
    report(furniture_drag.end_furniture_drag(memento))
    return True


def rotate_furniture(furniture: DocumentObject, angles: tuple[float, float, float]) -> bool:
    """Donne à l'ensemble l'orientation ``angles`` (X, Y, Z du ``Placement`` de son Std Part,
    degrés, de -360 à 360) autour du centre de sa boîte, pièces et liaisons comprises, puis
    recalcule. Faux, sans rien écrire, si l'ensemble n'a pas de Std Part propre ou si une
    expression pilote ce ``Placement`` (un sous-ensemble relié à son parent se tourne à la
    souris). ``ValueError`` traduite si un angle est invalide. Aucune transaction."""
    turned = furniture_drag.rotate_furniture_to(furniture, angles)
    if turned:
        furniture.Document.recompute()
    return turned


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
