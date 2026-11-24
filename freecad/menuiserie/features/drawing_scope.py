# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ce que dessinent les plans (issue #153, ADR 0053) : ensembles, pièces, Std Part, solides
d'autres ateliers et copies par lien (``App::Link``, y compris les tableaux de liens) d'un Std
Part d'ensemble ou d'une pièce. TechDraw place lui-même un lien et ses éléments ; un lien n'est
jamais déplié en objets du document, sinon ses copies se dessineraient à la place de l'original.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
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
    "MAX_LINK_ELEMENTS",
    "NOTHING",
    "LinkWalk",
    "document_scope",
    "drawing_sources",
    "link_occurrences",
    "link_target",
    "links_in",
    "object_key",
    "workshop_inside",
]

LINK_TYPE: Final = "App::Link"
MAX_LINK_DEPTH: Final = 8  # liens de liens dépliés au plus pour compter les pièces
MAX_LINK_VISITS: Final = 10_000  # cibles de liens lues au plus par parcours (document piégé)
MAX_LINK_ELEMENTS: Final = 10_000  # copies d'un tableau de liens au plus

NOTHING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan impossible : aucune pièce à dessiner.")
_TOO_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan impossible : « {label} » montre plus de {limit} copies."
)
_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan impossible : plus de {limit} liens imbriqués à lire."
)
_FOREIGN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan impossible : « {label} » appartient à un autre document."
)


@dataclass
class LinkWalk:
    """Mémoire d'un parcours des liens : ce que montre chaque cible déjà vue (par document et
    nom), celles en cours (une cible qui se montre elle-même, directement ou non, coupe la
    boucle) et le nombre de cibles lues, borné contre les documents piégés."""

    shown: dict[tuple[str, str], list[DocumentObject]] = field(default_factory=dict)
    running: set[tuple[str, str]] = field(default_factory=set)
    visits: int = 0
    memo: dict[tuple[str, ...], object] = field(default_factory=dict)  # pour les appelants


def object_key(obj: DocumentObject) -> tuple[str, str]:
    """Clé d'un objet, unique entre documents."""
    doc = getattr(obj, "Document", None)
    return (str(getattr(doc, "Name", doc)), str(obj.Name))


def link_target(obj: DocumentObject) -> DocumentObject | None:
    """Objet que vise directement le lien ``obj`` (un autre lien, un Std Part, une pièce, dans
    ce document ou un autre), ``None`` si ce n'est pas un lien, s'il ne vise rien ou se vise
    lui-même. Un tableau de liens vise sa cible (``getLinkedObject`` rendrait le tableau)."""
    if getattr(obj, "TypeId", None) != LINK_TYPE:
        return None
    linked = getattr(obj, "LinkedObject", None)
    if isinstance(linked, tuple):  # lien vers un sous-élément : (objet, sous-nom)
        linked = linked[0] if linked else None
    if linked is None or object_key(linked) == object_key(obj):
        return None
    return linked


def link_occurrences(obj: DocumentObject) -> int:
    """Nombre de copies que montre le lien ``obj`` : ses éléments s'il est un tableau, sinon 1.
    ``ValueError`` traduite au-delà de ``MAX_LINK_ELEMENTS`` (document piégé)."""
    count = getattr(obj, "ElementCount", 0)
    count = max(1, int(count)) if isinstance(count, int) else 1
    if count > MAX_LINK_ELEMENTS:
        raise ValueError(
            translated(_TOO_MANY, {"label": str(obj.Label), "limit": str(MAX_LINK_ELEMENTS)})
        )
    return count


def workshop_inside(target: DocumentObject, walk: LinkWalk | None = None) -> list[DocumentObject]:
    """Ce que montre un lien vers ``target`` : ``target`` lui-même si c'est un ensemble, une
    pièce de l'atelier ou un lien qui en montre, sinon ceux du Std Part ``target`` dont
    l'ensemble n'y est pas aussi (un sous-ensemble lié seul est gardé), ceux de ses Std Part
    imbriqués et ses liens imbriqués tels quels (chacun apporte son nombre de copies)."""
    if is_furniture(target) or is_timber(target) or is_machined_part(target):
        return [target]
    walk = walk if walk is not None else LinkWalk()
    key = object_key(target)
    if key in walk.shown:
        return walk.shown[key]
    if key in walk.running:
        return []  # boucle : la cible se montre elle-même
    walk.visits += 1
    if walk.visits > MAX_LINK_VISITS:
        raise ValueError(translated(_TOO_DEEP, {"limit": str(MAX_LINK_VISITS)}))
    walk.running.add(key)
    try:
        if link_target(target) is not None:
            found = [target] if _drawn_link(target, walk) else []
        elif is_std_part(target):
            present: set[str] = set()
            _collect_names(target, present)
            found = _inside(target, present, walk)
        else:
            found = []
    finally:
        walk.running.discard(key)
    walk.shown[key] = found
    return found


def _collect_names(container: DocumentObject, names: set[str]) -> None:
    """Noms des objets rangés dans ``container`` et ses Std Part imbriqués."""
    for obj in container.Group:
        names.add(obj.Name)
        if is_std_part(obj):
            _collect_names(obj, names)


def _inside(container: DocumentObject, present: set[str], walk: LinkWalk) -> list[DocumentObject]:
    found: list[DocumentObject] = []
    for obj in container.Group:
        if is_furniture(obj) or is_timber(obj):
            parent = furniture_of(obj)
            if parent is None or parent.Name not in present:
                found.append(obj)
        elif is_std_part(obj):
            found.extend(_inside(obj, present, walk))
        elif _drawn_link(obj, walk):
            found.append(obj)
    return found


def _drawn_link(obj: DocumentObject, walk: LinkWalk | None = None) -> bool:
    """Vrai si ``obj`` est un lien qui montre des ensembles ou des pièces de l'atelier."""
    target = link_target(obj)
    return target is not None and bool(workshop_inside(target, walk))


def links_in(furniture: DocumentObject, walk: LinkWalk | None = None) -> list[DocumentObject]:
    """Liens rangés dans le Std Part de ``furniture`` (copies posées dans le meuble)."""
    container = std_part_of(furniture)
    group = container.Group if container is not None else []
    return [obj for obj in group if _drawn_link(obj, walk)]


def _expanded(obj: DocumentObject, seen: set[str], walk: LinkWalk) -> Iterator[DocumentObject]:
    """Objets à projeter pour ``obj`` : les membres d'un ensemble (sous-ensembles et liens de
    son Std Part compris), la pièce usinée d'une pièce de bois assemblée, un lien tel quel,
    sinon l'objet lui-même s'il a une forme."""
    if obj.Name in seen:
        return
    seen.add(obj.Name)
    if is_furniture(obj):
        for member in [*members_of(obj), *links_in(obj, walk)]:
            yield from _expanded(member, seen, walk)
        return
    if link_target(obj) is not None:
        link_occurrences(obj)  # refus d'un tableau démesuré avant toute forme
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
    walk = LinkWalk()
    found = [
        obj
        for obj in doc.Objects
        if ((is_furniture(obj) or is_timber(obj)) and furniture_of(obj) is None)
        or (_top_level(obj) and _drawn_link(obj, walk))
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
    walk = LinkWalk()
    sources = [shown for obj in objects for shown in _expanded(obj, seen, walk)]
    if not sources:
        raise ValueError(translated(NOTHING))
    return sources
