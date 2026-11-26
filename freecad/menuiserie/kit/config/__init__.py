# SPDX-License-Identifier: LGPL-2.1-or-later
"""Configuration d'un atelier FreeCAD : catalogue de réglages, stockage, dossier (ADR 0069).

- :mod:`.catalog` : description et validation bornée des réglages (Python pur) ;
- :mod:`.store` : lecture et écriture des réglages derrière une interface de stockage
  (paramètres FreeCAD ou mémoire), option « Dernier utilisé » (Python pur) ;
- :mod:`.folder` : dossier de l'atelier et écriture atomique d'un fichier (Python pur) ;
- :mod:`.page_model` : filtre, comptes et affichage des valeurs de la page (Python pur) ;
- :mod:`.import_model` : lignes de l'aperçu d'un import et sélection (Python pur) ;
- :mod:`.page`, :mod:`.page_rows` et :mod:`.page_extra` : page de préférences Qt construite
  d'après un catalogue, avec des lignes supplémentaires fournies par l'atelier ;
- :mod:`.page_exchange`, :mod:`.page_dialogs` et :mod:`.page_import` : boutons Exporter et
  Importer, leurs dialogues remplaçables et la fenêtre d'aperçu (Qt, par la couche ``PySide`` de
  FreeCAD ; seuls modules, avec la page, qui importent Qt).

Aucun de ces modules n'importe FreeCAD ni le reste de l'atelier Menuiserie : l'atelier qui les
utilise fournit son catalogue, le chemin de ses paramètres et ses traductions.
"""
