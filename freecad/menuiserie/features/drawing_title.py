# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cartouche d'une page de plan de l'atelier (issue #153, ADR 0053, lot P-b).

Les cases du gabarit TechDraw (``EditableTexts``) reçoivent l'ouvrage, le matériau, l'échelle, la
date et l'auteur ; le client et le numéro de devis sont facultatifs. Le titre, le client et le
numéro de devis saisis sont gardés sur la page (propriétés masquées) pour être réécrits quand le
plan est refait.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Final

from freecad.menuiserie.core.drawing import (
    TitleFields,
    clean_field,
    fit_to_cell,
    placeholder_keys,
    scale_text,
    title_block_texts,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features import drawing_settings
from freecad.menuiserie.features.drawing_scope import (
    LinkWalk,
    children_of,
    link_target,
    workshop_inside,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_container import is_std_part
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.machined_part import blank_of, is_machined_part
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = ["STORED", "fill_title_block"]

# Saisies du cartouche gardées sur la page, pour les retrouver quand le plan est refait.
STORED: Final = {
    "title": "MenuiserieDrawingTitle",
    "client": "MenuiserieDrawingClient",
    "quote": "MenuiserieDrawingQuote",
}
MAX_MATERIALS: Final = 3  # au-delà, le cartouche écrit « divers »

_VARIOUS: Final = QT_TRANSLATE_NOOP("Menuiserie", "divers")
_KIND: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan de l'ouvrage")


def _materials(objects: Sequence[DocumentObject], seen: set[str], walk: LinkWalk) -> set[str]:
    """Matériaux des pièces de bois de ``objects`` : membres des ensembles, brute d'une pièce
    usinée, pièces d'un Std Part ou d'une copie par lien compris."""
    found: set[str] = set()
    for obj in objects:
        if obj.Name in seen:
            continue
        seen.add(obj.Name)
        target = link_target(obj)
        if target is not None or is_std_part(obj):  # copie par lien, Std Part d'un meuble
            found |= _materials(workshop_inside(target or obj, walk), seen, walk)
        elif is_furniture(obj):
            found |= _materials(children_of(obj, walk), seen, walk)
        elif is_machined_part(obj):
            found |= _materials([blank_of(obj)], seen, walk)
        elif is_timber(obj):
            found.add(clean_field(str(getattr(obj, "Material", ""))))
    return found - {""}


def _material_text(objects: Sequence[DocumentObject]) -> str:
    names = sorted(_materials(objects, set(), LinkWalk()))
    return ", ".join(names) if len(names) <= MAX_MATERIALS else translated(_VARIOUS)


def _default_title(doc: Document, objects: Sequence[DocumentObject]) -> str:
    """Nom de l'ouvrage : le libellé de l'objet dessiné s'il est seul, sinon celui du document."""
    return str(objects[0].Label if len(objects) == 1 else doc.Label)


def _stored(page: DocumentObject, key: str, given: str | None, default: str = "") -> str:
    """Saisie ``key`` du cartouche : ``given`` si elle est fournie, sinon celle de la page, sinon
    ``default`` ; la valeur fournie est enregistrée sur la page."""
    name = STORED[key]
    if given is not None:  # une saisie vidée rend la valeur par défaut
        setattr(page, name, clean_field(given))
        return str(getattr(page, name)) or clean_field(default)
    return str(getattr(page, name, "")) or clean_field(default)


def fill_title_block(
    page: DocumentObject,
    objects: Sequence[DocumentObject],
    inputs: Mapping[str, str | None],
    scale: float,
    kind: str | None = None,
) -> None:
    """Écrit le cartouche du gabarit de ``page`` (``inputs`` : saisies ``title``, ``client`` et
    ``quote``, ``None`` pour garder celle de la page ; ``kind`` : genre du document, déjà traduit,
    « Plan de l'ouvrage » par défaut) ; les cases que l'atelier ne connaît pas (et
    celles que le menuisier a remplies lui-même dans ces cases-là) ne sont pas touchées."""
    doc = page.Document
    values = TitleFields(
        title=_stored(page, "title", inputs.get("title"), _default_title(doc, objects)),
        material=_material_text(objects),
        kind=kind if kind is not None else translated(_KIND),
        scale=scale_text(scale),
        date=date.today().isoformat(),
        author=drawing_settings.default_author(str(getattr(doc, "CreatedBy", ""))),
        client=_stored(page, "client", inputs.get("client")),
        quote=_stored(page, "quote", inputs.get("quote")),
    )
    template = page.Template
    texts = dict(getattr(template, "EditableTexts", None) or {})
    if texts:
        written = {
            key: fit_to_cell(key, text) for key, text in title_block_texts(texts, values).items()
        }
        texts.update({key: "" for key in placeholder_keys(texts, written)})
        texts.update(written)
        template.EditableTexts = texts
