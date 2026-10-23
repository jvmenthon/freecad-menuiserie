# SPDX-License-Identifier: LGPL-2.1-or-later
"""Robustesse de la pièce de bois (issue #13, J2a : critères D8, R1, R2), sur des objets simulés.
L'objet réel, la réouverture d'un fichier et le panneau sont vérifiés par
``tests/integration/test_suites_revue_j1b.py`` et ``tests/gui/verifications_robustesse.py``."""

from __future__ import annotations

import types
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.materials import MaterialLibrary, load_library
from tests.unit.aides_freecad import simulated_freecad

LIBRARY: MaterialLibrary = load_library(DATA_DIR / "materiaux.json", None)[0]
HOSTILE = "Futur\n‮" + "x" * 80
MODES = {0: [], 1: ["ReadOnly"], 2: ["Hidden"]}


class FakePart:
    """Pièce de bois minimale : propriétés dans un dictionnaire, modes d'édition mémorisés."""

    def __init__(self, **props: Any) -> None:
        self.props = {"Label": "M1", **props}
        self.State: list[str] = []
        self.Document = types.SimpleNamespace(Transacting=False)
        self.modes: dict[str, list[str]] = {}

    @property
    def PropertiesList(self) -> list[str]:  # nom imposé par FreeCAD
        return list(self.props)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.__dict__["props"][name]
        except KeyError:
            raise AttributeError(name) from None

    def getEditorMode(self, name: str) -> list[str]:
        return self.modes.get(name, [])

    def setEditorMode(self, name: str, mode: int) -> None:
        self.modes[name] = MODES[mode]


def solid(**props: Any) -> FakePart:
    """Pièce en chêne, version courante, lisible par ``record_of``."""
    values: dict[str, Any] = {
        "Mark": "M1",
        "MaterialId": "chene",
        "Material": "Chêne",
        "Category": "Solid",
        "GrainDirection": "Length",
        "Version": 2,
        "Length": types.SimpleNamespace(Value=800.0),
        "Width": types.SimpleNamespace(Value=200.0),
        "Thickness": types.SimpleNamespace(Value=22.0),
        "LengthAllowance": types.SimpleNamespace(Value=10.0),
        "WidthAllowance": types.SimpleNamespace(Value=5.0),
        "ThicknessAllowance": types.SimpleNamespace(Value=2.0),
        "Density": types.SimpleNamespace(getValueAs=lambda _unit: 710.0),
    }
    return FakePart(**{**values, **props})


