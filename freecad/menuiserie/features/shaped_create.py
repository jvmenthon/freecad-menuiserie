# SPDX-License-Identifier: LGPL-2.1-or-later
"""Création d'une pièce en bois et changement de son repère (ADR 0020, B1, B4, B6, B11).

:func:`create_shaped_part` et :func:`create_shaped_parts` lisent la source (refus traduits, avant
toute création), calculent une fois le repère de chaque solide (:mod:`.shaped_frame`), puis créent
les pièces dans le conteneur de la source, au ``Placement`` qui les met exactement à la place de la
source. La source n'est jamais modifiée ; elle est masquée à la fin, une fois liée (l'annulation la
réaffiche). Aucun ViewProvider ni transaction ni recalcul ici : voir :mod:`freecad.menuiserie.api`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.shaped import Axes
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated, translated_errors
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.part_names import label_of_mark
from freecad.menuiserie.features.shaped_frame import (
    LocalForm,
    automatic_axes,
    axes_placement,
    local_form,
    placement_axes,
)
from freecad.menuiserie.features.shaped_part import (
    OBJECT_NAME,
    ShapedPart,
    is_profile,
    source_solid,
)
from freecad.menuiserie.features.shaped_part_schema import (
    DEFAULT_PROFILE_THICKNESS,
    apply_editor_modes,
)
from freecad.menuiserie.features.shaped_sources import (
    SourceReading,
    container_of,
    picked_solid,
    read_source,
    signature_text,
)
from freecad.menuiserie.features.wood_material import shows_grain

__all__ = [
    "DEFAULT_PROFILE_THICKNESS",
    "converted_part_of",
    "create_shaped_part",
    "create_shaped_parts",
    "reframe",
    "reset_axes",
]

_ALREADY_CONVERTED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » est déjà la forme d'une pièce en bois (« {part} »)."
)
_TOO_DETAILED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » : forme trop détaillée pour chercher son repère automatiquement ; les axes de "
    "la source sont gardés.",
)


@dataclass(frozen=True)
class _Plan:
    """Ce qu'il faut savoir d'un solide avant de créer sa pièce : forme locale, repère, rang."""

    form: LocalForm
    axes: Axes
    limited: bool
    index: int
    signature: str


def converted_part_of(obj: DocumentObject) -> DocumentObject | None:
    """Pièce en bois qui enveloppe déjà ``obj`` (``Source`` = ``obj``), ``None`` sinon."""
    for other in obj.InList:
        if type(getattr(other, "Proxy", None)) is ShapedPart and other.Source == obj:
            return other
    return None


def _checked_reading(source: DocumentObject, thickness: float) -> SourceReading:
    """Lecture de ``source`` (:func:`.shaped_sources.read_source`), puis refus (``ValueError``
    traduite) si elle est déjà convertie."""
    reading = read_source(source, thickness)
    part = converted_part_of(reading.source)
    if part is not None:
        params = {"label": quoted_value(reading.source.Label), "part": quoted_value(part.Label)}
        raise ValueError(translated(_ALREADY_CONVERTED, params))
    return reading


def _plans(reading: SourceReading) -> list[_Plan]:
    """Un plan par solide de ``reading`` : repère automatique, forme locale et cotes validées
    (``ValueError`` traduite si une cote sort des bornes). Un solide seul n'a pas de rang."""
    indexed = len(reading.solids) > 1
    plans = []
    for index, solid in enumerate(reading.solids):
        axes, limited = automatic_axes(solid)
        form = local_form(solid, axes)
        with translated_errors():
            Dimensions(*form.extents)
        signature = signature_text(solid) if indexed else ""
        plans.append(_Plan(form, axes, limited, index if indexed else -1, signature))
    return plans


def create_shaped_parts(
    source: DocumentObject,
    *,
    material_id: str | None = None,
    mark: str = "",
    profile_thickness: float = DEFAULT_PROFILE_THICKNESS,
) -> list[DocumentObject]:
    """Crée une pièce en bois par solide de ``source`` (plusieurs seulement pour une forme
    importée, B11), sans ViewProvider ni transaction ni recalcul.

    ``material_id`` vaut par défaut le matériau par défaut de la bibliothèque ; ``mark`` est le
    repère de chaque pièce ; ``profile_thickness`` (mm) n'est lue que pour une esquisse. Refus
    traduits (``TypeError``, ``ValueError``) et ``UnknownMaterialError`` avant toute création."""
    library = get_library()
    material = library.default_material() if material_id is None else library.get(material_id)
    reading = _checked_reading(source, profile_thickness)
    plans = _plans(reading)
    parts = [_build(reading, material, plan, mark, profile_thickness) for plan in plans]
    reading.source.Visibility = False  # seule modification de la source, après la liaison (B1)
    return parts


