# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur tirée à la souris dans un sens puis dans l'autre (retours de jv, 2026-11-16).

Agrandir puis rapetisser l'épaisseur d'une pièce assemblée, par l'une ou l'autre face : au
relâchement, l'assemblage tient. Les pièces posées sur la face tirée la suivent pendant le
glissement (issue #133), comme celles qui s'allongent (ADR 0060) ; l'aperçu recalcule les
assemblages qui tiennent, pour que les usinages soient à leur place.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.test_epaisseur_cote import corner, holds

App = pytest.importorskip("FreeCAD")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
Vec3 = pytest.importorskip("freecad.menuiserie.core.geometry").Vec3
machined = pytest.importorskip("freecad.menuiserie.features.machined_part")
machined_plans = pytest.importorskip("freecad.menuiserie.features.machined_plans")

pytestmark = pytest.mark.integration

SEQUENCES = ([25, 30, 20, 10, 5], [30, 18, 10], [25, 12], [10, 30, 12])


@pytest.mark.parametrize("piece", ["guest", "host"])
@pytest.mark.parametrize("lowered", [False, True])
@pytest.mark.parametrize("values", SEQUENCES)
def test_agrandir_puis_rapetisser(
    document: Any, piece: str, lowered: bool, values: list[float]
) -> None:
    host, guest, joint = corner(document)
    part = guest if piece == "guest" else host
    memento = drag.begin_drag(part)
    for value in values:
        shift = Vec3(0, 0, 18 - value) if lowered else Vec3(0, 0, 0)
        drag.resize_part(memento, "Thickness", value, shift, lowered=lowered)
    drag.end_drag(memento)
    assert holds(document, joint), joint.State


def test_piece_posee_suit_la_face_pendant_le_glissement(document: Any) -> None:
    """H tirée par sa face haute : I, posée dessus, monte avec elle à chaque pas."""
    host, guest, _joint = corner(document)
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0))
    assert guest.Placement.Base.z == pytest.approx(25)
    drag.resize_part(memento, "Thickness", 12, Vec3(0, 0, 0))
    assert guest.Placement.Base.z == pytest.approx(12)
    messages = drag.end_drag(memento)
    assert any("suivent sa face" in m for m in messages)


def test_echap_rend_la_piece_posee(document: Any) -> None:
    host, guest, _joint = corner(document)
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0))
    drag.restore(memento)
    assert guest.Placement.Base.z == pytest.approx(18)
    assert host.Thickness.Value == 18


def test_apercu_recalcule_les_pieces_usinees(document: Any) -> None:
    """Pendant le glissement, les pièces usinées (celle de H, allongée, comprise) sont
    recalculées avec leurs assemblages : la vue 3D montre les usinages à leur place."""
    host, guest, _joint = corner(document)
    machined_host = machined.machined_part_of(host)
    machined_guest = machined.machined_part_of(guest)
    assert machined_host is not None and machined_guest is not None
    memento = drag.begin_drag(guest)
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    assert machined_host.Shape.BoundBox.XLength == pytest.approx(412)
    assert machined_host.Shape.BoundBox.XMin == pytest.approx(-12)
    assert machined_guest.Shape.BoundBox.XLength == pytest.approx(30)
    drag.restore(memento)
    assert machined_host.Shape.BoundBox.XLength == pytest.approx(400)


def _z(part: Any) -> float:
    return float(part.Placement.Base.z)


def test_piece_posee_bloquee_reste_en_place_pendant_le_glissement(document: Any) -> None:
    """I posée mais pilotée par une expression : elle ne suit pas, rien n'est écrit de travers."""
    host, guest, _joint = corner(document)
    guest.setExpression("Placement.Base.z", "18 mm")
    document.recompute()
    memento = drag.begin_drag(host)
    for value in (25, 12, 30):
        drag.resize_part(memento, "Thickness", value, Vec3(0, 0, 0))
        assert _z(guest) == pytest.approx(18)
    messages = drag.end_drag(memento)
    assert not any("suivent sa face" in m for m in messages)
    assert guest.ExpressionEngine, "expression perdue"


