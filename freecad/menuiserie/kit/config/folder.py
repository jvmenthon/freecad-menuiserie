# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dossier de l'atelier et écriture atomique d'un fichier (ADR 0069).

Python pur : l'atelier fournit le réglage, l'ancien chemin éventuel et le dossier de repli.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

__all__ = ["absolute_path", "workshop_folder", "write_text_atomic"]


def absolute_path(text: str) -> Path | None:
    """Chemin absolu tiré de ``text``, ``None`` s'il est vide, relatif ou invalide."""
    text = text.strip()
    if not text or "\0" in text:
        return None
    try:
        path = Path(text).expanduser()
    except RuntimeError:  # « ~utilisateur » inconnu
        return None
    return path if path.is_absolute() else None


def workshop_folder(custom: str, legacy_file: str, fallback: Path) -> Path:
    """Dossier de l'atelier : le réglage s'il est un chemin absolu, sinon le dossier de l'ancien
    fichier de bibliothèque (aucun fichier n'est déplacé), sinon ``fallback``. Un chemin relatif
    dépendrait du dossier courant de FreeCAD : il est ignoré."""
    folder = absolute_path(custom)
    if folder is not None:
        return folder
    legacy = absolute_path(legacy_file)
    if legacy is not None:
        return legacy.parent
    return fallback


def write_text_atomic(path: Path, text: str, prefix: str = ".tmp-") -> None:
    """Écrit ``text`` (UTF-8, fins de ligne ``\\n``) par un fichier temporaire du même dossier
    puis un remplacement : jamais de fichier à moitié écrit. ``OSError`` si l'écriture échoue."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=prefix)
    try:
        try:
            handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        except BaseException:
            os.close(descriptor)
            raise
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
