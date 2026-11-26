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
    assert state.kinds == {export.PlanKind.OVERALL, export.PlanKind.EXPLODED}
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
    found = export.pages_to_export(doc, [existing], [a, b], [export.PlanKind.OVERALL])
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


def test_piece_usinee_et_sa_brute_partagent_la_meme_ligne(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le plan dessine la pièce usinée : la brute (et sa jumelle) l'ont pour plan."""
    brute, jumelle, usinee = _obj("Brute"), _obj("Jumelle"), _obj("Usinee")
    page = _page("PlanUsinee", "part", (usinee,))
    _groups(export, monkeypatch, [[brute, jumelle]])
    monkeypatch.setattr(export, "machined_part_of", lambda obj: usinee if obj is brute else None)
    state = export.export_state(_doc(brute, jumelle, usinee, page))
    assert state.page_of == {"Brute": page, "Jumelle": page}
    assert state.missing([brute, jumelle]) == []
    assert state.other_pages == []


def test_deux_pages_pour_un_meme_groupe_la_seconde_reste_a_part(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = _obj("A"), _obj("B")
    first, second = _page("Plan1", "part", (a,)), _page("Plan2", "part", (b,))
    _groups(export, monkeypatch, [[a, b]])
    state = export.export_state(_doc(a, b, first, second))
    assert state.page_of == {"A": first, "B": first}
    assert state.other_pages == [second]


def test_page_sans_vues_ni_gabarit_ne_plante_pas(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare = SimpleNamespace(Name="Nue", Label="Nue", TypeId=PAGE)
    marked = SimpleNamespace(
        Name="Marquee",
        Label="Marquee",
        TypeId=PAGE,
        MenuiserieDrawing=True,
        MenuiserieDrawingKind="part",
        MenuiserieDrawingViews="Absente",
    )
    _groups(export, monkeypatch, [])
    state = export.export_state(_doc(bare, marked))
    assert state.other_pages == [bare, marked]


def test_objets_qui_ne_sont_pas_des_pages_sont_ignores(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _groups(export, monkeypatch, [])
    state = export.export_state(_doc(_obj("A"), SimpleNamespace(Name="Sans", Label="Sans")))
    assert state.other_pages == []
    assert state.kinds == set()


def test_rien_de_coche_ne_donne_aucune_page_et_ne_cree_rien(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interdit(*_args: Any) -> None:
        raise AssertionError("rien ne doit être créé")

    monkeypatch.setattr(export, "make_part_drawings", interdit)
    monkeypatch.setattr(export, "make_overall_drawing", interdit)
    monkeypatch.setattr(export, "make_exploded_drawing", interdit)
    monkeypatch.setattr(export, "blanks_of", list)
    assert export.pages_to_export(_doc(), [], []) == []


def test_page_cochee_et_ses_pieces_ne_font_qu_une_feuille(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = _obj("A"), _obj("B")
    page = _page("Plan", "part", (a,))
    _groups(export, monkeypatch, [[a, b]])
    monkeypatch.setattr(export, "blanks_of", list)
    assert export.pages_to_export(_doc(a, b, page), [page], [a, b]) == [page]


def test_pieces_identiques_manquantes_sont_toutes_confiees_a_la_creation(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le regroupement en un plan par groupe est fait par ``make_part_drawings`` : les deux
    pièces lui sont données, et le plan créé sert aux deux."""
    a, b = _obj("A"), _obj("B")
    doc = _doc(a, b)
    _groups(export, monkeypatch, [[a, b]])
    monkeypatch.setattr(export, "blanks_of", list)
    received: list[list[Any]] = []

    def make_parts(document: Any, blanks: list[Any], _options: Any) -> list[Any]:
        received.append(list(blanks))
        document.Objects.append(_page("Plan", "part", (a,)))
        return []

    monkeypatch.setattr(export, "make_part_drawings", make_parts)
    found = export.pages_to_export(doc, [], [a, b])
    assert received == [[a, b]]
    assert [page.Name for page in found] == ["Plan"]


def test_plans_de_l_ouvrage_demandes_sans_piece(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(export, "document_scope", lambda _doc: [])
    monkeypatch.setattr(export, "blanks_of", list)
    monkeypatch.setattr(export, "make_overall_drawing", lambda *_a: _page("Ouvrage", ""))
    monkeypatch.setattr(export, "make_exploded_drawing", lambda *_a: _page("Eclate", "exploded"))
    kinds = [export.PlanKind.EXPLODED, export.PlanKind.OVERALL]
    found = export.pages_to_export(_doc(), [], [], kinds)
    assert [page.Name for page in found] == ["Ouvrage", "Eclate"]


def test_un_plan_impossible_a_creer_remonte_l_erreur(
    export: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = _obj("A")
    _groups(export, monkeypatch, [[a]])
    monkeypatch.setattr(export, "blanks_of", list)

    def refuse(*_args: Any) -> None:
        raise ValueError("TechDraw manque")

    monkeypatch.setattr(export, "make_part_drawings", refuse)
    with pytest.raises(ValueError, match="TechDraw"):
        export.pages_to_export(_doc(a), [], [a])


@pytest.fixture
def exports(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import cutlist_export

        yield cutlist_export


def test_nom_numerote_libre(exports: ModuleType, tmp_path: Any) -> None:
    plans = tmp_path / "plans.pdf"
    assert exports.numbered_path(plans) == tmp_path / "plans 2.pdf"
    plans.write_bytes(b"")
    (tmp_path / "plans 2.pdf").write_bytes(b"")
    assert exports.numbered_path(plans) == tmp_path / "plans 3.pdf"
    assert exports.numbered_path(tmp_path / "plans 2.pdf") == tmp_path / "plans 3.pdf"
    assert exports.numbered_path(tmp_path / "2026.pdf") == tmp_path / "2026 2.pdf"


def test_nombre_final_d_un_nom_n_est_pas_un_numero(exports: ModuleType, tmp_path: Any) -> None:
    """« Plan 2026 » (sans « Plan » à côté) n'a pas de numéro posé par l'export."""
    assert exports.numbered_path(tmp_path / "Plan 2026.pdf") == tmp_path / "Plan 2026 2.pdf"
    assert exports.numbered_path(tmp_path / "Plan 12.pdf") == tmp_path / "Plan 12 2.pdf"


def test_aucun_nom_libre_est_refuse(
    exports: ModuleType, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exports, "_MAX_NUMBER", 3)
    for name in ("plans.pdf", "plans 2.pdf", "plans 3.pdf"):
        (tmp_path / name).write_bytes(b"")
    with pytest.raises(ValueError, match="aucun nom libre"):
        exports.numbered_path(tmp_path / "plans.pdf")


def test_fichier_deja_la_selon_le_choix(exports: ModuleType, tmp_path: Any) -> None:
    plans = tmp_path / "plans.pdf"
    interdit = lambda *_a: pytest.fail("pas de question pour un fichier libre")  # noqa: E731
    assert exports.free_target(plans, interdit) == plans
    plans.write_bytes(b"")
    questions: list[tuple[str, str]] = []

    def choix(reponse: str | None) -> Any:
        def choose(path: Any, other: Any) -> str | None:
            questions.append((path.name, other.name))
            return reponse

        return choose

    assert exports.free_target(plans, choix(exports.OVERWRITE)) == plans
    assert exports.free_target(plans, choix(exports.NUMBERED)) == tmp_path / "plans 2.pdf"
    assert exports.free_target(plans, choix(None)) is None
    assert questions == [("plans.pdf", "plans 2.pdf")] * 3