def test_piece_posee_membre_d_ensemble_reste_en_place(document: Any) -> None:
    host, guest, _joint = corner(document)
    api = pytest.importorskip("freecad.menuiserie.api")
    api.make_furniture([guest], "Meuble")
    document.recompute()
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0))
    assert _z(guest) == pytest.approx(18)
    drag.restore(memento)
    assert _z(guest) == pytest.approx(18) and host.Thickness.Value == 18


def test_chaine_de_pieces_posees_suit_toute_la_chaine(document: Any) -> None:
    """K est assemblée à I, elle-même posée sur H : toutes montent avec la face de H."""
    from tests.integration.test_epaisseur_cote_limites import two_hosts

    host, top, guest, joint, joint2 = two_hosts(document)
    z_top = _z(top)
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    assert _z(guest) == pytest.approx(30) and _z(top) == pytest.approx(z_top + 12)
    drag.resize_part(memento, "Thickness", 10, Vec3(0, 0, 0))
    assert _z(guest) == pytest.approx(10) and _z(top) == pytest.approx(z_top - 8)
    drag.restore(memento)
    assert _z(guest) == pytest.approx(18) and _z(top) == pytest.approx(z_top)
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0))
    drag.end_drag(memento)
    assert holds(document, joint) and holds(document, joint2)


def test_face_basse_ne_deplace_pas_la_piece_posee_sur_la_face_haute(document: Any) -> None:
    host, guest, joint = corner(document)
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, -12), lowered=True)
    assert _z(guest) == pytest.approx(18)
    drag.end_drag(memento)
    assert holds(document, joint)


def test_longueur_et_largeur_ne_deplacent_aucune_piece(document: Any) -> None:
    host, guest, _joint = corner(document)
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Length", 450, Vec3(0, 0, 0))
    drag.resize_part(memento, "Width", 160, Vec3(0, 0, 0))
    assert memento.follows.parts() == []
    assert _z(guest) == pytest.approx(18)
    drag.restore(memento)


def test_echap_apres_plusieurs_pas_rend_la_piece_posee_exactement(document: Any) -> None:
    host, guest, joint = corner(document)
    start = App.Placement(guest.Placement)
    memento = drag.begin_drag(host)
    for value, lowered in ((25, False), (30, True), (8, False), (40, True)):
        shift = Vec3(0, 0, 18 - value) if lowered else Vec3(0, 0, 0)
        drag.resize_part(memento, "Thickness", value, shift, lowered=lowered)
    drag.restore(memento)
    assert guest.Placement.isSame(start, 1e-9)
    assert holds(document, joint)


def test_exception_pendant_le_suivi_ne_laisse_rien_a_moitie_ecrit(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.integration.test_epaisseur_cote_limites import two_hosts

    thickness_follow = pytest.importorskip("freecad.menuiserie.features.thickness_follow")
    host, top, guest, _joint, _joint2 = two_hosts(document)
    original = thickness_follow.shift_part
    calls: list[str] = []

    def failing(piece: Any, shift: Any) -> None:
        calls.append(piece.Name)
        if len(calls) == 2:
            raise RuntimeError("panne simulée")
        original(piece, shift)

    memento = drag.begin_drag(host)
    monkeypatch.setattr(thickness_follow, "shift_part", failing)
    with pytest.raises(RuntimeError):
        drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    assert len(calls) == 2
    assert _z(guest) == pytest.approx(18) and _z(top) == pytest.approx(400)


def test_piece_posee_supprimee_pendant_le_glissement(document: Any) -> None:
    host, guest, _joint = corner(document)
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0))
    document.removeObject(guest.Name)
    try:
        drag.resize_part(memento, "Thickness", 12, Vec3(0, 0, 0))
    except (ReferenceError, ValueError, RuntimeError, App.Base.FreeCADError):
        drag.restore(memento)
    assert host.Thickness.Value in (12, 18)


