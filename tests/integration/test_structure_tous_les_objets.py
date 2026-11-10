# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046) : tout objet de l'atelier est dans l'arbre, une seule fois.

Document mêlant pièces dans et hors ensemble, tourillons, LR32, pieds, coulisse, faux tenons,
Distance et liste de débit : les assemblages et Distances sans ensemble de rattachement
(pieds, coulisse, faux tenons entre pièces libres) vont dans le nœud « Quincaillerie (N) » de la
racine, et rien n'est perdu ni répété.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from tests.integration.bureau import build_desk
from tests.integration.test_distance_gardee import keep
from tests.integration.test_pieds_coulisses import sides, upright_side
from tests.integration.types_assemblages import LOOSE_TENON, blanks

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
shaped_sources = pytest.importorskip("freecad.menuiserie.features.shaped_sources")
structure_source = pytest.importorskip("freecad.menuiserie.features.structure_source")
tree_module = pytest.importorskip("freecad.menuiserie.core.structure_tree")
hardware_module = pytest.importorskip("freecad.menuiserie.core.structure_hardware")
joint_module = pytest.importorskip("freecad.menuiserie.features.joints.base")

NodeKind = tree_module.NodeKind


def build_document(document: Any) -> dict[str, Any]:
    """Bureau (tourillons, Distance), armoire (côté + LR32), et, hors de tout ensemble : une
    planche à pieds, un tiroir à coulisse et deux planches à faux tenons ; puis la liste de
    débit."""
    desk = build_desk(document)
    distance = keep(desk)
    side = upright_side(document)
    api.make_furniture([side], "Armoire")
    pins = api.make_shelf_pins(side)
    panel = api.make_wood_part(600, 500, 19, "chene", mark="Planche", doc=document)
    document.recompute()
    feet = api.make_foot(panel)
    host, guest = sides(document)
    slide = api.make_drawer_slide(host, guest)
    tenon_host, tenon_guest = blanks(document, LOOSE_TENON)
    tenons = api.make_loose_tenons(tenon_host, tenon_guest)
    api.make_cut_list(document)
    document.recompute()
    return {
        "desk": desk,
        "distance": distance,
        "pins": pins,
        "feet": feet,
        "slide": slide,
        "tenons": tenons,
    }


def roots_of(document: Any) -> tuple[Any, ...]:
    return tuple(structure_source.structure_of(document))


def row_keys(roots: Any) -> list[str]:
    return [node.key for root in roots for node in root.walk() if node.key]


def test_tout_objet_de_l_atelier_est_dans_l_arbre_une_seule_fois(document: Any) -> None:
    build_document(document)
    roots = roots_of(document)
    expected = {
        structure_source.row_key_of(obj)
        for obj in document.Objects
        if shaped_sources.is_workshop_object(obj)
    }
    shown = Counter(row_keys(roots))
    assert expected <= set(shown)
    assert [key for key, count in shown.items() if count > 1] == []
    assert all(root.kind is not NodeKind.LEFTOVERS for root in roots)  # rien ne tombe au filet


def test_quincaillerie_libre_dans_un_noeud_a_la_racine(document: Any) -> None:
    objects = build_document(document)
    root_hardware = [root for root in roots_of(document) if root.kind is NodeKind.HARDWARE]
    assert len(root_hardware) == 1
    (group,) = root_hardware
    assert group.expanded is False
    assert {child.key for child in group.children} == {
        objects["feet"].Name,
        objects["slide"].Name,
        objects["tenons"].Name,
    }
    assert {child.kind for child in group.children} == {NodeKind.HARDWARE_ITEM}
    subtypes = {child.key: child.subtype for child in group.children}
    assert subtypes[objects["feet"].Name] == "Foot"
    assert subtypes[objects["slide"].Name] == "DrawerSlide"
    assert subtypes[objects["tenons"].Name] == "LooseTenon"


def test_toute_quincaillerie_est_sous_un_noeud_quincaillerie(document: Any) -> None:
    build_document(document)
    roots = roots_of(document)
    hardware = {
        node.key
        for root in roots
        for group in root.walk()
        if group.kind is NodeKind.HARDWARE
        for node in group.children
    }
    for obj in document.Objects:
        if joint_module.is_joint(obj):
            kind_is_hardware = hardware_module.is_hardware_kind(obj.Proxy.KIND)
            assert (obj.Name in hardware) is kind_is_hardware, obj.Name
    assert document.Objects  # le document n'est pas vide


def test_assemblages_d_ensemble_restent_sous_leur_ensemble(document: Any) -> None:
    objects = build_document(document)
    under = {
        child.key: group.kind
        for root in roots_of(document)
        if root.kind is NodeKind.FURNITURE
        for group in root.children
        if group.kind in (NodeKind.JOINTS, NodeKind.HARDWARE)
        for child in group.children
    }
    assert under[objects["distance"].Name] is NodeKind.JOINTS
    assert under[objects["pins"].Name] is NodeKind.HARDWARE  # LR32
    assert {under[joint.Name] for joint in objects["desk"].joints} == {
        NodeKind.HARDWARE
    }  # tourillons


def test_lignes_libres_selectionnables_par_leur_cle(document: Any) -> None:
    objects = build_document(document)
    for name in ("feet", "slide", "tenons"):
        joint = objects[name]
        assert structure_source.row_key_of(joint) == joint.Name
        assert joint.Name in row_keys(roots_of(document))
