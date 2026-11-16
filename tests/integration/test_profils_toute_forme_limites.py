# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites des profils sur arêtes natives (ADR 0063, revue de test des lots P-b et P-c).

Remplacement d'arêtes déjà profilées par un autre profil natif, modification d'un profil,
recalcul après chaque propriété, annuler / rétablir, réouverture avec une arête perdue, pièce
rangée dans un Std Part, pièce en biais, arêtes courbes et faces courbes, chaîne d'arêtes
alignées, cotes et noms invalides.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import pairwise
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
pytest.importorskip("Sketcher")
edge_frames = pytest.importorskip("freecad.menuiserie.features.edge_frames")
edge_profile = pytest.importorskip("freecad.menuiserie.features.edge_profile")
api = pytest.importorskip("freecad.menuiserie.api")

Point = tuple[float, float]
Segment3 = tuple[tuple[float, float, float], tuple[float, float, float]]
EPAISSEUR = 20.0
EN_L: tuple[Point, ...] = ((0, 0), (400, 0), (400, 80), (150, 80), (150, 200), (0, 200))
ENCOCHE_GAUCHE: tuple[Point, ...] = ((0, 200), (0, 120), (30, 120), (30, 60), (0, 60), (0, 0))
AVANT: Segment3 = ((0, 0, EPAISSEUR), (400, 0, EPAISSEUR))  # 400 mm, deux bouts libres
INTERIEUR: Segment3 = ((150, 80, EPAISSEUR), (400, 80, EPAISSEUR))  # 250 mm, finit au coin rentrant
GAUCHE: Segment3 = ((0, 0, EPAISSEUR), (0, 200, EPAISSEUR))  # coupée en deux par l'encoche


def _corps(doc: Any, contour: Iterable[Any], *, refine: bool | None = None) -> tuple[Any, Any]:
    """Corps PartDesign : contour fermé de segments ``((x, y), (x, y))`` ou d'arcs ``Part``."""
    body = doc.addObject("PartDesign::Body", "Corps")
    sketch = body.newObject("Sketcher::SketchObject", "Esquisse")
    for geometry in contour:
        sketch.addGeometry(geometry, False)
    pad = body.newObject("PartDesign::Pad", "Protrusion")
    pad.Profile = sketch
    pad.Length = EPAISSEUR
    if refine is not None:
        pad.Refine = refine
    doc.recompute()
    return body, sketch


def _segments(points: tuple[Point, ...]) -> list[Any]:
    closed = (*points, points[0])
    return [
        Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0))
        for start, end in pairwise(closed)
    ]


def _piece(doc: Any, contour: Iterable[Any] | None = None, **options: Any) -> tuple[Any, Any]:
    body, sketch = _corps(doc, _segments(EN_L) if contour is None else contour, **options)
    shaped = api.make_shaped_part(body)
    doc.recompute()
    return shaped, sketch


def _nom(shape: Any, segment: Segment3) -> str:
    """Nom de l'arête de ``shape`` dont les bouts sont ceux de ``segment``."""
    wanted = sorted((App.Vector(*segment[0]), App.Vector(*segment[1])), key=tuple)
    for index, edge in enumerate(shape.Edges, start=1):
        ends = sorted((v.Point for v in edge.Vertexes), key=tuple)
        if len(ends) == 2 and all((p - q).Length < 1e-6 for p, q in zip(ends, wanted, strict=True)):
            return f"Edge{index}"
    raise AssertionError(f"arête {segment} absente")


def _encoche_a_gauche(doc: Any, sketch: Any) -> None:
    sketch.delGeometry(5)
    for start, end in pairwise(ENCOCHE_GAUCHE):
        sketch.addGeometry(Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0)), False)
    doc.recompute()


def _enleve(shaped: Any) -> float:
    machined = api.machined_part_of(shaped)
    assert machined.Shape.isValid()
    assert "Invalid" not in machined.State
    return float(shaped.Shape.Volume - machined.Shape.Volume)


def _quart_de_rond(radius: float, length: float) -> float:
    return (1 - math.pi / 4) * radius**2 * length


def _chanfrein(size: float, length: float) -> float:
    return size * size / 2 * length


# --- Remplacement d'arêtes déjà profilées (``_strip`` sur EdgeRefs) ---------------------------


