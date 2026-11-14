# ADR 0058 — Profils d'arête sur arêtes natives (nommage topologique de FreeCAD 1.x)

- Statut : **proposé** (jv a choisi l'option le 2026-11-14 ; ADR à accepter avec la spécification)
- Date : 2026-11-14
- Spécification : [docs/specs/profils-sur-toute-forme.md](../specs/profils-sur-toute-forme.md)
- ADR liés : [0029 — Profils d'arête](0029-profils-d-arete-par-balayage.md) (complété : sa décision 3
  ne vaut plus que pour les pièces en boîte), [0006 — Pièce brute et usinée](0006-piece-brute-et-piece-usinee.md),
  [0056 — Nommage topologique de FreeCAD 1.1](0056-nommage-topologique-freecad-1-1.md),
  [0057 — Solide retrouvé par ses faces](0057-solide-retrouve-par-ses-faces.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md)

## Contexte

L'ADR 0029 désigne une arête par un code local (« Z+Y- ») parmi 12, ce qui est stable mais ne
vaut que pour une boîte. Une pièce dessinée a des arêtes en nombre quelconque. Il rejetait aussi
`makeFillet`/`makeChamfer` et les numéros d'arête parce que FreeCAD 0.x renumérotait les arêtes à
chaque recalcul. FreeCAD ≥ 1.0 conserve des noms cartographiés ; une sonde en CI (1.1, 2026-11-14)
a montré que, sur un corps en L, 16 liens `PropertyLinkSub` sur 16 suivent leur arête après une
encoche, alors que 12 arêtes changent de numéro. Limites connues : sans carte d'éléments, le lien
garde le numéro ; une arête scindée est perdue.

Options :

1. **Boîte d'encombrement** : profils sur les 12 arêtes de la boîte englobante. Surprend sur une
   forme dessinée (arête profilée qui n'est pas sur la pièce). Rejetée.
2. **Arêtes extrudées** : retrouver les arêtes de la pièce parmi celles d'une boîte par position.
   Ne couvre pas L, T, pièces obliques. Rejetée.
3. **Arêtes natives par `PropertyLinkSub`**, repère de coupe calculé sur l'arête. **Retenue**
   (choix de jv).
4. **`makeFillet`/`makeChamfer` seuls** sur la forme : suivent bien les arêtes natives mais ne font
   que deux familles. Réservée au lot des arêtes courbes (spécification, Q2).

## Décision

1. **`EdgeProfile.EdgeRefs`** (`App::PropertyLinkSub`, objet : la brute) désigne les arêtes
   natives. `Edges` (codes de boîte) reste pour les pièces en boîte ; l'un ou l'autre, jamais les
   deux. `Part` reste la brute. `Version` passe à 2 ; migration : `EdgeRefs` vide.
2. **Carte d'éléments obligatoire** : un profil natif est refusé (création et recalcul) si la forme
   de la brute n'a pas de carte d'éléments, car le lien désignerait alors un numéro, au risque d'une
   autre arête silencieusement. Aucune empreinte de position (les cotes changent légitimement).
3. **Repère de l'arête** : calculé dans `features/edge_frames.py` (seul module qui lit la forme
   FreeCAD) : arête droite, deux faces voisines planes, direction de chaque face, dièdre,
   convexité. `core/edges` reçoit des nombres (`EdgeFrame`) et garde sa coupe en Python pur. Au
   dièdre de 90° la coupe est celle de l'ADR 0029.
4. **Familles** : chanfrein, quart de rond et gorge à tout dièdre saillant ; demi-rond,
   bec-de-corbin et doucine à angle droit seulement. Arête rentrante, courbe ou entre faces non
   planes : refusée au premier lot, avec la raison.
5. **Graphe** : inchangé, sans cycle (brute → profil → pièce usinée) ; le lien pointe la brute.
   Ordre des opérations de la pièce usinée inchangé (ADR 0029, décision 5).
6. **Arête perdue** : le profil le signale seul ; la pièce usinée ignore alors ce profil avec un
   avertissement visible (recommandation, à confirmer par jv, spécification Q3).
7. **Bouts** : dépassement de 0,01 mm seulement si le prolongement de l'arête sort du solide.
8. **Persistance** : chemin et noms figés (règles de l'ADR 0003) ; valeurs de `Family` inchangées.

## Conséquences

- Les profils fonctionnent sur toute pièce dessinée à arêtes droites entre faces planes, et
  survivent aux modifications du corps dans les cas mesurés (cotes, encoche, ajout de fonction).
- Deux modes de désignation coexistent (codes de boîte, liens) : un peu plus de code, mais les
  documents du jalon 1 et les pièces étirées par un ensemble restent intacts.
- Dépendance à FreeCAD ≥ 1.0 (déjà acquise : 1.1, ADR 0023). Comportement des liens à revérifier à
  chaque nouvelle version majeure (tests d'intégration du lot P-0).
- Un fichier enregistré avec des arêtes natives est refusé par une version plus ancienne de
  l'atelier (version inconnue).
- Revenir sur cette décision (codes de position par arête) demanderait de retrouver les arêtes
  d'une forme quelconque par la géométrie, plus fragile.
