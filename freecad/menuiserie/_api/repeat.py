# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition de pièces de la façade publique (R-b1, ADR 0043).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Final

import FreeCAD as App

from freecad.menuiserie._api.joints import show_joint
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import RepeatParams
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import repeat, repeat_copies, repeat_links
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import report
from freecad.menuiserie.features.i18n import translated

__all__ = ["dissociate", "edit_repeat", "make_repeat", "repeat_of"]

_MAKE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répéter")
_EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier la répétition")
_DISSOCIATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Dissocier la copie")
_NOT_A_REPEAT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est ni une répétition ni une copie liée à une répétition."
)
_NOT_A_COPY: Final = QT_TRANSLATE_NOOP("Menuiserie", "« {label} » n'est pas une copie liée.")


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
        from freecad.menuiserie.gui.view_providers.wood_part import ViewProviderWoodPart

        for copy in created.copies:
            provider = ViewProviderFurniture if is_furniture(copy) else ViewProviderWoodPart
            provider(copy.ViewObject)
    for joint in created.joints:
        show_joint(joint)
    report(created.notices)


def make_repeat(
    objects: Sequence[DocumentObject], params: RepeatParams, *, transaction: bool = True
) -> DocumentObject:
    """Répète les pièces de bois et les ensembles ``objects`` selon ``params``
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

    Un seul bloc annulable, un seul recalcul. Refus traduits avant toute création : ``TypeError``
    (autre chose qu'une pièce de bois ou un ensemble de pièces de bois), ``ValueError`` (aucune
    pièce, copie déjà liée, pièce répétée avec son ensemble, longueur trop courte, trop de
    copies…), ``KeyError`` (matériau inconnu). ``transaction=False`` : l'appelant a ouvert la
    sienne (commande de l'interface) et la valide ; sinon elle est ouverte et validée ici."""
    sources = repeat_copies.checked_sources(objects, one_container=False)
    repeat_copies.resolve_for(sources, params)
    container = repeat_copies.common_container(sources)
    doc = sources[0].Document
    with _undoable(doc, _MAKE_TRANSACTION, own=transaction):
        obj = repeat.create_repeat(doc, sources, container)
        _show_repeat(obj)
        _show(repeat_copies.apply_repeat(obj, params))
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


def edit_repeat(obj: DocumentObject, params: RepeatParams, *, transaction: bool = True) -> None:
    """Change le réglage de la répétition ``obj`` (ou d'une de ses copies) : ajoute les copies qui
    manquent (rangs à la suite de l'ancien nombre), supprime les dernières si le nombre baisse
    (avec leur pièce usinée et leurs assemblages), réécrit le pas et les expressions, bascule
    ``FollowResize`` (le pas devient, ou cesse d'être, une expression sur la cote de l'ensemble).
    Même transaction (``transaction``), même recalcul et mêmes refus que :func:`make_repeat` ;
    rien n'est modifié si le réglage est refusé."""
    found = _checked_repeat(obj)
    repeat_copies.resolve_for(repeat.sources_of(found), params)
    with _undoable(found.Document, _EDIT_TRANSACTION, own=transaction):
        _show(repeat_copies.apply_repeat(found, params))


def dissociate(copy: DocumentObject, *, transaction: bool = True) -> None:
    """Dissocie la copie ``copy`` : ses expressions et ses propriétés ``Repeat``, ``RepeatSource``
    et ``RepeatIndex`` sont retirées, la pièce garde ses valeurs actuelles et devient libre,
    reliée à son ensemble par les liaisons normales. Une copie d'ensemble est dissociée avec tous
    ses membres copiés. La répétition garde les autres copies et son nombre (les rangs ne bougent
    pas). ``TypeError`` traduite si ``copy`` n'est pas une copie liée. Un bloc annulable, un
    recalcul (``transaction`` : voir :func:`make_repeat`)."""
    if not repeat.is_copy(copy):
        raise TypeError(translated(_NOT_A_COPY, {"label": quoted_value(copy.Label)}))
    with _undoable(copy.Document, _DISSOCIATE_TRANSACTION, own=transaction):
        copy.Document.recompute()  # les valeurs gardées sont celles de la source à jour
        repeat_links.unlink_copy(copy)


def repeat_of(obj: DocumentObject) -> DocumentObject | None:
    """Répétition de ``obj`` : lui-même si c'est une répétition, celle dont c'est une copie liée,
    sinon ``None``."""
    return repeat.repeat_of(obj)
