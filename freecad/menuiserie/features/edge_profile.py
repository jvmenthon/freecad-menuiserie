# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profil d'arête : chanfrein, quart de rond, gorge, bec-de-corbin, doucine… (issue #5, ADR 0029).

Un :class:`EdgeProfile` lie une pièce de bois brute à un ensemble d'arêtes (codes locaux
``"Z+Y-"``) qui reçoivent le même profil. Sa forme est vide : il ne fait que décrire ses coupes,
que la pièce usinée (:mod:`freecad.menuiserie.features.machined_part`) soustrait de la brute.
Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe et les noms des
propriétés sont écrits dans les documents ; ils ne changent jamais, et les valeurs de ``Family``
ne font que s'ajouter à la fin.
"""

from __future__ import annotations

from typing import ClassVar, Final

import Part

from freecad.menuiserie.core._extrusion import Extrusion
from freecad.menuiserie.core.edges import (
    EdgeFamily,
    EdgeId,
    all_edges,
    edge_cut,
    parse_edge,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import (
    READ_ONLY,
    DocumentObject,
    StatelessProxy,
    proxy_is,
)
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.schema import LENGTH, PropertySpec, version_spec
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.features.wood_part_record import dimensions_of

__all__ = [
    "FAMILY_LABELS",
    "MODEL_VERSION",
    "EdgeProfile",
    "checked_codes",
    "edge_cuts",
    "family_of",
    "is_edge_profile",
    "profile_cuts",
]

OBJECT_NAME: Final = "EdgeProfile"
MODEL_VERSION: Final = 1
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Profil d'arête")

FAMILY_LABELS: Final = {
    EdgeFamily.CHAMFER: QT_TRANSLATE_NOOP("Menuiserie", "Chanfrein"),
    EdgeFamily.ROUND: QT_TRANSLATE_NOOP("Menuiserie", "Quart de rond"),
    EdgeFamily.COVE: QT_TRANSLATE_NOOP("Menuiserie", "Gorge"),
    EdgeFamily.BULLNOSE: QT_TRANSLATE_NOOP("Menuiserie", "Demi-rond"),
    EdgeFamily.BEAK: QT_TRANSLATE_NOOP("Menuiserie", "Bec-de-corbin"),
    EdgeFamily.OGEE: QT_TRANSLATE_NOOP("Menuiserie", "Doucine"),
}

_NO_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Profil d'arête sans pièce : la pièce de bois a été supprimée."
)
_SHAPED_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est une pièce en bois (forme dessinée) : les profils d'arête ne s'appliquent "
    "qu'aux pièces de bois (boîtes).",
)
_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas une pièce de bois : elle ne peut pas recevoir de profil."
)
_NO_EDGE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Choisissez au moins une arête à profiler.")
_BAD_EDGES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les arêtes d'un profil doivent être différentes (douze au plus)."
)
_BAD_FAMILY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Famille de profil inconnue : {family}.")
_ON_PART: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce « {label} » : {message}")

PROPERTIES: Final = (
    PropertySpec(
        "Part",
        "App::PropertyLink",
        "Profil",
        QT_TRANSLATE_NOOP("App::Property", "Pièce de bois brute dont les arêtes sont profilées."),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Edges",
        "App::PropertyStringList",
        "Profil",
        QT_TRANSLATE_NOOP(
            "App::Property",
            'Arêtes profilées, par leurs deux faces dans le repère de la pièce ("Z+Y-" : '
            "dessus-avant).",
        ),
    ),
    PropertySpec(
        "Family",
        "App::PropertyEnumeration",
        "Profil",
        QT_TRANSLATE_NOOP("App::Property", "Forme du profil."),
        default=EdgeFamily.ROUND.value,
        label=QT_TRANSLATE_NOOP("Menuiserie", "Profil"),
        choices=tuple((family.value, FAMILY_LABELS[family]) for family in EdgeFamily),
    ),
    PropertySpec(
        "SizeA",
        LENGTH,
        "Profil",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Première cote du profil, mesurée sur la première face de l'arête (rayon pour les "
            "profils ronds).",
        ),
        default=1.0,
        label=QT_TRANSLATE_NOOP("Menuiserie", "Cote A"),
    ),
    PropertySpec(
        "SizeB",
        LENGTH,
        "Profil",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Seconde cote du profil, mesurée sur la seconde face (0 : égale à la première pour "
            "le chanfrein et le quart de rond).",
        ),
        default=0.0,
        label=QT_TRANSLATE_NOOP("Menuiserie", "Cote B"),
    ),
    version_spec(
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données du profil, utilisée pour migrer les anciens fichiers.",
        ),
        MODEL_VERSION,
    ),
)
CHOICES: Final = {"Family": [family.value for family in EdgeFamily]}


class EdgeProfile(StatelessProxy):
    """Proxy du FeaturePython « profil d'arête ». Chemin de module figé (ADR 0003)."""

    TYPE: ClassVar[str] = "Menuiserie::EdgeProfile"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés du profil, à leurs valeurs par défaut."""
        obj.Proxy = self
        schema.add_missing_properties(obj, PROPERTIES, choices=CHOICES)
        schema.apply_editor_modes(obj, PROPERTIES)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types des propriétés contrôlés, migration, modes d'édition (ADR 0003)."""
        schema.restore_schema(obj, PROPERTIES, self.VERSION, NOUN, CHOICES)
        for name, choices in CHOICES.items():
            if name in obj.PropertiesList and obj.getEnumerationsOfProperty(name) != choices:
                current = getattr(obj, name)
                setattr(obj, name, choices)
                setattr(obj, name, current if current in choices else choices[0])

    def execute(self, obj: DocumentObject) -> None:
        """Forme vide ; contrôle seulement que les coupes sont possibles (``ValueError``
        traduite sinon : cote trop grande, pièce en bois, arête inconnue)."""
        edge_cuts(obj)
        obj.Shape = Part.Shape()


