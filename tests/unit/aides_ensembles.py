# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bureau de référence de la spécification J4 (§ 3) pour les tests de ``core.furniture``."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from freecad.menuiserie.core.furniture import (
    Edge,
    FurnitureBox,
    InteriorMode,
    Member,
    Rules,
    follow_rules,
    with_default_options,
)
from freecad.menuiserie.core.geometry import PlacedBlock, RigidTransform
from freecad.menuiserie.core.part_model import Dimensions
from tests.unit.aides_assemblages import Point, matrix

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
TURN_Y_MINUS_90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]  # L selon Z, e selon -X
TURN_X_PLUS_90 = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]  # l selon Z, e selon -Y

BOX = FurnitureBox(1200.0, 600.0, 750.0)
LABELS = {"P": "Plateau", "JG": "Joue gauche", "JD": "Joue droite", "V": "Voile"}


def placed(size: Point, base: Point, rotation: list[list[float]] = IDENTITY) -> PlacedBlock:
    """Pièce de cotes L x l x e au placement donné."""
    return PlacedBlock(Dimensions(*size), RigidTransform.from_matrix(matrix(rotation, base)))


BLOCKS = {
    "P": placed((1200.0, 600.0, 30.0), (0.0, 0.0, 720.0)),
    "JG": placed((720.0, 560.0, 22.0), (22.0, 0.0, 0.0), TURN_Y_MINUS_90),
    "JD": placed((720.0, 560.0, 22.0), (1200.0, 0.0, 0.0), TURN_Y_MINUS_90),
    "V": placed((1156.0, 400.0, 18.0), (22.0, 459.0, 320.0), TURN_X_PLUS_90),
}


def piece(key: str, **changes: object) -> Member:
    """Membre « pièce » du bureau, options à calculer sauf si ``fixed`` est donné."""
    member = Member(key, block=BLOCKS[key], label=LABELS[key])
    return replace(member, **changes)  # type: ignore[arg-type]


def desk(**modes: InteriorMode) -> list[Member]:
    """Les quatre membres du bureau, options à calculer, modes donnés par clé."""
    return [piece(key, mode=modes.get(key, InteriorMode.STAY)) for key in BLOCKS]


def with_options(
    members: Iterable[Member], extra: Mapping[str, frozenset[Edge]] | None = None
) -> list[Member]:
    """Options par défaut, puis options ``extra`` ajoutées (cases cochées par le menuisier)."""
    resolved = with_default_options(BOX, list(members))
    extra = extra or {}
    return [
        replace(m, fixed=(m.fixed or frozenset()) | extra.get(m.key, frozenset())) for m in resolved
    ]


BACK = frozenset({Edge.BACK})
FIXED_BACK = {"JG": BACK, "JD": BACK}


def desk_rules(members: list[Member], box: FurnitureBox = BOX) -> tuple[list[Member], Rules]:
    """Membres et règles de suivi (avertissements ignorés)."""
    return members, follow_rules(box, members)[0]
