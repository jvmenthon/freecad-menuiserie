# SPDX-License-Identifier: LGPL-2.1-or-later
"""Matériaux et bibliothèque : bornes, règles de champ, ``Texture``, ``Material``.

Chaque règle de champ est une fonction ``normalized_…`` qui renvoie la valeur normalisée, ou
``None`` si la valeur est invalide. La lecture JSON (``_parser``) la transforme en anomalie,
le constructeur de :class:`Material` en ``ValueError`` : les bornes ne sont écrites qu'ici.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final, TypeGuard, cast

from freecad.menuiserie.core._validation import (
    MIN_DIMENSION_MM,
    FrozenMapping,
    bounded_float,
    decimal_text,
    has_forbidden_character,
    nfc,
)
from freecad.menuiserie.core.text import quoted_value

MAX_ID_LENGTH: Final = 64
MAX_NAME_LENGTH: Final = 80
MIN_DENSITY: Final = 50.0
MAX_DENSITY: Final = 2000.0
MAX_THICKNESSES: Final = 50
MIN_THICKNESS_MM: Final = MIN_DIMENSION_MM
MAX_THICKNESS_MM: Final = 300.0
MAX_TEXTURE_PATH_LENGTH: Final = 255
MIN_TEXTURE_SIZE_MM: Final = 10.0
MAX_TEXTURE_SIZE_MM: Final = 10_000.0
TEXTURE_EXTENSIONS: Final = (".png", ".jpg", ".jpeg")
_COLOR_COMPONENTS: Final = 3
_MAX_COLOR_COMPONENT: Final = 255

_ID_PATTERN: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_LANGUAGE_PATTERN: Final = re.compile(r"[a-z]{2}")


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


def _numbers(value: object, lengths: range, minimum: float, maximum: float) -> list[float] | None:
    """Liste ou tuple de nombres finis (pas booléens) bornés, de longueur prise dans ``lengths``."""
    if not isinstance(value, (list, tuple)) or len(value) not in lengths:
        return None
    numbers = [bounded_float(item, minimum, maximum) for item in value]
    valid = [number for number in numbers if number is not None]
    return valid if len(valid) == len(numbers) else None


def normalized_id(value: object) -> str | None:
    """Identifiant de 1 à ``MAX_ID_LENGTH`` caractères : a-z, chiffres, tirets internes."""
    if isinstance(value, str) and len(value) <= MAX_ID_LENGTH and _ID_PATTERN.fullmatch(value):
        return value
    return None


def is_language_code(value: object) -> TypeGuard[str]:
    """Code de langue ISO 639-1 : deux lettres minuscules (« fr »)."""
    return isinstance(value, str) and _LANGUAGE_PATTERN.fullmatch(value) is not None


def normalized_label(value: object) -> str | None:
    """Libellé en forme NFC sans espaces de bord, de 1 à ``MAX_NAME_LENGTH`` caractères permis."""
    if not isinstance(value, str):
        return None
    label = nfc(value).strip()
    if 1 <= len(label) <= MAX_NAME_LENGTH and not has_forbidden_character(label):
        return label
    return None


def normalized_names(value: object) -> FrozenMapping | None:
    """Au moins un couple {code de langue: libellé}, libellés normalisés."""
    if not isinstance(value, Mapping) or not value:
        return None
    names: dict[str, str] = {}
    for language, label in value.items():
        normalized = normalized_label(label)
        if not is_language_code(language) or normalized is None:
            return None
        names[language] = normalized
    return FrozenMapping(names)


def normalized_density(value: object) -> float | None:
    """Masse volumique en kg/m³, entre ``MIN_DENSITY`` et ``MAX_DENSITY``."""
    return bounded_float(value, MIN_DENSITY, MAX_DENSITY)


def normalized_thicknesses(value: object) -> tuple[float, ...] | None:
    """1 à ``MAX_THICKNESSES`` épaisseurs en mm (0,1 à 300), triées et sans doublon."""
    lengths = range(1, MAX_THICKNESSES + 1)
    numbers = _numbers(value, lengths, MIN_THICKNESS_MM, MAX_THICKNESS_MM)
    return None if numbers is None else tuple(sorted(set(numbers)))


def normalized_color(value: object) -> tuple[int, int, int] | None:
    """Couleur RVB : exactement trois entiers (pas booléens) de 0 à 255."""
    if not isinstance(value, (list, tuple)) or len(value) != _COLOR_COMPONENTS:
        return None
    red, green, blue = value
    if _is_color_component(red) and _is_color_component(green) and _is_color_component(blue):
        return red, green, blue
    return None


def _is_color_component(value: object) -> TypeGuard[int]:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_COLOR_COMPONENT
    )


def normalized_texture_size(value: object) -> tuple[float, float] | None:
    """Largeur et hauteur réelles couvertes par l'image, en mm (10 à 10 000)."""
    numbers = _numbers(value, range(2, 3), MIN_TEXTURE_SIZE_MM, MAX_TEXTURE_SIZE_MM)  # 2 nombres
    return None if numbers is None else (numbers[0], numbers[1])


