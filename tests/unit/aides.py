# SPDX-License-Identifier: LGPL-2.1-or-later
"""Données et fabriques partagées par les tests unitaires de la bibliothèque de matériaux."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from freecad.menuiserie.core.materials import LibraryIssue, Material, MaterialKind, Severity

SOURCE = "/chemin/utilisateur/materiaux.json"
OAK: dict[str, object] = {
    "id": "chene",
    "kind": "solid",
    "name": "Chêne",
    "density": 710,
    "thicknesses": [22],
    "color": "#B8875A",
}


def _can_create_symlinks() -> bool:
    """Faux sous Windows sans le droit de créer des liens symboliques."""
    with tempfile.TemporaryDirectory() as folder:
        try:
            (Path(folder) / "lien").symlink_to(folder)
        except OSError:
            return False
    return True


requires_symlinks = pytest.mark.skipif(
    not _can_create_symlinks(), reason="création de liens symboliques impossible"
)


def document(*entries: object, **root: object) -> dict[str, object]:
    """Document de bibliothèque au format 1 ; ``root`` ajoute ou remplace des clés racines."""
    return {"format": 1, "materials": list(entries), **root}


def errors(issues: list[LibraryIssue]) -> list[LibraryIssue]:
    """Seuls les signalements de gravité « erreur »."""
    return [issue for issue in issues if issue.severity is Severity.ERROR]


def write(tmp_path: Path, content: str | bytes, name: str = "materiaux.json") -> Path:
    """Écrit ``content`` (texte UTF-8 ou octets bruts) dans ``tmp_path / name``."""
    path = tmp_path / name
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


def make_material(
    material_id: str,
    label: str,
    kind: MaterialKind = MaterialKind.SOLID,
    *,
    has_grain: bool | None = None,
) -> Material:
    """Matériau valide minimal ; le fil suit par défaut la règle de ``kind``."""
    return Material(
        id=material_id,
        kind=kind,
        names={"fr": label},
        density=600.0,
        thicknesses=(18.0, 22.0),
        color=(10, 20, 30),
        has_grain=kind.has_grain_by_default if has_grain is None else has_grain,
    )
