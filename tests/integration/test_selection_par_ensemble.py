# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chaîne d'ensembles d'une pièce pour la sélection dans la vue 3D (ADR 0048) : non-régression."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import build_parts
from tests.integration.test_ensemble_membres import caisson

pytestmark = pytest.mark.integration

api = pytest.importorskip("freecad.menuiserie.api")
chain = pytest.importorskip("freecad.menuiserie.features.selection_chain")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
rules = pytest.importorskip("freecad.menuiserie.core.selection_chain")


def names(objects: list[Any]) -> list[str]:
    return [obj.Name for obj in objects]


def meuble(document: Any) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Bureau qui contient le sous-ensemble Caisson : (bureau, caisson, plateau, pièces du
    caisson)."""
    bureau = build_parts(document)
    sub, parts = caisson(document)
    furniture, _ = api.make_furniture(
        [*(bureau.parts[mark] for mark in ("P", "JG", "JD")), sub], label="Bureau"
    )
    return furniture, sub, bureau.parts["P"], parts


def test_piece_libre_sans_chaine(document: Any) -> None:
    piece = api.make_wood_part(500, 300, 18, "chene", doc=document)
    document.recompute()
    assert chain.selection_chain_of(piece) == []


def test_chaine_d_une_piece_et_de_sa_piece_usinee(document: Any) -> None:
    furniture, sub, plateau, parts = meuble(document)
    assert names(chain.selection_chain_of(plateau)) == [furniture.Name, plateau.Name]
    bottom = parts["CB"]
    expected = [furniture.Name, sub.Name, bottom.Name]
    assert names(chain.selection_chain_of(bottom)) == expected
    machined = api.machined_part_of(bottom)
    if machined is not None:  # la pièce visible est l'usinée : même chaîne (brute en dernier)
        assert names(chain.selection_chain_of(machined)) == expected
    assert names(chain.selection_chain_of(sub)) == [furniture.Name, sub.Name]
    assert chain.selection_chain_of(furniture) == []  # ensemble de plus haut niveau


def test_normalise_std_part_et_piece_usinee(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    assert chain.normalized(container.std_part_of(furniture)) == furniture
    assert chain.normalized(container.std_part_of(sub)) == sub
    machined = api.machined_part_of(parts["CG"])
    if machined is not None:
        assert chain.normalized(machined) == parts["CG"]


def test_parcours_complet_descente_et_remontee(document: Any) -> None:
    """Clic, double-clics jusqu'à la pièce, double-clic de plus (panneau), remontée."""
    furniture, sub, _, parts = meuble(document)
    keys = names(chain.selection_chain_of(parts["CB"]))
    current = rules.click_target(keys, None)
    assert current == furniture.Name
    current = rules.double_click_target(keys, current)
    assert current == sub.Name
    assert rules.click_target(keys, current) == sub.Name  # clic simple dans le tiroir : inchangé
    current = rules.double_click_target(keys, current)
    assert current == parts["CB"].Name
    assert rules.double_click_target(keys, current) is None  # panneau de la pièce
    up = rules.up_target(names(chain.selection_chain_of(parts["CB"])))
    assert up == sub.Name
    assert rules.up_target(names(chain.selection_chain_of(sub))) == furniture.Name


# --- Cas limites : lecture seule, enregistrement, annulation, suppression ---------------------


def etat(document: Any) -> list[tuple[str, tuple[str, ...]]]:
    return sorted((obj.Name, tuple(obj.PropertiesList)) for obj in document.Objects)


def test_la_chaine_n_ecrit_rien_dans_le_document(document: Any) -> None:
    """ADR 0007 : aucun objet, propriété ni transaction ; la chaîne est une simple lecture."""
    furniture, sub, plateau, parts = meuble(document)
    avant = etat(document)
    undo_avant = document.UndoCount
    for obj in (furniture, sub, plateau, parts["CB"]):
        chain.selection_chain_of(obj)
        chain.normalized(obj)
    assert etat(document) == avant
    assert document.UndoCount == undo_avant


