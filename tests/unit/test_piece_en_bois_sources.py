# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecteurs de sources de la pièce en bois (B2, B11) sur des objets simulés.

Les refus et leurs messages, le choix du lecteur, les solides d'une forme importée et leur empreinte
sont vérifiés ici sans FreeCAD ; les vraies formes (corps PartDesign, esquisse, import) le sont par
``tests/integration/test_piece_en_bois.py``."""

from __future__ import annotations

import math
import types
from collections.abc import Iterator
from typing import Any

import pytest

from tests.unit.aides_freecad import simulated_freecad
from tests.unit.aides_piece_en_bois import (
    FakeShape,
    FakeSolid,
    FakeSource,
    FakeWire,
    body,
    sketch,
    workshop_proxy,
)


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """``features.shaped_sources`` importé sur un FreeCAD simulé."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import shaped_sources

        yield shaped_sources


def solid_shape(*volumes: float) -> FakeShape:
    return FakeShape(tuple(FakeSolid(volume) for volume in volumes))


# --- Refus d'objets ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module",
    [
        "freecad.menuiserie.features.wood_part",
        "freecad.menuiserie.features.machined_part",
        "freecad.menuiserie.features.shaped_part",
        "freecad.menuiserie.features.furniture",
        "freecad.menuiserie.features.joints.mortise_tenon",
    ],
)
def test_objet_de_l_atelier_refuse(sources: Any, module: str) -> None:
    obj = FakeSource(solid_shape(10.0), proxy=workshop_proxy(module))
    with pytest.raises(TypeError, match="objet de l'atelier"):
        sources.read_source(obj, 22.0)


def test_proxy_d_un_autre_atelier_accepte(sources: Any) -> None:
    obj = FakeSource(solid_shape(10.0), proxy=workshop_proxy("Draft.draftobjects.wire"))
    assert len(sources.read_source(obj, 22.0).solids) == 1


def test_type_non_pris_en_charge(sources: Any) -> None:
    obj = FakeSource(solid_shape(10.0), derived=("App::Part",), label="Assemblage")
    with pytest.raises(TypeError, match="« Assemblage » ne peut pas devenir une pièce en bois"):
        sources.read_source(obj, 22.0)


def test_le_libelle_cite_est_echappe_et_tronque(sources: Any) -> None:
    obj = FakeSource(derived=(), label="Corps\n‮" + "x" * 80)
    with pytest.raises(TypeError) as caught:
        sources.read_source(obj, 22.0)
    message = str(caught.value)
    assert "\n" not in message
    assert "‮" not in message
    assert len(message) < 250


# --- Forme Part ----------------------------------------------------------------------------


def test_forme_part_a_un_solide(sources: Any) -> None:
    obj = FakeSource(solid_shape(1000.0), type_id="Part::Box")
    reading = sources.read_source(obj, 22.0)
    assert reading.source is obj
    assert len(reading.solids) == 1
    assert not reading.profile
    assert not reading.importable


@pytest.mark.parametrize(
    ("shape", "message"),
    [
        (None, "pas de forme"),
        (FakeShape(null=True), "pas de forme"),
        (FakeShape(), "n'est pas un solide"),
        (FakeShape((FakeSolid(valid=False),)), "solide valide"),
        (FakeShape((FakeSolid(0.0),)), "solide valide"),
        (FakeShape((FakeSolid(), FakeSolid(valid=False))), "solide valide"),
    ],
    ids=["absente", "nulle", "sans-solide", "invalide", "volume-nul", "un-invalide"],
)
def test_forme_vide_ou_invalide_refusee(sources: Any, shape: Any, message: str) -> None:
    obj = FakeSource(shape, type_id="Part::Box", label="Pied")
    with pytest.raises(ValueError, match=message):
        sources.read_source(obj, 22.0)


def test_forme_parametrique_a_plusieurs_solides_refusee(sources: Any) -> None:
    obj = FakeSource(solid_shape(1.0, 2.0), type_id="Part::Cut", out_list=(object(),), label="Cut")
    with pytest.raises(ValueError, match="séparez-les en plusieurs corps") as caught:
        sources.read_source(obj, 22.0)
    assert "2 solides" in str(caught.value)


def test_copie_simple_a_plusieurs_solides_est_importable(sources: Any) -> None:
    obj = FakeSource(solid_shape(1.0, 2.0, 3.0), type_id="Part::Feature")
    reading = sources.read_source(obj, 22.0)
    assert reading.importable
    assert [solid.Volume for solid in reading.solids] == [1.0, 2.0, 3.0]


