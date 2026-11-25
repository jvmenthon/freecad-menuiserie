# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier Menuiserie : catalogue, accès et dossier de l'atelier (ADR 0031, 0069).

Seul point de lecture des préférences de l'atelier : les autres modules demandent une valeur à
:func:`settings`, jamais à ``App.ParamGet``. ``core/`` ne lit aucun réglage, il reçoit des valeurs.
La mécanique (validation, stockage, « Dernier utilisé ») vient de :mod:`freecad.menuiserie.kit`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.edges import BROKEN_EDGE_MM, EdgeFamily
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints.dovetail import DEFAULT_ANGLE_DEG
from freecad.menuiserie.core.joints.dowels import MAX_SPACING_MM, DowelParams
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.core.joints.rabbet import RabbetParams
from freecad.menuiserie.core.joints.tongue_groove import (
    DEFAULT_TONGUE_LENGTH_MM,
    TongueGrooveParams,
)
from freecad.menuiserie.core.part_model import (
    DEFAULT_DIMENSIONS,
    DEFAULT_PANEL_ALLOWANCES,
    DEFAULT_SOLID_ALLOWANCES,
    MAX_DIMENSION_MM,
    MIN_DIMENSION_MM,
    Allowances,
)
from freecad.menuiserie.kit.config.catalog import Catalog, Kind, Setting
from freecad.menuiserie.kit.config.folder import workshop_folder as resolve_workshop_folder
from freecad.menuiserie.kit.config.store import FreeCADStore, Settings

__all__ = [
    "CATALOG",
    "PARAM_PATH",
    "USER_LIBRARY_FOLDER",
    "USER_LIBRARY_PARAM",
    "WORKSHOP_FOLDER",
    "settings",
    "workshop_folder",
]

PARAM_PATH: Final = "User parameter:BaseApp/Preferences/Mod/Menuiserie"
USER_LIBRARY_PARAM: Final = "UserLibraryPath"  # ancien réglage, lu pour materiaux.json seul
USER_LIBRARY_FOLDER: Final = "Menuiserie"  # sous-dossier des données utilisateur de FreeCAD

# Clés (noms des paramètres FreeCAD, figés : une clé renommée perd la valeur de l'utilisateur).
BROKEN_EDGE: Final = "NewPartBrokenEdge"
BROKEN_EDGE_SIZE: Final = "NewPartBrokenEdgeSize"
EDGE_PROFILE: Final = "EdgeProfileFamily"
EDGE_PROFILE_SIZE: Final = "EdgeProfileSize"
LENGTH: Final = "NewPartLength"
WIDTH: Final = "NewPartWidth"
THICKNESS: Final = "NewPartThickness"
MATERIAL: Final = "NewPartMaterial"
SOLID_ALLOWANCES: Final = ("SolidLengthAllowance", "SolidWidthAllowance", "SolidThicknessAllowance")
PANEL_ALLOWANCES: Final = ("PanelLengthAllowance", "PanelWidthAllowance", "PanelThicknessAllowance")
MORTISE_CLEARANCE: Final = "MortiseClearance"
MORTISE_THROUGH: Final = "MortiseThrough"
GROOVE_CLEARANCE: Final = "GrooveClearance"
TONGUE_LENGTH: Final = "TongueLength"
GROOVE_THROUGH: Final = "GrooveThrough"
RABBET_THROUGH: Final = "RabbetThrough"
DOWEL_CLEARANCE: Final = "DowelHoleClearance"
DOWEL_SPACING: Final = "DowelMaxSpacing"
DOVETAIL_ANGLE: Final = "DovetailAngle"
SLOT_FREE_SIZE: Final = "LooseTenonFreeSize"
WORKSHOP_FOLDER: Final = "WorkshopFolder"
PROJECTS_FOLDER: Final = "ProjectsFolder"

MM: Final = QT_TRANSLATE_NOOP("Menuiserie", "mm")
DEGREES: Final = QT_TRANSLATE_NOOP("Menuiserie", "°")
NEW_PARTS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièces neuves")
EDGES: Final = QT_TRANSLATE_NOOP("Menuiserie", "Chants")
JOINTS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Assemblages")
STORAGE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Stockage")

_MAX_CLEARANCE_MM: Final = 20.0  # jeu d'usinage : au-delà, c'est une faute de saisie
_MAX_EDGE_MM: Final = 100.0
_MAX_ALLOWANCE_MM: Final = 1000.0


def _length(  # noqa: PLR0913 (description d'un réglage : tous ses champs sont nommés)
    key: str,
    default: float,
    label: str,
    tooltip: str,
    group: str,
    *,
    minimum: float = MIN_DIMENSION_MM,
    maximum: float = MAX_DIMENSION_MM,
    remember_last: bool = False,
) -> Setting:
    """Cote en mm."""
    return Setting(
        key,
        Kind.FLOAT,
        default,
        label,
        tooltip,
        group,
        unit=MM,
        minimum=minimum,
        maximum=maximum,
        remember_last=remember_last,
    )


