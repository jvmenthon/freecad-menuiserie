# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition de pièces dans le document (lot R-b1, ADR 0043, ``docs/specs/repetition.md``).

R1 copies et positions, R8 annulation en un bloc, R9 la source modifiée, R10 le pas modifié,
R11 dissocier, R13 liste de débit, R16 changer le nombre ; suppression de la répétition ou de la
source, réouverture du document, refus. Pas d'assemblage ni d'ensemble (lots R-b2 et R-c).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.cadre import placement, stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")

Reopen = Callable[[Any], Any]
COPY_PROPERTIES = ("Repeat", "RepeatSource", "RepeatIndex")
BOUND = ("Length", "Width", "Thickness", "Material", "GrainDirection", "Placement.Base.x")


def params(**values: Any) -> Any:
    """Cinq copies à 100 mm sur Y, sauf réglage contraire."""
    return api.RepeatParams(**{"count": 5, "step": 100.0, "axis": "Y", **values})


def source(doc: Any, mark: str = "Barreau", size: Any = (300, 40, 22), **kwargs: Any) -> Any:
    """Pièce de chêne recalculée."""
    part = api.make_wood_part(*size, "chene", mark=mark, doc=doc, **kwargs)
    doc.recompute()
    return part


def copies(rep: Any, src: Any = None) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep, src)
    return found


def offsets_y(rep: Any, src: Any = None) -> list[float]:
    return [round(c.Placement.Base.y, 6) for c in copies(rep, src)]


def engine(obj: Any) -> dict[str, str]:
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


@pytest.fixture
def undoable(document: Any) -> Any:
    """Document dont les annulations sont enregistrées."""
    document.UndoMode = 1
    return document


# --- R1 : création -------------------------------------------------------------------------


def test_cinq_copies_aux_bonnes_positions(document: Any) -> None:
    barreau = source(document)
    barreau.Placement = placement(10, 20)
    document.recompute()
    rep = api.make_repeat([barreau], params())
    assert repeat.is_repeat(rep) and rep.Name == "Repeat"
    assert (rep.Count, rep.Step.Value, rep.Axis, rep.Mode) == (5, 100.0, "Y", "Linear")
    assert [c.Label for c in copies(rep)] == [f"Barreau {k}" for k in range(2, 7)]
    assert [c.RepeatIndex for c in copies(rep)] == [1, 2, 3, 4, 5]
    assert offsets_y(rep) == [120.0, 220.0, 320.0, 420.0, 520.0]
    for c in copies(rep):
        assert (c.Placement.Base.x, c.Placement.Base.z) == (10.0, 0.0)
        assert c.Shape.isValid() and c.Shape.Volume == pytest.approx(barreau.Shape.Volume)
        assert (c.Length, c.Width, c.Thickness) == (
            barreau.Length,
            barreau.Width,
            barreau.Thickness,
        )
    assert stale_or_invalid(document) == []


def test_la_repetition_n_a_pas_de_forme_et_ses_champs_sont_proteges(document: Any) -> None:
    rep = api.make_repeat([source(document)], params())
    assert not hasattr(rep, "Shape")
    assert rep.Source[0].Label == "Barreau"
    for name in ("Source", "Count", "Mode", "Spacing", "Axis", "Span", "CopyJoints"):
        assert rep.getEditorMode(name) == ["ReadOnly"], name
    for name in ("Step", "Reverse"):
        assert rep.getEditorMode(name) == [], name
    assert {rep.getGroupOfProperty(n) for n in ("Source", "Count", "Step", "Reverse")} == {
        "Répétition"
    }
    assert rep.Version == 1
    for c in copies(rep):
        for name in COPY_PROPERTIES:
            assert c.getEditorMode(name) == ["ReadOnly"], name
            assert c.getGroupOfProperty(name) == "Répétition"
        assert c.Repeat == rep and c.RepeatSource.Label == "Barreau"


