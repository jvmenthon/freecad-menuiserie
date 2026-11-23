# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ce que dessinent les plans (issue #153, ADR 0053) : ensembles, pièces, Std Part, solides
d'autres ateliers et copies par lien (``App::Link``, y compris les tableaux de liens) d'un Std
Part d'ensemble ou d'une pièce. TechDraw place lui-même un lien et ses éléments ; un lien n'est
jamais déplié en objets du document, sinon ses copies se dessineraient à la place de l'original.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.furniture_container import is_std_part, std_part_of
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.machined_part import is_machined_part, machined_part_of
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = [
    "MAX_LINK_DEPTH",
    "NOTHING",
    "document_scope",
    "drawing_sources",
    "link_occurrences",
    "link_target",
    "links_in",
    "workshop_inside",
]

LINK_TYPE: Final = "App::Link"
MAX_LINK_DEPTH: Final = 8  # liens de liens suivis au plus, contre les boucles

NOTHING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan impossible : aucune pièce à dessiner.")
_FOREIGN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan impossible : « {label} » appartient à un autre document."
)


def link_target(obj: DocumentObject) -> DocumentObject | None:
    """Objet que vise le lien ``obj`` (au bout des liens de liens), ``None`` si ce n'est pas un
    lien ou s'il ne vise rien."""
    if getattr(obj, "TypeId", None) != LINK_TYPE or getattr(obj, "LinkedObject", None) is None:
        return None
    target = obj.getLinkedObject(True)
    return None if target is None or target.Name == obj.Name else target


def link_occurrences(obj: DocumentObject) -> int:
    """Nombre de copies que montre le lien ``obj`` : ses éléments s'il est un tableau, sinon 1."""
    count = getattr(obj, "ElementCount", 0)
    return max(1, int(count)) if isinstance(count, int) else 1


def workshop_inside(target: DocumentObject, depth: int = 0) -> list[DocumentObject]:
    """Ensembles et pièces de l'atelier que montre un lien vers ``target`` : ``target`` lui-même
    s'il en est un, sinon ceux de plus haut niveau rangés dans le Std Part ``target`` (ceux de
    ses Std Part et liens imbriqués compris)."""
    if is_furniture(target) or is_timber(target) or is_machined_part(target):
        return [target]
    if depth >= MAX_LINK_DEPTH:
        return []
    inner = link_target(target)
    if inner is not None:
        return workshop_inside(inner, depth + 1)
    if not is_std_part(target):
        return []
    found: list[DocumentObject] = []
    for obj in target.Group:
        if is_furniture(obj) or is_timber(obj):
            if furniture_of(obj) is None:
                found.append(obj)
        elif is_std_part(obj) or link_target(obj) is not None:
            found.extend(workshop_inside(obj, depth + 1))
    return found


def _drawn_link(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` est un lien qui montre des ensembles ou des pièces de l'atelier."""
    target = link_target(obj)
    return target is not None and bool(workshop_inside(target))


def links_in(furniture: DocumentObject) -> list[DocumentObject]:
    """Liens rangés dans le Std Part de ``furniture`` (copies posées dans le meuble)."""
    container = std_part_of(furniture)
    group = container.Group if container is not None else []
    return [obj for obj in group if _drawn_link(obj)]


def _expanded(obj: DocumentObject, seen: set[str]) -> Iterator[DocumentObject]:
    """Objets à projeter pour ``obj`` : les membres d'un ensemble (sous-ensembles et liens de
    son Std Part compris), la pièce usinée d'une pièce de bois assemblée, un lien tel quel,
    sinon l'objet lui-même s'il a une forme."""
    if obj.Name in seen:
        return
    seen.add(obj.Name)
    if is_furniture(obj):
        for member in [*members_of(obj), *links_in(obj)]:
            yield from _expanded(member, seen)
        return
    if link_target(obj) is not None:
        yield obj
        return
    shown = (machined_part_of(obj) or obj) if is_timber(obj) else obj
    shape = getattr(shown, "Shape", None)
    if shown.Name != obj.Name and shown.Name in seen:
        return
    seen.add(shown.Name)
    if obj.TypeId == "App::Part" or (shape is not None and not shape.isNull()):
        yield shown


def _top_level(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` n'est rangé dans aucun groupe ni Std Part."""
    return obj.getParentGroup() is None and obj.getParentGeoFeatureGroup() is None


def document_scope(doc: Document) -> list[DocumentObject]:
    """Ce que dessine le plan quand rien n'est sélectionné : les ensembles de plus haut niveau,
    les pièces de bois hors ensemble et les liens hors de tout conteneur qui en montrent
    (copies d'un meuble), par nom."""
    found = [
        obj
        for obj in doc.Objects
        if ((is_furniture(obj) or is_timber(obj)) and furniture_of(obj) is None)
        or (_drawn_link(obj) and _top_level(obj))
    ]
    return sorted(found, key=lambda obj: obj.Name)


def drawing_sources(doc: Document, objects: Sequence[DocumentObject]) -> list[DocumentObject]:
    """Objets à projeter pour dessiner ``objects`` (ensembles, pièces, Std Part, liens, solides
    d'autres ateliers), sans doublon et dans l'ordre donné. ``ValueError`` traduite pour un objet
    d'un autre document ou s'il n'y a rien à dessiner."""
    for obj in objects:
        if getattr(obj, "Document", None) != doc:
            raise ValueError(translated(_FOREIGN, {"label": str(getattr(obj, "Label", obj))}))
    seen: set[str] = set()
    sources = [shown for obj in objects for shown in _expanded(obj, seen)]
    if not sources:
        raise ValueError(translated(NOTHING))
    return sources
