# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseurs vivantes et pièces verrouillées dans l'ensemble (ADR 0019, critères D2 à D5)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import EXPRESSIONS, LAYOUT, Bureau
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

WIDTH_BLOCKED = "Impossible de changer la largeur de l'ensemble à 1300 mm"
THICKNESS_BLOCKED = "Impossible de changer l'épaisseur de « Joue gauche » à 25 mm"
RELINK = "utilisez « Relier les pièces »"


def snapshot(bureau: Bureau) -> dict[str, dict[str, str]]:
    return {mark: bureau.expressions(mark) for mark in LAYOUT}


# --- D2 : l'épaisseur d'une joue est vivante --------------------------------------------------


def test_epaisseur_de_la_joue_gauche(bureau: Bureau, vue_rapport: Any) -> None:
    vue_rapport.messages.clear()
    bureau.parts["JG"].Thickness = 25
    bureau.doc.recompute()
    assert bureau.bounds("JG")[0] == (0, 25)
    assert bureau.bounds("V")[0] == (25, 1178)
    assert bureau.sizes("V")[0] == 1153
    assert bureau.bounds("JD")[0] == (1178, 1200)
    assert bureau.furniture.Width.Value == 1200
    assert bureau.dowel_counts() == [4, 4]
    assert stale_or_invalid(bureau.doc) == []
    assert vue_rapport.de_niveau("Warning") == []
    assert snapshot(bureau) == EXPRESSIONS


def test_epaisseur_de_la_joue_droite(bureau: Bureau, vue_rapport: Any) -> None:
    vue_rapport.messages.clear()
    bureau.parts["JD"].Thickness = 25
    bureau.doc.recompute()
    assert bureau.bounds("JD")[0] == (1175, 1200)
    assert bureau.bounds("V")[0] == (22, 1175)
    assert bureau.sizes("V")[0] == 1153
    assert bureau.bounds("JG")[0] == (0, 22)
    assert bureau.furniture.Width.Value == 1200
    assert stale_or_invalid(bureau.doc) == []
    assert vue_rapport.de_niveau("Warning") == []


# --- D3 : seules les pièces pleine largeur changent de cote -----------------------------------


def test_largeur_du_bureau(bureau: Bureau) -> None:
    before = {mark: bureau.sizes(mark) for mark in LAYOUT}
    bureau.furniture.Width = 1400
    bureau.doc.recompute()
    after = {mark: bureau.sizes(mark) for mark in LAYOUT}
    assert [mark for mark in LAYOUT if after[mark] != before[mark]] == ["P", "V"]
    assert after["P"][0] == 1400
    assert after["V"][0] == 1356
    assert bureau.bounds("JD")[0] == (1378, 1400)
    assert stale_or_invalid(bureau.doc) == []


# --- D4 : pièce verrouillée, refus puis déverrouillage ----------------------------------------


def test_voile_verrouille_relie_tout_l_ensemble(bureau: Bureau) -> None:
    voile = bureau.parts["V"]
    api.set_member_options(voile, locked=True)
    assert voile.Locked is True
    expressions = bureau.expressions("V")
    assert "Length" not in expressions
    assert "Width" not in expressions
    assert expressions["Placement.Base.x"] == EXPRESSIONS["V"]["Placement.Base.x"]
    # La joue droite, qui suivait la largeur, suit désormais les épaisseurs et le voile.
    assert bureau.expressions("JD")["Placement.Base.x"] == (
        "<<Bureau>>.Origin.x + WoodPart001.Thickness + Thickness + 1156 mm"
    )
    api.set_member_options(voile, locked=False)
    assert snapshot(bureau) == EXPRESSIONS


def test_largeur_refusee_par_la_rangee_bloquee(bureau: Bureau) -> None:
    voile = bureau.parts["V"]
    api.set_member_options(voile, locked=True)
    api.resize_furniture(bureau.furniture, depth=800)  # la profondeur n'est pas bloquée
    assert bureau.bounds("V")[1] == (641, 659)
    before, sizes = snapshot(bureau), {mark: bureau.sizes(mark) for mark in LAYOUT}
    with pytest.raises(api.LockedPiecesError) as error:
        api.resize_furniture(bureau.furniture, width=1300)
    assert isinstance(error.value, ValueError)
    locked: Any = error.value
    assert locked.members == (voile,)
    assert WIDTH_BLOCKED in str(error.value)
    assert "cotes fixes : « Voile »" in str(error.value)
    assert bureau.furniture.Width.Value == 1200
    assert snapshot(bureau) == before
    assert {mark: bureau.sizes(mark) for mark in LAYOUT} == sizes


def test_deverrouiller_et_redimensionner(bureau: Bureau) -> None:
    voile = bureau.parts["V"]
    api.set_member_options(voile, locked=True)
    api.unlock_and_resize(bureau.furniture, [voile], width=1300)
    assert voile.Locked is False
    assert bureau.furniture.Width.Value == 1300
    assert snapshot(bureau) == EXPRESSIONS
    assert bureau.sizes("V")[0] == 1256
    assert bureau.bounds("JD")[0] == (1278, 1300)
    assert stale_or_invalid(bureau.doc) == []


