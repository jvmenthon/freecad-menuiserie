# SPDX-License-Identifier: LGPL-2.1-or-later
"""Repère et encombrement d'une forme dessinée avec Sketcher / PartDesign (PD-a, ADR 0020).

Ce module est une façade : il ré-exporte l'API publique des sous-modules. ``features/`` extrait
un :class:`ShapeSample` de la forme, demande le repère (:func:`principal_axes`, :func:`ordered`,
:func:`turned_axes`), les cotes d'encombrement et le coin minimal (:func:`measure_points`), et
l'empreinte de regroupement (:class:`ShapeSignature`) et celle d'un solide importé
(:func:`encode_fingerprint`, :func:`fingerprint_matches`). Au-delà des plafonds de taille
(:data:`MAX_FACES`, :data:`MAX_EDGES`, :data:`MAX_POINTS`), ``ShapeSample.exceeds_limits`` est
vrai et :func:`principal_axes` renvoie les axes de la source : l'appelant avertit. Aucun import de
FreeCAD ni de Qt.
"""

from __future__ import annotations

from freecad.menuiserie.core.shaped._axes import (
    Axes,
    Bounds,
    measure_points,
    ordered,
    principal_axes,
    turned_axes,
)
from freecad.menuiserie.core.shaped._fingerprint import encode_fingerprint, fingerprint_matches
from freecad.menuiserie.core.shaped._material_check import (
    MISSING_MATERIAL_THRESHOLD,
    missing_material_ratio,
    missing_material_warning_due,
)
from freecad.menuiserie.core.shaped._sample import (
    MAX_COORDINATE_MM,
    MAX_EDGES,
    MAX_FACES,
    MAX_POINTS,
    ShapeSample,
)
from freecad.menuiserie.core.shaped._signature import ShapeSignature

__all__ = [
    "MAX_COORDINATE_MM",
    "MAX_EDGES",
    "MAX_FACES",
    "MAX_POINTS",
    "MISSING_MATERIAL_THRESHOLD",
    "Axes",
    "Bounds",
    "ShapeSample",
    "ShapeSignature",
    "encode_fingerprint",
    "fingerprint_matches",
    "measure_points",
    "missing_material_ratio",
    "missing_material_warning_due",
    "ordered",
    "principal_axes",
    "turned_axes",
]