def test_remplacement_par_un_autre_profil_natif(document: Any) -> None:
    shaped, _sketch = _piece(document)
    avant, interieur = _nom(shaped.Shape, AVANT), _nom(shaped.Shape, INTERIEUR)
    ancien, _ = api.add_edge_profile(shaped, [avant, interieur], "Chamfer", 2.0)
    count = len(document.Objects)
    with pytest.raises(ValueError, match="déjà"):
        api.add_edge_profile(shaped, [avant], "Round", 2.0)
    assert len(document.Objects) == count
    nouveau, _ = api.add_edge_profile(shaped, [avant], "Round", 2.0, replace=True)
    assert list(ancien.EdgeRefs[1]) == [interieur]
    assert ancien.EdgeRefs[0] == shaped
    assert list(nouveau.EdgeRefs[1]) == [avant]
    attendu = _chanfrein(2.0, 250.0) + _quart_de_rond(2.0, 400.0)
    assert _enleve(shaped) == pytest.approx(attendu, rel=1e-2)
    # toutes les arêtes de l'ancien profil reprises : il disparaît
    api.add_edge_profile(shaped, [interieur], "Cove", 2.0, replace=True)
    restants = {
        (p.Family, tuple(p.EdgeRefs[1])) for p in api.edge_profiles_of(shaped)
    }  # le nom de l'ancien profil peut être repris par le nouveau
    assert restants == {("Round", (avant,)), ("Cove", (interieur,))}


def test_remplacement_apres_une_arete_perdue(document: Any) -> None:
    """L'ancien profil garde son arête perdue (toujours signalée) et cède l'arête suivie."""
    shaped, sketch = _piece(document)
    avant, gauche = _nom(shaped.Shape, AVANT), _nom(shaped.Shape, GAUCHE)
    ancien, _ = api.add_edge_profile(shaped, [avant, gauche], "Chamfer", 2.0)
    _encoche_a_gauche(document, sketch)
    perdues = edge_profile.lost_edges(ancien)
    assert len(perdues) == 1
    avant = _nom(shaped.Shape, AVANT)
    api.add_edge_profile(shaped, [avant], "Round", 2.0, replace=True)
    assert edge_profile.lost_edges(ancien) == perdues
    assert avant not in list(ancien.EdgeRefs[1])
    assert "Invalid" not in ancien.State
    assert _enleve(shaped) == pytest.approx(_quart_de_rond(2.0, 400.0), rel=1e-2)


# --- Modification d'un profil existant ---------------------------------------------------------


def test_modifier_un_profil_natif(document: Any) -> None:
    shaped, _sketch = _piece(document)
    avant, interieur = _nom(shaped.Shape, AVANT), _nom(shaped.Shape, INTERIEUR)
    profile, _ = api.add_edge_profile(shaped, [avant], "Chamfer", 2.0)
    api.set_edge_profile(profile, [interieur], "Round", 3.0)
    assert list(profile.EdgeRefs[1]) == [interieur]
    assert list(profile.Edges) == []
    assert _enleve(shaped) == pytest.approx(_quart_de_rond(3.0, 250.0), rel=1e-2)
    # refus avant toute écriture : rien ne change
    with pytest.raises(ValueError):
        api.set_edge_profile(profile, ["Z+Y-"], "Round", 3.0)
    with pytest.raises(ValueError, match="pas les deux"):
        api.set_edge_profile(profile, [avant, "Z+Y-"], "Round", 3.0)
    with pytest.raises(ValueError, match="trop grand"):
        api.set_edge_profile(profile, [avant], "Round", 15.0)
    assert list(profile.EdgeRefs[1]) == [interieur]
    assert profile.Family == "Round"
    assert profile.SizeA.Value == pytest.approx(3.0)


def test_arete_choisie_a_nouveau_apres_perte(document: Any, vue_rapport: Any) -> None:
    shaped, sketch = _piece(document)
    profile, _ = api.add_edge_profile(shaped, [_nom(shaped.Shape, GAUCHE)], "Chamfer", 2.0)
    _encoche_a_gauche(document, sketch)
    assert edge_profile.lost_edges(profile)
    vue_rapport.messages.clear()
    api.set_edge_profile(profile, [_nom(shaped.Shape, AVANT)], "Chamfer", 2.0)
    assert edge_profile.lost_edges(profile) == []
    assert not any("perdues" in text for text in vue_rapport.de_niveau("Warning"))
    assert _enleve(shaped) == pytest.approx(_chanfrein(2.0, 400.0), rel=1e-2)


