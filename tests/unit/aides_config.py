# SPDX-License-Identifier: LGPL-2.1-or-later
"""Catalogue d'exemple des tests de ``kit/config`` (ADR 0069)."""

from __future__ import annotations

from freecad.menuiserie.kit.config.catalog import Catalog, Kind, Setting


def length_setting(key: str = "Jeu", default: float = 2.0, *, remember: bool = True) -> Setting:
    return Setting(
        key,
        Kind.FLOAT,
        default,
        "Jeu",
        "Jeu d'usinage.",
        "Assemblages",
        unit="mm",
        minimum=0.0,
        maximum=20.0,
        remember_last=remember,
    )


def sample_catalog() -> Catalog:
    return Catalog(
        [
            length_setting(),
            Setting(
                "Debouchant",
                Kind.BOOL,
                False,
                "Débouchant",
                "Traverse.",
                "Assemblages",
                remember_last=True,
            ),
            Setting(
                "Nombre", Kind.INT, 3, "Nombre", "Nombre.", "Assemblages", minimum=1, maximum=9
            ),
            Setting(
                "Profil",
                Kind.CHOICE,
                "Round",
                "Profil",
                "Profil.",
                "Chants",
                choices=("Round", "Chamfer"),
            ),
            Setting("Dossier", Kind.PATH, "", "Dossier", "Dossier.", "Stockage"),
        ]
    )