@pytest.fixture
def modules(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.SimpleNamespace]:
    """``wood_part``, ``wood_part_restore`` et ``wood_part_schema`` sur un FreeCAD simulé, avec
    la bibliothèque intégrée et la langue française."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import wood_part, wood_part_restore, wood_part_schema

        for module in (wood_part, wood_part_restore):
            monkeypatch.setattr(module, "get_library", lambda: LIBRARY, raising=False)
            monkeypatch.setattr(module, "display_language", lambda: "fr")
        yield types.SimpleNamespace(
            wood=wood_part, restore=wood_part_restore, schema=wood_part_schema
        )


def bare_proxy(modules: Any) -> Any:
    """Proxy ``WoodPart`` sans objet (``__init__`` n'est pas rappelé à la réouverture)."""
    return modules.wood.WoodPart.__new__(modules.wood.WoodPart)


# --- D8 : pièce illisible -> UnsupportedPartError traduite ---------------------------------


def test_record_of_lit_une_piece_connue(modules: Any) -> None:
    record = modules.wood.record_of(solid())
    assert (record.material_id, record.kind.value, record.grain.value) == (
        "chene",
        "solid",
        "Length",
    )
    assert record.density == 710.0


@pytest.mark.parametrize("prop", ["Category", "GrainDirection"])
def test_record_of_valeur_inconnue_leve_une_erreur_traduite(modules: Any, prop: str) -> None:
    part = solid(Version=3, Label=HOSTILE, **{prop: HOSTILE})
    with pytest.raises(modules.wood.UnsupportedPartError) as caught:
        modules.wood.record_of(part)
    assert not isinstance(caught.value, KeyError)
    message = str(caught.value)
    assert f"inconnue pour {prop}" in message
    assert "\n" not in message
    assert "‮" not in message
    assert len(message) < 400


# --- R1 : pièce d'un document plus récent ---------------------------------------------------


@pytest.mark.parametrize(
    ("props", "expected"),
    [({}, False), ({"Version": 2}, False), ({"Version": 3}, True), ({"Version": "x"}, False)],
    ids=["absente", "courante", "plus-recente", "illisible"],
)
def test_version_plus_recente_detectee(modules: Any, props: dict[str, Any], expected: bool) -> None:
    assert modules.schema.is_from_newer_version(FakePart(**props)) is expected


def follow_material_choice(modules: Any, part: FakePart) -> list[str]:
    """Identifiants des matériaux que ``onChanged("Material")`` sélectionne."""
    chosen: list[str] = []
    proxy = bare_proxy(modules)
    proxy.select_material = lambda _obj, material: chosen.append(material.id)
    proxy.onChanged(part, "Material")
    return chosen


def test_choix_du_materiau_suivi_hors_document_plus_recent(modules: Any) -> None:
    assert follow_material_choice(modules, solid(Material="MDF")) == ["mdf"]


def test_choix_du_materiau_ignore_dans_un_document_plus_recent(modules: Any) -> None:
    assert follow_material_choice(modules, solid(Material="MDF", Version=3)) == []


def test_select_material_refuse_dans_un_document_plus_recent(modules: Any) -> None:
    part = solid(Version=3, Label=HOSTILE)
    with pytest.raises(modules.wood.UnsupportedPartError, match="plus récente"):
        bare_proxy(modules).select_material(part, LIBRARY.get("mdf"))
    assert (part.MaterialId, part.Material, part.Category) == ("chene", "Chêne", "Solid")


def test_select_material_valeur_inconnue_n_ecrit_rien(modules: Any) -> None:
    part = solid(Category=HOSTILE)
    with pytest.raises(modules.wood.UnsupportedPartError, match="inconnue pour Category"):
        bare_proxy(modules).select_material(part, LIBRARY.get("mdf"))
    assert (part.MaterialId, part.Material) == ("chene", "Chêne")


def test_modes_d_edition_du_materiau(modules: Any) -> None:
    part = solid()
    modules.schema.apply_editor_modes(part, material_read_only=True)
    assert part.modes["Material"] == ["ReadOnly"]
    assert part.modes["MaterialId"] == ["ReadOnly"]
    modules.schema.apply_editor_modes(part)
    assert part.modes["Material"] == []


# --- R2 : matériau de la réparation retrouvé d'après le libellé ----------------------------

ABSENT = None


@pytest.mark.parametrize(
    ("props", "expected"),
    [
        ({}, "chene"),
        ({"MaterialId": ABSENT, "Material": "MDF"}, "mdf"),
        ({"MaterialId": ABSENT, "Material": "Inconnu"}, "chene"),
        ({"MaterialId": ABSENT, "Material": ABSENT}, "chene"),
        ({"MaterialId": ABSENT, "Material": 7}, "chene"),
        ({"MaterialId": "disparu", "Material": "MDF"}, "chene"),
        ({"MaterialId": "cp-bouleau", "Material": "MDF"}, "cp-bouleau"),
    ],
    ids=[
        "id",
        "libelle",
        "libelle-inconnu",
        "sans-libelle",
        "libelle-illisible",
        "id-inconnu",
        "id-2",
    ],
)
def test_materiau_de_la_reparation(modules: Any, props: dict[str, Any], expected: str) -> None:
    part = FakePart(MaterialId="chene", Material="Chêne")
    for name, value in props.items():
        if value is ABSENT:
            del part.props[name]
        else:
            part.props[name] = value
    assert modules.restore.migration_material(part, LIBRARY).id == expected
