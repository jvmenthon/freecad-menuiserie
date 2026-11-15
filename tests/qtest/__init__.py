# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénarios d'interface joués avec QTest dans le vrai FreeCAD (``freecad -t <module>``).

Les modules ne s'appellent pas ``test_*.py`` : pytest ne doit pas les ramasser (ils importent
``FreeCADGui``). Voir ``docs/tests-gui-qtest.md``.
"""
