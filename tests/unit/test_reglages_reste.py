# SPDX-License-Identifier: LGPL-2.1-or-later
"""Reste des réglages de l'atelier, lot CA-d (ADR 0069, spécification § 7) : sens du fil, taquets,
caisson, pas de rotation, panneau « Structure », liste de débit et format des plans.

Un réglage qui influence un document est copié dans l'objet à sa création et jamais relu ensuite ;
un réglage d'interface est lu à l'usage. Sans réglage modifié, le comportement est celui d'avant.
"""

from __future__ import annotations

import ast
import importlib
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core.cutlist import DEFAULT_MARK_PREFIX
from freecad.menuiserie.core.drawing import DEFAULT_FORMAT, PAGE_FORMATS
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.shelf_pins import (
    AUTO_DEPTH_MM,
    AUTO_DIAMETER_MM,
    ShelfPinsParams,
)
from freecad.menuiserie.core.rotation import DEFAULT_STEP_DEGREES, snapped_turn
from freecad.menuiserie.core.structure_autostart import should_open_by_default
from freecad.menuiserie.core.templates.carcass import CarcassParams
from freecad.menuiserie.kit.config.catalog import Kind, SettingError
from tests.unit.aides import ROOT
from tests.unit.aides_reglages import settings_module

GUI = ROOT / "freecad" / "menuiserie" / "gui"


