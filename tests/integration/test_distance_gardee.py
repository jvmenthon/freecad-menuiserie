# SPDX-License-Identifier: LGPL-2.1-or-later
"""Distance gardée dans un ensemble (DI-c, critères F3 et F5 à F7, B6, ADR 0022).

Bureau de référence : la Distance relie le bas de la joue gauche (z = 0) au bas du voile
(z = 320), l'axe Z de l'ensemble.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.elements_choisis import element_name
from tests.integration.bureau import Bureau, build_desk
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_assemblages_compatibilite import FREECAD_LIB, run_python

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
distance_module = pytest.importorskip("freecad.menuiserie.features.distance")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
geometry = pytest.importorskip("freecad.menuiserie.core.geometry")

BAS_JOUE = (11, 280, 0)
BAS_VOILE = (600, 450, 320)


def keep(bureau: Bureau, value: float = 320, *, keep_it: bool = True, container: Any = None) -> Any:
    """Distance gardée entre le bas de la joue gauche et le bas du voile (le voile bouge) ;
    ``container`` : Std Part qui contient le bureau (chemin de sélection de l'interface)."""

    def pick(mark: str, near: tuple[float, float, float]) -> Any:
        part = bureau.parts[mark]
        name = element_name(part, "Face", near)
        if container is None:
            return api.PickedElement(part, name)
        return api.PickedElement(container, f"{part.Name}.{name}")

    api.set_distance(pick("JG", BAS_JOUE), pick("V", BAS_VOILE), value, keep=keep_it)
    found = [o for o in bureau.doc.Objects if distance_module.is_distance(o)]
    return found[0] if found else None


def distances(doc: Any) -> list[Any]:
    return [o for o in doc.Objects if distance_module.is_distance(o)]


def v_z(bureau: Bureau) -> tuple[float, float]:
    return bureau.bounds("V")[2]


# --- F5 : l'objet ---------------------------------------------------------------------------


def test_objet_distance(bureau: Bureau) -> None:
    dist = keep(bureau)
    assert dist.TypeId == "App::FeaturePython"
    assert dist.Proxy.TYPE == "Menuiserie::Distance"
    assert dist.Version == 1
    assert "Shape" not in dist.PropertiesList
    assert (dist.PieceA, dist.PieceB) == (bureau.parts["JG"], bureau.parts["V"])
    assert (dist.Axis, dist.SideA, dist.SideB) == ("Z", "Start", "Start")
    assert dist.Value.Value == pytest.approx(320)
    assert dist.Label == "Distance : Joue gauche \N{EN DASH} Voile"
    assert dist.getEditorMode("PieceA") == ["ReadOnly"]
    assert dist.getEditorMode("Axis") == ["ReadOnly"]
    assert dist.getEditorMode("SideA") == ["Hidden"]
    assert dist.getTypeIdOfProperty("Value") == "App::PropertyLength"
    assert dist.Proxy.dumps() is None
    assert stale_or_invalid(bureau.doc) == []


def test_placee_dans_le_groupe_de_l_ensemble(document: Any) -> None:
    part = document.addObject("App::Part", "Meuble")
    bureau = build_desk(document, part)
    dist = keep(bureau)
    assert dist.getParentGeoFeatureGroup() == part
    assert bureau.furniture.getParentGeoFeatureGroup() == part


def test_a_cote_de_l_ensemble_sans_groupe(bureau: Bureau) -> None:
    dist = keep(bureau)
    assert dist.getParentGeoFeatureGroup() is None


def test_pas_de_distance_sans_la_case(bureau: Bureau) -> None:
    assert keep(bureau, 300, keep_it=False) is None
    assert v_z(bureau) == (300, 700)


# --- F3 : le bureau de référence ------------------------------------------------------------


def test_expressions_et_valeurs(bureau: Bureau) -> None:
    dist = keep(bureau)
    assert dist.Name == "Distance"
    expressions = bureau.expressions("V")
    assert expressions["Width"] == "<<Bureau>>.Height - WoodPart.Thickness - Distance.Value"
    assert expressions["Placement.Base.z"] == "<<Bureau>>.Origin.z + Distance.Value"
    assert bureau.expressions("JG") == {
        "Length": "<<Bureau>>.Height - WoodPart.Thickness",
        "Width": "<<Bureau>>.Depth - 40 mm",
        "Placement.Base.x": "<<Bureau>>.Origin.x + Thickness",
    }
    assert v_z(bureau) == (320, 720)


def test_hauteur_epaisseur_et_valeur(bureau: Bureau) -> None:
    dist = keep(bureau)
    bureau.furniture.Height = 800
    bureau.doc.recompute()
    assert v_z(bureau) == (320, 770)  # le haut du voile suit le plateau, 320 mm conservés
    bureau.parts["P"].Thickness = 25
    bureau.doc.recompute()
    assert v_z(bureau) == (320, 775)
    dist.Value = 300  # sans aucun code de l'atelier
    bureau.doc.recompute()
    assert v_z(bureau) == (300, 775)
    assert stale_or_invalid(bureau.doc) == []


def test_valeur_liee_a_une_expression(bureau: Bureau) -> None:
    dist = keep(bureau)
    dist.setExpression("Value", "200 mm + 80 mm")
    bureau.doc.recompute()
    assert v_z(bureau) == (280, 720)


# --- F6 : suppression liée ------------------------------------------------------------------


def test_supprimer_la_distance_relie_l_ensemble(bureau: Bureau) -> None:
    dist = keep(bureau)
    bureau.doc.removeObject(dist.Name)
    bureau.doc.recompute()
    assert distances(bureau.doc) == []
    assert v_z(bureau) == (320, 720)  # la pièce ne bouge pas
    assert bureau.expressions("V")["Width"].endswith("- 320 mm")
    assert "Placement.Base.z" not in bureau.expressions("V")
    bureau.furniture.Height = 800
    bureau.doc.recompute()
    assert v_z(bureau) == (320, 770)
    assert stale_or_invalid(bureau.doc) == []


def test_supprimer_une_piece_supprime_la_distance(document: Any) -> None:
    bureau = build_desk(document, joined=False)  # sans tourillons : rien d'autre ne casse
    keep(bureau)
    bureau.doc.removeObject(bureau.parts["V"].Name)
    bureau.doc.recompute()
    assert distances(bureau.doc) == []
    assert bureau.expressions("JG")["Length"] == "<<Bureau>>.Height - WoodPart.Thickness"
    assert stale_or_invalid(bureau.doc) == []


def test_supprimer_la_piece_a_supprime_la_distance(document: Any) -> None:
    bureau = build_desk(document, joined=False)
    keep(bureau)
    bureau.doc.removeObject(bureau.parts["JG"].Name)
    bureau.doc.recompute()
    assert distances(bureau.doc) == []
    assert stale_or_invalid(bureau.doc) == []


def test_retirer_une_piece_de_l_ensemble(bureau: Bureau) -> None:
    keep(bureau)
    api.remove_from_furniture([bureau.shown("V")])
    bureau.doc.recompute()
    assert distances(bureau.doc) == []
    assert stale_or_invalid(bureau.doc) == []


def test_supprimer_l_ensemble(bureau: Bureau) -> None:
    keep(bureau)
    bureau.doc.removeObject(bureau.furniture.Name)
    bureau.doc.recompute()
    assert distances(bureau.doc) == []
    assert bureau.expressions("V") == {}
    assert v_z(bureau) == (320, 720)


def test_annuler_la_suppression(bureau: Bureau) -> None:
    bureau.doc.UndoMode = 1
    name = keep(bureau).Name
    bureau.doc.openTransaction("Supprimer")
    bureau.doc.removeObject(bureau.parts["V"].Name)
    bureau.doc.commitTransaction()
    bureau.doc.undo()
    bureau.doc.recompute()
    assert [o.Name for o in distances(bureau.doc)] == [name]
    assert bureau.expressions("V")["Width"].endswith("Distance.Value")
    assert stale_or_invalid(bureau.doc) == []


# --- F7 : copie, réouverture, document sans l'atelier ------------------------------------------


def test_copie_suit_les_pieces_copiees(document: Any) -> None:
    part = document.addObject("App::Part", "Meuble")
    bureau = build_desk(document, part)
    keep(bureau)
    count = len(document.Objects)
    [copy] = document.copyObject([part], True)  # comme « Dupliquer la sélection »
    document.recompute()
    created = document.Objects[count:]
    [new] = [o for o in created if distance_module.is_distance(o)]
    copied = {o.Name for o in created}
    assert new.PieceA.Name in copied and new.PieceB.Name in copied
    assert new.PieceA != bureau.parts["JG"]
    assert new.getParentGeoFeatureGroup() == copy
    [furniture] = [o for o in created if o.Name.startswith("Furniture")]
    furniture.Height = 800
    document.recompute()
    assert bureau.bounds("V")[2] == (320, 720)  # l'original ne bouge pas
    assert new.PieceB.Shape.BoundBox.ZMax == pytest.approx(770)
    assert api.rebind_furniture(furniture) == ()  # la liaison de la copie n'est pas « utilisateur »
    assert stale_or_invalid(document) == []


def test_reouverture(bureau: Bureau, rouvrir: Any) -> None:
    keep(bureau)
    name = distances(bureau.doc)[0].Name
    voile = bureau.parts["V"].Name
    doc = rouvrir(bureau.doc)
    dist = doc.getObject(name)
    assert distance_module.is_distance(dist)
    assert dist.PieceA.Label == "Joue gauche" and dist.Version == 1
    assert dist.getEnumerationsOfProperty("Axis") == ["X", "Y", "Z"]
    dist.Value = 300
    doc.recompute()
    assert doc.getObject(voile).Shape.BoundBox.ZMin == pytest.approx(300)
    assert stale_or_invalid(doc) == []


SANS_ATELIER = """
import importlib.util, json, sys
import FreeCAD
found = importlib.util.find_spec("freecad.menuiserie") is not None
doc = FreeCAD.openDocument(sys.argv[1])
distance = doc.getObject("Distance")
voile = doc.getObject(sys.argv[2])
before = voile.Placement.Base.z
distance.Value = 300
doc.recompute()
z, width = voile.Placement.Base.z, voile.Width.Value
print("RESULTAT " + json.dumps([found, distance.Proxy is None, before, z, width]))
"""


def test_document_rouvert_sans_l_atelier(bureau: Bureau, tmp_path: Path) -> None:
    """Distance inerte (proxy introuvable) : changer sa valeur déplace quand même le voile,
    par les expressions natives."""
    keep(bureau)
    path = tmp_path / "bureau.FCStd"
    bureau.doc.saveAs(str(path))
    script = tmp_path / "ouvrir.py"
    script.write_text(SANS_ATELIER, encoding="utf-8")
    output = run_python([str(script), str(path), bureau.parts["V"].Name], tmp_path, [FREECAD_LIB])
    [line] = [line for line in output.splitlines() if line.startswith("RESULTAT ")]
    found, inert, before, low, width = json.loads(line.removeprefix("RESULTAT "))
    assert (found, inert) == (False, True)
    assert (round(before, 3), round(low, 3), round(width, 3)) == (320, 300, 420)


# --- B6 : le glissement met la valeur à jour ----------------------------------------------------


def test_echap_retablit_la_valeur(bureau: Bureau) -> None:
    dist = keep(bureau)
    voile = bureau.parts["V"]
    memento = drag.begin_drag(voile)
    dist.Value = 999
    drag.restore(memento)
    assert dist.Value.Value == pytest.approx(320)


def test_rangee_bloquee_par_la_distance(bureau: Bureau) -> None:
    api.set_member_options(bureau.parts["V"], locked=True)
    with pytest.raises(ValueError, match="garder la distance"):
        keep(bureau)
    assert distances(bureau.doc) == []
    assert v_z(bureau) == (320, 720)


def test_distance_non_gardable_hors_ensemble(document: Any) -> None:
    a = api.make_wood_part(400, 100, 20, "chene", doc=document)
    b = api.make_wood_part(400, 100, 20, "chene", doc=document)
    b.Placement = App.Placement(App.Vector(0, 0, 200), App.Rotation())
    document.recompute()
    face_a = api.PickedElement(a, element_name(a, "Face", (200, 50, 20)))
    face_b = api.PickedElement(b, element_name(b, "Face", (200, 50, 200)))
    with pytest.raises(ValueError, match="même ensemble"):
        api.set_distance(face_a, face_b, 100, keep=True)
    assert b.Placement.Base.z == 200  # rien n'a bougé


def test_garde_dans_un_std_part_tourne(document: Any) -> None:
    """Les éléments sont lus en coordonnées globales : le Std Part tourné et déplacé, la
    Distance est la même et les liaisons suivent."""
    part = document.addObject("App::Part", "Meuble")
    part.Placement = App.Placement(App.Vector(150, -80, 25), App.Rotation(App.Vector(0, 0, 1), 30))
    bureau = build_desk(document, part)
    dist = keep(bureau, container=part)
    assert (dist.Axis, dist.SideA, dist.SideB) == ("Z", "Start", "Start")
    bureau.furniture.Height = 800
    document.recompute()
    assert v_z(bureau) == (320, 770)


def test_rangee_bloquee_puis_ne_plus_garder(bureau: Bureau) -> None:
    """La Distance compte comme une pièce verrouillée : cote refusée, puis « Ne plus garder et
    appliquer » (la Distance fait partie des pièces proposées)."""
    keep(bureau)
    api.set_member_options(bureau.parts["V"], locked=True)
    with pytest.raises(api.LockedPiecesError) as error:
        api.resize_furniture(bureau.furniture, height=800)
    pieces = list(error.value.members)
    assert [p.Name for p in pieces] == ["WoodPart003", "Distance"]
    assert "Distance : Joue gauche" in str(error.value)
    assert bureau.furniture.Height.Value == 750  # rien n'a été écrit
    api.unlock_and_resize(bureau.furniture, pieces, height=800)
    assert distances(bureau.doc) == []
    assert bureau.furniture.Height.Value == 800
    assert bureau.parts["V"].Locked is False
    assert stale_or_invalid(bureau.doc) == []


def test_ne_plus_garder_seul(bureau: Bureau) -> None:
    keep(bureau)
    api.set_member_options(bureau.parts["V"], locked=True)
    with pytest.raises(api.LockedPiecesError) as error:
        api.resize_furniture(bureau.furniture, height=800)
    only = [p for p in error.value.members if distance_module.is_distance(p)]
    api.unlock_and_resize(bureau.furniture, only, height=800)  # le voile reste verrouillé
    assert bureau.parts["V"].Locked is True
    assert distances(bureau.doc) == []
    assert v_z(bureau) == (370, 770)  # voile verrouillé : il monte avec le plateau (#86)
