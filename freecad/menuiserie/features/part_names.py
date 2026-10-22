# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nom d'une pièce = son repère (J6b, ADR 0011) : lectures du document partagées par la pièce de
bois brute et la pièce usinée. Les règles (suffixe « (n) », aller-retour) sont dans
:mod:`freecad.menuiserie.core.naming`."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.naming import label_for_mark
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.schema import warn

__all__ = [
    "DEFAULT_LABEL",
    "default_label",
    "label_of_mark",
    "mark_is_bound",
    "other_labels",
    "unique_label_after_copy",
    "warn_mark_bound",
]

DEFAULT_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce de bois")
_MARK_BOUND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le repère de « {label} » est piloté par une expression : renommer la pièce ne le change "
    "pas ; modifiez l'expression.",
)


def default_label() -> str:
    """Libellé d'une pièce sans repère, traduit (« Pièce de bois »)."""
    return translated(DEFAULT_LABEL)


def other_labels(obj: DocumentObject) -> set[str]:
    """Libellés de tous les autres objets du document de ``obj``."""
    return {str(other.Label) for other in obj.Document.Objects if other.Name != obj.Name}


def unique_label_after_copy(obj: DocumentObject) -> str | None:
    """Libellé unique à donner à ``obj`` qui vient d'être restauré, ``None`` s'il n'en faut pas.

    Copier-coller, Std Dupliquer et fusion de documents restaurent le libellé du modèle sans
    passer par :meth:`onBeforeChangeLabel` (``allowDuplicateLabel`` est vrai) : l'objet porte
    alors celui d'un autre. Le test est le doublon lui-même, car ``Document.Importing`` n'est
    pas vrai pour tout copier-coller. Une réouverture ordinaire (libellés tous uniques) et une
    annulation / un rétablissement ne changent donc rien (J6b, L6 ; J6, L5 bis)."""
    if obj.Document.Transacting:
        return None
    label = str(obj.Label)
    taken = other_labels(obj)
    return label_for_mark(label, label, taken) if label in taken else None


def label_of_mark(obj: DocumentObject, mark: str) -> str:
    """Libellé de la pièce ``obj`` pour le repère ``mark`` : unique dans son document."""
    return label_for_mark(mark, default_label(), other_labels(obj))


def mark_is_bound(obj: DocumentObject) -> bool:
    """Vrai si le repère de la pièce ``obj`` est piloté par une expression."""
    return any(path.lstrip(".") == "Mark" for path, _ in obj.ExpressionEngine)


def warn_mark_bound(obj: DocumentObject) -> None:
    """Avertissement dans la vue rapport : le nom ne peut pas changer un repère piloté."""
    warn(obj, _MARK_BOUND)
