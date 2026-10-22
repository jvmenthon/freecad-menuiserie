# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objet ``CutList`` et numérotation des repères sur des objets simulés (J2f : V1 à V4, N1).

Le graphe de dépendances de FreeCAD (``mustExecute``, recalcul après les pièces), Annuler et la
réouverture sans l'atelier sont vérifiés par ``tests/integration/test_liste_de_debit_vivante.py``
et ``test_numerotation_reperes.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests.unit.aides_debit_document import Obj, World, group, link, simulated_world
from tests.unit.aides_debit_feuille import FakeFeature, FakeSheet, SheetDoc


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def part(world: World, name: str, mark: str = "", length: float = 800) -> Obj:
    return world.part(name, mark, (length, 200, 22), ExpressionEngine=[])


def live(world: World, doc: SheetDoc, objects: list[Obj] | None = None) -> FakeFeature:
    """Liste vivante de ``doc``, créée par ``ensure_cut_list``."""
    world.features.cutlist_object.ensure_cut_list(doc, objects)
    found = world.features.cutlist_object.find_cut_list(doc)
    assert isinstance(found, FakeFeature)
    return found


def must_execute(world: World, obj: FakeFeature) -> bool:
    return bool(obj.Proxy.mustExecute(obj))


# --- création par make_cut_list (ensure_cut_list) ------------------------------------------


def test_creation_en_une_transaction_feuille_objet_portee_et_sources(world: World) -> None:
    board, shelf = part(world, "WoodPart", "M1"), part(world, "WoodPart001", "M2")
    doc = SheetDoc(board, shelf, Obj("Autre", "Part::Box"))
    sheet, messages = world.features.cutlist_object.ensure_cut_list(doc, [board])
    obj = world.features.cutlist_object.find_cut_list(doc)
    assert doc.log == [
        "open Liste de débit",
        "add MenuiserieCutList",
        "add CutList",
        "commit",
    ]
    assert isinstance(sheet, FakeSheet)
    assert messages == ()
    assert (obj.Name, obj.TypeId, obj.Label) == (
        "CutList",
        "App::FeaturePython",
        "Mise à jour de la liste de débit",
    )
    assert obj.Proxy.TYPE == "Menuiserie::CutList"
    assert (obj.Sheet, obj.Scope, obj.Version) == (sheet, [board], 1)
    assert obj.types == {
        "Sheet": "App::PropertyLink",
        "Scope": "App::PropertyLinkListHidden",
        "Sources": "App::PropertyLinkList",
        "Version": "App::PropertyInteger",
    }
    assert obj.modes == {"Sheet": 1, "Sources": 2, "Version": 2}
    assert [source.Name for source in obj.Sources] == ["WoodPart"]  # seule la portée est lue
    assert sheet.cells["A3"] == "'Sélection : 1 objet"
    assert obj.purged == 1  # rien à recalculer après l'écriture


def test_deuxieme_appel_reutilise_les_deux_objets_et_change_la_portee(world: World) -> None:
    board, shelf = part(world, "WoodPart", "M1"), part(world, "WoodPart001", "M2")
    doc = SheetDoc(board, shelf)
    obj = live(world, doc, [board])
    doc.log.clear()
    sheet, _ = world.features.cutlist_object.ensure_cut_list(doc)
    assert doc.log == ["open Liste de débit", "commit"]
    assert world.features.cutlist_object.find_cut_list(doc) is obj
    assert (obj.Sheet, obj.Scope) == (sheet, [])
    assert sorted(source.Name for source in obj.Sources) == ["WoodPart", "WoodPart001"]
    assert sheet.cells["A3"] == "'Tout le document"
    assert [o.Name for o in doc.Objects].count("CutList") == 1


def test_feuille_recreee_est_reliee_a_l_objet_existant(world: World) -> None:
    doc = SheetDoc(part(world, "WoodPart", "M1"))
    obj = live(world, doc)
    doc.Objects.remove(obj.Sheet)
    obj.props["Sheet"] = None  # FreeCAD vide le lien d'un objet supprimé
    sheet, _ = world.features.cutlist_object.ensure_cut_list(doc)
    assert obj.Sheet is sheet
    assert len([o for o in doc.Objects if o.TypeId == "App::FeaturePython"]) == 1


def test_objet_supprime_la_feuille_est_gardee_et_un_objet_est_recree(world: World) -> None:
    doc = SheetDoc(part(world, "WoodPart", "M1"))
    obj = live(world, doc)
    sheet = obj.Sheet
    doc.Objects.remove(obj)
    sheet.set("P1", "'garde")
    again, _ = world.features.cutlist_object.ensure_cut_list(doc)
    assert again is sheet
    assert sheet.cells["P1"] == "'garde"
    assert world.features.cutlist_object.find_cut_list(doc) is not obj


