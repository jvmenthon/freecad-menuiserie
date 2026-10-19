# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bibliothèque de matériaux : essences massives et panneaux (ADR 0002).

Lecture, validation et fusion des fichiers JSON de matériaux (format 1). Les fonctions
de lecture ne lèvent jamais d'exception pour un fichier invalide : chaque anomalie est
renvoyée sous forme de :class:`LibraryIssue`, dont le message est un gabarit français
marqué pour la traduction.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Final, TypeGuard

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

FORMAT_VERSION: Final = 1
MAX_FILE_BYTES: Final = 1_048_576
MAX_MATERIALS: Final = 500
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
MAX_ISSUES: Final = 200
MAX_LISTED_KEYS: Final = 5

BUILTIN_SOURCE: Final = QT_TRANSLATE_NOOP("Menuiserie", "intégrée")
"""Source citée dans les anomalies de la bibliothèque intégrée."""

_ROOT_KEYS: Final = frozenset({"format", "materials"})
_ENTRY_KEYS: Final = frozenset(
    {"id", "kind", "name", "density", "thicknesses", "color", "has_grain", "texture"}
)
_TEXTURE_KEYS: Final = ("image", "size")
_ID_PATTERN: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_LANGUAGE_PATTERN: Final = re.compile(r"[a-z]{2}")
_COLOR_PATTERN: Final = re.compile(r"#[0-9A-Fa-f]{6}")
# Contrôle, format (invisibles, bidi), demi-substituts, usage privé, non attribués, séparateurs
# de ligne et de paragraphe : refusés dans les libellés.
_FORBIDDEN_CATEGORIES: Final = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
_MAX_QUOTED_LENGTH: Final = 32
# Ouverture sans blocage (tube nommé) ni héritage par un processus fils ; binaire sous Windows.
_OPEN_FLAGS: Final = (
    os.O_RDONLY
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_BINARY", 0)
)

# Gabarits des anomalies : « source » est toujours fourni dans les paramètres.
_FILE_UNREADABLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "{source} : fichier illisible ({error}).")
_FILE_NOT_REGULAR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : ce chemin ne désigne pas un fichier ordinaire."
)
_FILE_TOO_LARGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : fichier trop volumineux ({size} octets, maximum {max} octets)."
)
_FILE_NOT_UTF8: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : le fichier n'est pas encodé en UTF-8."
)
_FILE_INVALID_JSON: Final = QT_TRANSLATE_NOOP("Menuiserie", "{source} : JSON invalide ({error}).")
_FILE_NON_FINITE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : valeur « {value} » refusée (NaN et Infinity sont interdits)."
)
_FILE_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : JSON trop profondément imbriqué."
)
_FILE_BUILTIN_MISSING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : bibliothèque de matériaux introuvable ({path})."
)
_ROOT_NOT_OBJECT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : la racine du fichier doit être un objet JSON."
)
_ROOT_FORMAT_INVALID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clé « format » absente ou non entière."
)
_ROOT_FORMAT_NEWER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : fichier créé par une version plus récente de l'atelier "
    "(format {format}, format pris en charge : {supported}).",
)
_ROOT_FORMAT_UNSUPPORTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : format {format} non pris en charge (format attendu : {supported})."
)
_ROOT_MATERIALS_INVALID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clé « materials » absente ou qui n'est pas une liste."
)
_ROOT_DUPLICATE_KEY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clé « {field} » en double à la racine du fichier."
)
_ROOT_UNKNOWN_KEYS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clés inconnues à la racine, ignorées : {keys}."
)
_ROOT_UNKNOWN_KEYS_MORE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : clés inconnues à la racine, ignorées : {keys} … et {more} autres."
)
_TOO_MANY_MATERIALS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : {count} matériaux, seuls les {max} premiers sont lus."
)
_ENTRIES_NOT_OBJECTS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : entrées n° {positions} ignorées, chaque matériau doit être un objet JSON.",
)
_ENTRY_MISSING_FIELD: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : matériau « {id} », champ « {field} » : champ obligatoire absent."
)
_ENTRY_UNKNOWN_KEYS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : matériau « {id} », clés inconnues ignorées : {keys}."
)
_ENTRY_UNKNOWN_KEYS_MORE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », clés inconnues ignorées : {keys} … et {more} autres.",
)
_ENTRY_DUPLICATE_KEY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : clé en double, entrée ignorée.",
)
_ENTRY_INVALID_ID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : identifiant de 1 à {max} caractères "
    "attendu (lettres minuscules sans accent, chiffres et tirets, ex. « cp-bouleau »).",
)
_ENTRY_DUPLICATE_ID: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : identifiant déjà utilisé "
    "dans ce fichier, entrée ignorée.",
)
_ENTRY_INVALID_KIND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : matériau « {id} », champ « {field} » : type attendu parmi {allowed}."
)
_ENTRY_INVALID_NAME: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : texte ou objet "
    "{{langue: libellé}} non vide attendu.",
)
_ENTRY_INVALID_LANGUAGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : code de langue « {language} » "
    "invalide (deux lettres minuscules attendues, ex. « fr »).",
)
_ENTRY_INVALID_LABEL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : libellé de 1 à {max} caractères "
    "sans caractère de contrôle ni caractère invisible attendu.",
)
_ENTRY_INVALID_DENSITY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : masse volumique entre {min} et {max} "
    "kg/m³ attendue.",
)
_ENTRY_INVALID_THICKNESSES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : liste de 1 à {count} épaisseurs "
    "attendue, chacune supérieure à 0 et au plus {max} mm.",
)
_ENTRY_INVALID_COLOR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : couleur au format « #RRGGBB » attendue.",
)
_ENTRY_INVALID_GRAIN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : valeur true ou false attendue.",
)
_TOO_MANY_ISSUES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{source} : {count} autres anomalies non affichées."
)
_ENTRY_INVALID_TEXTURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : objet avec les clés « image » et "
    "« size » attendu.",
)
_ENTRY_INVALID_TEXTURE_IMAGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : chemin relatif de 1 à {max} caractères "
    "vers une image {extensions} attendu (séparateur « / », sans « .. », « \\ » ni « : »).",
)
_ENTRY_TEXTURE_OUTSIDE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : l'image doit se trouver dans le dossier "
    "du fichier de bibliothèque (lien symbolique vers l'extérieur refusé).",
)
_ENTRY_TEXTURE_NO_FOLDER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : dossier du fichier de bibliothèque "
    "inconnu, chemin de l'image impossible à résoudre.",
)
_ENTRY_INVALID_TEXTURE_SIZE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : deux nombres entre {min} et {max} mm "
    "attendus (largeur et hauteur réelles couvertes par l'image).",
)
_MERGE_REPLACED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : le matériau « {id} » remplace le matériau intégré de même identifiant.",
)
_MERGE_LABEL_TAKEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{source} : matériau « {id} », champ « {field} » : libellé « {label} » déjà utilisé "
    "par le matériau « {other} », entrée ignorée.",
)


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


