# SPDX-License-Identifier: LGPL-2.1-or-later
"""Textes de l'encadré « où ajouter l'épaisseur ? » (ADR 0060, maquette C).

Chaque phrase est un modèle complet, traduisible tel quel : aucun mot n'est recollé ni mis en
minuscule ici (l'ordre des mots et l'accord changent d'une langue à l'autre). Aucun import de
``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.thickness_common import length_text, quoted, quoted_parts

__all__ = [
    "extend_text",
    "keep_text",
    "not_flush_text",
    "other_side_text",
    "question_text",
    "revert_text",
    "still_broken_text",
    "title_text",
]

_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "{kind} avec {partners}.")
_ADD: Final = QT_TRANSLATE_NOOP("Menuiserie", "Où ajouter les {delta} ?")
_REMOVE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Où retirer les {delta} ?")
# (épaisseur ajoutée, face basse du côté de l'autre pièce) → modèle
_STAYS_FLUSH: Final = {
    (True, True): QT_TRANSLATE_NOOP("Menuiserie", "Vers l'intérieur (reste à fleur)"),
    (True, False): QT_TRANSLATE_NOOP("Menuiserie", "Vers l'extérieur (reste à fleur)"),
    (False, True): QT_TRANSLATE_NOOP("Menuiserie", "Côté intérieur (reste à fleur)"),
    (False, False): QT_TRANSLATE_NOOP("Menuiserie", "Côté extérieur (reste à fleur)"),
}
# (épaisseur ajoutée, face haute du côté de l'autre pièce) → modèle
_EXTEND: Final = {
    (True, True): QT_TRANSLATE_NOOP(
        "Menuiserie", "Vers l'intérieur et allonger {partners} de {delta}"
    ),
    (True, False): QT_TRANSLATE_NOOP(
        "Menuiserie", "Vers l'extérieur et allonger {partners} de {delta}"
    ),
    (False, True): QT_TRANSLATE_NOOP(
        "Menuiserie", "Côté intérieur et raccourcir {partners} de {delta}"
    ),
    (False, False): QT_TRANSLATE_NOOP(
        "Menuiserie", "Côté extérieur et raccourcir {partners} de {delta}"
    ),
}
_REVERT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Revenir à {thickness}")
_KEEP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Laisser en l'état")
_NOT_FLUSH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} n'arrive pas à fleur de la face qui bouge."
)
_STILL_BROKEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Défait encore : {joints}.")


def title_text(broken: Sequence[DocumentObject], partners: Sequence[DocumentObject]) -> str:
    """« Queue d'aronde avec « H ». » : sortes des assemblages ``broken`` et autres pièces."""
    kinds: list[str] = []
    for joint in broken:
        kind = translated(joint.Proxy.LABEL)
        if kind not in kinds:
            kinds.append(kind)
    return translated(_TITLE, {"kind": ", ".join(kinds), "partners": quoted_parts(partners)})


def question_text(old: float, new: float) -> str:
    """« Où ajouter les 12 mm ? » (ou « retirer »)."""
    template = _ADD if new > old else _REMOVE
    return translated(template, {"delta": length_text(new - old)})


def other_side_text(adding: bool, inward: bool) -> str:
    """Choix « de l'autre côté » : ``inward`` si la face basse est du côté de l'autre pièce."""
    return translated(_STAYS_FLUSH[(adding, inward)])


def extend_text(
    adding: bool, inward: bool, partners: Sequence[DocumentObject], delta: float
) -> str:
    """Choix « prolonger l'autre pièce » : ``inward`` si la face haute est de son côté."""
    params = {"partners": quoted_parts(partners), "delta": length_text(delta)}
    return translated(_EXTEND[(adding, inward)], params)


def keep_text() -> str:
    """« Laisser en l'état » : l'épaisseur telle que saisie, face haute déplacée (issue #133)."""
    return translated(_KEEP)


def revert_text(thickness: float) -> str:
    """« Revenir à 18 mm »."""
    return translated(_REVERT, {"thickness": length_text(thickness)})


def not_flush_text(part: DocumentObject) -> str:
    """Raison : ``part`` n'arrive pas à fleur de la face qui bouge."""
    return translated(_NOT_FLUSH, {"label": quoted(part)})


def still_broken_text(joints: Sequence[DocumentObject]) -> str:
    """Raison : assemblages ``joints`` encore défaits."""
    return translated(_STILL_BROKEN, {"joints": quoted_parts(joints)})
