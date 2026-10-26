# SPDX-License-Identifier: LGPL-2.1-or-later
"""Collecte de la liste de débit : document ou sélection → entrées de débit (J2c, D1 à D8).

Visiteur du document qui délègue à une petite table de lecteurs par type d'objet (pièce, pièce
usinée, ensemble, lien, conteneur). Une brute est comptée une fois par chemin d'accès direct ;
chaque ``App::Link`` ajoute une occurrence de sa cible (fois ``ElementCount`` pour un tableau),
liens imbriqués compris. Lecture seule : aucune écriture dans le document, aucun recalcul.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Final

from freecad.menuiserie.core.cutlist import CutEntry, CutList, Hardware, build_cut_list
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.notice import Notice
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.cutlist_parts import (
    CollectNoticeKind,
    dowel_hardware,
    entry_of,
    is_dowel_joint,
    notice,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.wood_part import is_wood_part

__all__ = [
    "Collected",
    "checked_objects",
    "collect",
    "collect_cut_list",
    "cut_list_of",
    "is_source",
]

MAX_DEPTH: Final = 32  # liens et conteneurs imbriqués, contre les boucles
MAX_VISITS: Final = 20_000  # objets lus au plus par collecte, contre les documents hostiles
MAX_QUANTITY: Final = 1_000_000  # occurrences d'une brute (et multiplicateur d'un chemin) au plus
_LINK_ELEMENT: Final = "App::LinkElement"  # compté par le tableau de liens qui le porte
_OTHER_DOCUMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » appartient à un autre document : liste de débit refusée."
)
_Reader = Callable[[DocumentObject, int, set[str], int], None]


@dataclass(frozen=True)
class Collected:
    """Résultat de la collecte : entrées, fournitures et avertissements."""

    entries: tuple[CutEntry, ...]
    hardware: tuple[Hardware, ...]
    notices: tuple[Notice, ...]
    sources: tuple[DocumentObject, ...] = ()  # objets lus : ce dont dépend une liste vivante


def _is_link(obj: DocumentObject) -> bool:
    """Lien qui vise un objet (un groupe de liens, sans cible, est un conteneur)."""
    return "LinkedObject" in obj.PropertiesList and obj.LinkedObject is not None


def _is_container(obj: DocumentObject) -> bool:
    return "Group" in obj.PropertiesList or "ElementList" in obj.PropertiesList


def is_source(obj: DocumentObject) -> bool:
    """Vrai si la collecte lit ``obj`` dès qu'il est dans la portée : pièce, pièce en bois, pièce
    usinée, ensemble, lien ou conteneur (un élément de tableau de liens est lu par son tableau). Les
    assemblages par tourillons n'en sont pas : ils ne sont lus que si leurs deux pièces sont dans
    la portée, et en ajouter un modifie leurs pièces usinées."""
    if obj.TypeId == _LINK_ELEMENT:
        return False
    return (
        is_wood_part(obj)
        or is_shaped_part(obj)
        or is_machined_part(obj)
        or is_furniture(obj)
        or _is_link(obj)
        or _is_container(obj)
    )


class _Walk:
    """Parcours : brutes vues (par nom) avec leur nombre d'occurrences, objets lus et
    avertissements."""

    def __init__(self) -> None:
        self.blanks: dict[str, DocumentObject] = {}
        self.read: dict[str, DocumentObject] = {}
        self.counts: dict[str, int] = defaultdict(int)
        self.notices: list[Notice] = []
        self.visits = 0  # visites faites, contre MAX_VISITS
        self._truncated = False
        self._capped = False
        # Prédicats passés comme fonctions (Semgrep les prend à tort pour des attributs).
        self._readers: tuple[tuple[Callable[[DocumentObject], bool], _Reader], ...] = (
            # nosemgrep: python.lang.maintainability.is-function-without-parentheses
            (is_wood_part, self._part),
            # nosemgrep: python.lang.maintainability.is-function-without-parentheses
            (is_shaped_part, self._part),
            # nosemgrep: python.lang.maintainability.is-function-without-parentheses
            (is_machined_part, self._machined),
            # nosemgrep: python.lang.maintainability.is-function-without-parentheses
            (is_furniture, self._furniture),
            (_is_link, self._link),
            (_is_container, self._container),
        )

    def visit(self, obj: DocumentObject, times: int, seen: set[str], depth: int) -> None:
        """Lit ``obj`` et ce qu'il contient, ``times`` fois ; ``seen`` : objets déjà lus par ce
        chemin d'accès (un objet atteint deux fois par le même chemin compte une fois). Au-delà
        de ``MAX_VISITS`` visites (liens multiples imbriqués : le nombre de chemins est
        exponentiel), la lecture s'arrête avec un avertissement « liste tronquée »."""
        if self.visits >= MAX_VISITS:
            if not self._truncated:
                self._truncated = True
                self.notices.append(notice(CollectNoticeKind.TRUNCATED, obj, limit=str(MAX_VISITS)))
            return
        self.visits += 1
        if obj.Name in seen:
            return
        seen.add(obj.Name)
        if depth > MAX_DEPTH:
            self.notices.append(notice(CollectNoticeKind.LINK_TOO_DEEP, obj))
            return
        for matches, read in self._readers:
            if matches(obj):
                self.read.setdefault(obj.Name, obj)
                read(obj, times, seen, depth)
                return

    def _part(self, obj: DocumentObject, times: int, seen: set[str], depth: int) -> None:
        del seen, depth
        self.blanks[obj.Name] = obj
        self.counts[obj.Name] = self._capped_quantity(obj, self.counts[obj.Name] + times)

    def _capped_quantity(self, obj: DocumentObject, quantity: int) -> int:
        """``quantity`` plafonnée à ``MAX_QUANTITY`` (avertissement une seule fois)."""
        if quantity <= MAX_QUANTITY:
            return quantity
        if not self._capped:
            self._capped = True
            self.notices.append(
                notice(CollectNoticeKind.QUANTITY_CAPPED, obj, limit=str(MAX_QUANTITY))
            )
        return MAX_QUANTITY

    def _machined(self, obj: DocumentObject, times: int, seen: set[str], depth: int) -> None:
        """Pièce usinée : comptée par sa brute (absente : rien)."""
        blank = getattr(obj, "Base", None)
        if blank is not None:
            self.visit(blank, times, seen, depth + 1)

    def _furniture(self, obj: DocumentObject, times: int, seen: set[str], depth: int) -> None:
        for member in members_of(obj):
            self.visit(member, times, seen, depth + 1)

    def _container(self, obj: DocumentObject, times: int, seen: set[str], depth: int) -> None:
        """Std Part, groupe, groupe de liens : leurs enfants, récursivement."""
        children = [*getattr(obj, "Group", ()), *getattr(obj, "ElementList", ())]
        for child in children:
            self.visit(child, times, seen, depth + 1)

    def _link(self, obj: DocumentObject, times: int, seen: set[str], depth: int) -> None:
        """Lien : une occurrence de sa cible (fois ``ElementCount``), lue par un chemin neuf
        puisque l'original, lui, compte aussi. Un lien vers un lien est suivi."""
        del seen
        target = obj.LinkedObject
        count = int(obj.ElementCount) if "ElementCount" in obj.PropertiesList else 0
        multiplied = self._capped_quantity(obj, times * max(1, count))
        self.visit(target, multiplied, set(), depth + 1)


