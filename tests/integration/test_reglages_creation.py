# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier lus à la création, dans un vrai document FreeCAD (CA-b, ADR 0069) :
sans réglage modifié, comportement d'avant ; réglages appliqués aux pièces neuves seulement ;
arête cassée sans casser la création ; annuler / rétablir, sauvegarde et réouverture."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest

from tests.integration.cadre import placement, stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
config = pytest.importorskip("freecad.menuiserie.features.settings")
new_part_settings = pytest.importorskip("freecad.menuiserie.features.new_part_settings")
edge_profile_create = pytest.importorskip("freecad.menuiserie.features.edge_profile_create")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")

Reopen = Callable[[Any], Any]


@pytest.fixture
def reglages() -> Iterator[Any]:
    """Réglages de l'atelier : toutes les clés du catalogue rétablies avant et après le test."""
    values = config.settings()
    values.reset_all()
    yield values
    values.reset_all()


def _profiles(part: Any) -> list[Any]:
    found: list[Any] = edge_profile_create.edge_profiles_of(part)
    return found


# --- sans réglage modifié : comme avant ----------------------------------------------------


def test_sans_reglage_modifie_valeurs_d_avant(document: Any, reglages: Any) -> None:
    part = api.make_wood_part(doc=document)
    assert (part.Length.Value, part.Width.Value, part.Thickness.Value) == (800.0, 200.0, 22.0)
    assert _profiles(part) == []
    assert part.LengthAllowance.Value == 20.0 and part.WidthAllowance.Value == 5.0
    explicit = api.make_wood_part(800, 200, 22, doc=document)
    assert part.MaterialId == explicit.MaterialId


def test_signature_historique_de_make_wood_part(document: Any, reglages: Any) -> None:
    """Les appelants positionnels (longueur, largeur, épaisseur, matériau) restent corrects."""
    part = api.make_wood_part(1000, 250, 27, "chene", mark="M1", doc=document)
    assert (part.Length.Value, part.Width.Value, part.Thickness.Value) == (1000, 250, 27)
    assert (part.MaterialId, part.Mark) == ("chene", "M1")


# --- réglages appliqués aux pièces neuves -------------------------------------------------


def test_cotes_materiau_et_surcotes_de_l_atelier(document: Any, reglages: Any) -> None:
    reglages.set(config.LENGTH, 1200.0)
    reglages.set(config.WIDTH, 300.0)
    reglages.set(config.THICKNESS, 27.0)
    reglages.set(config.MATERIAL, "chene")
    reglages.set(config.SOLID_ALLOWANCES[0], 35.0)
    part = api.make_wood_part(doc=document)
    assert (part.Length.Value, part.Width.Value, part.Thickness.Value) == (1200.0, 300.0, 27.0)
    assert part.MaterialId == "chene"
    assert part.LengthAllowance.Value == 35.0
    given = api.make_wood_part(500, doc=document)  # l'appelant l'emporte sur le réglage
    assert given.Length.Value == 500.0 and given.Width.Value == 300.0


def test_materiau_retire_de_la_bibliotheque_retombe_sur_le_premier(
    document: Any, reglages: Any
) -> None:
    reglages.set(config.MATERIAL, "materiau-disparu")
    part = api.make_wood_part(doc=document)
    assert part.isValid() and part.MaterialId != "materiau-disparu"


def test_reglages_ni_sur_les_copies_ni_sur_les_repetitions(document: Any, reglages: Any) -> None:
    source = api.make_wood_part(280, 40, 22, "chene", doc=document)
    reglages.set(config.SOLID_ALLOWANCES[0], 99.0)
    reglages.set(config.BROKEN_EDGE, True)
    before = source.LengthAllowance.Value
    rep = api.make_repeat([source], api.RepeatParams(count=3, step=300.0, axis="X"))
    copies = repeat.copies_of(rep)
    assert len(copies) == 3
    assert source.LengthAllowance.Value == before
    assert all(c.LengthAllowance.Value == before for c in copies)
    assert _profiles(source) == []  # l'arête cassée ne vise que les pièces neuves
    assert stale_or_invalid(document) == []


def test_reglage_modifie_apres_creation_ne_touche_pas_les_pieces_existantes(
    document: Any, reglages: Any
) -> None:
    part = api.make_wood_part(doc=document)
    reglages.set(config.SOLID_ALLOWANCES[0], 77.0)
    reglages.set(config.LENGTH, 1.0e3)
    document.recompute()
    assert part.LengthAllowance.Value == 20.0 and part.Length.Value == 800.0


