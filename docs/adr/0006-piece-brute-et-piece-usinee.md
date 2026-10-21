# ADR 0006 — Comment un assemblage modifie les pièces : pièce brute et pièce usinée

- Statut : **accepté** (jv, 2026-10-20)
- Date : 2026-10-20
- Spécification : [docs/specs/J3-assemblages.md](../specs/J3-assemblages.md), § 4.1 à 4.4
- ADR liés : [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md) (contrat de
  persistance, forme = parallélépipède aux cotes finies), [0007 — Compatibilité avec les autres
  ateliers](0007-compatibilite-avec-les-autres-ateliers.md)

## Contexte

Un assemblage (tenon-mortaise, rainure-languette, feuillure, tourillons, puis mi-bois et queue
d'aronde en J4) relie deux pièces et modifie leur forme ; il est paramétrique : si une pièce change
de cotes ou de position, l'assemblage suit. Dans FreeCAD, « suivre » veut dire « dépendre » : le
graphe de recalcul est un graphe orienté sans cycle **entre objets** (pas entre propriétés).

Or la mortaise du montant dépend de la position et des cotes de la traverse, et le tenon de la
traverse dépend de celles du montant. Si la forme usinée d'une pièce et ses cotes vivent dans le
même objet, on obtient montant → traverse → montant : un **cycle**, que FreeCAD refuse de recalculer.
Ce n'est pas un détail de réalisation : toute solution où `WoodPart` porte à la fois ses cotes et
sa forme coupée par un assemblage qui lit l'autre pièce contient ce cycle.

Contraintes :

- ADR 0003 : `WoodPart` est un contrat figé (chemin, propriétés, `Version` = 2) ; sa forme est le
  parallélépipède aux cotes finies et `execute()` ne lit que ses trois cotes. Les documents J1
  doivent s'ouvrir sans migration.
- CONTRIBUTING : `execute()` ne fait que reconstruire `obj.Shape` (un objet n'écrit jamais dans un
  autre pendant le recalcul).
- Une pièce porte souvent plusieurs assemblages (un montant de cadre a deux mortaises, une traverse
  deux tenons), qui ne doivent pas dépendre de l'ordre de création.
- ADR 0007 : les formes produites restent des `Part::Feature` ordinaires, utilisables par les
  autres ateliers et lisibles sans l'atelier.

Options étudiées :

1. **Coupe dans `WoodPart`** (la pièce liste ses assemblages et se coupe elle-même) : cycle
   ci-dessus. Le contourner par des liens cachés ou des noms d'objets en texte rend le recalcul
   faux (une pièce déplacée ne retouche pas l'autre ; une cote pilotée par une expression est lue
   avant d'être évaluée) et casse au renommage, au copier-coller et à l'annulation. Rejetée.
2. **L'assemblage porte la forme coupée des deux pièces** (comme `Part::Cut`) : une pièce à deux
   assemblages apparaît deux fois, ou il faut chaîner les assemblages (le second coupe le résultat
   du premier), ce qui rend l'ordre significatif et l'arbre illisible. Rejetée.
3. **Un conteneur unique** (« ouvrage ») qui calcule toutes les pièces : une seule forme composée,
   plus de couleur ni de texture par pièce, sélection d'une pièce impossible. Rejetée.
4. **Copie cachée des cotes** recopiée par `onChanged` : écrit dans un autre objet hors recalcul,
   faux avec les expressions (évaluées pendant le recalcul), fragile à l'annulation. Rejetée.
5. **Séparer la pièce brute et la pièce usinée.** Retenue.

## Décision

1. **Pièce brute** : `WoodPart` reste inchangée (J1, `Version` 2). Elle porte les cotes, le
   matériau, le fil, le repère et les surcotes ; sa forme reste le parallélépipède. La liste de
   débit (J2) continue de la lire.
2. **Assemblage** : un objet `Part::FeaturePython` par assemblage (une classe de proxy par type,
   squelette commun en Template Method), qui relie deux pièces **brutes** (`HostPart`,
   `GuestPart`). Son `execute()` calcule le plan d'usinage à partir des seules pièces brutes et de
   ses paramètres, et ne construit comme forme que les pièces rapportées (tourillons) ; la forme
   est vide pour les autres types.
3. **Pièce usinée** (`MachinedPart`, `Part::FeaturePython`) : créée à la première liaison d'une
   pièce brute, une seule par pièce brute. Elle lie la pièce brute (`Base`) et la liste de ses
   assemblages (`Joints`). Sa forme = (parallélépipède de la brute ∪ ajouts) − enlèvements, dans
   le repère local de la brute, placée au `Placement` de la brute. C'est elle qui est affichée ;
   la brute est masquée et apparaît sous elle dans l'arbre.
4. **Graphe de recalcul** sans cycle, en une seule passe : pièces brutes → assemblages → pièces
   usinées. Chaque assemblage ne lit que des pièces brutes : deux assemblages d'une même pièce sont
   indépendants et leur ordre de création n'a aucun effet. Seule exception (précision du
   2026-10-21, correction D1) : pour vérifier sa cohérence, l'assemblage lit aussi `Base` et
   `Joints` des pièces usinées qui le citent (`InList`), sans en dépendre dans le graphe ; aucun
   cycle n'est créé.
5. **Géométrie dans `core/`** : le plan d'usinage (enlèvements et ajouts en boîtes, cylindres et
   prismes (`Prism`, J4) dans le repère local de chaque pièce) est calculé en Python pur par une stratégie par type
   d'assemblage (registre), testée sans FreeCAD ; `features/` ne fait que convertir en formes Part
   et appliquer les booléennes.
