# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export CSV de la liste de débit : dialectes, nombres affichés, neutralisation (J2b, C7 et C8).

Module privé : la façade ``core.cutlist`` ré-exporte l'API publique. ``core/`` ne traduit pas :
les libellés sont des gabarits marqués pour ``lupdate`` que ``features/`` traduit en passant sa
fonction ``translate`` ; l'écriture du fichier (``dialect.encoding``) est aussi à ``features/``.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core.cutlist._build import CutList
from freecad.menuiserie.core.cutlist._model import CutLine, Hardware, HardwareKind, MaterialTotal
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions, GrainDirection

Translate = Callable[[str], str]

DIMENSION_DECIMALS: Final = 1
VOLUME_DECIMALS: Final = 4
AREA_DECIMALS: Final = 3
MASS_DECIMALS: Final = 2
# Un tableur interprète une cellule qui commence par l'un de ces caractères comme une formule.
_FORMULA_STARTS: Final = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class CsvDialect:
    """Convention d'un fichier CSV : séparateur, séparateur décimal, encodage, fin de ligne."""

    delimiter: str
    decimal_separator: str
    encoding: str
    line_terminator: str


# Excel et LibreOffice en français : « ; », virgule décimale, UTF-8 avec BOM, CRLF (★ Q4).
FRENCH_CSV: Final = CsvDialect(";", ",", "utf-8-sig", "\r\n")
INTERNATIONAL_CSV: Final = CsvDialect(",", ".", "utf-8-sig", "\r\n")


LINE_HEADERS: Final = (
    QT_TRANSLATE_NOOP("Menuiserie", "Repère"),
    QT_TRANSLATE_NOOP("Menuiserie", "Qté"),
    QT_TRANSLATE_NOOP("Menuiserie", "Longueur finie (mm)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Largeur finie (mm)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur finie (mm)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Longueur de débit (mm)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Largeur de débit (mm)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur de débit (mm)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Matériau"),
    QT_TRANSLATE_NOOP("Menuiserie", "Fil"),
    QT_TRANSLATE_NOOP("Menuiserie", "Ensemble"),
    QT_TRANSLATE_NOOP("Menuiserie", "Volume de débit (m³)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Masse (kg)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Surface (m²)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Remarque"),
)
TOTALS_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Totaux par matériau")
TOTALS_HEADERS: Final = (
    QT_TRANSLATE_NOOP("Menuiserie", "Matériau"),
    QT_TRANSLATE_NOOP("Menuiserie", "Qté"),
    QT_TRANSLATE_NOOP("Menuiserie", "Volume de débit (m³)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Masse (kg)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Surface (m²)"),
)
GRAND_TOTAL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Total général")
HARDWARE_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Fournitures")
HARDWARE_HEADERS: Final = (
    QT_TRANSLATE_NOOP("Menuiserie", "Fourniture"),
    QT_TRANSLATE_NOOP("Menuiserie", "Diamètre (mm)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Longueur (mm)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Qté"),
)
GRAIN_LABELS: Final[Mapping[GrainDirection, str]] = MappingProxyType(
    {
        GrainDirection.LENGTH: QT_TRANSLATE_NOOP("Menuiserie", "Longueur"),
        GrainDirection.WIDTH: QT_TRANSLATE_NOOP("Menuiserie", "Largeur"),
        GrainDirection.NONE: QT_TRANSLATE_NOOP("Menuiserie", "Sans fil"),
    }
)
HARDWARE_LABELS: Final[Mapping[HardwareKind, str]] = MappingProxyType(
    {HardwareKind.DOWEL: QT_TRANSLATE_NOOP("Menuiserie", "Tourillon")}
)
ADDITIONS_REMARK: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Ajouts compris (L / l / e) : {length} / {width} / {thickness} mm"
)


def format_number(value: float, decimals: int, dialect: CsvDialect = FRENCH_CSV) -> str:
    """Cote arrondie à ``decimals`` décimales, sans zéros inutiles (« 800 », « 22,5 »)."""
    text = f"{round(value, decimals):.{decimals}f}".rstrip("0").rstrip(".")
    return (text or "0").replace(".", dialect.decimal_separator)


def _fixed(value: float, decimals: int, dialect: CsvDialect) -> str:
    return f"{value:.{decimals}f}".replace(".", dialect.decimal_separator)