class Modules:
    """Modules de ``features`` importés avec le FreeCAD simulé, au-dessus des réglages."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.values = config.settings()
        self.part: Any = importlib.import_module("freecad.menuiserie.features.new_part_settings")
        self.joint: Any = importlib.import_module("freecad.menuiserie.features.joint_settings")
        self.template: Any = importlib.import_module(
            "freecad.menuiserie.features.template_settings"
        )
        self.interface: Any = importlib.import_module(
            "freecad.menuiserie.features.interface_settings"
        )
        self.marks: Any = importlib.import_module("freecad.menuiserie.features.cutlist_marks")
        self.export: Any = importlib.import_module("freecad.menuiserie.features.cutlist_export")
        self.drawing: Any = importlib.import_module("freecad.menuiserie.features.drawing_settings")


@pytest.fixture
def modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Modules]:
    with settings_module(monkeypatch, tmp_path) as config:
        yield Modules(config)


def _quantity(value: float) -> Any:
    return types.SimpleNamespace(Value=value)


# --- catalogue ------------------------------------------------------------------------------


def test_valeurs_par_defaut_celles_du_code(modules: Modules) -> None:
    config, values = modules.config, modules.values
    carcass = CarcassParams()
    expected = {
        config.GRAIN: config.GRAIN_AUTO,
        config.SHELF_PIN_PITCH: ShelfPinsParams().pitch,
        config.SHELF_PIN_DIAMETER: AUTO_DIAMETER_MM,
        config.SHELF_PIN_DEPTH: AUTO_DEPTH_MM,
        config.MARK_PREFIX: DEFAULT_MARK_PREFIX,
        config.CUTLIST_EXPORT_FOLDER: "",
        config.DRAWING_FORMAT: DEFAULT_FORMAT,
        config.ROTATION_STEP: DEFAULT_STEP_DEGREES,
        config.STRUCTURE_AUTO_OPEN: True,
        **{key: getattr(carcass, name) for name, key in config.CARCASS_FIELDS.items()},
    }
    assert {key: values.value(key) for key in expected} == expected
    assert (values.value(config.SHELF_PIN_PITCH), AUTO_DIAMETER_MM, AUTO_DEPTH_MM) == (32.0, 5, 12)
    assert (DEFAULT_STEP_DEGREES, DEFAULT_FORMAT) == (15.0, "A3")


def test_groupes_et_choix_du_lot(modules: Modules) -> None:
    config = modules.config
    groups = {
        config.GRAIN: config.NEW_PARTS,
        config.SHELF_PIN_PITCH: config.SHELF_PINS,
        config.CARCASS_FIELDS["width"]: config.TEMPLATES,
        config.MARK_PREFIX: config.CUTLIST,
        config.CUTLIST_EXPORT_FOLDER: config.CUTLIST,
        config.DRAWING_FORMAT: config.DRAWINGS,
        config.ROTATION_STEP: config.DISPLAY,
        config.STRUCTURE_AUTO_OPEN: config.DISPLAY,
    }
    for key, group in groups.items():
        assert config.CATALOG.get(key).group == group, key
    assert config.CATALOG.get(config.CUTLIST_EXPORT_FOLDER).kind is Kind.PATH
    assert config.CATALOG.get(config.DRAWING_FORMAT).choices == tuple(PAGE_FORMATS)
    assert config.CATALOG.get(config.GRAIN).choices == (config.GRAIN_AUTO, "Length", "Width")
    assert all(not s.advanced for s in config.CATALOG)


def test_dernier_utilise_seulement_pour_les_valeurs_proposees(modules: Modules) -> None:
    config = modules.config
    for key in (
        config.SHELF_PIN_PITCH,
        config.SHELF_PIN_DIAMETER,
        config.SHELF_PIN_DEPTH,
        config.DRAWING_FORMAT,
        *config.CARCASS_FIELDS.values(),
    ):
        assert config.CATALOG.get(key).remember_last, key
    for key in (
        config.GRAIN,
        config.MARK_PREFIX,
        config.CUTLIST_EXPORT_FOLDER,
        config.ROTATION_STEP,
        config.STRUCTURE_AUTO_OPEN,
    ):
        assert not config.CATALOG.get(key).remember_last, key


def test_bornes_des_nouveaux_reglages(modules: Modules) -> None:
    config, values = modules.config, modules.values
    bounds = {
        config.ROTATION_STEP: (1.0, 90.0),
        config.SHELF_PIN_DIAMETER: (1.0, 30.0),
        config.SHELF_PIN_DEPTH: (1.0, 100.0),
        config.SHELF_PIN_PITCH: (3.0, 200.0),
        config.CARCASS_FIELDS["thickness"]: (0.1, 300.0),
    }
    for key, (low, high) in bounds.items():
        assert values.set(key, low) == low
        assert values.set(key, high) == high
        for bad in (low - 0.01, high + 0.01, 0.0, float("nan")):
            with pytest.raises(SettingError):
                values.set(key, bad)
    with pytest.raises(SettingError):
        values.set(config.DRAWING_FORMAT, "A5")
    with pytest.raises(SettingError):
        values.set(config.GRAIN, "None")  # « sans fil » n'est pas un choix de l'atelier


def test_valeur_abimee_redonne_le_defaut(modules: Modules) -> None:
    config, values = modules.config, modules.values
    modules.config.group.SetString(config.DRAWING_FORMAT, "Z9")
    modules.config.group.SetFloat(config.ROTATION_STEP, 0.0)
    modules.config.group.SetString(config.GRAIN, "Diagonal")
    assert values.value(config.DRAWING_FORMAT) == "A3"
    assert values.value(config.ROTATION_STEP) == 15.0
    assert values.value(config.GRAIN) == config.GRAIN_AUTO


# --- sens du fil ------------------------------------------------------------------------------


def _grained(direction: str = "Length") -> Any:
    return types.SimpleNamespace(GrainDirection=direction)


def test_fil_automatique_ne_change_rien(modules: Modules) -> None:
    part = _grained()
    modules.part.apply_new_grain(part)
    assert part.GrainDirection == "Length"


def test_fil_de_l_atelier_copie_dans_la_piece_neuve(modules: Modules) -> None:
    modules.values.set(modules.config.GRAIN, "Width")
    part = _grained()
    modules.part.apply_new_grain(part)
    assert part.GrainDirection == "Width"
    modules.values.set(modules.config.GRAIN, "Length")  # réglage changé après coup
    assert part.GrainDirection == "Width"  # la pièce existante garde son sens


def test_fil_de_l_atelier_ignore_une_piece_sans_fil(modules: Modules) -> None:
    modules.values.set(modules.config.GRAIN, "Width")
    panel = _grained("None")
    modules.part.apply_new_grain(panel)
    assert panel.GrainDirection == "None"


def test_page_donne_un_libelle_a_chaque_choix_du_fil(modules: Modules) -> None:
    """``GRAIN_CHOICES`` de la page reprend, dans l'ordre, les valeurs du catalogue."""
    tree = ast.parse((GUI / "preferences_page.py").read_text(encoding="utf-8"))
    assigned = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "GRAIN_CHOICES"
    )
    assert isinstance(assigned, ast.Tuple)
    values = [ast.unparse(pair.elts[0]) for pair in assigned.elts if isinstance(pair, ast.Tuple)]
    assert values == ["GRAIN_AUTO", "'Length'", "'Width'"]
    assert modules.config.CATALOG.get(modules.config.GRAIN).choices == (
        modules.config.GRAIN_AUTO,
        "Length",
        "Width",
    )