class Severity(Enum):
    """Gravité d'une anomalie de la bibliothèque."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


_SEVERITY_RANK: Final = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}


class _FrozenMapping(Mapping[str, str]):
    """Dictionnaire de textes immuable et hachable (libellés, paramètres d'anomalie)."""

    __slots__ = ("_items",)

    def __init__(self, items: Mapping[str, str]) -> None:
        self._items: dict[str, str] = dict(items)

    def __getitem__(self, key: str) -> str:
        return self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __hash__(self) -> int:
        return hash(frozenset(self._items.items()))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._items!r})"


@dataclass(frozen=True)
class LibraryIssue:
    """Anomalie rencontrée en lisant ou en fusionnant une bibliothèque.

    ``template`` est un gabarit français marqué pour la traduction ; ``params``
    contient toujours ``source`` et sert à le remplir (``template.format(**params)``).
    """

    severity: Severity
    source: str
    template: str
    params: Mapping[str, str]
    material_id: str | None = None

    def __post_init__(self) -> None:
        params = _FrozenMapping({"source": self.source, **self.params})
        object.__setattr__(self, "params", params)

    def format(self) -> str:
        """Gabarit non traduit, rempli avec ses paramètres (tests, journaux)."""
        return self.template.format_map(self.params)


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
        names = {language: _nfc(label) for language, label in self.names.items()}
        object.__setattr__(self, "names", _FrozenMapping(names))
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


class LibraryFormatError(ValueError):
    """Anomalie bloquante d'un fichier ou d'une entrée ; usage interne, convertie en anomalie."""

    def __init__(self, issue: LibraryIssue) -> None:
        super().__init__(issue.format())
        self.issue = issue


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
        wanted = _nfc(name)
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


def _nfc(text: str) -> str:
    """Texte en forme normalisée NFC (« é » composé plutôt que « e » + accent combinant)."""
    return unicodedata.normalize("NFC", text)


