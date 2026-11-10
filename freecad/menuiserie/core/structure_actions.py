# SPDX-License-Identifier: LGPL-2.1-or-later
"""Décisions du panneau « Structure » (ADR 0046, lot 3), calculées sans FreeCAD ni Qt.

Menu contextuel et glisser-déposer demandent ici si une action est permise : chaque fonction
``decide_…`` renvoie une :class:`Decision` (autorisée, ou refusée avec un gabarit français
traduisible et ses paramètres) et ne modifie rien. Les faits viennent d'un :class:`MoveFacts`, lu
dans le document par ``features/structure_facts.py`` ; les clés sont celles des lignes du panneau
(nom de la pièce usinée à la place de sa brute, nom de l'ensemble).

Règle de l'assemblage vers l'extérieur (ADR 0026, ADR 0038), critère ``core/assembly_scope`` : une
pièce qui change d'ensemble, seule ou avec le sous-ensemble qui la contient, ne doit porter
d'assemblage qu'avec des pièces qui vont avec elle ou qui se retrouveront dans le même ensemble
qu'elle (hors de tout ensemble si elle sort). FreeCAD range en effet toute la fermeture de liens
d'une pièce dans le Std Part d'arrivée : l'assemblage ne serait plus rangé avec ses deux pièces.
Le dépôt est alors refusé et l'assemblage doit être supprimé d'abord. Même règle pour créer un
ensemble (ADR 0037), sauf pour une pièce assemblée hors de tout ensemble, que l'api range avec elle.
"""

from __future__ import annotations

import html
from collections.abc import Collection, Iterable, Sequence
from typing import Final

from freecad.menuiserie.core.assembly_scope import CREATE_NOTHING, CREATE_STAYS, GOES_TO, STAYS_IN
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.structure_decision import Decision, Move, Note, refuse
from freecad.menuiserie.core.structure_move_facts import MoveFacts, top_level
from freecad.menuiserie.core.structure_plan import Part, plan_parts
from freecad.menuiserie.core.structure_rename import MAX_NAME_LENGTH, cleaned_name, decide_rename
from freecad.menuiserie.core.structure_tree import NodeKind

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
    "« {piece} » est assemblée à « {other} », qui ne serait pas dans le même ensemble qu'elle "
    "(« {target} ») : le déplacement séparerait l'assemblage de l'une de ses pièces. Déplacez les "
    "deux pièces ensemble, ou supprimez d'abord l'assemblage.",
)
_OUTWARD_OUT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} », qui reste dans « {furniture} » : la sortir de son "
    "ensemble séparerait l'assemblage de l'une de ses pièces. Sortez les deux pièces "
    "ensemble, ou supprimez d'abord l'assemblage.",
)
_OUTWARD_NEW: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} », qui est dans un autre ensemble : aucun nouvel "
    "ensemble cohérent ne peut les réunir. Choisissez aussi « {other} », ou supprimez d'abord "
    "l'assemblage.",
)
_GOES_FREE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} », qui n'est dans aucun ensemble : elle reste hors "
    "ensemble avec elle, et non dans « {target} ».",
)
_STAYS_FREE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {piece} » est assemblée à « {other} », qui n'est dans aucun ensemble : elle reste hors "
    "ensemble avec elle. Rangez aussi « {other} » pour les déplacer ensemble.",
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


def _outward(facts: MoveFacts, part: Part, target: str | None) -> Decision:
    """Refus : aucun rangement cohérent pour la partie, une pièce assemblée à une pièce qui ne
    sera pas avec elle."""
    names = {"piece": facts.label(part.piece), "other": facts.label(part.other)}
    if target is not None:
        return refuse(_OUTWARD_INTO, target=facts.label(target), **names)
    return refuse(_OUTWARD_OUT, furniture=facts.label(facts.parent[part.other]), **names)


