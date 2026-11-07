# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tests d'import pour vérifier que le refactoring des fichiers longs est correct.

Ces tests vérifient que les imports des modules refactorés fonctionnent toujours
correctement après la division des fichiers > 300 lignes.
"""

from __future__ import annotations

import pytest


class TestShelfPinsImports:
    """Test des imports pour shelf_pins."""

    def test_import_strategy(self) -> None:
        """Test l'import de ShelfPinsStrategy depuis le package."""
        from freecad.menuiserie.core.joints.shelf_pins import ShelfPinsStrategy
        assert ShelfPinsStrategy.kind.name == "SHELF_PINS"

    def test_import_params(self) -> None:
        """Test l'import des paramètres et valeurs."""
        from freecad.menuiserie.core.joints.shelf_pins import (
            ShelfPinsParams,
            ShelfPinsValues,
            FACES,
        )
        assert FACES == ("auto", "plus", "minus")
        params = ShelfPinsParams()
        assert params.hole_diameter == 0.0

    def test_import_ Functions(self) -> None:
        """Test l'import des fonctions utilitaires."""
        from freecad.menuiserie.core.joints.shelf_pins import (
            opposite_values,
            pin_rests,
            facing_side,
            picked_choice,
        )
        assert callable(opposite_values)
        assert callable(pin_rests)
        assert callable(facing_side)
        assert callable(picked_choice)

    def test_import_from_registry(self) -> None:
        """Test que l'import depuis _registry fonctionne."""
        from freecad.menuiserie.core.joints._registry import strategy_for
        from freecad.menuiserie.core.joints._base import JointKind
        strategy = strategy_for(JointKind.SHELF_PINS)
        assert strategy.kind == JointKind.SHELF_PINS

    def test_import_from_magnet_guides(self) -> None:
        """Test que magnet_guides peut toujours importer depuis shelf_pins."""
        # Simule l'import fait dans magnet_guides.py
        from freecad.menuiserie.core.joints.shelf_pins import opposite_values, pin_rests
        assert callable(opposite_values)
        assert callable(pin_rests)


class TestSlotsImports:
    """Test des imports pour slots."""

    def test_import_strategies(self) -> None:
        """Test l'import des stratégies."""
        from freecad.menuiserie.core.joints.slots import (
            LooseTenonStrategy,
            BiscuitStrategy,
        )
        assert LooseTenonStrategy.kind.name == "LOOSE_TENON"
        assert BiscuitStrategy.kind.name == "BISCUIT"

    def test_import_params(self) -> None:
        """Test l'import des paramètres."""
        from freecad.menuiserie.core.joints.slots import (
            SlotParams,
            SlotSize,
            SlotValues,
            AUTO_SIZE,
            LOOSE_TENON_SIZES,
            BISCUIT_SIZES,
        )
        assert AUTO_SIZE == "auto"
        assert len(LOOSE_TENON_SIZES) == 6
        assert len(BISCUIT_SIZES) == 3

    def test_import_from_registry(self) -> None:
        """Test que l'import depuis _registry fonctionne."""
        from freecad.menuiserie.core.joints._registry import strategy_for
        from freecad.menuiserie.core.joints._base import JointKind
        loose_tenon = strategy_for(JointKind.LOOSE_TENON)
        biscuit = strategy_for(JointKind.BISCUIT)
        assert loose_tenon.kind == JointKind.LOOSE_TENON
        assert biscuit.kind == JointKind.BISCUIT


class TestSlidesImports:
    """Test des imports pour slides."""

    def test_import_strategy(self) -> None:
        """Test l'import de SlideStrategy."""
        from freecad.menuiserie.core.joints.slides import SlideStrategy
        assert SlideStrategy.kind.name == "DRAWER_SLIDE"

    def test_import_params(self) -> None:
        """Test l'import des paramètres."""
        from freecad.menuiserie.core.joints.slides import (
            SlideParams,
            SlideValues,
            SLIDE_LENGTHS,
        )
        assert len(SLIDE_LENGTHS) == 8
        assert SLIDE_LENGTHS == (250.0, 300.0, 350.0, 400.0, 450.0, 500.0, 550.0, 600.0)

    def test_import_from_registry(self) -> None:
        """Test que l'import depuis _registry fonctionne."""
        from freecad.menuiserie.core.joints._registry import strategy_for
        from freecad.menuiserie.core.joints._base import JointKind
        strategy = strategy_for(JointKind.DRAWER_SLIDE)
        assert strategy.kind == JointKind.DRAWER_SLIDE


class TestPackageStructure:
    """Test de la structure des packages."""

    def test_shelf_pins_package_exists(self) -> None:
        """Test que le package shelf_pins existe et a la bonne structure."""
        import importlib
        import freecad.menuiserie.core.joints.shelf_pins as pkg
        assert hasattr(pkg, "ShelfPinsStrategy")
        assert hasattr(pkg, "ShelfPinsParams")
        assert hasattr(pkg, "ShelfPinsValues")

    def test_slots_package_exists(self) -> None:
        """Test que le package slots existe et a la bonne structure."""
        import importlib
        import freecad.menuiserie.core.joints.slots as pkg
        assert hasattr(pkg, "LooseTenonStrategy")
        assert hasattr(pkg, "BiscuitStrategy")
        assert hasattr(pkg, "SlotParams")

    def test_slides_package_exists(self) -> None:
        """Test que le package slides existe et a la bonne structure."""
        import importlib
        import freecad.menuiserie.core.joints.slides as pkg
        assert hasattr(pkg, "SlideStrategy")
        assert hasattr(pkg, "SlideParams")
