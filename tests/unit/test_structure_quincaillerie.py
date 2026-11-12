# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046) : catégorie « Quincaillerie » et icône de chaque type."""

from __future__ import annotations

import re

import pytest

from freecad.menuiserie.core._validation import FrozenMapping
from freecad.menuiserie.core.hardware import FAMILIES, HardwareItem, joint_kind_of
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.structure_hardware import (
    HARDWARE_KINDS,
    WOOD_JOINT_KINDS,
    is_hardware_kind,
)
from freecad.menuiserie.core.structure_icons import (
    DISTANCE_SUBTYPE,
    ICON_BY_KIND,
    ICON_BY_SUBTYPE,
    SHAPED_SUBTYPE,
    icon_name,
)
from freecad.menuiserie.core.structure_tree import NodeKind
from tests.unit.aides import ROOT

ICONS = ROOT / "freecad" / "menuiserie" / "resources" / "icons"
GUI = ROOT / "freecad" / "menuiserie" / "gui"
COMMANDS = (GUI / "commands" / "joints.py").read_text(encoding="utf-8")


def test_la_table_suit_les_familles_du_catalogue_de_l_adr_0033() -> None:
    posed = set()
    for family in FAMILIES:
        item = HardwareItem(id="x", family=family, label="x", params=FrozenMapping({}), source="t")
        if (kind := joint_kind_of(item)) is not None:
            posed.add(kind)
    # fixations posées depuis le catalogue mais rangées sous « Assemblages » (jv)
    fixations = {JointKind.DOWELS, JointKind.LOOSE_TENON, JointKind.BISCUIT}
    assert posed - fixations == HARDWARE_KINDS
    assert fixations <= posed


def test_chaque_type_est_assemblage_ou_quincaillerie_jamais_les_deux() -> None:
    assert set(JointKind) == HARDWARE_KINDS | WOOD_JOINT_KINDS
    assert frozenset() == HARDWARE_KINDS & WOOD_JOINT_KINDS


@pytest.mark.parametrize(
    "kind",
    [
        JointKind.FOOT,
        JointKind.DRAWER_SLIDE,
        JointKind.SHELF_PINS,
        JointKind.HINGE,
    ],
)
def test_quincaillerie(kind: JointKind) -> None:
    assert is_hardware_kind(kind)


@pytest.mark.parametrize(
    "kind",
    [
        JointKind.MORTISE_TENON,
        JointKind.TONGUE_GROOVE,
        JointKind.RABBET,
        JointKind.HALF_LAP,
        JointKind.DOVETAIL,
        JointKind.MITER,
        JointKind.DOWELS,
        JointKind.LOOSE_TENON,
        JointKind.BISCUIT,
    ],
)
def test_assemblage_taille_dans_le_bois(kind: JointKind) -> None:
    assert not is_hardware_kind(kind)


@pytest.mark.parametrize("kind", list(JointKind), ids=lambda k: k.value)
def test_chaque_assemblage_a_l_icone_de_sa_commande(kind: JointKind) -> None:
    name = icon_name(NodeKind.JOINT, kind.value)
    assert name == f"Menuiserie_{kind.value}.svg"
    assert (ICONS / name).is_file()
    assert f'"{name[:-4]}"' in COMMANDS  # l'icône est celle de la commande, pas un doublon


def test_distance_et_piece_en_forme_ont_leur_icone() -> None:
    assert icon_name(NodeKind.JOINT, DISTANCE_SUBTYPE) == "Menuiserie_Distance.svg"
    assert icon_name(NodeKind.PIECE, SHAPED_SUBTYPE) == "Menuiserie_ShapedPartObject.svg"
    assert icon_name(NodeKind.PIECE) == "Menuiserie_WoodPart.svg"


def test_type_inconnu_retombe_sur_l_icone_du_genre() -> None:
    assert icon_name(NodeKind.JOINT, "Inconnu") == ICON_BY_KIND[NodeKind.JOINT]
    assert icon_name(NodeKind.HARDWARE) == "Menuiserie_Hardware.svg"


def test_toutes_les_icones_de_lignes_existent_et_aucune_n_est_un_doublon() -> None:
    names = {*ICON_BY_KIND.values(), *ICON_BY_SUBTYPE.values()}
    for name in names:
        assert (ICONS / name).is_file(), name
    generator = (ROOT / "tools" / "generer_icones.py").read_text(encoding="utf-8")
    assert '"Menuiserie_Hardware.svg"' in generator
    assert len(re.findall(r'"Menuiserie_Hardware\.svg"', generator)) == 1
