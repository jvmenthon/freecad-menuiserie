# SPDX-License-Identifier: LGPL-2.1-or-later
"""Décisions du panneau « Structure » (ADR 0046, lot 3), calculées sans FreeCAD ni Qt.

Menu contextuel et glisser-déposer demandent ici si une action est permise : chaque fonction
``decide_…`` renvoie une :class:`Decision` (autorisée, ou refusée avec un gabarit français
traduisible et ses paramètres) et ne modifie rien. Les faits viennent d'un :class:`MoveFacts`, lu
dans le document par ``features/structure_facts.py`` ; les clés sont celles des lignes du panneau
(nom de la pièce usinée à la place de sa brute, nom de l'ensemble).

Règle de l'assemblage vers l'extérieur (ADR 0026) : une pièce qui change d'ensemble, seule ou avec
le sous-ensemble qui la contient, ne doit porter d'assemblage qu'avec des pièces qui vont avec
elle ou qui sont déjà dans l'ensemble d'arrivée (sous-ensembles compris, ou hors de tout ensemble
si la pièce sort). Sinon l'assemblage ne serait plus rangé avec ses deux pièces : le dépôt est
refusé et l'assemblage doit être supprimé d'abord.
"""

from __future__ import annotations

import html
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from freecad.menuiserie.core.assembly_scope import keeps_assembly
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.structure_decision import Decision, refuse
from freecad.menuiserie.core.structure_rename import MAX_NAME_LENGTH, cleaned_name, decide_rename
from freecad.menuiserie.core.structure_tree import NodeKind
from freecad.menuiserie.core.text import quoted_value

__all__ = [
    "BUSY",
    "DRAGGABLE_KINDS",
    "MAX_NAME_LENGTH",
    "NO_DROP_KINDS",
    "Decision",
    "MoveFacts",
    "cleaned_name",
    "creates_sub_furniture",
    "decide_create",
    "decide_delete",
    "decide_drop",
    "decide_open",
    "decide_rename",
    "decide_rename_target",
    "decide_selection",
    "drop_blocked",
    "drop_target",
    "plain_tooltip",
    "top_level",
]

# Lignes qu'on glisse : les pièces et les ensembles (pas les assemblages).
DRAGGABLE_KINDS: Final = frozenset({NodeKind.PIECE, NodeKind.FURNITURE})
# Lignes qui ne reçoivent jamais de dépôt (une répétition gère ses copies, les autres objets
# ne se touchent pas) : y glisser une pièce est refusé, pas interprété comme « hors ensemble ».
NO_DROP_KINDS: Final = frozenset(
    {NodeKind.REPEAT, NodeKind.COPY, NodeKind.CUTLIST, NodeKind.OTHERS, NodeKind.OTHER}
)

BUSY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Terminez d'abord le panneau de tâche ouvert (OK ou Annuler)."
)
_NOTHING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucun élément choisi.")
_NOT_MOVABLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La sélection contient un élément qui ne se range pas (assemblage, objet supprimé ou "
    "d'un autre document) : seuls les pièces et les ensembles du document actif se rangent.",
)
_IS_COPY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {item} » est une copie de répétition : elle suit sa répétition et ne se range pas à part.",
)
_COPY_TARGET: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {item} » est une copie de répétition : on n'y range pas de pièce."
)
_FOREIGN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cet élément vient d'un autre atelier : l'atelier Menuiserie ne le modifie pas (il ne "
    "l'ouvre, ne le renomme, ne le range ni ne le supprime).",
)
_NO_DROP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cette ligne ne reçoit pas de pièce : déposez-la sur un ensemble.",
)
_CYCLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {item} » ne peut pas entrer dans « {target} » : « {target} » est « {item} » ou se "
    "trouve déjà dedans.",
)
_ALREADY_IN: Final = QT_TRANSLATE_NOOP("Menuiserie", "« {item} » est déjà dans « {target} ».")
_ALREADY_FREE: Final = QT_TRANSLATE_NOOP("Menuiserie", "« {item} » n'est dans aucun ensemble.")
_OUTWARD_INTO: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} », qui n'est pas dans « {target} » : le "
    "déplacement séparerait l'assemblage de l'une de ses pièces. Déplacez les deux pièces "
    "ensemble, ou supprimez d'abord l'assemblage.",
)
_OUTWARD_OUT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} », qui reste dans « {furniture} » : la sortir de son "
    "ensemble séparerait l'assemblage de l'une de ses pièces. Sortez les deux pièces "
    "ensemble, ou supprimez d'abord l'assemblage.",
)
_OUTWARD_NEW: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} », qui ne serait pas dans le nouvel ensemble ni dans "
    "l'ensemble qui le contient : l'assemblage serait séparé de l'une de ses pièces. Choisissez "
    "aussi « {other} », ou supprimez d'abord l'assemblage.",
)
_NOT_SAME: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les éléments choisis ne sont pas tous dans le même ensemble : choisissez des éléments d'un "
    "seul ensemble, ou des pièces hors ensemble.",
)
_NOT_RENAMABLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Seuls les pièces et les ensembles se renomment ici."
)
_ONE_ROW: Final = QT_TRANSLATE_NOOP("Menuiserie", "Choisissez une seule ligne.")


