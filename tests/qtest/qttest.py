# SPDX-License-Identifier: LGPL-2.1-or-later
"""Seul point d'entrée de ``QtTest`` dans le dépôt.

La couche de compatibilité ``PySide`` de FreeCAD n'expose pas QtTest : il est importé de PySide6
(FreeCAD 1.1), à défaut de PySide2. Exception unique à la règle « toujours ``from PySide import`` »
(CONTRIBUTING, règles FreeCAD n° 5), vérifiée par ``test_qt_par_la_couche_de_freecad`` : réservée
aux scénarios de ``tests/qtest``, jamais à l'atelier.
"""

try:
    from PySide6.QtTest import QTest
except ImportError:  # FreeCAD compilé avec Qt 5
    from PySide2.QtTest import QTest

__all__ = ["QTest"]
