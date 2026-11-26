# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier lus au moment de l'usage (ADR 0069).

Les réglages d'interface (pas de rotation, panneau « Structure », dossier d'export) n'écrivent
rien dans un document : ils sont relus à chaque usage, donc un changement agit aussitôt. Le
préfixe des repères, lui, est copié dans les pièces numérotées (il n'est lu qu'à la numérotation).
"""

from __future__ import annotations

from pathlib import Path

from freecad.menuiserie.core.cutlist import DEFAULT_MARK_PREFIX
from freecad.menuiserie.features import settings as config
from freecad.menuiserie.kit.config.folder import absolute_path

__all__ = ["export_folder", "mark_prefix", "rotation_step", "structure_auto_open"]


def rotation_step() -> float:
    """Pas de l'aimant d'angle d'une rotation à la souris (degrés)."""
    return float(config.settings().value(config.ROTATION_STEP))


def structure_auto_open() -> bool:
    """Vrai si le panneau « Structure » s'ouvre seul à l'activation de l'atelier."""
    return bool(config.settings().value(config.STRUCTURE_AUTO_OPEN))


def export_folder() -> Path | None:
    """Dossier proposé pour exporter la liste de débit ; ``None`` (dossier du document) s'il est
    vide ou n'est pas un chemin absolu."""
    return absolute_path(str(config.settings().value(config.CUTLIST_EXPORT_FOLDER)))


def mark_prefix() -> str:
    """Préfixe des repères attribués par la numérotation automatique : « M » si le réglage est
    vide."""
    return str(config.settings().value(config.MARK_PREFIX)).strip() or DEFAULT_MARK_PREFIX
