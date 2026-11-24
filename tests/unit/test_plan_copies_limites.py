# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans, retour de jv du 23/11 : cas limites des fonctions pures (revue testeur de la PR #247,
issue #153, ADR 0053) : place des cotes, chaînes bornées, texte du cartouche, copies par lien et
arbre du choix des pièces."""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterator
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from freecad.menuiserie.core.drawing import chain_labels, fit_to_cell
from tests.unit.aides_freecad import simulated_freecad


def _width(_start: float, _end: float) -> float:
    return 10.0


@pytest.fixture
def dims(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import drawing_dims

        yield drawing_dims


@pytest.fixture
def scope(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import drawing_scope

        yield drawing_scope


@pytest.fixture
def choice(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import drawing_choice

        yield drawing_choice


def _font(dims: ModuleType, monkeypatch: pytest.MonkeyPatch, size: float) -> None:
    params = SimpleNamespace(GetFloat=lambda _name, _default: size)
    monkeypatch.setattr(dims.App, "ParamGet", lambda _path: params)


@pytest.mark.parametrize("size", [0.0, -3.0, 0.99, 20.01, 1e9, math.nan, math.inf])
def test_taille_de_texte_invalide_rend_celle_de_techdraw(
    dims: ModuleType, monkeypatch: pytest.MonkeyPatch, size: float
) -> None:
    _font(dims, monkeypatch, size)
    assert dims.dimension_font_mm() == 5.0


def test_ecart_aux_lettres_suit_la_taille_du_texte(
    dims: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _font(dims, monkeypatch, 5.0)
    assert dims.section_clearance_mm() == pytest.approx(18.0)
    _font(dims, monkeypatch, 1.0)
    assert dims.section_clearance_mm() == 14.0  # plancher
    _font(dims, monkeypatch, 20.0)
    assert dims.section_clearance_mm() == pytest.approx(66.0)


def test_bande_des_cotes_grandit_avec_la_taille_du_texte(
    dims: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _font(dims, monkeypatch, 3.5)
    small = dims.overall_band_mm()
    _font(dims, monkeypatch, 5.0)
    assert dims.overall_band_mm() > small
    assert dims.overall_band_mm(chains=False) < dims.overall_band_mm()


def test_chaine_sans_limite_explicite_inchangee() -> None:
    segments = [(0.0, 30.0), (30.0, 60.0), (60.0, 90.0)]
    assert chain_labels(segments, _width) == chain_labels(segments, _width, (-math.inf, math.inf))
    assert [m for _, _, m in chain_labels(segments, _width)] == [15.0, 45.0, 75.0]


def test_limites_inversees_ou_vides_omettent_la_chaine() -> None:
    segments = [(0.0, 30.0), (30.0, 60.0)]
    assert chain_labels(segments, _width, (50.0, -50.0)) == []
    assert chain_labels(segments, _width, (100.0, 200.0)) == []


def test_limite_droite_serree_retire_le_dernier_point() -> None:
    labels = chain_labels([(0.0, 30.0), (30.0, 60.0), (60.0, 63.0)], _width, (0.0, 62.0))
    assert all(middle + 5.0 <= 62.0 for _, _, middle in labels)
    assert all(a[2] + 5.0 < b[2] - 5.0 for a, b in itertools.pairwise(labels))


def test_segments_nuls_ou_negatifs_ne_levent_pas() -> None:
    assert isinstance(chain_labels([(0.0, 0.0), (0.0, 0.0)], _width), list)
    assert isinstance(chain_labels([(30.0, 0.0), (0.0, -30.0)], _width), list)


def test_texte_vide_ou_blanc_du_cartouche() -> None:
    assert fit_to_cell("drawing_title", "") == ""
    assert fit_to_cell("client", "x" * 5) == "x" * 5


def test_texte_exactement_a_la_capacite_est_garde() -> None:
    capacity = int((90.0 - 4.5) / (0.6 * 3.5))
    assert fit_to_cell("client", "x" * capacity) == "x" * capacity
    assert fit_to_cell("client", "x" * (capacity + 1)) == "x" * (capacity - 1) + "…"


def test_raccourci_ne_laisse_pas_d_espace_avant_les_points() -> None:
    fitted = fit_to_cell("client", "mot " * 60)
    assert fitted.endswith("…") and not fitted.endswith(" …")


class Obj(SimpleNamespace):
    """Faux objet FreeCAD : un lien vise ``target`` (``None`` = ne vise rien)."""

    def __init__(self, name: str, **fields: Any) -> None:
        super().__init__(**{"Name": name, "Label": name, "Document": "doc", **fields})

    def getLinkedObject(self, _recurse: bool) -> Any:
        return self.target


def _link(name: str, target: Any, **fields: Any) -> Obj:
    return Obj(name, TypeId="App::Link", LinkedObject=target, target=target, **fields)


def test_lien_vide_ou_sur_lui_meme_ne_vise_rien(scope: ModuleType) -> None:
    assert scope.link_target(Obj("P", TypeId="Part::Box")) is None
    assert scope.link_target(_link("L", None)) is None
    loop = _link("L", None)
    loop.LinkedObject = loop
    loop.target = loop
    assert scope.link_target(loop) is None


def test_lien_vers_autre_document_est_une_cible(scope: ModuleType) -> None:
    target = Obj("T", TypeId="App::Part")
    target.Document = "autre"
    assert scope.link_target(_link("L", target)) is target
    same_name = Obj("L", TypeId="App::Part")
    same_name.Document = "autre"  # même nom mais autre document : pas lui-même
    assert scope.link_target(_link("L", same_name)) is same_name


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, 1), (-4, 1), (1, 1), (5, 5), (None, 1), ("3", 1), (2.0, 1)],
)
def test_nombre_de_copies_d_un_lien(scope: ModuleType, count: Any, expected: int) -> None:
    link = _link("L", Obj("T"))
    if count is not None:
        link.ElementCount = count
    assert scope.link_occurrences(link) == expected


def test_objet_sans_element_count_compte_une_copie(scope: ModuleType) -> None:
    assert scope.link_occurrences(Obj("P")) == 1


def test_pieces_d_un_std_part_vide_ou_etranger(scope: ModuleType) -> None:
    assert scope.workshop_inside(Obj("S", TypeId="App::Part", Group=[])) == []
    assert scope.workshop_inside(Obj("X", TypeId="Part::Feature")) == []


def test_part_label_repere_et_libelle(choice: ModuleType) -> None:
    assert choice.part_label(Obj("A", Label="Montant", Mark="M1")) == "M1 Montant"
    assert choice.part_label(Obj("A", Label="M1 Montant", Mark="M1")) == "M1 Montant"
    assert choice.part_label(Obj("A", Label="Montant", Mark="  ")) == "Montant"
    assert choice.part_label(Obj("A", Label="Montant")) == "Montant"


def test_ligne_sans_enfant_compte_une_piece(choice: ModuleType, monkeypatch: Any) -> None:
    monkeypatch.setattr(choice, "is_furniture", lambda obj: obj.Name == "E")
    assert choice.Choice(Obj("P")).parts == 1
    assert choice.Choice(Obj("E")).parts == 0  # ensemble vide
    group = choice.Choice(Obj("E"), (choice.Choice(Obj("P")), choice.Choice(Obj("Q"))))
    assert group.parts == 2
    nested = choice.Choice(Obj("F"), (group, choice.Choice(Obj("R"))))
    assert nested.parts == 3