def test_expressions_natives_de_la_copie(document: Any) -> None:
    barreau = source(document)
    rep = api.make_repeat([barreau], params(axis="Z", reverse=False, count=2))
    last = copies(rep)[-1]
    expected = {
        "Length": f"{barreau.Name}.Length",
        "Placement.Base.x": f"{barreau.Name}.Placement.Base.x",
        "Placement.Base.z": (
            f"{barreau.Name}.Placement.Base.z + 2 * (Repeat.Reverse ? -1 : 1) * Repeat.Step"
        ),
        "Placement.Rotation": f"{barreau.Name}.Placement.Rotation",
        "Material": f"{barreau.Name}.Material",
    }
    assert {k: v for k, v in engine(last).items() if k in expected} == expected
    assert "Mark" not in engine(last)  # le libellé de la copie est propre à elle


def test_materiau_fil_et_surcotes_recopies(document: Any) -> None:
    barreau = api.make_wood_part(300, 40, 22, "noyer", mark="Barreau", doc=document)
    barreau.GrainDirection = "Width"
    barreau.LengthAllowance = 12
    document.recompute()
    rep = api.make_repeat([barreau], params(count=2))
    for c in copies(rep):
        assert (c.MaterialId, c.Material, c.GrainDirection) == ("noyer", barreau.Material, "Width")
        assert c.LengthAllowance == barreau.LengthAllowance
        assert c.Density == barreau.Density


def test_plusieurs_sources_chacune_ses_copies_au_meme_pas(document: Any) -> None:
    a = source(document, "A")
    b = source(document, "B", (200, 30, 18))
    b.Placement = placement(0, 500)
    document.recompute()
    rep = api.make_repeat([a, b], params(count=3))
    assert [c.Label for c in copies(rep, a)] == ["A 2", "A 3", "A 4"]
    assert [c.Label for c in copies(rep, b)] == ["B 2", "B 3", "B 4"]
    assert offsets_y(rep, a) == [100.0, 200.0, 300.0]
    assert offsets_y(rep, b) == [600.0, 700.0, 800.0]
    assert copies(rep, b)[0].Length.Value == 200.0
    assert len(copies(rep)) == 6


def test_nombre_sur_une_longueur_et_pas_sur_une_longueur(document: Any) -> None:
    barreau = source(document)  # 40 mm de large sur Y
    on_span = api.make_repeat(
        [barreau],
        api.RepeatParams(spacing="CountOnSpan", count=4, span=440, axis="Y"),
    )
    assert (on_span.Count, on_span.Step.Value) == (4, 100.0)
    assert offsets_y(on_span) == [100.0, 200.0, 300.0, 400.0]
    other = source(document, "Autre")
    by_step = api.make_repeat(
        [other], api.RepeatParams(spacing="StepOnSpan", step=100, span=440, axis="Y")
    )
    assert (by_step.Count, by_step.Spacing) == (4, "StepOnSpan")


def test_refus_avant_toute_creation(document: Any) -> None:
    barreau = source(document)
    box = document.addObject("Part::Box", "Bloc")
    count = len(document.Objects)
    with pytest.raises(ValueError, match=r"aucune copie|longueur"):
        api.make_repeat([barreau], api.RepeatParams(spacing="CountOnSpan", count=2, span=30))
    with pytest.raises(ValueError, match="aucune pièce"):
        api.make_repeat([], params())
    with pytest.raises(TypeError, match="pas une pièce de bois"):
        api.make_repeat([barreau, box], params())
    assert len(document.Objects) == count


def test_autres_types_de_pieces_refuses(document: Any) -> None:
    host, guest = source(document, "H"), source(document, "G")
    guest.Placement = placement(0, 40)
    document.recompute()
    api.make_dowels(host, guest)
    document.recompute()
    with pytest.raises(TypeError, match="seules les pièces de bois"):
        api.make_repeat([api.machined_part_of(host)], params())
    furniture, _ = api.make_furniture([host, guest])
    with pytest.raises(TypeError, match="seules les pièces de bois"):
        api.make_repeat([furniture], params())


