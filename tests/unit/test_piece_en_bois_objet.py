# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce en bois : schéma, proxy, prédicats, création et API (B1, B5, B7, B9, B11), sur des objets
simulés. L'objet réel, les formes OCC et la réouverture sont vérifiés par
``tests/integration/test_piece_en_bois.py``."""

from __future__ import annotations

import contextlib
import importlib
import types
from collections.abc import Iterator
from typing import Any, ClassVar

import pytest

from tests.unit.aides_freecad import simulated_freecad
from tests.unit.aides_piece_en_bois import FakeSolid, FakeSource, workshop_proxy

MODES = {0: [], 1: ["ReadOnly"], 2: ["Hidden"]}
MATERIAL_NAMES = (
    "Material",
    "MaterialId",
    "Category",
    "Density",
    "GrainDirection",
    "PreferredGrainDirection",
    "Mark",
    "LengthAllowance",
    "WidthAllowance",
    "ThicknessAllowance",
)
WOOD_PART_NAMES = (
    "Length",
    "Width",
    "Thickness",
    *MATERIAL_NAMES,
    "Version",
)


@pytest.fixture
def modules(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.SimpleNamespace]:
    """Modules de la pièce de bois et de la pièce en bois sur un FreeCAD simulé."""
    with simulated_freecad(monkeypatch) as report:
        api = importlib.import_module("freecad.menuiserie.api")  # pas l'ancien attribut du paquet
        from freecad.menuiserie.features import (
            shaped_create,
            shaped_part,
            shaped_part_schema,
            wood_material,
            wood_material_proxy,
            wood_part,
            wood_part_schema,
        )

        yield types.SimpleNamespace(
            api=api,
            create=shaped_create,
            shaped=shaped_part,
            shaped_schema=shaped_part_schema,
            material=wood_material,
            proxy=wood_material_proxy,
            wood=wood_part,
            wood_schema=wood_part_schema,
            report=report,
        )


class FakePart:
    """Objet FreeCAD minimal : propriétés, modes d'édition, statuts, écritures journalisées."""

    def __init__(self, **props: Any) -> None:
        values = {"Label": "P1", "Mark": "", **props}
        object.__setattr__(self, "props", values)
        object.__setattr__(self, "State", [])
        object.__setattr__(self, "Document", types.SimpleNamespace(Transacting=False))
        object.__setattr__(self, "modes", {})
        object.__setattr__(self, "status", {})
        object.__setattr__(self, "writes", [])
        object.__setattr__(self, "ExpressionEngine", [])

    @property
    def PropertiesList(self) -> list[str]:  # nom imposé par FreeCAD
        return list(self.props)

    def __getattr__(self, name: str) -> Any:
        try:
            return object.__getattribute__(self, "props")[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self.writes.append(name)
        self.props[name] = value

    def getEditorMode(self, name: str) -> list[str]:  # nom imposé par FreeCAD
        modes: list[str] = self.modes.get(name, [])
        return modes

    def setEditorMode(self, name: str, mode: int) -> None:  # nom imposé par FreeCAD
        self.writes.append(f"mode:{name}")
        self.modes[name] = MODES[mode]

    def getPropertyStatus(self, name: str) -> list[str]:  # nom imposé par FreeCAD
        status: list[str] = self.status.get(name, [])
        return status

    def setPropertyStatus(self, name: str, value: str) -> None:  # nom imposé par FreeCAD
        self.status.setdefault(name, []).append(value)

    def setExpression(self, name: str, expression: str | None) -> None:  # nom imposé par FreeCAD
        kept = [(path, text) for path, text in self.ExpressionEngine if path != name]
        if expression is not None:
            kept.append((name, expression))
        object.__setattr__(self, "ExpressionEngine", kept)


def shaped_proxy(modules: types.SimpleNamespace) -> Any:
    """Proxy ``ShapedPart`` sans objet (``__init__`` n'est pas rappelé à la réouverture)."""
    return modules.shaped.ShapedPart.__new__(modules.shaped.ShapedPart)


def with_proxy(modules: types.SimpleNamespace, **props: Any) -> FakePart:
    part = FakePart(**props)
    part.props["Proxy"] = shaped_proxy(modules)
    return part


# --- Extraction du matériau : WoodPart inchangée (ADR 0020, décision 6) ---------------------


def test_les_proprietes_de_la_piece_de_bois_sont_inchangees(modules: Any) -> None:
    specs = modules.wood_schema.PROPERTIES
    assert tuple(spec.name for spec in specs) == WOOD_PART_NAMES
    assert modules.wood_schema.MODEL_VERSION == 2
    assert modules.wood.WoodPart.VERSION == 2
    by_name = {spec.name: spec for spec in specs}
    assert by_name["Version"].mode == 2
    assert by_name["Version"].group == "Base"
    assert [by_name[name].group for name in ("Length", "Width", "Thickness")] == ["Dimensions"] * 3
    assert all(by_name[name].mode == 0 for name in ("Length", "Width", "Thickness"))


def test_les_deux_pieces_partagent_les_proprietes_de_materiau(modules: Any) -> None:
    wood = {spec.name: spec for spec in modules.wood_schema.PROPERTIES}
    shaped = {spec.name: spec for spec in modules.shaped_schema.PROPERTIES}
    for name in (*MATERIAL_NAMES, "Version"):
        assert shaped[name] == wood[name], name
    assert tuple(spec.name for spec in modules.material.MATERIAL_PROPERTIES) == MATERIAL_NAMES


def test_les_deux_proxys_partagent_le_comportement_de_materiau(modules: Any) -> None:
    base = modules.proxy.MaterialProxy
    assert issubclass(modules.wood.WoodPart, base)
    assert issubclass(modules.shaped.ShapedPart, base)
    for proxy_class in (modules.wood.WoodPart, modules.shaped.ShapedPart):
        for method in ("onBeforeChangeLabel", "select_material", "sync_label", "adopt_mark"):
            assert getattr(proxy_class, method) is getattr(base, method), method


def test_contrat_de_persistance_de_la_piece_en_bois(modules: Any) -> None:
    proxy_class = modules.shaped.ShapedPart
    assert proxy_class.__module__ == "freecad.menuiserie.features.shaped_part"
    assert proxy_class.__qualname__ == "ShapedPart"
    assert proxy_class.TYPE == "Menuiserie::ShapedPart"
    assert proxy_class.VERSION == modules.shaped_schema.MODEL_VERSION == 1
    assert shaped_proxy(modules).dumps() is None


# --- Schéma de la pièce en bois (B5, B9, B11) -----------------------------------------------


def test_proprietes_propres_de_la_piece_en_bois(modules: Any) -> None:
    by_name = {spec.name: spec for spec in modules.shaped_schema.PROPERTIES}
    assert [(n, by_name[n].type_id, by_name[n].group, by_name[n].mode) for n in by_name][:8] == [
        ("Source", "App::PropertyLink", "Forme", 0),
        ("SourceAxes", "App::PropertyPlacement", "Forme", 2),
        ("ProfileThickness", "App::PropertyLength", "Forme", 2),
        ("SolidIndex", "App::PropertyInteger", "Forme", 1),
        ("SolidSignature", "App::PropertyString", "Forme", 2),
        ("Length", "App::PropertyLength", "Dimensions", 1),
        ("Width", "App::PropertyLength", "Dimensions", 1),
        ("Thickness", "App::PropertyLength", "Dimensions", 1),
    ]
    assert modules.shaped_schema.DIMENSION_NAMES == ("Length", "Width", "Thickness")
    assert modules.shaped_schema.DEFAULT_PROFILE_THICKNESS == 22.0


def test_cotes_en_sortie_et_modes_d_edition(modules: Any) -> None:
    part = FakePart(
        Length=1,
        Width=1,
        Thickness=1,
        ProfileThickness=1,
        SolidIndex=-1,
        Source=None,
        SourceAxes=None,
        SolidSignature="",
    )
    modules.shaped_schema.apply_editor_modes(part)
    assert [part.status[name] for name in ("Length", "Width", "Thickness")] == [["Output"]] * 3
    assert [part.modes[name] for name in ("Length", "Width", "Thickness")] == [["ReadOnly"]] * 3
    assert part.modes["ProfileThickness"] == ["Hidden"]
    assert part.modes["SolidIndex"] == ["Hidden"]
    assert part.modes["SourceAxes"] == ["Hidden"]
    assert part.modes["SolidSignature"] == ["Hidden"]


@pytest.mark.parametrize(
    ("profile", "index", "profile_mode", "index_mode"),
    [(True, -1, [], ["Hidden"]), (False, 2, ["Hidden"], ["ReadOnly"])],
)
def test_modes_selon_la_source(
    modules: Any, profile: bool, index: int, profile_mode: list[str], index_mode: list[str]
) -> None:
    part = FakePart(Length=1, Width=1, Thickness=1, ProfileThickness=22, SolidIndex=index)
    part.modes["ProfileThickness"] = ["Hidden"]  # état initial (propriété ajoutée masquée)
    modules.shaped_schema.apply_editor_modes(part, profile=profile)
    assert part.modes["ProfileThickness"] == profile_mode
    assert part.modes["SolidIndex"] == index_mode


def test_le_statut_output_n_est_pose_qu_une_fois(modules: Any) -> None:
    part = FakePart(Length=1, Width=1, Thickness=1)
    modules.shaped_schema.apply_editor_modes(part)
    written = len(part.writes)
    modules.shaped_schema.apply_editor_modes(part)
    assert part.status["Length"] == ["Output"]
    assert len(part.writes) == written  # rien n'est réécrit


@pytest.mark.parametrize(("version", "newer"), [(0, False), (1, False), (2, True), ("x", False)])
def test_version_plus_recente_detectee(modules: Any, version: Any, newer: bool) -> None:
    part = FakePart(Version=version)
    assert modules.shaped_schema.is_from_newer_version(part) is newer


# --- Prédicats ------------------------------------------------------------------------------


def test_predicats_de_pieces(modules: Any) -> None:
    shaped = with_proxy(modules)
    wood = FakePart(Proxy=modules.wood.WoodPart.__new__(modules.wood.WoodPart))
    other = FakePart(Proxy=workshop_proxy("Draft.proxy"))
    assert modules.shaped.is_shaped_part(shaped)
    assert not modules.shaped.is_shaped_part(wood)
    assert modules.wood.is_wood_part(wood)
    assert not modules.wood.is_wood_part(shaped)
    for obj in (shaped, wood):
        assert modules.shaped.is_timber(obj)
    unrelated: list[Any] = [other, FakePart(), None, object()]
    for obj in unrelated:
        assert not modules.shaped.is_timber(obj)
        assert not modules.shaped.is_shaped_part(obj)


def test_predicat_d_un_objet_supprime(modules: Any) -> None:
    class Deleted:
        @property
        def Proxy(self) -> Any:  # nom imposé par FreeCAD
            raise ReferenceError("objet supprimé")

    assert not modules.shaped.is_timber(Deleted())
    assert not modules.shaped.is_shaped_part(Deleted())


def test_les_predicats_sont_dans_l_api(modules: Any) -> None:
    assert modules.api.is_shaped_part is modules.shaped.is_shaped_part
    assert modules.api.is_timber is modules.shaped.is_timber


def test_dimensions_et_enregistrement_valent_pour_les_deux_pieces(modules: Any) -> None:
    assert modules.shaped.dimensions_of is modules.wood.dimensions_of
    assert modules.shaped.record_of is modules.wood.record_of


# --- Mode profil ----------------------------------------------------------------------------


def test_mode_profil_selon_la_source(modules: Any) -> None:
    profile = FakePart(Source=FakeSource(derived=("Part::Part2DObject",)))
    body = FakePart(Source=FakeSource(derived=("PartDesign::Body",)))
    assert modules.shaped.is_profile(profile)
    assert not modules.shaped.is_profile(body)
    assert not modules.shaped.is_profile(FakePart(Source=None))
    assert not modules.shaped.is_profile(FakePart())


# --- Cotes de sortie : expression refusée (B5) ----------------------------------------------


def test_expression_sur_une_cote_refusee(modules: Any) -> None:
    part = with_proxy(modules, Label="Pied")
    part.setExpression("Length", "Width * 2")
    part.setExpression("Mark", "'P1'")
    part.Proxy.onChanged(part, "ExpressionEngine")
    assert [path for path, _text in part.ExpressionEngine] == ["Mark"]
    [warning] = modules.report
    assert "Length" in warning
    assert "viennent du dessin" in warning
    assert "« Pied »" in warning


@pytest.mark.parametrize("name", ["Length", "Width", "Thickness"])
def test_chaque_cote_est_protegee(modules: Any, name: str) -> None:
    part = with_proxy(modules)
    part.setExpression(name, "10 mm")
    part.Proxy.onChanged(part, "ExpressionEngine")
    assert part.ExpressionEngine == []


def test_expression_conservee_pendant_la_restauration(modules: Any) -> None:
    part = with_proxy(modules)
    part.State.append("Restore")
    part.setExpression("Length", "10 mm")
    part.Proxy.onChanged(part, "ExpressionEngine")
    assert part.ExpressionEngine == [("Length", "10 mm")]
    assert modules.report == []


def test_une_autre_propriete_ne_declenche_rien(modules: Any) -> None:
    part = with_proxy(modules)
    part.setExpression("Length", "10 mm")
    part.Proxy.onChanged(part, "Placement")
    assert part.ExpressionEngine == [("Length", "10 mm")]


# --- execute : forme, Placement et cotes de sortie (B3, B5) ---------------------------------


def dims(length: float, width: float, thickness: float) -> dict[str, Any]:
    return {
        name: types.SimpleNamespace(Value=value)
        for name, value in zip(
            ("Length", "Width", "Thickness"), (length, width, thickness), strict=True
        )
    }


def test_execute_ecrit_les_cotes_qui_changent_seulement(
    modules: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    form = types.SimpleNamespace(shape="SHAPE", extents=(720.0, 95.0, 45.0))
    monkeypatch.setattr(modules.shaped, "shaped_form", lambda _obj: form)
    part = with_proxy(modules, Placement="PLACEMENT", **dims(720.0, 90.0, 45.0))
    part.Proxy.execute(part)
    assert part.Shape == "SHAPE"
    assert part.Placement == "PLACEMENT"
    cotes = [write for write in part.writes if write in ("Length", "Width", "Thickness")]
    assert cotes == ["Width"]
    assert part.Width == 95.0


def test_execute_ne_touche_aucune_cote_inchangee(
    modules: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    form = types.SimpleNamespace(shape="SHAPE", extents=(720.0, 95.0, 45.0))
    monkeypatch.setattr(modules.shaped, "shaped_form", lambda _obj: form)
    part = with_proxy(modules, Placement="P", **dims(720.0, 95.0, 45.0))
    part.Proxy.execute(part)
    assert [w for w in part.writes if w in ("Length", "Width", "Thickness")] == []


def test_execute_laisse_passer_le_refus_de_la_source(
    modules: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_obj: Any) -> None:
        raise ValueError("source refusée")

    monkeypatch.setattr(modules.shaped, "shaped_form", refuse)
    part = with_proxy(modules, Placement="P", **dims(1.0, 1.0, 1.0))
    with pytest.raises(ValueError, match="source refusée"):
        part.Proxy.execute(part)
    assert "Shape" not in part.props


def test_source_supprimee_met_la_piece_en_erreur_sans_exception_python(modules: Any) -> None:
    part = with_proxy(modules, Label="Pied", Source=None)
    with pytest.raises(ValueError, match="« Pied » sans forme") as caught:
        modules.shaped.shaped_form(part)
    assert "annulez la suppression" in str(caught.value)


def test_source_solid_lit_epaisseur_rang_et_empreinte(
    modules: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FakeSource()
    seen: list[tuple[Any, ...]] = []
    reading = object()

    def read(obj: Any, thickness: float) -> Any:
        seen.append((obj, thickness))
        return reading

    def pick(read_: Any, index: int, signature: str) -> str:
        seen.append((read_, index, signature))
        return "SOLID"

    monkeypatch.setattr(modules.shaped, "read_source", read)
    monkeypatch.setattr(modules.shaped, "picked_solid", pick)
    part = with_proxy(
        modules,
        Source=source,
        ProfileThickness=types.SimpleNamespace(Value=30.0),
        SolidIndex=2,
        SolidSignature="abc",
    )
    assert modules.shaped.source_solid(part) == "SOLID"
    assert seen == [(source, 30.0), (reading, 2, "abc")]


def test_repere_illisible_met_la_piece_en_erreur(
    modules: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(modules.shaped, "source_solid", lambda _obj: "RAW")

    def unreadable(_placement: Any) -> None:
        raise ValueError("x : vecteur unitaire attendu")

    monkeypatch.setattr(modules.shaped, "placement_axes", unreadable)
    part = with_proxy(modules, Label="Pied", SourceAxes=object())
    with pytest.raises(ValueError, match="repère de la pièce est illisible"):
        modules.shaped.shaped_form(part)


@pytest.mark.parametrize("extents", [(0.0, 50.0, 20.0), (720.0, 95.0, 0.05), (30_000.0, 5.0, 5.0)])
def test_cote_hors_bornes_met_la_piece_en_erreur(
    modules: Any, monkeypatch: pytest.MonkeyPatch, extents: tuple[float, float, float]
) -> None:
    monkeypatch.setattr(modules.shaped, "source_solid", lambda _obj: "RAW")
    monkeypatch.setattr(modules.shaped, "placement_axes", lambda _placement: "AXES")
    monkeypatch.setattr(
        modules.shaped,
        "local_form",
        lambda raw, axes: types.SimpleNamespace(shape=raw, frame=axes, extents=extents),
    )
    part = with_proxy(modules, Label="Pied", SourceAxes=object())
    with pytest.raises(ValueError, match="Cote invalide"):
        modules.shaped.shaped_form(part)


def test_forme_dans_le_repere_de_la_piece(modules: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    form = types.SimpleNamespace(shape="LOCAL", frame="F", extents=(720.0, 95.0, 45.0))
    monkeypatch.setattr(modules.shaped, "source_solid", lambda _obj: "RAW")
    monkeypatch.setattr(modules.shaped, "placement_axes", lambda _placement: "AXES")
    monkeypatch.setattr(modules.shaped, "local_form", lambda raw, axes: form)
    assert modules.shaped.shaped_form(with_proxy(modules, SourceAxes=object())) is form


def test_empreinte_de_forme_et_forme_de_base(modules: Any) -> None:
    shape = types.SimpleNamespace(
        Volume=1_234_567.0,
        Area=54_321.0,
        Faces=[1, 2, 3, 4, 5, 6],
        copy=lambda: types.SimpleNamespace(Placement="P"),
    )
    part = FakePart(Shape=shape)
    signature = modules.shaped.signature_of(part)
    assert (signature.volume, signature.area, signature.faces) == (1_235_000.0, 54_320.0, 6)
    assert modules.shaped.base_shape_of(part).Placement is not None


# --- Création (B1, B2, B11) -----------------------------------------------------------------


class Journal:
    """Événements dans l'ordre : écritures des objets créés et de la source."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []


class Created:
    """Pièce en cours de création, qui journalise ses écritures."""

    def __init__(self, journal: Journal, container: Any = None) -> None:
        object.__setattr__(self, "journal", journal)
        object.__setattr__(self, "container", container)
        object.__setattr__(self, "values", {})

    def __setattr__(self, name: str, value: Any) -> None:
        self.journal.events.append(("part", name))
        self.values[name] = value

    def __getattr__(self, name: str) -> Any:
        return object.__getattribute__(self, "values")[name]

    def getParentGeoFeatureGroup(self) -> None:  # nom imposé par FreeCAD
        return None


class Hideable(FakeSource):
    """Source dont la visibilité est journalisée."""

    def __init__(self, journal: Journal, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "journal", journal)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "Visibility" and hasattr(self, "journal"):
            self.journal.events.append(("source", name))
        object.__setattr__(self, name, value)


class FakeProxy:
    """``ShapedPart`` remplacé : enregistre le matériau choisi."""

    materials: ClassVar[list[Any]] = []

    def __init__(self, obj: Any) -> None:
        obj.Proxy = self

    def select_material(self, _obj: Any, material: Any) -> None:
        self.materials.append(material)

    def synchronizing(self) -> Any:
        return contextlib.nullcontext()

    def library(self) -> Any:
        return None


@pytest.fixture
def creation(modules: Any, monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """Création de pièces en bois avec tout ce qui touche à OCC remplacé."""
    journal = Journal()
    created: list[Created] = []
    containers: list[Any] = []
    FakeProxy.materials = []

    class Document:
        def addObject(self, type_id: str, name: str) -> Created:  # nom imposé par FreeCAD
            assert (type_id, name) == ("Part::FeaturePython", "ShapedPart")
            obj = Created(journal)
            created.append(obj)
            return obj

    library = types.SimpleNamespace(
        default_material=lambda: "DEFAULT",
        get=lambda identifier: {"chene": "CHENE"}[identifier],
    )
    create = modules.create
    monkeypatch.setattr(create, "get_library", lambda: library)
    monkeypatch.setattr(create, "ShapedPart", FakeProxy)
    monkeypatch.setattr(create, "automatic_axes", lambda _solid: ("AXES", False))
    monkeypatch.setattr(
        create,
        "local_form",
        lambda _solid, _axes: types.SimpleNamespace(
            shape="S", frame="FRAME", extents=(720.0, 95.0, 45.0)
        ),
    )
    monkeypatch.setattr(create, "axes_placement", lambda axes: f"placement({axes})")
    monkeypatch.setattr(create, "apply_editor_modes", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(create, "shows_grain", lambda *_args: True)
    monkeypatch.setattr(create, "is_profile", lambda _obj: False)
    monkeypatch.setattr(create, "label_of_mark", lambda _obj, mark: f"label:{mark}")
    monkeypatch.setattr(
        create, "container_of", lambda source: containers[0] if containers else None
    )
    monkeypatch.setattr(create, "_placement_of", lambda _obj, _source, frame: f"at({frame})")
    return types.SimpleNamespace(
        journal=journal, created=created, containers=containers, document=Document(), create=create
    )


def source_with(creation: types.SimpleNamespace, *volumes: float, **kwargs: Any) -> Hideable:
    source = Hideable(creation.journal, label="Corps", **kwargs)
    source.Document = creation.document
    source.reading = tuple(FakeSolid(volume) for volume in volumes)
    return source


@pytest.fixture
def reading(modules: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """``read_source`` rend les solides préparés sur la source simulée."""

    def read(source: Any, _thickness: float) -> Any:
        return modules.create.SourceReading(
            source, source.reading, profile=False, importable=len(source.reading) > 1
        )

    monkeypatch.setattr(modules.create, "read_source", read)


def test_creation_d_une_piece(creation: Any, reading: None) -> None:
    source = source_with(creation, 1000.0)
    [part] = creation.create.create_shaped_parts(source, material_id="chene", mark="P1")
    assert part is creation.created[0]
    assert FakeProxy.materials == ["CHENE"]
    assert part.Source is source
    assert part.SourceAxes == "placement(AXES)"
    assert (part.SolidIndex, part.SolidSignature) == (-1, "")
    assert (part.Length, part.Width, part.Thickness) == (720.0, 95.0, 45.0)
    assert part.Placement == "at(FRAME)"
    assert (part.Mark, part.Label) == ("P1", "label:P1")
    assert source.Visibility is False


def test_la_source_est_masquee_apres_la_liaison(creation: Any, reading: None) -> None:
    source = source_with(creation, 1000.0)
    creation.create.create_shaped_parts(source)
    events = creation.journal.events
    assert events.index(("part", "Source")) < events.index(("source", "Visibility"))
    assert events[-1] == ("source", "Visibility")
    assert events.count(("source", "Visibility")) == 1


def test_materiau_par_defaut(creation: Any, reading: None) -> None:
    creation.create.create_shaped_parts(source_with(creation, 1000.0))
    assert FakeProxy.materials == ["DEFAULT"]


def test_piece_rangee_dans_le_conteneur_de_la_source(creation: Any, reading: None) -> None:
    container = types.SimpleNamespace(added=[])
    container.addObject = container.added.append
    creation.containers.append(container)
    [part] = creation.create.create_shaped_parts(source_with(creation, 1000.0))
    assert container.added == [part]


def test_forme_importee_une_piece_par_solide(creation: Any, reading: None) -> None:
    source = source_with(creation, 100.0, 100.0, 250.0)
    parts = creation.create.create_shaped_parts(source, mark="V")
    assert [part.SolidIndex for part in parts] == [0, 1, 2]
    assert parts[0].SolidSignature == parts[1].SolidSignature != ""
    assert parts[0].SolidSignature != parts[2].SolidSignature
    assert {part.Source for part in parts} == {source}
    assert [part.Mark for part in parts] == ["V"] * 3
    assert creation.journal.events.count(("source", "Visibility")) == 1


def test_une_piece_refuse_plusieurs_solides(creation: Any, reading: None) -> None:
    source = source_with(creation, 100.0, 200.0)
    with pytest.raises(ValueError, match="2 solides"):
        creation.create.create_shaped_part(source)
    assert creation.created == []
    assert source.Visibility is True


def test_une_piece_a_un_seul_solide(creation: Any, reading: None) -> None:
    part = creation.create.create_shaped_part(source_with(creation, 100.0))
    assert part is creation.created[0]


def test_refus_de_la_source_ne_cree_rien(
    creation: Any, modules: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_source: Any, _thickness: float) -> None:
        raise TypeError("objet refusé")

    monkeypatch.setattr(creation.create, "read_source", refuse)
    source = source_with(creation, 1.0)
    with pytest.raises(TypeError, match="objet refusé"):
        creation.create.create_shaped_parts(source)
    assert creation.created == []
    assert creation.journal.events == []
    assert source.Visibility is True


def test_cote_hors_bornes_ne_cree_rien(
    creation: Any, reading: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        creation.create,
        "local_form",
        lambda _solid, _axes: types.SimpleNamespace(shape="S", frame="F", extents=(0.0, 5.0, 5.0)),
    )
    source = source_with(creation, 1.0)
    with pytest.raises(ValueError, match="Cote invalide"):
        creation.create.create_shaped_parts(source)
    assert creation.created == []
    assert source.Visibility is True


def test_materiau_inconnu_ne_cree_rien(creation: Any, reading: None) -> None:
    source = source_with(creation, 1.0)
    with pytest.raises(KeyError):
        creation.create.create_shaped_parts(source, material_id="inconnu")
    assert creation.created == []
    assert source.Visibility is True


def test_source_deja_convertie_refusee(creation: Any, modules: Any, reading: None) -> None:
    source = source_with(creation, 1.0)
    existing = FakePart(Label="Pied", Source=source)
    existing.props["Proxy"] = shaped_proxy(modules)
    source.InList.append(existing)
    with pytest.raises(ValueError, match="« Corps » est déjà la forme d'une pièce en bois"):
        creation.create.create_shaped_parts(source)
    assert creation.created == []
    assert source.Visibility is True
    assert creation.create.converted_part_of(source) is existing


def test_source_non_convertie(creation: Any, modules: Any) -> None:
    source = source_with(creation, 1.0)
    source.InList.append(FakePart(Source=source))  # un lien qui n'est pas une pièce en bois
    other = with_proxy(modules, Source=FakeSource())
    source.InList.append(other)
    assert creation.create.converted_part_of(source) is None


def test_forme_trop_detaillee_avertit(
    creation: Any, modules: Any, reading: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(creation.create, "automatic_axes", lambda _solid: ("AXES", True))
    creation.create.create_shaped_parts(source_with(creation, 1.0))
    [warning] = modules.report
    assert "forme trop détaillée" in warning
    assert "« Corps »" in warning


# --- API ------------------------------------------------------------------------------------


class Recompute:
    def __init__(self) -> None:
        self.count = 0

    def recompute(self) -> None:
        self.count += 1


def test_api_make_shaped_part(modules: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    document = Recompute()
    part = types.SimpleNamespace(Document=document)
    calls: list[dict[str, Any]] = []

    def create(source: Any, **kwargs: Any) -> Any:
        calls.append({"source": source, **kwargs})
        return part

    monkeypatch.setattr(modules.api, "create_shaped_part", create)
    monkeypatch.setattr(modules.api.App, "GuiUp", False, raising=False)
    assert modules.api.make_shaped_part("SRC", "chene", "P1") is part
    assert calls == [
        {"source": "SRC", "material_id": "chene", "mark": "P1", "profile_thickness": 22.0}
    ]
    assert document.count == 1
    modules.api.make_shaped_part("SRC", profile_thickness=30.0)
    assert calls[1] == {"source": "SRC", "material_id": None, "mark": "", "profile_thickness": 30.0}


def test_api_make_shaped_parts(modules: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    document = Recompute()
    parts = [types.SimpleNamespace(Document=document), types.SimpleNamespace(Document=document)]
    monkeypatch.setattr(modules.api, "create_shaped_parts", lambda _source, **_kwargs: parts)
    monkeypatch.setattr(modules.api.App, "GuiUp", False, raising=False)
    source = types.SimpleNamespace(Document=document)
    assert modules.api.make_shaped_parts(source) == parts
    assert document.count == 1


def test_api_reset_shaped_axes(modules: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    document = Recompute()
    part = with_proxy(modules)
    object.__setattr__(part, "Document", document)
    reset: list[Any] = []
    monkeypatch.setattr(modules.api, "reset_axes", reset.append)
    modules.api.reset_shaped_axes(part)
    assert reset == [part]
    assert document.count == 1


def test_api_reset_refuse_un_objet_qui_n_est_pas_une_piece_en_bois(modules: Any) -> None:
    with pytest.raises(TypeError, match="« Planche » n'est pas une pièce en bois"):
        modules.api.reset_shaped_axes(FakePart(Label="Planche"))


def test_viewprovider_absent_sans_interface(modules: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modules.api.App, "GuiUp", False, raising=False)
    modules.api._show_shaped([FakePart()])  # sans interface (freecadcmd) : aucun ViewProvider
