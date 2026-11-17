# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce d'ensemble assemblée : mêmes choix qu'une pièce seule, puis l'ensemble
est relié d'après le résultat (ADR 0060, jv 2026-11-17).

Bureau de référence : joue gauche « JG » (22 mm, x de 0 à 22), voile « V » entre les joues,
tourillons JG-V et JD-V ; ensemble de 1200 mm de large.
"""

from __future__ import annotations

from typing import Any

import pytest

App = pytest.importorskip("FreeCAD")
choice = pytest.importorskip("freecad.menuiserie.features.thickness_choice")
base = pytest.importorskip("freecad.menuiserie.features.joints.base")
bindings = pytest.importorskip("freecad.menuiserie.features.furniture_bindings")
common = pytest.importorskip("freecad.menuiserie.features.thickness_common")
furniture = pytest.importorskip("freecad.menuiserie.features.furniture")

pytestmark = pytest.mark.integration

Choice = choice.Choice


def _state(bureau: Any) -> dict[str, tuple[Any, ...]]:
    return {
        mark: (
            tuple(round(v, 6) for v in part.Placement.Base),
            part.Length.Value,
            part.Width.Value,
            part.Thickness.Value,
        )
        for mark, part in bureau.parts.items()
    }


def _all_hold(document: Any) -> bool:
    for obj in document.Objects:
        if base.is_joint(obj):
            try:
                base.plan_for(obj)
            except ValueError:
                return False
    return True


@pytest.fixture
def bureau(document: Any) -> Any:
    from tests.integration.bureau import build_desk

    return build_desk(document)


def test_piece_d_ensemble_assemblee_a_les_choix(bureau: Any) -> None:
    joue = bureau.parts["JG"]
    assert common.offers_thickness_choice(joue)
    assert not common.offers_thickness_choice(bureau.parts["P"])  # plateau sans assemblage
    edit = choice.ThicknessEdit(joue)
    conflict = edit.probe(30)
    assert conflict is not None
    assert [o.choice for o in conflict.options] == [
        Choice.AS_TYPED,
        Choice.OTHER_SIDE,
        Choice.EXTEND,
        Choice.REVERT,
    ]
    offered = {o.choice: o.reason for o in conflict.options}
    assert offered[Choice.AS_TYPED] is None and offered[Choice.OTHER_SIDE] is None
    assert "membre d'un ensemble" not in (offered[Choice.EXTEND] or "")
    edit.restore()
    edit.finish()


def test_piece_a_cotes_fixes_garde_le_comportement_de_l_ensemble(bureau: Any) -> None:
    joue = bureau.parts["JG"]
    joue.Locked = True
    assert not common.offers_thickness_choice(joue)


@pytest.mark.parametrize("picked", [Choice.AS_TYPED, Choice.OTHER_SIDE])
def test_choix_puis_ensemble_relie_d_apres_le_resultat(
    bureau: Any, document: Any, picked: Any
) -> None:
    joue = bureau.parts["JG"]
    edit = choice.ThicknessEdit(joue)
    assert edit.probe(30) is not None
    edit.apply(30, picked)
    before = _state(bureau)
    edit.finish()
    assert edit.finish() == []  # une seule fois
    document.recompute()
    assert _state(bureau) == before  # liaisons refaites d'après la géométrie : rien ne bouge
    assert joue.Thickness.Value == 30
    assert bureau.furniture.Width.Value == pytest.approx(1208)  # boîte à l'enveloppe
    assert _all_hold(document)
    assert bindings.workshop_expressions(bureau.parts["V"])  # liaisons rendues aux membres


def test_choix_de_l_autre_cote_pousse_les_pieces_assemblees(bureau: Any) -> None:
    joue, voile, droite = (bureau.parts[m] for m in ("JG", "V", "JD"))
    x_voile, x_droite = voile.Placement.Base.x, droite.Placement.Base.x
    edit = choice.ThicknessEdit(joue)
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)
    assert voile.Placement.Base.x == pytest.approx(x_voile + 8)
    assert droite.Placement.Base.x == pytest.approx(x_droite + 8)
    edit.finish()


def test_saisie_trop_mince_rien_d_ecrit_puis_relie(bureau: Any, document: Any) -> None:
    joue = bureau.parts["JG"]
    start = _state(bureau)
    edit = choice.ThicknessEdit(joue)
    conflict = edit.probe(10)  # tourillons trop profonds pour 10 mm
    assert conflict is not None and conflict.preferred() is None
    assert _state(bureau) == start
    edit.finish()
    document.recompute()
    assert _state(bureau) == start
    assert _all_hold(document)


def test_liaisons_mises_de_cote_pendant_les_saisies(bureau: Any) -> None:
    voile = bureau.parts["V"]
    assert bindings.workshop_expressions(voile)
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    assert not bindings.workshop_expressions(voile)
    edit.finish()
    assert bindings.workshop_expressions(voile)


def test_membre_bloque_hors_de_son_ensemble_libere(bureau: Any) -> None:
    joue = bureau.parts["JG"]
    reason = common.blocker(joue, ("Length",))
    assert reason is not None and "membre d'un ensemble" in reason
    edit = choice.ThicknessEdit(joue)  # liaisons de l'atelier mises de côté
    assert common.blocker(joue, ("Length",), bureau.furniture) is None
    with furniture.writing(joue):  # sans relier l'ensemble
        joue.Locked = True
    locked = common.blocker(joue, ("Length",), bureau.furniture)
    assert locked is not None and "cotes fixes" in locked
    assert common.blocker(joue, ("Placement",), bureau.furniture) is None
    edit.finish()


# --- Cas limites : revue du testeur (jv, 2026-11-17) ----------------------------------------------


def _bindings(bureau: Any) -> dict[str, dict[str, str]]:
    return {mark: dict(bindings.workshop_expressions(p)) for mark, p in bureau.parts.items()}


def _snapshot(bureau: Any) -> tuple[Any, ...]:
    """Cotes, placements, liaisons, expressions et boîte de l'ensemble."""
    engines = {m: sorted((k, t) for k, t in p.ExpressionEngine) for m, p in bureau.parts.items()}
    frame = (bureau.furniture.Width.Value, bureau.furniture.Origin.x)
    return (_state(bureau), _bindings(bureau), engines, frame)