def _flag(key: str, default: bool, label: str, tooltip: str, group: str) -> Setting:
    """Case à cocher qui retient le dernier choix si on le demande."""
    return Setting(key, Kind.BOOL, default, label, tooltip, group, remember_last=True)


_ALLOWANCE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Ajoutée à la cote finie dans la liste de débit d'une pièce neuve."
)


def _allowances(
    keys: tuple[str, str, str], values: Allowances, labels: tuple[str, str, str]
) -> list[Setting]:
    """Surcotes de débit (longueur, largeur, épaisseur) d'un type de pièce."""
    defaults = (values.length, values.width, values.thickness)
    return [
        _length(
            key, value, label, _ALLOWANCE_TIP, NEW_PARTS, minimum=0.0, maximum=_MAX_ALLOWANCE_MM
        )
        for key, value, label in zip(keys, defaults, labels, strict=True)
    ]


def _new_parts() -> list[Setting]:
    return [
        _length(
            LENGTH,
            DEFAULT_DIMENSIONS.length,
            QT_TRANSLATE_NOOP("Menuiserie", "Longueur"),
            QT_TRANSLATE_NOOP("Menuiserie", "Longueur d'une pièce neuve."),
            NEW_PARTS,
        ),
        _length(
            WIDTH,
            DEFAULT_DIMENSIONS.width,
            QT_TRANSLATE_NOOP("Menuiserie", "Largeur"),
            QT_TRANSLATE_NOOP("Menuiserie", "Largeur d'une pièce neuve."),
            NEW_PARTS,
        ),
        _length(
            THICKNESS,
            DEFAULT_DIMENSIONS.thickness,
            QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur"),
            QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur d'une pièce neuve."),
            NEW_PARTS,
        ),
        Setting(
            MATERIAL,
            Kind.TEXT,
            "",
            QT_TRANSLATE_NOOP("Menuiserie", "Matériau"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Matériau d'une pièce neuve. Vide : premier de la bibliothèque."
            ),
            NEW_PARTS,
        ),
        *_allowances(
            SOLID_ALLOWANCES,
            DEFAULT_SOLID_ALLOWANCES,
            (
                QT_TRANSLATE_NOOP("Menuiserie", "Surcote en longueur, massif"),
                QT_TRANSLATE_NOOP("Menuiserie", "Surcote en largeur, massif"),
                QT_TRANSLATE_NOOP("Menuiserie", "Surcote en épaisseur, massif"),
            ),
        ),
        *_allowances(
            PANEL_ALLOWANCES,
            DEFAULT_PANEL_ALLOWANCES,
            (
                QT_TRANSLATE_NOOP("Menuiserie", "Surcote en longueur, panneau"),
                QT_TRANSLATE_NOOP("Menuiserie", "Surcote en largeur, panneau"),
                QT_TRANSLATE_NOOP("Menuiserie", "Surcote en épaisseur, panneau"),
            ),
        ),
    ]


def _edges() -> list[Setting]:
    return [
        _flag(
            BROKEN_EDGE,
            False,
            QT_TRANSLATE_NOOP("Menuiserie", "Arête cassée sur les pièces neuves"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Ajoute une arête cassée à toutes les arêtes d'une pièce neuve."
            ),
            EDGES,
        ),
        _length(
            BROKEN_EDGE_SIZE,
            BROKEN_EDGE_MM,
            QT_TRANSLATE_NOOP("Menuiserie", "Taille de l'arête cassée"),
            QT_TRANSLATE_NOOP("Menuiserie", "Rayon de l'arête cassée des pièces neuves."),
            EDGES,
            maximum=_MAX_EDGE_MM,
            remember_last=True,
        ),
        Setting(
            EDGE_PROFILE,
            Kind.CHOICE,
            EdgeFamily.ROUND.value,
            QT_TRANSLATE_NOOP("Menuiserie", "Profil proposé"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Profil proposé à l'ouverture de la finition des chants."
            ),
            EDGES,
            choices=tuple(family.value for family in EdgeFamily),
            remember_last=True,
        ),
        _length(
            EDGE_PROFILE_SIZE,
            BROKEN_EDGE_MM,
            QT_TRANSLATE_NOOP("Menuiserie", "Taille du profil proposé"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Cote proposée à l'ouverture de la finition des chants."
            ),
            EDGES,
            maximum=_MAX_EDGE_MM,
            remember_last=True,
        ),
    ]


def _clearance(key: str, default: float, label: str, tooltip: str) -> Setting:
    return _length(
        key,
        default,
        label,
        tooltip,
        JOINTS,
        minimum=0.0,
        maximum=_MAX_CLEARANCE_MM,
        remember_last=True,
    )


