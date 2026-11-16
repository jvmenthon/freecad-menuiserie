# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de l'ADR 0062 : réouverture, assemblage entre pièces empilées, saisie caractère
par caractère, cote trop petite, sous-ensemble membre."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.test_ensemble_epaisseurs_au_prorata import empilees, etat

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")


def test_reouverture_apres_changement_de_hauteur(
    document: Any, rouvrir: Callable[[Any], Any]
) -> None:
    furniture, fond, dessus = empilees(document)
    api.resize_furniture(furniture, height=50)
    document.recompute()
    names = (furniture.Name, fond.Name, dessus.Name)
    doc = rouvrir(document)
    furniture, fond, dessus = (doc.getObject(name) for name in names)
    assert stale_or_invalid(doc) == []
    assert etat(fond, dessus) == (27.5, 22.5, 0.0, 27.5, 50.0)
    assert furniture.Height.Value == pytest.approx(50.0)
    api.resize_furniture(furniture, height=20)  # les liaisons ont survécu
    doc.recompute()
    assert etat(fond, dessus) == (11.0, 9.0, 0.0, 11.0, 20.0)


@pytest.mark.parametrize("maker", ["make_biscuits", "make_loose_tenons"])
def test_assemblage_entre_pieces_empilees_suit(document: Any, maker: str) -> None:
    furniture, fond, dessus = empilees(document)
    joint = getattr(api, maker)(fond, dessus)
    document.recompute()
    assert stale_or_invalid(document) == []
    api.resize_furniture(furniture, height=50)
    document.recompute()
    assert etat(fond, dessus) == (27.5, 22.5, 0.0, 27.5, 50.0)
    assert stale_or_invalid(document) == []
    assert "Invalid" not in joint.State


def test_saisie_caractere_par_caractere(document: Any) -> None:
    """Le panneau applique 5, puis 50 : le résultat final est celui d'un seul 50."""
    furniture, fond, dessus = empilees(document)
    for text in (5, 50):
        furniture.Height = text
        document.recompute()
        assert stale_or_invalid(document) == []
    assert etat(fond, dessus) == (27.5, 22.5, 0.0, 27.5, 50.0)


def test_saisie_passant_par_une_cote_trop_petite(document: Any, vue_rapport: Any) -> None:
    """Saisie « 0,3 » avant « 30 » : l'étape refusée ne doit pas laisser les épaisseurs
    et la cote en désaccord au point de fausser la saisie suivante."""
    furniture, fond, dessus = empilees(document)
    furniture.Height = 0.3  # 0,3 x 22 / 40 = 0,165 : ok ; 0,3 x 18 / 40 = 0,135 : ok
    document.recompute()
    furniture.Height = 0.1  # fond 0,055 mm : sous 0,1 mm
    document.recompute()
    furniture.Height = 30
    document.recompute()
    assert stale_or_invalid(document) == []
    assert fond.Thickness.Value + dessus.Thickness.Value == pytest.approx(30.0)
    assert fond.Thickness.Value / dessus.Thickness.Value == pytest.approx(22 / 18)


def test_cote_trop_petite_par_l_api_ne_change_rien(document: Any) -> None:
    furniture, fond, dessus = empilees(document)
    with pytest.raises(ValueError):
        api.resize_furniture(furniture, height=0.1)
    assert etat(fond, dessus) == (22.0, 18.0, 0.0, 22.0, 40.0)
    assert furniture.Height.Value == pytest.approx(40.0)


def test_annuler_la_saisie_de_l_editeur(document: Any) -> None:
    document.UndoMode = 1
    furniture, fond, dessus = empilees(document)
    document.clearUndos()
    document.openTransaction("Saisie")
    furniture.Height = 50
    document.commitTransaction()
    document.recompute()
    document.undo()
    document.recompute()
    assert etat(fond, dessus) == (22.0, 18.0, 0.0, 22.0, 40.0)
    assert furniture.Height.Value == pytest.approx(40.0)
    document.redo()
    document.recompute()
    assert etat(fond, dessus) == (27.5, 22.5, 0.0, 27.5, 50.0)
    document.clearUndos()


