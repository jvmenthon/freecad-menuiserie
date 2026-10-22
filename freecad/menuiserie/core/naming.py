# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nom d'une pièce = son repère (J6b, ADR 0011), sans FreeCAD.

Le repère (``Mark``) est la donnée ; le libellé (``Label``) en est le reflet. Un libellé est
unique dans un document alors que des pièces identiques partagent un repère : le doublon reçoit
le suffixe « (n) » (n ≥ 2), que le retour du libellé vers le repère retire.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from typing import Final

__all__ = ["DUPLICATE_SUFFIX", "label_for_mark", "mark_from_label"]

DUPLICATE_SUFFIX: Final = " ({n})"  # n ≥ 2
_FIRST_DUPLICATE: Final = 2
_SUFFIX: Final = re.compile(r" \((?:[2-9]|[1-9][0-9]+)\)$")


def label_for_mark(mark: str, default: str, taken: Collection[str]) -> str:
    """Libellé d'une pièce de repère ``mark``, absent de ``taken`` (libellés des **autres**
    objets du document).

    Un repère vide (ou d'espaces) donne ``default``. Le texte est gardé tel quel ; s'il est déjà
    pris, le premier « texte (n) » libre à partir de n = 2 est rendu.
    """
    base = mark if mark.strip() else default
    label = base
    number = _FIRST_DUPLICATE
    while label in taken:
        label = base + DUPLICATE_SUFFIX.format(n=number)
        number += 1
    return label


def mark_from_label(label: str, default: str) -> str:
    """Repère déduit d'un libellé saisi : suffixe « (n) » final (n ≥ 2) retiré ; ``default``
    (ou un texte vide) donne un repère vide.

    Limite documentée : un repère saisi « A (2) » dans l'arborescence devient « A », et un
    repère égal à ``default`` redevient vide.
    """
    mark = _SUFFIX.sub("", label)
    if not mark.strip() or mark == default:
        return ""
    return mark