def quoted_value(value: object) -> str:
    """Valeur fournie par un fichier, raccourcie et échappée pour être citée dans un message.

    Au plus ``_MAX_QUOTED_LENGTH`` caractères (suivis de « … » si elle est tronquée) ; les
    caractères non imprimables sont échappés (``\\n``, ``\\u202e``…). Ne lève jamais d'exception.
    """
    if isinstance(value, str):
        text = value
    else:
        try:
            text = repr(value)
        except ValueError:  # entier trop long pour être converti en texte
            return "?"
    escaped = repr(text[:_MAX_QUOTED_LENGTH])[1:-1]
    return escaped + "…" if len(text) > _MAX_QUOTED_LENGTH else escaped


def to_finite_float(value: object) -> float | None:
    """Nombre JSON fini (entier ou flottant, pas booléen) converti en flottant, sinon ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _make_issue(
    severity: Severity,
    source: str,
    template: str,
    material_id: str | None = None,
    **params: str,
) -> LibraryIssue:
    return LibraryIssue(severity, source, template, params, material_id)


def _file_error(source: str, template: str, **params: str) -> LibraryFormatError:
    return LibraryFormatError(_make_issue(Severity.ERROR, source, template, **params))


def _capped(issues: list[LibraryIssue]) -> list[LibraryIssue]:
    """Au plus ``MAX_ISSUES`` anomalies, plus une anomalie de synthèse pour les suivantes."""
    if len(issues) <= MAX_ISSUES:
        return issues
    omitted = issues[MAX_ISSUES:]
    severity = max((issue.severity for issue in omitted), key=_SEVERITY_RANK.__getitem__)
    summary = _make_issue(severity, omitted[0].source, _TOO_MANY_ISSUES, count=str(len(omitted)))
    return [*issues[:MAX_ISSUES], summary]


def _unknown_keys_params(keys: Sequence[str]) -> dict[str, str]:
    """Paramètres ``keys`` (au plus ``MAX_LISTED_KEYS`` clés déjà échappées) et ``more``."""
    listed = ", ".join(f"« {key} »" for key in keys[:MAX_LISTED_KEYS])
    return {"keys": listed, "more": str(max(len(keys) - MAX_LISTED_KEYS, 0))}


class _JsonObject(dict[str, object]):
    """Objet JSON dont des clés apparaissent plusieurs fois (``json`` garde la dernière valeur)."""

    __slots__ = ("duplicate_keys",)

    def __init__(self, pairs: list[tuple[str, object]], duplicate_keys: tuple[str, ...]) -> None:
        super().__init__(pairs)
        self.duplicate_keys = duplicate_keys


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """``object_pairs_hook`` : objet JSON ordinaire, ou :class:`_JsonObject` si clés en double."""
    result = dict(pairs)
    if len(result) == len(pairs):
        return result
    seen: set[str] = set()
    duplicates: dict[str, None] = {}
    for key, _ in pairs:
        if key in seen:
            duplicates[key] = None
        seen.add(key)
    return _JsonObject(pairs, tuple(duplicates))


def _contains_duplicate_keys(value: object) -> bool:
    """Vrai si ``value`` est ou contient un objet JSON à clés en double (sans récursion)."""
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, _JsonObject):
            return True
        if isinstance(current, dict):
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return False


def _duplicated_field(data: Mapping[str, object]) -> str | None:
    """Clé en double de ``data``, ou clé dont la valeur contient un objet à clés en double."""
    if isinstance(data, _JsonObject):
        return data.duplicate_keys[0]
    return next((key for key, value in data.items() if _contains_duplicate_keys(value)), None)


@dataclass(frozen=True)
class _Entry:
    """Entrée brute de la liste ``materials`` en cours de validation."""

    source: str
    position: int
    data: Mapping[str, object]
    folder: Path | None = None
    material_id: str | None = None

    @property
    def shown_id(self) -> str:
        """Identifiant cité dans les anomalies : l'identifiant validé, sinon « #position »."""
        return self.material_id if self.material_id is not None else f"#{self.position}"

    def issue(self, severity: Severity, template: str, field: str, **params: str) -> LibraryIssue:
        return _make_issue(
            severity,
            self.source,
            template,
            self.material_id,
            id=self.shown_id,
            field=field,
            **params,
        )

    def error(self, template: str, field: str, **params: str) -> LibraryFormatError:
        return LibraryFormatError(self.issue(Severity.ERROR, template, field, **params))

    def require(self, key: str) -> object:
        if key not in self.data:
            raise self.error(_ENTRY_MISSING_FIELD, key)
        return self.data[key]

    def unknown_keys_issues(self) -> list[LibraryIssue]:
        """Au plus un avertissement, qui liste les clés inconnues de l'entrée."""
        keys = [quoted_value(key) for key in self.data if key not in _ENTRY_KEYS]
        texture = self.data.get("texture")
        if isinstance(texture, dict):
            keys += [f"texture.{quoted_value(k)}" for k in texture if k not in _TEXTURE_KEYS]
        if not keys:
            return []
        template = _ENTRY_UNKNOWN_KEYS_MORE if len(keys) > MAX_LISTED_KEYS else _ENTRY_UNKNOWN_KEYS
        params = _unknown_keys_params(keys)
        issue = _make_issue(
            Severity.WARNING, self.source, template, self.material_id, id=self.shown_id, **params
        )
        return [issue]


