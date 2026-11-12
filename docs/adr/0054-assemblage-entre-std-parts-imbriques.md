# ADR 0054 — Assemblage entre pièces de Std Part imbriqués

- Statut : **proposé**
- Date : 2026-11-12
- Issue : #209
- ADR liés : [0003](0003-modele-de-la-piece-de-bois.md), [0007](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008](0008-ensemble-objet-de-cotes.md), [0038](0038-ensemble-a-la-souris.md)

## Contexte

Depuis l'ADR 0038, chaque ensemble et chaque sous-ensemble a son Std Part. Deux pièces d'un même
ensemble (une pièce de tiroir et une pièce du caisson) peuvent donc avoir des conteneurs
différents. `_checked_blanks` exigeait le même conteneur : « Les deux pièces doivent être dans le
même conteneur ». Or la géométrie d'un assemblage lit le `Placement` des brutes, local à leur
conteneur.

## Décision

1. **Conteneurs acceptés** : les mêmes (comportement inchangé), ou deux Std Part (`App::Part`) de
   la même arborescence (même Std Part racine : imbriqués ou frères). Refus traduit inchangé
   sinon : corps PartDesign, pièce hors de tout Std Part face à une pièce rangée, arborescences
   distinctes.
2. **Repère de calcul** : celui du conteneur de l'hôte. L'hôte y est lu par son `Placement` ;
   l'invitée, si son conteneur diffère, par `conteneur_hôte.getGlobalPlacement().inverse() *
   invitée.getGlobalPlacement()`. Le plan de `core` ne dépend que du placement relatif des deux
   brutes : les enlèvements restent exprimés dans le repère de chaque brute. L'assemblage et sa
   pièce usinée restent dans le conteneur de l'hôte (inchangé).
3. **Suivi des déplacements** : déplacer un Std Part ne touche pas les pièces qu'il contient.
   Une propriété cachée `Frames` (`App::PropertyLinkListGlobal`) garde les Std Part des deux pièces
   quand leurs conteneurs diffèrent (vide sinon) ; leur modification recalcule l'assemblage.
4. **Portée des liens** : `HostPart` et `GuestPart` passent de `App::PropertyLink` à
   `App::PropertyLinkGlobal`, sinon FreeCAD refuse un lien vers un autre Std Part (comme `Furniture`,
   ADR 0038). Les documents existants sont migrés à la réouverture (type recréé, pièce gardée) ;
   sans effet sur les autres ateliers (le lien reste un lien).
5. Hors périmètre : le perçage LR32 (`both_sides`, voisines) ne considère toujours que les pièces du
   même conteneur ; la coulisse utilise les rotations globales.

## Conséquences

- Un assemblage entre tiroir et caisson donne la même forme qu'entre pièces d'un même conteneur.
- Non testé dans FreeCAD pendant la rédaction (pas de FreeCAD dans la session) : tests
  d'intégration `test_assemblage_std_parts.py` en CI.