def test_apercu_assemblage_qui_ne_tient_plus_change_quand_meme_la_taille(
    document: Any, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """Assemblage qui ne tient plus pendant le glissement : la pièce usinée change de taille à
    l'écran (jv, 2026-11-16 : elle se déplaçait sans grandir), sans trace ni recalcul de
    l'assemblage."""
    blank_preview = pytest.importorskip("freecad.menuiserie.features.blank_preview")
    _host, guest, joint = corner(document)
    machined_guest = machined.machined_part_of(guest)
    assert machined_guest is not None
    before = machined_guest.Shape.BoundBox

    def broken(_joint: Any) -> None:
        raise ValueError("ne tient plus")

    monkeypatch.setattr(blank_preview, "plan_for", broken)
    monkeypatch.setattr(machined_plans, "plan_for", broken)
    recomputes: list[str] = []
    monkeypatch.setattr(type(joint.Proxy), "execute", lambda _s, o: recomputes.append(o.Name))
    capfd.readouterr()
    memento = drag.begin_drag(guest)
    drag.resize_part(memento, "Length", 300, Vec3(0, 0, 0))
    after = machined_guest.Shape.BoundBox
    assert max(before.XLength, before.YLength, before.ZLength) > 400  # queues comprises
    assert max(after.XLength, after.YLength, after.ZLength) == pytest.approx(300)  # brute seule
    assert recomputes == []
    out = capfd.readouterr()
    assert "Traceback" not in out.out + out.err
    drag.restore(memento)


@pytest.mark.parametrize("lowered", [False, True])
def test_apercu_epaisseur_pas_a_fleur_grandit_a_l_ecran(document: Any, lowered: bool) -> None:
    """Poignée d'épaisseur de H (aucune pièce à prolonger) : la pièce usinée de H prend
    l'épaisseur tirée dans l'aperçu, sans seulement se déplacer."""
    host, _guest, _joint = corner(document)
    machined_host = machined.machined_part_of(host)
    assert machined_host is not None
    memento = drag.begin_drag(host)
    for value in (25, 40, 10):
        shift = Vec3(0, 0, 18 - value) if lowered else Vec3(0, 0, 0)
        drag.resize_part(memento, "Thickness", value, shift, lowered=lowered)
        assert machined_host.Shape.BoundBox.ZLength == pytest.approx(value, abs=1e-6)
    drag.restore(memento)


def test_echap_rend_la_forme_usinee_complete(document: Any) -> None:
    """Après un aperçu où l'assemblage ne tenait plus, Échap rend la pièce usinée avec tous ses
    usinages (pas de forme partielle laissée)."""
    _host, guest, _joint = corner(document)
    machined_guest = machined.machined_part_of(guest)
    assert machined_guest is not None
    volume = machined_guest.Shape.Volume
    memento = drag.begin_drag(guest)
    drag.resize_part(memento, "Length", 300, Vec3(0, 0, 0))
    drag.restore(memento)
    assert machined_guest.Shape.Volume == pytest.approx(volume)


def _broken_joint(monkeypatch: pytest.MonkeyPatch) -> None:
    blank_preview = pytest.importorskip("freecad.menuiserie.features.blank_preview")

    def broken(_joint: Any) -> None:
        raise ValueError("ne tient plus")

    monkeypatch.setattr(blank_preview, "plan_for", broken)
    monkeypatch.setattr(machined_plans, "plan_for", broken)


@pytest.mark.parametrize(("prop", "value"), [("Length", 300), ("Width", 100), ("Thickness", 40)])
def test_apercu_assemblage_qui_ne_tient_plus_taille_juste_et_echap_rend_la_forme(
    document: Any,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    prop: str,
    value: float,
) -> None:
    """Pièce debout I (queues) : brute à la cote tirée dans l'aperçu, sans trace ; Échap puis
    recalcul rendent la forme usinée d'avant, au volume près."""
    _host, guest, joint = corner(document)
    machined_guest = machined.machined_part_of(guest)
    assert machined_guest is not None
    volume, box = machined_guest.Shape.Volume, machined_guest.Shape.BoundBox
    placement = App.Placement(machined_guest.Placement)
    with monkeypatch.context() as patch:
        _broken_joint(patch)
        capfd.readouterr()
        memento = drag.begin_drag(guest)
        drag.resize_part(memento, prop, value, Vec3(0, 0, 0))
        shown = machined_guest.Shape
        sizes = sorted((shown.BoundBox.XLength, shown.BoundBox.YLength, shown.BoundBox.ZLength))
        expected = sorted(
            float(getattr(guest, name).Value) for name in ("Length", "Width", "Thickness")
        )
        assert guest.Shape.isValid() and shown.isValid()
        assert sizes == pytest.approx(expected, abs=1e-6)  # brute seule, aucune queue
        assert shown.Volume == pytest.approx(expected[0] * expected[1] * expected[2], rel=1e-6)
        drag.restore(memento)
        out = capfd.readouterr()
        assert "Traceback" not in out.out + out.err
    assert getattr(guest, prop).Value != value
    assert holds(document, joint)
    assert machined_guest.Shape.Volume == pytest.approx(volume, rel=1e-9)
    assert machined_guest.Shape.BoundBox.isValid()
    assert (machined_guest.Shape.BoundBox.XLength, machined_guest.Shape.BoundBox.ZLength) == (
        pytest.approx(box.XLength),
        pytest.approx(box.ZLength),
    )
    assert machined_guest.Placement.isSame(placement, 1e-9)


def test_apercu_assemblage_qui_tient_garde_ses_usinages(document: Any) -> None:
    """Un assemblage qui tient pendant le glissement reste usiné dans l'aperçu (volume de la
    pièce usinée différent de celui de la brute seule)."""
    _host, guest, _joint = corner(document)
    machined_guest = machined.machined_part_of(guest)
    assert machined_guest is not None
    memento = drag.begin_drag(guest)
    drag.resize_part(memento, "Width", 120, Vec3(0, 0, 0))
    blank_volume = guest.Length.Value * guest.Width.Value * guest.Thickness.Value
    assert machined_guest.Shape.Volume != pytest.approx(blank_volume, rel=1e-6)
    drag.restore(memento)


def test_apercu_puis_assemblage_qui_tient_de_nouveau_reprend_les_usinages(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pas de forme restée en cache d'un aperçu sans usinage : un pas où l'assemblage tient
    redonne la pièce usinée."""
    _host, guest, _joint = corner(document)
    machined_guest = machined.machined_part_of(guest)
    assert machined_guest is not None
    full = machined_guest.Shape.Volume
    memento = drag.begin_drag(guest)
    with monkeypatch.context() as patch:
        _broken_joint(patch)
        drag.resize_part(memento, "Width", 100, Vec3(0, 0, 0))
        assert machined_guest.Shape.Volume == pytest.approx(
            guest.Length.Value * guest.Width.Value * guest.Thickness.Value, rel=1e-6
        )
    drag.resize_part(memento, "Width", 150, Vec3(0, 0, 0))  # l'assemblage tient de nouveau
    assert machined_guest.Shape.Volume == pytest.approx(full, rel=1e-6)
    drag.restore(memento)


def test_relachement_avec_assemblage_qui_ne_tient_plus_previent_sans_planter(
    document: Any,
) -> None:
    """Épaisseur trop mince pour les queues : l'aperçu montre la brute, le relâchement ne lève
    rien et le recalcul signale l'assemblage (il n'est pas perdu en silence)."""
    _host, guest, joint = corner(document)
    memento = drag.begin_drag(guest)
    drag.resize_part(memento, "Thickness", 2, Vec3(0, 0, 0))
    machined_guest = machined.machined_part_of(guest)
    assert machined_guest is not None
    assert machined_guest.Shape.isValid()
    box = machined_guest.Shape.BoundBox
    assert min(box.XLength, box.YLength, box.ZLength) == pytest.approx(2, abs=1e-6)
    drag.end_drag(memento)
    document.recompute()
    assert guest.Thickness.Value == 2
    assert not holds(document, joint)
