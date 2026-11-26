# Recette manuelle : épaisseurs et formats personnels (issue #71, ADR 0028)

1. Créer une pièce en contreplaqué, ouvrir « Épaisseurs standard » : les épaisseurs du matériau,
   et « Ajouter une épaisseur… » sont proposés, sans aucun format de panneau (jv, 2026-11-26).
2. « Ajouter une épaisseur… » : saisir 19 mm. Le menu la liste ; choisie, elle n'affiche plus
   « hors standard ».
3. Fermer FreeCAD, ouvrir un autre projet : l'épaisseur est encore proposée. Le fichier
   `dimensions.json` est à côté de `materiaux.json` (dossier utilisateur `Menuiserie`).
4. Saisir 0 mm ou une valeur hors bornes : message de refus, rien n'est écrit.