def _redirection(facts: MoveFacts, part: Part, target: str | None, *, stays: bool) -> Note:
    """Où va la partie quand ce n'est pas l'endroit demandé (``stays`` : elle y est déjà)."""
    names = {"piece": facts.label(part.piece), "other": facts.label(part.other)}
    names["target"] = "" if target is None else facts.label(target)
    if part.dest:
        names["dest"] = facts.label(part.dest[0])
        return Note(STAYS_IN if stays else GOES_TO, names)
    return Note(_STAYS_FREE if stays else _GOES_FREE, names)


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
    ``None``. Une pièce assemblée à une pièce qui reste ailleurs est rangée à l'endroit cohérent le
    plus proche (``moves``, ``notes``). Autorisé : ``keys`` = ce qui change d'ensemble. Refusé,
    avec la raison : panneau de tâche ouvert, rien ou un élément inconnu, cycle d'ensembles, déjà
    en place, aucun rangement cohérent pour un assemblage."""
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
    wanted = [] if target is None else [target, *facts.chain(target)]
    parts = plan_parts(facts, moving, wanted)
    if (broken := next((part for part in parts if part.dest is None), None)) is not None:
        return _outward(facts, broken, target)
    return _drop_of(facts, parts, tuple(wanted), target)


def _drop_of(
    facts: MoveFacts, parts: Sequence[Part], wanted: tuple[str, ...], target: str | None
) -> Decision:
    """Décision d'un dépôt dont toutes les parties ont un endroit : où va chacune, ce qui n'est
    pas ce qui était demandé. Refusé si rien ne change ou si un endroit forme un cycle."""
    moves: dict[str | None, list[str]] = {}
    notes: list[Note] = []
    for part in parts:
        where = part.dest[0] if part.dest else None
        if (cycle := next((k for k in part.keys if _inside(facts, k, where)), None)) is not None:
            return refuse(_CYCLE, item=facts.label(cycle), target=facts.label(where or ""))
        coming = [key for key in part.keys if facts.parent.get(key) != where]
        moves.setdefault(where, []).extend(coming)
        if part.dest != wanted:
            note = _redirection(facts, part, target, stays=not coming)
            notes.append(note)
    if not any(moves.values()):
        return refuse(notes[0].template, **notes[0].params)
    placed = tuple(Move(where, tuple(found)) for where, found in moves.items() if found)
    keys = tuple(key for move in placed for key in move.keys)
    return Decision(True, keys=keys, moves=placed, notes=tuple(notes))


def _inside(facts: MoveFacts, key: str, where: str | None) -> bool:
    return where is not None and (key == where or key in facts.chain(where))


def decide_create(facts: MoveFacts, keys: Iterable[str]) -> Decision:
    """« Créer un (sous-)ensemble depuis la sélection » (ADR 0037) : permis si les éléments sont
    tous hors ensemble (nouvel ensemble) ou tous dans le même ensemble (sous-ensemble). Le nouvel
    ensemble a son propre Std Part : une pièce assemblée à une pièce qui reste dans l'ensemble
    parent reste dans ce parent (``notes``), hors du nouvel ensemble ; refusé s'il n'y a rien à
    créer ou si le rangement n'est pas cohérent. Une pièce assemblée à une pièce hors ensemble est
    rangée avec elle (ADR 0038)."""
    chosen = top_level(facts, keys)
    if (refusal := _movable(facts, chosen)) is not None:
        return refusal
    if len({facts.parent.get(key) for key in chosen}) != 1:
        return refuse(_NOT_SAME)
    parent = facts.parent.get(chosen[0])
    above = [] if parent is None else [parent, *facts.chain(parent)]
    entering: list[str] = []
    notes: list[Note] = []
    for part in plan_parts(facts, chosen, ["", *above], ignore_free=True):
        names = {"piece": facts.label(part.piece), "other": facts.label(part.other)}
        if part.dest == ("", *above):
            entering.extend(part.keys)
        elif part.dest is not None and part.dest == tuple(above):
            notes.append(Note(CREATE_STAYS, {**names, "dest": facts.label(parent or "")}))
        else:
            return refuse(_OUTWARD_NEW, **names)
    if not entering:
        return refuse(CREATE_NOTHING, **notes[0].params)
    return Decision(True, keys=tuple(entering), notes=tuple(notes))


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