# --- arête cassée --------------------------------------------------------------------------


def test_arete_cassee_cochee_sur_les_douze_aretes(document: Any, reglages: Any) -> None:
    reglages.set(config.BROKEN_EDGE, True)
    reglages.set(config.BROKEN_EDGE_SIZE, 2.0)
    part = api.make_wood_part(doc=document)
    [profile] = _profiles(part)
    assert profile.SizeA.Value == 2.0 and len(profile.Edges) == 12
    assert stale_or_invalid(document) == []


def test_arete_cassee_refusee_n_empeche_pas_la_creation(
    document: Any, reglages: Any, vue_rapport: Any
) -> None:
    reglages.set(config.BROKEN_EDGE, True)
    reglages.set(config.BROKEN_EDGE_SIZE, 100.0)  # plus de la moitié de l'épaisseur : refusée
    part = api.make_wood_part(doc=document)
    assert part.isValid() and _profiles(part) == []
    assert vue_rapport.de_niveau("Warning")
    assert stale_or_invalid(document) == []


def test_arete_cassee_annuler_retablir(document: Any, reglages: Any) -> None:
    reglages.set(config.BROKEN_EDGE, True)
    document.openTransaction("création")
    part = api.make_wood_part(doc=document)
    document.commitTransaction()
    name = part.Name
    assert len(_profiles(part)) == 1
    document.undo()
    document.recompute()
    assert document.getObject(name) is None
    assert [o for o in document.Objects if o.TypeId == "Part::FeaturePython"] == []
    document.redo()
    document.recompute()
    restored = document.getObject(name)
    assert restored is not None and len(_profiles(restored)) == 1
    assert stale_or_invalid(document) == []


def test_arete_cassee_sauvegarde_et_reouverture(
    document: Any, reglages: Any, rouvrir: Reopen
) -> None:
    reglages.set(config.BROKEN_EDGE, True)
    reglages.set(config.SOLID_ALLOWANCES[1], 8.0)
    part = api.make_wood_part(doc=document)
    name = part.Name
    reopened = rouvrir(document)
    restored = reopened.getObject(name)
    assert restored.WidthAllowance.Value == 8.0
    assert len(_profiles(restored)) == 1
    reopened.recompute()
    assert stale_or_invalid(reopened) == []


def test_pieces_dessinees_arete_cassee_sans_exception(document: Any, reglages: Any) -> None:
    """Une pièce dessinée aux arêtes non suivies (primitive) : refus éventuel de l'arête cassée
    traité en avertissement, jamais d'exception."""
    reglages.set(config.BROKEN_EDGE, True)
    source = document.addObject("Part::Cylinder", "Cylindre")
    document.recompute()
    part = api.make_shaped_part(source)
    assert part.isValid()
    assert stale_or_invalid(document) == []


# --- gabarit -------------------------------------------------------------------------------


def test_gabarit_sans_reglage_modifie_ne_cree_pas_de_profil(document: Any, reglages: Any) -> None:
    furniture, _ = api.make_carcass(document)
    assert furniture.isValid()
    assert [o for o in document.Objects if "EdgeProfile" in o.Name] == []


def test_gabarit_arete_cassee_annuler(document: Any, reglages: Any) -> None:
    reglages.set(config.BROKEN_EDGE, True)
    before = len(document.Objects)
    document.openTransaction("caisson")
    api.make_carcass(document)
    document.commitTransaction()
    assert len(document.Objects) > before
    assert [o for o in document.Objects if "EdgeProfile" in o.Name]
    document.undo()
    document.recompute()
    assert len(document.Objects) == before
    assert stale_or_invalid(document) == []


# --- assemblages --------------------------------------------------------------------------


def test_assemblage_neuf_prend_le_reglage_et_l_appelant_l_emporte(
    document: Any, reglages: Any
) -> None:
    low = api.make_wood_part(6000, 60, 22, "chene", mark="Basse", doc=document)
    bar = api.make_wood_part(280, 40, 22, "chene", mark="B", doc=document)
    bar.Placement = placement(40, 60, 90)
    document.recompute()
    reglages.set(config.MORTISE_CLEARANCE, 3.0)
    joint = api.make_mortise_tenon(low, bar)
    assert joint.MortiseClearance.Value == 3.0
    again = api.make_mortise_tenon(low, bar, mortise_clearance=1.0)
    assert again.MortiseClearance.Value == 1.0
    document.recompute()
    assert stale_or_invalid(document) == []
