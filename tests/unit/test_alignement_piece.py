# SPDX-License-Identifier: LGPL-2.1-or-later
"""``features/part_align`` (AL-b, ADR 0054) sans FreeCAD réel : choix de la pièce, refus avant
toute écriture, retour en arrière (le mouvement lui-même est vérifié en intégration)."""

from __future__ import annotations

from collections.abc import Iterator
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.snap import FaceTarget, Frame
from tests.unit.aides_freecad import simulated_freecad

FRAME = Frame(Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
PLANAR = FaceTarget("Face1", FRAME, (1.0, 1.0), True)
CURVED = FaceTarget("Face2", FRAME, (1.0, 1.0), False)


class Element:
    """Élément choisi de test : ``owner()`` est l'objet porteur."""

    def __init__(self, obj: Any, element: str = "Face1") -> None:
        self.obj, self.element, self.subname = obj, element, f"{obj}.{element}"

    def owner(self) -> Any:
        return self.obj

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import part_align

        yield part_align


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    targets: tuple[Any, Any],
    pieces: tuple[Any, Any],
) -> None:
    monkeypatch.setattr(module, "targets_of", lambda _e, _o: targets)
    monkeypatch.setattr(module, "piece_of", lambda e: None, raising=False)
    from freecad.menuiserie.features import distance_move

    monkeypatch.setattr(
        distance_move, "piece_of", lambda e: pieces[0] if e.obj == "A" else pieces[1]
    )


def test_arete_ou_sommet_refuse(module: ModuleType) -> None:
    with pytest.raises(ValueError):
        module.FaceAlign(Element("A", "Edge1"), Element("B"))
    with pytest.raises(ValueError):
        module.FaceAlign(Element("A"), Element("B", "Vertex1"))


def test_meme_objet_refuse(module: ModuleType) -> None:
    with pytest.raises(ValueError):
        module.FaceAlign(Element("A"), Element("A", "Face2"))


def test_la_seconde_piece_bouge_par_defaut(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, module, (PLANAR, PLANAR), ("brute A", "brute B"))
    first, second = Element("A"), Element("B")
    aligned = module.FaceAlign(first, second)
    assert (aligned.moving_index, aligned.moving_part) == (1, "brute B")
    assert module.FaceAlign(first, second, first).moving_part == "brute A"


def test_objet_d_un_autre_atelier_ne_bouge_jamais(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, module, (PLANAR, PLANAR), ("brute A", None))
    first, second = Element("A"), Element("B")
    assert module.FaceAlign(first, second).moving_part == "brute A"
    with pytest.raises(ValueError):
        module.FaceAlign(first, second, second)  # forcer l'objet étranger : refusé


def test_aucune_piece_de_l_atelier_refuse(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, module, (PLANAR, PLANAR), (None, None))
    with pytest.raises(ValueError):
        module.FaceAlign(Element("A"), Element("B"))


