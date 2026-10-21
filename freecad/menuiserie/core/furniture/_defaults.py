# SPDX-License-Identifier: LGPL-2.1-or-later
"""Options « fixe » par défaut des membres qui entrent dans l'ensemble (J4a, critères F3, F4).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Chaîne de règles d'une
distance, première qui s'applique : **bord** (``fixed_by_default``) ; **contact** avec une face
d'un autre membre qui suit le bord de son propre côté, de proche en proche ; sinon non fixe.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from freecad.menuiserie.core.contact import Contact, classify
from freecad.menuiserie.core.furniture._follow import followed_edge
from freecad.menuiserie.core.furniture._model import Edge, FurnitureAxis, FurnitureBox, Member
from freecad.menuiserie.core.furniture._spans import Spans, distances, frame_block, square_spans
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM

# Face d'un membre (bord de son côté) en contact avec la face d'un autre membre (clé, côté).
_Touch = tuple[Edge, str, Edge]


def fixed_by_default(distance: float) -> bool:
    """Option par défaut d'une distance au bord de l'ensemble (règle « bord »).

    **Q7, question ouverte** : la spécification applique la recommandation ★, « une distance
    non nulle n'est pas fixe par défaut ». Seule une distance nulle (≤ ``CONTACT_TOLERANCE_MM``)
    est fixe, quelle que soit la valeur des autres (1 mm, 40 mm). Cette fonction est le seul
    endroit à changer si jv répond autrement (« Oui » : ``return True``).
    """
    return distance <= CONTACT_TOLERANCE_MM


def _touches(key: str, frame: Spans, others: Mapping[str, Spans]) -> list[_Touch]:
    touches: list[_Touch] = []
    for other_key in sorted(others):
        if other_key == key:
            continue
        relation = classify(frame_block(frame), frame_block(others[other_key]))
        if isinstance(relation, Contact):
            face = relation.host_face
            side = Edge.of(FurnitureAxis.of(face.index), face.sign > 0)
            touches.append((side, other_key, side.opposite()))
    return touches


def default_fixed(box: FurnitureBox, members: Sequence[Member]) -> Mapping[str, frozenset[Edge]]:
    """Options par défaut des membres dont ``fixed`` est ``None`` (les autres servent de
    contexte et gardent les leurs) ; résultat indépendant de l'ordre des membres.

    Un membre qui n'est pas d'équerre n'a aucune distance fixe.
    """
    ordered = sorted(members, key=lambda member: member.key)
    spans = {m.key: s for m in ordered if (s := square_spans(m)) is not None}
    edge_distance = {key: distances(frame, box) for key, frame in spans.items()}
    fixed: dict[str, frozenset[Edge]] = {}
    for member in ordered:
        near = {e for e, d in edge_distance.get(member.key, {}).items() if fixed_by_default(d)}
        fixed[member.key] = member.fixed if member.fixed is not None else frozenset(near)
    pending = [m.key for m in ordered if m.fixed is None and m.key in spans]
    touches = {key: _touches(key, spans[key], spans) for key in pending}
    changed = True
    while changed:
        changed = False
        for key in pending:
            for side, other, other_side in touches[key]:
                followed = followed_edge(
                    fixed[other], spans[other][side.axis], other_side, edge_distance[other]
                )
                if side not in fixed[key] and followed is side:
                    fixed[key] = fixed[key] | {side}
                    changed = True
    return {member.key: fixed[member.key] for member in members if member.fixed is None}


def with_default_options(box: FurnitureBox, members: Sequence[Member]) -> tuple[Member, ...]:
    """Membres dont les options manquantes (``fixed`` = ``None``) sont remplacées par les
    options par défaut ; les autres sont rendus tels quels."""
    defaults = default_fixed(box, members)
    return tuple(
        replace(member, fixed=defaults[member.key]) if member.key in defaults else member
        for member in members
    )