def test_une_copie_liee_ne_se_repete_pas(document: Any) -> None:
    rep = api.make_repeat([source(document)], params(count=1))
    with pytest.raises(ValueError, match="dissociez-la"):
        api.make_repeat(copies(rep), params())


def test_cent_copies_se_recalculent_vite(document: Any) -> None:
    barreau = source(document, size=(300, 5, 22))
    rep = api.make_repeat([barreau], params(count=100, step=10))
    assert (rep.Count, len(copies(rep))) == (100, 100)
    barreau.Length = 400
    started = time.perf_counter()
    document.recompute()
    assert time.perf_counter() - started < 2.0
    assert copies(rep)[-1].Length.Value == 400.0
    assert stale_or_invalid(document) == []
    with pytest.raises(ValueError, match="100"):
        api.edit_repeat(rep, params(count=101))
    assert len(copies(rep)) == 100


# --- R8 : annulation en un bloc ------------------------------------------------------------


def test_annulation_et_retablissement_en_un_bloc(undoable: Any) -> None:
    barreau = source(undoable)
    before = {o.Name for o in undoable.Objects}
    api.make_repeat([barreau], params())
    assert len(undoable.Objects) == len(before) + 6
    undoable.undo()
    assert {o.Name for o in undoable.Objects} == before
    assert barreau.ExpressionEngine == []
    undoable.redo()
    undoable.recompute()
    rep = undoable.getObject("Repeat")
    assert len(copies(rep)) == 5 and offsets_y(rep) == [100.0, 200.0, 300.0, 400.0, 500.0]
    assert stale_or_invalid(undoable) == []


def test_la_transaction_de_l_appelant_est_respectee(undoable: Any) -> None:
    barreau = source(undoable)
    before = len(undoable.Objects)
    undoable.openTransaction("Mon bloc")
    api.make_repeat([barreau], params(count=2), transaction=False)
    api.edit_repeat(undoable.getObject("Repeat"), params(count=3), transaction=False)
    undoable.commitTransaction()
    undoable.undo()
    assert len(undoable.Objects) == before


def test_refus_pendant_edition_ne_laisse_rien(undoable: Any) -> None:
    barreau = source(undoable)
    rep = api.make_repeat([barreau], params(count=2))
    before = (rep.Count, len(undoable.Objects), engine(copies(rep)[0]))
    with pytest.raises(ValueError):
        api.edit_repeat(rep, api.RepeatParams(spacing="CountOnSpan", count=2, span=10))
    assert (rep.Count, len(undoable.Objects), engine(copies(rep)[0])) == before


# --- R9, R10 : la source et le pas ---------------------------------------------------------


def test_source_modifiee_les_copies_suivent(document: Any) -> None:
    barreau = source(document)
    rep = api.make_repeat([barreau], params(count=3))
    barreau.Length, barreau.Width, barreau.Thickness = 500, 60, 30
    barreau.Placement = placement(7, 11, 90)
    document.recompute()
    assert stale_or_invalid(document) == []
    for k, c in enumerate(copies(rep), start=1):
        assert (c.Length.Value, c.Width.Value, c.Thickness.Value) == (500, 60, 30)
        assert c.Placement.Base.x == pytest.approx(7)
        assert c.Placement.Base.y == pytest.approx(11 + 100 * k)
        assert c.Placement.Rotation.isSame(barreau.Placement.Rotation, 1e-9)
        assert c.Shape.BoundBox.ZLength == pytest.approx(30)