@dataclass(frozen=True)
class MoveFacts:
    """Ce que les décisions savent du document : libellés des pièces et des ensembles, ensembles,
    ensemble de chaque membre (``parent``), pièces assemblées à chaque pièce (``links``) et
    panneau de tâche ouvert (``busy``), copies de répétition (``copies``, qui ne se rangent pas
    à part) et objets d'autres ateliers (``foreign``, qu'on ne touche pas)."""

    labels: Mapping[str, str]
    furnitures: frozenset[str]
    parent: Mapping[str, str]
    links: Mapping[str, frozenset[str]] = field(default_factory=dict)
    busy: bool = False
    copies: frozenset[str] = frozenset()
    foreign: frozenset[str] = frozenset()

    def label(self, key: str) -> str:
        """Libellé cité dans un message."""
        return quoted_value(self.labels.get(key, key))

    def chain(self, key: str) -> list[str]:
        """Ensembles qui contiennent ``key``, du plus proche au plus éloigné (cycle coupé)."""
        found: list[str] = []
        current = self.parent.get(key)
        while current is not None and current not in found:
            found.append(current)
            current = self.parent.get(current)
        return found

    def pieces_under(self, key: str) -> set[str]:
        """``key`` si c'est une pièce, sinon les pièces de l'ensemble et de ses sous-ensembles."""
        if key not in self.furnitures:
            return {key}
        found: set[str] = set()
        seen = {key}
        pending = [key]
        while pending:
            current = pending.pop()
            for child, owner in self.parent.items():
                if owner != current or child in seen:
                    continue
                seen.add(child)
                if child in self.furnitures:
                    pending.append(child)
                else:
                    found.add(child)
        return found


def top_level(facts: MoveFacts, keys: Iterable[str]) -> list[str]:
    """``keys`` sans doublon ni élément dont un ensemble ancêtre est aussi choisi (il se
    déplace avec cet ensemble), dans l'ordre reçu."""
    chosen = list(dict.fromkeys(keys))
    return [key for key in chosen if not set(facts.chain(key)) & set(chosen)]


def _movable(facts: MoveFacts, keys: Sequence[str]) -> Decision | None:
    """Refus commun à toute action sur une sélection de pièces et d'ensembles, ``None`` sinon."""
    if facts.busy:
        return refuse(BUSY)
    if not keys:
        return refuse(_NOTHING)
    if any(key in facts.foreign for key in keys):
        return refuse(_FOREIGN)
    if (copy := next((key for key in keys if key in facts.copies), None)) is not None:
        return refuse(_IS_COPY, item=facts.label(copy))
    if any(key not in facts.labels for key in keys):
        return refuse(_NOT_MOVABLE)
    return None


