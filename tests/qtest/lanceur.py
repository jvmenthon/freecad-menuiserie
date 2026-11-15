# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lance un scénario QTest dans FreeCAD et quitte avec son code de retour (CI).

    SCENARIO=tests.qtest.scenario_queue_aronde RAPPORT_QTEST=rapport.txt \\
        xvfb-run -a freecad tests/qtest/lanceur.py

Par rapport au mode test de FreeCAD (``freecad -t <module>``, pratique à la main) :

- le rapport ``unittest`` est écrit dans le fichier ``RAPPORT_QTEST`` au fil de l'eau : la sortie
  standard de FreeCAD est une console tamponnée, perdue si le processus plante ;
- une erreur d'import du scénario donne un rapport et le code 1, pas une boîte de dialogue ;
- le processus quitte par ``os._exit`` : l'arrêt normal de FreeCAD détruit les enveloppes PySide
  des widgets après leurs objets C++ et plante parfois (SIGSEGV dans
  ``Shiboken::BindingManager``), ce qui ferait échouer un scénario réussi.
"""

import os
import traceback
import unittest


def main() -> int:
    with open(os.environ["RAPPORT_QTEST"], "w", encoding="utf-8", buffering=1) as rapport:
        try:
            suite = unittest.defaultTestLoader.loadTestsFromName(os.environ["SCENARIO"])
            resultat = unittest.TextTestRunner(stream=rapport, verbosity=2).run(suite)
        except Exception:
            rapport.write(traceback.format_exc())
            return 1
        return 0 if resultat.wasSuccessful() and resultat.testsRun else 1


os._exit(main())