def test_materiau_de_la_source_suivi_par_les_copies(document: Any) -> None:
    barreau = source(document)
    rep = api.make_repeat([barreau], params(count=2))
    barreau.Material = "Noyer"
    document.recompute()
    assert [(c.MaterialId, c.Material) for c in copies(rep)] == [("noyer", "Noyer")] * 2
    barreau.GrainDirection = "Width"
    document.recompute()
    assert {c.GrainDirection for c in copies(rep)} == {"Width"}
    api.make_wood_part  # noqa: B018  (l'API publique de matériau est celle de la pièce)
    from freecad.menuiserie.features.wood_part import set_material

    set_material(barreau, "mdf")
    document.recompute()
    assert [(c.MaterialId, c.Category, c.GrainDirection) for c in copies(rep)] == [
        ("mdf", "MDF", "None")
    ] * 2
    assert stale_or_invalid(document) == []


def test_pas_modifie_les_copies_se_deplacent(document: Any) -> None:
    rep = api.make_repeat([source(document)], params())
    rep.Step = 250
    document.recompute()
    assert offsets_y(rep) == [250.0, 500.0, 750.0, 1000.0, 1250.0]
    rep.Reverse = True
    document.recompute()
    assert offsets_y(rep) == [-250.0, -500.0, -750.0, -1000.0, -1250.0]
    assert stale_or_invalid(document) == []


def test_sens_inverse_des_la_creation_et_axe_x(document: Any) -> None:
    rep = api.make_repeat([source(document)], params(axis="X", reverse=True, count=2))
    assert [c.Placement.Base.x for c in copies(rep)] == [-100.0, -200.0]
    assert {c.Placement.Base.y for c in copies(rep)} == {0.0}


# --- R11 : dissocier -----------------------------------------------------------------------


def test_dissocier_une_copie(undoable: Any) -> None:
    barreau = source(undoable)
    rep = api.make_repeat([barreau], params(count=3))
    second = copies(rep)[1]
    api.dissociate(second)
    assert not repeat.is_copy(second) and api.repeat_of(second) is None
    assert second.ExpressionEngine == []
    assert [p for p in COPY_PROPERTIES if p in second.PropertiesList] == []
    assert second.Placement.Base.y == 200.0 and second.Length.Value == 300.0
    assert (rep.Count, [c.RepeatIndex for c in copies(rep)]) == (3, [1, 3])
    barreau.Length = 450
    rep.Step = 150
    undoable.recompute()
    assert second.Length.Value == 300.0 and second.Placement.Base.y == 200.0
    assert [c.Length.Value for c in copies(rep)] == [450.0, 450.0]
    assert offsets_y(rep) == [150.0, 450.0]
    assert stale_or_invalid(undoable) == []


def test_dissocier_annulable(undoable: Any) -> None:
    rep = api.make_repeat([source(undoable)], params(count=2))
    second = copies(rep)[1]
    api.dissociate(second)
    undoable.undo()
    assert repeat.is_copy(second) and second.RepeatIndex == 2
    assert "Placement.Base.y" in engine(second)


def test_dissocier_ne_touche_pas_une_formule_de_l_utilisateur(document: Any) -> None:
    rep = api.make_repeat([source(document)], params(count=1))
    only = copies(rep)[0]
    only.addProperty("App::PropertyLength", "Jeu", "Perso")
    only.setExpression("Mark", "Jeu.Value + 0")  # formule sans lien avec la répétition
    api.dissociate(only)
    assert "Mark" in engine(only)


def test_dissocier_refuse_ce_qui_n_est_pas_une_copie(document: Any) -> None:
    barreau = source(document)
    with pytest.raises(TypeError, match="pas une copie liée"):
        api.dissociate(barreau)


def test_repeat_of(document: Any) -> None:
    barreau = source(document)
    rep = api.make_repeat([barreau], params(count=1))
    assert api.repeat_of(rep) == rep and api.repeat_of(copies(rep)[0]) == rep
    assert api.repeat_of(barreau) is None


# --- R16 : changer le nombre ---------------------------------------------------------------