def _parse_id(entry: _Entry) -> str:
    value = entry.require("id")
    if isinstance(value, str) and len(value) <= MAX_ID_LENGTH and _ID_PATTERN.fullmatch(value):
        return value
    raise entry.error(_ENTRY_INVALID_ID, "id", max=str(MAX_ID_LENGTH))


def _parse_kind(entry: _Entry) -> MaterialKind:
    value = entry.require("kind")
    for kind in MaterialKind:
        if value == kind.value:
            return kind
    allowed = ", ".join(kind.value for kind in MaterialKind)
    raise entry.error(_ENTRY_INVALID_KIND, "kind", allowed=allowed)


def _has_forbidden_character(text: str) -> bool:
    return any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in text)


def _parse_label(entry: _Entry, value: object) -> str:
    if isinstance(value, str):
        label = _nfc(value).strip()
        if 1 <= len(label) <= MAX_NAME_LENGTH and not _has_forbidden_character(label):
            return label
    raise entry.error(_ENTRY_INVALID_LABEL, "name", max=str(MAX_NAME_LENGTH))


def _parse_names(entry: _Entry) -> dict[str, str]:
    value = entry.require("name")
    if isinstance(value, str):
        value = {"fr": value}
    if not isinstance(value, dict) or not value:
        raise entry.error(_ENTRY_INVALID_NAME, "name")
    names: dict[str, str] = {}
    for language, label in value.items():
        if not isinstance(language, str) or not _LANGUAGE_PATTERN.fullmatch(language):
            raise entry.error(_ENTRY_INVALID_LANGUAGE, "name", language=quoted_value(language))
        names[language] = _parse_label(entry, label)
    return names


def _parse_density(entry: _Entry) -> float:
    density = to_finite_float(entry.require("density"))
    if density is not None and MIN_DENSITY <= density <= MAX_DENSITY:
        return density
    raise entry.error(
        _ENTRY_INVALID_DENSITY, "density", min=f"{MIN_DENSITY:g}", max=f"{MAX_DENSITY:g}"
    )


def _parse_thicknesses(entry: _Entry) -> tuple[float, ...]:
    value = entry.require("thicknesses")
    if isinstance(value, list) and 1 <= len(value) <= MAX_THICKNESSES:
        numbers = [to_finite_float(item) for item in value]
        valid = [n for n in numbers if n is not None and 0 < n <= MAX_THICKNESS_MM]
        if len(valid) == len(value):
            return tuple(sorted(set(valid)))
    raise entry.error(
        _ENTRY_INVALID_THICKNESSES,
        "thicknesses",
        count=str(MAX_THICKNESSES),
        max=f"{MAX_THICKNESS_MM:g}",
    )


def _parse_color(entry: _Entry) -> tuple[int, int, int]:
    value = entry.require("color")
    if not isinstance(value, str) or not _COLOR_PATTERN.fullmatch(value):
        raise entry.error(_ENTRY_INVALID_COLOR, "color")
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def _parse_has_grain(entry: _Entry, kind: MaterialKind) -> bool:
    value = entry.data.get("has_grain", kind.has_grain_by_default)
    if not isinstance(value, bool):
        raise entry.error(_ENTRY_INVALID_GRAIN, "has_grain")
    return value


def _is_safe_image_path(value: object) -> TypeGuard[str]:
    """Chemin relatif portable vers une image : ni absolu, ni « .. », ni « \\ », ni « : »."""
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_TEXTURE_PATH_LENGTH:
        return False
    if _has_forbidden_character(value) or "\\" in value or ":" in value:
        return False
    parts = value.split("/")
    if parts[0] == "" or ".." in parts:
        return False
    return PurePosixPath(parts[-1]).suffix.lower() in TEXTURE_EXTENSIONS


