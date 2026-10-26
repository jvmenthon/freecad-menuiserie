# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sources acceptées par la pièce en bois : un lecteur par sorte de source (ADR 0020, B2, B11).

Patron Stratégie : chaque lecteur sait reconnaître une sorte de source (:meth:`accepts`) et en
lire les solides (:meth:`read`) dans le **repère propre de la source** (placement défait) ; la
table :data:`READERS` en fixe l'ordre. Ajouter une sorte de source = ajouter un lecteur.

- :class:`BodyReader` : ``PartDesign::Body`` (forme de son ``Tip``), toute fonction PartDesign et
  toute esquisse de corps, ramenées à leur corps ;
- :class:`ProfileReader` : esquisse (``Part::Part2DObject``) plane et fermée, extrudée de
  l'épaisseur du profil le long de sa normale ;
- :class:`ShapeReader` : tout autre ``Part::Feature`` (dont ceux des autres ateliers), un seul
  solide ; plusieurs solides seulement pour une forme importée (type exactement ``Part::Feature``,
  sans dépendance), qui ne se recalcule jamais.

Les refus (``ValueError`` ou ``TypeError`` au message traduit) précèdent toute création d'objet.
Aucun lecteur ne modifie la source.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final, Protocol

import FreeCAD as App
import Part

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM, MIN_DIMENSION_MM
from freecad.menuiserie.core.shaped import encode_fingerprint, fingerprint_matches
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.snap_geometry import ERRORS

__all__ = [
    "READERS",
    "BodyReader",
    "ProfileReader",
    "ShapeReader",
    "SourceReader",
    "SourceReading",
    "container_of",
    "is_workshop_object",
    "picked_solid",
    "read_source",
    "signature_text",
    "solid_values",
]

PLANAR_TOLERANCE_MM: Final = 1e-5  # écart à l'épaisseur nulle d'une esquisse plane
_ATELIER_PACKAGE: Final = "freecad.menuiserie"

_WORKSHOP_OBJECT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est un objet de l'atelier Menuiserie : seule une forme dessinée avec "
    "FreeCAD peut devenir une pièce en bois.",
)
_UNSUPPORTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » ne peut pas devenir une pièce en bois : choisissez un corps PartDesign, une "
    "forme Part ou une esquisse fermée.",
)
_ALREADY_CONVERTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » est déjà la forme d'une pièce en bois (« {part} »)."
)
_EMPTY_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'a pas de forme à convertir (corps sans protrusion, forme vide)."
)
_NOT_A_SOLID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La forme de « {label} » n'est pas un solide (surface, fil de fer)."
)
_INVALID_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La forme de « {label} » n'est pas un solide valide."
)
_SEVERAL_SOLIDS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » contient {count} solides et se recalcule : séparez-les en plusieurs corps avant "
    "de les convertir.",
)
_SEVERAL_IMPORTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » contient {count} solides : convertissez-les en une pièce chacun."
)
_OPEN_SKETCH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'esquisse « {label} » n'est pas fermée : fermez ses contours pour la convertir."
)
_NOT_PLANAR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'esquisse « {label} » n'est pas plane ou son contour est invalide."
)
_SEVERAL_FACES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "L'esquisse « {label} » dessine plusieurs surfaces séparées : une pièce en bois n'a qu'un "
    "contour (avec ses trous éventuels).",
)
_PROFILE_THICKNESS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Épaisseur du profil invalide : {value} mm (valeur finie, entre {min} et {max} mm attendue).",
)
_SOLID_MISSING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le solide n° {index} de « {label} » n'existe plus : la forme importée a été remplacée.",
)
_SOLID_CHANGED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le solide n° {index} de « {label} » n'est plus celui qui a été converti (forme remplacée) : "
    "supprimez cette pièce et convertissez de nouveau.",
)


@dataclass(frozen=True)
class SourceReading:
    """Solides d'une source, dans son repère propre (placement défait).

    ``source`` : objet à lier (le corps pour une fonction PartDesign) ; ``profile`` : la forme
    vient d'une esquisse extrudée ; ``importable`` : forme non paramétrique, dont chaque solide
    donne une pièce (indice stable)."""

    source: DocumentObject
    solids: tuple[Any, ...]
    profile: bool = False
    importable: bool = False


class SourceReader(Protocol):
    """Lecteur d'une sorte de source (patron Stratégie)."""

    def accepts(self, obj: DocumentObject) -> bool:
        """Vrai si ce lecteur sait lire ``obj``."""
        raise NotImplementedError

    def read(self, obj: DocumentObject, thickness: float) -> SourceReading:
        """Solides de ``obj`` ; ``ValueError`` ou ``TypeError`` traduite si la source est
        refusée. ``thickness`` : épaisseur du profil d'une esquisse (mm)."""
        raise NotImplementedError


