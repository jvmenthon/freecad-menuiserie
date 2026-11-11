# SPDX-License-Identifier: LGPL-2.1-or-later
"""Marqueur de FreeCAD 1.1 pour la suppression du contenu d'un groupe (Std Part d'ensemble)."""

from __future__ import annotations

from freecad.menuiserie.gui.view_providers.deletion import GROUP_DELETION, in_group_deletion


def test_marqueur_de_freecad_reconnu() -> None:
    assert GROUP_DELETION == "group_recursive_deletion"
    assert in_group_deletion(["group_recursive_deletion"])
    assert in_group_deletion(("group_recursive_deletion",))


def test_suppression_ordinaire_non_reconnue() -> None:
    assert not in_group_deletion([])
    assert not in_group_deletion(None)
    assert not in_group_deletion("group_recursive_deletion")
    assert not in_group_deletion(["Face1"])
