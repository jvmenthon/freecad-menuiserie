# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046) au-dessus du Std Part par ensemble (ADR 0038) : changer
d'ensemble, sortir, créer un sous-ensemble, annuler (Ctrl+Z), assemblage vers l'extérieur,
« Renommer » par l'api, Std Part et Origine absents des lignes du panneau."""

from __future__ import annotations

from functools import partial
from typing import Any

import pytest

from tests.integration.bureau import build_desk, build_parts
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_ensemble_std_part import geometry

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
structure_facts = pytest.importorskip("freecad.menuiserie.features.structure_facts")
structure_foreign = pytest.importorskip("freecad.menuiserie.features.structure_foreign")
structure_source = pytest.importorskip("freecad.menuiserie.features.structure_source")
tree_module = pytest.importorskip("freecad.menuiserie.core.structure_tree")


def holder(obj: Any) -> Any:
    """Conteneur (Std Part) direct de ``obj``."""
    return obj.getParentGeoFeatureGroup()


def std_part(furniture: Any) -> Any:
    part = container.std_part_of(furniture)
    assert part is not None
    return part


def transaction(document: Any, name: str, action: Any) -> Any:
    """Exécute ``action`` dans une transaction annulable, comme le fait le panneau."""
    document.UndoMode = 1
    document.clearUndos()
    document.openTransaction(name)
    result = action()
    document.commitTransaction()
    return result


def two_furnitures(document: Any) -> tuple[Any, Any, Any, Any]:
    """Bureau (plateau) et Armoire (voile) côte à côte à la racine."""
    desk = build_parts(document)
    first, _ = api.make_furniture([desk.parts["P"]], "Bureau")
    second, _ = api.make_furniture([desk.parts["V"]], "Armoire")
    return desk, first, second, desk.parts["P"]


# --- Changer d'ensemble, sortir, Ctrl+Z ---------------------------------------------------------


def test_changer_d_ensemble_range_la_piece_dans_le_std_part_d_arrivee(document: Any) -> None:
    desk, first, second, plateau = two_furnitures(document)
    before = geometry(document)
    transaction(document, "Changer", partial(api.add_to_furniture, second, [plateau], move=True))
    assert api.furniture_of(plateau) == second
    assert holder(plateau) == std_part(second)
    assert holder(api.machined_part_of(plateau) or plateau) == std_part(second)
    assert holder(desk.parts["V"]) == std_part(second)
    assert plateau.Name not in {obj.Name for obj in std_part(first).Group}
    assert geometry(document) == before  # rien ne bouge à l'écran
    assert stale_or_invalid(document) == []


def test_changer_d_ensemble_s_annule_et_se_retablit(document: Any) -> None:
    _desk, first, second, plateau = two_furnitures(document)
    before = geometry(document)
    properties = set(plateau.PropertiesList)
    transaction(document, "Changer", partial(api.add_to_furniture, second, [plateau], move=True))
    document.undo()
    document.recompute()
    assert api.furniture_of(plateau) == first
    assert holder(plateau) == std_part(first)
    assert set(plateau.PropertiesList) == properties
    assert geometry(document) == before
    assert stale_or_invalid(document) == []
    document.redo()
    document.recompute()
    assert api.furniture_of(plateau) == second
    assert holder(plateau) == std_part(second)


def test_sortir_de_l_ensemble_laisse_la_piece_a_sa_place(document: Any) -> None:
    _desk, first, _second, plateau = two_furnitures(document)
    before = geometry(document)
    transaction(
        document, "Sortir", partial(api.remove_from_furniture, [plateau], keep_properties=True)
    )
    assert api.furniture_of(plateau) is None
    assert holder(plateau) is None  # conteneur du Std Part de Bureau : la racine
    assert "Furniture" in plateau.PropertiesList  # orphelin : propriétés de membre gardées
    assert geometry(document) == before
    document.undo()
    document.recompute()
    assert api.furniture_of(plateau) == first
    assert holder(plateau) == std_part(first)
    assert geometry(document) == before
    assert stale_or_invalid(document) == []


def test_sortie_puis_retour_d_un_orphelin(document: Any) -> None:
    _desk, first, second, plateau = two_furnitures(document)
    api.remove_from_furniture([plateau], keep_properties=True)
    api.add_to_furniture(second, [plateau])
    assert api.furniture_of(plateau) == second and holder(plateau) == std_part(second)
    assert stale_or_invalid(document) == []
    assert holder(std_part(first)) is None


def test_commande_retirer_garde_aussi_les_proprietes(document: Any) -> None:
    """« Retirer de l'ensemble » (commande native) et « Sortir » du panneau sont alignés."""
    _desk, _first, _second, plateau = two_furnitures(document)
    api.remove_from_furniture([plateau], keep_properties=True)
    assert plateau.Furniture is None and plateau.FurnitureBindings == {}


# --- Sous-ensemble et assemblage (M1) ----------------------------------------------------------


