# ADR 0029 — Profils d'arête : section balayée, soustraite dans la pièce usinée

- Statut : **accepté** (jv, 2026-11-01)
- Date : 2026-11-01
- Spécification : [docs/specs/finition-des-chants.md](../specs/finition-des-chants.md), § 4.1 à 4.5
- ADR liés : [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md) (complété),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0020 — La pièce en bois](0020-piece-en-bois-enveloppe-d-un-corps.md)

## Contexte

jv veut donner des profils aux arêtes des pièces (chanfrein, quart de rond, arête cassée, gorge,
demi-rond, bec-de-corbin, doucine), paramétriques, sans changer les cotes finies ni le débit,
compatibles avec les assemblages, et avec une bibliothèque de profils extensible.

Contraintes : le graphe de recalcul est sans cycle (ADR 0006) ; `execute()` ne reconstruit que
`obj.Shape` ; la logique est en Python pur dans `core/` ; les formes restent des `Part::Feature`
ordinaires (ADR 0007) ; le choix d'une arête ne doit pas dépendre d'un numéro d'arête instable.

Options étudiées :

1. **Propriété de `WoodPart`** (liste de profils dans la brute) : change un contrat figé
   (ADR 0003), oblige à migrer tous les documents et mélange cotes et usinage, ce que l'ADR 0006
   a justement séparé. Rejetée.
2. **`Part.makeFillet` / `makeChamfer` sur la forme usinée** : coins parfaits, mais les arêtes se
   retrouvent par numéro (instable après un assemblage : nommage topologique), échecs OCC fréquents
   sur formes coupées, impossible à tester sans FreeCAD, et uniquement chanfrein et congé (pas de
   gorge, de doucine ni de bec-de-corbin). Rejetée.
3. **Un objet par profil, qui retire de la matière dans la pièce usinée** (même mécanisme que les
   assemblages), la section étant calculée en `core/` et balayée le long de l'arête. Retenue.
4. **Un objet `Part::Cut` par profil** (outils FreeCAD standard) : change la nature de l'objet
   affiché, brise les assemblages (qui lisent la pièce usinée) et multiplie les objets. Rejetée.

## Décision

1. **Objet `EdgeProfile`** (`Part::FeaturePython`, type `Menuiserie::EdgeProfile`, « Profil
   d'arête »), un par ensemble d'arêtes de même profil, lié à une pièce **brute** (`Part`). Sa
   forme est vide ; son `execute()` ne vérifie que ses bornes. Il apparaît dans `Finishes`, nouvelle
   liste de `MachinedPart` (lecture seule).
2. **Graphe sans cycle** : brute → profil → pièce usinée. Un profil ne lit que sa brute.
3. **Arêtes désignées par un code local** (`"Z+Y-"`, deux faces du repère local de la pièce,
   énumération fermée de 12). Jamais de numéro d'arête de la forme. Le choix survit aux
   changements de cotes, aux rotations et aux assemblages.
4. **Section balayée en `core/edges/`** : chaque famille de profil (chanfrein, quart de rond,
   gorge, demi-rond, bec-de-corbin, doucine) est une stratégie enregistrée dans un registre ; elle
   renvoie une section plane (segments et arcs exacts). `edge_cut` la balaye le long de l'arête
   (nouveau type `Extrusion`, dans `PlanSolid`). `features/solids.py` la convertit en solide
   `Part`. « Arête cassée » est un préréglage du quart de rond.
5. **Ordre des opérations** de la pièce usinée :
   `brute − bande − profils − trims, puis + ajouts − enlèvements des assemblages`. Les profils
   passent avant les ajouts et les enlèvements : un tenon garde ses arêtes vives, une mortaise reste
   d'équerre. Un profil qui touche la zone d'un assemblage donne un avertissement.
6. **Persistance** (règles de l'ADR 0003) : chemin figé
   `freecad.menuiserie.features.edge_profile.EdgeProfile`, proxy sans état, `Version` = 1.
   `MachinedPart` passe en `Version` 2 (propriété `Finishes` vide à la migration).
7. **Périmètre** : pièces de bois et pièces usinées. Une pièce en bois (`ShapedPart`, forme libre)
   est refusée ; profils personnels (JSON) et arrondi de coin reportés.

## Conséquences

- Les documents existants s'ouvrent sans changement ; `WoodPart` et les assemblages sont intacts.
- Un nouveau type de solide balayé (`Extrusion`) dans `core/` sert aussi à de futurs usinages
  (rainures profilées, moulures).
- Au croisement de deux arêtes profilées, la forme est la coupe commune des deux balayages
  (angle vif, sans coin sphérique) ; assumé et documenté.
- Les cotes et le volume affichés ne changent pas (le volume est légèrement surestimé).
- Une version plus ancienne de l'atelier refuse la pièce usinée enregistrée en version 2.
- Revenir sur cette décision (profils portés par la brute) demanderait une migration de tous les
  documents : d'où cet ADR.
