# Recette manuelle : épaisseurs et formats personnels (issue #71, ADR 0028)

1. Créer une pièce en contreplaqué, ouvrir « Épaisseurs standard » : les épaisseurs du matériau,
   « Ajouter une épaisseur… » et un sous-menu « Formats de panneau » sont proposés.
2. « Ajouter une épaisseur… » : saisir 19 mm. Le menu la liste ; choisie, elle n'affiche plus
   « hors standard ».
3. « Formats de panneau > Ajouter un format… » : 2800 puis 2070 mm. Le choisir règle la longueur
   et la largeur de la pièce.
4. Fermer FreeCAD, ouvrir un autre projet : épaisseur et format sont encore proposés. Le fichier
   `dimensions.json` est à côté de `materiaux.json` (dossier utilisateur `Menuiserie`).
5. Saisir 0 mm ou une valeur hors bornes : message de refus, rien n'est écrit.