def test_deverrouiller_et_changer_l_epaisseur(bureau: Bureau) -> None:
    voile, joue = bureau.parts["V"], bureau.parts["JG"]
    api.set_member_options(voile, locked=True)
    with pytest.raises(api.LockedPiecesError) as error:
        api.unlock_and_set_thickness(joue, 25, [])  # aucune pièce déverrouillée : toujours bloquée
    locked: Any = error.value
    assert locked.members == (voile,)
    assert THICKNESS_BLOCKED in str(error.value)
    assert joue.Thickness.Value == 22
    assert voile.Locked is True
    api.unlock_and_set_thickness(joue, 25, [voile])
    assert (joue.Thickness.Value, voile.Locked) == (25, False)
    bureau.doc.recompute()
    assert bureau.bounds("V")[0] == (25, 1178)
    assert stale_or_invalid(bureau.doc) == []


def test_deverrouiller_une_piece_hors_ensemble_est_refuse(bureau: Bureau, document: Any) -> None:
    alone = api.make_wood_part(doc=document)
    before = snapshot(bureau)
    with pytest.raises(ValueError, match="n'est membre d'aucun ensemble"):
        api.unlock_and_resize(bureau.furniture, [alone], width=1300)
    assert bureau.furniture.Width.Value == 1200
    assert snapshot(bureau) == before


def test_sans_pieces_verrouillees_rien_ne_change(bureau: Bureau) -> None:
    """Aucune pièce verrouillée au départ : le bureau se redimensionne comme avant."""
    assert all(part.Locked is False for part in bureau.parts.values())
    api.resize_furniture(bureau.furniture, width=1300)
    assert bureau.furniture.Width.Value == 1300


def test_epaisseur_controlee_par_le_panneau(bureau: Bureau, document: Any) -> None:
    """``set_member_thickness`` (panneau de la pièce, G3) : contrôle puis écrit ; refus avant
    toute écriture si la rangée est bloquée ; une pièce hors ensemble est simplement écrite."""
    from freecad.menuiserie.features.furniture_locks import set_member_thickness

    joue, voile = bureau.parts["JG"], bureau.parts["V"]
    set_member_thickness(joue, 25.0)
    assert joue.Thickness.Value == 25
    api.set_member_options(voile, locked=True)
    with pytest.raises(api.LockedPiecesError) as error:
        set_member_thickness(joue, 30.0)
    locked: Any = error.value
    assert locked.members == (voile,)
    assert joue.Thickness.Value == 25
    alone = api.make_wood_part(doc=document)
    assert set_member_thickness(alone, 40.0) == []
    assert alone.Thickness.Value == 40


# --- D5 : saisies de l'éditeur de propriétés --------------------------------------------------


def test_verrou_saisi_dans_l_editeur(bureau: Bureau, vue_rapport: Any) -> None:
    voile = bureau.parts["V"]
    vue_rapport.messages.clear()
    voile.Locked = True
    expressions = bureau.expressions("V")
    assert "Length" not in expressions
    assert "Width" not in expressions
    warnings = vue_rapport.de_niveau("Warning")
    assert any(RELINK in text for text in warnings)  # la joue droite est à refaire
    api.rebind_furniture(bureau.furniture)
    assert bureau.expressions("JD")["Placement.Base.x"].endswith("+ 1156 mm")


def test_largeur_saisie_dans_une_rangee_bloquee(bureau: Bureau, vue_rapport: Any) -> None:
    api.set_member_options(bureau.parts["V"], locked=True)
    vue_rapport.messages.clear()
    bureau.furniture.Width = 1300
    assert bureau.furniture.Width.Value == 1300  # appliquée (Q4)
    warnings = vue_rapport.de_niveau("Warning")
    assert any(WIDTH_BLOCKED in text for text in warnings)


def test_epaisseur_saisie_dans_une_rangee_bloquee(bureau: Bureau, vue_rapport: Any) -> None:
    api.set_member_options(bureau.parts["V"], locked=True)
    vue_rapport.messages.clear()
    bureau.parts["JG"].Thickness = 25
    assert bureau.parts["JG"].Thickness.Value == 25  # appliquée
    warnings = vue_rapport.de_niveau("Warning")
    assert any(THICKNESS_BLOCKED in text for text in warnings)


def test_epaisseur_saisie_qui_casse_un_assemblage(bureau: Bureau, vue_rapport: Any) -> None:
    vue_rapport.messages.clear()
    bureau.parts["JG"].Thickness = 1190  # le voile n'aurait plus de longueur : appliquée, avertie
    assert bureau.parts["JG"].Thickness.Value == 1190
    warnings = vue_rapport.de_niveau("Warning")
    assert any("« Voile » deviendrait trop petite" in text for text in warnings)