6. **Persistance** (règles de l'ADR 0003, appliquées aux nouveaux objets) : chemins figés
   `freecad.menuiserie.features.machined_part.MachinedPart` et
   `freecad.menuiserie.features.joints.<module>.<Classe>Joint` ; proxies sans état ; `Version` = 1
   et migration dans `onDocumentRestored`. Les aides de réouverture de `WoodPart` sont rendues
   génériques (description des propriétés en données) pour être partagées sans duplication.

## Conséquences

- Les documents J1 s'ouvrent sans changement ; une pièce sans assemblage reste une simple
  `WoodPart`.
- Une pièce assemblée est représentée par **deux objets** : la pièce usinée (visible, sélectionnée
  dans la vue 3D) et la pièce brute (masquée, enfant dans l'arbre). Il faut donc :
  - un double-clic sur la pièce usinée qui ouvre le panneau de la pièce brute ;
  - un déplacement de la pièce usinée reporté sur la brute (question Q4 de la spécification) ;
  - une apparence (couleur, texture) de la pièce usinée lue sur sa brute ;
  - des commandes et une API qui acceptent indifféremment l'une ou l'autre.
- Le nombre d'objets du document augmente (une pièce usinée par pièce assemblée, un objet par
  assemblage). Acceptable pour des meubles (quelques dizaines de pièces).
- La forme usinée peut déborder de la brute (tenon, languette ajoutés : question Q1) ; la liste de
  débit (J2) devra lire les ajouts des assemblages pour les longueurs de débit.
- Un assemblage ne voit pas les usinages des autres (il travaille sur les pièces brutes) :
  deux assemblages qui se recoupent s'additionnent simplement. Suffisant pour J3 et J4.
- La forme de chaque objet est une `Shape` Part ordinaire, enregistrée dans le `.FCStd` :
  utilisable par `Part::Cut`, TechDraw, l'export STEP, et visible sans l'atelier (ADR 0007).
- Revenir sur cette décision (couper dans `WoodPart`) demanderait de résoudre le cycle et une
  migration de tous les documents J3 : c'est une décision difficile à défaire, d'où cet ADR.
