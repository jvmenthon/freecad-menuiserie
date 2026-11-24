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


def test_std_part_qui_se_lie_lui_meme_ne_boucle_pas(scope: ModuleType) -> None:
    """Revue sécurité : un Std Part qui contient dix liens vers lui-même (document piégé) est
    lu une fois, sans boucle ni explosion, et ne montre rien."""
    trap = Obj("S", TypeId="App::Part", Group=[])
    trap.Group = [_link(f"L{i}", trap) for i in range(10)]
    walk = scope.LinkWalk()
    assert scope.workshop_inside(trap, walk) == []
    assert walk.visits == 1


def test_tableau_de_liens_demesure_refuse(scope: ModuleType) -> None:
    with pytest.raises(ValueError):
        scope.link_occurrences(_link("L", None, ElementCount=scope.MAX_LINK_ELEMENTS + 1))
    assert scope.link_occurrences(_link("L", None, ElementCount=3)) == 3


def test_tableau_vise_sa_cible_et_non_lui_meme(scope: ModuleType) -> None:
    """Un tableau de liens rend lui-même par ``getLinkedObject`` : sa cible est lue sur
    ``LinkedObject``."""
    target = Obj("T", TypeId="App::Part", Group=[])
    array = _link("A", target, ElementCount=3)
    array.target = array  # ce que FreeCAD rend pour un tableau
    assert scope.link_target(array) is target


def _part(name: str, group: list[Any]) -> Obj:
    return Obj(name, TypeId="App::Part", Group=group)


def test_deux_liens_qui_se_visent_ne_bouclent_pas(scope: ModuleType) -> None:
    """Revue testeur : A vise B qui vise A (document piégé) : rien n'est montré, sans erreur."""
    first = _link("A", None)
    second = _link("B", first)
    first.LinkedObject = second
    walk = scope.LinkWalk()
    assert scope.workshop_inside(first, walk) == []
    assert scope.workshop_inside(second, walk) == []


def test_lien_vers_sous_element_vise_son_objet(scope: ModuleType) -> None:
    target = _part("T", [])
    assert scope.link_target(_link("L", (target, "Sub."))) is target
    assert scope.link_target(_link("L", ())) is None


def test_cible_commune_lue_une_seule_fois(scope: ModuleType) -> None:
    shared = _part("S", [])
    holder = _part("H", [_link(f"L{i}", shared) for i in range(50)])
    walk = scope.LinkWalk()
    assert scope.workshop_inside(holder, walk) == []
    assert walk.visits == 2  # le conteneur et la cible commune


def test_trop_de_cibles_lues_refuse(scope: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scope, "MAX_LINK_VISITS", 3)
    holder = _part("H", [_link(f"L{i}", _part(f"S{i}", [])) for i in range(10)])
    with pytest.raises(ValueError, match="liens imbriqués"):
        scope.workshop_inside(holder, scope.LinkWalk())


def test_plafond_d_elements_exactement_atteint(scope: ModuleType) -> None:
    link = _link("L", None, ElementCount=scope.MAX_LINK_ELEMENTS)
    assert scope.link_occurrences(link) == scope.MAX_LINK_ELEMENTS


def test_cle_d_objet_distingue_les_documents(scope: ModuleType) -> None:
    here, there = Obj("P"), Obj("P")
    there.Document = SimpleNamespace(Name="autre")
    here.Document = SimpleNamespace(Name="ici")
    assert scope.object_key(here) != scope.object_key(there)
    assert scope.object_key(here) == ("ici", "P")


@pytest.fixture
def parts(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import drawing_parts

        yield parts_module(drawing_parts, monkeypatch)


def parts_module(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """``drawing_parts`` où seules les pièces nommées « B… » sont des pièces de bois."""
    monkeypatch.setattr(module, "is_timber", lambda obj: obj.Name.startswith("B"))
    monkeypatch.setattr(module, "is_furniture", lambda _obj: False)
    monkeypatch.setattr(module, "is_machined_part", lambda _obj: False)
    monkeypatch.setattr(
        module, "workshop_inside", lambda target, _walk=None: list(getattr(target, "Group", []))
    )
    return module


def test_tableau_de_liens_multiplie_les_pieces(parts: ModuleType, scope: ModuleType) -> None:
    box = Obj("B1", TypeId="Part::Box")
    array = _link("L", _part("S", [box]), ElementCount=4)
    found = list(parts._blanks([array], set(), scope.LinkWalk()))
    assert [(blank.Name, count) for blank, count in found] == [("B1", 4)]


def test_liens_de_liens_multiplient_et_plafonnent(parts: ModuleType, scope: ModuleType) -> None:
    box = Obj("B1", TypeId="Part::Box")
    inner = _link("I", _part("S", [box]), ElementCount=3)
    outer = _link("O", _part("T", [inner]), ElementCount=5)
    found = list(parts._blanks([outer], set(), scope.LinkWalk()))
    assert [count for _, count in found] == [15]
    huge = _link("H", _part("U", [box]), ElementCount=scope.MAX_LINK_ELEMENTS)
    capped = list(parts._blanks([huge, _link("H2", huge)], set(), scope.LinkWalk()))
    assert all(count <= parts.MAX_QUANTITY for _, count in capped)


def test_lien_vide_ne_donne_aucune_piece(parts: ModuleType, scope: ModuleType) -> None:
    assert list(parts._blanks([_link("L", _part("S", []))], set(), scope.LinkWalk())) == []