def test_chaine_apres_enregistrement_et_reouverture(document: Any, rouvrir: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    top = furniture.Name  # les objets Python du document fermé deviennent inaccessibles
    attendu = {
        parts["CB"].Name: [top, sub.Name, parts["CB"].Name],
        sub.Name: [top, sub.Name],
    }
    rouvert = rouvrir(document)
    for name, expected in attendu.items():
        assert names(chain.selection_chain_of(rouvert.getObject(name))) == expected
    assert chain.selection_chain_of(rouvert.getObject(top)) == []


def test_chaine_apres_annulation_et_retablissement_du_regroupement(document: Any) -> None:
    bureau = build_parts(document)
    pieces = [bureau.parts[mark] for mark in ("P", "JG", "JD")]
    document.UndoMode = 1  # annulation désactivée par défaut dans les documents de test
    document.clearUndos()
    document.openTransaction("Regrouper")
    furniture, _ = api.make_furniture(pieces, label="Bureau")
    document.commitTransaction()
    assert names(chain.selection_chain_of(pieces[0])) == [furniture.Name, pieces[0].Name]
    name, piece_name = furniture.Name, pieces[0].Name
    document.undo()
    assert chain.selection_chain_of(document.getObject(piece_name)) == []  # pièce redevenue libre
    document.redo()
    assert names(chain.selection_chain_of(document.getObject(piece_name))) == [name, piece_name]


def test_chaine_apres_suppression_du_sous_ensemble_et_de_la_piece(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    document.UndoMode = 1
    document.clearUndos()
    bottom_name, removed = parts["CB"].Name, parts["CG"].Name  # lus avant la suppression
    document.openTransaction("Supprimer")
    document.removeObject(removed)
    document.commitTransaction()
    # Les autres membres gardent leur chaîne.
    assert names(chain.selection_chain_of(document.getObject(bottom_name))) == [
        furniture.Name,
        sub.Name,
        bottom_name,
    ]
    document.undo()
    assert document.getObject(removed) is not None


def test_chaine_sans_cycle_ni_doublon(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    keys = names(chain.selection_chain_of(parts["CB"]))
    assert len(keys) == len(set(keys))
    assert keys[0] == furniture.Name
    assert chain.selection_chain_of(furniture) == []
    assert rules.double_click_target(keys, furniture.Name) == sub.Name
    assert rules.up_target(names(chain.selection_chain_of(furniture))) is None


# --- ADR 0049 : cotes du parent recalées sur l'enveloppe de ses membres ------------------------

drag = pytest.importorskip("freecad.menuiserie.features.furniture_drag")
envelope = pytest.importorskip("freecad.menuiserie.features.furniture_envelope")


def global_boxes(document: Any, skip: set[str]) -> dict[str, tuple[float, ...]]:
    """Boîtes globales arrondies des objets à forme, sauf ``skip``."""
    found = {}
    for obj in document.Objects:
        if obj.Name in skip or obj.TypeId != "Part::FeaturePython" or obj.Shape.isNull():
            continue
        shape = obj.Shape.copy()
        shape.Placement = obj.getGlobalPlacement()
        b = shape.BoundBox
        found[obj.Name] = tuple(
            round(v, 3) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)
        )
    return found


def sizes(furniture: Any) -> tuple[float, ...]:
    origin = furniture.Origin
    return tuple(
        round(v, 3)
        for v in (
            origin.x,
            origin.y,
            origin.z,
            furniture.Width.Value,
            furniture.Depth.Value,
            furniture.Height.Value,
        )
    )


def assert_enveloppe(furniture: Any) -> None:
    box = envelope.member_envelope(furniture)
    expected = (*(box.lo(i) for i in range(3)), *(box.size(i) for i in range(3)))
    assert sizes(furniture) == pytest.approx(expected, abs=1e-3)


def caisson_names(parts: dict[str, Any]) -> set[str]:
    """Brutes et pièces usinées du caisson (celles qui bougent avec lui)."""
    found = {part.Name for part in parts.values()}
    found |= {m.Name for part in parts.values() if (m := api.machined_part_of(part)) is not None}
    return found


def test_sous_ensemble_deplace_hors_du_parent_l_agrandit(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    skip = caisson_names(parts)
    others = global_boxes(document, skip)
    width = furniture.Width.Value
    assert api.move_furniture(sub, (900, 0, 0))
    document.recompute()
    # Le plateau va de 0 à 1200, le caisson sorti à droite finit à 1340 : le parent s'agrandit.
    assert furniture.Width.Value > width + 100
    assert_enveloppe(furniture)
    assert global_boxes(document, skip) == others  # les autres pièces ne bougent pas
    assert names(chain.selection_chain_of(parts["CB"]))[0] == furniture.Name


def test_sous_ensemble_deplace_a_gauche_decale_l_origine(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    skip = caisson_names(parts)
    others = global_boxes(document, skip)
    x0 = furniture.Origin.x
    assert api.move_furniture(sub, (-700, 0, 0))
    document.recompute()
    assert furniture.Origin.x < x0 - 600
    assert_enveloppe(furniture)
    assert global_boxes(document, skip) == others


def test_sous_ensemble_tourne_le_parent_englobe_la_rotation(document: Any) -> None:
    furniture, sub, _, _ = meuble(document)
    memento = drag.begin_furniture_drag(sub)
    assert drag.rotate_furniture_by(memento, 2, 30.0)
    drag.end_furniture_drag(memento)
    document.recompute()
    assert_enveloppe(furniture)


def test_enveloppe_deja_juste_rien_n_est_ecrit(document: Any) -> None:
    furniture, _, _, _ = meuble(document)
    if envelope.reframe(furniture):  # première fois : recalage éventuel de la création
        document.recompute()
    assert envelope.reframe(furniture) is False


def test_sous_ensemble_n_est_jamais_recale(document: Any) -> None:
    _, sub, _, _ = meuble(document)
    assert envelope.reframe(sub) is False


def test_creation_autour_d_un_ensemble_tourne_l_englobe(document: Any) -> None:
    """Non-régression (jv, 2026-11-11) : un ensemble créé autour d'un ensemble tourné doit
    englober sa rotation dès la création."""
    bureau = build_parts(document)
    sub, _ = caisson(document)
    memento = drag.begin_furniture_drag(sub)
    assert drag.rotate_furniture_by(memento, 2, 45.0)
    drag.end_furniture_drag(memento)
    document.recompute()
    furniture, _ = api.make_furniture([bureau.parts["P"], sub], label="Meuble")
    document.recompute()
    assert_enveloppe(furniture)


def test_le_parent_retrecit_quand_on_ramene_le_sous_ensemble(document: Any) -> None:
    """jv, 2026-11-11 : « la boîte doit toujours être de la taille de l'ensemble », sans marge.
    Ramener le sous-ensemble rend au parent ses cotes de départ."""
    furniture, sub, _, _ = meuble(document)
    depart = sizes(furniture)
    assert api.move_furniture(sub, (900, 0, 0))
    document.recompute()
    assert sizes(furniture) != depart
    assert api.move_furniture(sub, (-900, 0, 0))
    document.recompute()
    assert sizes(furniture) == pytest.approx(depart, abs=1e-3)
    assert_enveloppe(furniture)


def test_repetition_qui_suit_le_parent_ne_bouge_pas(document: Any) -> None:
    """Revue B1 : une répétition « Suivre le redimensionnement » lit les cotes du parent ;
    le recaler redistribuerait ses copies. Le parent n'est donc pas recalé : rien ne bouge."""
    bureau = build_parts(document)
    sub, parts = caisson(document)
    furniture, _ = api.make_furniture(
        [*(bureau.parts[mark] for mark in ("P", "JG", "JD")), sub], label="Bureau"
    )
    rep = api.make_repeat(
        [bureau.parts["JG"]], api.RepeatParams(count=1, step=300.0, axis="X", follow_resize=True)
    )
    document.recompute()
    skip = caisson_names(parts)
    others = global_boxes(document, skip)
    avant = sizes(furniture)
    assert api.move_furniture(sub, (900, 0, 0))
    document.recompute()
    assert sizes(furniture) == avant
    assert global_boxes(document, skip) == others  # copies de la répétition comprises
    assert rep.Document is not None


def test_copies_d_un_sous_ensemble_repete_englobees(document: Any) -> None:
    """Revue M1 : les copies d'un sous-ensemble répété suivent leur source par expression ;
    l'enveloppe est calculée après leur recalcul, pas à leur ancienne place."""
    furniture, sub, _, _ = meuble(document)
    api.make_repeat([sub], api.RepeatParams(count=1, step=500.0, axis="X"))
    document.recompute()
    assert api.move_furniture(sub, (900, 0, 0))
    document.recompute()
    assert_enveloppe(furniture)
