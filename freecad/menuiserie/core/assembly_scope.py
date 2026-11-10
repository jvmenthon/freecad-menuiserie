# SPDX-License-Identifier: LGPL-2.1-or-later
"""Critère unique de l'assemblage « vers l'extérieur » (ADR 0026, ADR 0038, ADR 0046), sans
FreeCAD ni Qt.

FreeCAD range toute la **fermeture de liens** d'un objet dans le Std Part où on le range (essai
de l'ADR 0038, confirmé sur FreeCAD 1.1) : deux pièces assemblées doivent donc être dans le même
ensemble, ou toutes deux hors de tout ensemble (:func:`keeps_assembly`). Quand l'endroit demandé
séparerait un assemblage, la pièce est rangée à l'endroit cohérent le plus proche
(:func:`destination`) : dans l'ensemble de la pièce assemblée qui reste, si cet ensemble est dans
la même branche que l'endroit demandé (c'est le plus proche ensemble parent commun), hors de tout
ensemble si l'autre pièce l'est ; sinon il n'y a pas de rangement cohérent.

Les « chaînes » sont les noms des ensembles qui contiennent une pièce, du plus proche au plus
éloigné (vide : hors ensemble). Partagé par les décisions du panneau (``decide_drop``,
``decide_create``) et par l'api (``features/furniture_entry``, ``furniture_members``).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

__all__ = [
    "CREATE_NOTHING",
    "CREATE_STAYS",
    "GOES_TO",
    "STAYS_IN",
    "destination",
    "keeps_assembly",
    "nearest_common",
]

# Messages communs au panneau et à l'api : où va une pièce dont l'assemblage imposait un autre
# endroit que celui demandé (paramètres : piece, other, dest, target).
GOES_TO: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} » : elle est rangée dans « {dest} », comme « {other} », "
    "et non dans « {target} ».",
)
STAYS_IN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} » : elle reste dans « {dest} », comme « {other} », "
    "et ne va pas dans « {target} ». Déplacez aussi « {other} » pour les ranger ensemble.",
)
CREATE_STAYS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} » : elle reste dans « {dest} », comme « {other} », "
    "hors du nouvel ensemble.",
)
CREATE_NOTHING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Rien à créer : « {piece} » est assemblée à « {other} » et reste dans « {dest} » avec elle. "
    "Choisissez aussi « {other} » pour former le nouvel ensemble.",
)


def nearest_common(first: Sequence[str], second: Sequence[str]) -> str | None:
    """Ensemble le plus proche de ``first`` qui est aussi dans ``second`` (``None`` : aucun)."""
    others = set(second)
    return next((name for name in first if name in others), None)


def keeps_assembly(moved: Sequence[str], other: Sequence[str]) -> bool:
    """Vrai si un assemblage entre une pièce qui sera dans les ensembles ``moved`` (après
    l'action) et une pièce qui reste dans ``other`` garde ses deux pièces dans le même Std Part :
    même ensemble le plus proche, ou toutes deux hors de tout ensemble."""
    return list(moved[:1]) == list(other[:1])


def destination(
    wanted: Sequence[str], others: Iterable[Sequence[str]], *, ignore_free: bool = False
) -> tuple[str, ...] | None:
    """Chaîne d'ensembles où ranger des pièces que l'on voulait ranger dans ``wanted``, alors que
    des pièces qui leur sont assemblées restent dans les chaînes ``others``. ``wanted`` si rien
    n'est séparé. Une autre pièce hors ensemble amène à sortir (chaîne vide), sauf avec
    ``ignore_free`` (l'api la range avec la pièce). Une autre pièce dans un ensemble amène dans cet
    ensemble s'il est dans la même branche que ``wanted`` (un ensemble commun existe), sinon
    ``None`` : aucun rangement cohérent, ou deux exigences qui se contredisent."""
    chains = [tuple(chain) for chain in others if chain or not ignore_free]
    dest = tuple(wanted)
    for chain in chains:
        if keeps_assembly(dest, chain):
            continue
        if not chain:
            dest = ()
        elif nearest_common(dest, chain) is None:
            return None
        else:
            dest = chain
    return dest if all(keeps_assembly(dest, chain) for chain in chains) else None
