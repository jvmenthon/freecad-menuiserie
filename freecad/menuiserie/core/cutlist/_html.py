# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export HTML autonome de la liste de débit (J2e, critère P1).

Module privé : la façade ``core.cutlist`` ré-exporte l'API publique. Le document n'a ni script ni
ressource externe ; tout texte passe par ``html.escape``. Il sert de source à l'export PDF (J2g).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from html import escape
from typing import Final

from freecad.menuiserie.core.cutlist._build import CutList
from freecad.menuiserie.core.cutlist._csv import (
    INTERNATIONAL_CSV,
    TableSection,
    Translate,
    table_sections,
)
from freecad.menuiserie.core.cutlist._thumbnail import (
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    svg_data_uri,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

DATE_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Date")
SCOPE_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Portée")
WARNINGS_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Avertissements")
THUMBNAIL_HEADER: Final = QT_TRANSLATE_NOOP("Menuiserie", "Miniature")

# A4 paysage ; aucune ressource externe (police du système, ni @import ni url()).
_STYLE: Final = """\
@page { size: A4 landscape; margin: 10mm; }
body { font-family: sans-serif; font-size: 9pt; color: #000; background: #fff; }
h1 { font-size: 16pt; margin: 0 0 4pt 0; }
h2 { font-size: 11pt; margin: 14pt 0 4pt 0; }
p.meta { margin: 0 0 8pt 0; }
table { border-collapse: collapse; width: 100%; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #666; padding: 2pt 4pt; }
th { background: #e8e8e8; text-align: left; }
td.num { text-align: right; }
td.thumb { text-align: center; vertical-align: middle; }
ul { margin: 0; padding-left: 16pt; }
"""
# Avec la colonne de miniatures, le tableau compte 120 px de plus : texte un peu plus petit.
_THUMBNAIL_STYLE: Final = "th, td { font-size: 7.5pt; padding: 2pt 3pt; }\n"


def _tag(name: str, content: str, attributes: str = "") -> str:
    return f"<{name}{attributes}>{content}</{name}>"


def _row(
    cells: Iterable[str], text_columns: frozenset[int], *, header: bool, leading: str = ""
) -> str:
    """Ligne de tableau ; ``leading`` : cellule déjà rendue placée avant les autres."""
    rendered = [leading]
    for index, cell in enumerate(cells):
        if header:
            rendered.append(_tag("th", escape(cell)))
        else:
            numeric = index not in text_columns
            rendered.append(_tag("td", escape(cell), ' class="num"' if numeric else ""))
    return _tag("tr", "".join(rendered))


def _thumbnail_cell(svg: str | None) -> str:
    """Cellule de miniature : image ``data:`` de la taille affichée, ou cellule vide."""
    if svg is None:
        return _tag("td", "", ' class="thumb"')
    image = f'<img src="{svg_data_uri(svg)}" width="{THUMBNAIL_WIDTH}" height="{THUMBNAIL_HEIGHT}">'
    return _tag("td", image, ' class="thumb"')


def _section(
    section: TableSection, thumbnails: Sequence[str | None] | None = None, header: str = ""
) -> str:
    """Tableau d'un bloc. ``thumbnails`` (un SVG ou ``None`` par ligne) ajoute une colonne de tête
    intitulée ``header`` ; il ne concerne que le bloc des lignes de la liste."""
    title = _tag("h2", escape(section.title)) if section.title else ""
    columns = section.text_columns
    if thumbnails is None:
        head = _row(section.header, columns, header=True)
        rows = [_row(row, columns, header=False) for row in section.rows]
    else:
        head = _row(section.header, columns, header=True, leading=_tag("th", escape(header)))
        rows = [
            _row(row, columns, header=False, leading=_thumbnail_cell(svg))
            for svg, row in zip(thumbnails, section.rows, strict=True)
        ]
    return title + _tag("table", _tag("thead", head) + _tag("tbody", "".join(rows)))


def _warnings(cut_list: CutList, translate: Translate) -> str:
    messages = dict.fromkeys(
        translate(notice.template).format_map(notice.params) for notice in cut_list.warnings
    )
    if not messages:
        return ""
    items = "".join(_tag("li", escape(message)) for message in messages)
    return _tag("h2", escape(translate(WARNINGS_TITLE))) + _tag("ul", items)


def to_html(
    cut_list: CutList,
    translate: Translate = str,
    title: str = "",
    scope: str = "",
    date: str = "",
    thumbnails: Mapping[str, str] | None = None,
) -> str:
    """Document HTML autonome de la liste de débit : titre, date, portée, tableau (mêmes colonnes
    que la feuille, nombres au format international), totaux, fournitures et avertissements.
    ``translate`` traduit les libellés ; ``title``, ``scope`` et ``date`` sont déjà prêts à
    l'affichage. Tout texte est échappé ; ni script ni ressource externe.

    ``thumbnails`` (clé de la ligne, ``CutLine.source`` → SVG de ``thumbnail_svg``) ajoute en tête
    de chaque ligne une colonne « Miniature » ; l'image est incluse en ``data:`` (le document
    reste autonome), une ligne sans miniature a une cellule vide. Vide ou absent : le document
    sans cette colonne. ``ValueError`` si une miniature n'est pas un SVG."""
    meta = " &nbsp;|&nbsp; ".join(
        f"{escape(translate(label))} : {escape(value)}"
        for label, value in ((DATE_LABEL, date), (SCOPE_LABEL, scope))
        if value
    )
    sections = table_sections(cut_list, translate, INTERNATIONAL_CSV)
    images = [thumbnails.get(line.source) for line in cut_list.lines] if thumbnails else None
    heading = translate(THUMBNAIL_HEADER)
    tables = [
        _section(section, images if index == 0 else None, heading)
        for index, section in enumerate(sections)
    ]
    style = _STYLE + (_THUMBNAIL_STYLE if images is not None else "")
    body = (
        _tag("h1", escape(title))
        + (_tag("p", meta, ' class="meta"') if meta else "")
        + "".join(tables)
        + _warnings(cut_list, translate)
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="fr"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title><style>\n{style}</style></head>\n"
        f"<body>{body}</body></html>\n"
    )
