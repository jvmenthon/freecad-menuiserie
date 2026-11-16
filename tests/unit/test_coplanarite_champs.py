# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aimant des flèches des champs du panneau « Répéter » (jv, 2026-11-16, ADR 0058) : valeur du
champ qui met une copie au ras d'une voisine (``snap_field``, pur) et valeur gardée dans le champ
(``FieldSnap`` : pas aimanté, saisie au clavier inchangée), Qt et FreeCAD remplacés par des
doublures le temps de l'import."""

from __future__ import annotations

import importlib
import sys
import types
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from freecad.menuiserie.core.geometry import Box
from freecad.menuiserie.core.magnet import (
    SNAP_REACH_MM,
    Guide,
    GuideKind,
    PlaneIndex,
    snap_field,
)
from freecad.menuiserie.core.repeat import AxisRepeat, RepeatAxis, RepeatParams

SHELF = [0.0, 22.0]  # dessous et dessus de la tablette source, sur Z
FAR = [(500.0, 600.0), (1000.0, 1100.0), (0.0, 0.0)]


def plane(position: float, axis: int = 2) -> Guide:
    ranges = list(FAR)
    ranges[axis] = (position, position)
    return Guide(GuideKind.PLANE, Box.from_ranges(ranges), axis, 1)


def two_copies(step: float) -> list[float]:
    """Décalages sur Z de deux copies au pas ``step``."""
    return [step, 2 * step]


INDEX = PlaneIndex([plane(200.0)])  # dessus d'un voisin à 200 mm


# --- snap_field -------------------------------------------------------------------------------


def test_valeur_aimantee_sous_un_millimetre() -> None:
    """Pas 89,2 : dessus de la 2e copie à 200,4 ; au pas 89, il est à 200 (au ras)."""
    assert snap_field(89.2, two_copies, SHELF, INDEX, 2) == pytest.approx(89.0)


def test_valeur_trop_loin_non_aimantee() -> None:
    assert snap_field(87.0, two_copies, SHELF, INDEX, 2) is None  # il faudrait 89 : 2 mm


def test_limite_d_un_millimetre_stricte() -> None:
    assert SNAP_REACH_MM == 1.0
    assert snap_field(90.0, two_copies, SHELF, INDEX, 2) is None  # écart de 1 mm exactement
    assert snap_field(89.99, two_copies, SHELF, INDEX, 2) == pytest.approx(89.0)


def test_valeur_deja_au_ras_gardee() -> None:
    assert snap_field(89.0, two_copies, SHELF, INDEX, 2) == pytest.approx(89.0)


def test_plus_proche_des_valeurs_possibles() -> None:
    """Deux voisins : dessus de la 1re copie à 111 (pas 89) ou de la 2e à 200 (pas 89) et 201
    (pas 89,5) : la plus proche de 89,4 l'emporte."""
    index = PlaneIndex([plane(200.0), plane(201.0)])
    assert snap_field(89.4, two_copies, SHELF, index, 2) == pytest.approx(89.5)


def test_autre_axe_ignore() -> None:
    assert snap_field(89.2, two_copies, SHELF, INDEX, 0) is None


def test_saisie_refusee_sans_aimant() -> None:
    def refused(_value: float) -> list[float]:
        raise ValueError("pas nul")

    assert snap_field(89.2, refused, SHELF, INDEX, 2) is None


def test_copie_qui_ne_depend_pas_du_champ() -> None:
    assert snap_field(89.2, lambda _f: [178.0], SHELF, INDEX, 2) is None


def test_nombre_de_copies_qui_change_sans_aimant() -> None:
    def changing(value: float) -> list[float]:
        return [value] if value < 89.2005 else [value, 2 * value]

    assert snap_field(89.2, changing, SHELF, INDEX, 2) is None


def test_valeur_trouvee_verifiee() -> None:
    """Au pas trouvé (89), le nombre de copies change : pas d'aimant."""

    def fewer_below(value: float) -> list[float]:
        return two_copies(value) if value > 89.1 else [value]

    assert snap_field(89.2, fewer_below, SHELF, INDEX, 2) is None


# --- FieldSnap : valeur gardée dans le champ ----------------------------------------------------


class _Field:
    def __init__(self, name: str) -> None:
        self._name = name

    def objectName(self) -> str:  # nom de Qt
        return self._name

    def installEventFilter(self, _filter: object) -> None:
        return None

    def removeEventFilter(self, _filter: object) -> None:
        return None