def decide_selection(facts: MoveFacts, keys: Iterable[str]) -> Decision:
    """La sélection ne contient que des pièces et des ensembles du document, et aucun panneau de
    tâche n'est ouvert : permis, ``keys`` = les plus hautes lignes choisies."""
    chosen = top_level(facts, keys)
    return _movable(facts, chosen) or Decision(True, keys=tuple(chosen))


def _split_assembly(
    facts: MoveFacts, moving: Sequence[str], after: Sequence[str]
) -> tuple[str, str] | None:
    """Première (pièce déplacée, pièce assemblée qui reste) dont l'assemblage perd son ensemble
    commun (:func:`keeps_assembly`) une fois la pièce dans les ensembles ``after``."""
    moved = set[str]().union(*(facts.pieces_under(key) for key in moving))
    for piece in sorted(moved):
        for other in sorted(facts.links.get(piece, frozenset()) - moved):
            if not keeps_assembly(after, facts.chain(other)):
                return piece, other
    return None


def _outward(facts: MoveFacts, moving: Sequence[str], target: str | None) -> Decision | None:
    """Refus si une pièce déplacée est assemblée à une pièce qui ne sera pas avec elle."""
    after = [] if target is None else [target, *facts.chain(target)]
    split = _split_assembly(facts, moving, after)
    if split is None:
        return None
    names = {"piece": facts.label(split[0]), "other": facts.label(split[1])}
    if target is not None:
        return refuse(_OUTWARD_INTO, target=facts.label(target), **names)
    return refuse(_OUTWARD_OUT, furniture=facts.label(facts.parent[split[1]]), **names)


def _in_place(facts: MoveFacts, movers: Sequence[str], target: str | None) -> Decision:
    first = movers[0]
    if target is None:
        return refuse(_ALREADY_FREE, item=facts.label(first))
    return refuse(_ALREADY_IN, item=facts.label(first), target=facts.label(target))


def _bad_target(facts: MoveFacts, target: str | None) -> Decision | None:
    """Refus si ``target`` n'est pas un ensemble qui reçoit des pièces (copie de répétition,
    objet inconnu), ``None`` sinon (y compris ``None`` : hors ensemble)."""
    if target is None:
        return None
    if target in facts.copies:
        return refuse(_COPY_TARGET, item=facts.label(target))
    return None if target in facts.furnitures else refuse(_NOT_MOVABLE)


def decide_drop(facts: MoveFacts, keys: Iterable[str], target: str | None) -> Decision:
    """Glisser-déposer (ou « Ajouter à l'ensemble » / « Sortir de l'ensemble ») : ranger les
    lignes ``keys`` dans l'ensemble ``target``, ou les sortir de leur ensemble si ``target`` est
    ``None``. Autorisé : ``keys`` = ce qui change d'ensemble. Refusé, avec la raison : panneau de
    tâche ouvert, rien ou un élément inconnu, cycle d'ensembles, déjà en place, assemblage vers
    l'extérieur."""
    movers = top_level(facts, keys)
    if (refusal := _movable(facts, movers)) is not None:
        return refusal
    if (refusal := _bad_target(facts, target)) is not None:
        return refusal
    for key in movers:
        if target is not None and (key == target or key in facts.chain(target)):
            return refuse(_CYCLE, item=facts.label(key), target=facts.label(target))
    moving = [key for key in movers if facts.parent.get(key) != target]
    if not moving:
        return _in_place(facts, movers, target)
    if (refusal := _outward(facts, moving, target)) is not None:
        return refusal
    return Decision(True, keys=tuple(moving))


def decide_create(facts: MoveFacts, keys: Iterable[str]) -> Decision:
    """« Créer un (sous-)ensemble depuis la sélection » (ADR 0037) : permis si les éléments sont
    tous hors ensemble (nouvel ensemble) ou tous dans le même ensemble (sous-ensemble). Le nouvel
    ensemble reste dans l'ensemble parent : un assemblage avec une pièce du parent y reste rangé
    (même critère que le dépôt, :func:`keeps_assembly`) ; vers une pièce hors du parent, il est
    séparé : refusé."""
    chosen = top_level(facts, keys)
    if (refusal := _movable(facts, chosen)) is not None:
        return refusal
    if len({facts.parent.get(key) for key in chosen}) != 1:
        return refuse(_NOT_SAME)
    parent = facts.parent.get(chosen[0])
    after = ["", *([] if parent is None else [parent, *facts.chain(parent)])]
    if (split := _split_assembly(facts, chosen, after)) is not None:
        return refuse(_OUTWARD_NEW, piece=facts.label(split[0]), other=facts.label(split[1]))
    return Decision(True, keys=tuple(chosen))


