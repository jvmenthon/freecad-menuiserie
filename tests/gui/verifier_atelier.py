# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifie que l'atelier se charge et s'active dans l'interface de FreeCAD.

Exécuté par FreeCAD lui-même (pas par pytest), l'atelier étant installé dans le
dossier ``Mod`` de ``FREECAD_USER_HOME`` :

    QT_QPA_PLATFORM=offscreen RESULTAT=resultat.txt freecad tests/gui/verifier_atelier.py

Le rapport est écrit dans le fichier ``RESULTAT`` car la sortie standard est captée
par la console de FreeCAD. Le code de retour vaut 0 si tout est correct.
"""

import os
import traceback

import FreeCADGui as Gui

ATELIER = "MenuiserieWorkbench"


def verifier() -> list[str]:
    """Retourne la liste des problèmes constatés (vide si tout va bien)."""
    if ATELIER not in Gui.listWorkbenches():
        return [f"{ATELIER} absent de la liste des ateliers"]
    Gui.activateWorkbench(ATELIER)
    actif = Gui.activeWorkbench()
    if actif.name() != ATELIER:
        return [f"atelier actif inattendu : {actif.name()}"]
    if not os.path.isfile(actif.Icon):
        return [f"icône introuvable : {actif.Icon}"]
    return []


def main() -> None:
    with open(os.environ["RESULTAT"], "w", encoding="utf-8") as rapport:
        try:
            problemes = verifier()
        except Exception:
            problemes = [traceback.format_exc()]
        rapport.write("\n".join(problemes) if problemes else "OK : atelier chargé et activé\n")
    # Quitte immédiatement, sans boîte de dialogue ni boucle d'événements.
    os._exit(1 if problemes else 0)


main()