def _resolve_in_folder(entry: _Entry, relative: str) -> Path:
    """Chemin absolu résolu de l'image ; elle doit rester dans le dossier du fichier."""
    if entry.folder is None:
        raise entry.error(_ENTRY_TEXTURE_NO_FOLDER, "texture.image")
    try:
        folder = entry.folder.resolve()
        image = (folder / relative).resolve()
    except (OSError, RuntimeError, ValueError) as error:  # boucle de liens, chemin invalide
        raise entry.error(_ENTRY_TEXTURE_OUTSIDE, "texture.image") from error
    if image == folder or not image.is_relative_to(folder):
        raise entry.error(_ENTRY_TEXTURE_OUTSIDE, "texture.image")
    return image


def _parse_texture_image(entry: _Entry, value: object) -> Path:
    if not _is_safe_image_path(value):
        raise entry.error(
            _ENTRY_INVALID_TEXTURE_IMAGE,
            "texture.image",
            max=str(MAX_TEXTURE_PATH_LENGTH),
            extensions=", ".join(TEXTURE_EXTENSIONS),
        )
    return _resolve_in_folder(entry, value)


def _parse_texture_size(entry: _Entry, value: object) -> tuple[float, float]:
    if isinstance(value, list) and len(value) == 2:
        numbers = [to_finite_float(item) for item in value]
        valid = [
            n for n in numbers if n is not None and MIN_TEXTURE_SIZE_MM <= n <= MAX_TEXTURE_SIZE_MM
        ]
        if len(valid) == 2:
            return valid[0], valid[1]
    raise entry.error(
        _ENTRY_INVALID_TEXTURE_SIZE,
        "texture.size",
        min=f"{MIN_TEXTURE_SIZE_MM:g}",
        max=f"{MAX_TEXTURE_SIZE_MM:g}",
    )


def _parse_texture(entry: _Entry) -> Texture | None:
    """Texture facultative ; toute anomalie rejette l'entrée, comme pour les autres champs."""
    if "texture" not in entry.data:
        return None
    value = entry.data["texture"]
    if not isinstance(value, dict):
        raise entry.error(_ENTRY_INVALID_TEXTURE, "texture")
    for key in _TEXTURE_KEYS:
        if key not in value:
            raise entry.error(_ENTRY_MISSING_FIELD, f"texture.{key}")
    image = _parse_texture_image(entry, value["image"])
    return Texture(image, _parse_texture_size(entry, value["size"]))


def _build_material(entry: _Entry, material_id: str) -> Material:
    kind = _parse_kind(entry)
    return Material(
        id=material_id,
        kind=kind,
        names=_parse_names(entry),
        density=_parse_density(entry),
        thicknesses=_parse_thicknesses(entry),
        color=_parse_color(entry),
        has_grain=_parse_has_grain(entry, kind),
        texture=_parse_texture(entry),
    )


def _identified(entry: _Entry) -> tuple[_Entry, str]:
    """Entrée munie de son identifiant ; :class:`LibraryFormatError` s'il est invalide ou répété."""
    if isinstance(entry.data, _JsonObject) and "id" in entry.data.duplicate_keys:
        raise entry.error(_ENTRY_DUPLICATE_KEY, "id")
    material_id = _parse_id(entry)
    return replace(entry, material_id=material_id), material_id


def _parse_entry(entry: _Entry) -> tuple[Material | None, list[LibraryIssue]]:
    """Valide une entrée ; s'arrête à la première règle violée (entrée rejetée)."""
    try:
        entry, material_id = _identified(entry)
    except LibraryFormatError as error:
        return None, [error.issue]
    issues = entry.unknown_keys_issues()
    duplicated = _duplicated_field(entry.data)
    if duplicated is not None:
        error_issue = entry.issue(Severity.ERROR, _ENTRY_DUPLICATE_KEY, quoted_value(duplicated))
        return None, [*issues, error_issue]
    try:
        material = _build_material(entry, material_id)
    except LibraryFormatError as error:
        return None, [*issues, error.issue]
    return material, issues