def creates_sub_furniture(facts: MoveFacts, keys: Iterable[str]) -> bool:
    """Vrai si la création depuis ``keys`` fait un sous-ensemble (éléments déjà dans un ensemble),
    faux pour un ensemble de plus haut niveau."""
    chosen = top_level(facts, keys)
    return bool(chosen) and chosen[0] in facts.parent


def decide_delete(keys: Sequence[str], *, busy: bool, foreign: Collection[str] = ()) -> Decision:
    """« Supprimer » : au moins une ligne d'un objet de l'atelier, aucun panneau de tâche ouvert
    (comme les commandes de l'atelier). Les fenêtres d'avertissement sont celles de l'arbre
    natif. Un objet d'un autre atelier (``foreign``) n'est jamais supprimé d'ici."""
    if busy:
        return refuse(BUSY)
    if not keys:
        return refuse(_NOTHING)
    if any(key in foreign for key in keys):
        return refuse(_FOREIGN)
    return Decision(True, keys=tuple(dict.fromkeys(keys)))


def decide_open(keys: Sequence[str], *, busy: bool, foreign: Collection[str] = ()) -> Decision:
    """« Ouvrir » (équivaut au double-clic) : une seule ligne, aucun panneau de tâche ouvert ;
    jamais pour un objet d'un autre atelier (``foreign``) : l'éditer, c'est le modifier."""
    if len(keys) != 1:
        return refuse(_ONE_ROW if keys else _NOTHING)
    if keys[0] in foreign:
        return refuse(_FOREIGN)
    if busy:
        return refuse(BUSY)
    return Decision(True, keys=tuple(keys))


def decide_rename_target(facts: MoveFacts, keys: Sequence[str]) -> Decision:
    """« Renommer » est proposé : une seule ligne, pièce ou ensemble du document."""
    if len(keys) != 1:
        return refuse(_ONE_ROW if keys else _NOTHING)
    if keys[0] in facts.foreign:
        return refuse(_FOREIGN)
    if keys[0] not in facts.labels:
        return refuse(_NOT_RENAMABLE)
    return Decision(True, keys=tuple(keys))


def plain_tooltip(text: str) -> str:
    """``text`` à afficher tel quel dans une infobulle : Qt prend pour du texte riche tout texte
    qui commence par une balise, donc les chevrons sont échappés et le texte est enveloppé
    dans une balise (sans quoi les entités s'afficheraient en toutes lettres)."""
    return f"<span>{html.escape(text, quote=False)}</span>"


def drop_target(path: Iterable[tuple[NodeKind, str]]) -> str | None:
    """Ensemble visé par un dépôt sur une ligne : ``path`` va de la ligne visée à la racine
    (genre et clé de chaque ligne) ; c'est le premier ensemble, la ligne elle-même si c'en est
    un. ``None`` (hors ensemble) si la ligne n'est dans aucun ensemble ou s'il n'y a pas de
    ligne."""
    return next((key for kind, key in path if kind is NodeKind.FURNITURE), None)


def drop_blocked(path: Iterable[tuple[NodeKind, str]]) -> str:
    """Gabarit du refus si un dépôt sur la ligne ``path`` (comme pour :func:`drop_target`) est
    impossible parce qu'une répétition, une liste de débit ou un autre objet est rencontré avant
    tout ensemble ; vide sinon."""
    for kind, _key in path:
        if kind is NodeKind.FURNITURE:
            return ""
        if kind in NO_DROP_KINDS:
            return _NO_DROP
    return ""
