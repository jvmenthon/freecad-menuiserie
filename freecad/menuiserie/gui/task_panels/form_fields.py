# SPDX-License-Identifier: LGPL-2.1-or-later
"""Champs de formulaire communs aux panneaux des gabarits (caisson, fermer le caisson) : cote en
mm, liste déroulante, liste des matériaux de la bibliothèque."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.features.freecad_types import Document
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.gui.task_panels.base import Widget, connect, length_spinbox

__all__ = [
    "build_preview",
    "clear_selection_later",
    "combo",
    "length_field",
    "material_box",
]


def length_field(
    layout: Widget, name: str, label: str, value: float, slot: Callable[..., None]
) -> Widget:
    """Champ de cote en mm (``Gui::QuantitySpinBox``) ajouté au formulaire."""
    field = length_spinbox(name, value)
    connect(field, "valueChanged(double)", slot)
    layout.addRow(translated(label), field)
    return field


def combo(layout: Widget, name: str, label: str, items: dict[str, str]) -> Widget:
    """Liste déroulante (identifiant → texte affiché) ajoutée au formulaire."""
    box = QtGui.QComboBox()
    box.setObjectName(name)
    # Largeur minimale indépendante du plus long texte : le volet des tâches est étroit.
    box.setSizeAdjustPolicy(QtGui.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(8)
    for key, text in items.items():
        box.addItem(text, key)
    layout.addRow(translated(label), box)
    return box


def material_box(
    layout: Widget, name: str, label: str, wanted: str, slot: Callable[..., None]
) -> Widget:
    """Matériaux de la bibliothèque ; ``wanted`` choisi s'il existe, sinon le matériau par
    défaut."""
    library = get_library()
    names = {material.id: material.name(display_language()) for material in library}
    box = combo(layout, name, label, names)
    chosen = wanted if wanted in names else library.default_material().id
    box.setCurrentIndex(box.findData(chosen))
    connect(box, "currentIndexChanged(int)", slot)
    return box


def build_preview(
    doc: Document,
    build: Callable[[], tuple[Any, Sequence[str]]],
    restart: Callable[[], None],
    unexpected: str,
) -> tuple[Any, str]:
    """Aperçu construit par ``build`` (qui renvoie l'ensemble et ses avis) : ``(ensemble,
    message)``. Un refus (``TypeError``, ``ValueError``) devient le message ; une erreur
    inattendue (noyau géométrique) ou un objet créé en erreur abandonne l'aperçu par ``restart``
    et dit pourquoi avec le gabarit ``unexpected`` (champ ``{reason}``)."""
    before = {obj.Name for obj in doc.Objects}
    try:
        with translated_errors():
            furniture, notices = build()
        failed = [
            str(obj.Label) for obj in doc.Objects if obj.Name not in before and not obj.isValid()
        ]
        if failed:
            raise RuntimeError(", ".join(failed))
        return furniture, "\n".join(notices)
    except (TypeError, ValueError) as error:
        return None, str(error)
    except Exception as error:  # OCC, objet en erreur : aperçu abandonné
        restart()
        return None, translated(unexpected, {"reason": str(error) or type(error).__name__})


def clear_selection_later(document: str) -> None:
    """Sélection du document vidée une fois le panneau refermé par FreeCAD : ni flèches ni
    poignées dans la vue 3D (ADR 0038 ; le panneau en fermant les retire de même)."""
    QtCore.QTimer.singleShot(0, partial(_clear_selection, document))


def _clear_selection(document: str) -> None:
    """Sélection du document vidée, s'il existe encore (fermé entre-temps : rien à faire)."""
    if document in App.listDocuments():
        Gui.Selection.clearSelection(document)
