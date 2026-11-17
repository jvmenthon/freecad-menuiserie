# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boîtes toujours recalées sur leurs membres, sous-ensembles compris (ADR 0065) : pièce
déplacée dans un sous-ensemble, sous-ensemble imbriqué déplacé, retour arrière si l'ensemble ne
peut pas être relié."""

from __future__ import annotations

from typing import Any

import pytest

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
envelope = pytest.importorskip("freecad.menuiserie.features.furniture_envelope")
part_drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
reframe = pytest.importorskip("freecad.menuiserie.features.furniture_reframe")
bindings = pytest.importorskip("freecad.menuiserie.features.furniture_bindings")
geometry = pytest.importorskip("freecad.menuiserie.core.geometry")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")

pytestmark = pytest.mark.integration


def _meuble(document: Any) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Bureau ⊃ Caisson ⊃ Fond (le dessous seul) : (bureau, caisson, fond, pièces du caisson)."""
    from tests.integration.bureau import build_parts
    from tests.integration.test_ensemble_membres import caisson

    desk = build_parts(document)
    sub, parts = caisson(document)
    inner, _ = api.make_furniture([parts["CB"]], label="Fond")
    document.recompute()
    bureau, _ = api.make_furniture(
        [*(desk.parts[mark] for mark in ("P", "JG", "JD")), sub], label="Bureau"
    )
    document.recompute()
    return bureau, sub, inner, parts


def _ajustee(furniture: Any) -> None:
    """Boîte = enveloppe des membres ; ``Origin`` nul pour un sous-ensemble."""
    assert envelope.frame_of(furniture) == envelope.member_envelope(furniture)
    if api.furniture_of(furniture) is not None:
        assert envelope.frame_of(furniture).min == geometry.Vec3(0.0, 0.0, 0.0)


def _ajustee_pres(furniture: Any) -> None:
    """Comme :func:`_ajustee`, à 1e-6 mm près (rotation du Std Part)."""
    frame, wanted = envelope.frame_of(furniture), envelope.member_envelope(furniture)
    for i in range(3):
        assert frame.lo(i) == pytest.approx(wanted.lo(i), abs=1e-5)
        assert frame.hi(i) == pytest.approx(wanted.hi(i), abs=1e-5)


def _globaux(parts: dict[str, Any]) -> dict[str, Any]:
    return {mark: App.Placement(part.getGlobalPlacement()) for mark, part in parts.items()}


