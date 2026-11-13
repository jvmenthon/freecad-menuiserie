# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarits de page de l'atelier : feuille ISO 216 avec cadre et cartouche en français.

Les fichiers SVG livrés dans ``resources/templates`` sont produits par ``tools/generer_gabarits.py``
à partir de :func:`template_svg` ; un test vérifie qu'ils n'ont pas dérivé. Le cartouche occupe le
coin bas droit, dans la place réservée par la mise en page (``TITLE_BLOCK_MM``). Ses cases
modifiables portent les noms que le remplissage du cartouche vise en premier.
"""

from __future__ import annotations

from typing import Final
from xml.sax.saxutils import escape, quoteattr

from freecad.menuiserie.core.drawing._layout import PAGE_FORMATS, Orientation, page_size

__all__ = ["TEMPLATE_FILES", "template_file_name", "template_svg"]

FRAME_MM: Final = 10.0  # du bord de la feuille au cadre
BLOCK_WIDTH_MM: Final = 180.0
BLOCK_ROWS_MM: Final = (18.0, 12.0, 12.0, 13.0)  # hauteurs des rangées, de haut en bas
_FONT: Final = "osifont, DejaVu Sans, sans-serif"
_LABEL_MM: Final = 2.5
_VALUE_MM: Final = 3.5
_TITLE_MM: Final = 6.0
# Cases de chaque rangée : (largeur, libellé, nom de case modifiable ou texte fixe).
_ROWS: Final = (
    ((180.0, "Ouvrage", "drawing_title"),),
    ((90.0, "Client", "client"), (90.0, "N° de devis", "quote")),
    ((90.0, "Matériau", "material"), (90.0, "Document", "document_type")),
    (
        (35.0, "Échelle", "scale"),
        (40.0, "Date", "date"),
        (65.0, "Auteur", "author"),
        (40.0, "Format", ""),
    ),
)


def template_file_name(fmt: str, orientation: Orientation) -> str:
    """Nom du fichier de gabarit : « Menuiserie_A3_Landscape.svg »."""
    return f"Menuiserie_{fmt.strip().upper()}_{orientation.value}.svg"


TEMPLATE_FILES: Final = tuple(
    template_file_name(fmt, orientation) for fmt in PAGE_FORMATS for orientation in Orientation
)


def _text(x: float, y: float, size: float, content: str, editable: str = "") -> str:
    attribute = f" freecad:editable={quoteattr(editable)}" if editable else ""
    return (
        f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" font-family={quoteattr(_FONT)}'
        ' fill="#000000" stroke="none"'
        f'{attribute}><tspan x="{x:g}" y="{y:g}">{escape(content)}</tspan></text>'
    )


def _block(right: float, bottom: float, fmt: str) -> list[str]:
    """Cartouche dont le coin bas droit est en (``right``, ``bottom``), coordonnées SVG (y vers
    le bas)."""
    left = right - BLOCK_WIDTH_MM
    top = bottom - sum(BLOCK_ROWS_MM)
    parts = [
        f'<rect x="{left:g}" y="{top:g}" width="{BLOCK_WIDTH_MM:g}" '
        f'height="{sum(BLOCK_ROWS_MM):g}" stroke-width="0.5" />'
    ]
    row_top = top
    for row, height in zip(_ROWS, BLOCK_ROWS_MM, strict=True):
        if row_top > top:
            parts.append(f'<path d="M {left:g},{row_top:g} H {right:g}" stroke-width="0.35" />')
        cell_left = left
        for width, label, name in row:
            if cell_left > left:
                parts.append(
                    f'<path d="M {cell_left:g},{row_top:g} V {row_top + height:g}" '
                    'stroke-width="0.35" />'
                )
            parts.append(_text(cell_left + 1.5, row_top + 3.5, _LABEL_MM, label))
            size = _TITLE_MM if name == "drawing_title" else _VALUE_MM
            value_y = row_top + height - 2.5
            if name:
                parts.append(_text(cell_left + 3.0, value_y, size, name, name))
            else:
                parts.append(_text(cell_left + 3.0, value_y, size, fmt))
            cell_left += width
        row_top += height
    return parts


def template_svg(fmt: str, orientation: Orientation) -> str:
    """Gabarit SVG pour TechDraw de la feuille ``fmt`` (« A3 »…) dans le sens ``orientation`` :
    cadre à 10 mm du bord et cartouche français au coin bas droit. ``TemplatedError`` pour un
    format inconnu."""
    page = page_size(fmt, orientation)
    name = fmt.strip().upper()
    width, height = page.width, page.height
    right, bottom = width - FRAME_MM, height - FRAME_MM
    body = [
        f'<rect x="{FRAME_MM:g}" y="{FRAME_MM:g}" width="{right - FRAME_MM:g}" '
        f'height="{bottom - FRAME_MM:g}" stroke-width="0.7" />',
        *_block(right, bottom, name),
    ]
    lines = "\n    ".join(body)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        "<!-- Gabarit de l'atelier Menuiserie, produit par tools/generer_gabarits.py -->\n"
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1"\n'
        '  xmlns:freecad="http://www.freecad.org/wiki/index.php?title=Svg_Namespace"\n'
        f'  width="{width:g}mm" height="{height:g}mm" viewBox="0 0 {width:g} {height:g}">\n'
        f"  <title>Menuiserie {name} {orientation.value}</title>\n"
        '  <g fill="none" stroke="#000000" stroke-linecap="square">\n'
        f"    {lines}\n"
        "  </g>\n"
        "</svg>\n"
    )
