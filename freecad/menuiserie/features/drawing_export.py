# SPDX-License-Identifier: LGPL-2.1-or-later
"""Choix des plans à exporter en PDF (issue #153, retour de jv du 24/11, maquette B).

Le panneau « Exporter en PDF » montre les plans de l'ouvrage (existants ou à créer), les autres
pages, puis l'arbre des ensembles où chaque pièce dit si son plan existe. Ce module, sans Qt,
lit l'état du document (quelle page dessine quelle pièce) et rassemble les pages à exporter en
créant d'abord les plans qui manquent.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.drawing import (
    KIND,
    PART_KIND,
    DrawingOptions,
    document_scope,
    is_page,
    is_workshop_drawing,
    make_overall_drawing,
    owned_names,
)
from freecad.menuiserie.features.drawing_exploded import EXPLODED_KIND, make_exploded_drawing
from freecad.menuiserie.features.drawing_parts import (
    blanks_of,
    make_part_drawings,
    part_groups,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.machined_part import machined_part_of

__all__ = [
    "MAX_EXPORT_PAGES",
    "TOO_MANY_PAGES",
    "ExportState",
    "PlanKind",
    "export_state",
    "pages_to_export",
]


class PlanKind(str, Enum):
    """Plan de l'ouvrage que l'export peut créer."""

    OVERALL = "overall"
    EXPLODED = "exploded"


_KIND_OF_PAGE: Final = {"": PlanKind.OVERALL, EXPLODED_KIND: PlanKind.EXPLODED}  # ``drawing.KIND``
_NOT_DRAWN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export impossible : le plan de « {label} » n'a pas pu être créé."
)
MAX_EXPORT_PAGES: Final = 200  # pages d'un export au plus (plans créés compris)
TOO_MANY_PAGES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export impossible : plus de {limit} pages ; cochez moins de plans."
)


@dataclass(frozen=True)
class ExportState:
    """État des plans du document : page de chaque pièce (par nom de brute, la même pour des
    pièces identiques), groupe de pièces identiques de chaque brute, pages qui ne sont pas des
    plans de pièce rattachés (ouvrage, vue éclatée, pages d'autres origines) et plans de
    l'ouvrage déjà faits."""

    page_of: dict[str, DocumentObject] = field(default_factory=dict)
    group_of: dict[str, int] = field(default_factory=dict)
    other_pages: list[DocumentObject] = field(default_factory=list)
    kinds: frozenset[PlanKind] = frozenset()

    def blank_pages(self, blanks: Sequence[DocumentObject]) -> list[DocumentObject]:
        """Pages existantes des pièces ``blanks``, sans doublon, dans leur ordre."""
        found = {page.Name: page for blank in blanks if (page := self.page_of.get(blank.Name))}
        return list(found.values())

    def parts_of(self, page: DocumentObject) -> list[str]:
        """Noms des pièces (brutes) dont ``page`` est le plan."""
        return [name for name, found in self.page_of.items() if found.Name == page.Name]

    def missing(self, blanks: Sequence[DocumentObject]) -> list[DocumentObject]:
        """Pièces de ``blanks`` sans plan."""
        return [blank for blank in blanks if blank.Name not in self.page_of]

    def plans_to_create(self, blanks: Sequence[DocumentObject]) -> int:
        """Plans de pièce à créer pour ``blanks`` : un par groupe de pièces identiques, un par
        pièce hors groupe."""
        missing = self.missing(blanks)
        groups = {self.group_of[blank.Name] for blank in missing if blank.Name in self.group_of}
        return len(groups) + sum(blank.Name not in self.group_of for blank in missing)


def _front_sources(page: DocumentObject) -> list[str]:
    """Noms des objets que dessine la vue de face d'un plan de pièce de l'atelier."""
    owned = set(owned_names(page))
    for view in getattr(page, "Views", []):
        if view.Name in owned and hasattr(view, "Source"):
            return [obj.Name for obj in view.Source]
    return []


def export_state(doc: Document) -> ExportState:
    """Lit les pages et les pièces de ``doc``. Une pièce a un plan si une page de plan de pièce
    de l'atelier dessine elle, sa pièce usinée ou une pièce identique."""
    pages = [obj for obj in doc.Objects if is_page(obj)]
    drawn: dict[str, DocumentObject] = {}
    kinds: set[PlanKind] = set()
    for page in pages:
        kind = str(getattr(page, KIND, "")) if is_workshop_drawing(page) else None
        if kind == PART_KIND:
            drawn.update(dict.fromkeys(_front_sources(page), page))
        elif kind in _KIND_OF_PAGE:
            kinds.add(_KIND_OF_PAGE[kind])
    try:
        groups = part_groups(doc, [])
    except ValueError:  # document démesuré : aucun plan de pièce rattaché
        groups = []
    page_of: dict[str, DocumentObject] = {}
    group_of: dict[str, int] = {}
    for index, members in enumerate(groups):
        shown = [(machined_part_of(blank) or blank).Name for blank in members]
        page = next((drawn[name] for name in shown if name in drawn), None)
        for blank in members:
            group_of[blank.Name] = index
            if page is not None:
                page_of[blank.Name] = page
    used = {page.Name for page in page_of.values()}
    others = [page for page in pages if page.Name not in used]
    return ExportState(page_of, group_of, others, frozenset(kinds))


def pages_to_export(
    doc: Document,
    pages: Sequence[DocumentObject],
    parts: Sequence[DocumentObject],
    kinds: Sequence[PlanKind] = (),
    options: DrawingOptions | None = None,
) -> list[DocumentObject]:
    """Pages à exporter, dans l'ordre : plans de l'ouvrage à créer (``kinds``), ``pages``
    existantes, puis les plans des pièces que montrent ``parts`` (ensembles, pièces, copies par
    lien), créés d'abord s'ils manquent. ``ValueError`` traduite
    si un plan ne peut pas être fait ou s'il y aurait plus de ``MAX_EXPORT_PAGES`` pages."""
    blanks = blanks_of(parts)
    state = export_state(doc) if blanks else ExportState()
    total = len(kinds) + len(pages) + len(state.blank_pages(blanks)) + state.plans_to_create(blanks)
    if total > MAX_EXPORT_PAGES:  # refus avant toute création (document piégé)
        raise ValueError(translated(TOO_MANY_PAGES, {"limit": str(MAX_EXPORT_PAGES)}))
    found: list[DocumentObject] = []
    if PlanKind.OVERALL in kinds:
        found.append(make_overall_drawing(doc, document_scope(doc), options))
    if PlanKind.EXPLODED in kinds:
        found.append(make_exploded_drawing(doc, document_scope(doc), options))
    found += pages
    if blanks:
        if state.missing(blanks):
            make_part_drawings(doc, state.missing(blanks), options)
            state = export_state(doc)
        if state.missing(blanks):  # une pièce que son nouveau plan ne rattache pas
            label = str(state.missing(blanks)[0].Label)
            raise ValueError(translated(_NOT_DRAWN, {"label": label}))
        found += state.blank_pages(blanks)
    unique = {page.Name: page for page in found}
    return list(unique.values())