def joints_of(desk: Any) -> list[str]:
    return [joint.Name for joint in desk.joints]


def test_sous_ensemble_d_une_seule_piece_assemblee_ne_cree_rien(document: Any) -> None:
    """Joue gauche est assemblée au voile (tous deux dans Bureau) : seule, elle reste dans Bureau
    avec le voile (même Std Part) ; il ne reste rien à ranger dans le sous-ensemble, refusé avant
    toute modification, avec la raison."""
    desk = build_desk(document)
    before = geometry(document)
    count = len([o for o in document.Objects if o.TypeId == "App::Part"])
    with pytest.raises(ValueError, match=r"Rien à créer.*reste dans « Bureau »"):
        api.make_furniture([desk.shown("JG")], "Tiroir")
    assert api.furniture_of(desk.parts["JG"]) == desk.furniture
    assert holder(desk.parts["JG"]) == std_part(desk.furniture)
    assert len([o for o in document.Objects if o.TypeId == "App::Part"]) == count
    assert geometry(document) == before


def test_sous_ensemble_des_pieces_assemblees_ensemble_s_annule_et_se_retablit(
    document: Any,
) -> None:
    """Joue gauche, joue droite et voile (assemblés) forment un sous-ensemble."""
    desk = build_desk(document)
    before = geometry(document)
    chosen = [desk.shown(mark) for mark in ("JG", "JD", "V")]
    sub, _ = transaction(document, "Sous-ensemble", partial(api.make_furniture, chosen, "Tiroir"))
    assert sub.Furniture == desk.furniture and holder(desk.parts["V"]) == std_part(sub)
    assert holder(desk.parts["P"]) == std_part(desk.furniture)
    assert geometry(document) == before
    assert stale_or_invalid(document) == []
    document.undo()
    document.recompute()
    assert api.furniture_of(desk.parts["JG"]) == desk.furniture
    assert holder(desk.parts["JG"]) == std_part(desk.furniture)
    assert geometry(document) == before
    assert stale_or_invalid(document) == []
    document.redo()
    document.recompute()
    assert api.furniture_of(desk.parts["JG"]).Label == "Tiroir"
    assert holder(desk.parts["JG"]).Label == "Tiroir (Std Part)"
    assert stale_or_invalid(document) == []


def test_sous_ensemble_laisse_dans_le_parent_la_piece_assemblee_a_une_piece_du_parent(
    document: Any,
) -> None:
    """Plateau (libre de tout assemblage) et joue gauche (assemblée au voile, resté dans Bureau) :
    le sous-ensemble ne reçoit que le plateau, la joue reste dans Bureau, avec un avertissement."""
    desk = build_desk(document)
    before = geometry(document)
    sub, notices = transaction(
        document,
        "Sous-ensemble",
        partial(api.make_furniture, [desk.shown("P"), desk.shown("JG")], "Tiroir"),
    )
    assert api.furniture_of(desk.parts["P"]) == sub and holder(desk.parts["P"]) == std_part(sub)
    assert api.furniture_of(desk.parts["JG"]) == desk.furniture
    assert holder(desk.parts["JG"]) == std_part(desk.furniture)
    assert any("reste dans « Bureau »" in message for message in notices)
    assert geometry(document) == before
    document.undo()
    document.recompute()
    assert api.furniture_of(desk.parts["P"]) == desk.furniture
    assert geometry(document) == before
    assert stale_or_invalid(document) == []


def test_deposer_sur_un_sous_ensemble_une_piece_assemblee_reste_dans_le_parent(
    document: Any,
) -> None:
    """Joue gauche déposée sur Tiroir (sous-ensemble de Bureau), assemblée au voile (Bureau) :
    elle reste dans Bureau, rien ne bouge, l'api le dit."""
    desk = build_desk(document)
    sub, _ = api.make_furniture([desk.shown("P")], "Tiroir")
    before = geometry(document)
    notices = transaction(
        document, "Ranger", partial(api.add_to_furniture, sub, [desk.parts["JG"]], move=True)
    )
    assert any("elle reste dans « Bureau »" in message for message in notices)
    assert api.furniture_of(desk.parts["JG"]) == desk.furniture
    assert holder(desk.parts["JG"]) == std_part(desk.furniture)
    assert holder(desk.parts["V"]) == std_part(desk.furniture)
    assert geometry(document) == before
    assert stale_or_invalid(document) == []


