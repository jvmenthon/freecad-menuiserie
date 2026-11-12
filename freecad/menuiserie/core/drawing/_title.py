# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cartouche du plan : quelles cases d'un gabarit TechDraw reçoivent quelles valeurs.

Un gabarit SVG de TechDraw nomme ses cases modifiables (``drawing_title``, ``scale``…) ; les noms
varient d'un gabarit à l'autre. Chaque champ de l'atelier vise donc une liste de noms connus, du
plus précis au plus général ; une case inconnue n'est jamais touchée.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, fields
from typing import Final

__all__ = ["MAX_FIELD_LENGTH", "TitleFields", "clean_field", "title_block_texts"]

MAX_FIELD_LENGTH: Final = 120
CLIENT_SEPARATOR: Final = "-"  # entre le titre et le client quand le gabarit n'a pas de case client
_CONTROL: Final = re.compile("[\x00-\x1f\x7f\u2028\u2029\u202a-\u202e\u2066-\u2069]")
# Noms de cases (en minuscules) par champ, dans l'ordre de préférence.
_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "title": ("drawing_title", "title", "document_title", "drawing_name", "titel", "benennung"),
    "material": ("part_material", "material", "werkstoff"),
    "scale": ("scale", "drawing_scale", "fc-sc", "fc-scale", "massstab", "maßstab"),
    "date": ("date", "fc-date", "date_of_issue", "issue_date", "creation_date", "datum"),
    "author": ("author_name", "author", "creator", "designed_by_name", "drawn_by", "ersteller"),
    "client": (
        "client",
        "customer",
        "kunde",
        "auftraggeber",
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
    """Valeurs du cartouche. ``client`` et ``quote`` (numéro de devis) sont facultatifs : vides,
    leurs cases sont vidées aussi."""

    title: str = ""
    material: str = ""
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
    client, un client saisi est écrit après le titre (« Bureau - Mme Dupont »)."""
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
    client = clean_field(values.client)
    if client and "client" not in placed and "title" in placed:
        # Gabarit sans case pour le client : il suit le titre de l'ouvrage.
        title_key = placed["title"]
        texts[title_key] = clean_field(f"{texts[title_key]} {CLIENT_SEPARATOR} {client}")
    return texts