def create_shaped_part(
    source: DocumentObject,
    *,
    material_id: str | None = None,
    mark: str = "",
    profile_thickness: float = DEFAULT_PROFILE_THICKNESS,
) -> DocumentObject:
    """Crée la pièce en bois de ``source``, qui ne doit avoir qu'un solide (sinon ``ValueError``
    traduite : voir :func:`create_shaped_parts`). Mêmes arguments et refus."""
    reading = read_source(source, profile_thickness)
    picked_solid(reading, -1, "")  # refus s'il y a plusieurs solides
    [part] = create_shaped_parts(
        source, material_id=material_id, mark=mark, profile_thickness=profile_thickness
    )
    return part


def _build(
    reading: SourceReading, material: Material, plan: _Plan, mark: str, thickness: float
) -> DocumentObject:
    """Pièce en bois d'un solide : dans le conteneur de la source, liée à elle, au repère et au
    ``Placement`` du plan, matériau et repère de menuiserie posés."""
    source = reading.source
    doc: Document = source.Document
    obj = doc.addObject("Part::FeaturePython", OBJECT_NAME)
    container = container_of(source)
    if container is not None:
        container.addObject(obj)
    proxy = ShapedPart(obj)
    proxy.select_material(obj, material)
    obj.Source = source
    obj.SourceAxes = axes_placement(plan.axes)
    obj.SolidIndex = plan.index
    obj.SolidSignature = plan.signature
    if reading.profile:
        obj.ProfileThickness = thickness
    for name, value in zip(("Length", "Width", "Thickness"), plan.form.extents, strict=True):
        setattr(obj, name, value)
    obj.Placement = _placement_of(obj, source, plan.form.frame)
    with proxy.synchronizing():  # le libellé est celui du repère (J6b), posé une seule fois
        obj.Mark = mark
        obj.Label = label_of_mark(obj, mark)
    apply_editor_modes(obj, show_grain=shows_grain(obj, proxy.library()), profile=is_profile(obj))
    if plan.limited:
        report_warning(translated(_TOO_DETAILED, {"label": quoted_value(source.Label)}))
    return obj


def _placement_of(obj: DocumentObject, source: DocumentObject, frame: Any) -> Any:
    """``Placement`` de ``obj`` (dans son conteneur) qui met le repère de la pièce à la place du
    repère ``frame`` de la source : ``conteneur⁻¹ · source · frame``."""
    group = obj.getParentGeoFeatureGroup()
    container = group.getGlobalPlacement() if group is not None else App.Placement()
    return container.inverse().multiply(source.getGlobalPlacement()).multiply(frame)


def reframe(part: DocumentObject, axes: Axes, raw: Any | None = None) -> None:
    """Change le repère de la pièce en bois ``part`` pour ``axes`` (dans le repère de la source)
    sans que la pièce bouge : son ``Placement`` est corrigé (`P' = P · F⁻¹ · F'`). Sert aux
    quarts de tour du repère et au repère automatique. ``raw`` : solide de la source, relu sinon.
    Aucun recalcul ici."""
    solid = source_solid(part) if raw is None else raw
    old = local_form(solid, placement_axes(part.SourceAxes))
    new = local_form(solid, axes)
    part.SourceAxes = axes_placement(axes)
    part.Placement = part.Placement.multiply(old.frame.inverse()).multiply(new.frame)


def reset_axes(part: DocumentObject) -> bool:
    """Repère automatique (:func:`.shaped_frame.automatic_axes`) de la forme actuelle de la pièce
    en bois ``part``, sans que la pièce bouge. Rend vrai si la forme dépasse les plafonds de
    taille : les axes de la source sont gardés, avec un avertissement traduit."""
    raw = source_solid(part)
    axes, limited = automatic_axes(raw)
    if limited:
        report_warning(translated(_TOO_DETAILED, {"label": quoted_value(part.Source.Label)}))
    reframe(part, axes, raw)
    return limited
