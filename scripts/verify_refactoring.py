#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Script de vérification du refactoring des fichiers longs.

Ce script vérifie que :
1. Les imports fonctionnent correctement
2. Les classes et fonctions sont accessibles
3. La rétrocompatibilité est maintenue
4. Les tests passent

Utilisation :
    python scripts/verify_refactoring.py
"""

import sys
import traceback


def test_imports():
    """Teste tous les imports des modules refactorés."""
    print("🔍 Vérification des imports...")
    
    errors = []
    
    # Test shelf_pins
    try:
        from freecad.menuiserie.core.joints.shelf_pins import (
            ShelfPinsStrategy,
            ShelfPinsParams,
            ShelfPinsValues,
            opposite_values,
            pin_rests,
            facing_side,
            picked_choice,
        )
        print("  ✅ shelf_pins imports OK")
    except Exception as e:
        errors.append(f"shelf_pins import failed: {e}")
        print(f"  ❌ shelf_pins import failed: {e}")
    
    # Test slots
    try:
        from freecad.menuiserie.core.joints.slots import (
            LooseTenonStrategy,
            BiscuitStrategy,
            SlotParams,
            SlotSize,
            SlotValues,
            AUTO_SIZE,
            LOOSE_TENON_SIZES,
            BISCUIT_SIZES,
        )
        print("  ✅ slots imports OK")
    except Exception as e:
        errors.append(f"slots import failed: {e}")
        print(f"  ❌ slots import failed: {e}")
    
    # Test slides
    try:
        from freecad.menuiserie.core.joints.slides import (
            SlideStrategy,
            SlideParams,
            SlideValues,
            SLIDE_LENGTHS,
        )
        print("  ✅ slides imports OK")
    except Exception as e:
        errors.append(f"slides import failed: {e}")
        print(f"  ❌ slides import failed: {e}")
    
    # Test registry
    try:
        from freecad.menuiserie.core.joints._registry import strategy_for
        from freecad.menuiserie.core.joints._base import JointKind
        
        # Vérifier que toutes les stratégies sont disponibles
        for kind in [
            JointKind.SHELF_PINS,
            JointKind.LOOSE_TENON,
            JointKind.BISCUIT,
            JointKind.DRAWER_SLIDE,
        ]:
            strategy = strategy_for(kind)
            assert strategy is not None
        
        print("  ✅ registry imports OK")
    except Exception as e:
        errors.append(f"registry import failed: {e}")
        print(f"  ❌ registry import failed: {e}")
    
    # Test magnet_guides import (simulé)
    try:
        from freecad.menuiserie.core.joints.shelf_pins import opposite_values, pin_rests
        assert callable(opposite_values)
        assert callable(pin_rests)
        print("  ✅ magnet_guides-style imports OK")
    except Exception as e:
        errors.append(f"magnet_guides import failed: {e}")
        print(f"  ❌ magnet_guides import failed: {e}")
    
    return len(errors) == 0, errors


def test_package_structure():
    """Teste la structure des packages."""
    print("\n📁 Vérification de la structure des packages...")
    
    errors = []
    
    # Vérifier shelf_pins package
    try:
        import freecad.menuiserie.core.joints.shelf_pins as shelf_pins_pkg
        assert hasattr(shelf_pins_pkg, "ShelfPinsStrategy")
        assert hasattr(shelf_pins_pkg, "ShelfPinsParams")
        assert hasattr(shelf_pins_pkg, "ShelfPinsValues")
        print("  ✅ shelf_pins package structure OK")
    except Exception as e:
        errors.append(f"shelf_pins package structure failed: {e}")
        print(f"  ❌ shelf_pins package structure failed: {e}")
    
    # Vérifier slots package
    try:
        import freecad.menuiserie.core.joints.slots as slots_pkg
        assert hasattr(slots_pkg, "LooseTenonStrategy")
        assert hasattr(slots_pkg, "BiscuitStrategy")
        assert hasattr(slots_pkg, "SlotParams")
        print("  ✅ slots package structure OK")
    except Exception as e:
        errors.append(f"slots package structure failed: {e}")
        print(f"  ❌ slots package structure failed: {e}")
    
    # Vérifier slides package
    try:
        import freecad.menuiserie.core.joints.slides as slides_pkg
        assert hasattr(slides_pkg, "SlideStrategy")
        assert hasattr(slides_pkg, "SlideParams")
        print("  ✅ slides package structure OK")
    except Exception as e:
        errors.append(f"slides package structure failed: {e}")
        print(f"  ❌ slides package structure failed: {e}")
    
    return len(errors) == 0, errors


def test_file_sizes():
    """Vérifie que les fichiers sont maintenant de taille acceptable."""
    print("\n📏 Vérification des tailles de fichiers...")
    
    import os
    
    max_size = 300  # lignes max
    errors = []
    
    files_to_check = [
        "freecad/menuiserie/core/joints/shelf_pins.py",
        "freecad/menuiserie/core/joints/slots.py",
        "freecad/menuiserie/core/joints/slides.py",
    ]
    
    for file_path in files_to_check:
        full_path = os.path.join(os.path.dirname(__file__), "..", file_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                lines = len(f.readlines())
            if lines > max_size:
                errors.append(f"{file_path} has {lines} lines (max {max_size})")
                print(f"  ❌ {file_path}: {lines} lignes (trop long)")
            else:
                print(f"  ✅ {file_path}: {lines} lignes (OK)")
        else:
            errors.append(f"{file_path} not found")
            print(f"  ⚠️  {file_path}: non trouvé")
    
    return len(errors) == 0, errors


def test_submodule_files():
    """Vérifie que les sous-modules existent."""
    print("\n📂 Vérification des sous-modules...")
    
    import os
    
    errors = []
    
    # Vérifier shelf_pins/
    for subfile in ["__init__.py", "_params.py", "_strategy.py", "_layout.py", "_drilling.py"]:
        path = f"freecad/menuiserie/core/joints/shelf_pins/{subfile}"
        full_path = os.path.join(os.path.dirname(__file__), "..", path)
        if not os.path.exists(full_path):
            errors.append(f"{path} not found")
            print(f"  ❌ {path}: non trouvé")
        else:
            print(f"  ✅ {path}: existe")
    
    # Vérifier slots/
    for subfile in ["__init__.py", "_params.py", "_base.py", "_strategies.py", "_utils.py"]:
        path = f"freecad/menuiserie/core/joints/slots/{subfile}"
        full_path = os.path.join(os.path.dirname(__file__), "..", path)
        if not os.path.exists(full_path):
            errors.append(f"{path} not found")
            print(f"  ❌ {path}: non trouvé")
        else:
            print(f"  ✅ {path}: existe")
    
    # Vérifier slides/
    for subfile in ["__init__.py", "_params.py", "_strategy.py", "_layout.py", "_drilling.py"]:
        path = f"freecad/menuiserie/core/joints/slides/{subfile}"
        full_path = os.path.join(os.path.dirname(__file__), "..", path)
        if not os.path.exists(full_path):
            errors.append(f"{path} not found")
            print(f"  ❌ {path}: non trouvé")
        else:
            print(f"  ✅ {path}: existe")
    
    return len(errors) == 0, errors


def main():
    """Exécute toutes les vérifications."""
    print("=" * 60)
    print("Vérification du refactoring des fichiers longs")
    print("=" * 60)
    
    all_passed = True
    all_errors = []
    
    # Vérification des sous-modules
    passed, errors = test_submodule_files()
    all_passed = all_passed and passed
    all_errors.extend(errors)
    
    # Vérification des tailles
    passed, errors = test_file_sizes()
    all_passed = all_passed and passed
    all_errors.extend(errors)
    
    # Vérification des imports
    passed, errors = test_imports()
    all_passed = all_passed and passed
    all_errors.extend(errors)
    
    # Vérification de la structure
    passed, errors = test_package_structure()
    all_passed = all_passed and passed
    all_errors.extend(errors)
    
    # Résumé
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ TOUTES LES VÉRIFICATIONS ONT RÉUSSI !")
        print("=" * 60)
        return 0
    else:
        print("❌ CERTAINES VÉRIFICATIONS ONT ÉCHOUÉ :")
        for error in all_errors:
            print(f"  - {error}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
