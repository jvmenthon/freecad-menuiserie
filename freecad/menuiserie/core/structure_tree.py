# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arbre simplifié du panneau « Structure » (ADR 0046, lot 1), calculé sans FreeCAD.

L'arbre est une valeur immuable bâtie par :func:`build_structure` d'après une
:class:`StructureSource` (lecture du document, fournie par ``features/``). Un nœud par ensemble
(les sous-ensembles sont ses enfants), ses pièces (brute et pièce usinée : une seule ligne), puis
un nœud « Assemblages (N) » (assemblages taillés dans le bois et Distances) et un nœud
« Quincaillerie (N) » (objets du commerce, ADR 0033 : voir ``core/structure_hardware``). Les
pièces hors ensemble sont à la racine. Les clés des nœuds sont les noms des objets du document.

Lot 4 : une répétition est une seule ligne « <nom> xN » dépliable en ses copies (qui ne sont plus
montrées à plat), la liste de débit une ligne, et les objets des autres ateliers sont repliés sous
« Autres objets (N) ». Ces lectures viennent d'une source **optionnelle**
(:class:`StructureExtras`).

Garantie : tout objet de l'atelier apparaît exactement une fois. Les assemblages et Distances
sans ensemble de rattachement (pieds ou coulisses sur une pièce hors ensemble, pièces d'ensembles
sans ensemble commun…) forment à la racine un nœud « Assemblages (N) » et un nœud
« Quincaillerie (N) », comme sous un ensemble ; tout objet de l'atelier
resté invisible va sous « Autres objets de l'atelier (N) » plutôt que d'être perdu.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final, Protocol

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

# Gabarit du nœud replié des assemblages ; ``{count}`` est le nombre d'éléments qu'il contient.
JOINTS_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Assemblages ({count})")
# Gabarit du nœud replié de la quincaillerie ; ``{count}`` est le nombre d'objets qu'il contient.
HARDWARE_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Quincaillerie ({count})")
# Nœud replié des objets d'autres ateliers ; ``{count}`` est leur nombre.
OTHERS_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Autres objets ({count})")
# Ligne d'une répétition ; ``{count}`` est le nombre de copies qu'elle déplie.
REPEAT_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "{name} \u00d7{count}")
# Nœud replié des objets de l'atelier qu'aucune autre ligne ne montre ; ``{count}`` est leur nombre.
LEFTOVERS_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Autres objets de l'atelier ({count})")


class NodeKind(Enum):
    """Nature d'un nœud du panneau."""

    FURNITURE = "furniture"
    PIECE = "piece"
    JOINTS = "joints"  # nœud replié « Assemblages (N) »
    JOINT = "joint"  # assemblage taillé dans le bois ou Distance
    HARDWARE = "hardware"  # nœud replié « Quincaillerie (N) »
    HARDWARE_ITEM = "hardware_item"  # pieds, coulisse, LR32, tourillons, faux tenons, biscuits
    REPEAT = "repeat"  # « <nom> xN », dépliable en ses copies
    COPY = "copy"  # copie d'une répétition (jamais glissable hors d'elle)
    CUTLIST = "cutlist"  # liste de débit
    OTHERS = "others"  # nœud replié « Autres objets (N) »
    OTHER = "other"  # objet d'un autre atelier (lecture seule)
    LEFTOVERS = "leftovers"  # nœud replié « Autres objets de l'atelier (N) »
    LEFTOVER = "leftover"  # objet de l'atelier qu'aucune autre ligne ne montre


@dataclass(frozen=True)
class StructureNode:
    """Un nœud de l'arbre. ``key`` est le nom de l'objet du document que la ligne sélectionne
    (pièce usinée à la place de sa brute) ; vide pour les nœuds repliés (« Assemblages (N) »…).
    ``subtype`` précise le type de l'objet pour choisir l'icône (vide : celle du genre)."""

    kind: NodeKind
    label: str
    key: str = ""
    subtype: str = ""  # type précis de l'objet (icône) : valeur de ``JointKind``, « distance »…
    children: tuple[StructureNode, ...] = ()
    expanded: bool = True

    def walk(self) -> list[StructureNode]:
        """Le nœud puis tous ses descendants, en profondeur d'abord."""
        found = [self]
        for child in self.children:
            found.extend(child.walk())
        return found


