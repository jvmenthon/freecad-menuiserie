# SPDX-License-Identifier: LGPL-2.1-or-later
"""Configuration d'un atelier FreeCAD : catalogue de réglages, stockage, dossier (ADR 0069).

- :mod:`.catalog` : description et validation bornée des réglages (Python pur) ;
- :mod:`.store` : lecture et écriture des réglages derrière une interface de stockage
  (paramètres FreeCAD ou mémoire), option « Dernier utilisé » (Python pur) ;
- :mod:`.folder` : dossier de l'atelier et écriture atomique d'un fichier (Python pur).

Aucun de ces modules n'importe FreeCAD, Qt ou le reste de l'atelier Menuiserie : l'atelier qui
les utilise fournit son catalogue, le chemin de ses paramètres et ses traductions.
"""