def _check_format(value: object, source: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _file_error(source, _ROOT_FORMAT_INVALID)
    if value != FORMAT_VERSION:
        template = _ROOT_FORMAT_NEWER if value > FORMAT_VERSION else _ROOT_FORMAT_UNSUPPORTED
        shown = quoted_value(value)
        raise _file_error(source, template, format=shown, supported=str(FORMAT_VERSION))


def _select_entries(
    raw_entries: list[object], source: str, folder: Path | None
) -> tuple[list[_Entry], list[LibraryIssue]]:
    """Entrées objets parmi les ``MAX_MATERIALS`` premières ; une erreur par règle violée."""
    issues: list[LibraryIssue] = []
    if len(raw_entries) > MAX_MATERIALS:
        issues.append(
            _make_issue(
                Severity.ERROR,
                source,
                _TOO_MANY_MATERIALS,
                count=str(len(raw_entries)),
                max=str(MAX_MATERIALS),
            )
        )
    kept = list(enumerate(raw_entries[:MAX_MATERIALS], start=1))
    rejected = [str(position) for position, raw in kept if not isinstance(raw, dict)]
    if rejected:
        positions = ", ".join(rejected)
        issues.append(
            _make_issue(Severity.ERROR, source, _ENTRIES_NOT_OBJECTS, positions=positions)
        )
    entries = [
        _Entry(source, position, raw, folder) for position, raw in kept if isinstance(raw, dict)
    ]
    return entries, issues


def _root_unknown_keys_issues(data: Mapping[object, object], source: str) -> list[LibraryIssue]:
    """Au plus un avertissement, qui liste les clés inconnues de la racine."""
    keys = [quoted_value(key) for key in data if key not in _ROOT_KEYS]
    if not keys:
        return []
    template = _ROOT_UNKNOWN_KEYS_MORE if len(keys) > MAX_LISTED_KEYS else _ROOT_UNKNOWN_KEYS
    return [_make_issue(Severity.WARNING, source, template, **_unknown_keys_params(keys))]


def _parse_root(
    data: object, source: str, folder: Path | None
) -> tuple[list[_Entry], list[LibraryIssue]]:
    """Vérifie la racine ; lève :class:`LibraryFormatError` si le fichier doit être ignoré."""
    if not isinstance(data, dict):
        raise _file_error(source, _ROOT_NOT_OBJECT)
    if isinstance(data, _JsonObject):
        raise _file_error(source, _ROOT_DUPLICATE_KEY, field=quoted_value(data.duplicate_keys[0]))
    _check_format(data.get("format"), source)
    raw_entries = data.get("materials")
    if not isinstance(raw_entries, list):
        raise _file_error(source, _ROOT_MATERIALS_INVALID)
    warnings = _root_unknown_keys_issues(data, source)
    entries, issues = _select_entries(raw_entries, source, folder)
    return entries, [*warnings, *issues]


def parse_materials(
    data: object, source: str, folder: Path | None = None
) -> tuple[list[Material], list[LibraryIssue]]:
    """Valide un document JSON déjà décodé (format 1) et en extrait les matériaux valides.

    ``folder`` est le dossier du fichier, auquel les chemins des textures sont relatifs ; sans
    lui, une entrée qui déclare une texture est rejetée. Au plus ``MAX_ISSUES`` anomalies sont
    renvoyées, suivies d'une anomalie de synthèse.
    """
    try:
        entries, issues = _parse_root(data, source, folder)
    except LibraryFormatError as error:
        return [], [error.issue]
    materials: dict[str, Material] = {}
    for entry in entries:
        material, entry_issues = _parse_entry(entry)
        issues.extend(entry_issues)
        if material is None:
            continue
        if material.id in materials:
            duplicate = replace(entry, material_id=material.id)
            issues.append(duplicate.issue(Severity.ERROR, _ENTRY_DUPLICATE_ID, "id"))
            continue
        materials[material.id] = material
    return list(materials.values()), _capped(issues)


def _unreadable(source: str, error: OSError) -> LibraryFormatError:
    return _file_error(source, _FILE_UNREADABLE, error=error.strerror or type(error).__name__)


def _read_at_most(descriptor: int, limit: int) -> bytes:
    """Lit au plus ``limit`` octets du descripteur (jusqu'à la fin du fichier)."""
    chunks: list[bytes] = []
    remaining = limit
    while remaining > 0:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_regular_file(descriptor: int, source: str) -> bytes:
    """Vérifie le type et la taille du fichier ouvert, puis le lit (lecture bornée)."""
    status = os.fstat(descriptor)
    if not stat.S_ISREG(status.st_mode):
        raise _file_error(source, _FILE_NOT_REGULAR)
    limit = str(MAX_FILE_BYTES)
    if status.st_size > MAX_FILE_BYTES:
        raise _file_error(source, _FILE_TOO_LARGE, size=str(status.st_size), max=limit)
    content = _read_at_most(descriptor, MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise _file_error(source, _FILE_TOO_LARGE, size=f"> {limit}", max=limit)
    return content


def _read_bytes(path: Path, source: str) -> bytes:
    """Lit au plus ``MAX_FILE_BYTES`` octets ; ``FileNotFoundError`` si le fichier est absent.

    Type et taille sont vérifiés sur le descripteur ouvert (``fstat``), puis la lecture se fait
    sur ce même descripteur : le fichier ne peut pas être remplacé entre contrôle et lecture.
    """
    try:
        descriptor = os.open(path, _OPEN_FLAGS)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise _unreadable(source, error) from error
    except ValueError as error:  # octet nul dans le chemin
        raise _file_error(source, _FILE_UNREADABLE, error=str(error)) from error
    try:
        return _read_regular_file(descriptor, source)
    except OSError as error:
        raise _unreadable(source, error) from error
    finally:
        os.close(descriptor)


class _NonFiniteConstantError(ValueError):
    """Constante JSON ``NaN``, ``Infinity`` ou ``-Infinity`` rencontrée."""

    def __init__(self, constant: str) -> None:
        super().__init__(constant)
        self.constant = constant


def _reject_constant(constant: str) -> object:
    raise _NonFiniteConstantError(constant)


def _decode_json(content: bytes, source: str) -> object:
    """Décode du JSON UTF-8 strict (BOM initial toléré) ; :class:`LibraryFormatError` sinon.

    Les objets à clés en double sont marqués (:class:`_JsonObject`) pour être signalés.
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise _file_error(source, _FILE_NOT_UTF8) from error
    try:
        return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_json_object)
    except _NonFiniteConstantError as error:
        raise _file_error(source, _FILE_NON_FINITE, value=error.constant) from error
    except ValueError as error:
        raise _file_error(source, _FILE_INVALID_JSON, error=str(error)) from error
    except RecursionError as error:
        raise _file_error(source, _FILE_TOO_DEEP) from error


def read_materials_file(
    path: Path, source: str | None = None
) -> tuple[list[Material], list[LibraryIssue]]:
    """Lit et valide un fichier de matériaux ; un fichier absent renvoie ``([], [])``.

    La taille est vérifiée avant lecture et seul ``json.loads`` est utilisé : aucune autre
    forme de désérialisation. ``source`` (chemin du fichier par défaut) est cité dans les
    anomalies.
    """
    label = str(path) if source is None else source
    result = _read_existing_file(path, label)
    return ([], []) if result is None else result


def _read_existing_file(path: Path, label: str) -> tuple[list[Material], list[LibraryIssue]] | None:
    """Comme :func:`read_materials_file`, mais ``None`` si le fichier est absent."""
    try:
        data = _decode_json(_read_bytes(path, label), label)
    except FileNotFoundError:
        return None
    except LibraryFormatError as error:
        return [], [error.issue]
    return parse_materials(data, label, path.parent)


def _label(material: Material) -> str:
    """Libellé français (déjà en forme NFC) : clé d'unicité de la bibliothèque."""
    return material.name("fr")


def _rejected(source: str, material: Material, label_owner: str | None) -> LibraryIssue:
    """Erreur de fusion : identifiant en double, ou libellé porté par ``label_owner``."""
    if label_owner is None:
        return _make_issue(
            Severity.ERROR, source, _ENTRY_DUPLICATE_ID, material.id, id=material.id, field="id"
        )
    return _make_issue(
        Severity.ERROR,
        source,
        _MERGE_LABEL_TAKEN,
        material.id,
        id=material.id,
        field="name",
        label=_label(material),
        other=label_owner,
    )


def _merge_builtin(builtin: Sequence[Material]) -> tuple[dict[str, Material], list[LibraryIssue]]:
    """Matériaux intégrés uniques (identifiant puis libellé), dans l'ordre ; doublons rejetés."""
    by_id: dict[str, Material] = {}
    owner_of_label: dict[str, str] = {}
    issues: list[LibraryIssue] = []
    for material in builtin:
        owner = owner_of_label.get(_label(material))
        if material.id in by_id or owner is not None:
            shown_owner = None if material.id in by_id else owner
            issues.append(_rejected(BUILTIN_SOURCE, material, shown_owner))
            continue
        by_id[material.id] = material
        owner_of_label[_label(material)] = material.id
    return by_id, issues


@dataclass(frozen=True)
class _Candidate:
    """Entrée utilisateur retenue provisoirement, avec sa position dans le fichier."""

    position: int
    material: Material


def _label_losers(
    builtin: Mapping[str, Material], candidates: Mapping[str, _Candidate]
) -> list[str]:
    """Identifiants utilisateur qui perdent un libellé disputé, au vu de l'état courant.

    Un matériau intégré non remplacé garde toujours son libellé ; entre deux entrées
    utilisateur, la première du fichier le garde.
    """
    holders: dict[str, list[tuple[int, str]]] = {}
    for material in builtin.values():
        if material.id not in candidates:
            holders.setdefault(_label(material), []).append((-1, material.id))
    for candidate in candidates.values():
        holders.setdefault(_label(candidate.material), []).append(
            (candidate.position, candidate.material.id)
        )
    losers: list[str] = []
    for owners in holders.values():
        losers += [material_id for _, material_id in sorted(owners)[1:]]
    return losers


def _user_candidates(
    user: Sequence[Material], source: str
) -> tuple[dict[str, _Candidate], dict[int, LibraryIssue]]:
    """Première entrée de chaque identifiant ; les suivantes sont rejetées (erreur)."""
    candidates: dict[str, _Candidate] = {}
    issues: dict[int, LibraryIssue] = {}
    for position, material in enumerate(user):
        if material.id in candidates:
            issues[position] = _rejected(source, material, None)
        else:
            candidates[material.id] = _Candidate(position, material)
    return candidates, issues


def _merge_user(
    builtin: Mapping[str, Material], user: Sequence[Material], source: str
) -> tuple[list[Material], list[LibraryIssue]]:
    """Applique tous les remplacements et ajouts, puis rétablit l'unicité des libellés.

    Le résultat ne dépend pas de l'ordre des remplacements : deux matériaux intégrés peuvent
    échanger leurs libellés. Une entrée rejetée pour son libellé rend sa place au matériau
    intégré qu'elle remplaçait, ce qui peut à son tour rejeter une autre entrée.
    """
    candidates, issues = _user_candidates(user, source)
    label_rejected: list[_Candidate] = []
    while losers := _label_losers(builtin, candidates):
        label_rejected += [candidates.pop(material_id) for material_id in losers]
    merged = [candidates[i].material if i in candidates else m for i, m in builtin.items()]
    merged += [c.material for c in candidates.values() if c.material.id not in builtin]
    owner_of_label = {_label(material): material.id for material in merged}
    for rejected in label_rejected:
        owner = owner_of_label[_label(rejected.material)]
        issues[rejected.position] = _rejected(source, rejected.material, owner)
    for candidate in candidates.values():
        if candidate.material.id in builtin:
            material_id = candidate.material.id
            info = _make_issue(Severity.INFO, source, _MERGE_REPLACED, material_id, id=material_id)
            issues[candidate.position] = info
    return merged, [issues[position] for position in sorted(issues)]


def merge_materials(
    builtin: Sequence[Material], user: Sequence[Material], user_source: str
) -> tuple[MaterialLibrary, list[LibraryIssue]]:
    """Fusionne les matériaux de l'utilisateur sur la bibliothèque intégrée (par identifiant).

    Identifiant nouveau : ajouté à la fin. Identifiant existant : remplace entièrement le
    matériau intégré, à sa place (anomalie info). Une fois tous les remplacements appliqués,
    une entrée utilisateur dont le libellé français est porté par un autre matériau est
    rejetée (erreur) ; le résultat ne dépend pas de l'ordre des remplacements.
    """
    by_id, issues = _merge_builtin(builtin)
    merged, user_issues = _merge_user(by_id, user, user_source)
    return MaterialLibrary(merged), _capped([*issues, *user_issues])


def load_library(
    builtin_path: Path, user_path: Path | None
) -> tuple[MaterialLibrary, list[LibraryIssue]]:
    """Charge la bibliothèque intégrée, puis la fusionne avec le fichier utilisateur s'il existe.

    Au plus ``MAX_ISSUES`` anomalies sont renvoyées, suivies d'une anomalie de synthèse.
    """
    result = _read_existing_file(builtin_path, BUILTIN_SOURCE)
    if result is None:
        missing = _make_issue(
            Severity.ERROR, BUILTIN_SOURCE, _FILE_BUILTIN_MISSING, path=str(builtin_path)
        )
        result = [], [missing]
    builtin, issues = result
    user: list[Material] = []
    user_source = "" if user_path is None else str(user_path)
    if user_path is not None:
        user, user_issues = read_materials_file(user_path, user_source)
        issues += user_issues
    library, merge_issues = merge_materials(builtin, user, user_source)
    return library, _capped([*issues, *merge_issues])
