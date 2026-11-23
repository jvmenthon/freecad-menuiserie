# Épaisseur d'une pièce assemblée, et ensemble supprimé avec son Std Part

- Statut : **proposée** (demandes de jv du 2026-11-15, doutes D1 et D4 du fil QTest)
- ADR : [0060](../adr/0060-epaisseur-qui-defait-un-assemblage.md),
  [0061](../adr/0061-ensemble-supprime-avec-son-std-part.md),
  [0065](../adr/0065-boites-toujours-recalees.md)
- Maquettes : panneau C (choisie), souris B (choisie)

## 1. Épaisseur qui défait un assemblage

Exemple : angle à queue d'aronde, H à plat (griffes), I debout (queues), I de 18 à 30 mm.

| Geste | Comportement |
| --- | --- |
| Panneau de I, épaisseur 30 | Encadré sous les cotes : « Queue d'aronde avec « H ». Où ajouter les 12 mm ? » ; « Vers l'intérieur (reste à fleur) » coché et appliqué ; « Vers l'extérieur et allonger « H » de 12 mm » ; « Revenir à 18 mm » |
| Clic sur « allonger » | I reprend sa place, H passe à 412 mm (son bout à fleur recule de 12 mm), visible tout de suite dans la vue 3D |
| « 22 » tapé à la place de « 18 » (étape « 2 ») | Aucun choix ne tient à 2 mm : rien n'est écrit (aucun assemblage en erreur), « OK » inactif, « Aucun choix ne garde l'assemblage à cette épaisseur : elle n'est pas appliquée. » ; la touche suivante applique 22 mm |
| Clic sur « Revenir » | I revient à 18 mm, le champ aussi, l'encadré disparaît |
| Panneau de H, épaisseur 30 (rien n'est défait : I suit sa face haute) | Encadré aussi : « Laisser en l'état » en tête, coché et appliqué ; puis « Vers l'intérieur (reste à fleur) », « allonger » (grisé si l'autre pièce n'arrive pas à fleur), « Revenir à 18 mm » |
| H copie d'une répétition | « allonger » grisé : « « H 2 » est une copie : elle suit sa répétition et ne peut pas être modifiée. » |
| « OK » | Une seule entrée d'annulation « Modifier une pièce de bois » |
| Poignée de la face extérieure de I | H s'allonge en direct ; « « H » +12,00 mm » près de la souris ; message dans la vue rapport au relâchement |
| Idem, H non modifiable | La poignée reste à 18 mm, « Butée : … » en rouge près de la souris |
| Poignée de la face intérieure de I | I s'épaissit vers l'intérieur, rien d'autre ne bouge |
| Poignée de la face haute, pièce posée dessus (tenon) | Elle monte avec la face, usinages à jour dans l'aperçu ; Échap la rend |
| Échap pendant le glissement | Tout revient, H compris |
| Bureau assemblé et regroupé, joue gauche 22 → 30 mm dans son panneau | Encadré avec les mêmes choix ; « vers l'intérieur » pousse la voile et la joue droite de 8 mm ; « OK » : ensemble de 1208 mm, membres reliés, aucun objet en erreur |
| Idem, « Annuler » | Cotes, placements et liaisons de l'ensemble rendus |
| Côté d'un caisson (sous-ensemble du bureau) épaissi vers l'extérieur, « OK » | Boîtes du caisson et du bureau recalées sur leurs membres, rien ne bouge à l'écran (ADR 0065) |

Critères d'acceptation : E1 encadré et choix ci-dessus (aussi quand rien n'est défait, avec
« Laisser en l'état ») ; E2 choix impossible grisé avec sa raison, rien d'écrit si aucun ne tient ;
E3 saisies successives sans cumul ; E4 une entrée d'annulation ; E5 souris : l'autre pièce suit,
butée si elle ne peut pas, Échap rend tout ; E6 membre d'ensemble assemblé : mêmes choix, ensemble
relié d'après le résultat, boîtes recalées jusqu'au plus haut parent (jv, 2026-11-17) ; membre
sans assemblage et éditeur de propriétés inchangés ; poignée d'un membre assemblé tirée vers
l'extérieur : la face tirée décide, boîte recalée (jv, 2026-11-23, ADR 0060 point 6).

## 2. Std Part d'ensemble supprimé en gardant son contenu

| Geste | Comportement |
| --- | --- |
| Suppr sur le Std Part, « Non » | Pièces en place (inchangé), objet ensemble supprimé juste après, membres déliés |
| Suppr, « Oui » | Tout est supprimé (inchangé) |
| Ctrl+Z | 1er : l'ensemble revient ; 2e : le Std Part revient, pièces rangées dedans |

Critères : S1 ensemble supprimé, géométrie inchangée, document sans erreur ; S2 rien supprimé
pendant la boucle de FreeCAD ; S3 deux entrées d'annulation ; S4 sous-ensemble : garde son Std
Part et sort du parent.
