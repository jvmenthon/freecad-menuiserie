# ADR 0043 — Répétition : un objet de cotes et des pièces ordinaires liées par expressions

- Statut : **accepté** (jv, 2026-11-08 ; Q4 et Q5 : cases « Recopier les assemblages » et
  « Suivre le redimensionnement », autres questions selon les ★)
- Date : 2026-11-07
- Spécification : [docs/specs/repetition.md](../specs/repetition.md), issue #180
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi des pièces par expressions natives](0009-suivi-par-expressions-natives.md),
  [0045 — Répétition en grille](0045-repetition-en-grille.md) (proposé : plusieurs axes à la fois)

## Contexte

jv veut une répétition modifiable après coup, dont les copies suivent l'original, dissociables,
extensible au cercle et au trajet. Options :

1. **Tableau Draft ou `App::Link`** : un seul objet à éléments virtuels. Les copies ne peuvent pas
   être usinées ni assemblées une à une et n'ont pas de ligne de débit propre. Rejetée.
2. **Copies indépendantes, créées par une commande** (esprit des gabarits, ADR 0010) : pas de
   suivi de l'original, pas modifiable après coup. Ne répond pas à la demande. Rejetée.
3. **Objet de cotes `Repeat` + copies réelles liées par expressions natives** : retenue. FreeCAD
   interdit de créer ou supprimer des objets pendant un recalcul, donc le nombre de copies change
   par une commande (transaction), tandis que le pas, les cotes et le placement suivent par
   expressions.

## Décision

1. `Repeat` est un objet de données sans forme (comme l'Ensemble) : `Source` (pièces ou ensembles ; un ensemble copié devient un sous-ensemble copie dont les cotes sont liées à la source), `Mode`
   (`Linear`, `Circular` et `Path` réservés, valeurs stables), `Count`, `Step`, `Axis`, `Reverse`.
2. Chaque copie est une pièce ordinaire portant `Repeat` et `RepeatIndex` (lecture seule) ; ses
   cotes et son placement sont des expressions sur la source et sur `Repeat`, écrites par l'API
   dans la transaction en cours, jamais pendant un recalcul.
3. Les assemblages de la source sont recréés pour chaque copie, liés à ceux de l'origine tant que
   la copie est liée.
4. « Dissocier » retire les expressions et le lien `Repeat` : la copie devient libre.
5. `core/repeat/` (Python pur) calcule les décalages ; Draft n'est utilisé que pour le mode
   trajet (placements le long d'une arête), importé tardivement dans `features/`.
6. Le geste de copie à la souris s'appuie sur la même fabrique (répétition d'une copie).

## Conséquences

- Nouveau type persistant : son chemin, son nom de classe et ses propriétés entrent dans le
  contrat de persistance (ADR 0003) dès la première version, d'où les valeurs de `Mode` réservées.
- Les copies gardent tous les avantages des pièces (usinage, assemblages, liste de débit).
- Le nombre de copies ne change que par la commande « Modifier la répétition », pas en tapant
  `Count` dans l'éditeur de propriétés (champ en lecture seule).
- 100 copies liées par expressions : coût de recalcul à mesurer au lot R-a.
- Lot R-b2 (assemblages) : un assemblage enfant porte `RepeatJoint` (lien vers l'origine, lecture
  seule) et ses paramètres sont des expressions sur ceux de l'origine. Une **pièce usinée** choisie
  comme source est remplacée par sa **pièce brute** : cotes, matériau et placement sont dans la
  brute (ADR 0006), la forme usinée dépend des assemblages de la source et ne se copie pas ; la
  copie est une brute neuve qui reçoit sa propre pièce usinée par ses assemblages recopiés. Cela
  évite de refuser la sélection naturelle (la pièce visible) sans copier un usinage qui n'a pas de
  sens pour la copie.
- **Conteneur `App::Part`** : la répétition est créée dans le conteneur de ses sources, comme leurs
  copies (un lien ne sort pas de la portée de son conteneur). L'**axe X, Y ou Z est celui du repère
  du conteneur** (celui de `Placement`, de `Origin` et de la boîte englobante lue sur la forme), pas
  celui du document : un conteneur translaté ou tourné déplace les copies le long de ses propres
  axes. Le glissement Ctrl (R-d) lit donc l'axe de la flèche dans `Placement` de la pièce, non dans
  son placement global, et n'a pas à refuser un conteneur tourné. Des sources réparties dans des
  conteneurs différents sont refusées (message traduit).
- **Assemblage impossible** (jv, 2026-11-10, remplace « créé même infaisable ») : un assemblage
  enfant n'est créé que s'il est réalisable entre la copie placée et sa pièce partenaire
  (`features/joints/feasible.plan_error`, mêmes calculs que `plan_for` ; le cache de plans ne
  mémorise jamais un échec). Chaque édition réévalue : l'enfant devenu impossible est supprimé,
  le manquant devenu possible est créé, le dissocié ne revient pas. Le nombre d'assemblages non
  recopiés est un avertissement (vue rapport et panneau). Limite : le recalcul seul ne crée ni ne
  supprime rien (pas d'écriture de structure dans `execute`/recalcul).
- **Ajouts après coup** : « Modifier la répétition » recopie les assemblages de la source sur
  **tous** les rangs (un assemblage ajouté à la source après la création va aussi aux copies
  existantes, sans doublon). Conséquence : un assemblage enfant supprimé à la main revient à la
  prochaine édition ; pour s'en passer, dissocier la copie ou décocher « Recopier les assemblages ».
  Un enfant dissocié (`unlink_joint`) ne revient pas.
- Une répétition dont la dernière source a été supprimée reste dans le document, vide : « Modifier »
  la refuse avec le message « aucune pièce à répéter » ; elle se supprime à la main.