def _label(obj: DocumentObject) -> str:
    return quoted_value(obj.Label)


def _refusal(template: str, obj: DocumentObject, **params: object) -> str:
    """Message traduit citant ``obj`` (libellé tronqué et échappé) et ``params``."""
    quoted = {name: quoted_value(value) for name, value in params.items()}
    return translated(template, {"label": _label(obj), **quoted})


def is_workshop_object(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` est un objet de l'atelier (pièce de bois, pièce usinée, pièce en bois,
    assemblage, ensemble, liste de débit…) : son proxy vient de ``freecad.menuiserie``."""
    proxy = getattr(obj, "Proxy", None)
    return type(proxy).__module__.startswith(_ATELIER_PACKAGE) if proxy is not None else False


def _without_placement(shape: Any) -> Any:
    """Copie de ``shape`` sans placement : dans le repère propre de la source."""
    clean = shape.copy()
    clean.Placement = App.Placement()
    return clean


def _solids_of(obj: DocumentObject, shape: Any) -> tuple[Any, ...]:
    """Solides valides de ``shape`` (repère propre de ``obj``) ; refus traduits si la forme est
    vide, sans solide ou invalide."""
    if shape is None or shape.isNull():
        raise ValueError(_refusal(_EMPTY_SHAPE, obj))
    clean = _without_placement(shape)
    solids = tuple(clean.Solids)
    if not solids:
        raise ValueError(_refusal(_NOT_A_SOLID, obj))
    if not all(solid.isValid() and solid.Volume > 0.0 for solid in solids):
        raise ValueError(_refusal(_INVALID_SHAPE, obj))
    return solids


def _single(reading: SourceReading) -> SourceReading:
    """``reading`` d'une forme qui se recalcule : refus s'il y a plusieurs solides."""
    count = len(reading.solids)
    if count > 1 and not reading.importable:
        raise ValueError(_refusal(_SEVERAL_SOLIDS, reading.source, count=count))
    return reading


class BodyReader:
    """Corps PartDesign (forme de son ``Tip``), fonction PartDesign ou esquisse de corps."""

    @staticmethod
    def body_of(obj: DocumentObject) -> DocumentObject | None:
        """Corps de ``obj`` (``obj`` lui-même s'il en est un), ``None`` s'il n'en a pas."""
        if obj.isDerivedFrom("PartDesign::Body"):
            return obj
        parent = obj.getParentGeoFeatureGroup()
        if parent is not None and parent.isDerivedFrom("PartDesign::Body"):
            return parent  # fonction PartDesign ou esquisse du corps
        return None

    def accepts(self, obj: DocumentObject) -> bool:
        """Vrai pour un corps, une fonction PartDesign ou une esquisse d'un corps."""
        return self.body_of(obj) is not None or obj.isDerivedFrom("PartDesign::Feature")

    def read(self, obj: DocumentObject, thickness: float) -> SourceReading:
        """Solide du ``Tip`` du corps de ``obj`` ; plusieurs solides refusés (forme
        paramétrique, leurs rangs changent quand on modifie le corps)."""
        del thickness
        body = self.body_of(obj)
        if body is None:
            raise TypeError(_refusal(_UNSUPPORTED, obj))
        return _single(SourceReading(body, _solids_of(body, body.Shape)))


class ProfileReader:
    """Esquisse plane et fermée, extrudée de l'épaisseur du profil le long de sa normale."""

    def accepts(self, obj: DocumentObject) -> bool:
        """Vrai pour une esquisse ou un autre objet 2D (``Part::Part2DObject``)."""
        return bool(obj.isDerivedFrom("Part::Part2DObject"))

    def read(self, obj: DocumentObject, thickness: float) -> SourceReading:
        """Solide de l'esquisse ``obj`` : face de tous ses contours (trous compris) extrudée de
        ``thickness`` selon l'axe Z de l'esquisse (sa normale). Esquisse ouverte, non plane ou à
        plusieurs surfaces séparées : refusée."""
        _check_thickness(thickness)
        if obj.Shape is None or obj.Shape.isNull() or not obj.Shape.Edges:
            raise ValueError(_refusal(_EMPTY_SHAPE, obj))
        flat = _without_placement(obj.Shape)
        if flat.BoundBox.ZLength > PLANAR_TOLERANCE_MM:
            raise ValueError(_refusal(_NOT_PLANAR, obj))
        face = _face_of(obj, flat)
        try:
            solid = face.extrude(App.Vector(0.0, 0.0, thickness))
        except ERRORS as error:
            raise ValueError(_refusal(_NOT_PLANAR, obj)) from error
        return SourceReading(obj, _solids_of(obj, solid), profile=True)


def _check_thickness(thickness: float) -> None:
    """``ValueError`` traduite si l'épaisseur du profil n'est pas finie ou hors bornes."""
    if math.isfinite(thickness) and MIN_DIMENSION_MM <= thickness <= MAX_DIMENSION_MM:
        return
    params = {"value": repr(thickness)[:20], "min": MIN_DIMENSION_MM, "max": MAX_DIMENSION_MM}
    raise ValueError(translated(_PROFILE_THICKNESS, {k: str(v) for k, v in params.items()}))


def _face_of(obj: DocumentObject, flat: Any) -> Any:
    """Face unique des contours fermés de ``flat`` ; refus traduit sinon."""
    wires = flat.Wires
    if not wires or not all(wire.isClosed() for wire in wires):
        raise ValueError(_refusal(_OPEN_SKETCH, obj))
    try:
        faces = Part.makeFace(wires, "Part::FaceMakerBullseye").Faces
    except ERRORS as error:
        raise ValueError(_refusal(_NOT_PLANAR, obj)) from error
    if len(faces) != 1:
        raise ValueError(_refusal(_SEVERAL_FACES, obj))
    return faces[0]


class ShapeReader:
    """Tout autre ``Part::Feature`` : un seul solide, sauf forme importée."""

    def accepts(self, obj: DocumentObject) -> bool:
        """Vrai pour un objet ``Part::Feature`` qui porte une forme."""
        return bool(obj.isDerivedFrom("Part::Feature"))

    def read(self, obj: DocumentObject, thickness: float) -> SourceReading:
        """Solides de la forme de ``obj`` ; plusieurs solides acceptés seulement si la source
        est une forme importée (type exactement ``Part::Feature``, sans dépendance)."""
        del thickness
        imported = obj.TypeId == "Part::Feature" and not obj.OutList
        reading = SourceReading(obj, _solids_of(obj, obj.Shape), importable=imported)
        return _single(reading)


READERS: Final[tuple[SourceReader, ...]] = (BodyReader(), ProfileReader(), ShapeReader())


def read_source(obj: DocumentObject, thickness: float) -> SourceReading:
    """Lecture de la source ``obj`` par le premier lecteur qui l'accepte.

    ``TypeError`` traduite pour un objet de l'atelier ou d'un type non pris en charge ;
    ``ValueError`` traduite pour une forme vide ou invalide, une esquisse ouverte, plusieurs
    solides d'une forme paramétrique, une épaisseur de profil hors bornes. La source déjà
    convertie n'est pas contrôlée ici (la pièce la lit à chaque recalcul)."""
    if is_workshop_object(obj):
        raise TypeError(_refusal(_WORKSHOP_OBJECT, obj))
    for reader in READERS:
        if reader.accepts(obj):
            return reader.read(obj, thickness)
    raise TypeError(_refusal(_UNSUPPORTED, obj))


def container_of(source: DocumentObject) -> DocumentObject | None:
    """Conteneur où ranger la pièce en bois : celui de la source (``App::Part`` ou groupe), ou
    ``None`` à la racine du document. Un corps ne reçoit que ses fonctions : on remonte au
    conteneur du corps."""
    parent = source.getParentGroup()
    while parent is not None and parent.isDerivedFrom("PartDesign::Body"):
        parent = parent.getParentGroup()
    return parent


def solid_values(solid: Any) -> list[float]:
    """Volume, aire, inertie et centre de masse du solide (repère propre de la source), valeurs
    de son empreinte."""
    inertia = solid.MatrixOfInertia.A
    center = solid.CenterOfMass
    return [
        float(solid.Volume),
        float(solid.Area),
        float(inertia[0]),
        float(inertia[5]),
        float(inertia[10]),
        float(center.x),
        float(center.y),
        float(center.z),
    ]


def picked_solid(reading: SourceReading, index: int, signature: str) -> Any:
    """Solide de ``reading`` que désigne la pièce : l'unique solide si ``index`` < 0, sinon le
    solide de rang ``index`` s'il existe et si son empreinte est ``signature``. ``ValueError``
    traduite sinon : jamais un solide pour un autre."""
    source = reading.source
    if index < 0:
        if len(reading.solids) != 1:
            raise ValueError(_refusal(_SEVERAL_IMPORTED, source, count=len(reading.solids)))
        return reading.solids[0]
    if index >= len(reading.solids):
        raise ValueError(_refusal(_SOLID_MISSING, source, index=index))
    solid = reading.solids[index]
    if not fingerprint_matches(signature, solid_values(solid)):
        raise ValueError(_refusal(_SOLID_CHANGED, source, index=index))
    return solid


def signature_text(solid: Any) -> str:
    """Empreinte textuelle (``SolidSignature``) de ``solid``."""
    return encode_fingerprint(solid_values(solid))