def test_deposer_toutes_les_pieces_assemblees_sur_le_sous_ensemble(document: Any) -> None:
    """Joues et voile (assemblés) déposés ensemble sur Tiroir : tous vont dans Tiroir ; Ctrl+Z
    puis Ctrl+Y."""
    desk = build_desk(document)
    sub, _ = api.make_furniture([desk.shown("P")], "Tiroir")
    before = geometry(document)
    chosen = [desk.parts[mark] for mark in ("JG", "JD", "V")]
    notices = transaction(document, "Ranger", partial(api.add_to_furniture, sub, chosen, move=True))
    assert notices == ()
    assert all(api.furniture_of(part) == sub for part in chosen)
    assert all(holder(part) == std_part(sub) for part in chosen)
    assert geometry(document) == before
    assert stale_or_invalid(document) == []
    document.undo()
    document.recompute()
    assert all(api.furniture_of(part) == desk.furniture for part in chosen)
    assert all(holder(part) == std_part(desk.furniture) for part in chosen)
    assert geometry(document) == before
    document.redo()
    document.recompute()
    assert all(api.furniture_of(part) == sub for part in chosen)
    assert stale_or_invalid(document) == []


def test_assemblage_vers_l_exterieur_refuse_sans_rien_changer(document: Any) -> None:
    """Joue gauche assemblée au voile (Bureau) ne passe pas dans un autre ensemble."""
    desk = build_desk(document)
    free = build_parts(document)
    target, _ = api.make_furniture([free.parts["P"]], "Armoire")
    before = geometry(document)
    with pytest.raises(ValueError, match="assemblée"):
        api.add_to_furniture(target, [desk.parts["JG"]], move=True)
    assert api.furniture_of(desk.parts["JG"]) == desk.furniture
    assert holder(desk.parts["JG"]) == std_part(desk.furniture)
    assert geometry(document) == before


def test_sortie_refusee_d_une_piece_assemblee_a_un_membre_qui_reste(document: Any) -> None:
    """Le panneau refuse avant l'api ; l'api garde la pièce dans le Std Part (ADR 0038)."""
    desk = build_desk(document)
    messages = api.remove_from_furniture([desk.parts["JG"]], keep_properties=True)
    assert api.furniture_of(desk.parts["JG"]) is None
    assert holder(desk.parts["JG"]) == std_part(desk.furniture)
    assert messages  # avertissement : la pièce reste dans le Std Part
    assert stale_or_invalid(document) == []


# --- Renommer par l'api (M2) -------------------------------------------------------------------


def test_renommer_une_piece_usinee_change_le_libelle_de_la_brute(document: Any) -> None:
    desk = build_desk(document)
    machined = desk.shown("P")
    transaction(document, "Renommer", partial(api.rename, machined, "  Dessus  "))
    assert desk.parts["P"].Label == "Dessus"
    document.undo()
    assert desk.parts["P"].Label == "Plateau"


def test_renommer_un_ensemble_suit_dans_le_std_part(document: Any) -> None:
    desk = build_desk(document)
    api.rename(desk.furniture, "Établi")
    assert desk.furniture.Label == "Établi"
    assert stale_or_invalid(document) == []


@pytest.mark.parametrize("name", ["", "   ", "a\nb", "x" * 500])
def test_renommer_refuse_un_nom_invalide_sans_rien_changer(document: Any, name: str) -> None:
    desk = build_desk(document)
    with pytest.raises(ValueError):
        api.rename(desk.parts["P"], name)
    assert desk.parts["P"].Label == "Plateau"


def test_renommer_un_autre_objet_est_refuse(document: Any) -> None:
    desk = build_desk(document)
    with pytest.raises(TypeError):
        api.rename(std_part(desk.furniture), "Autre")


# --- Std Part et Origine : jamais « Autres objets » ni ensemble ---------------------------------


def nodes_of(document: Any) -> list[Any]:
    return [node for root in structure_source.structure_of(document) for node in root.walk()]


def check_no_std_part_row(document: Any) -> None:
    ignored = {
        obj.Name
        for obj in document.Objects
        if obj.TypeId == "App::Part" or obj.TypeId.startswith("App::Origin")
    }
    assert ignored  # le test ne vérifie rien sans Std Part
    assert not ignored & {obj.Name for obj in structure_foreign.foreign_objects(document)}
    facts = structure_facts.facts_of(document)
    assert not ignored & set(facts.furnitures) and not ignored & set(facts.labels)
    nodes = nodes_of(document)
    assert not ignored & {node.key for node in nodes}
    others = [node for node in nodes if node.kind is tree_module.NodeKind.OTHER]
    assert others == []


def test_std_part_et_origine_absents_du_panneau(document: Any) -> None:
    desk = build_desk(document)
    check_no_std_part_row(document)
    api.make_furniture([desk.shown(m) for m in ("JG", "JD", "V")], "Tiroir")  # imbriqué
    check_no_std_part_row(document)
    api.remove_from_furniture([desk.parts["P"]], keep_properties=True)
    check_no_std_part_row(document)


def test_les_ensembles_du_panneau_sont_ceux_de_l_atelier(document: Any) -> None:
    desk = build_desk(document)
    sub, _ = api.make_furniture([desk.shown(m) for m in ("JG", "JD", "V")], "Tiroir")
    facts = structure_facts.facts_of(document)
    assert set(facts.furnitures) == {desk.furniture.Name, sub.Name}
    assert facts.parent[sub.Name] == desk.furniture.Name
