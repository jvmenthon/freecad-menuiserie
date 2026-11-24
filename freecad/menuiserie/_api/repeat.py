# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition de pièces de la façade publique (R-b1, ADR 0043).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie._api.joints import show_joint
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import RepeatParams
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import (
    repeat,
    repeat_copies,
    repeat_joints,
    repeat_links,
    repeat_stop,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import report
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.repeat_stop_raw import raw_stops
from freecad.menuiserie.features.shaped_part import is_shaped_part

__all__ = ["dissociate", "edit_repeat", "make_repeat", "repeat_of"]

_MAKE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répéter")
_EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier la répétition")
_DISSOCIATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Dissocier la répétition")
_STILL_CITED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est dissociée et supprimée, mais d'autres objets la citaient (formule, lien) : "
    "{others}. Ces liens sont rompus ; corrigez-les ou annulez (Ctrl+Z).",
)
_MAX_NAMED: Final = 5
_NOT_A_REPEAT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est ni une répétition ni une copie liée à une répétition."
)


@contextmanager
def _undoable(doc: Document, title: str, *, own: bool) -> Iterator[None]:
    """Un seul bloc annulable et un seul recalcul. ``own`` : la transaction est ouverte ici,
    validée après le recalcul, ou abandonnée si une erreur survient (rien ne reste à moitié
    écrit) ; sinon elle est celle de l'appelant, qui la valide (FreeCAD ne permet pas de savoir
    si une transaction encore vide est ouverte)."""
    if own:
        doc.openTransaction(translated(title))
    try:
        yield
        doc.recompute()
    except BaseException:
        if own:
            doc.abortTransaction()
        raise
    if own:
        doc.commitTransaction()


def _show(created: repeat_copies.Created) -> None:
    """ViewProviders des copies et des assemblages créés, quand l'interface est chargée."""
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.furniture import ViewProviderFurniture
        from freecad.menuiserie.gui.view_providers.shaped_part import ViewProviderShapedPart
        from freecad.menuiserie.gui.view_providers.wood_part import ViewProviderWoodPart

        for copy in created.copies:
            if is_furniture(copy):
                provider: Any = ViewProviderFurniture
            elif is_shaped_part(copy):
                provider = ViewProviderShapedPart
            else:
                provider = ViewProviderWoodPart
            provider(copy.ViewObject)
    for joint in created.joints:
        show_joint(joint)
    report(created.notices)


def make_repeat(
    objects: Sequence[DocumentObject],
    params: RepeatParams,
    *,
    transaction: bool = True,
    stops: repeat_stop.Stops | None = None,
) -> DocumentObject:
    """Répète les pièces de bois, les pièces en bois et les ensembles ``objects`` selon ``params``
    (:class:`RepeatParams`, mm) et renvoie la répétition (objet de cotes sans forme, nom interne
    ``Repeat``).

    Chaque source reçoit ``Count`` copies, au même pas, qui sont de vraies pièces de bois
    liées à la source par expressions natives : cotes, matériau, sens du fil et surcotes sont
    ceux de la source, le placement suit la source plus ``k`` pas sur l'axe. Modifier la source
    ou ``Step`` déplace ou redimensionne donc les copies au recalcul. Libellé d'une copie :
    « {libellé de la source} {k+1} ».

    Source membre d'un ensemble : ses copies le sont aussi, avec les mêmes options (mode,
    « fixe », verrou) ; une copie liée suit sa source et ne reçoit pas les liaisons de
    l'ensemble, mais compte comme membre pour ses voisines. ``params.follow_resize`` : le pas
    suit la cote de l'ensemble (``ValueError`` traduite si une source n'est dans aucun ensemble).

    Source = ensemble (ou sous-ensemble) : chaque copie est un nouvel ensemble, sous-ensemble du
    même parent s'il y en a un, dont ``Width``, ``Depth``, ``Height`` et ``Origin`` suivent la
    source, avec une copie de chaque membre (récursivement) rangée dedans avec ses options. Les
    cotes d'un membre que l'ensemble de la source pilote viennent des liaisons de l'ensemble
    copie, les autres suivent le membre source. Assemblages internes (cas A) et vers une pièce
    extérieure (cas B) recopiés selon ``copy_joints``. Une sélection peut mêler pièces et
    ensembles ; une pièce n'est pas répétée en même temps que son ensemble.

    Source = pièce en bois à forme libre (ADR 0050) : la copie est une pièce en bois qui lie le même
    corps ; repère, épaisseur de profil, matériau, fil et surcotes suivent la source par expression,
    les cotes d'encombrement sont recalculées depuis le corps (jamais liées).

    ``stops`` (ADR 0047) : butée (:class:`Stop`) de chaque axe ; dans les modes « sur une
    longueur », la longueur de l'axe est alors la distance à la butée (``AxisRepeat.span`` ou
    ``RepeatParams.span`` : une valeur positive de départ, remplacée), et elle **suit** la butée.

    Un seul bloc annulable, un seul recalcul. Refus traduits avant toute création : ``TypeError``
    (autre chose qu'une pièce de bois, une pièce en bois ou un ensemble de telles pièces),
    ``ValueError`` (aucune pièce, copie déjà liée, pièce répétée avec son ensemble, longueur trop
    courte, trop de copies…), ``KeyError`` (matériau inconnu). ``transaction=False`` : l'appelant
    a ouvert la sienne (commande de l'interface) et la valide ; sinon elle est ouverte et validée
    ici."""
    sources = repeat_copies.checked_sources(objects, one_container=False)
    stops = raw_stops(stops) or {}  # jamais une pièce usinée : cycle avec les assemblages
    params = repeat_stop.bounded_params(sources, params, stops)
    repeat_copies.resolve_for(sources, params)
    container = repeat_copies.common_container(sources)
    doc = sources[0].Document
    with _undoable(doc, _MAKE_TRANSACTION, own=transaction):
        obj = repeat.create_repeat(doc, sources, container)
        _show_repeat(obj)
        _show(repeat_copies.apply_repeat(obj, params, stops))
    return obj