def test_deverrouiller_et_appliquer_annulable_en_un_coup(document: Any) -> None:
    document.UndoMode = 1
    furniture, fond, dessus = empilees(document)
    dessus.Locked = True
    document.recompute()
    document.clearUndos()
    document.openTransaction("Déverrouiller")
    api.unlock_and_resize(furniture, [dessus], height=50)
    document.commitTransaction()
    document.recompute()
    document.undo()
    document.recompute()
    assert etat(fond, dessus) == (22.0, 18.0, 0.0, 22.0, 40.0)
    assert dessus.Locked is True
    document.clearUndos()


def test_piece_en_bois_a_cotes_dessinees_refuse(document: Any) -> None:
    """Rien n'est écrit si la pièce d'une des couches est dessinée : refus inchangé."""
    furniture, fond, dessus = empilees(document)
    dessus.Locked = True
    document.recompute()
    with pytest.raises(ValueError):
        api.resize_furniture(furniture, height=50)
    assert furniture.Height.Value == pytest.approx(40.0)
    assert etat(fond, dessus) == (22.0, 18.0, 0.0, 22.0, 40.0)


def test_sous_ensemble_seul_dans_l_ensemble(document: Any) -> None:
    """Le sous-ensemble suit son parent par expression : on ne change pas les épaisseurs
    de ses planches en cachette ; la cote est soit refusée, soit suivie sans toucher aux
    épaisseurs, mais jamais à moitié écrite."""
    inner, fond, dessus = empilees(document)
    outer, _ = api.make_furniture([inner], label="Parent")
    document.recompute()
    before = (outer.Height.Value, inner.Height.Value, etat(fond, dessus))
    try:
        api.resize_furniture(outer, height=50)
    except ValueError:
        assert (outer.Height.Value, inner.Height.Value, etat(fond, dessus)) == before
    else:
        document.recompute()
        assert stale_or_invalid(document) == []
        assert outer.Height.Value == pytest.approx(inner.Height.Value)
        assert (fond.Thickness.Value, dessus.Thickness.Value) in {(22.0, 18.0), (27.5, 22.5)}
        top = max(dessus.Shape.BoundBox.ZMax, fond.Shape.BoundBox.ZMax)
        assert top <= outer.Height.Value + 1e-6


def test_planches_cote_a_cote_dans_une_couche_par_l_api(document: Any) -> None:
    g = api.make_wood_part(300, 400, 22, "chene", mark="G", doc=document)
    d = api.make_wood_part(300, 400, 22, "chene", mark="D", doc=document)
    d.Placement = App.Placement(App.Vector(300, 0, 0), App.Rotation())
    t = api.make_wood_part(600, 400, 18, "chene", mark="T", doc=document)
    t.Placement = App.Placement(App.Vector(0, 0, 22), App.Rotation())
    document.recompute()
    furniture, _ = api.make_furniture([g, d, t], label="Deux couches")
    document.recompute()
    api.resize_furniture(furniture, height=50)
    document.recompute()
    assert stale_or_invalid(document) == []
    assert (g.Thickness.Value, d.Thickness.Value, t.Thickness.Value) == pytest.approx(
        (27.5, 27.5, 22.5)
    )
    assert t.Shape.BoundBox.ZMin == pytest.approx(27.5)


def test_saisie_commencant_par_zero_puis_cote_valide(document: Any) -> None:
    """« 0 » (début de « 0,5 » ou champ vidé) est refusé ; la cote valide qui suit doit
    de nouveau faire suivre les épaisseurs au prorata."""
    furniture, fond, dessus = empilees(document)
    for height in (0, 50):
        furniture.Height = height
        document.recompute()
    assert fond.Thickness.Value + dessus.Thickness.Value == pytest.approx(50.0)