def _invalid(owner: str, field: str, value: object, expected: str) -> ValueError:
    shown = quoted_value(value)
    return ValueError(f"{owner}, champ « {field} » : {expected} attendu, reçu « {shown} »")


@dataclass(frozen=True)
class Texture:
    """Image de texture d'un matériau ; à défaut (image absente ou illisible), la couleur.

    ``image`` est le chemin absolu résolu de l'image, dont l'existence n'est pas vérifiée ici.
    ``size`` donne la largeur et la hauteur réelles couvertes par l'image, en mm ; le fil du
    bois suit la largeur de l'image. ``folder`` est le dossier résolu de la bibliothèque, dont
    l'image ne doit pas sortir quand elle est ouverte (par défaut : le dossier de l'image).
    ``ValueError`` si l'un des trois est invalide.
    """

    image: Path
    size: tuple[float, float]
    folder: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.image, Path) or not self.image.is_absolute():
            raise _invalid("texture", "image", self.image, "chemin absolu (Path)")
        size = normalized_texture_size(self.size)
        if size is None:
            expected = f"deux nombres entre {MIN_TEXTURE_SIZE_MM:g} et {MAX_TEXTURE_SIZE_MM:g} mm"
            raise _invalid("texture", "size", self.size, expected)
        object.__setattr__(self, "size", size)
        folder = self.image.parent if self.folder is None else self.folder
        if not isinstance(folder, Path) or not folder.is_absolute():
            raise _invalid("texture", "folder", folder, "dossier absolu contenant l'image")
        if not is_inside_folder(folder, self.image):
            raise _invalid("texture", "folder", folder, "dossier absolu contenant l'image")
        object.__setattr__(self, "folder", folder)

    @property
    def library_folder(self) -> Path:
        """Dossier dont l'image ne doit pas sortir (``folder``, renseigné par ``__post_init__``)."""
        return cast(Path, self.folder)


def is_inside_folder(folder: Path, path: Path) -> bool:
    """Vrai si ``path`` est un descendant strict de ``folder`` (chemins déjà résolus)."""
    return path != folder and path.is_relative_to(folder)


def _kind(value: object) -> MaterialKind | None:
    return value if isinstance(value, MaterialKind) else None


def _flag(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


# Règles appliquées par le constructeur de Material : champ, normalisation, valeur attendue.
_MATERIAL_RULES: Final[tuple[tuple[str, Callable[[object], object | None], str], ...]] = (
    ("id", normalized_id, f"identifiant de 1 à {MAX_ID_LENGTH} caractères (a-z, 0-9, tirets)"),
    ("kind", _kind, "MaterialKind"),
    (
        "names",
        normalized_names,
        f"au moins un libellé {{langue: libellé}} de 1 à {MAX_NAME_LENGTH} caractères",
    ),
    ("density", normalized_density, f"nombre fini entre {MIN_DENSITY:g} et {MAX_DENSITY:g} kg/m³"),
    (
        "thicknesses",
        normalized_thicknesses,
        f"1 à {MAX_THICKNESSES} nombres finis entre {decimal_text(MIN_THICKNESS_MM)} "
        f"et {decimal_text(MAX_THICKNESS_MM)} mm",
    ),
    ("color", normalized_color, "trois entiers de 0 à 255"),
    ("has_grain", _flag, "booléen"),
)


@dataclass(frozen=True)
class Material:
    """Essence massive ou panneau, tel que décrit dans la bibliothèque (immuable, hachable).

    Tous les champs sont validés et normalisés à la construction, avec les bornes de la
    lecture JSON : ``ValueError`` citant le champ fautif sinon.
    """

    id: str
    kind: MaterialKind
    names: Mapping[str, str]
    density: float
    thicknesses: tuple[float, ...]
    color: tuple[int, int, int]
    has_grain: bool
    texture: Texture | None = None

    def __post_init__(self) -> None:
        owner = f"matériau « {quoted_value(self.id)} »"
        for field, normalize, expected in _MATERIAL_RULES:
            value = getattr(self, field)
            normalized = normalize(value)
            if normalized is None:
                raise _invalid(owner, field, value, expected)
            object.__setattr__(self, field, normalized)
        if self.texture is not None and not isinstance(self.texture, Texture):
            raise _invalid(owner, "texture", self.texture, "Texture ou None")

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
