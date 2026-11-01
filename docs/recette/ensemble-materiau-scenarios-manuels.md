# Recette manuelle : matériau de toutes les pièces d'un ensemble (issue #77)

1. Créer un ensemble (par exemple le gabarit Caisson), puis un second ensemble qui le contient
   avec deux pièces de chêne de plus.
2. Double-clic sur l'ensemble extérieur : le panneau montre « Matériau de toutes les pièces »
   avec la liste des matériaux et « Appliquer ».
3. Choisir « Hêtre », **Appliquer** : toutes les pièces, y compris celles du sous-ensemble,
   prennent la couleur et la texture du hêtre ; **OK**. Une seule entrée « Modifier l'ensemble »
   dans l'historique ; Édition > Annuler rétablit le chêne partout.
4. Piloter le matériau d'une pièce par une expression (propriété `MaterialId`), puis **Appliquer** :
   cette pièce reste telle quelle, un avertissement le dit sous la liste et dans la vue rapport ;
   les autres changent.
5. **Annuler** le panneau après un « Appliquer » : tout revient au matériau d'origine.
