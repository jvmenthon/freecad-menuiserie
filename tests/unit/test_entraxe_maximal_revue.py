# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revue testeur de l'entraxe maximal (ADR 0070) : limites, obliques, gabarits, reliquats."""

from __future__ import annotations

import contextlib
import importlib
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import JointError
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.dowels import (
    MAX_DOWEL_COUNT,
    DowelParams,
    auto_count,
    positions,
)
from freecad.menuiserie.core.joints.slots import SlotParams
from freecad.menuiserie.core.joints.slots._params import AUTO_SPACING_MM
from freecad.menuiserie.core.joints.slots._strategy import LooseTenonStrategy
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM
from freecad.menuiserie.core.templates.carcass import dowel_params
from tests.unit.aides_assemblages import block
from tests.unit.aides_biais import stile_block, tilted_rail
from tests.unit.aides_reglages import settings_module
from tests.unit.test_entraxe_maximal import boards

ROOT = Path(__file__).resolve().parents[2]
DOWELS = strategy_for(JointKind.DOWELS)
TENON = LooseTenonStrategy()


def _auto_count(width: float, edge: float, along: float, max_spacing: float) -> int:
    """Nombre de mortaises d'un contact de ``width`` (planche de 22 mm de large 100)."""
    size = (width, 100.0, 22.0)
    host, guest = block(size), block(size, (0.0, 100.0, 0.0))
    params = SlotParams(max_spacing=max_spacing, edge_distance=edge)
    return TENON.resolve(host, guest, params).count


@pytest.mark.parametrize("max_spacing", [10.0, 33.3, 60.0, 70.1, 128.0, 150.0, 1000.0])
@pytest.mark.parametrize("pitches", [1, 2, 3, 7, 12, 20])
def test_entraxe_reel_jamais_au_dessus_du_maximum(max_spacing: float, pitches: int) -> None:
    """Contact dont la portée est un multiple exact de l'entraxe : pas d'arrondi qui ajoute un
    écart de trop (tourillons ; mortaises quand le contact tient dans les cotes admises)."""
    edge = 17.3
    width = pitches * max_spacing + 2 * edge
    counts = [auto_count(width, edge, 1.0, max_spacing)]
    if 50.0 <= width <= MAX_DIMENSION_MM:
        with contextlib.suppress(JointError):  # entraxe plus court que la mortaise : refusé
            counts.append(_auto_count(width, edge, 1.0, max_spacing))
    for count in counts:
        assert count <= MAX_DOWEL_COUNT
        if count > 1:
            assert (width - 2 * edge) / (count - 1) <= max_spacing * (1 + 1e-9)


@pytest.mark.parametrize("max_spacing", [10.0, 20.0])
def test_tres_long_contact_borne_a_cinquante(max_spacing: float) -> None:
    assert auto_count(1e6, 20.0, 8.0, max_spacing) == MAX_DOWEL_COUNT
    assert _auto_count(MAX_DIMENSION_MM, 20.0, 8.0, max_spacing) == MAX_DOWEL_COUNT


def test_nombre_minimal_deux_ou_un() -> None:
    assert auto_count(300.0, 16.0, 8.0, 1000.0) == 2
    assert _auto_count(300.0, 50.0, 12.0, 1000.0) == 2
    assert auto_count(30.0, 16.0, 8.0, 100.0) == 1
    assert len(positions(30.0, 16.0, 1)) == 1


@pytest.mark.parametrize("degrees", [5.0, 10.0, 30.0])
@pytest.mark.parametrize("max_spacing", [0.0, 30.0, 60.0, 1000.0])
def test_tourillons_en_biais_suivent_l_entraxe(degrees: float, max_spacing: float) -> None:
    host, guest = stile_block(), tilted_rail(degrees)
    values = DOWELS.resolve(host, guest, DowelParams(max_spacing=max_spacing))
    straight = DOWELS.resolve(host, tilted_rail(0.0), DowelParams(max_spacing=max_spacing))
    plan = DOWELS.plan(host, guest, DowelParams(max_spacing=max_spacing))
    assert values.count == straight.count == len(plan.inserts) == len(plan.host_cuts)
    if values.count > 1:
        assert values.spacing <= (max_spacing or 128.0) * (1 + 1e-9) or values.count == 50


