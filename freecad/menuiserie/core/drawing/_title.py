# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cartouche du plan : quelles cases d'un gabarit TechDraw reçoivent quelles valeurs.

Un gabarit SVG de TechDraw nomme ses cases modifiables (``drawing_title``, ``scale``…) ; les noms
varient d'un gabarit à l'autre. Chaque champ de l'atelier vise donc une liste de noms connus, du
plus précis au plus général ; une case inconnue n'est jamais touchée.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from typing import Final

__all__ = [
    "MAX_FIELD_LENGTH",
    "TitleFields",
    "clean_field",
    "placeholder_keys",
    "title_block_texts",
]

MAX_FIELD_LENGTH: Final = 120
SEPARATOR: Final = "-"  # entre un champ et celui qu'il suit faute de case à lui
_CONTROL: Final = re.compile("[\x00-\x1f\x7f\u2028\u2029\u202a-\u202e\u2066-\u2069]")
# Noms de cases (en minuscules) par champ, dans l'ordre de préférence.
_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "title": ("drawing_title", "title", "document_title", "drawing_name", "titel", "benennung"),
    "material": ("part_material", "material", "werkstoff"),
    "scale": ("scale", "drawing_scale", "fc-sc", "fc-scale", "massstab", "maßstab"),
    "date": ("date", "fc-date", "date_of_issue", "issue_date", "creation_date", "datum"),
    "author": ("author_name", "author", "creator", "designed_by_name", "drawn_by", "ersteller"),
    "kind": ("document_type", "dokumentenart", "drawing_type"),
    "client": (
        "client",
        "customer",
        "kunde",
        "auftraggeber",
        "owner",
        "owner_1",
        "supplementary_title",
        "subtitle",
        "drawing_subtitle",
        "untertitel",
    ),
    "quote": (
        "quote",
        "drawing_number",
        "document_number",
        "identification_number",
        "part_number",
        "sachnummer",
        "zeichnungsnummer",
    ),
}


@dataclass(frozen=True)
class TitleFields:
    """Valeurs du cartouche. ``kind`` est le genre du document (« Plan de l'ouvrage »).
    ``client`` et ``quote`` (numéro de devis) sont facultatifs : vides, leurs cases sont vidées
    aussi."""

    title: str = ""
    material: str = ""
    kind: str = ""
    scale: str = ""
    date: str = ""
    author: str = ""
    client: str = ""
    quote: str = ""


def clean_field(text: str) -> str:
    """Texte d'une case : sur une ligne, sans caractère de contrôle ni de sens d'écriture, espaces
    de bord retirés, au plus ``MAX_FIELD_LENGTH`` caractères."""
    return " ".join(_CONTROL.sub(" ", text).split())[:MAX_FIELD_LENGTH]


def title_block_texts(keys: Iterable[str], values: TitleFields) -> dict[str, str]:
    """Cases à écrire (nom exact du gabarit → texte) pour ``values``, parmi les cases ``keys`` du
    gabarit. Chaque champ remplit la première de ses cases connues que le gabarit possède et
    qu'un champ précédent n'a pas prise ; les autres cases ne sont pas citées. Sans case pour le
    client, un client saisi est écrit après le titre (« Bureau - Mme Dupont ») ; sans case pour
    le matériau, il suit le genre du document (« Plan de l'ouvrage - Chêne »)."""
    by_lower = {key.lower(): key for key in keys}
    taken: set[str] = set()
    placed: dict[str, str] = {}  # champ → case
    texts: dict[str, str] = {}
    for field in fields(values):
        key = next(
            (name for name in _ALIASES[field.name] if name in by_lower and name not in taken),
            None,
        )
        if key is not None:
            taken.add(key)
            placed[field.name] = by_lower[key]
            texts[by_lower[key]] = clean_field(getattr(values, field.name))
    # Gabarit sans case pour le client ou le matériau : ils suivent le titre ou le genre.
    _append(texts, placed, "client", "title", values.client)
    _append(texts, placed, "material", "kind", values.material)
    return texts


def _append(
    texts: dict[str, str], placed: dict[str, str], field: str, host: str, value: str
) -> None:
    text = clean_field(value)
    if text and field not in placed and host in placed:
        key = placed[host]
        texts[key] = clean_field(f"{texts[key]} {SEPARATOR} {text}")


def placeholder_keys(texts: Mapping[str, str], written: Iterable[str]) -> list[str]:
    """Cases de ``texts`` (case → texte actuel du gabarit) que l'atelier n'écrit pas et dont le
    texte est encore l'exemple du gabarit (le nom de la case, « Genehmiger » pour
    ``Genehmiger``) : elles sont vidées pour ne pas s'imprimer telles quelles."""
    skipped = set(written)
    return [
        key
        for key, text in texts.items()
        if key not in skipped and text.strip() and text.strip().casefold() == key.casefold()
    ]