def test_forme_part_feature_avec_dependance_n_est_pas_importable(sources: Any) -> None:
    obj = FakeSource(solid_shape(1.0, 2.0), type_id="Part::Feature", out_list=(object(),))
    with pytest.raises(ValueError, match="séparez-les"):
        sources.read_source(obj, 22.0)


def test_forme_part_featurepython_d_un_autre_atelier(sources: Any) -> None:
    obj = FakeSource(
        solid_shape(1.0), type_id="Part::FeaturePython", proxy=workshop_proxy("Curves.proxy")
    )
    assert len(sources.read_source(obj, 22.0).solids) == 1


# --- Corps PartDesign ----------------------------------------------------------------------


def test_corps_lit_la_forme_du_tip(sources: Any) -> None:
    obj = body(solid_shape(1000.0))
    reading = sources.read_source(obj, 22.0)
    assert reading.source is obj
    assert not reading.importable


def test_corps_sans_forme_refuse(sources: Any) -> None:
    with pytest.raises(ValueError, match="pas de forme"):
        sources.read_source(body(FakeShape(null=True)), 22.0)


def test_corps_a_plusieurs_solides_refuse(sources: Any) -> None:
    with pytest.raises(ValueError, match="séparez-les"):
        sources.read_source(body(solid_shape(1.0, 2.0)), 22.0)


@pytest.mark.parametrize("member", ["feature", "esquisse"])
def test_fonction_partdesign_ramenee_a_son_corps(sources: Any, member: str) -> None:
    corps = body(solid_shape(1000.0))
    if member == "feature":
        obj = FakeSource(
            solid_shape(5.0),
            type_id="PartDesign::Pad",
            derived=("PartDesign::Pad", "PartDesign::Feature", "Part::Feature"),
            geo_parent=corps,
        )
    else:
        obj = sketch(FakeShape(edges=4), "Sketch")
        obj.geo_parent = corps
    reading = sources.read_source(obj, 22.0)
    assert reading.source is corps
    assert reading.solids[0].Volume == 1000.0
    assert not reading.profile


def test_fonction_partdesign_sans_corps_refusee(sources: Any) -> None:
    orphan = FakeSource(
        solid_shape(5.0), derived=("PartDesign::Feature", "Part::Feature"), label="Pad"
    )
    with pytest.raises(TypeError, match="« Pad » ne peut pas devenir"):
        sources.read_source(orphan, 22.0)


# --- Esquisse en mode profil ---------------------------------------------------------------


@pytest.mark.parametrize("thickness", [0.0, -5.0, 0.05, 20_001.0, math.inf, math.nan])
def test_epaisseur_du_profil_hors_bornes(sources: Any, thickness: float) -> None:
    obj = sketch(FakeShape(edges=4))
    with pytest.raises(ValueError, match="Épaisseur du profil invalide"):
        sources.read_source(obj, thickness)


def test_esquisse_vide_refusee(sources: Any) -> None:
    with pytest.raises(ValueError, match="pas de forme"):
        sources.read_source(sketch(FakeShape(edges=0)), 22.0)


def test_esquisse_ouverte_refusee(sources: Any) -> None:
    obj = sketch(FakeShape(edges=3, wires=(FakeWire(True), FakeWire(False))), "Profil")
    with pytest.raises(ValueError, match="« Profil » n'est pas fermée"):
        sources.read_source(obj, 22.0)


def test_esquisse_sans_contour_refusee(sources: Any) -> None:
    with pytest.raises(ValueError, match="n'est pas fermée"):
        sources.read_source(sketch(FakeShape(edges=2, wires=())), 22.0)


def test_esquisse_non_plane_refusee(sources: Any) -> None:
    obj = sketch(FakeShape(edges=4, wires=(FakeWire(),), z_length=3.0))
    with pytest.raises(ValueError, match="n'est pas plane"):
        sources.read_source(obj, 22.0)