# --- Recalcul après modification de chaque propriété ------------------------------------------


def test_recalcul_apres_chaque_propriete(document: Any) -> None:
    shaped, _sketch = _piece(document)
    profile, _ = api.add_edge_profile(shaped, [_nom(shaped.Shape, AVANT)], "Round", 2.0)
    profile.SizeA = 4.0
    document.recompute()
    assert _enleve(shaped) == pytest.approx(_quart_de_rond(4.0, 400.0), rel=1e-2)
    profile.Family = "Chamfer"
    profile.SizeB = 3.0
    document.recompute()
    assert _enleve(shaped) == pytest.approx(0.5 * 4.0 * 3.0 * 400.0, rel=1e-2)
    profile.SizeA = 15.0  # plus de la moitié de l'épaisseur (20 mm)
    document.recompute()
    assert "Invalid" in profile.State
    profile.SizeA = 4.0
    document.recompute()
    assert "Invalid" not in profile.State
    assert _enleve(shaped) == pytest.approx(0.5 * 4.0 * 3.0 * 400.0, rel=1e-2)


def test_codes_et_liens_ensemble_refuses_au_recalcul(document: Any) -> None:
    """B1 : ``Edges`` et ``EdgeRefs`` exclusifs, même écrits à la main dans la console."""
    shaped, _sketch = _piece(document)
    profile, _ = api.add_edge_profile(shaped, [_nom(shaped.Shape, AVANT)], "Round", 2.0)
    profile.Edges = ["Z+Y-"]
    document.recompute()
    assert "Invalid" in profile.State
    with pytest.raises(ValueError, match="pas les deux"):
        edge_profile.edge_cuts(profile)


def test_lien_vers_une_autre_piece_refuse(document: Any) -> None:
    shaped, _sketch = _piece(document)
    autre, _ = _piece(document)
    name = _nom(shaped.Shape, AVANT)
    profile, _ = api.add_edge_profile(shaped, [name], "Round", 2.0)
    profile.EdgeRefs = (autre, [name])
    document.recompute()
    assert "Invalid" in profile.State


# --- Annuler / rétablir ------------------------------------------------------------------------


def test_annuler_retablir_creation_et_modification(document: Any) -> None:
    document.UndoMode = 1
    shaped, _sketch = _piece(document)
    avant, interieur = _nom(shaped.Shape, AVANT), _nom(shaped.Shape, INTERIEUR)
    document.openTransaction("Profil")
    profile, _ = api.add_edge_profile(shaped, [avant], "Round", 2.0)
    document.commitTransaction()
    name = profile.Name
    document.openTransaction("Modification")
    api.set_edge_profile(profile, [interieur], "Chamfer", 2.0)
    document.commitTransaction()

    document.undo()
    document.recompute()
    restored = document.getObject(name)
    assert list(restored.EdgeRefs[1]) == [avant]
    assert restored.Family == "Round"
    assert _enleve(shaped) == pytest.approx(_quart_de_rond(2.0, 400.0), rel=1e-2)

    document.undo()
    document.recompute()
    assert document.getObject(name) is None
    assert api.machined_part_of(shaped) is None

    document.redo()
    document.redo()
    document.recompute()
    redone = document.getObject(name)
    assert redone.EdgeRefs[0] == shaped
    assert list(redone.EdgeRefs[1]) == [interieur]
    assert _enleve(shaped) == pytest.approx(_chanfrein(2.0, 250.0), rel=1e-2)


def test_annuler_un_remplacement_rend_ses_aretes_a_l_ancien_profil(document: Any) -> None:
    document.UndoMode = 1
    shaped, _sketch = _piece(document)
    avant, interieur = _nom(shaped.Shape, AVANT), _nom(shaped.Shape, INTERIEUR)
    ancien, _ = api.add_edge_profile(shaped, [avant, interieur], "Chamfer", 2.0)
    document.openTransaction("Remplacement")
    api.add_edge_profile(shaped, [avant], "Round", 2.0, replace=True)
    document.commitTransaction()
    document.undo()
    document.recompute()
    assert sorted(ancien.EdgeRefs[1]) == sorted([avant, interieur])
    assert len(api.edge_profiles_of(shaped)) == 1
    assert _enleve(shaped) == pytest.approx(_chanfrein(2.0, 650.0), rel=1e-2)


# --- Réouverture -------------------------------------------------------------------------------


