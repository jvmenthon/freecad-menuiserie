# SPDX-License-Identifier: LGPL-2.1-or-later
"""Configuration d'un atelier FreeCAD : catalogue de réglages, stockage, dossier (ADR 0069).

- :mod:`.catalog` : description et validation bornée des réglages (Python pur) ;
- :mod:`.store` : lecture et écriture des réglages derrière une interface de stockage
  (paramètres FreeCAD ou mémoire), option « Dernier utilisé » (Python pur) ;
- :mod:`.folder` : dossier de l'atelier et écriture atomique d'un fichier (Python pur) ;
- :mod:`.page_model` : filtre, comptes et affichage des valeurs de la page (Python pur) ;
- :mod:`.page` et :mod:`.page_rows` : page de préférences Qt construite d'après un catalogue
  (seuls modules qui importent Qt, par la couche ``PySide`` de FreeCAD).

Aucun de ces modules n'importe FreeCAD ni le reste de l'atelier Menuiserie : l'atelier qui les
utilise fournit son catalogue, le chemin de ses paramètres et ses traductions.
"""
