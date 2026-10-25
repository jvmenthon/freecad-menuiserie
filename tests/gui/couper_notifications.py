# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coupe la zone de notifications de FreeCAD avant les vérifications hors écran.

Lancé par ``freecadcmd`` avec le même ``FREECAD_USER_HOME`` que ``verifier_atelier.py``. Hors
écran, la bulle de notification appelle ``raise()``, que le greffon « offscreen » ne prend pas en
charge ; l'avertissement de Qt repasse par la zone de notifications, qui attend alors son propre
verrou : FreeCAD se bloque jusqu'à la limite de temps de la CI. Les réglages sont lus au démarrage
de l'interface, d'où ce lancement préalable.
"""

import os
import sys

import FreeCAD as App

if not os.environ.get("FREECAD_USER_HOME"):
    # Sans dossier d'utilisateur dédié, ce seraient les préférences du développeur.
    sys.exit("FREECAD_USER_HOME non défini : préférences de l'utilisateur laissées intactes")

parametres = App.ParamGet("User parameter:BaseApp/Preferences/NotificationArea")
parametres.SetBool("NotificationAreaEnabled", False)
parametres.SetBool("NonIntrusiveNotificationsEnabled", False)
App.saveParameter()
