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

# A4 paysage ; aucune ressource externe (police du système, ni @import ni url()). Sous-ensemble
# CSS compris par ``QTextDocument`` (aperçu et PDF) : sélecteurs simples, ni ombre ni arrondi.
# Teintes de bois : brun foncé (en-têtes), brun doré (titres), crème (une ligne sur deux).
_STYLE: Final = """\
@page { size: A4 landscape; margin: 10mm; }
body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 9pt;
  color: #2b2622; background: #ffffff; }
h1 { font-size: 18pt; font-weight: 600; color: #3d2b1f; margin: 0 0 2pt 0; }
h2 { font-size: 11pt; font-weight: 600; color: #8a5a2b; margin: 16pt 0 5pt 0; }
p.meta { color: #7a6f66; margin: 0 0 12pt 0; }
table { border-collapse: collapse; width: 100%; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background-color: #3d2b1f; color: #ffffff; font-weight: 600; text-align: left;
  vertical-align: middle; }
td { vertical-align: middle; border-bottom: 1px solid #e6ddd3; }
tr.alt { background-color: #f8f4ef; }
tr.total { background-color: #efe5d8; font-weight: 600; }
th.num, td.num { text-align: right; }
td.thumb { text-align: center; vertical-align: middle; }
ul { margin: 0; padding-left: 14pt; color: #8a4b0f; }
li { margin: 0 0 2pt 0; }
"""
# Avec la colonne de miniatures, le tableau compte 120 px de plus : texte un peu plus petit.
_THUMBNAIL_STYLE: Final = "th, td { font-size: 7.5pt; }\n"


def _tag(name: str, content: str, attributes: str = "") -> str:
    return f"<{name}{attributes}>{content}</{name}>"


def _row(
    cells: Iterable[str],
    text_columns: frozenset[int],
    *,
    header: bool,
    leading: str = "",
    css_class: str = "",
) -> str:
    """Ligne de tableau ; ``leading`` : cellule déjà rendue placée avant les autres ;
    ``css_class`` : classe de la ligne (``alt`` une ligne sur deux, ``total``)."""
    rendered = [leading]
    for index, cell in enumerate(cells):
        attributes = "" if index in text_columns else ' class="num"'
        rendered.append(_tag("th" if header else "td", escape(cell), attributes))
    return _tag("tr", "".join(rendered), f' class="{css_class}"' if css_class else "")


def _thumbnail_cell(svg: str | None) -> str:
    """Cellule de miniature : image ``data:`` de la taille affichée, ou cellule vide."""
    if svg is None:
        return _tag("td", "", ' class="thumb"')
    image = f'<img src="{svg_data_uri(svg)}" width="{THUMBNAIL_WIDTH}" height="{THUMBNAIL_HEIGHT}">'
    return _tag("td", image, ' class="thumb"')


def _row_class(index: int, count: int, *, total_last: bool) -> str:
    if total_last and index == count - 1:
        return "total"
    return "alt" if index % 2 else ""


def _section(
    section: TableSection,
    thumbnails: Sequence[str | None] | None = None,
    header: str = "",
    *,
    total_last: bool = False,
) -> str:
    """Tableau d'un bloc, une ligne sur deux teintée. ``thumbnails`` (un SVG ou ``None`` par
    ligne) ajoute une colonne de tête intitulée ``header`` ; il ne concerne que le bloc des lignes
    de la liste. ``total_last`` : la dernière ligne est le total général (mise en avant)."""
    title = _tag("h2", escape(section.title)) if section.title else ""
    columns = section.text_columns
    count = len(section.rows)
    leading = (None,) * count if thumbnails is None else thumbnails
    head = _row(
        section.header,
        columns,
        header=True,
        leading="" if thumbnails is None else _tag("th", escape(header)),
    )
    rows = [
        _row(
            row,
            columns,
            header=False,
            leading="" if thumbnails is None else _thumbnail_cell(svg),
            css_class=_row_class(index, count, total_last=total_last),
        )
        for index, (svg, row) in enumerate(zip(leading, section.rows, strict=True))
    ]
    # Attributs plutôt que CSS : QTextDocument ignore ``border-spacing`` et le ``padding`` des
    # cellules d'un tableau à ``cellpadding``. Seul le tableau des lignes prend toute la largeur.
    width = ' width="100%"' if not section.title else ""
    attributes = f'{width} cellspacing="0" cellpadding="5"'
    return title + _tag("table", _tag("thead", head) + _tag("tbody", "".join(rows)), attributes)


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
        _section(
            section,
            images if index == 0 else None,
            heading,
            total_last=index == 1 and bool(cut_list.lines),
        )
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