def _joints() -> list[Setting]:
    return [
        _clearance(
            MORTISE_CLEARANCE,
            MortiseTenonParams().mortise_clearance,
            QT_TRANSLATE_NOOP("Menuiserie", "Jeu de mortaise"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Profondeur de mortaise en plus de la longueur du tenon."
            ),
        ),
        _flag(
            MORTISE_THROUGH,
            MortiseTenonParams().through,
            QT_TRANSLATE_NOOP("Menuiserie", "Mortaise débouchante"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Mortaise qui traverse la pièce, pour un nouvel assemblage."
            ),
            JOINTS,
        ),
        _clearance(
            GROOVE_CLEARANCE,
            TongueGrooveParams().groove_clearance,
            QT_TRANSLATE_NOOP("Menuiserie", "Jeu de rainure"),
            QT_TRANSLATE_NOOP("Menuiserie", "Profondeur de rainure en plus de la languette."),
        ),
        _length(
            TONGUE_LENGTH,
            DEFAULT_TONGUE_LENGTH_MM,
            QT_TRANSLATE_NOOP("Menuiserie", "Longueur de languette"),
            QT_TRANSLATE_NOOP("Menuiserie", "Longueur de languette d'un nouvel assemblage."),
            JOINTS,
            maximum=_MAX_ALLOWANCE_MM,
            remember_last=True,
        ),
        _flag(
            GROOVE_THROUGH,
            TongueGrooveParams().through_groove,
            QT_TRANSLATE_NOOP("Menuiserie", "Rainure débouchante"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Rainure sur toute la longueur, pour un nouvel assemblage."
            ),
            JOINTS,
        ),
        _flag(
            RABBET_THROUGH,
            RabbetParams().through,
            QT_TRANSLATE_NOOP("Menuiserie", "Feuillure débouchante"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Feuillure sur toute la longueur, pour un nouvel assemblage."
            ),
            JOINTS,
        ),
        _clearance(
            DOWEL_CLEARANCE,
            DowelParams().hole_clearance,
            QT_TRANSLATE_NOOP("Menuiserie", "Jeu de fond des tourillons"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Profondeur de perçage en plus du tourillon, de chaque côté."
            ),
        ),
        _length(
            DOWEL_SPACING,
            MAX_SPACING_MM,
            QT_TRANSLATE_NOOP("Menuiserie", "Entraxe maximal des tourillons"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Écart maximal entre deux tourillons placés automatiquement."
            ),
            JOINTS,
            minimum=10.0,
            maximum=_MAX_ALLOWANCE_MM,
            remember_last=True,
        ),
        Setting(
            DOVETAIL_ANGLE,
            Kind.FLOAT,
            DEFAULT_ANGLE_DEG,
            QT_TRANSLATE_NOOP("Menuiserie", "Angle de queue d'aronde"),
            QT_TRANSLATE_NOOP("Menuiserie", "Angle des flancs des queues d'un nouvel assemblage."),
            JOINTS,
            unit=DEGREES,
            minimum=1.0,
            maximum=30.0,
            remember_last=True,
        ),
        _flag(
            SLOT_FREE_SIZE,
            False,
            QT_TRANSLATE_NOOP("Menuiserie", "Faux tenons : taille libre"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Propose une taille libre plutôt que la liste des tailles."
            ),
            JOINTS,
        ),
    ]


def _storage() -> list[Setting]:
    return [
        Setting(
            WORKSHOP_FOLDER,
            Kind.PATH,
            "",
            QT_TRANSLATE_NOOP("Menuiserie", "Dossier de l'atelier"),
            QT_TRANSLATE_NOOP(
                "Menuiserie",
                "Fichiers personnels : matériaux, dimensions, quincaillerie. Vide : par défaut.",
            ),
            STORAGE,
        ),
        Setting(
            PROJECTS_FOLDER,
            Kind.PATH,
            "",
            QT_TRANSLATE_NOOP("Menuiserie", "Dossier des projets"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Dossier proposé pour un nouveau projet. Vide : Documents/Menuiserie."
            ),
            STORAGE,
        ),
    ]


CATALOG: Final = Catalog([*_new_parts(), *_edges(), *_joints(), *_storage()])


def settings() -> Settings:
    """Réglages de l'atelier, lus dans les préférences de FreeCAD et bornés par :data:`CATALOG`."""
    return Settings(CATALOG, FreeCADStore(App.ParamGet, PARAM_PATH))


def workshop_folder() -> Path:
    """Dossier de l'atelier (ADR 0069) : le réglage, sinon le dossier de l'ancien chemin de
    bibliothèque, sinon ``<données utilisateur de FreeCAD>/Menuiserie``."""
    legacy = str(App.ParamGet(PARAM_PATH).GetString(USER_LIBRARY_PARAM, ""))
    fallback = Path(App.getUserAppDataDir()) / USER_LIBRARY_FOLDER
    return resolve_workshop_folder(str(settings().value(WORKSHOP_FOLDER)), legacy, fallback)