def test_recalcul_apres_chaque_modification() -> None:
    """Un entraxe plus petit donne plus de trous, jamais moins."""
    counts = [
        DOWELS.resolve(*boards(500.0), DowelParams(max_spacing=value)).count
        for value in (1000.0, 300.0, 120.0, 60.0, 20.0)
    ]
    assert counts == sorted(counts) and counts[0] < counts[-1]


def test_gabarit_caisson_laisse_l_entraxe_a_zero() -> None:
    """ADR 0070 : les gabarits créent leurs assemblages avec ``MaxSpacing`` = 0."""
    assert dowel_params(18.0, 8.0).max_spacing == 0.0
    closing = importlib.import_module("freecad.menuiserie.core.templates.closing_joints")
    assert closing._dowels(18.0, 18.0, 8.0).max_spacing == 0.0


class _Joint:
    """Assemblage factice : ``MaxSpacing`` donné, les autres propriétés à leur valeur par défaut."""

    def __init__(self, kind: JointKind, values: dict[str, Any]) -> None:
        self.Proxy = SimpleNamespace(KIND=kind)
        self._values = values

    def __getattr__(self, name: str) -> Any:
        return self._values[name]


def _fake(config: Any, kind: JointKind, spacing: float) -> _Joint:
    module = importlib.import_module("freecad.menuiserie.features.joint_settings")
    names = {**module._PARAMETERS.get(kind, {}), **module._COPIED.get(kind, {})}
    values = {module.property_name(n): config.CATALOG.get(k).default for n, k in names.items()}
    values["MaxSpacing"] = spacing
    return _Joint(kind, values)


@pytest.mark.parametrize("kind", [JointKind.DOWELS, JointKind.LOOSE_TENON, JointKind.BISCUIT])
def test_dernier_utilise_retient_l_entraxe(
    kind: JointKind, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with settings_module(monkeypatch, tmp_path) as config:
        module = importlib.import_module("freecad.menuiserie.features.joint_settings")
        key = module._COPIED[kind]["max_spacing"]
        assert config.CATALOG.get(key).remember_last  # « Dernier utilisé » proposé
        module.record_joint_used(_fake(config, kind, 77.0))
        assert config.settings().value(key) == config.CATALOG.get(key).default  # case décochée
        config.settings().set_remember_last(key, True)
        module.record_joint_used(_fake(config, kind, 77.0))
        assert config.settings().value(key) == 77.0


def test_entraxe_nul_d_un_gabarit_ne_pollue_pas_le_dernier_utilise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with settings_module(monkeypatch, tmp_path) as config:
        module = importlib.import_module("freecad.menuiserie.features.joint_settings")
        module.record_joint_used(_fake(config, JointKind.DOWELS, 0.0))  # refusé : ignoré
        assert config.settings().value(config.DOWEL_SPACING) >= 10.0


def test_aucun_champ_nombre_dans_les_assemblages_a_entraxe() -> None:
    """Plus de ``Count`` ni de ``count`` saisi pour tourillons, faux tenons, lamellos."""
    for path in ("features/joints/dowels.py", "features/joints/slots.py"):
        text = (ROOT / "freecad/menuiserie" / path).read_text(encoding="utf-8")
        assert not re.search(r'PropertySpec\(\s*"Count"', text)
        assert "count_param" not in text
    for path in ("core/joints/dowels.py", "core/joints/slots/_params.py"):
        text = (ROOT / "freecad/menuiserie" / path).read_text(encoding="utf-8")
        assert "count_param" not in text.replace("import", "")


def test_la_valeur_par_defaut_des_lamellos_est_150() -> None:
    assert SlotParams().max_spacing == 0.0
    assert AUTO_SPACING_MM == 150.0


def test_verifications_gui_sans_champ_nombre_des_tourillons() -> None:
    """DEFAUT : ``tests/gui/verifications_panneau_assemblage.py`` cherche encore les champs
    ``Count`` et ``CountAuto`` du formulaire des tourillons (supprimés par l'ADR 0070)."""
    text = (ROOT / "tests/gui/verifications_panneau_assemblage.py").read_text(encoding="utf-8")
    assert 'widget(form, "Count")' not in text
    assert '"CountAuto"' not in text
