# SPDX-License-Identifier: LGPL-2.1-or-later
"""Choix d'un gabarit de page parmi ceux que TechDraw fournit (ADR 0053 : aucun gabarit installé).

Les noms de fichiers changent d'une version de FreeCAD à l'autre (``A3_Landscape_ISO7200TD.svg``,
``ISO/A3_Landscape_ISO5457_minimal.svg``…) : le choix se fait sur des mots du chemin, pas sur un
nom fixe.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from freecad.menuiserie.core.drawing._layout import Orientation

__all__ = ["pick_template"]

# Du préféré au toléré : cartouche ISO 7200, autre gabarit ISO, puis n'importe lequel.
_PREFERRED: Final = ("iso7200", "iso5457", "iso")
# Variantes d'un même gabarit à ne prendre qu'à défaut : feuille nue, autres normes et métiers.
_LAST_RESORT: Final = ("blank", "asme", "ansi", "gost", "arch", "din", "zh_", "ru_")


def _words(path: str) -> str:
    return path.replace("\\", "/").lower()


def _rank(path: str) -> tuple[int, int, int, str]:
    words = _words(path)
    preferred = next(
        (index for index, word in enumerate(_PREFERRED) if word in words), len(_PREFERRED)
    )
    resort = sum(word in words for word in _LAST_RESORT)
    return resort, preferred, len(path), path


def pick_template(paths: Iterable[str], fmt: str, orientation: Orientation) -> str | None:
    """Meilleur gabarit de ``paths`` (chemins de fichiers SVG) pour le format ``fmt`` et le sens
    ``orientation`` ; ``None`` si aucun ne convient. Le choix est stable : à qualité égale, le
    chemin le plus court puis l'ordre alphabétique."""
    wanted = (fmt.strip().lower(), orientation.value.lower())
    if not wanted[0]:
        return None
    candidates = [
        path
        for path in paths
        if _words(path).endswith(".svg")
        and all(word in _words(path).rsplit("/", 1)[-1] for word in wanted)
    ]
    return min(candidates, key=_rank, default=None)
