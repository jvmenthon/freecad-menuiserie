# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition de pièces de la façade publique (R-b1, ADR 0043).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import RepeatParams
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import repeat, repeat_copies, repeat_links
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
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


def _show(copies: Sequence[DocumentObject]) -> None:
    """ViewProvider des copies créées, quand l'interface est chargée."""
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.wood_part import ViewProviderWoodPart

        for copy in copies:
            ViewProviderWoodPart(copy.ViewObject)


def make_repeat(
    objects: Sequence[DocumentObject], params: RepeatParams, *, transaction: bool = True
) -> DocumentObject:
    """Répète les pièces de bois ``objects`` selon ``params`` (:class:`RepeatParams`, mm) et
    renvoie la répétition (objet de cotes sans forme, nom interne ``Repeat``).

    Chaque source reçoit ``Count`` copies, au même pas, qui sont de vraies pièces de bois
    liées à la source par expressions natives : cotes, matériau, sens du fil et surcotes sont
    ceux de la source, le placement suit la source plus ``k`` pas sur l'axe. Modifier la source
    ou ``Step`` déplace ou redimensionne donc les copies au recalcul. Libellé d'une copie :
    « {libellé de la source} {k+1} ». Un seul bloc annulable, un seul recalcul. Refus traduits
    avant toute création : ``TypeError`` (autre chose qu'une pièce de bois), ``ValueError``
    (aucune pièce, copie déjà liée, longueur trop courte, trop de copies…), ``KeyError``
    (matériau inconnu). ``transaction=False`` : l'appelant a ouvert la sienne (commande de
    l'interface) et la valide ; sinon elle est ouverte et validée ici."""
    sources = repeat_copies.checked_sources(objects)
    repeat_copies.resolve_for(sources, params)
    doc = sources[0].Document
    with _undoable(doc, _MAKE_TRANSACTION, own=transaction):
        obj = repeat.create_repeat(doc, sources)
        _show(repeat_copies.apply_repeat(obj, params))
    return obj


def _checked_repeat(obj: DocumentObject) -> DocumentObject:
    found = repeat.repeat_of(obj)
    if found is None:
        raise TypeError(translated(_NOT_A_REPEAT, {"label": quoted_value(obj.Label)}))
    return found


def edit_repeat(obj: DocumentObject, params: RepeatParams, *, transaction: bool = True) -> None:
    """Change le réglage de la répétition ``obj`` (ou d'une de ses copies) : ajoute les copies qui
    manquent (rangs à la suite de l'ancien nombre), supprime les dernières si le nombre baisse
    (avec leur pièce usinée et leurs assemblages), réécrit le pas et les expressions. Même
    transaction (``transaction``), même recalcul et mêmes refus que :func:`make_repeat` ; rien
    n'est modifié si le réglage est refusé."""
    found = _checked_repeat(obj)
    repeat_copies.resolve_for(repeat.sources_of(found), params)
    with _undoable(found.Document, _EDIT_TRANSACTION, own=transaction):
        _show(repeat_copies.apply_repeat(found, params))


def dissociate(copy: DocumentObject, *, transaction: bool = True) -> None:
    """Dissocie la copie ``copy`` : ses expressions et ses propriétés ``Repeat``, ``RepeatSource``
    et ``RepeatIndex`` sont retirées, la pièce garde ses valeurs actuelles et devient libre. La
    répétition garde les autres copies et son nombre (les rangs ne bougent pas). ``TypeError``
    traduite si ``copy`` n'est pas une copie liée. Un bloc annulable, un recalcul (``transaction``
    : voir :func:`make_repeat`)."""
    if not repeat.is_copy(copy):
        raise TypeError(translated(_NOT_A_COPY, {"label": quoted_value(copy.Label)}))
    with _undoable(copy.Document, _DISSOCIATE_TRANSACTION, own=transaction):
        copy.Document.recompute()  # les valeurs gardées sont celles de la source à jour
        repeat_links.unlink_copy(copy)


def repeat_of(obj: DocumentObject) -> DocumentObject | None:
    """Répétition de ``obj`` : lui-même si c'est une répétition, celle dont c'est une copie liée,
    sinon ``None``."""
    return repeat.repeat_of(obj)
