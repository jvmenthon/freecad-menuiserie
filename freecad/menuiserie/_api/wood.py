# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces de bois de la façade publique : pièce paramétrique (J1) et pièce dessinée (PD-b).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

from collections.abc import Sequence

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.shaped_create import (
    create_shaped_part,
    create_shaped_parts,
    reset_axes,
)
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.shaped_part_schema import DEFAULT_PROFILE_THICKNESS
from freecad.menuiserie.features.wood_part import create_wood_part, validated_arguments

# --- Pièce de bois (J1) -------------------------------------------------------------------


def make_wood_part(
    length: float = 800.0,
    width: float = 200.0,
    thickness: float = 22.0,
    material_id: str | None = None,
    *,
    mark: str = "",
    doc: Document | None = None,
) -> DocumentObject:
    """Crée une pièce de bois (cotes finies en mm), l'affiche si l'interface est chargée et
    recalcule le document.

    ``doc`` vaut par défaut le document actif, ou un nouveau document s'il n'y en a pas : les
    cotes et le matériau sont validés avant, si bien qu'une erreur ne crée aucun document. Aucune
    transaction n'est ouverte : c'est à l'appelant de le faire pour pouvoir annuler.
    """
    validated_arguments(length, width, thickness, material_id)
    document = doc if doc is not None else App.ActiveDocument or App.newDocument()
    obj = create_wood_part(
        document,
        length=length,
        width=width,
        thickness=thickness,
        material_id=material_id,
        mark=mark,
    )
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.wood_part import (
            ViewProviderWoodPart,
        )

        ViewProviderWoodPart(obj.ViewObject)
    document.recompute()
    return obj


# --- Pièce en bois (PD-b) -----------------------------------------------------------------

_NOT_A_SHAPED_PART = QT_TRANSLATE_NOOP("Menuiserie", "« {label} » n'est pas une pièce en bois.")


def make_shaped_part(
    source: DocumentObject,
    material: str | None = None,
    mark: str = "",
    *,
    profile_thickness: float = DEFAULT_PROFILE_THICKNESS,
) -> DocumentObject:
    """Crée la pièce en bois de ``source`` (ADR 0020) et recalcule le document.

    ``source`` : corps ``PartDesign::Body`` (forme de son ``Tip``), fonction PartDesign (ramenée à
    son corps), forme ``Part::Feature`` à un seul solide valide, ou esquisse plane et fermée
    (extrudée de ``profile_thickness`` mm le long de sa normale). ``material`` : identifiant du
    matériau (défaut : celui de la bibliothèque) ; ``mark`` : repère de la pièce.

    La pièce est rangée dans le conteneur de la source (``App::Part``, groupe), exactement à sa
    place ; la source n'est jamais modifiée, seulement masquée une fois liée. Une forme importée à
    plusieurs solides se convertit avec :func:`make_shaped_parts` (une pièce par solide). Refus
    traduits avant toute création : ``TypeError`` (objet de l'atelier, type non pris en charge),
    ``ValueError`` (forme vide ou invalide, plusieurs solides, esquisse ouverte, cote hors bornes,
    source déjà convertie), ``KeyError`` (matériau inconnu). Aucune transaction n'est ouverte :
    c'est à l'appelant de le faire pour pouvoir annuler.
    """
    part = create_shaped_part(
        source, material_id=material, mark=mark, profile_thickness=profile_thickness
    )
    _show_shaped([part])
    part.Document.recompute()
    return part


def make_shaped_parts(
    source: DocumentObject,
    material: str | None = None,
    mark: str = "",
    *,
    profile_thickness: float = DEFAULT_PROFILE_THICKNESS,
) -> list[DocumentObject]:
    """Crée une pièce en bois par solide de ``source`` et recalcule le document (B11).

    Pour une forme importée (type exactement ``Part::Feature``, sans dépendance : STEP, IGES,
    copie simple) à plusieurs solides : une pièce par solide, liée à la même source avec son rang
    (``SolidIndex``) et son empreinte (``SolidSignature``), dans la transaction de l'appelant.
    Pour toute autre source, une liste d'une pièce, comme :func:`make_shaped_part` (mêmes
    arguments, mêmes refus)."""
    parts = create_shaped_parts(
        source, material_id=material, mark=mark, profile_thickness=profile_thickness
    )
    _show_shaped(parts)
    source.Document.recompute()
    return parts


def reset_shaped_axes(part: DocumentObject) -> None:
    """Repère automatique de la pièce en bois ``part`` : recalcule ses axes d'après la forme
    actuelle de sa source (``SourceAxes``) sans que la pièce bouge, puis recalcule le document.

    C'est, avec les quarts de tour du repère, le seul moyen de changer ``SourceAxes`` : un
    recalcul ordinaire le garde. ``TypeError`` traduite si ``part`` n'est pas une pièce en bois.
    """
    if not is_shaped_part(part):
        raise TypeError(translated(_NOT_A_SHAPED_PART, {"label": quoted_value(part.Label)}))
    reset_axes(part)
    part.Document.recompute()


def _show_shaped(parts: Sequence[DocumentObject]) -> None:
    """Pose le ViewProvider des pièces en bois si l'interface est chargée (texture et couleur du
    matériau, source rangée sous la pièce dans l'arbre)."""
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.shaped_part import (
            ViewProviderShapedPart,
        )

        for part in parts:
            ViewProviderShapedPart(part.ViewObject)
