# SPDX-License-Identifier: LGPL-2.1-or-later
"""Transactions du panneau de tâche (lot J1c, critères C3, C4 et C6), côté document.

Le panneau écrit chaque modification dans l'objet, le recalcule (``obj.recompute()``), puis
valide (« OK ») ou abandonne (« Annuler ») la transaction ouverte par la commande ou par
``start_editing``. Ces tests rejouent cette suite d'appels dans ``freecadcmd`` : ce que le
panneau promet (valeurs d'origine rétablies, une seule entrée d'annulation, expression saisie
par la touche « = » retirée par « Annuler ») repose sur ce comportement du document.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

CREATE = "Créer une pièce de bois"
EDIT = "Modifier une pièce de bois"
# Propriétés que le panneau peut modifier, plus celles qui suivent le matériau.
PANEL_PROPERTIES = (
    "Length",
    "Width",
    "Thickness",
    "LengthAllowance",
    "WidthAllowance",
    "ThicknessAllowance",
    "Mark",
    "Material",
    "MaterialId",
    "Category",
    "Density",
    "GrainDirection",
)


def snapshot(obj: Any) -> dict[str, str]:
    """Valeurs des propriétés du panneau (texte : quantités comparables) et volume."""
    values = {name: str(getattr(obj, name)) for name in PANEL_PROPERTIES}
    return values | {"Volume": str(round(obj.Shape.Volume))}


def created_by_command(doc: Any) -> Any:
    """Pièce créée comme par la commande, transaction validée comme par « OK »."""
    doc.UndoMode = 1
    doc.openTransaction(CREATE)
    obj = wood_part.create_wood_part(doc)
    doc.commitTransaction()
    doc.recompute()
    return obj


def edit_like_the_panel(obj: Any) -> None:
    """Toutes les modifications du panneau, chacune suivie de l'aperçu (``obj.recompute``)."""
    obj.Document.openTransaction(EDIT)
    wood_part.set_material(obj, "hetre")
    obj.recompute()
    for name, value in (("Length", 1000), ("Width", 250), ("Thickness", 27)):
        setattr(obj, name, value)
        obj.recompute()
    obj.Mark = "M1"
    obj.GrainDirection = "Width"
    obj.LengthAllowance = 30


def test_annuler_l_edition_retablit_toutes_les_valeurs(document: Any) -> None:
    obj = created_by_command(document)
    before = snapshot(obj)
    edit_like_the_panel(obj)
    document.abortTransaction()
    document.recompute()
    assert snapshot(obj) == before
    assert document.UndoNames == [CREATE]
    assert obj.isValid()


def test_ok_une_seule_entree_annulable_et_retablissable(document: Any) -> None:
    obj = created_by_command(document)
    before = snapshot(obj)
    edit_like_the_panel(obj)
    document.commitTransaction()
    document.recompute()
    after = snapshot(obj)
    assert document.UndoNames == [EDIT, CREATE]
    document.undo()
    assert snapshot(obj) == before
    document.redo()
    assert snapshot(obj) == after


def test_annuler_la_creation_ne_laisse_rien(document: Any) -> None:
    document.UndoMode = 1
    document.openTransaction(CREATE)
    obj = wood_part.create_wood_part(document)
    obj.Length = 1000
    obj.recompute()
    document.abortTransaction()
    assert document.Objects == []
    assert document.UndoCount == 0


def test_annuler_retire_une_expression_saisie_dans_le_panneau(document: Any) -> None:
    """Touche « = » d'un champ de cote : l'expression est posée dans la transaction."""
    obj = created_by_command(document)
    document.openTransaction(EDIT)
    obj.setExpression("Length", "Width * 4")
    obj.recompute()
    assert obj.Length.Value == 800
    obj.Width = 250
    obj.recompute()
    document.abortTransaction()
    document.recompute()
    assert dict(obj.ExpressionEngine) == {}
    assert (obj.Length.Value, obj.Width.Value) == (800, 200)


def test_annuler_garde_une_expression_existante(document: Any) -> None:
    obj = created_by_command(document)
    obj.setExpression("LengthAllowance", "Length / 40")
    document.recompute()
    document.openTransaction(EDIT)
    obj.Length = 1000
    wood_part.set_material(obj, "mdf")
    obj.recompute()
    assert obj.LengthAllowance.Value == 25
    document.abortTransaction()
    document.recompute()
    assert dict(obj.ExpressionEngine) == {"LengthAllowance": "Length / 40"}
    assert (obj.LengthAllowance.Value, obj.MaterialId) == (20, "chene")