def _memes(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return all(first[mark].isSame(second[mark], 1e-6) for mark in first)


def test_meuble_imbrique_ajuste_au_depart(document: Any) -> None:
    bureau, sub, inner, _ = _meuble(document)
    for level in (inner, sub, bureau):
        _ajustee(level)


def test_piece_deplacee_hors_du_sous_ensemble_recale_toute_la_chaine(document: Any) -> None:
    bureau, sub, inner, parts = _meuble(document)
    hauteur = sub.Height.Value
    memento = part_drag.begin_drag(parts["CB"])
    part_drag.move_part(memento, geometry.Vec3(0.0, 0.0, -100.0))
    part_drag.end_drag(memento)
    document.recompute()
    vus = _globaux(parts)
    assert sub.Height.Value == pytest.approx(hauteur + 100.0)
    for level in (inner, sub, bureau):
        _ajustee(level)
    document.recompute()  # rien ne bouge au recalcul : les liaisons suivent la géométrie
    assert _memes(vus, _globaux(parts))


def test_sous_ensemble_imbrique_deplace_recale_ses_parents(document: Any) -> None:
    bureau, sub, inner, parts = _meuble(document)
    assert api.move_furniture(inner, (0, 0, -100))
    document.recompute()
    vus = _globaux(parts)
    assert vus["CB"].Base.z == pytest.approx(300.0)
    for level in (inner, sub, bureau):
        _ajustee(level)
    assert api.move_furniture(inner, (0, 0, 100))  # ramené : le caisson retrouve sa taille
    document.recompute()
    assert sub.Height.Value == pytest.approx(300.0)
    for level in (inner, sub, bureau):
        _ajustee(level)


def test_liaison_impossible_rend_boites_positions_et_liaisons(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bureau, sub, inner, parts = _meuble(document)
    memento = part_drag.begin_drag(parts["CB"])
    part_drag.move_part(memento, geometry.Vec3(0.0, 0.0, -100.0))
    chain = (inner, sub, bureau)
    boites = [envelope.frame_of(level) for level in chain]
    liaisons = [dict(bindings.workshop_expressions(obj)) for obj in (*parts.values(), *chain)]
    vus = _globaux(parts)
    std = [App.Placement(container.std_part_of(level).Placement) for level in chain]
    appels = []
    vraie = reframe.bind_furniture

    def echoue_au_parent(furniture: Any) -> Any:
        appels.append(furniture.Label)
        if furniture is bureau:
            raise ValueError("cycle")
        return vraie(furniture)

    monkeypatch.setattr(reframe, "bind_furniture", echoue_au_parent)
    with pytest.raises(ValueError):
        reframe.relink_framed(inner)
    assert appels == ["Fond", "Caisson", "Bureau"]
    assert [envelope.frame_of(level) for level in chain] == boites
    assert [dict(bindings.workshop_expressions(o)) for o in (*parts.values(), *chain)] == liaisons
    assert _memes(vus, _globaux(parts))
    assert all(
        container.std_part_of(level).Placement.isSame(placement, 1e-9)
        for level, placement in zip(chain, std, strict=True)
    )
    part_drag.restore(memento)


# --- Cas limites du testeur (revue de 9d315ba) ---------------------------------------------


def _sortir(document: Any, parts: dict[str, Any], dz: float = -100.0) -> None:
    """Fond du caisson descendu de ``dz`` à la souris (geste complet, recalcul compris)."""
    memento = part_drag.begin_drag(parts["CB"])
    part_drag.move_part(memento, geometry.Vec3(0.0, 0.0, dz))
    part_drag.end_drag(memento)
    document.recompute()


def _tourner(document: Any, furniture: Any) -> None:
    """Std Part du sous-ensemble tourné de 90 degrés autour de Z (écrit directement : la liaison
    de position de l'atelier ne porte que sur ``Placement.Base.x``)."""
    part = container.std_part_of(furniture)
    turned = App.Placement(part.Placement)
    turned.Rotation = App.Rotation(App.Vector(0, 0, 1), 90)
    part.Placement = turned
    document.recompute()


def _etat(document: Any, parts: dict[str, Any], chain: tuple[Any, ...]) -> Any:
    return (
        [envelope.frame_of(level) for level in chain],
        [App.Placement(container.std_part_of(level).Placement) for level in chain],
        {mark: App.Placement(part.Placement) for mark, part in parts.items()},
        [dict(bindings.workshop_expressions(o)) for o in (*parts.values(), *chain)],
    )


def _meme_etat(first: Any, second: Any) -> bool:
    return (
        first[0] == second[0]
        and all(a.isSame(b, 1e-9) for a, b in zip(first[1], second[1], strict=True))
        and all(first[2][m].isSame(second[2][m], 1e-9) for m in first[2])
        and first[3] == second[3]
    )


def test_sous_ensemble_tourne_le_decalage_passe_par_la_rotation(document: Any) -> None:
    bureau, sub, inner, parts = _meuble(document)
    _tourner(document, sub)
    avant = _globaux(parts)
    boite = envelope.frame_of(sub)
    _sortir(document, parts)
    apres = _globaux(parts)
    # les pièces qui n'ont pas bougé à la souris restent en place à l'écran
    for mark in ("CG", "CD"):
        assert apres[mark].isSame(avant[mark], 1e-6)
    assert apres["CB"].Base.z == pytest.approx(avant["CB"].Base.z - 100.0)
    assert sub.Height.Value == pytest.approx(boite.max.z - boite.min.z + 100.0)
    for level in (inner, sub, bureau):
        _ajustee(level)
    assert container.std_part_of(sub).Placement.Rotation.isSame(
        App.Placement(App.Vector(), App.Rotation(App.Vector(0, 0, 1), 90)).Rotation, 1e-9
    )
    document.recompute()
    assert _memes(apres, _globaux(parts))


def test_sous_ensemble_tourne_deplace_en_largeur(document: Any) -> None:
    """Décalage non nul en X/Y dans le repère d'un Std Part tourné."""
    bureau, sub, inner, parts = _meuble(document)
    _tourner(document, sub)
    avant = _globaux(parts)
    memento = part_drag.begin_drag(parts["CD"])
    part_drag.move_part(memento, geometry.Vec3(-60.0, 0.0, 0.0))
    part_drag.end_drag(memento)
    document.recompute()
    apres = _globaux(parts)
    for mark in ("CG", "CB"):
        assert apres[mark].isSame(avant[mark], 1e-6)
    for level in (inner, sub, bureau):
        _ajustee_pres(level)


def test_membre_copie_de_repetition_sous_ensemble_non_recale_remontee_continue(
    document: Any,
) -> None:
    bureau, sub, inner, parts = _meuble(document)
    api.make_repeat([parts["CB"]], api.RepeatParams(count=2, step=100.0, axis="Z"))
    document.recompute()  # les copies rejoignent « Fond », placées par formule
    assert not envelope._movable(inner)  # pylint: disable=protected-access
    boite = envelope.frame_of(inner)
    std = App.Placement(container.std_part_of(inner).Placement)
    _sortir(document, parts)
    # « Fond » n'est pas décalé ; ses parents, eux, sont recalés sur leurs membres
    assert envelope.frame_of(inner) == boite
    assert container.std_part_of(inner).Placement.isSame(std, 1e-9)
    assert envelope.frame_of(sub) == envelope.member_envelope(sub)
    assert envelope.frame_of(bureau) == envelope.member_envelope(bureau)
    document.recompute()
    from tests.integration.cadre import stale_or_invalid

    assert stale_or_invalid(document) == []


def test_parent_pilote_par_formule_n_est_pas_recale_mais_le_sous_ensemble_si(
    document: Any,
) -> None:
    bureau, sub, inner, parts = _meuble(document)
    largeur = bureau.Width.Value
    bureau.setExpression("Height", "1000 mm")
    document.recompute()
    boite = envelope.frame_of(bureau)
    _sortir(document, parts)
    assert envelope.frame_of(bureau) == boite  # piloté : intact
    assert bureau.Width.Value == pytest.approx(largeur)
    for level in (inner, sub):
        _ajustee(level)
    assert bureau.ExpressionEngine  # la formule est toujours là
    assert bureau.Height.Value == pytest.approx(1000.0)


def test_ensemble_du_milieu_non_recalable_la_remontee_continue(document: Any) -> None:
    bureau, sub, inner, parts = _meuble(document)
    sub.setExpression("Width", "400 mm")  # formule d'utilisateur : le caisson n'est pas recalé
    document.recompute()
    boite = envelope.frame_of(sub)
    _sortir(document, parts)
    assert envelope.frame_of(sub) == boite
    _ajustee(inner)
    enveloppe = envelope.member_envelope(bureau)
    assert envelope.frame_of(bureau) == enveloppe  # le bureau a été recalé malgré tout


def test_assemblages_toujours_valides_apres_decalage(document: Any) -> None:
    from tests.integration.bureau import build_parts
    from tests.integration.cadre import stale_or_invalid
    from tests.integration.test_ensemble_membres import caisson

    desk = build_parts(document)
    sub, parts = caisson(document)
    document.recompute()
    bureau, _ = api.make_furniture(
        [*(desk.parts[mark] for mark in ("P", "JG", "JD")), sub], label="Bureau"
    )
    document.recompute()
    api.make_mortise_tenon(parts["CG"], parts["CB"])
    document.recompute()
    assert stale_or_invalid(document) == []
    usinee = api.machined_part_of(parts["CB"])
    volume = usinee.Shape.Volume
    memento = part_drag.begin_drag(parts["CD"])  # côté droit élargi vers l'extérieur
    part_drag.move_part(memento, geometry.Vec3(0.0, 0.0, 0.0))
    part_drag.end_drag(memento)
    document.recompute()
    assert api.move_furniture(sub, (30, 0, 0))  # décalage non nul du sous-ensemble en X
    document.recompute()
    assert stale_or_invalid(document) == []
    assert usinee.Shape.Volume == pytest.approx(volume)
    for level in (sub, bureau):
        _ajustee(level)


def test_annulation_rend_tout(document: Any) -> None:
    bureau, sub, inner, parts = _meuble(document)
    chain = (inner, sub, bureau)
    document.UndoMode = 1
    avant = _etat(document, parts, chain)
    globaux = _globaux(parts)
    document.openTransaction("Déplacer la pièce")
    _sortir(document, parts)
    document.commitTransaction()
    assert not _meme_etat(avant, _etat(document, parts, chain))
    apres = _etat(document, parts, chain)
    document.undo()
    document.recompute()
    assert _meme_etat(avant, _etat(document, parts, chain))
    assert _memes(globaux, _globaux(parts))
    document.redo()
    document.recompute()
    assert _meme_etat(apres, _etat(document, parts, chain))


def test_annulation_du_deplacement_d_un_sous_ensemble(document: Any) -> None:
    bureau, sub, inner, parts = _meuble(document)
    chain = (inner, sub, bureau)
    document.UndoMode = 1
    avant = _etat(document, parts, chain)
    document.openTransaction("Déplacer")
    assert api.move_furniture(inner, (0, 0, -100))
    document.commitTransaction()
    document.undo()
    document.recompute()
    assert _meme_etat(avant, _etat(document, parts, chain))


def test_enregistrement_et_reouverture_apres_recalage(document: Any, tmp_path: Any) -> None:
    from tests.integration.cadre import stale_or_invalid

    _, sub, _, parts = _meuble(document)
    _sortir(document, parts)
    hauteur = sub.Height.Value
    globaux = {mark: App.Placement(p.getGlobalPlacement()) for mark, p in parts.items()}
    chemin = tmp_path / "boites.FCStd"
    document.saveAs(str(chemin))
    App.closeDocument(document.Name)
    ouvert = App.openDocument(str(chemin))
    try:
        ouvert.recompute()
        assert stale_or_invalid(ouvert) == []
        rb = ouvert.getObjectsByLabel("Bureau")[0]
        rs = ouvert.getObjectsByLabel("Caisson")[0]
        ri = ouvert.getObjectsByLabel("Fond")[0]
        assert rs.Height.Value == pytest.approx(hauteur)
        for level in (ri, rs, rb):
            _ajustee(level)
        for mark, placement in globaux.items():
            rouvert = ouvert.getObjectsByLabel(mark)[0].getGlobalPlacement()
            assert rouvert.isSame(placement, 1e-6)
        # et la suite fonctionne : ramener la pièce rétrécit le caisson
        pieces = {m: ouvert.getObjectsByLabel(m)[0] for m in parts}
        memento = part_drag.begin_drag(pieces["CB"])
        part_drag.move_part(memento, geometry.Vec3(0.0, 0.0, 100.0))
        part_drag.end_drag(memento)
        ouvert.recompute()
        assert rs.Height.Value == pytest.approx(hauteur - 100.0)
        assert stale_or_invalid(ouvert) == []
    finally:
        App.closeDocument(ouvert.Name)


@pytest.mark.parametrize("dz", [0.0, 1e-9, -0.05, -5000.0])
def test_deplacements_limites(document: Any, dz: float) -> None:
    bureau, sub, inner, parts = _meuble(document)
    _sortir(document, parts, dz=dz)
    for level in (inner, sub, bureau):
        _ajustee_pres(level)


@pytest.mark.parametrize("dz", [-1e5, 1e6])
def test_deplacement_demesure_refuse_et_tout_revient(document: Any, dz: float) -> None:
    bureau, sub, inner, parts = _meuble(document)
    chain = (inner, sub, bureau)
    avant = _etat(document, parts, chain)
    memento = part_drag.begin_drag(parts["CB"])
    part_drag.move_part(memento, geometry.Vec3(0.0, 0.0, dz))
    with pytest.raises(ValueError):
        part_drag.end_drag(memento)
    document.recompute()
    assert _meme_etat(avant, _etat(document, parts, chain))


# --- ADR 0065 point 5 : entrée et sortie ----------------------------------------------------


def _bureau_et_caisson(document: Any) -> tuple[Any, Any, dict[str, Any]]:
    from tests.integration.bureau import build_parts
    from tests.integration.test_ensemble_membres import caisson

    desk = build_parts(document)
    sub, parts = caisson(document)
    bureau, _ = api.make_furniture([desk.parts[m] for m in ("P", "JG", "JD")], label="Bureau")
    document.recompute()
    return bureau, sub, parts


def test_sous_ensemble_entre_puis_sort_le_parent_suit(document: Any) -> None:
    from tests.integration.cadre import stale_or_invalid

    bureau, sub, parts = _bureau_et_caisson(document)
    depart = envelope.frame_of(bureau)
    vus = _globaux(parts)
    api.add_to_furniture(bureau, [sub])
    _ajustee(bureau)
    _ajustee(sub)
    assert _memes(vus, _globaux(parts))
    api.remove_from_furniture([sub])
    assert envelope.frame_of(bureau) == depart
    assert _memes(vus, _globaux(parts))
    assert not stale_or_invalid(document)


def test_dernier_membre_retire_sans_erreur(document: Any) -> None:
    from tests.integration.cadre import stale_or_invalid

    piece = api.make_wood_part(600.0, 60.0, 22.0, "chene", doc=document)
    document.recompute()
    api.make_furniture([piece], "Seul")
    assert api.remove_from_furniture([piece]) == ()
    assert not stale_or_invalid(document)


def test_recalage_impossible_rend_la_boite_et_garde_l_entree(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un ensemble qui ne peut pas être relié après l'entrée revient à son état d'avant le
    recalage ; l'entrée reste (refusée seulement avant toute modification) et le refus est dit."""
    from tests.integration.cadre import stale_or_invalid

    first = api.make_wood_part(600.0, 60.0, 22.0, "chene", doc=document)
    second = api.make_wood_part(600.0, 60.0, 22.0, "chene", doc=document)
    second.Placement.Base = App.Vector(0.0, 500.0, 0.0)
    document.recompute()
    furniture, _ = api.make_furniture([first], "Cadre")

    def refuse(_furniture: Any) -> Any:
        raise ValueError("cycle simulé")

    monkeypatch.setattr(reframe, "bind_furniture", refuse)
    messages = api.add_to_furniture(furniture, [second])
    assert any("cycle simulé" in message for message in messages)
    assert api.furniture_of(second) == furniture
    assert not stale_or_invalid(document)


def test_ensemble_pilote_par_une_formule_garde_sa_boite(document: Any) -> None:
    """ADR 0065 point 3 : une cote pilotée par une formule de l'utilisateur n'est pas recalée."""
    first = api.make_wood_part(600.0, 60.0, 22.0, "chene", doc=document)
    second = api.make_wood_part(600.0, 60.0, 22.0, "chene", doc=document)
    second.Placement.Base = App.Vector(0.0, 100.0, 0.0)
    document.recompute()
    furniture, _ = api.make_furniture([first], "Cadre")
    first.Locked = True
    furniture.setExpression("Depth", "1000 mm")
    document.recompute()
    api.add_to_furniture(furniture, [second])
    assert furniture.Depth.Value == 1000.0