def test_esquisse_a_plusieurs_surfaces_refusee(
    sources: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    faces = types.SimpleNamespace(Faces=[object(), object()])
    monkeypatch.setattr(sources.Part, "makeFace", lambda *_args: faces, raising=False)
    obj = sketch(FakeShape(edges=8, wires=(FakeWire(), FakeWire())))
    with pytest.raises(ValueError, match="plusieurs surfaces séparées"):
        sources.read_source(obj, 22.0)


def test_esquisse_fermee_extrudee(sources: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    extruded: list[Any] = []

    class Face:
        def extrude(self, vector: Any) -> FakeShape:
            extruded.append(vector)
            return solid_shape(2200.0)

    monkeypatch.setattr(sources.App, "Vector", lambda x, y, z: (x, y, z), raising=False)

    made = types.SimpleNamespace(Faces=[Face()])
    monkeypatch.setattr(sources.Part, "makeFace", lambda *_args: made, raising=False)
    obj = sketch(FakeShape(edges=4, wires=(FakeWire(),)))
    reading = sources.read_source(obj, 22.0)
    assert reading.profile
    assert reading.source is obj
    assert [solid.Volume for solid in reading.solids] == [2200.0]
    assert extruded == [(0.0, 0.0, 22.0)]  # le long de la normale de l'esquisse (Z)


def test_face_invalide_de_l_esquisse_refusee(sources: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_args: Any) -> Any:
        raise ValueError("contour croisé")

    monkeypatch.setattr(sources.Part, "makeFace", broken, raising=False)
    monkeypatch.setattr(sources, "ERRORS", (ValueError,))  # les erreurs d'OCC, simulées
    obj = sketch(FakeShape(edges=4, wires=(FakeWire(),)))
    with pytest.raises(ValueError, match="n'est pas plane ou son contour est invalide"):
        sources.read_source(obj, 22.0)


# --- Solide d'une forme importée (B11) -----------------------------------------------------


def reading_of(sources: Any, *solids: FakeSolid) -> Any:
    obj = FakeSource(label="Import")
    return sources.SourceReading(obj, tuple(solids), importable=len(solids) > 1)


def test_solide_unique_sans_rang(sources: Any) -> None:
    solid = FakeSolid()
    assert sources.picked_solid(reading_of(sources, solid), -1, "") is solid


def test_plusieurs_solides_sans_rang_refuse(sources: Any) -> None:
    with pytest.raises(ValueError, match="2 solides"):
        sources.picked_solid(reading_of(sources, FakeSolid(), FakeSolid(2.0)), -1, "")


def test_solide_designe_par_son_rang_et_son_empreinte(sources: Any) -> None:
    first, second = FakeSolid(100.0), FakeSolid(200.0, center=(1.0, 2.0, 3.0))
    reading = reading_of(sources, first, second)
    assert sources.picked_solid(reading, 1, sources.signature_text(second)) is second
    assert sources.picked_solid(reading, 0, sources.signature_text(first)) is first


def test_deux_solides_identiques_ont_la_meme_empreinte(sources: Any) -> None:
    assert sources.signature_text(FakeSolid(100.0)) == sources.signature_text(FakeSolid(100.0))


def test_empreinte_qui_ne_correspond_plus_refusee(sources: Any) -> None:
    first, second = FakeSolid(100.0), FakeSolid(200.0)
    stored = sources.signature_text(first)
    swapped = reading_of(sources, second, first)  # forme remplacée : solides renumérotés
    with pytest.raises(ValueError, match="n'est plus celui qui a été converti"):
        sources.picked_solid(swapped, 0, stored)
    assert sources.picked_solid(swapped, 1, stored) is first


def test_rang_inexistant_refuse(sources: Any) -> None:
    with pytest.raises(ValueError, match="solide n° 3 de « Import » n'existe plus"):
        sources.picked_solid(reading_of(sources, FakeSolid(), FakeSolid(2.0)), 3, "x")


def test_empreinte_illisible_refusee(sources: Any) -> None:
    reading = reading_of(sources, FakeSolid(), FakeSolid(2.0))
    with pytest.raises(ValueError, match="n'est plus celui"):
        sources.picked_solid(reading, 0, "")


# --- Conteneur -----------------------------------------------------------------------------


def test_conteneur_de_la_source(sources: Any) -> None:
    part = FakeSource(derived=("App::Part",), label="Meuble")
    assert sources.container_of(FakeSource(group_parent=part)) is part
    assert sources.container_of(FakeSource()) is None


def test_un_corps_ne_recoit_que_ses_fonctions(sources: Any) -> None:
    part = FakeSource(derived=("App::Part",), label="Meuble")
    corps = body(solid_shape(1.0))
    corps.group_parent = part
    esquisse = sketch(FakeShape(edges=4))
    esquisse.group_parent = corps
    assert sources.container_of(esquisse) is part
    assert sources.container_of(corps) is part
    assert sources.container_of(body(solid_shape(1.0))) is None


def test_position_propre_d_un_solide_de_compose_inscrite_dans_la_geometrie(sources: Any) -> None:
    """Un solide importé décalé (placement propre) garde sa position dans le repère de la source."""
    calls: list[str] = []

    class Located(FakeSolid):
        def __init__(self) -> None:
            super().__init__()
            self.Placement = types.SimpleNamespace(
                isIdentity=lambda: False, toMatrix=lambda: "matrice"
            )

        def copy(self) -> Located:
            return self

        def transformShape(self, matrix: str, copy: bool) -> None:  # nom imposé par FreeCAD
            calls.append(f"{matrix} {copy}")

    baked = sources._baked(Located())
    assert calls == ["matrice True"]
    assert baked.Placement is not None
