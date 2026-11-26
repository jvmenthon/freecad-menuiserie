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
from freecad.menuiserie.core.part_model import (
    DEFAULT_DIMENSIONS,
    DEFAULT_PANEL_ALLOWANCES,
    DEFAULT_SOLID_ALLOWANCES,
    Allowances,
    GrainDirection,
)
from freecad.menuiserie.features import settings_hardware as hardware
from freecad.menuiserie.features import settings_interface as interface
from freecad.menuiserie.features import settings_joints as joints
from freecad.menuiserie.features import settings_output as output
from freecad.menuiserie.features import settings_templates as templates
from freecad.menuiserie.features.settings_build import flag_setting, length_setting
from freecad.menuiserie.kit.config.catalog import Catalog, Kind, Setting
from freecad.menuiserie.kit.config.folder import absolute_path
from freecad.menuiserie.kit.config.folder import workshop_folder as resolve_workshop_folder
from freecad.menuiserie.kit.config.store import FreeCADStore, Settings

__all__ = [
    "CATALOG",
    "PARAM_PATH",
    "USER_LIBRARY_FOLDER",
    "USER_LIBRARY_PARAM",
    "WORKSHOP_FOLDER",
    "legacy_library_file",
    "settings",
    "workshop_folder",
]

PARAM_PATH: Final = "User parameter:BaseApp/Preferences/Mod/Menuiserie"
USER_LIBRARY_PARAM: Final = "UserLibraryPath"  # ancien réglage, lu pour materiaux.json seul
USER_LIBRARY_FOLDER: Final = "Menuiserie"  # sous-dossier des données utilisateur de FreeCAD

# Clés et groupe des assemblages (:mod:`.settings_joints`), accessibles ici comme les autres.
DOVETAIL_ANGLE: Final = joints.DOVETAIL_ANGLE
DOWEL_CLEARANCE: Final = joints.DOWEL_CLEARANCE
DOWEL_SPACING: Final = joints.DOWEL_SPACING
GROOVE_CLEARANCE: Final = joints.GROOVE_CLEARANCE
GROOVE_THROUGH: Final = joints.GROOVE_THROUGH
JOINTS: Final = joints.JOINTS
MORTISE_CLEARANCE: Final = joints.MORTISE_CLEARANCE
MORTISE_THROUGH: Final = joints.MORTISE_THROUGH
RABBET_THROUGH: Final = joints.RABBET_THROUGH
SLOT_FREE_SIZE: Final = joints.SLOT_FREE_SIZE
SLOT_SPACING: Final = joints.SLOT_SPACING
TONGUE_LENGTH: Final = joints.TONGUE_LENGTH

# Taquets, gabarits, liste de débit, plans et affichage : clés et groupes de leurs catalogues.
SHELF_PIN_DEPTH: Final = hardware.SHELF_PIN_DEPTH
SHELF_PIN_DIAMETER: Final = hardware.SHELF_PIN_DIAMETER
SHELF_PIN_PITCH: Final = hardware.SHELF_PIN_PITCH
SHELF_PINS: Final = hardware.SHELF_PINS
CARCASS_FIELDS: Final = templates.CARCASS_FIELDS
TEMPLATES: Final = templates.TEMPLATES
CUTLIST: Final = output.CUTLIST
CUTLIST_EXPORT_FOLDER: Final = output.CUTLIST_EXPORT_FOLDER
DRAWING_FORMAT: Final = output.DRAWING_FORMAT
DRAWINGS: Final = output.DRAWINGS
MARK_PREFIX: Final = output.MARK_PREFIX
DISPLAY: Final = interface.DISPLAY
ROTATION_STEP: Final = interface.ROTATION_STEP
STRUCTURE_AUTO_OPEN: Final = interface.STRUCTURE_AUTO_OPEN

# Clés (noms des paramètres FreeCAD, figés : une clé renommée perd la valeur de l'utilisateur).
BROKEN_EDGE: Final = "NewPartBrokenEdge"
BROKEN_EDGE_SIZE: Final = "NewPartBrokenEdgeSize"
EDGE_PROFILE: Final = "EdgeProfileFamily"
EDGE_PROFILE_SIZE: Final = "EdgeProfileSize"
LENGTH: Final = "NewPartLength"
WIDTH: Final = "NewPartWidth"
THICKNESS: Final = "NewPartThickness"
MATERIAL: Final = "NewPartMaterial"
GRAIN: Final = "NewPartGrain"
GRAIN_AUTO: Final = (
    "Auto"  # sens du fil du matériau (valeur du réglage, jamais écrite dans une pièce)
)
SOLID_ALLOWANCES: Final = ("SolidLengthAllowance", "SolidWidthAllowance", "SolidThicknessAllowance")
PANEL_ALLOWANCES: Final = ("PanelLengthAllowance", "PanelWidthAllowance", "PanelThicknessAllowance")
WORKSHOP_FOLDER: Final = "WorkshopFolder"
PROJECTS_FOLDER: Final = "ProjectsFolder"

