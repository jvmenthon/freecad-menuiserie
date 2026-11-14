# SPDX-License-Identifier: LGPL-2.1-or-later
"""Génère les gabarits de page de l'atelier dans ``freecad/menuiserie/resources/templates``.

Un gabarit par format (A4 à A0) et par sens, dessiné par
:func:`freecad.menuiserie.core.drawing.template_svg` : cadre et cartouche en français. Rien n'est
installé dans FreeCAD : TechDraw lit ces fichiers depuis le dossier de l'atelier.

Usage : ``python tools/generer_gabarits.py [dossier_de_sortie]``
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from freecad.menuiserie.core.drawing import (  # noqa: E402
    PAGE_FORMATS,
    Orientation,
    template_file_name,
    template_svg,
)

TEMPLATES_DIR = ROOT / "freecad" / "menuiserie" / "resources" / "templates"


def main(argv: list[str]) -> int:
    folder = Path(argv[1]) if len(argv) > 1 else TEMPLATES_DIR
    folder.mkdir(parents=True, exist_ok=True)
    for fmt in PAGE_FORMATS:
        for orientation in Orientation:
            path = folder / template_file_name(fmt, orientation)
            path.write_text(template_svg(fmt, orientation), encoding="utf-8", newline="\n")
            print(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