def test_avertissements_renvoyes_et_ecrits_dans_la_feuille(world: World) -> None:
    doc = SheetDoc(part(world, "WoodPart", "M1"), part(world, "WoodPart001", "M1", 900))
    sheet, messages = world.features.cutlist_object.ensure_cut_list(doc)
    assert any("Repère M1" in message for message in messages)
    assert any(cell.startswith("'Repère M1") for cell in sheet.cells.values())


def test_objet_d_un_autre_document_refuse_avant_toute_transaction(world: World) -> None:
    doc = SheetDoc(part(world, "WoodPart", "M1"))
    stranger = SheetDoc(part(world, "WoodPart", "E"))
    with pytest.raises(ValueError, match="autre document"):
        world.features.cutlist_object.ensure_cut_list(doc, [stranger.Objects[0]])
    assert doc.log == []


def test_echec_annule_la_transaction(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("échec")

    monkeypatch.setattr(world.features.cutlist_sheet, "_fill", boom)
    doc = SheetDoc(part(world, "WoodPart", "M1"))
    with pytest.raises(RuntimeError):
        world.features.cutlist_object.ensure_cut_list(doc)
    assert doc.log[-1] == "abort"
    assert "commit" not in doc.log


# --- recalcul : execute / mustExecute -------------------------------------------------------


def test_objet_sans_proxy_n_est_pas_une_liste(world: World) -> None:
    plain = Obj("CutList", "App::FeaturePython", Sheet=None)
    doc = SheetDoc(plain)
    assert world.features.cutlist_object.find_cut_list(doc) is None
    assert not world.features.cutlist_object.is_cut_list(plain)


def test_must_execute_vrai_quand_une_piece_est_ajoutee_ou_supprimee(world: World) -> None:
    board = part(world, "WoodPart", "M1")
    doc = SheetDoc(board)
    obj = live(world, doc)
    assert not must_execute(world, obj)
    extra = part(world, "WoodPart001", "M2")
    extra.Document = doc
    doc.Objects.append(extra)
    assert must_execute(world, obj)
    obj.Proxy.execute(obj)
    assert not must_execute(world, obj)
    doc.Objects.remove(extra)
    obj.props["Sources"] = [board]  # FreeCAD retire l'objet supprimé des liens
    assert not must_execute(world, obj)


@pytest.mark.parametrize("kind", ["link", "group"])
def test_must_execute_voit_les_liens_et_les_conteneurs(world: World, kind: str) -> None:
    board = part(world, "WoodPart", "M1")
    doc = SheetDoc(board)
    obj = live(world, doc)
    added = link("Lien", board) if kind == "link" else group("Part", board)
    added.Document = doc
    doc.Objects.append(added)
    assert must_execute(world, obj)


def test_must_execute_ignore_les_autres_ateliers_et_les_elements_de_lien(world: World) -> None:
    doc = SheetDoc(part(world, "WoodPart", "M1"))
    obj = live(world, doc)
    for extra in (Obj("Boite", "Part::Box"), Obj("Element", "App::LinkElement", LinkedObject=None)):
        extra.Document = doc
        doc.Objects.append(extra)
    assert not must_execute(world, obj)


def test_must_execute_faux_avec_une_portee_choisie_sans_feuille_ou_pendant_une_annulation(
    world: World,
) -> None:
    board = part(world, "WoodPart", "M1")
    doc = SheetDoc(board)
    scoped = live(world, doc, [board])
    extra = part(world, "WoodPart001", "M2")
    extra.Document = doc
    doc.Objects.append(extra)
    assert not must_execute(world, scoped)  # portée choisie : ses objets sont dans Sources
    scoped.props["Scope"] = []
    assert must_execute(world, scoped)
    doc.Transacting = True
    assert not must_execute(world, scoped)
    doc.Transacting = False
    scoped.props["Sheet"] = None
    assert not must_execute(world, scoped)


def test_execute_reecrit_la_feuille_et_met_a_jour_sources(world: World) -> None:
    board = part(world, "WoodPart", "M1")
    doc = SheetDoc(board)
    obj = live(world, doc)
    sheet = obj.Sheet
    board.props["Length"].Value = 1234.0
    sheet.set("P1", "'garde")
    sheets_before = sheet.recomputed
    obj.Proxy.execute(obj)
    assert sheet.cells["C6"] == "1234"
    assert sheet.cells["P1"] == "'garde"
    assert sheet.recomputed == sheets_before + 1
    assert [source.Name for source in obj.Sources] == ["WoodPart"]


def test_sources_reecrit_seulement_si_les_objets_lus_changent(world: World) -> None:
    doc = SheetDoc(part(world, "WoodPart", "M1"))
    obj = live(world, doc)
    writes: list[Any] = []

    class Spy(dict[str, Any]):
        def __setitem__(self, key: str, value: Any) -> None:
            writes.append(key)
            super().__setitem__(key, value)

    obj.props = Spy(obj.props)
    obj.Proxy.execute(obj)
    assert "Sources" not in writes
    extra = part(world, "WoodPart001", "M2")
    extra.Document = doc
    doc.Objects.append(extra)
    obj.Proxy.execute(obj)
    assert "Sources" in writes


def test_execute_sans_feuille_ou_pour_un_modele_plus_recent_ne_fait_rien(world: World) -> None:
    doc = SheetDoc(part(world, "WoodPart", "M1"))
    obj = live(world, doc)
    sheet = obj.Sheet
    sheet.cells.clear()
    obj.props["Version"] = 99
    obj.Proxy.execute(obj)
    assert sheet.cells == {}
    obj.props["Version"] = 1
    obj.props["Sheet"] = None
    obj.Proxy.execute(obj)  # feuille supprimée : aucune erreur
    assert sheet.cells == {}


def test_la_date_de_la_feuille_dit_qu_elle_est_automatique(world: World) -> None:
    doc = SheetDoc(part(world, "WoodPart", "M1"))
    sheet = live(world, doc).Sheet
    assert sheet.cells["A2"].endswith("mise à jour automatiquement à chaque recalcul du document.")


# --- N1 : numérotation des repères ----------------------------------------------------------


def numbered(world: World, doc: SheetDoc, *args: Any, **kwargs: Any) -> dict[str, str]:
    return dict(world.features.cutlist_marks.number_marks(doc, *args, **kwargs))


def test_un_repere_par_groupe_en_une_transaction_puis_recalcul(world: World) -> None:
    long_a, long_b = part(world, "A", length=800), part(world, "B", length=800)
    short = part(world, "C", length=300)
    doc = SheetDoc(long_a, long_b, short)
    assert numbered(world, doc) == {"A": "M1", "B": "M1", "C": "M2"}
    assert [long_a.Mark, long_b.Mark, short.Mark] == ["M1", "M1", "M2"]
    assert doc.log == ["open Numéroter les repères", "recompute", "commit"]


def test_reperes_existants_gardes_et_sautes_prefixe_et_portee(world: World) -> None:
    kept, named = part(world, "A", "M1"), part(world, "B", "Plateau", 500)
    first, second = part(world, "C", length=400), part(world, "D", length=300)
    doc = SheetDoc(kept, named, first, second)
    assert numbered(world, doc, [second]) == {"D": "M2"}
    assert numbered(world, doc, prefix="P") == {"C": "P1"}
    assert kept.Mark == "M1"
    assert named.Mark == "Plateau"


def test_rien_a_numeroter_n_ouvre_pas_de_transaction(world: World) -> None:
    doc = SheetDoc(part(world, "A", "M1"))
    assert numbered(world, doc) == {}
    assert doc.log == []


def test_repere_pilote_par_une_expression_laisse_de_cote(world: World) -> None:
    driven = world.part("A", "", (800, 200, 22), ExpressionEngine=[("Mark", "<<X>>")])
    free = part(world, "B", length=300)
    doc = SheetDoc(driven, free)
    assert numbered(world, doc) == {"B": "M1"}
    assert driven.Mark == ""


@pytest.mark.parametrize("prefix", ["", "   "])
def test_prefixe_vide_refuse(world: World, prefix: str) -> None:
    doc = SheetDoc(part(world, "A"))
    with pytest.raises(ValueError, match="préfixe"):
        numbered(world, doc, prefix=prefix)
    assert doc.log == []


def test_numerotation_d_un_objet_d_un_autre_document_refusee(world: World) -> None:
    doc = SheetDoc(part(world, "A"))
    other = SheetDoc(part(world, "A"))
    with pytest.raises(ValueError, match="autre document"):
        numbered(world, doc, [other.Objects[0]])
    assert doc.log == []


def test_echec_d_ecriture_annule_la_transaction(world: World) -> None:
    class Refusing(Obj):
        def __setattr__(self, name: str, value: Any) -> None:
            if name == "Mark":
                raise RuntimeError("refusé")
            super().__setattr__(name, value)

    board = Refusing("A", "Part::FeaturePython", **part(world, "A").props)
    doc = SheetDoc(board)
    with pytest.raises(RuntimeError):
        numbered(world, doc)
    assert doc.log == ["open Numéroter les repères", "abort"]