@pytest.mark.parametrize("value", [0, -5, 1e-9, 1e7, float("nan")])
def test_epaisseur_invalide_rien_d_ecrit_ensemble_relie(
    bureau: Any, document: Any, value: float
) -> None:
    joue = bureau.parts["JG"]
    start = _snapshot(bureau)
    edit = choice.ThicknessEdit(joue)
    with pytest.raises(ValueError, match="Cote invalide"):
        edit.probe(value)
    edit.finish()
    document.recompute()
    assert _snapshot(bureau) == start
    assert _all_hold(document)


def test_saisies_successives_sans_cumul(bureau: Any, document: Any) -> None:
    joue, voile, droite = (bureau.parts[m] for m in ("JG", "V", "JD"))
    x_voile, x_droite = voile.Placement.Base.x, droite.Placement.Base.x
    edit = choice.ThicknessEdit(joue)
    for value in (30, 40, 25):
        assert edit.probe(value) is not None
        edit.apply(value, Choice.OTHER_SIDE)
    assert voile.Placement.Base.x == pytest.approx(x_voile + 3)
    assert droite.Placement.Base.x == pytest.approx(x_droite + 3)
    edit.finish()
    document.recompute()
    assert bureau.furniture.Width.Value == pytest.approx(1203)
    assert _all_hold(document)