# --- taquets ----------------------------------------------------------------------------------


def test_taquets_sans_reglage_modifie_comme_avant(modules: Modules) -> None:
    assert modules.joint.apply_joint_settings(JointKind.SHELF_PINS, {}) == {}


def test_taquets_reglages_modifies_copies_a_la_creation(modules: Modules) -> None:
    config, values = modules.config, modules.values
    values.set(config.SHELF_PIN_PITCH, 25.0)
    values.set(config.SHELF_PIN_DIAMETER, 6.0)
    values.set(config.SHELF_PIN_DEPTH, 10.0)
    apply = modules.joint.apply_joint_settings
    assert apply(JointKind.SHELF_PINS, {}) == {
        "pitch": 25.0,
        "hole_diameter": 6.0,
        "hole_depth": 10,
    }
    given = apply(JointKind.SHELF_PINS, {"pitch": 32.0})
    assert given["pitch"] == 32.0 and given["hole_diameter"] == 6.0  # l'appelant l'emporte
    values.set(config.SHELF_PIN_PITCH, 40.0)  # changé après coup : rien n'est relu
    assert given["pitch"] == 32.0


def test_fabrique_des_taquets_applique_les_reglages(
    modules: Modules, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``create_shelf_pins`` : réglage modifié donné au perçage, pièce voisine non cherchée."""
    factories = importlib.import_module("freecad.menuiserie.features.joints.factories")
    created: list[Any] = []

    def capture(
        _joint_class: Any, _doc: Any, _host: Any, _guest: Any, params: Any, **_: Any
    ) -> Any:
        created.append(params)
        return types.SimpleNamespace(Neighbors=[])

    monkeypatch.setattr(factories, "create_joint", capture)
    monkeypatch.setattr(factories, "blank_of", lambda part: part)
    monkeypatch.setattr(factories, "timber_blanks_around", lambda _part: [])
    factories.create_shelf_pins("doc", "cote", both_sides=False)
    assert (created[0].pitch, created[0].hole_diameter, created[0].hole_depth) == (32.0, 0.0, 0.0)
    modules.values.set(modules.config.SHELF_PIN_DIAMETER, 6.0)
    factories.create_shelf_pins("doc", "cote", both_sides=False)
    assert created[1].hole_diameter == 6.0 and created[1].hole_depth == 0.0


def test_dernier_utilise_des_taquets(modules: Modules) -> None:
    config, values = modules.config, modules.values
    shelf_pins = importlib.import_module("freecad.menuiserie.features.joints.shelf_pins")
    joint = types.SimpleNamespace(
        Proxy=object.__new__(shelf_pins.ShelfPinsJoint),
        Pitch=_quantity(25.0),
        HoleDiameter=_quantity(0.0),  # automatique : refusé par le réglage, ignoré
        HoleDepth=_quantity(10.0),
    )
    values.set_remember_last(config.SHELF_PIN_PITCH, True)
    values.set_remember_last(config.SHELF_PIN_DIAMETER, True)
    modules.joint.record_joint_used(joint)
    assert values.value(config.SHELF_PIN_PITCH) == 25.0
    assert values.value(config.SHELF_PIN_DIAMETER) == AUTO_DIAMETER_MM
    assert values.value(config.SHELF_PIN_DEPTH) == AUTO_DEPTH_MM  # case non cochée


# --- caisson ----------------------------------------------------------------------------------


def test_caisson_propose_les_valeurs_du_noyau_sans_reglage(modules: Modules) -> None:
    proposals = modules.template.carcass_proposals()
    assert set(proposals) == {
        "width",
        "depth",
        "height",
        "thickness",
        "back_thickness",
        "rabbet_depth",
    }
    carcass = CarcassParams()
    assert proposals == {name: getattr(carcass, name) for name in proposals}
    assert CarcassParams(**proposals) == carcass


def test_caisson_propose_les_valeurs_de_l_atelier(modules: Modules) -> None:
    config, values = modules.config, modules.values
    values.set(config.CARCASS_FIELDS["width"], 800.0)
    values.set(config.CARCASS_FIELDS["rabbet_depth"], 12.0)
    proposals = modules.template.carcass_proposals()
    assert (proposals["width"], proposals["rabbet_depth"], proposals["height"]) == (800, 12, 720)
    assert CarcassParams(**proposals).width == 800.0
    assert CarcassParams().width == 600.0  # l'API reste sur les valeurs de ``core``
    values.set(config.CARCASS_FIELDS["width"], 900.0)  # changé après coup
    assert proposals["width"] == 800.0  # un formulaire déjà ouvert garde ce qu'il a reçu


def test_caisson_dernier_utilise_a_la_validation(modules: Modules) -> None:
    config, values = modules.config, modules.values
    chosen = {"width": 700.0, "depth": 350.0, "shelf_count": 3, "material_id": "x"}
    modules.template.record_carcass_used(chosen)
    assert values.value(config.CARCASS_FIELDS["width"]) == 600.0  # case non cochée
    values.set_remember_last(config.CARCASS_FIELDS["width"], True)
    modules.template.record_carcass_used(chosen)
    assert values.value(config.CARCASS_FIELDS["width"]) == 700.0
    assert values.value(config.CARCASS_FIELDS["depth"]) == 400.0  # non cochée
    assert values.value(config.CARCASS_FIELDS["height"]) == 720.0  # champ absent : ignoré
    modules.template.record_carcass_used({"width": -5.0})  # valeur refusée : ignorée
    assert values.value(config.CARCASS_FIELDS["width"]) == 700.0


def test_formulaire_du_caisson_utilise_les_propositions() -> None:
    source = (GUI / "task_panels" / "carcass.py").read_text(encoding="utf-8")
    assert "carcass_proposals()" in source and "record_carcass_used(" in source
    assert "def _before_commit" in source  # saisies lues avant la fermeture du formulaire


# --- pas de rotation --------------------------------------------------------------------------


def test_pas_de_rotation_lu_a_l_usage(modules: Modules) -> None:
    assert modules.interface.rotation_step() == 15.0
    modules.values.set(modules.config.ROTATION_STEP, 45.0)
    assert modules.interface.rotation_step() == 45.0
    assert snapped_turn(0.0, 40.0, modules.interface.rotation_step()) == 45.0
    assert snapped_turn(0.0, 20.0) == 15.0  # pas habituel
    assert snapped_turn(0.0, 20.0, 45.0) == 0.0


def test_rotation_a_la_souris_relit_le_pas_a_chaque_geste() -> None:
    source = (GUI / "drag" / "states.py").read_text(encoding="utf-8")
    assert "self.step = rotation_step()" in source
    assert "snapped_turn(self.base, self.total, self.step, free=self.shift)" in source


# --- panneau Structure ------------------------------------------------------------------------


def test_panneau_structure_ouverture_reglee(modules: Modules) -> None:
    assert modules.interface.structure_auto_open() is True
    modules.values.set(modules.config.STRUCTURE_AUTO_OPEN, False)
    assert modules.interface.structure_auto_open() is False
    modules.values.set(modules.config.STRUCTURE_AUTO_OPEN, True)
    assert modules.interface.structure_auto_open() is True


@pytest.mark.parametrize("closed", [False, True])
@pytest.mark.parametrize("exists", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_ouverture_automatique_du_panneau(closed: bool, exists: bool, enabled: bool) -> None:
    result = should_open_by_default(closed_by_user=closed, exists=exists, enabled=enabled)
    assert result is (enabled and not closed and not exists)
    assert should_open_by_default(closed_by_user=closed, exists=exists) is (
        not closed and not exists
    )


def test_ouverture_du_panneau_lit_le_reglage() -> None:
    source = (GUI / "structure_panel.py").read_text(encoding="utf-8")
    assert "enabled=structure_auto_open()" in source


# --- liste de débit ---------------------------------------------------------------------------


def test_prefixe_des_reperes(modules: Modules) -> None:
    assert modules.interface.mark_prefix() == "M"
    modules.values.set(modules.config.MARK_PREFIX, "  P-")
    assert modules.interface.mark_prefix() == "P-"
    modules.values.set(modules.config.MARK_PREFIX, "   ")
    assert modules.interface.mark_prefix() == "M"  # vide : « M »
    modules.values.set(modules.config.MARK_PREFIX, "")
    assert modules.interface.mark_prefix() == "M"


class _Document:
    """Document minimal : transactions et objets nommés ``a`` et ``b``."""

    def __init__(self) -> None:
        self.objects = {name: types.SimpleNamespace(Mark="") for name in "ab"}
        self.opened: list[str] = []

    def getObject(self, name: str) -> Any:
        return self.objects[name]

    def openTransaction(self, name: str) -> None:
        self.opened.append(name)

    def commitTransaction(self) -> None:
        pass

    def recompute(self) -> None:
        pass


def test_numerotation_ecrit_le_prefixe_de_l_atelier_puis_ne_le_relit_pas(
    modules: Modules, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefixes: list[str] = []

    def plan(_doc: Any, _objects: Any, prefix: str) -> dict[str, str]:
        prefixes.append(prefix)
        return {"a": f"{prefix}1", "b": f"{prefix}2"}

    monkeypatch.setattr(modules.marks, "_plan", plan)
    doc = _Document()
    assert modules.marks.number_marks(doc) == {"a": "M1", "b": "M2"}
    modules.values.set(modules.config.MARK_PREFIX, "P")
    assert modules.marks.number_marks(doc) == {"a": "P1", "b": "P2"}
    assert doc.objects["a"].Mark == "P1"
    modules.values.set(modules.config.MARK_PREFIX, "Z")  # changé après coup
    assert doc.objects["a"].Mark == "P1"  # le repère écrit ne change pas
    assert modules.marks.number_marks(doc, prefix="Q") == {"a": "Q1", "b": "Q2"}  # l'appelant gagne
    assert prefixes == ["M", "P", "Q"]
    with pytest.raises(ValueError, match="préfixe"):
        modules.marks.number_marks(doc, prefix="  ")


def test_dossier_d_export_lu_a_l_usage(modules: Modules, tmp_path: Path) -> None:
    config, values = modules.config, modules.values
    assert modules.interface.export_folder() is None
    values.set(config.CUTLIST_EXPORT_FOLDER, str(tmp_path / "debits"))
    assert modules.interface.export_folder() == tmp_path / "debits"
    values.set(config.CUTLIST_EXPORT_FOLDER, "")
    assert modules.interface.export_folder() is None
    modules.config.group.SetString(config.CUTLIST_EXPORT_FOLDER, "relatif/dossier")
    assert modules.interface.export_folder() is None  # un chemin relatif est ignoré


def test_chemin_d_export_propose(modules: Modules, tmp_path: Path) -> None:
    proposed = modules.export.proposed_path
    document = tmp_path / "meubles" / "bureau.FCStd"
    beside = proposed("bureau", str(document))
    assert beside.parent == document.parent  # sans réglage : à côté du document
    assert proposed("bureau", str(document), folder=tmp_path / "debits") == (
        tmp_path / "debits" / beside.name
    )
    assert proposed("Sans nom", "", home=tmp_path, folder=tmp_path / "x").parent == tmp_path / "x"
    assert proposed("Sans nom", "", home=tmp_path).parent == tmp_path


def test_boite_d_export_demande_le_dossier_reglage() -> None:
    source = (GUI / "commands" / "cutlist.py").read_text(encoding="utf-8")
    assert source.count("folder=export_folder()") == 2  # CSV et PDF


# --- plans cotés ------------------------------------------------------------------------------


def test_format_de_feuille_des_plans(modules: Modules) -> None:
    config, values = modules.config, modules.values
    assert modules.drawing.default_format() == "A3"
    assert modules.drawing.DrawingOptions().resolved_format() == "A3"
    values.set(config.DRAWING_FORMAT, "A4")
    assert modules.drawing.default_format() == "A4"
    assert modules.drawing.DrawingOptions().resolved_format() == "A4"
    assert modules.drawing.DrawingOptions(page_format="A2").resolved_format() == "A2"
    config.group.SetString(config.DRAWING_FORMAT, "Z9")  # modifié à la main : le défaut
    assert modules.drawing.default_format() == "A3"
    assert modules.drawing.PAGE_FORMAT == "DrawingPageFormat"  # clé historique conservée


def test_format_des_plans_dernier_utilise(modules: Modules) -> None:
    config, values = modules.config, modules.values
    assert not modules.drawing.record_format("A1")  # case non cochée
    assert values.value(config.DRAWING_FORMAT) == "A3"
    values.set_remember_last(config.DRAWING_FORMAT, True)
    assert modules.drawing.record_format("A1")
    assert values.value(config.DRAWING_FORMAT) == "A1"
    assert not modules.drawing.record_format("A9")  # format inconnu : ignoré
    assert values.value(config.DRAWING_FORMAT) == "A1"


def test_panneau_des_plans_retient_le_format() -> None:
    source = (GUI / "task_panels" / "drawing.py").read_text(encoding="utf-8")
    assert "drawing_settings.record_format(" in source
