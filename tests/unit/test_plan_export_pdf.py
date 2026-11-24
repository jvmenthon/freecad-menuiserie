# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export PDF des plans (retour de jv du 24/11, maquette B) : état des plans du document et
pages à exporter, avec des pages et des pièces simulées."""

from __future__ import annotations

from collections.abc import Iterator
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from tests.unit.aides_freecad import simulated_freecad

PAGE = "TechDraw::DrawPage"


@pytest.fixture
def export(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import drawing_export

        monkeypatch.setattr(drawing_export, "machined_part_of", lambda _obj: None)
        yield drawing_export


def _obj(name: str, **fields: Any) -> SimpleNamespace:
    return SimpleNamespace(Name=name, Label=name, TypeId="Part::Feature", **fields)


def _page(name: str, kind: str | None, sources: tuple[Any, ...] = ()) -> SimpleNamespace:
    """Page de plan : de l'atelier si ``kind`` n'est pas ``None`` (« part », « », …)."""
    front = SimpleNamespace(Name=f"{name}Face", Source=list(sources))
    fields: dict[str, Any] = {"Views": [front]}
    if kind is not None:
        fields |= {
            "MenuiserieDrawing": True,
            "MenuiserieDrawingKind": kind,
            "MenuiserieDrawingViews": front.Name,
        }
    return SimpleNamespace(Name=name, Label=name, TypeId=PAGE, **fields)


def _doc(*objects: Any) -> SimpleNamespace:
    return SimpleNamespace(Objects=list(objects))


def _groups(export: ModuleType, monkeypatch: pytest.MonkeyPatch, groups: list[list[Any]]) -> None:
    monkeypatch.setattr(export, "part_groups", lambda _doc, _objects: groups)


def test_une_page_de_piece_vaut_pour_les_pieces_identiques(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    joue_g, joue_d, fond = _obj("JoueG"), _obj("JoueD"), _obj("Fond")
    page = _page("PlanJoue", "part", (joue_d,))
    _groups(export, monkeypatch, [[joue_g, joue_d], [fond]])
    state = export.export_state(_doc(joue_g, joue_d, fond, page))
    assert state.page_of == {"JoueG": page, "JoueD": page}
    assert state.missing([joue_g, fond]) == [fond]
    assert state.blank_pages([joue_g, joue_d, fond]) == [page]
    assert state.other_pages == []


def test_plans_de_l_ouvrage_et_pages_etrangeres_a_part(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    overall, exploded = _page("Ouvrage", ""), _page("Eclate", "exploded")
    foreign = _page("PageTechDraw", None)
    orphan = _page("PlanOrphelin", "part", (_obj("Disparue"),))
    _groups(export, monkeypatch, [])
    state = export.export_state(_doc(overall, exploded, foreign, orphan))
    assert state.kinds == {"", "exploded"}
    assert state.other_pages == [overall, exploded, foreign, orphan]


def test_plans_a_creer_un_par_groupe(export: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    a, b, c = _obj("A"), _obj("B"), _obj("C")
    _groups(export, monkeypatch, [[a, b], [c]])
    state = export.export_state(_doc(a, b, c))
    assert state.plans_to_create([a, b, c]) == 2
    assert state.plans_to_create([a, b]) == 1
    assert state.plans_to_create([]) == 0


def test_document_demesure_n_a_aucun_plan_de_piece(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_doc: Any, _objects: Any) -> list[list[Any]]:
        raise ValueError("démesuré")

    monkeypatch.setattr(export, "part_groups", refuse)
    page = _page("Plan", "part", (_obj("A"),))
    state = export.export_state(_doc(page))
    assert state.page_of == {}
    assert state.other_pages == [page]


def test_pages_a_exporter_dans_l_ordre_et_plans_crees(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plans de l'ouvrage à créer, pages cochées, puis plans des pièces (créés s'ils manquent),
    sans doublon."""
    a, b = _obj("A"), _obj("B")
    existing = _page("PlanA", "part", (a,))
    made: list[Any] = []
    doc = _doc(a, b, existing)
    _groups(export, monkeypatch, [[a], [b]])
    monkeypatch.setattr(export, "document_scope", lambda _doc: [a, b])
    monkeypatch.setattr(export, "blanks_of", list)
    monkeypatch.setattr(export, "make_overall_drawing", lambda *_a: _page("Ouvrage", ""))

    def make_parts(document: Any, blanks: list[Any], _options: Any) -> list[Any]:
        made.extend(blanks)
        page = _page("PlanB", "part", tuple(blanks))
        document.Objects.append(page)
        return [page]

    monkeypatch.setattr(export, "make_part_drawings", make_parts)
    found = export.pages_to_export(doc, [existing], [a, b], [export.OVERALL])
    assert [page.Name for page in found] == ["Ouvrage", "PlanA", "PlanB"]
    assert made == [b]


def test_rien_a_creer_ne_touche_pas_au_document(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = _obj("A")
    existing = _page("PlanA", "part", (a,))
    _groups(export, monkeypatch, [[a]])
    monkeypatch.setattr(export, "blanks_of", list)

    def interdit(*_args: Any) -> None:
        raise AssertionError("aucun plan ne doit être créé")

    monkeypatch.setattr(export, "make_part_drawings", interdit)
    monkeypatch.setattr(export, "make_overall_drawing", interdit)
    assert export.pages_to_export(_doc(a, existing), [], [a]) == [existing]