def is_edge_profile(obj: object) -> bool:
    """Vrai si ``obj`` est un profil d'arête de l'atelier (faux pour un objet supprimé)."""
    return proxy_is(obj, EdgeProfile)


def family_of(name: str) -> EdgeFamily:
    """Famille désignée par sa valeur (``"Round"``) ; ``ValueError`` traduite sinon."""
    try:
        return EdgeFamily(name)
    except ValueError:
        raise ValueError(translated(_BAD_FAMILY, {"family": quoted_value(name)})) from None


def checked_codes(edges: object) -> list[str]:
    """Codes des arêtes ``edges`` (codes, noms français ou :class:`EdgeId`), dans l'ordre des
    douze arêtes ; ``ValueError`` traduite si la liste est vide, a un doublon, ou nomme une arête
    inconnue."""
    if isinstance(edges, str) or not isinstance(edges, list | tuple | set | frozenset):
        raise ValueError(translated(_NO_EDGE))
    with translated_errors():
        ids = [item if isinstance(item, EdgeId) else parse_edge(item) for item in edges]
    if not ids:
        raise ValueError(translated(_NO_EDGE))
    codes = [edge.code for edge in ids]
    if len(set(codes)) != len(codes):
        raise ValueError(translated(_BAD_EDGES))
    return [edge.code for edge in all_edges() if edge.code in codes]


def profile_cuts(
    label: str, dimensions: Dimensions, codes: list[str], family: EdgeFamily, a: float, b: float
) -> list[Extrusion]:
    """Coupes de chaque arête de ``codes`` pour une pièce de cotes ``dimensions`` ; ``ValueError``
    traduite, qui nomme la pièce ``label``, si une cote est refusée."""
    try:
        with translated_errors():
            return [edge_cut(dimensions, parse_edge(code), family, a, b) for code in codes]
    except ValueError as error:
        raise ValueError(
            translated(_ON_PART, {"label": quoted_value(label), "message": str(error)})
        ) from None


def edge_cuts(profile: DocumentObject) -> list[Extrusion]:
    """Coupes du profil ``profile`` sur sa pièce, dans le repère local de celle-ci.
    ``ValueError`` traduite si la pièce manque, n'est pas une pièce de bois (boîte), si les
    arêtes sont invalides ou si une cote est refusée."""
    part = profile.Part
    if part is None:
        raise ValueError(translated(_NO_PART))
    label = quoted_value(part.Label)
    if is_shaped_part(part):
        raise ValueError(translated(_SHAPED_PART, {"label": label}))
    if not is_wood_part(part):
        raise ValueError(translated(_NOT_A_WOOD_PART, {"label": label}))
    codes = checked_codes(list(profile.Edges))
    with translated_errors():
        dimensions = dimensions_of(part)
    return profile_cuts(
        str(part.Label),
        dimensions,
        codes,
        family_of(profile.Family),
        profile.SizeA.Value,
        profile.SizeB.Value,
    )