def test_deux_suites_de_saisies_se_suivent(bureau: Any, document: Any) -> None:
    """« Autre cote » (``forget``) relie l'ensemble ; la suite suivante repart de cet état."""
    joue = bureau.parts["JG"]
    for value, width in ((30, 1208), (34, 1212)):
        edit = choice.ThicknessEdit(joue)
        assert not bindings.workshop_expressions(bureau.parts["V"])
        edit.probe(value)
        edit.apply(value, Choice.OTHER_SIDE)
        edit.finish()
        document.recompute()
        assert bureau.furniture.Width.Value == pytest.approx(width)
        assert bindings.workshop_expressions(bureau.parts["V"])
        assert _all_hold(document)


def test_revenir_rend_des_liaisons_identiques_a_celles_du_depart(
    bureau: Any, document: Any
) -> None:
    start = _snapshot(bureau)
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)
    edit.apply(22, Choice.REVERT)
    edit.finish()
    document.recompute()
    assert _snapshot(bureau) == start


def test_annuler_puis_retablir_apres_ok(bureau: Any, document: Any) -> None:
    """Une seule transaction : une annulation rend tout (liaisons comprises), le
    rétablissement remet le résultat."""
    document.UndoMode = 1
    document.clearUndos()
    start = _snapshot(bureau)
    document.openTransaction("Modifier une pièce de bois")
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)
    edit.finish()
    document.commitTransaction()
    document.recompute()
    final = _snapshot(bureau)
    assert final != start and len(document.UndoNames) == 1
    document.undo()
    document.recompute()
    assert _snapshot(bureau) == start
    document.redo()
    document.recompute()
    assert _snapshot(bureau) == final
    assert _all_hold(document)


def test_annuler_la_transaction_sans_finish_rend_les_liaisons(bureau: Any, document: Any) -> None:
    """« Annuler » du panneau : transaction abandonnée alors que les liaisons étaient de côté."""
    document.UndoMode = 1
    document.clearUndos()
    start = _snapshot(bureau)
    document.openTransaction("Modifier une pièce de bois")
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)
    document.abortTransaction()
    document.recompute()
    assert _snapshot(bureau) == start


def test_sauvegarde_et_reouverture_apres_le_choix(bureau: Any, document: Any, rouvrir: Any) -> None:
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)
    edit.finish()
    document.recompute()
    names = {mark: part.Name for mark, part in bureau.parts.items()}
    furniture_name = bureau.furniture.Name
    before = _snapshot(bureau)
    reopened = rouvrir(document)
    reopened.recompute()
    bureau.doc = reopened
    bureau.parts = {mark: reopened.getObject(name) for mark, name in names.items()}
    bureau.furniture = reopened.getObject(furniture_name)
    assert _snapshot(bureau) == before
    assert _all_hold(reopened)
    # la réouverture donne un ensemble qui se redimensionne encore par ses liaisons
    bureau.furniture.Width = 1300
    reopened.recompute()
    assert bureau.parts["JD"].Placement.Base.x == pytest.approx(1300)


