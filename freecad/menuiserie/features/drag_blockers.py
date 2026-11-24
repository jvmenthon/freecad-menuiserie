# SPDX-License-Identifier: LGPL-2.1-or-later
"""Raison pour laquelle une cote ne se tire pas à la souris (ADR 0068).

Une poignée impossible n'est plus cachée : elle est dessinée grisée, avec un cadenas, et son
infobulle dit pourquoi (titre, explication, piste « → … »). :func:`size_blocker` choisit la raison
d'un axe de la pièce, :func:`blocker_text` la traduit. Les raisons sont rangées de la plus
générale à la plus précise : une pièce verrouillée l'est sur ses trois axes, quelle que soit la
famille de son bois. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.magnet import THICKNESS_AXIS
from freecad.menuiserie.features.i18n import translated

__all__ = ["Blocker", "SizeBlock", "blocked_sizes", "blocker_text", "size_blocker"]

Blocker = tuple[str, str, str]  # titre, explication, piste (traduits)


class SizeBlock(Enum):
    """Pourquoi une cote ne se tire pas."""

    LOCKED = "locked"  # « Cotes fixes » (ADR 0019)
    SHAPED = "shaped"  # pièce en bois : cotes du dessin (#87)
    FORMULA = "formula"  # formule de l'utilisateur sur la cote
    POSITION = "position"  # formule de l'utilisateur sur la position de l'axe
    PANEL = "panel"  # épaisseur d'un panneau : celle de la bibliothèque (Q4)


_TEXTS: Final = {
    SizeBlock.LOCKED: (
        QT_TRANSLATE_NOOP("Menuiserie", "Cotes fixes"),
        QT_TRANSLATE_NOOP("Menuiserie", "La pièce garde ses cotes quand l'ensemble change."),
        QT_TRANSLATE_NOOP(
            "Menuiserie", "→ Décocher « Cotes fixes » dans le panneau de l'ensemble."
        ),
    ),
    SizeBlock.SHAPED: (
        QT_TRANSLATE_NOOP("Menuiserie", "Cotes du dessin"),
        QT_TRANSLATE_NOOP("Menuiserie", "Les cotes d'une pièce en bois viennent de son dessin."),
        QT_TRANSLATE_NOOP("Menuiserie", "→ Modifier le dessin pour changer sa taille."),
    ),
    SizeBlock.FORMULA: (
        QT_TRANSLATE_NOOP("Menuiserie", "{size} pilotée par une formule"),
        QT_TRANSLATE_NOOP("Menuiserie", "Une formule calcule cette cote."),
        QT_TRANSLATE_NOOP("Menuiserie", "→ Retirer la formule pour la tirer à la souris."),
    ),
    SizeBlock.POSITION: (
        QT_TRANSLATE_NOOP("Menuiserie", "Position pilotée par une formule"),
        QT_TRANSLATE_NOOP(
            "Menuiserie", "Tirer cette face déplacerait la pièce sur un axe fixé par une formule."
        ),
        QT_TRANSLATE_NOOP("Menuiserie", "→ Retirer la formule du placement pour la tirer."),
    ),
    SizeBlock.PANEL: (
        QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur non modifiable"),
        QT_TRANSLATE_NOOP(
            "Menuiserie", "Un panneau garde l'épaisseur de la bibliothèque : {thickness} mm."
        ),
        QT_TRANSLATE_NOOP(
            "Menuiserie", "→ Choisir une autre épaisseur standard dans le panneau de la pièce."
        ),
    ),
}
_SIZE_NAMES: Final = (
    QT_TRANSLATE_NOOP("Menuiserie", "Longueur"),
    QT_TRANSLATE_NOOP("Menuiserie", "Largeur"),
    QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur"),
)


def size_blocker(
    axis: int,
    *,
    locked: bool,
    shaped: bool,
    formula: bool,
    position: bool,
    panel: bool,
) -> SizeBlock | None:
    """Raison qui empêche de tirer la cote de l'axe ``axis`` (0 = longueur…), la première dans
    l'ordre de :class:`SizeBlock` ; ``None`` si la cote se tire. ``panel`` ne compte que pour
    l'épaisseur (:data:`THICKNESS_AXIS`)."""
    reasons = (
        (locked, SizeBlock.LOCKED),
        (shaped, SizeBlock.SHAPED),
        (formula, SizeBlock.FORMULA),
        (position, SizeBlock.POSITION),
        (panel and axis == THICKNESS_AXIS, SizeBlock.PANEL),
    )
    return next((block for blocked, block in reasons if blocked), None)


def _number(value: float) -> str:
    rounded = round(value, 1)
    return f"{rounded:.0f}" if rounded == int(rounded) else f"{rounded:.1f}"


def blocker_text(block: SizeBlock, axis: int, thickness: float) -> Blocker:
    """Titre, explication et piste traduits de ``block`` pour l'axe ``axis`` ; ``thickness``
    (mm) est l'épaisseur du panneau citée par :attr:`SizeBlock.PANEL`."""
    params = {
        "size": translated(_SIZE_NAMES[axis]),
        "thickness": _number(thickness),
    }
    title, detail, hint = _TEXTS[block]
    return translated(title, params), translated(detail, params), translated(hint, params)


def blocked_sizes(
    *,
    locked: bool,
    shaped: bool,
    formulas: Sequence[bool],
    fixed: frozenset[int],
    panel: bool,
    thickness: float,
) -> tuple[tuple[int, Blocker], ...]:
    """Axes de la pièce dont la cote ne se tire pas, chacun avec sa raison traduite :
    ``locked`` (« Cotes fixes »), ``shaped`` (pièce en bois), ``formulas`` (formule de
    l'utilisateur sur la longueur, la largeur, l'épaisseur), ``fixed`` (axes dont la position est
    fixée par une formule), ``panel`` (panneau d'épaisseur ``thickness`` mm)."""
    blocked = []
    for axis in range(3):
        block = size_blocker(
            axis,
            locked=locked,
            shaped=shaped,
            formula=formulas[axis],
            position=axis in fixed,
            panel=panel,
        )
        if block is not None:
            blocked.append((axis, blocker_text(block, axis, thickness)))
    return tuple(blocked)