def test_ajouter_des_copies(undoable: Any) -> None:
    rep = api.make_repeat([source(undoable)], params(count=2))
    first = copies(rep)[0].Name
    api.edit_repeat(rep, params(count=5))
    assert rep.Count == 5
    assert [c.Label for c in copies(rep)] == [f"Barreau {k}" for k in range(2, 7)]
    assert offsets_y(rep) == [100.0, 200.0, 300.0, 400.0, 500.0]
    assert copies(rep)[0].Name == first  # les copies existantes ne sont pas refaites
    undoable.undo()
    assert (rep.Count, len(copies(rep))) == (2, 2)


def test_retirer_les_dernieres_copies(undoable: Any) -> None:
    rep = api.make_repeat([source(undoable)], params(count=5))
    api.edit_repeat(rep, params(count=2))
    assert rep.Count == 2
    assert [c.RepeatIndex for c in copies(rep)] == [1, 2]
    assert len([o for o in undoable.Objects if o.TypeId == "Part::FeaturePython"]) == 3
    assert stale_or_invalid(undoable) == []
    undoable.undo()
    assert len(copies(rep)) == 5


def test_modifier_pas_axe_et_sens_reecrit_les_expressions(document: Any) -> None:
    rep = api.make_repeat([source(document)], params(count=2))
    api.edit_repeat(rep, params(count=2, step=60, axis="X", reverse=True))
    assert (rep.Step.Value, rep.Axis, rep.Reverse) == (60.0, "X", True)
    assert [c.Placement.Base.x for c in copies(rep)] == [-60.0, -120.0]
    assert {c.Placement.Base.y for c in copies(rep)} == {0.0}


def test_plusieurs_sources_changer_le_nombre(document: Any) -> None:
    a, b = source(document, "A"), source(document, "B")
    rep = api.make_repeat([a, b], params(count=2))
    api.edit_repeat(rep, params(count=3))
    assert [len(copies(rep, s)) for s in (a, b)] == [3, 3]
    api.edit_repeat(rep, params(count=1))
    assert [len(copies(rep, s)) for s in (a, b)] == [1, 1]


def test_copie_dissociee_ne_revient_pas(document: Any) -> None:
    rep = api.make_repeat([source(document)], params(count=3))
    api.dissociate(copies(rep)[0])  # rang 1
    api.edit_repeat(rep, params(count=5))
    assert [c.RepeatIndex for c in copies(rep)] == [2, 3, 4, 5]
    api.edit_repeat(rep, params(count=2))
    assert [c.RepeatIndex for c in copies(rep)] == [2]


def test_edition_depuis_une_copie(document: Any) -> None:
    rep = api.make_repeat([source(document)], params(count=2))
    api.edit_repeat(copies(rep)[1], params(count=3))
    assert rep.Count == 3


# --- Suppression ---------------------------------------------------------------------------


def test_supprimer_la_repetition_dissocie_les_copies(undoable: Any) -> None:
    rep = api.make_repeat([source(undoable)], params(count=3))
    kept = copies(rep)
    undoable.removeObject(rep.Name)
    assert undoable.getObject("Repeat") is None
    for c in kept:
        assert not repeat.is_copy(c) and c.ExpressionEngine == []
    undoable.recompute()
    assert offsets_y_of(kept) == [100.0, 200.0, 300.0]
    assert stale_or_invalid(undoable) == []


def offsets_y_of(parts: list[Any]) -> list[float]:
    return [round(p.Placement.Base.y, 6) for p in parts]


def test_supprimer_la_source_dissocie_les_copies(undoable: Any) -> None:
    barreau = source(undoable)
    rep = api.make_repeat([barreau], params(count=3))
    kept = copies(rep)
    undoable.removeObject(barreau.Name)
    assert rep.Source == []
    for c in kept:
        assert not repeat.is_copy(c) and c.ExpressionEngine == []
    undoable.recompute()
    assert offsets_y_of(kept) == [100.0, 200.0, 300.0]
    assert stale_or_invalid(undoable) == []