def test_reouverture_avec_une_arete_perdue(document: Any, rouvrir: Any) -> None:
    shaped, sketch = _piece(document)
    names = [_nom(shaped.Shape, AVANT), _nom(shaped.Shape, GAUCHE)]
    profile, _ = api.add_edge_profile(shaped, names, "Chamfer", 2.0)
    _encoche_a_gauche(document, sketch)
    perdues = edge_profile.lost_edges(profile)
    assert perdues
    profile_name, shaped_name = profile.Name, shaped.Name
    doc = rouvrir(document)
    doc.recompute()
    reopened = doc.getObject(profile_name)
    assert edge_profile.lost_edges(reopened) == perdues
    assert "Invalid" not in reopened.State
    assert _enleve(doc.getObject(shaped_name)) == pytest.approx(_chanfrein(2.0, 400.0), rel=1e-2)


def test_reouverture_puis_modification_du_corps(document: Any, rouvrir: Any) -> None:
    """Après réouverture, le lien suit encore son arête quand l'esquisse change."""
    shaped, _sketch = _piece(document)
    api.add_edge_profile(shaped, [_nom(shaped.Shape, AVANT)], "Chamfer", 2.0)
    shaped_name = shaped.Name
    doc = rouvrir(document)
    reopened = doc.getObject(shaped_name)
    sketch = next(o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject")
    _encoche_a_gauche(doc, sketch)
    profile = api.edge_profiles_of(reopened)[0]
    assert list(profile.EdgeRefs[1]) == [_nom(reopened.Shape, AVANT)]
    assert _enleve(reopened) == pytest.approx(_chanfrein(2.0, 400.0), rel=1e-2)


# --- Pièce rangée dans un Std Part, pièce en biais ---------------------------------------------


def test_piece_dans_un_std_part_deplace(document: Any) -> None:
    container = document.addObject("App::Part", "Meuble")
    container.Placement = App.Placement(App.Vector(500, 300, 100), App.Rotation(0, 0, 30))
    body, _sketch = _corps(document, _segments(EN_L))
    container.addObject(body)
    document.recompute()
    shaped = api.make_shaped_part(body)
    document.recompute()
    assert shaped.getParentGeoFeatureGroup() == container
    profile, _ = api.add_edge_profile(shaped, [_nom(shaped.Shape, AVANT)], "Round", 2.0)
    assert profile.getParentGeoFeatureGroup() == container
    assert "Invalid" not in profile.State
    assert _enleve(shaped) == pytest.approx(_quart_de_rond(2.0, 400.0), rel=1e-2)


def test_piece_en_biais(document: Any) -> None:
    """Corps tourné et basculé : la coupe se calcule dans le repère de la pièce."""
    body, _sketch = _corps(document, _segments(EN_L))
    body.Placement = App.Placement(App.Vector(30, -50, 200), App.Rotation(25, 40, 10))
    document.recompute()
    shaped = api.make_shaped_part(body)
    document.recompute()
    names = [
        f"Edge{index}"
        for index, edge in enumerate(shaped.Shape.Edges, start=1)
        if abs(edge.Length - 400.0) < 1e-6
    ]
    assert len(names) == 2  # bord avant, en haut et en bas
    api.add_edge_profile(shaped, names, "Chamfer", 3.0)
    assert _enleve(shaped) == pytest.approx(2 * _chanfrein(3.0, 400.0), rel=1e-2)


def test_profil_donne_par_la_piece_usinee(document: Any) -> None:
    shaped, _sketch = _piece(document)
    api.add_edge_profile(shaped, [_nom(shaped.Shape, AVANT)], "Chamfer", 2.0)
    machined = api.machined_part_of(shaped)
    second, _ = api.add_edge_profile(machined, [_nom(shaped.Shape, INTERIEUR)], "Chamfer", 2.0)
    assert second.Part == shaped
    assert _enleve(shaped) == pytest.approx(_chanfrein(2.0, 650.0), rel=1e-2)


# --- Arêtes courbes, faces courbes, chaîne tangente ----------------------------------------------


def _coin_arrondi() -> list[Any]:
    """Rectangle 300 x 100 dont le coin (300, 100) est arrondi (rayon 20)."""
    v = App.Vector
    arc = Part.ArcOfCircle(Part.Circle(v(280, 80, 0), v(0, 0, 1), 20), 0.0, math.pi / 2)
    return [
        Part.LineSegment(v(0, 0, 0), v(300, 0, 0)),
        Part.LineSegment(v(300, 0, 0), v(300, 80, 0)),
        arc,
        Part.LineSegment(v(280, 100, 0), v(0, 100, 0)),
        Part.LineSegment(v(0, 100, 0), v(0, 0, 0)),
    ]


def test_arete_courbe_et_faces_courbes_refusees(document: Any) -> None:
    shaped, _sketch = _piece(document, _coin_arrondi())
    shape = edge_profile.native_shape(shaped)
    courbe = next(
        index
        for index, edge in enumerate(shape.Edges, start=1)
        if not isinstance(edge.Curve, Part.Line)
    )
    count = len(document.Objects)
    with pytest.raises(ValueError, match="courbe"):
        api.add_edge_profile(shaped, [f"Edge{courbe}"], "Chamfer", 1.0)
    # arête droite verticale au pied de l'arrondi : entre un plan et un cylindre
    pied = _nom(shaped.Shape, ((300, 80, 0), (300, 80, EPAISSEUR)))
    with pytest.raises(ValueError, match="faces courbes"):
        api.add_edge_profile(shaped, [pied], "Chamfer", 1.0)
    assert len(document.Objects) == count
    assert edge_frames.native_edge(shape, courbe).refusal


def test_chaine_tangente_autour_d_un_arrondi(document: Any) -> None:
    """Q4 : un clic sur le bord du dessus prend l'arc tangent et le bord suivant."""
    shaped, _sketch = _piece(document, _coin_arrondi())
    shape = edge_profile.native_shape(shaped)
    droite = edge_frames.edge_index(_nom(shape, ((300, 0, EPAISSEUR), (300, 80, EPAISSEUR))))
    chaine = edge_frames.tangent_chain(shape, droite)
    longueurs = sorted(round(shape.Edges[index - 1].Length, 3) for index in chaine)
    assert longueurs == sorted([80.0, round(math.pi * 10, 3), 280.0])


def test_chaine_d_aretes_alignees_coupe_continue(document: Any) -> None:
    """B3 : deux arêtes alignées bout à bout (corps non affiné) donnent une coupe continue,
    sans entaille ni reste à leur jonction."""
    split = ((0, 0), (200, 0), (400, 0), (400, 100), (0, 100))
    shaped, _sketch = _piece(document, _segments(split), refine=False)
    shape = edge_profile.native_shape(shaped)
    first = edge_frames.edge_index(_nom(shape, ((0, 0, EPAISSEUR), (200, 0, EPAISSEUR))))
    second = _nom(shape, ((200, 0, EPAISSEUR), (400, 0, EPAISSEUR)))
    chaine = edge_frames.tangent_chain(shape, first)
    assert sorted(chaine) == sorted([first, edge_frames.edge_index(second)])
    api.add_edge_profile(shaped, [edge_frames.edge_name(i) for i in chaine], "Round", 3.0)
    machined = api.machined_part_of(shaped)
    assert len(machined.Shape.Solids) == 1
    assert _enleve(shaped) == pytest.approx(_quart_de_rond(3.0, 400.0), rel=1e-3)


# --- Valeurs et noms invalides -----------------------------------------------------------------


@pytest.mark.parametrize("size", [0.0, -1.0, math.nan, math.inf, 1e9])
def test_cotes_invalides_refusees_sans_creation(document: Any, size: float) -> None:
    shaped, _sketch = _piece(document)
    count = len(document.Objects)
    with pytest.raises(ValueError):
        api.add_edge_profile(shaped, [_nom(shaped.Shape, AVANT)], "Chamfer", size)
    assert len(document.Objects) == count


@pytest.mark.parametrize(
    "name", ["?Edge3", "Edge0", "Edge01", "edge3", "Edge3 ", "Face1", "Edge1234567", ""]
)
def test_noms_d_aretes_suspects_refuses(document: Any, name: str) -> None:
    shaped, _sketch = _piece(document)
    count = len(document.Objects)
    with pytest.raises((ValueError, TypeError)):
        api.add_edge_profile(shaped, [name], "Chamfer", 1.0)
    assert len(document.Objects) == count


def test_au_plus_64_aretes_par_profil(document: Any) -> None:
    shaped, _sketch = _piece(document)
    with pytest.raises(ValueError, match="au plus 64"):
        api.add_edge_profile(shaped, [f"Edge{i}" for i in range(1, 66)], "Chamfer", 1.0)
    with pytest.raises(ValueError):
        api.add_edge_profile(shaped, ["Edge1", "Edge1"], "Chamfer", 1.0)


def test_famille_inconnue_refusee(document: Any) -> None:
    shaped, _sketch = _piece(document)
    with pytest.raises((ValueError, KeyError)):
        api.add_edge_profile(shaped, [_nom(shaped.Shape, AVANT)], "Moulure", 1.0)


# --- C6 : contour intérieur d'une face, bouts fermés d'un U, chaîne longue --------------------


def test_face_percee_tout_son_contour_profile(document: Any) -> None:
    """Un clic sur le dessus d'un cadre prend aussi le contour du jour ; le profil passe sur les
    8 arêtes et la pièce usinée reste un seul solide valide."""
    dehors = _segments(((0, 0), (300, 0), (300, 200), (0, 200)))
    dedans = _segments(((60, 60), (240, 60), (240, 140), (60, 140)))
    shaped, _sketch = _piece(document, [*dehors, *dedans])
    shape = shaped.Shape
    dessus = next(
        f"Face{i}"
        for i, face in enumerate(shape.Faces, start=1)
        if abs(face.CenterOfMass.z - EPAISSEUR) < 1e-6
    )
    names = edge_frames.face_edge_names(shape, dessus)
    assert len(names) == 8
    api.add_edge_profile(shaped, names, "Chamfer", 2.0)
    machined = api.machined_part_of(shaped)
    assert len(machined.Shape.Solids) == 1
    assert _enleve(shaped) > _chanfrein(2.0, 2 * (300 + 200) + 2 * (180 + 80)) * 0.95


def test_fond_d_un_u_sans_entaille_aux_deux_bouts(document: Any) -> None:
    en_u = ((0, 0), (300, 0), (300, 200), (200, 200), (200, 80), (100, 80), (100, 200), (0, 200))
    shaped, _sketch = _piece(document, _segments(en_u))
    fond = _nom(shaped.Shape, ((100, 80, EPAISSEUR), (200, 80, EPAISSEUR)))
    shape = edge_profile.native_shape(shaped)
    frame = edge_frames.native_edge(shape, edge_frames.edge_index(fond)).frame
    assert frame is not None
    assert (frame.extend_start, frame.extend_end) == (False, False)
    api.add_edge_profile(shaped, [fond], "Round", 3.0)
    assert _enleve(shaped) == pytest.approx(_quart_de_rond(3.0, 100.0), rel=1e-3)


def test_chaine_tangente_longue_garde_l_arete_cliquee(document: Any) -> None:
    """Plus de 64 arêtes alignées : la chaîne est tronquée, mais jamais sans l'arête cliquée."""
    count = 70
    devant = [(400.0 * i / count, 0.0) for i in range(count + 1)]
    shaped, _sketch = _piece(
        document, _segments((*devant, (400.0, 100.0), (0.0, 100.0))), refine=False
    )
    shape = edge_profile.native_shape(shaped)
    dessus = [
        index
        for index, edge in enumerate(shape.Edges, start=1)
        if all(abs(v.Point.y) < 1e-6 and abs(v.Point.z - EPAISSEUR) < 1e-6 for v in edge.Vertexes)
    ]
    assert len(dessus) == count
    for index in (min(dessus), max(dessus)):
        chaine = edge_frames.tangent_chain(shape, index)
        assert len(chaine) <= edge_frames.MAX_NATIVE_EDGES
        assert index in chaine


# --- § 7 : fonction du corps supprimée ----------------------------------------------------------


def _protrusion(doc: Any, body: Any, points: tuple[Point, ...]) -> Any:
    sketch = body.newObject("Sketcher::SketchObject", "Esquisse")
    for geometry in _segments(points):
        sketch.addGeometry(geometry, False)
    pad = body.newObject("PartDesign::Pad", "Protrusion")
    pad.Profile = sketch
    pad.Length = EPAISSEUR
    doc.recompute()
    return pad


def test_fonction_supprimee_arete_perdue_signalee(document: Any, vue_rapport: Any) -> None:
    """Corps en deux protrusions (un L) : supprimer la seconde perd l'arête qu'elle portait,
    l'arête de la première reste suivie et garde son profil."""
    body = document.addObject("PartDesign::Body", "Corps")
    _protrusion(document, body, ((0, 0), (400, 0), (400, 100), (0, 100)))
    second = _protrusion(document, body, ((0, 100), (150, 100), (150, 200), (0, 200)))
    shaped = api.make_shaped_part(body)
    document.recompute()
    avant = _nom(shaped.Shape, AVANT)
    fond = _nom(shaped.Shape, ((0, 200, EPAISSEUR), (150, 200, EPAISSEUR)))
    profile, _ = api.add_edge_profile(shaped, [avant, fond], "Chamfer", 2.0)
    sketch = second.Profile[0]
    body.removeObject(second)
    document.removeObject(second.Name)
    document.removeObject(sketch.Name)
    document.recompute()
    assert len(edge_profile.lost_edges(profile)) == 1
    suivie = [name for name in profile.EdgeRefs[1] if not name.startswith("?")]
    assert suivie == [_nom(shaped.Shape, AVANT)]
    assert any("perdues" in text for text in vue_rapport.de_niveau("Warning"))
    assert "Invalid" not in profile.State
    assert _enleve(shaped) == pytest.approx(_chanfrein(2.0, 400.0), rel=1e-2)


def test_modifier_un_profil_avec_arete_perdue_message_clair(document: Any) -> None:
    """Redonner au profil ses propres arêtes (``designated_edges``) pour ne changer que la cote :
    l'arête perdue doit être nommée comme perdue, pas comme un mélange de codes et de noms."""
    shaped, sketch = _piece(document)
    names = [_nom(shaped.Shape, AVANT), _nom(shaped.Shape, GAUCHE)]
    profile, _ = api.add_edge_profile(shaped, names, "Chamfer", 2.0)
    _encoche_a_gauche(document, sketch)
    with pytest.raises(ValueError) as refus:
        api.set_edge_profile(profile, edge_profile.designated_edges(profile), "Chamfer", 3.0)
    assert "pas les deux" not in str(refus.value)
    assert "perdue" in str(refus.value)


# --- Arêtes relues d'un fichier modifié à la main (revue, M2) --------------------------------


def _profil_relu(doc: Any, noms: list[str]) -> tuple[Any, Any]:
    """Profil créé normalement, puis ses arêtes réécrites comme dans un fichier modifié."""
    corps, _esquisse = _corps(doc, _segments(EN_L))
    piece = api.make_shaped_part(corps)
    doc.recompute()
    profil, _messages = api.add_edge_profile(piece, ["Edge1"], "Chamfer", 1.0)
    profil.EdgeRefs = (piece, noms)
    doc.recompute()
    return piece, profil


@pytest.mark.parametrize(
    "noms",
    [
        [f"Edge{rang}" for rang in range(1, edge_frames.MAX_NATIVE_EDGES + 2)],  # 65 arêtes
        ["Edge1", "?Edge1"],  # la même arête, suivie et perdue
        ["Edge2", "Edge2"],
    ],
    ids=["trop-nombreuses", "suivie-et-perdue", "doublon"],
)
def test_aretes_relues_invalides_profil_en_erreur(document: Any, noms: list[str]) -> None:
    _piece, profil = _profil_relu(document, noms)
    assert "Invalid" in profil.State
    with pytest.raises(ValueError, match="au plus 64") as refus:
        edge_profile.edge_cuts(profil)
    assert "?Edge" not in str(refus.value)


def test_nom_illisible_signale_sans_etre_recopie(document: Any, vue_rapport: Any) -> None:
    intrus = "<b>Texte‮injecté</b>"
    _piece, profil = _profil_relu(document, ["Edge1", intrus])
    # nom illisible traité comme une arête perdue : signalé, la pièce usinée suit
    assert "Invalid" not in profil.State
    avertissements = vue_rapport.de_niveau("Warning")
    assert any("nom illisible" in texte for texte in avertissements)
    assert all(intrus not in texte for texte in avertissements)
    assert all(intrus not in nom for nom in edge_profile.lost_edges(profil))


def test_aretes_d_une_autre_piece_refusees(document: Any) -> None:
    piece, profil = _profil_relu(document, ["Edge1"])
    autre_corps, _esquisse = _corps(document, _segments(EN_L))
    autre = api.make_shaped_part(autre_corps)
    document.recompute()
    profil.EdgeRefs = (autre, ["Edge1"])
    document.recompute()
    assert profil.Part == piece
    assert "Invalid" in profil.State
    with pytest.raises(ValueError, match="autre pièce"):
        edge_profile.edge_cuts(profil)