def _roots(doc: Document, objects: Sequence[DocumentObject] | None) -> list[DocumentObject]:
    if objects:
        return list(objects)
    return [obj for obj in doc.Objects if obj.TypeId != _LINK_ELEMENT]


def _hardware(doc: Document, walk: _Walk, notices: list[Notice]) -> list[Hardware]:
    """Tourillons des assemblages dont les deux pièces sont dans la portée, autant de fois que
    les deux pièces sont vues ensemble (liens compris)."""
    found = []
    for joint in doc.Objects:
        if not is_dowel_joint(joint):
            continue
        host, guest = joint.HostPart, joint.GuestPart
        if host is None or guest is None:
            continue
        times = min(walk.counts.get(host.Name, 0), walk.counts.get(guest.Name, 0))
        if not times:
            continue
        walk.read.setdefault(joint.Name, joint)
        item = dowel_hardware(joint, times, notices)
        if item is not None:
            found.append(item)
    return found


def collect(doc: Document, objects: Sequence[DocumentObject] | None = None) -> Collected:
    """Entrées de débit du document ``doc`` ou, si ``objects`` est donné et non vide, de ces
    objets (pièces, pièces usinées, ensembles, Std Part, groupes, liens), avec les fournitures
    (tourillons) et les avertissements. Une entrée par brute, quantité = nombre d'occurrences."""
    walk = _Walk()
    direct: set[str] = set()
    for root in _roots(doc, objects):
        walk.visit(root, 1, direct, 0)
    notices = walk.notices
    entries = []
    for name in sorted(walk.blanks):
        entry = entry_of(walk.blanks[name], walk.counts[name], notices)
        if entry is not None:
            entries.append(entry)
    hardware = _hardware(doc, walk, notices)
    read = (walk.read[name] for name in sorted(walk.read))
    sources = [obj for obj in read if obj.TypeId != _LINK_ELEMENT]
    return Collected(tuple(entries), tuple(hardware), tuple(notices), tuple(sources))


def checked_objects(
    doc: Document, objects: Sequence[DocumentObject] | None
) -> Sequence[DocumentObject] | None:
    """``objects`` s'ils sont tous de ``doc`` (``None`` ou vide : tout le document) ;
    ``ValueError`` traduite pour un objet d'un autre document."""
    for obj in objects or ():
        if obj.Document != doc:
            raise ValueError(translated(_OTHER_DOCUMENT, {"label": quoted_value(obj.Label)}))
    return objects or None


def collect_cut_list(
    doc: Document, objects: Sequence[DocumentObject] | None = None
) -> tuple[CutList, tuple[DocumentObject, ...]]:
    """Liste de débit de ``doc`` ou de ``objects`` et objets lus pour la calculer : collecte,
    regroupement et totaux, les avertissements de la collecte avant ceux du regroupement.
    Lecture seule ; ``ValueError`` traduite pour un objet d'un autre document ou une entrée
    invalide."""
    chosen = checked_objects(doc, objects)
    collected = collect(doc, chosen)
    with translated_errors():
        cut_list = build_cut_list(collected.entries, collected.hardware)
    warnings = (*collected.notices, *cut_list.warnings)
    return replace(cut_list, warnings=warnings), collected.sources


def cut_list_of(doc: Document, objects: Sequence[DocumentObject] | None = None) -> CutList:
    """Liste de débit de ``doc`` ou de ``objects`` (:func:`collect_cut_list`, sans les objets
    lus). Lecture seule ; ``ValueError`` traduite pour un objet d'un autre document ou une
    entrée invalide."""
    return collect_cut_list(doc, objects)[0]