def test_supprimer_une_source_garde_les_autres(undoable: Any) -> None:
    a, b = source(undoable, "A"), source(undoable, "B")
    rep = api.make_repeat([a, b], params(count=2))
    undoable.removeObject(a.Name)
    assert rep.Source == [b] and len(copies(rep)) == 2
    undoable.recompute()
    assert stale_or_invalid(undoable) == []
    api.edit_repeat(rep, params(count=3))
    assert len(copies(rep)) == 3


def test_suppression_annulable(undoable: Any) -> None:
    barreau = source(undoable)
    rep = api.make_repeat([barreau], params(count=2))
    undoable.openTransaction("Supprimer")
    undoable.removeObject(barreau.Name)
    undoable.commitTransaction()
    undoable.undo()
    rep = undoable.getObject("Repeat")
    assert len(copies(rep)) == 2 and "Placement.Base.y" in engine(copies(rep)[0])
    undoable.recompute()
    assert stale_or_invalid(undoable) == []


def test_supprimer_une_copie_laisse_les_autres(document: Any) -> None:
    rep = api.make_repeat([source(document)], params(count=3))
    document.removeObject(copies(rep)[1].Name)
    document.recompute()
    assert [c.RepeatIndex for c in copies(rep)] == [1, 3]
    assert rep.Count == 3
    assert stale_or_invalid(document) == []


# --- Enregistrer et rouvrir ----------------------------------------------------------------


def test_reouverture_conserve_expressions_et_proprietes(document: Any, rouvrir: Reopen) -> None:
    barreau = source(document)
    rep = api.make_repeat([barreau], params(count=3, reverse=True))
    names = (barreau.Name, rep.Name)
    engines = {c.Name: engine(c) for c in copies(rep)}
    doc = rouvrir(document)
    barreau, rep = (doc.getObject(n) for n in names)
    proxy = type(rep.Proxy)
    assert (proxy.__module__, proxy.__name__, proxy.TYPE) == (
        "freecad.menuiserie.features.repeat",
        "Repeat",
        "Menuiserie::Repeat",
    )
    assert rep.Proxy.dumps() is None
    assert rep.Version == 1 and rep.Mode == "Linear" and rep.Axis == "Y" and rep.Count == 3
    assert rep.Source == [barreau] and rep.getEditorMode("Count") == ["ReadOnly"]
    assert {c.Name: engine(c) for c in copies(rep)} == engines
    assert [c.RepeatIndex for c in copies(rep)] == [1, 2, 3]
    assert stale_or_invalid(doc) == []
    barreau.Length = 640
    rep.Step = 80
    doc.recompute()
    assert copies(rep)[-1].Length.Value == 640.0
    assert offsets_y(rep) == [-80.0, -160.0, -240.0]
    api.edit_repeat(rep, params(count=4, reverse=True, step=80))
    assert len(copies(rep)) == 4 and stale_or_invalid(doc) == []
    api.dissociate(copies(rep)[0])
    assert stale_or_invalid(doc) == []


# --- R13 : liste de débit ------------------------------------------------------------------


def test_liste_de_debit_n_plus_un_pieces(document: Any) -> None:
    rep = api.make_repeat([source(document)], params(count=4))
    cut_list = api.cut_list_of(document)
    (line,) = cut_list.lines  # pièces identiques : une ligne, quantité 5 (source et 4 copies)
    assert line.quantity == 5 and cut_list.warnings == ()
    assert set(line.marks) == {"Barreau", *(c.Mark for c in copies(rep))}
    freed = copies(rep)[0]
    api.dissociate(freed)
    freed.Width = 50  # libre : elle peut différer, et la ligne se scinde
    document.recompute()
    assert sorted(line.quantity for line in api.cut_list_of(document).lines) == [1, 4]