@pytest.fixture(scope="module")
def field_snap() -> Iterator[Any]:
    """Module ``repeat_field_snap`` importé avec PySide (``QObject`` = ``object``) et FreeCAD
    remplacés ; les modules importés sont retirés ensuite."""
    qtcore = types.SimpleNamespace(
        QObject=object, QEvent=MagicMock(), Qt=MagicMock(), QTimer=MagicMock()
    )
    pyside = types.ModuleType("PySide")
    pyside.QtCore = qtcore  # type: ignore[attr-defined]
    pyside.QtGui = MagicMock()  # type: ignore[attr-defined]
    stubs: dict[str, Any] = {
        "PySide": pyside,
        "FreeCAD": MagicMock(),
        "FreeCADGui": MagicMock(),
    }
    before = set(sys.modules)
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        yield importlib.import_module("freecad.menuiserie.gui.task_panels.repeat_field_snap")
    finally:
        for name in set(sys.modules) - before:
            if name.startswith("freecad.menuiserie"):
                del sys.modules[name]
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def snap_at_20(raw: float) -> float | None:
    return 20.0 if abs(raw - 20.0) < 1.0 else None


def stepped(module: Any, field: _Field, stepping: bool) -> Any:
    snap = module.FieldSnap([field])
    snap._watch = types.SimpleNamespace(stepping=lambda _f: stepping, close=lambda: None)
    return snap


def test_suite_de_jv_aux_fleches(field_snap: Any) -> None:
    """Face voisine à 20 : 17,2 ; 18,2 ; 19,2 → 20 ; 21,2 (le pas repart de la valeur brute)."""
    field = _Field("stepZ")
    snap = stepped(field_snap, field, stepping=True)
    snap.note(field, 17.2)
    shown = [snap.target(field, 18.2, snap_at_20)]
    shown.append(snap.target(field, 19.2, snap_at_20))
    shown.append(snap.target(field, 20.2, snap_at_20))
    shown.append(snap.target(field, 21.0, snap_at_20))  # Qt : 20 + 1
    assert shown == pytest.approx([18.2, 19.2, 20.0, 21.2])


def test_retour_en_arriere_aux_fleches(field_snap: Any) -> None:
    field = _Field("stepZ")
    snap = stepped(field_snap, field, stepping=True)
    snap.note(field, 21.2)
    assert snap.target(field, 20.2, snap_at_20) == pytest.approx(20.2)  # 20 pas encore franchi
    assert snap.target(field, 19.2, snap_at_20) == pytest.approx(20.0)  # franchi : au ras
    assert snap.target(field, 19.0, snap_at_20) == pytest.approx(18.2)  # Qt : 20 - 1


def test_saisie_au_clavier_inchangee(field_snap: Any) -> None:
    field = _Field("stepZ")
    snap = stepped(field_snap, field, stepping=False)
    snap.note(field, 17.2)
    assert snap.target(field, 19.6, snap_at_20) == 19.6
    assert snap.target(field, 20.3, snap_at_20) == 20.3


def test_saisie_puis_fleche_repart_de_la_saisie(field_snap: Any) -> None:
    field = _Field("spanZ")
    snap = stepped(field_snap, field, stepping=False)
    snap.note(field, 17.2)
    snap.target(field, 18.5, snap_at_20)  # saisie
    snap._watch = types.SimpleNamespace(stepping=lambda _f: True, close=lambda: None)
    assert snap.target(field, 19.5, snap_at_20) == pytest.approx(19.5)  # 20 pas franchi
    assert snap.target(field, 20.5, snap_at_20) == pytest.approx(20.0)


def test_aimant_en_erreur_garde_la_valeur_brute(field_snap: Any) -> None:
    def broken(_raw: float) -> float | None:
        raise RuntimeError("objet supprimé")

    field = _Field("stepZ")
    snap = stepped(field_snap, field, stepping=True)
    snap.note(field, 17.2)
    assert snap.target(field, 18.2, broken) == pytest.approx(18.2)


def test_premier_changement_sans_valeur_connue(field_snap: Any) -> None:
    field = _Field("stepZ")
    snap = stepped(field_snap, field, stepping=True)
    assert snap.target(field, 20.2, snap_at_20) == 20.2  # rien de noté : pas d'aimant


def test_champ_remplace_dans_la_ligne(field_snap: Any) -> None:
    params = RepeatParams(
        grid=(AxisRepeat(RepeatAxis.X, 3, 100.0), AxisRepeat(RepeatAxis.Z, 2, 50.0, 400.0))
    )
    step = field_snap.with_field(params, RepeatAxis.Z, "step", 89.0)
    span = field_snap.with_field(params, RepeatAxis.Z, "span", 500.0)
    assert [line.step for line in step.grid] == [100.0, 89.0]
    assert [line.span for line in span.grid] == [0.0, 500.0]
