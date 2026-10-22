# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export HTML autonome de la liste de débit (J2e, critère P1).

Module privé : la façade ``core.cutlist`` ré-exporte l'API publique. Le document n'a ni script ni
ressource externe ; tout texte passe par ``html.escape``. Il sert de source à l'export PDF (J2g).
"""

from __future__ import annotations

from collections.abc import Iterable
from html import escape
from typing import Final

from freecad.menuiserie.core.cutlist._build import CutList
from freecad.menuiserie.core.cutlist._csv import (
    INTERNATIONAL_CSV,
    TableSection,
    Translate,
    table_sections,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

DATE_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Date")
SCOPE_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Portée")
WARNINGS_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Avertissements")

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
ul { margin: 0; padding-left: 16pt; }
"""


def _tag(name: str, content: str, attributes: str = "") -> str:
    return f"<{name}{attributes}>{content}</{name}>"


def _row(cells: Iterable[str], text_columns: frozenset[int], *, header: bool) -> str:
    rendered = []
    for index, cell in enumerate(cells):
        if header:
            rendered.append(_tag("th", escape(cell)))
        else:
            numeric = index not in text_columns
            rendered.append(_tag("td", escape(cell), ' class="num"' if numeric else ""))
    return _tag("tr", "".join(rendered))


def _section(section: TableSection) -> str:
    title = _tag("h2", escape(section.title)) if section.title else ""
    head = _tag("thead", _row(section.header, section.text_columns, header=True))
    body = "".join(_row(row, section.text_columns, header=False) for row in section.rows)
    return title + _tag("table", head + _tag("tbody", body))


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
) -> str:
    """Document HTML autonome de la liste de débit : titre, date, portée, tableau (mêmes colonnes
    que la feuille, nombres au format international), totaux, fournitures et avertissements.
    ``translate`` traduit les libellés ; ``title``, ``scope`` et ``date`` sont déjà prêts à
    l'affichage. Tout texte est échappé ; ni script ni ressource externe."""
    meta = " &nbsp;|&nbsp; ".join(
        f"{escape(translate(label))} : {escape(value)}"
        for label, value in ((DATE_LABEL, date), (SCOPE_LABEL, scope))
        if value
    )
    sections = table_sections(cut_list, translate, INTERNATIONAL_CSV)
    body = (
        _tag("h1", escape(title))
        + (_tag("p", meta, ' class="meta"') if meta else "")
        + "".join(_section(section) for section in sections)
        + _warnings(cut_list, translate)
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="fr"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title><style>\n{_STYLE}</style></head>\n"
        f"<body>{body}</body></html>\n"
    )
