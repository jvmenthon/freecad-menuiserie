# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dossier de l'atelier et écriture atomique d'un fichier (ADR 0069).

Python pur : l'atelier fournit le réglage, l'ancien chemin éventuel et le dossier de repli.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

__all__ = ["workshop_folder", "write_text_atomic"]


def workshop_folder(custom: str, legacy_file: str, fallback: Path) -> Path:
    """Dossier de l'atelier : le réglage s'il est renseigné, sinon le dossier de l'ancien fichier
    de bibliothèque (aucun fichier n'est déplacé), sinon ``fallback``."""
    if custom.strip():
        return Path(custom.strip()).expanduser()
    if legacy_file.strip():
        return Path(legacy_file.strip()).expanduser().parent
    return fallback


def write_text_atomic(path: Path, text: str, prefix: str = ".tmp-") -> None:
    """Écrit ``text`` (UTF-8, fins de ligne ``\\n``) par un fichier temporaire du même dossier
    puis un remplacement : jamais de fichier à moitié écrit. ``OSError`` si l'écriture échoue."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=prefix)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