def test_exception_pendant_finish_ne_perd_pas_les_liaisons(
    bureau: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``bind_furniture`` échoue : les membres ne doivent pas rester sans aucune liaison ; la
    fin des saisies se rejoue (ou les liaisons de départ sont rendues)."""
    member = pytest.importorskip("freecad.menuiserie.features.thickness_member")
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)

    def failing(_furniture: Any) -> Any:
        raise ValueError("panne simulée")

    monkeypatch.setattr(member, "bind_furniture", failing)
    with pytest.raises(ValueError, match="panne simulée"):
        edit.finish()
    monkeypatch.undo()
    edit.finish()
    assert all(_bindings(bureau).values())


def test_piece_supprimee_pendant_les_saisies(bureau: Any, document: Any) -> None:
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)
    document.removeObject(bureau.parts["P"].Name)  # membre sans assemblage
    edit.finish()
    document.recompute()
    assert bindings.workshop_expressions(bureau.parts["V"])
    assert bureau.parts["JG"].Thickness.Value == 30


def test_ensemble_pilote_par_une_formule_n_est_pas_recale(bureau: Any, document: Any) -> None:
    """Boîte pilotée par l'utilisateur : ``reframe`` refuse, la géométrie choisie est gardée et
    les membres sont reliés à la boîte inchangée."""
    bureau.furniture.setExpression("Width", "1200 mm")
    document.recompute()
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)
    placed = _state(bureau)
    edit.finish()
    document.recompute()
    assert bureau.furniture.Width.Value == pytest.approx(1200)
    assert dict(bureau.furniture.ExpressionEngine)["Width"] == "1200 mm"
    assert _state(bureau) == placed
    assert bindings.workshop_expressions(bureau.parts["V"])
    assert _all_hold(document)


def test_voisin_a_cotes_fixes_est_deplace_mais_pas_prolonge(bureau: Any, document: Any) -> None:
    voile = bureau.parts["V"]
    api = pytest.importorskip("freecad.menuiserie.api")
    api.set_member_options(voile, locked=True)
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)  # le voile garde ses cotes : il est seulement poussé
    assert voile.Length.Value == pytest.approx(1156)
    assert voile.Placement.Base.x == pytest.approx(30)
    edit.finish()
    document.recompute()
    assert voile.Length.Value == pytest.approx(1156)
    assert _all_hold(document)


def test_prolonger_refuse_si_le_voisin_a_des_cotes_fixes(document: Any) -> None:
    from tests.integration.test_epaisseur_cote import corner

    api = pytest.importorskip("freecad.menuiserie.api")
    host, guest, _joint = corner(document)
    api.make_furniture([host, guest], label="F")
    api.set_member_options(host, locked=True)
    edit = choice.ThicknessEdit(guest)
    conflict = edit.probe(30)
    assert conflict is not None
    reasons = {o.choice: o.reason for o in conflict.options}
    assert "cotes fixes" in (reasons[Choice.EXTEND] or "")
    with pytest.raises(choice.UnavailableError):
        edit.apply(30, Choice.EXTEND)
    assert host.Length.Value == 400  # état de départ rendu
    edit.finish()


def test_distance_gardee_de_l_ensemble_reste_valide(bureau: Any, document: Any) -> None:
    from tests.integration.test_distance_gardee import keep

    distance = keep(bureau)
    for mark in ("JG", "V"):
        edit = choice.ThicknessEdit(bureau.parts[mark])
        conflict = edit.probe(30)
        assert conflict is not None
        edit.apply(30, Choice.OTHER_SIDE)
        edit.finish()
        document.recompute()
        assert distance.Value.Value == pytest.approx(320)
        assert bureau.parts["V"].Placement.Base.z == pytest.approx(320)
        assert _all_hold(document)
        assert bindings.workshop_expressions(bureau.parts["V"])


def test_sous_ensemble_est_relie_sans_recaler_sa_boite(document: Any) -> None:
    """Côté du caisson, assemblé au dessous, épaissi vers l'extérieur : le caisson est relié
    d'après le résultat, sa boîte n'est pas recalée (ADR 0049 : un sous-ensemble ne l'est
    jamais, sa position est portée par son Std Part) ; rien ne bouge au recalcul."""
    from freecad.menuiserie.features.furniture_envelope import frame_of, member_envelope
    from tests.integration.bureau import build_parts
    from tests.integration.test_ensemble_membres import caisson

    api = pytest.importorskip("freecad.menuiserie.api")
    desk = build_parts(document)
    sub, parts = caisson(document)
    api.make_dowels(parts["CG"], parts["CB"])
    document.recompute()
    api.make_furniture([desk.parts["P"], desk.parts["JG"], desk.parts["JD"], sub], label="Bureau")
    before = frame_of(sub)
    edit = choice.ThicknessEdit(parts["CG"])
    assert edit.probe(30) is not None
    edit.apply(30, Choice.OTHER_SIDE)
    placed = {name: App.Placement(p.Placement) for name, p in parts.items()}
    edit.finish()
    document.recompute()
    assert frame_of(sub) == before
    assert member_envelope(sub) != before  # le côté sort de la boîte : limite connue
    assert all(p.Placement.isSame(placed[name], 1e-6) for name, p in parts.items())
    assert _all_hold(document)
