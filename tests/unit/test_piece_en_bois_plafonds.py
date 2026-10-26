# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plafonds de la pièce en bois (spec § 4.9) : solides d'une source, maillage, contrôle E3.

Une forme peut venir d'un STEP hostile ou d'un document d'autrui : le travail fait sur elle reste
borné et un volume dégénéré ne bloque jamais un assemblage. Formes simulées, sans FreeCAD ; les
vraies formes le sont par ``tests/integration/test_piece_en_bois*.py``."""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie.core.shaped import MAX_FACES
from tests.unit.aides_freecad import simulated_freecad
from tests.unit.aides_piece_en_bois import FakeShape, FakeSolid, FakeSource
from tests.unit.test_piece_en_bois_repere import Box, Line, Plane


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """``features.shaped_sources`` importé sur un FreeCAD simulé."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import shaped_sources

        yield shaped_sources


@pytest.fixture
def frame(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """``features.shaped_frame`` importé sur un FreeCAD simulé."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import shaped_frame

        part = sys.modules["Part"]
        monkeypatch.setattr(part, "Plane", Plane, raising=False)
        monkeypatch.setattr(part, "Line", Line, raising=False)
        monkeypatch.setattr(shaped_frame, "ERRORS", (RuntimeError, ValueError, TypeError))
        monkeypatch.setattr(part, "LineSegment", type("LineSegment", (), {}), raising=False)
        yield shaped_frame


# --- Solides d'une source ---------------------------------------------------------------------


def test_trop_de_solides_refuses_avant_tout_controle(sources: Any) -> None:
    count = sources.MAX_SOLIDS + 1
    shape = FakeShape(tuple(FakeSolid(valid=False) for _ in range(count)))  # isValid n'est pas lu
    obj = FakeSource(shape, type_id="Part::Feature", label="Import")
    with pytest.raises(ValueError, match="plus que les 256") as caught:
        sources.read_source(obj, 22.0)
    assert f"{count} solides" in str(caught.value)


def test_plafond_de_solides_atteint_accepte(sources: Any) -> None:
    shape = FakeShape(tuple(FakeSolid(1.0) for _ in range(sources.MAX_SOLIDS)))
    obj = FakeSource(shape, type_id="Part::Feature")
    assert len(sources.read_source(obj, 22.0).solids) == sources.MAX_SOLIDS


# --- Maillage ---------------------------------------------------------------------------------


@pytest.mark.parametrize("diagonal", [float("inf"), float("nan"), 1.0e9, 1.0e300])
def test_forme_demesuree_ou_non_finie_n_est_pas_maillee(frame: Any, diagonal: float) -> None:
    box = Box((100.0, 50.0, 20.0))
    box.BoundBox = types.SimpleNamespace(DiagonalLength=diagonal)
    assert frame.sample_of(box) is None
    assert box.tessellated == []


def test_diagonale_limite_encore_maillee(frame: Any) -> None:
    box = Box((100.0, 50.0, 20.0))
    box.BoundBox = types.SimpleNamespace(DiagonalLength=frame.MAX_MESH_DIAGONAL_MM)
    assert frame.sample_of(box) is not None
    assert box.tessellated == [50.0]


# --- Contrôle de la matière (E3) ----------------------------------------------------------------


class Common:
    """Résultat d'une intersection : un volume."""

    def __init__(self, volume: float) -> None:
        self.Volume = volume


class Body:
    """Forme dont l'intersection avec toute sonde a un volume donné (ou échoue)."""

    def __init__(self, volume: float, faces: int = 6, error: Exception | None = None) -> None:
        self.volume, self.Faces, self.error, self.calls = volume, [object()] * faces, error, 0

    def common(self, _probe: Any) -> Common:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return Common(self.volume)


@pytest.fixture
def material(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """``features.joint_material`` sur un FreeCAD simulé, boîte et forme à volonté."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import joint_material

        monkeypatch.setattr(joint_material, "solid_shape", lambda solid: solid)
        monkeypatch.setattr(joint_material, "grown_shape", lambda shape, _margin: shape)
        monkeypatch.setattr(joint_material, "ERRORS", (RuntimeError, ValueError))
        yield joint_material


def worst(
    module: Any, monkeypatch: pytest.MonkeyPatch, box: Body, shape: Body, cuts: int = 1
) -> float:
    monkeypatch.setattr(module, "box_of", lambda _part: box)
    monkeypatch.setattr(module, "base_shape_of", lambda _part: shape)
    ratio: float = module.worst_missing_ratio(types.SimpleNamespace(), [object()] * cuts, [])
    return ratio


def test_matiere_manquante_mesuree(material: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    assert worst(material, monkeypatch, Body(100.0), Body(50.0)) == pytest.approx(0.5)


@pytest.mark.parametrize("volume", [float("nan"), float("inf"), -1.0])
def test_volume_degenere_ne_bloque_pas_l_assemblage(
    material: Any, monkeypatch: pytest.MonkeyPatch, volume: float
) -> None:
    assert worst(material, monkeypatch, Body(100.0), Body(volume)) == 0.0


@pytest.mark.parametrize("error", [RuntimeError("OCC"), ValueError("volume")])
def test_echec_du_noyau_ne_bloque_pas_l_assemblage(
    material: Any, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    assert worst(material, monkeypatch, Body(100.0, error=error), Body(50.0)) == 0.0


def test_forme_trop_detaillee_sans_booleenne(
    material: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    box, shape = Body(100.0), Body(0.0, faces=MAX_FACES + 1)
    assert worst(material, monkeypatch, box, shape) == 0.0
    assert box.calls == shape.calls == 0


def test_sondes_bornees(material: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    box = Body(100.0)
    worst(material, monkeypatch, box, Body(100.0), cuts=material.MAX_PROBES + 40)
    assert box.calls == material.MAX_PROBES