class StructureSource(Protocol):
    """Lecture du document par le modèle : des noms d'objets et des libellés, rien d'autre."""

    def root_furnitures(self) -> Sequence[str]:
        """Ensembles qui ne sont membres d'aucun autre."""

    def loose_pieces(self) -> Sequence[str]:
        """Pièces qui ne sont membres d'aucun ensemble."""

    def sub_furnitures(self, furniture: str) -> Sequence[str]:
        """Sous-ensembles directs de ``furniture``."""

    def pieces(self, furniture: str) -> Sequence[str]:
        """Pièces directes de ``furniture`` (la pièce usinée à la place de sa brute)."""

    def joints(self, furniture: str) -> Sequence[str]:
        """Assemblages (hors quincaillerie) et Distances de ``furniture``."""

    def hardware(self, furniture: str) -> Sequence[str]:
        """Objets de quincaillerie de ``furniture`` (pieds, coulisses, LR32, tourillons…)."""

    def loose_joints(self) -> Sequence[str]:
        """Assemblages et Distances qu'aucun ensemble ne range (``joints`` ne les rend pour
        aucun ensemble)."""

    def loose_hardware(self) -> Sequence[str]:
        """Objets de quincaillerie qu'aucun ensemble ne range."""

    def subtype(self, key: str) -> str:
        """Type précis de l'objet ``key`` (valeur de ``JointKind``, « distance », « shaped »),
        vide si le genre de ligne suffit."""

    def label(self, key: str) -> str:
        """Libellé affiché pour l'objet ``key`` (vocabulaire du débutant)."""


class StructureExtras(Protocol):
    """Lectures facultatives du lot 4, toutes par nom d'objet. Une source qui n'en fournit pas
    donne le même arbre qu'aux lots 1 à 3."""

    def repetitions(self, container: str | None) -> Sequence[str]:
        """Répétitions rangées dans l'ensemble ``container`` (``None`` : hors ensemble)."""

    def copies(self, repetition: str) -> Sequence[str]:
        """Copies de ``repetition`` (clés de ligne), dans l'ordre d'affichage."""

    def all_copies(self) -> Collection[str]:
        """Copies de toutes les répétitions : elles ne sont montrées que sous leur répétition."""

    def cut_lists(self) -> Sequence[str]:
        """Listes de débit (le tableur n'en fait pas partie)."""

    def other_objects(self) -> Sequence[str]:
        """Objets d'autres ateliers à montrer sous « Autres objets »."""

    def workshop_objects(self) -> Sequence[str]:
        """Clés de ligne de **tous** les objets de l'atelier du document (la pièce usinée à la
        place de sa brute) : ceux que l'arbre ne montre pas vont sous « Autres objets de
        l'atelier »."""


def default_hardware_title(count: int) -> str:
    """Gabarit français (non traduit) du nœud « Quincaillerie (n) »."""
    return HARDWARE_TITLE.format(count=count)


def default_joints_title(count: int) -> str:
    """Gabarit français (non traduit) du nœud « Assemblages (n) »."""
    return JOINTS_TITLE.format(count=count)


def default_others_title(count: int) -> str:
    """Gabarit français (non traduit) du nœud « Autres objets (n) »."""
    return OTHERS_TITLE.format(count=count)


def default_leftovers_title(count: int) -> str:
    """Gabarit français (non traduit) du nœud « Autres objets de l'atelier (n) »."""
    return LEFTOVERS_TITLE.format(count=count)


def default_repeat_label(name: str, count: int) -> str:
    """Gabarit français (non traduit) de la ligne de répétition."""
    return REPEAT_LABEL.format(name=name, count=count)


@dataclass(frozen=True)
class Titles:
    """Textes traduits de l'arbre : nœud « Assemblages (n) », nœud « Autres objets (n) » et ligne
    de répétition (nom, nombre de copies). Par défaut, les gabarits français sans traduction."""

    joints: Callable[[int], str] = default_joints_title
    others: Callable[[int], str] = default_others_title
    repeat: Callable[[str, int], str] = default_repeat_label
    leftovers: Callable[[int], str] = default_leftovers_title
    hardware: Callable[[int], str] = default_hardware_title


def build_structure(
    source: StructureSource,
    joints_title: Callable[[int], str],
    extras: StructureExtras | None = None,
    titles: Titles | None = None,
) -> tuple[StructureNode, ...]:
    """Racines de l'arbre : les ensembles de plus haut niveau, les pièces hors ensemble, puis (avec
    ``extras``) les répétitions, les listes de débit et le nœud « Autres objets ».
    ``joints_title(n)`` donne le texte traduit du nœud « Assemblages (n) » ; ``titles`` les autres
    (son ``joints`` est alors ignoré)."""
    used = titles if titles is not None else Titles(joints=joints_title)
    return _Builder(source, extras, used).roots()