def neutralize_formula(text: str) -> str:
    """Texte préfixé d'une apostrophe s'il commencerait une formule de tableur (C7)."""
    return f"'{text}" if text.startswith(_FORMULA_STARTS) else text


def additions_remark(line: CutLine, translate: Translate, dialect: CsvDialect = FRENCH_CSV) -> str:
    """Remarque d'une ligne dont le débit compte des ajouts d'assemblage, sinon texte vide."""
    additions = line.additions
    if not (additions.length or additions.width or additions.thickness):
        return ""
    params = {
        name: "+" + format_number(value, DIMENSION_DECIMALS, dialect)
        for name, value in (
            ("length", additions.length),
            ("width", additions.width),
            ("thickness", additions.thickness),
        )
    }
    return translate(ADDITIONS_REMARK).format_map(params)


def _line_row(line: CutLine, translate: Translate, dialect: CsvDialect) -> list[str]:
    sizes = (*_sizes(line.finished), *_sizes(line.rough))
    # is_panel est une propriété : la règle Semgrep la prend à tort pour une méthode.
    # nosemgrep: python.lang.maintainability.is-function-without-parentheses
    area = line.area_m2() if line.kind.is_panel else None
    return [
        line.display_mark,
        str(line.quantity),
        *(format_number(size, DIMENSION_DECIMALS, dialect) for size in sizes),
        line.material_name,
        translate(GRAIN_LABELS[line.grain]),
        ", ".join(line.furniture),
        _fixed(line.volume_m3(rough=True), VOLUME_DECIMALS, dialect),
        _fixed(line.mass_kg(rough=True), MASS_DECIMALS, dialect),
        "" if area is None else _fixed(area, AREA_DECIMALS, dialect),
        additions_remark(line, translate, dialect),
    ]


def _sizes(dimensions: Dimensions) -> tuple[float, float, float]:
    return dimensions.length, dimensions.width, dimensions.thickness


def _total_row(total: MaterialTotal, dialect: CsvDialect) -> list[str]:
    area = total.area_m2
    return [
        total.material_name,
        str(total.quantity),
        _fixed(total.volume_m3, VOLUME_DECIMALS, dialect),
        _fixed(total.mass_kg, MASS_DECIMALS, dialect),
        "" if area is None else _fixed(area, AREA_DECIMALS, dialect),
    ]


def _hardware_row(item: Hardware, translate: Translate, dialect: CsvDialect) -> list[str]:
    return [
        translate(HARDWARE_LABELS[item.kind]),
        format_number(item.diameter, DIMENSION_DECIMALS, dialect),
        format_number(item.length, DIMENSION_DECIMALS, dialect),
        str(item.quantity),
    ]


def _rows(cut_list: CutList, translate: Translate, dialect: CsvDialect) -> list[Sequence[str]]:
    rows: list[Sequence[str]] = [[translate(h) for h in LINE_HEADERS]]
    rows += [_line_row(line, translate, dialect) for line in cut_list.lines]
    if cut_list.lines:
        rows += [[], [translate(TOTALS_TITLE)], [translate(h) for h in TOTALS_HEADERS]]
        rows += [_total_row(total, dialect) for total in cut_list.totals]
        mass = _fixed(cut_list.total_mass_kg, MASS_DECIMALS, dialect)
        rows.append([translate(GRAND_TOTAL), "", "", mass, ""])
    if cut_list.hardware:
        rows += [[], [translate(HARDWARE_TITLE)], [translate(h) for h in HARDWARE_HEADERS]]
        rows += [_hardware_row(item, translate, dialect) for item in cut_list.hardware]
    return rows


def to_csv(cut_list: CutList, dialect: CsvDialect = FRENCH_CSV, translate: Translate = str) -> str:
    """Texte CSV : en-tête, une ligne par groupe, puis totaux et fournitures séparés par une
    ligne vide. Les textes qui commenceraient une formule sont neutralisés (C7). Le fichier est
    écrit par l'appelant avec ``dialect.encoding`` et sans conversion de fin de ligne."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=dialect.delimiter, lineterminator=dialect.line_terminator)
    for row in _rows(cut_list, translate, dialect):
        writer.writerow(neutralize_formula(cell) for cell in row)
    return buffer.getvalue()
