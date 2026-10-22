# SPDX-License-Identifier: LGPL-2.1-or-later
"""Numérotation automatique des repères dans le document (J2f, critère N1, spécification J2 § 10).

Le calcul est pur (:func:`freecad.menuiserie.core.cutlist.assign_marks`) : un repère ``M<n>`` par
groupe de pièces sans repère, regroupées comme dans la liste de débit. Ce module le lit dans le
document et écrit les repères en une seule transaction ; le libellé de chaque pièce suit son
repère (J6, ADR 0011).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from freecad.menuiserie.core.cutlist import DEFAULT_MARK_PREFIX, assign_marks, group_key
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.cutlist_collect import checked_objects, collect
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.part_names import mark_is_bound
from freecad.menuiserie.features.wood_part import is_wood_part

__all__ = ["number_marks"]

TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Numéroter les repères")
_EMPTY_PREFIX: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le préfixe des repères ne peut pas être vide."
)


def _plan(doc: Document, objects: Sequence[DocumentObject] | None, prefix: str) -> dict[str, str]:
    """Repère à écrire par pièce brute sans repère (nom interne → repère). Une pièce dont le
    repère est piloté par une expression est laissée de côté : elle ne consomme aucun numéro."""
    collected = collect(doc, checked_objects(doc, objects))
    entries = [
        entry
        for entry in collected.entries
        if entry.record.mark or not mark_is_bound(doc.getObject(entry.source))
    ]
    used = [str(obj.Mark) for obj in doc.Objects if is_wood_part(obj)]
    marks = assign_marks(entries, prefix, used)
    return {entry.source: marks[group_key(entry)] for entry in entries if not entry.record.mark}


def number_marks(
    doc: Document,
    objects: Sequence[DocumentObject] | None = None,
    prefix: str = DEFAULT_MARK_PREFIX,
) -> dict[str, str]:
    """Donne un repère ``<prefix><n>`` à chaque groupe de pièces sans repère de ``doc`` (ou de
    ``objects``, ``None`` ou vide : tout le document) et renvoie le repère écrit pour chaque
    pièce (nom interne → repère). Les pièces d'un même groupe (mêmes cotes, matériau, fil,
    surcotes et ajouts) partagent le leur ; le premier numéro libre est pris, ensemble puis
    cotes décroissantes. Une pièce qui a déjà un repère ne change pas, ni une dont le repère est
    piloté par une expression. Une seule transaction « Numéroter les repères », document
    recalculé (la liste de débit vivante suit) ; rien n'est ouvert s'il n'y a rien à numéroter.
    ``ValueError`` traduite pour un préfixe vide ou un objet d'un autre document."""
    if not prefix.strip():
        raise ValueError(translated(_EMPTY_PREFIX))
    written = _plan(doc, objects, prefix)
    if not written:
        return {}
    doc.openTransaction(translated(TITLE))
    try:
        for name, mark in written.items():
            doc.getObject(name).Mark = mark
        doc.recompute()
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return written
