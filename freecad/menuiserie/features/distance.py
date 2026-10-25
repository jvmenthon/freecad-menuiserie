# SPDX-License-Identifier: LGPL-2.1-or-later
"""Distance gardée entre deux pièces d'un ensemble (DI-c, ADR 0022, critères F5 à F7).

Une Distance (``App::FeaturePython`` sans forme, nom interne ``Distance``) retient deux pièces
(liens ``PieceA`` et ``PieceB``), l'axe de l'ensemble (``Axis``), le côté de chaque pièce sur cet
axe (``SideA``, ``SideB`` : début ou fin de son étendue) et la distance ``Value``. Aucun nom
topologique n'est retenu. Les règles des rangées (:mod:`freecad.menuiserie.core.furniture`) la
lisent comme un bloc rigide virtuel ; les pièces voisines citent ``Name.Value`` dans leurs
expressions : changer ``Value`` ne fait appel à aucun code de l'atelier (ADR 0009).

Les liens sont des ``App::PropertyLinkHidden`` : un lien ordinaire ferait dépendre la Distance des
pièces alors que celles-ci dépendent d'elle par leurs expressions (cycle refusé par FreeCAD) ;
un lien caché est réécrit par « Dupliquer » et ne déclenche pas la boîte « objets référencés » de
la suppression. La Distance est supprimée avec l'une de ses pièces ou son ensemble
(:func:`remove_touching`).

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe ``Distance`` et
les noms des propriétés sont écrits dans les documents ; ils ne changent jamais.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import ClassVar, Final

from freecad.menuiserie.core.furniture import FurnitureAxis, KeptGap
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import (
    HIDDEN,
    READ_ONLY,
    Document,
    DocumentObject,
    StatelessProxy,
    proxy_is,
)
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.schema import LENGTH, PropertySpec, version_spec

__all__ = [
    "AXES",
    "DISTANCE_PROPERTIES",
    "OBJECT_NAME",
    "SIDES",
    "Distance",
    "create_distance",
    "distances_of",
    "distances_touching",
    "is_distance",
    "kept_gap_of",
    "remove_touching",
]

OBJECT_NAME: Final = "Distance"
MODEL_VERSION: Final = 1
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Distance")
LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Distance : {a} \N{EN DASH} {b}")
GROUP: Final = "Distance"
AXES: Final = ("X", "Y", "Z")  # axes de l'ensemble : largeur, profondeur, hauteur
SIDES: Final = ("Start", "End")  # début ou fin de l'étendue de la pièce sur l'axe

DISTANCE_PROPERTIES: Final = (
    PropertySpec(
        "PieceA",
        "App::PropertyLinkHidden",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Première pièce, du côté de laquelle la distance est mesurée."
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "PieceB",
        "App::PropertyLinkHidden",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Seconde pièce."),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Axis",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Axe de l'ensemble sur lequel la distance est mesurée : X (largeur), Y (profondeur) "
            "ou Z (hauteur).",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "SideA",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Face de la première pièce : début ou fin sur l'axe."),
        mode=HIDDEN,
    ),
    PropertySpec(
        "SideB",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Face de la seconde pièce : début ou fin sur l'axe."),
        mode=HIDDEN,
    ),
    PropertySpec(
        "Value",
        LENGTH,
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Distance gardée entre les deux faces. Les pièces de l'ensemble la suivent par leurs "
            "expressions : la changer (ou la lier à une expression, un tableur) déplace les "
            "pièces.",
        ),
        default=0.0,
    ),
    version_spec(
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la distance, utilisée pour migrer les anciens "
            "fichiers.",
        ),
        MODEL_VERSION,
    ),
)
_CHOICES: Final = {"Axis": list(AXES), "SideA": list(SIDES), "SideB": list(SIDES)}


class Distance(StatelessProxy):
    """Proxy de la Distance gardée. Chemin de module figé (ADR 0003) ; sans état enregistré."""

    TYPE: ClassVar[str] = "Menuiserie::Distance"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés de la Distance, à leurs valeurs par défaut."""
        obj.Proxy = self
        schema.add_missing_properties(obj, DISTANCE_PROPERTIES, choices=_CHOICES)
        schema.apply_editor_modes(obj, DISTANCE_PROPERTIES)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types contrôlés (ADR 0003), listes des énumérations rétablies."""
        schema.restore_schema(obj, DISTANCE_PROPERTIES, self.VERSION, NOUN)
        for name, choices in _CHOICES.items():
            value = getattr(obj, name, None)
            if value in choices and obj.getEnumerationsOfProperty(name) != choices:
                setattr(obj, name, choices)
                setattr(obj, name, value)

    def unsetupObject(self, obj: DocumentObject) -> None:
        """Distance supprimée : l'ensemble est relié sans elle, dans la même transaction (les
        pièces ne bougent pas, leurs expressions ne citent plus la Distance)."""
        from freecad.menuiserie.features.furniture_relink import distance_removed

        distance_removed(obj)

    def execute(self, obj: DocumentObject) -> None:
        """Aucune forme : la valeur est lue par les expressions des pièces."""
        del obj


def is_distance(obj: object) -> bool:
    """Vrai si ``obj`` est une Distance de l'atelier (faux pour un objet supprimé)."""
    return proxy_is(obj, Distance)


