# SPDX-License-Identifier: LGPL-2.1-or-later
"""Un assemblage impossible n'est pas recopié par une répétition (ADR 0043, décision de jv).

Scénario de jv : une pièce A assemblée à une pièce B de 500 mm (faux tenons) est répétée le long
de B ; les copies qui dépassent B n'ont pas d'assemblage, aucun objet n'est en erreur et le
nombre d'assemblages non recopiés est signalé. Chaque édition de la répétition réévalue tout.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.aides_grille import Line, X, Z, grid
from tests.integration.cadre import placement, stale_or_invalid
from tests.integration.conftest import VueRapport
from tests.integration.test_repetition_assemblages import Scene, children, copies, part

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat_joints = pytest.importorskip("freecad.menuiserie.features.repeat_joints")
plan_cache = pytest.importorskip("freecad.menuiserie.features.joints.plan_cache")
NOT_COPIED = "n'ont pas été recopiés"
LENGTH_B = 500


class Pair:
    """B (500 mm, axe X) et A (barreau d'axe Y posé contre B), assemblés par des faux tenons."""

    def __init__(self, doc: Any) -> None:
        self.doc = doc
        self.long = part(doc, "B", (LENGTH_B, 60, 22), placement(0, 0))
        self.bar = part(doc, "A", (280, 40, 22), placement(140, 60, 90))
        self.origin = api.make_loose_tenons(self.long, self.bar)
        doc.recompute()

    def make(self, count: int, step: float, **values: Any) -> Any:
        params = api.RepeatParams(count=count, step=step, axis="X", **values)
        return api.make_repeat([self.bar], params)

    def edit(self, rep: Any, count: int, step: float) -> None:
        api.edit_repeat(rep, api.RepeatParams(count=count, step=step, axis="X"))

    def touching(self, rep: Any) -> list[int]:
        """Rangs des copies qui ont un assemblage enfant."""
        return sorted(
            copy.RepeatIndex for copy in copies(rep) if repeat_joints.joints_of_part(copy)
        )

    def assert_healthy(self) -> None:
        assert stale_or_invalid(self.doc) == []
        assert [o.Name for o in self.doc.Objects if "Error" in o.getStatusString()] == []


@pytest.fixture
def pair(document: Any) -> Pair:
    return Pair(document)


def test_copies_au_dela_de_la_piece_sans_assemblage_et_signalees(
    pair: Pair, vue_rapport: VueRapport
) -> None:
    rep = pair.make(5, 100.0)  # A à 140 + k * 100 : les copies 1 à 3 touchent B (500 mm)
    assert pair.touching(rep) == [1, 2, 3]
    assert len(children(pair.origin)) == 3
    assert len(api.machined_part_of(pair.long).Joints) == 4
    assert any(
        "2 assemblages n'ont pas été recopiés" in w for w in vue_rapport.de_niveau("Warning")
    )
    pair.assert_healthy()


def test_aucun_avertissement_quand_tout_est_possible(pair: Pair, vue_rapport: VueRapport) -> None:
    rep = pair.make(3, 100.0)
    assert pair.touching(rep) == [1, 2, 3]
    assert not any(NOT_COPIED in w for w in vue_rapport.de_niveau("Warning"))


def test_un_seul_assemblage_non_recopie_au_singulier(pair: Pair, vue_rapport: VueRapport) -> None:
    pair.make(4, 100.0)
    assert any("1 assemblage n'a pas été recopié" in w for w in vue_rapport.de_niveau("Warning"))


def test_edition_qui_raccourcit_puis_rallonge_le_pas(pair: Pair) -> None:
    rep = pair.make(4, 100.0)  # la copie 4 (540 mm) sort de B
    assert pair.touching(rep) == [1, 2, 3]
    pair.edit(rep, 4, 200.0)  # 340, 540, 740 : seule la copie 1 touche encore
    assert pair.touching(rep) == [1]
    assert len(api.machined_part_of(pair.long).Joints) == 2
    pair.assert_healthy()
    pair.edit(rep, 4, 80.0)  # toutes dans B de nouveau : l'assemblage manquant est créé
    assert pair.touching(rep) == [1, 2, 3, 4]
    assert len(api.machined_part_of(pair.long).Joints) == 5
    pair.assert_healthy()


def test_enfant_dissocie_ne_revient_pas(pair: Pair) -> None:
    rep = pair.make(2, 100.0)
    victim = repeat_joints.joints_of_part(copies(rep)[0])[0]
    repeat_joints.unlink_joint(victim)
    pair.edit(rep, 2, 200.0)
    pair.edit(rep, 2, 100.0)
    assert victim.Name in [j.Name for j in repeat_joints.joints_of_part(copies(rep)[0])]
    assert repeat_joints.origin_of(victim) is None
    assert len(repeat_joints.joints_of_part(copies(rep)[0])) == 1
    pair.assert_healthy()


def test_recalcul_seul_ne_cree_ni_ne_supprime_rien(pair: Pair) -> None:
    rep = pair.make(2, 100.0)
    count = len(pair.doc.Objects)
    for copy in copies(rep):
        assert repeat_joints.joints_of_part(copy)
    pair.bar.Placement = placement(900, 60, 90)  # source déplacée : copies hors de B
    pair.doc.recompute()
    assert len(pair.doc.Objects) == count  # limite documentée : rien n'est écrit au recalcul


def test_grille_les_cellules_impossibles_n_ont_pas_d_assemblage(
    document: Any, vue_rapport: VueRapport
) -> None:
    scene = Scene(document)  # traverses de 600 mm, barreau à x = 140
    rep = api.make_repeat([scene.bar], grid(Line(X, 4, 200.0), Line(Z, 2, 4.0)))
    columns = {
        repeat_joints.origin_of(j) and copy.RepeatCell[0]
        for copy in copies(rep)
        for j in repeat_joints.joints_of_part(copy)
    }
    assert columns == {0, 1, 2}  # 140, 340, 540, 740 : la colonne 3 sort de l'hôte
    assert any(NOT_COPIED in w for w in vue_rapport.de_niveau("Warning"))
    assert stale_or_invalid(document) == []


def test_annuler_et_retablir(document: Any) -> None:
    document.UndoMode = 1
    pair = Pair(document)
    rep = pair.make(5, 100.0)
    document.undo()
    document.recompute()
    assert [o for o in document.Objects if hasattr(o, "RepeatJoint")] == []
    document.redo()
    document.recompute()
    assert len(children(pair.origin)) == 3
    pair.edit(rep, 5, 70.0)
    assert pair.touching(rep) == [1, 2, 3, 4, 5]
    document.undo()
    document.recompute()
    assert len(children(pair.origin)) == 3
    document.redo()
    document.recompute()
    assert len(children(pair.origin)) == 5
    pair.assert_healthy()


def test_le_cache_de_plans_ne_memorise_pas_l_echec(pair: Pair) -> None:
    plan_cache.reset_plan_cache()
    rep = pair.make(5, 100.0)
    size = plan_cache.plan_cache_size()
    pair.edit(rep, 5, 100.0)  # mêmes impossibles réévalués : rien de nouveau mémorisé
    assert plan_cache.plan_cache_size() == size
    pair.edit(rep, 5, 70.0)  # ce qui était impossible devient possible : plan calculé, pas relu
    assert pair.touching(rep) == [1, 2, 3, 4, 5]
    pair.assert_healthy()
