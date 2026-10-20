# SPDX-License-Identifier: LGPL-2.1-or-later
"""Matériaux et bibliothèque : bornes, ``MaterialKind``, ``Texture``, ``Material``."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

from freecad.menuiserie.core._validation import FrozenMapping, nfc

MAX_ID_LENGTH: Final = 64
MAX_NAME_LENGTH: Final = 80
MIN_DENSITY: Final = 50.0
MAX_DENSITY: Final = 2000.0
MAX_THICKNESSES: Final = 50
MAX_THICKNESS_MM: Final = 300.0
MAX_TEXTURE_PATH_LENGTH: Final = 255
MIN_TEXTURE_SIZE_MM: Final = 10.0
MAX_TEXTURE_SIZE_MM: Final = 10_000.0
TEXTURE_EXTENSIONS: Final = (".png", ".jpg", ".jpeg")


class MaterialKind(str, Enum):
    """Famille de matériau ; la valeur est celle écrite dans le fichier JSON."""

    SOLID = "solid"
    PLYWOOD = "plywood"
    MDF = "mdf"
    MELAMINE = "melamine"

    @property
    def is_panel(self) -> bool:
        """Vrai pour les panneaux (contreplaqué, MDF, mélaminé)."""
        return self is not MaterialKind.SOLID

    @property
    def has_grain_by_default(self) -> bool:
        """Fil par défaut : vrai pour le massif et le contreplaqué."""
        return self in (MaterialKind.SOLID, MaterialKind.PLYWOOD)


@dataclass(frozen=True)
class Texture:
    """Image de texture d'un matériau ; à défaut (image absente ou illisible), la couleur.

    ``image`` est le chemin absolu résolu de l'image, dont l'existence n'est pas vérifiée ici.
    ``size`` donne la largeur et la hauteur réelles couvertes par l'image, en mm ; le fil du
    bois suit la largeur de l'image.
    """

    image: Path
    size: tuple[float, float]


@dataclass(frozen=True)
class Material:
    """Essence massive ou panneau, tel que décrit dans la bibliothèque (immuable, hachable)."""

    id: str
    kind: MaterialKind
    names: Mapping[str, str]
    density: float
    thicknesses: tuple[float, ...]
    color: tuple[int, int, int]
    has_grain: bool
    texture: Texture | None = None

    def __post_init__(self) -> None:
        if not self.names:
            raise ValueError(f"le matériau « {self.id} » n'a aucun libellé")
        names = {language: nfc(label) for language, label in self.names.items()}
        object.__setattr__(self, "names", FrozenMapping(names))
        object.__setattr__(self, "thicknesses", tuple(self.thicknesses))
        object.__setattr__(self, "color", tuple(self.color))

    def name(self, lang: str = "fr") -> str:
        """Libellé dans la langue demandée, sinon français, sinon la première langue disponible."""
        for candidate in (lang, "fr"):
            if candidate in self.names:
                return self.names[candidate]
        return next(iter(self.names.values()))


class UnknownMaterialError(KeyError):
    """Identifiant de matériau absent de la bibliothèque."""


class MaterialLibrary:
    """Collection immuable et ordonnée de matériaux.

    Identifiants et libellés français uniques : ``ValueError`` sinon.
    """

    __slots__ = ("_by_id", "_materials")

    def __init__(self, materials: Iterable[Material]) -> None:
        self._materials: tuple[Material, ...] = tuple(materials)
        by_id: dict[str, Material] = {}
        labels: set[str] = set()
        for material in self._materials:
            label = material.name("fr")
            if material.id in by_id:
                raise ValueError(f"identifiant de matériau en double : « {material.id} »")
            if label in labels:
                raise ValueError(f"libellé de matériau en double : « {label} »")
            by_id[material.id] = material
            labels.add(label)
        self._by_id: Mapping[str, Material] = by_id

    def __contains__(self, material_id: object) -> bool:
        return material_id in self._by_id

    def __iter__(self) -> Iterator[Material]:
        """Matériaux intégrés puis ajouts de l'utilisateur, dans l'ordre des fichiers."""
        return iter(self._materials)

    def __len__(self) -> int:
        return len(self._materials)

    def get(self, material_id: str) -> Material:
        """Matériau d'identifiant donné ; lève :class:`UnknownMaterialError` s'il n'existe pas."""
        material = self._by_id.get(material_id)
        if material is None:
            raise UnknownMaterialError(material_id)
        return material

    def find(self, material_id: str) -> Material | None:
        """Matériau d'identifiant donné, ou ``None``."""
        return self._by_id.get(material_id)

    def find_by_name(self, name: str, lang: str = "fr") -> Material | None:
        """Matériau dont le libellé (comparé en forme NFC) vaut ``name``, ou ``None``."""
        wanted = nfc(name)
        return next((m for m in self._materials if m.name(lang) == wanted), None)

    def by_kind(self, *kinds: MaterialKind) -> list[Material]:
        """Matériaux des familles données, dans l'ordre ; tous si aucune famille n'est donnée."""
        if not kinds:
            return list(self._materials)
        return [m for m in self._materials if m.kind in kinds]

    def default_material(self) -> Material:
        """Premier matériau massif, sinon le premier ; :class:`UnknownMaterialError` si vide."""
        if not self._materials:
            raise UnknownMaterialError("bibliothèque de matériaux vide")
        solids = self.by_kind(MaterialKind.SOLID)
        return solids[0] if solids else self._materials[0]