def _piece(obj: DocumentObject, prop: str) -> DocumentObject | None:
    try:
        return getattr(obj, prop, None)
    except ReferenceError:  # pièce supprimée
        return None


def distance_furniture(obj: DocumentObject) -> DocumentObject | None:
    """Ensemble de la Distance : celui de ses pièces, ``None`` si elles n'en ont plus ou n'ont pas
    le même."""
    first, second = _piece(obj, "PieceA"), _piece(obj, "PieceB")
    if first is None or second is None:
        return None
    furniture = furniture_of(first)
    return furniture if furniture is not None and furniture == furniture_of(second) else None


def distances_of(furniture: DocumentObject) -> list[DocumentObject]:
    """Distances de ``furniture`` (leurs deux pièces en sont membres), par nom."""
    found = [
        obj
        for obj in furniture.Document.Objects
        if is_distance(obj) and distance_furniture(obj) == furniture
    ]
    return sorted(found, key=lambda obj: obj.Name)


def distances_touching(doc: Document, names: Collection[str]) -> list[DocumentObject]:
    """Distances de ``doc`` dont l'une des pièces porte un ``Name`` de ``names``, par nom."""
    found = []
    for obj in doc.Objects:
        if not is_distance(obj):
            continue
        pieces = (_piece(obj, "PieceA"), _piece(obj, "PieceB"))
        if any(piece is not None and piece.Name in names for piece in pieces):
            found.append(obj)
    return sorted(found, key=lambda obj: obj.Name)


def remove_touching(doc: Document, names: Collection[str]) -> list[str]:
    """Supprime les Distances de ``doc`` qui touchent l'une des pièces ``names`` (chacune relie
    l'ensemble sans elle, :meth:`Distance.unsetupObject`) ; renvoie leurs noms."""
    removed = [obj.Name for obj in distances_touching(doc, names)]
    for name in removed:
        if doc.getObject(name) is not None:
            doc.removeObject(name)
    return removed


def kept_gap_of(obj: DocumentObject) -> KeptGap | None:
    """Distance vue par ``core`` ; ``None`` si ses pièces manquent, sont identiques, ou si l'axe
    est illisible (donnée d'un document plus récent)."""
    first, second = _piece(obj, "PieceA"), _piece(obj, "PieceB")
    if first is None or second is None or first.Name == second.Name:
        return None
    if obj.Axis not in AXES:
        return None
    return KeptGap(
        obj.Name,
        first.Name,
        obj.SideA == SIDES[1],
        second.Name,
        obj.SideB == SIDES[1],
        FurnitureAxis.of(AXES.index(obj.Axis)),
        str(obj.Label),
    )


def _write_sides(obj: DocumentObject, gap: KeptGap, value: float) -> None:
    obj.Axis = AXES[gap.axis.index]
    obj.SideA = SIDES[int(gap.a_end)]
    obj.SideB = SIDES[int(gap.b_end)]
    obj.Value = value


def create_distance(
    furniture: DocumentObject,
    first: DocumentObject,
    second: DocumentObject,
    gap: KeptGap,
    value: float,
) -> DocumentObject:
    """Crée la Distance ``gap`` de valeur ``value`` (mm) entre les pièces ``first`` et
    ``second`` de ``furniture`` (sans transaction, recalcul ni liaisons : voir
    :func:`.furniture_members.keep_distance`). Placée dans le groupe de l'ensemble s'il en a un,
    sinon à côté de lui ; libellé « Distance : A, B »."""
    doc = furniture.Document
    obj = doc.addObject("App::FeaturePython", OBJECT_NAME)
    Distance(obj)
    obj.PieceA, obj.PieceB = first, second
    _write_sides(obj, gap, value)
    obj.Label = translated(LABEL, {"a": str(first.Label), "b": str(second.Label)})
    container = furniture.getParentGeoFeatureGroup()
    if container is not None:
        container.addObject(obj)
    return obj