def test_deux_faces_de_la_meme_piece_refusees(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pièce usinée et sa brute, ou assemblage et sa pièce invitée : même brute, refus."""
    _patch(monkeypatch, module, (PLANAR, PLANAR), ("brute", "brute"))
    with pytest.raises(ValueError):
        module.FaceAlign(Element("A"), Element("B"))


def test_moving_hors_de_la_paire_refuse(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, module, (PLANAR, PLANAR), ("brute A", "brute B"))
    with pytest.raises(ValueError):
        module.FaceAlign(Element("A"), Element("B"), Element("C"))


def test_face_non_plane_refusee_sans_ecriture(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    for pair in ((CURVED, PLANAR), (PLANAR, CURVED)):
        _patch(monkeypatch, module, pair, ("brute A", "brute B"))
        aligned = module.FaceAlign(Element("A"), Element("B"))
        touched: list[str] = []
        monkeypatch.setattr(module, "raw_part", lambda part, log=touched: log.append("raw"))
        with pytest.raises(ValueError):
            aligned.apply()
        assert touched == []  # refus avant toute lecture ou écriture de la pièce


def test_placement_pilote_par_formule_refuse_sans_ecriture(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, module, (PLANAR, PLANAR), ("brute A", "brute B"))
    raw = SimpleNamespace(Label="Montant")
    monkeypatch.setattr(module, "raw_part", lambda _part: raw)
    monkeypatch.setattr(module, "placement_expression", lambda _raw: "Params.X")
    calls: list[str] = []
    monkeypatch.setattr(module, "begin_drag", lambda _raw: calls.append("begin"))
    monkeypatch.setattr(module, "write_placement", lambda *_a: calls.append("write"))
    aligned = module.FaceAlign(Element("A"), Element("B"))
    monkeypatch.setattr(module, "global_motion", lambda _a: calls.append("motion"))
    with pytest.raises(ValueError, match="Montant"):
        aligned.apply()
    assert calls == []


def test_echec_pendant_l_ecriture_restaure_la_piece(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, module, (PLANAR, PLANAR), ("brute A", "brute B"))
    raw = SimpleNamespace(
        Label="Montant",
        getGlobalPlacement=lambda: SimpleNamespace(
            Base=(0.0, 0.0, 0.0),
            Rotation=SimpleNamespace(Q=(0.0, 0.0, 0.0, 1.0)),
            multiply=lambda _o: SimpleNamespace(
                inverse=lambda: SimpleNamespace(multiply=lambda x: x)
            ),
        ),
    )
    memento = SimpleNamespace(placement=SimpleNamespace(inverse=lambda: None), part=raw)
    restored: list[Any] = []
    monkeypatch.setattr(module, "raw_part", lambda _part: raw)
    monkeypatch.setattr(module, "placement_expression", lambda _raw: None)
    monkeypatch.setattr(module, "begin_drag", lambda _raw: memento)
    monkeypatch.setattr(module, "global_motion", lambda _a: SimpleNamespace(multiply=lambda s: s))

    def boom(*_args: Any) -> None:
        raise RuntimeError("écriture impossible")

    monkeypatch.setattr(module, "write_placement", boom)
    monkeypatch.setattr(module, "restore", restored.append)
    with pytest.raises(RuntimeError):
        module.FaceAlign(Element("A"), Element("B")).apply()
    assert restored == [memento]


def test_annulation_du_choix_des_assemblages_restaure_et_remonte(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``end_drag`` lève ``DragCancelledError`` : la brute est restaurée et l'exception remonte
    (la commande en fait un refus, la transaction est annulée)."""
    from freecad.menuiserie.features.drag_joints import DragCancelledError

    _patch(monkeypatch, module, (PLANAR, PLANAR), ("brute A", "brute B"))
    placement = SimpleNamespace(
        Base=(0.0, 0.0, 0.0),
        Rotation=SimpleNamespace(Q=(0.0, 0.0, 0.0, 1.0)),
        multiply=lambda _o: SimpleNamespace(inverse=lambda: SimpleNamespace(multiply=lambda x: x)),
    )
    raw = SimpleNamespace(Label="M", getGlobalPlacement=lambda: placement)
    memento = SimpleNamespace(placement=SimpleNamespace(inverse=lambda: None), part=raw)
    restored: list[Any] = []
    monkeypatch.setattr(module, "raw_part", lambda _part: raw)
    monkeypatch.setattr(module, "placement_expression", lambda _raw: None)
    monkeypatch.setattr(module, "begin_drag", lambda _raw: memento)
    monkeypatch.setattr(module, "global_motion", lambda _a: SimpleNamespace(multiply=lambda s: s))
    monkeypatch.setattr(module, "write_placement", lambda *_a: None)
    monkeypatch.setattr(module, "restore", restored.append)

    def cancel(_memento: Any, _choose: Any) -> list[str]:
        raise DragCancelledError("annulé")

    monkeypatch.setattr(module, "end_drag", cancel)
    with pytest.raises(DragCancelledError):
        module.FaceAlign(Element("A"), Element("B")).apply()
    assert restored == [memento]


def test_mode_inconnu_de_l_api_refuse_avant_toute_lecture(monkeypatch: pytest.MonkeyPatch) -> None:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie import api

        with pytest.raises(ValueError, match="mode"):
            api.align_faces(object(), object(), mode="oblique")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            api.align_faces(object(), object(), mode="FLUSH")  # type: ignore[arg-type]
