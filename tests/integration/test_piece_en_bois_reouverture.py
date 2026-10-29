# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce en bois : réouverture, document sans l'atelier, fichiers altérés (B9, B11, ADR 0003).

Le document est enregistré puis rouvert : dans le même interpréteur (migration, version plus
récente, texte hostile, source supprimée, forme importée à plusieurs solides) et dans un
interpréteur où l'atelier n'est pas importable (la forme enregistrée s'affiche, la source reste
éditable).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.integration.test_assemblages_compatibilite import FREECAD_LIB, run_python
from tests.integration.test_piece_en_bois import (
    TOLERANCE,
    box,
    dimensions,
    imported,
    leg,
    part_of,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")
shaped_part = pytest.importorskip("freecad.menuiserie.features.shaped_part")

Reopen = Callable[[Any], Any]
HOSTILE = "\n‮" + "x" * 40
VERSION = shaped_part.ShapedPart.VERSION

# Interpréteur sans l'atelier : ouvre le document, modifie le dessin de la source et recalcule.
EDIT_WITHOUT_WORKBENCH = """
import importlib.util, json, sys
import FreeCAD, Part, PartDesign, Sketcher
found = importlib.util.find_spec("freecad.menuiserie") is not None
doc = FreeCAD.openDocument(sys.argv[1])
part, body, pad = (doc.getObject(name) for name in sys.argv[2:5])
before = [part.Shape.Volume, body.Shape.Volume]
pad.Length = pad.Length.Value * 2
doc.recompute()
result = {
    "workbench": found,
    "valid": part.Shape.isValid(),
    "before": before,
    "after": [part.Shape.Volume, body.Shape.Volume],
}
print("RESULTAT " + json.dumps(result))
"""


def assert_safe(warning: str) -> None:
    """Une seule ligne, sans caractère bidi ni texte démesuré."""
    assert warning.endswith("\n")
    assert warning.count("\n") == 1
    assert "‮" not in warning
    assert len(warning) < 400


# --- B9 : document ouvert sans l'atelier ---------------------------------------------------


def test_document_ouvert_sans_l_atelier(document: Any, tmp_path: Path) -> None:
    body = leg(document)
    part = part_of(body)
    document.recompute()
    pad = body.Group[1]
    path = tmp_path / "sans_atelier.FCStd"
    document.saveAs(str(path))
    script = tmp_path / "editer.py"
    script.write_text(EDIT_WITHOUT_WORKBENCH, encoding="utf-8")
    arguments = [str(script), str(path), part.Name, body.Name, pad.Name]
    output = run_python(arguments, tmp_path, [FREECAD_LIB])
    [line] = [text for text in output.splitlines() if text.startswith("RESULTAT ")]
    result: dict[str, Any] = json.loads(line.removeprefix("RESULTAT "))
    assert result["workbench"] is False
    assert result["valid"]
    assert result["before"][0] == pytest.approx(part.Shape.Volume)
    # La source reste éditable : le corps suit son dessin. La pièce, sans atelier, garde la forme
    # enregistrée (rien ne la recalcule).
    assert result["after"][1] == pytest.approx(2 * result["before"][1], rel=TOLERANCE)
    assert result["after"][0] == pytest.approx(result["before"][0])


# --- B9 : réouverture dans l'atelier -------------------------------------------------------


def test_reouverture_sans_modification(document: Any, rouvrir: Reopen) -> None:
    body = leg(document)
    part = part_of(body)
    part.Mark = "P1"
    document.recompute()
    name, expected, volume = part.Name, dimensions(part), part.Shape.Volume
    reopened = rouvrir(document)
    restored = reopened.getObject(name)
    assert restored.Shape.Volume == pytest.approx(volume)
    assert reopened.recompute() == 0
    assert [obj.Name for obj in reopened.Objects if "Touched" in obj.State] == []
    assert dimensions(restored) == pytest.approx(expected, abs=TOLERANCE)
    assert restored.Label == "P1"


def test_migration_d_un_ancien_fichier(document: Any, rouvrir: Reopen) -> None:
    part = part_of(leg(document))
    document.recompute()
    grain, expected = part.PreferredGrainDirection, dimensions(part)
    for name in ("Version", "ThicknessAllowance", "PreferredGrainDirection"):
        part.removeProperty(name)
    name = part.Name
    restored = rouvrir(document).getObject(name)
    assert restored.Version == VERSION
    assert restored.ThicknessAllowance.Value == 0
    assert restored.PreferredGrainDirection == grain
    assert restored.getEditorMode("Version") == ["Hidden"]
    assert restored.getGroupOfProperty("ThicknessAllowance") == "Débit"
    restored.Document.recompute()
    assert "Invalid" not in restored.State
    assert dimensions(restored) == pytest.approx(expected, abs=TOLERANCE)
    assert "Output" in restored.getPropertyStatus("Length")


@pytest.mark.parametrize("version", [VERSION + 1, 2**31 - 1])
def test_version_plus_recente_signalee(
    document: Any, rouvrir: Reopen, vue_rapport: Any, version: int
) -> None:
    part = part_of(leg(document))
    document.recompute()
    part.Version = version
    name, expected = part.Name, dimensions(part)
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert restored.Version == version
    warnings = [text for text in vue_rapport.de_niveau("Warning") if "plus récente" in text]
    assert len(warnings) == 1
    assert f"modèle {version}, {VERSION} au plus" in warnings[0]
    assert "ReadOnly" in restored.getEditorMode("Material")
    restored.Document.recompute()
    assert "Invalid" not in restored.State
    assert dimensions(restored) == pytest.approx(expected, abs=TOLERANCE)


def test_version_d_un_type_inattendu_traitee_comme_0(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    part = part_of(leg(document))
    document.recompute()
    part.removeProperty("Version")
    part.addProperty("App::PropertyString", "Version")
    part.Version = "abc" + HOSTILE
    name = part.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    assert restored.getTypeIdOfProperty("Version") == "App::PropertyInteger"
    assert restored.Version == VERSION
    warnings = [text for text in vue_rapport.de_niveau("Warning") if "illisible" in text]
    assert len(warnings) == 1
    assert_safe(warnings[0])


def test_textes_hostiles_cites_tronques_et_echappes(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    part = part_of(leg(document))
    document.recompute()
    part.MaterialId = "inconnu" + HOSTILE + "y" * 2_000_000
    name = part.Name
    vue_rapport.messages.clear()
    restored = rouvrir(document).getObject(name)
    warnings = vue_rapport.de_niveau("Warning")
    assert warnings
    for warning in warnings:
        assert_safe(warning)
    assert any("« inconnu\\n\\u202exxx" in warning for warning in warnings)
    restored.Document.recompute()
    assert "Invalid" not in restored.State


def test_reouverture_avec_la_source_supprimee(document: Any, rouvrir: Reopen) -> None:
    source = box(document, (45.0, 95.0, 720.0))
    part = part_of(source)
    document.recompute()
    name, volume = part.Name, part.Shape.Volume
    document.removeObject(source.Name)
    document.recompute()
    restored_document = rouvrir(document)
    restored = restored_document.getObject(name)
    assert restored.Shape.Volume == pytest.approx(volume)  # la forme enregistrée est là
    restored.touch()
    restored_document.recompute()  # aucune exception Python
    assert "Invalid" in restored.State
    assert "sans forme" in restored.getStatusString()


# --- B11 : formes importées à plusieurs solides ----------------------------------------------


def test_pieces_d_une_forme_importee_apres_reouverture(document: Any, rouvrir: Reopen) -> None:
    first, second = Part.makeBox(100, 50, 20), Part.makeBox(200, 40, 20)
    second.translate(App.Vector(300, 0, 0))
    source = imported(document, first, second)
    parts = api.make_shaped_parts(source)
    document.recompute()
    names = [part.Name for part in parts]
    expected = [dimensions(part) for part in parts]
    signatures = [part.SolidSignature for part in parts]
    reopened = rouvrir(document)
    assert reopened.recompute() == 0
    restored = [reopened.getObject(name) for name in names]
    assert [part.SolidIndex for part in restored] == [0, 1]
    assert [part.SolidSignature for part in restored] == signatures
    for part, size in zip(restored, expected, strict=True):
        assert "Invalid" not in part.State
        assert dimensions(part) == pytest.approx(size, abs=TOLERANCE)