NEW_PARTS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièces neuves")
EDGES: Final = QT_TRANSLATE_NOOP("Menuiserie", "Chants")
STORAGE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Stockage")

_MAX_EDGE_MM: Final = 100.0
_MAX_ALLOWANCE_MM: Final = 1000.0


_ALLOWANCE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Ajoutée à la cote finie dans la liste de débit d'une pièce neuve."
)


def _allowances(
    keys: tuple[str, str, str], values: Allowances, labels: tuple[str, str, str]
) -> list[Setting]:
    """Surcotes de débit (longueur, largeur, épaisseur) d'un type de pièce."""
    defaults = (values.length, values.width, values.thickness)
    return [
        length_setting(
            key, value, label, _ALLOWANCE_TIP, NEW_PARTS, minimum=0.0, maximum=_MAX_ALLOWANCE_MM
        )
        for key, value, label in zip(keys, defaults, labels, strict=True)
    ]


def _new_parts() -> list[Setting]:
    return [
        length_setting(
            LENGTH,
            DEFAULT_DIMENSIONS.length,
            QT_TRANSLATE_NOOP("Menuiserie", "Longueur"),
            QT_TRANSLATE_NOOP("Menuiserie", "Longueur d'une pièce neuve."),
            NEW_PARTS,
        ),
        length_setting(
            WIDTH,
            DEFAULT_DIMENSIONS.width,
            QT_TRANSLATE_NOOP("Menuiserie", "Largeur"),
            QT_TRANSLATE_NOOP("Menuiserie", "Largeur d'une pièce neuve."),
            NEW_PARTS,
        ),
        length_setting(
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
                "Menuiserie",
                "Matériau d'une pièce neuve. Vide : premier matériau de la bibliothèque.",
            ),
            NEW_PARTS,
        ),
        Setting(
            GRAIN,
            Kind.CHOICE,
            GRAIN_AUTO,
            QT_TRANSLATE_NOOP("Menuiserie", "Sens du fil"),
            QT_TRANSLATE_NOOP(
                "Menuiserie",
                "Sens du fil d'une pièce neuve en matériau à fil. Automatique : celui du matériau.",
            ),
            NEW_PARTS,
            choices=(GRAIN_AUTO, GrainDirection.LENGTH.value, GrainDirection.WIDTH.value),
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
        flag_setting(
            BROKEN_EDGE,
            False,
            QT_TRANSLATE_NOOP("Menuiserie", "Arête cassée sur les pièces neuves"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Ajoute une arête cassée à toutes les arêtes d'une pièce neuve."
            ),
            EDGES,
        ),
        length_setting(
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
        length_setting(
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


def _storage() -> list[Setting]:
    return [
        Setting(
            WORKSHOP_FOLDER,
            Kind.PATH,
            "",
            QT_TRANSLATE_NOOP("Menuiserie", "Dossier de l'atelier"),
            QT_TRANSLATE_NOOP(
                "Menuiserie",
                "Matériaux, dimensions et quincaillerie personnels. Vide : dossier par défaut.",
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


CATALOG: Final = Catalog(
    [
        *_new_parts(),
        *_edges(),
        *joints.joint_settings(),
        *hardware.hardware_settings(),
        *templates.template_settings(),
        *output.output_settings(),
        *interface.interface_settings(),
        *_storage(),
    ]
)


def settings() -> Settings:
    """Réglages de l'atelier, lus dans les préférences de FreeCAD et bornés par :data:`CATALOG`."""
    return Settings(CATALOG, FreeCADStore(App.ParamGet, PARAM_PATH))


def workshop_folder() -> Path:
    """Dossier de l'atelier (ADR 0069) : le réglage, sinon le dossier de l'ancien chemin de
    bibliothèque, sinon ``<données utilisateur de FreeCAD>/Menuiserie``."""
    legacy = legacy_library_file()
    fallback = Path(App.getUserAppDataDir()) / USER_LIBRARY_FOLDER
    return resolve_workshop_folder(
        str(settings().value(WORKSHOP_FOLDER)), str(legacy or ""), fallback
    )


def legacy_library_file() -> Path | None:
    """Ancien paramètre ``UserLibraryPath`` (compatibilité, ADR 0069) s'il est un chemin absolu."""
    return absolute_path(str(App.ParamGet(PARAM_PATH).GetString(USER_LIBRARY_PARAM, "")))