def _show_repeat(obj: DocumentObject) -> None:
    """ViewProvider de la répétition (icône, double-clic), quand l'interface est chargée."""
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.repeat import ensure_view_provider

        ensure_view_provider(obj)


def _checked_repeat(obj: DocumentObject) -> DocumentObject:
    found = repeat.repeat_of(obj)
    if found is None:
        raise TypeError(translated(_NOT_A_REPEAT, {"label": quoted_value(obj.Label)}))
    return found


def edit_repeat(
    obj: DocumentObject,
    params: RepeatParams,
    *,
    transaction: bool = True,
    stops: repeat_stop.Stops | None = None,
) -> None:
    """Change le réglage de la répétition ``obj`` (ou d'une de ses copies) : ajoute les copies qui
    manquent (rangs à la suite de l'ancien nombre), supprime les dernières si le nombre baisse
    (avec leur pièce usinée et leurs assemblages), réécrit le pas et les expressions, bascule
    ``FollowResize`` (le pas devient, ou cesse d'être, une expression sur la cote de l'ensemble).
    Même transaction (``transaction``), même recalcul et mêmes refus que :func:`make_repeat` ;
    rien n'est modifié si le réglage est refusé. ``stops`` : butées de chaque axe (voir
    :func:`make_repeat`) ; ``None`` garde celles de la répétition (retirées si le mode n'a plus de
    longueur), un dictionnaire vide les retire. ``transaction`` vrai : après le recalcul, les
    assemblages posés à la main sur une copie devenus impossibles sont signalés dans la vue rapport
    (le panneau, lui, les affiche sous le réglage)."""
    found = _checked_repeat(obj)
    sources = repeat.sources_of(found)
    kept = repeat_stop.kept_stops(found, params, raw_stops(stops))
    params = repeat_stop.bounded_params(sources, params, kept, found)
    repeat_copies.resolve_for(sources, params)
    with _undoable(found.Document, _EDIT_TRANSACTION, own=transaction):
        _show(repeat_copies.apply_repeat(found, params, kept))
    if transaction:  # le panneau, lui, l'affiche sous le réglage
        report(filter(None, [repeat_joints.hand_joints_warning(found)]))  # après le recalcul


def dissociate(obj: DocumentObject, *, transaction: bool = True) -> None:
    """Dissocie la répétition de ``obj`` (la répétition elle-même ou l'une de ses copies liées,
    demande de jv du 2026-11-23) : toutes ses copies perdent leurs expressions et leurs
    propriétés ``Repeat``, ``RepeatSource`` et ``RepeatIndex``, gardent leurs valeurs actuelles
    et deviennent des pièces (ou des ensembles) libres, reliées à leur ensemble par les liaisons
    normales, avec leurs assemblages ; puis la répétition est supprimée. Les pièces d'origine ne
    changent pas. ``TypeError`` traduite si ``obj`` n'est ni une répétition ni une copie liée.
    Un bloc annulable, un recalcul (``transaction`` : voir :func:`make_repeat`)."""
    found = repeat.repeat_of(obj)
    if found is None:
        raise TypeError(translated(_NOT_A_REPEAT, {"label": quoted_value(obj.Label)}))
    doc = found.Document
    with _undoable(doc, _DISSOCIATE_TRANSACTION, own=transaction):
        doc.recompute()  # les valeurs gardées sont celles des sources à jour
        freed = [c for c in repeat.copies_of(found) if not repeat.is_inner_copy(c)]
        parents = {}
        for copy in freed:  # toutes d'abord : relier au fil de l'eau citerait une copie libre
            parents[copy.Name] = furniture_of(copy)  # depuis une copie encore liée (cycle)
            repeat_links.unlink_copy(copy, relink=False)  # un ensemble emporte ses membres
        for copy in freed:
            repeat_links.relink_free(copy, parents[copy.Name])
        _warn_still_cited(found)
        doc.removeObject(found.Name)  # plus aucune copie liée : rien n'est supprimé avec elle


def _warn_still_cited(rep: DocumentObject) -> None:
    """Avertit si d'autres objets que le conteneur de ``rep`` la citent encore (formule d'un
    tableur, lien d'un autre atelier) : sa suppression romprait leurs liens sans le dire. Ces
    objets ne sont jamais modifiés."""
    others = {obj.Name: obj for obj in rep.InList if rep not in (getattr(obj, "Group", None) or ())}
    if not others:
        return
    labels = [f"« {quoted_value(obj.Label)} »" for obj in others.values()]
    shown = labels[:_MAX_NAMED] + (["…"] if len(labels) > _MAX_NAMED else [])
    report(
        [translated(_STILL_CITED, {"label": quoted_value(rep.Label), "others": ", ".join(shown)})]
    )


def repeat_of(obj: DocumentObject) -> DocumentObject | None:
    """Répétition de ``obj`` : lui-même si c'est une répétition, celle dont c'est une copie liée,
    sinon ``None``."""
    return repeat.repeat_of(obj)