class _Builder:
    """Construit l'arbre d'une source ; ``seen`` coupe un cycle éventuel de sous-ensembles."""

    def __init__(
        self, source: StructureSource, extras: StructureExtras | None, titles: Titles
    ) -> None:
        self._source = source
        self._extras = extras
        self._titles = titles
        self._hidden = frozenset(extras.all_copies()) if extras is not None else frozenset()
        self._seen: set[str] = set()

    def roots(self) -> tuple[StructureNode, ...]:
        roots = [self._furniture(key) for key in self._visible(self._source.root_furnitures())]
        roots.extend(self._piece(key) for key in self._visible(self._source.loose_pieces()))
        roots.extend(self._joints(self._source.loose_joints()))
        roots.extend(self._hardware(self._source.loose_hardware()))
        roots.extend(self._repetitions(None))
        roots.extend(self._cut_lists())
        roots.extend(self._leftovers(roots))
        roots.extend(self._others())
        return tuple(roots)

    def _visible(self, keys: Sequence[str]) -> list[str]:
        """``keys`` sans les copies de répétition (montrées sous leur répétition)."""
        return [key for key in keys if key not in self._hidden]

    def _leaf(self, kind: NodeKind, key: str) -> StructureNode:
        return StructureNode(kind, self._source.label(key), key, self._source.subtype(key))

    def _piece(self, key: str) -> StructureNode:
        return self._leaf(NodeKind.PIECE, key)

    def _furniture(self, key: str) -> StructureNode:
        """Nœud de l'ensemble ``key`` : sous-ensembles, pièces, répétitions, puis les
        assemblages repliés."""
        source = self._source
        self._seen.add(key)
        children = [
            self._furniture(sub)
            for sub in self._visible(source.sub_furnitures(key))
            if sub not in self._seen
        ]
        children.extend(self._piece(piece) for piece in self._visible(source.pieces(key)))
        children.extend(self._repetitions(key))
        children.extend(self._joints(source.joints(key)))
        children.extend(self._hardware(source.hardware(key)))
        return StructureNode(NodeKind.FURNITURE, source.label(key), key, children=tuple(children))

    def _joints(self, joints: Sequence[str]) -> list[StructureNode]:
        """Nœud replié « Assemblages (N) » de ``joints``, absent s'il n'y en a pas."""
        return self._group(joints, NodeKind.JOINTS, NodeKind.JOINT, self._titles.joints)

    def _hardware(self, items: Sequence[str]) -> list[StructureNode]:
        """Nœud replié « Quincaillerie (N) » de ``items``, absent s'il n'y en a pas."""
        return self._group(items, NodeKind.HARDWARE, NodeKind.HARDWARE_ITEM, self._titles.hardware)

    def _group(
        self,
        keys: Sequence[str],
        group: NodeKind,
        leaf: NodeKind,
        title: Callable[[int], str],
    ) -> list[StructureNode]:
        if not keys:
            return []
        leaves = tuple(self._leaf(leaf, key) for key in keys)
        return [StructureNode(group, title(len(leaves)), "", children=leaves, expanded=False)]

    def _repetitions(self, container: str | None) -> list[StructureNode]:
        """Une ligne « <nom> xN » par répétition, repliée sur ses copies."""
        if self._extras is None:
            return []
        nodes = []
        for key in self._extras.repetitions(container):
            copies = tuple(
                StructureNode(NodeKind.COPY, self._source.label(copy), copy)
                for copy in self._extras.copies(key)
            )
            label = self._titles.repeat(self._source.label(key), len(copies))
            nodes.append(
                StructureNode(NodeKind.REPEAT, label, key, children=copies, expanded=False)
            )
        return nodes

    def _cut_lists(self) -> list[StructureNode]:
        if self._extras is None:
            return []
        return [
            StructureNode(NodeKind.CUTLIST, self._source.label(key), key)
            for key in self._extras.cut_lists()
        ]

    def _others(self) -> list[StructureNode]:
        """Nœud replié des objets d'autres ateliers, absent s'il n'y en a pas."""
        keys = self._extras.other_objects() if self._extras is not None else ()
        if not keys:
            return []
        leaves = tuple(StructureNode(NodeKind.OTHER, self._source.label(k), k) for k in keys)
        title = self._titles.others(len(leaves))
        return [StructureNode(NodeKind.OTHERS, title, "", children=leaves, expanded=False)]

    def _leftovers(self, roots: Sequence[StructureNode]) -> list[StructureNode]:
        """Objets de l'atelier que ``roots`` ne montre pas, repliés ; absent s'il n'y en a pas."""
        if self._extras is None:
            return []
        shown = {node.key for root in roots for node in root.walk() if node.key}
        keys = [key for key in dict.fromkeys(self._extras.workshop_objects()) if key not in shown]
        if not keys:
            return []
        leaves = tuple(self._leaf(NodeKind.LEFTOVER, k) for k in keys)
        title = self._titles.leftovers(len(leaves))
        return [StructureNode(NodeKind.LEFTOVERS, title, "", children=leaves, expanded=False)]
