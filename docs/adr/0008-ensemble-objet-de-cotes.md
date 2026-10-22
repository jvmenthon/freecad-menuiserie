# ADR 0008 — L'Ensemble : un objet de cotes hors conteneur

- Statut : **accepté** (jv, 2026-10-21 : question Q1 de la spécification J4, recommandation retenue)
- Date : 2026-10-21
- Spécification : [docs/specs/J4-ensembles.md](../specs/J4-ensembles.md), § 4.1, § 4.4.1, § 4.9
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0009 — Suivi des pièces par expressions natives](0009-suivi-par-expressions-natives.md)

## Contexte

Exigence de jv : modifier la profondeur d'un bureau et de toutes les pièces concernées. Il faut un
objet « Ensemble » qui porte des cotes globales (`Width`, `Depth`, `Height`) et que les pièces
suivent par des expressions FreeCAD natives (ADR 0007, point 6). Cet objet doit aussi permettre de
déplacer, tourner et dupliquer un meuble, sans gêner Std Part, `App::Link`, l'atelier Assembly,
TechDraw ni l'export STEP.

Dans FreeCAD, un groupe (`Group` d'une extension de groupe) **lie** ses enfants : il en dépend
dans le graphe de recalcul. Or les pièces doivent dépendre des cotes de l'ensemble (leurs
expressions le lisent). Si l'ensemble est le groupe de ses pièces, on obtient
ensemble → pièce → ensemble. Vérifié sur FreeCAD 1.1 (2026-10-21) : pour un `App::Part` comme
pour un `App::DocumentObjectGroupPython` portant une cote, `setExpression` sur un enfant qui lit
cette cote est refusé (« cyclic reference »). De plus, un groupe géométrique (`GeoFeatureGroup`, comme Std Part)
change le repère et la portée des liens de ses enfants.

Options étudiées :

1. **Conteneur de l'atelier** (`App::GeometryPython` + `App::GeoFeatureGroupExtensionPython`) :
   repère propre et déplacement natif. Mais le cycle ci-dessus apparaît dès qu'une pièce lit une
   cote de son conteneur. Le contourner (cotes portées par un objet enfant, liens cachés) rend le
   modèle obscur. Cette option refait aussi Std Part. Sa prise en charge par TechDraw, Assembly et
   l'export STEP n'est pas garantie pour un groupe Python, et l'assembleur de J3 refuse les pièces
   de conteneurs différents. Rejetée.
2. **Std Part natif** (`App::Part`) muni de propriétés dynamiques : pas de proxy, donc ni
   `Version` ni migration (ADR 0003), ni avertissement au changement de cote. Le cycle conteneur →
   enfant → conteneur demeure. Rejetée.
3. **Feuille de calcul** (`Spreadsheet::Sheet`) qui porte les cotes : native et sans cycle, mais
   sans règle, sans avertissement et sans lien avec les pièces. L'utilisateur peut toujours en
   utiliser une pour piloter les cotes de l'ensemble. Rejetée comme modèle, gardée comme usage
   possible.
4. **Objet de cotes hors conteneur.** Retenue.

## Décision

1. L'Ensemble est un `App::FeaturePython` (nom interne `Furniture`, type `Menuiserie::Furniture`,
   libellé « Ensemble »). Il n'a **pas de forme** et **aucun lien vers ses membres**. Il porte
   `Width`, `Depth`, `Height`, `Origin` (coin de départ), `Template` et `Version`. (`EdgeMargin`,
   un seuil de retrait proposé avant la réponse de jv à Q3, est supprimé : chaque membre porte
   ses propres options de distance, ADR 0009.)
2. **Appartenance** : chaque membre (pièce brute ou sous-ensemble) porte un lien `Furniture` vers
   son ensemble. Les membres sont l'`InList` de l'ensemble, filtrée par ce lien. Les dépendances
   vont toujours des membres vers l'ensemble.
3. **Repère** : celui du conteneur commun de l'ensemble et de ses membres (document ou Std Part),
   avec X = largeur, Y = profondeur, Z = hauteur. Les membres d'un ensemble sont tous dans le même
   conteneur que lui, comme les deux pièces d'un assemblage J3.
4. **Déplacer, tourner, dupliquer un meuble** : par Std Part et `App::Link`, outils natifs.
   L'Ensemble ne les remplace pas et ne les modifie pas. Un Std Part qui contient un ensemble sert
   aussi de composant dans l'atelier Assembly.
5. **Arbre** : le ViewProvider présente les membres sous l'ensemble (`claimChildren`, affichage
   seulement). Le document ne contient aucun lien pour cela.
6. **Persistance** : contrat de l'ADR 0003 (chemin figé
   `freecad.menuiserie.features.furniture.Furniture`, proxy sans état, `Version` = 1, migration
   dans `onDocumentRestored`).

## Conséquences

- Aucun cycle possible : ensemble → membres → assemblages → pièces usinées, en un seul recalcul.
- Les pièces gardent leur conteneur, leur repère et la portée de leurs liens. Les assemblages de J3
  et leur règle « même conteneur » s'appliquent sans changement.
- Le menuisier qui veut déplacer tout le meuble le range dans un Std Part. Le panneau et le README
  l'expliquent.
- Supprimer l'ensemble par un script (`doc.removeObject`) appelle `Furniture.unsetupObject`, qui
  fait `release_members` : les expressions de liaison des membres sont retirées, les pièces
  gardent leur forme. Dans l'interface, `onDelete` du ViewProvider appelle `remove_members`
  (critère P2), qui retire en plus les propriétés de membre (groupe « Ensemble »). Écart : par
  script, ces propriétés restent sur les membres.
- Les sous-ensembles (Q2 : retenus par jv le 2026-10-21) sont des membres comme les autres :
  leurs cotes et leur `Origin` reçoivent des liaisons, et ils portent les mêmes options de
  distance que les pièces.
- Revenir à un conteneur demanderait de déplacer les pièces dans un groupe et de migrer chaque
  document J4. C'est une décision difficile à défaire, d'où cet ADR.
