# ADR 0045 — Répétition en grille X × Y × Z : un mode de saisie, une ligne par axe, copies repérées par cellule

- Statut : **proposé** (demande de jv du 2026-11-08 ; lecture « grille » à confirmer par jv)
- Date : 2026-11-08
- Spécification : [docs/specs/repetition.md](../specs/repetition.md), § 9 « Grille »
- ADR liés : [0043 — Répétition](0043-repetition-objet-de-cotes-et-copies-liees.md),
  [0044 — Répétition d'ensembles](0044-repetition-d-ensembles-et-liaisons-des-copies.md),
  [0003 — Contrat de persistance](0003-contrat-de-persistance.md)

## Contexte

jv : « la répétition peut se faire sur tous les axes en même temps mais avec le même mode de
saisie ». L'objet `Repeat` (ADR 0043) ne répète que sur un axe. Lecture retenue : une **grille**
X × Y × Z. Le mode de saisie (`SpacingMode` : nombre et pas, nombre sur une longueur, pas sur une
longueur) est un seul choix commun ; chaque axe a ses valeurs et son sens. Exemple : 4 × 3 sur X et
Y, pas de 100 mm sur X et de 150 mm sur Y, donne 11 copies en plus de l'original.

Trois questions de modèle se posent : où ranger les réglages de chaque axe sans casser les
documents existants, comment identifier une copie quand le nombre d'un axe change (un rang
linéaire se renumérote : la copie « 5 » d'une grille 4 × 3 devient la « 6 » si X passe à 5), et
quoi faire des assemblages et du suivi du redimensionnement.

## Décision

1. **Modèle de calcul (`core/repeat`).** `RepeatParams` gagne `grid`, un tuple de `AxisRepeat`
   (axe, nombre, pas, longueur, sens) ; `spacing` reste unique. L'ancienne forme à un axe
   (`axis=`, `count=`, `step=`…) reste valable : c'est une grille d'une ligne
   (`RepeatParams.lines`). Le nombre d'une ligne de grille est celui des **éléments de l'axe,
   original compris** ; 1 = axe inactif et écarté (4 × 3 se lit tel quel). L'ancien `count` reste
   un nombre de copies : `count = n` équivaut à une ligne de `n + 1` éléments.
2. **Total borné.** Copies = (nx · ny · nz) − 1, au plus `MAX_COPIES` (100) ; au-delà,
   `RepeatError` traduite (« 11 × 10 donneraient 109 copies… »), avant toute création. En « pas
   sur une longueur », le contrôle se fait après le calcul des nombres.
3. **Identité par cellule.** Chaque copie porte `RepeatCell` (`App::PropertyIntegerList`, lecture
   seule) : `[i, j, k]`, son rang sur X, Y et Z (`[0, 0, 0]` est l'original). C'est la cellule qui
   identifie la copie ; `RepeatIndex` reste un rang linéaire (X d'abord, puis Y, puis Z) pour
   l'ordre d'affichage et les libellés, recalculé à chaque modification. Un libellé automatique
   (« Barreau 5 ») suit le nouveau rang ; un libellé que l'utilisateur a changé est gardé.
   Une copie d'un document d'avant la grille n'a pas `RepeatCell` : sa cellule se déduit de son
   rang sur l'axe de la première ligne (`cell_of`), sans migration.
4. **Persistance (ADR 0003).** La première ligne garde les propriétés historiques de `Repeat`
   (`Axis`, `Count`, `Step`, `Span`, `Reverse`) ; les deux suivantes les reprennent avec le suffixe
   `2` et `3` (`Axis2`, `Count2`, `Step2`, `Span2`, `Reverse2`…). Dans chaque ligne, `Count` est le
   nombre de copies en plus de l'original le long de l'axe. Les lignes sont triées X, Y, Z ; une
   ligne 2 ou 3 inutilisée a `Axis2` = `None`. `Step*` et `Reverse*` sont modifiables dans
   l'éditeur de propriétés (les copies suivent) ; le reste est en lecture seule. Un document
   d'avant la grille n'a ni lignes 2 et 3 ni `RepeatCell` : les propriétés sont ajoutées à
   l'ouverture ou à la première modification ; `Version` reste 1 (ajouts facultatifs, rien à
   migrer). Les noms de ces propriétés sont figés comme les autres.
5. **Expressions.** La position d'une copie de cellule `(i, j, k)` est la source plus, sur chaque
   axe dont le rang n'est pas nul, `rang × (R.Reverse ? −1 : 1) × R.Step` (ligne 2 : `Reverse2`,
   `Step2`…), sur l'axe du repère du conteneur (ADR 0043). Même règle pour l'`Origin` d'un
   ensemble copie et pour le `Placement` de son Std Part (ADR 0044).
6. **Modifier la grille** (`edit_repeat`). Les copies des cellules conservées et leurs assemblages
   enfants restent ; celles des cellules nouvelles sont créées ; celles des cellules qui sortent
   sont supprimées (avec assemblages et Std Part) ; changer un pas déplace les copies par leurs
   expressions. Une cellule qui avait une copie avant la modification et n'en a plus (supprimée ou
   dissociée à la main) n'est pas recréée, comme pour le rang auparavant. Cas particulier : quand
   la répétition passe d'**un seul axe à un seul autre axe**, les copies suivent sur le nouvel
   axe (comportement antérieur) au lieu d'être recréées.
7. **Assemblages.** « Recopier les assemblages » est inchangé. Un assemblage entre deux sources
   vise les copies de la **même cellule** ; une pièce fixe reçoit un assemblage par copie. Un
   assemblage impossible pour une cellule (copie hors de l'hôte…) n'est pas recopié, jugé cellule
   par cellule à chaque édition (ADR 0043, décision de jv du 2026-11-10).
8. **Ensembles.** Un ensemble se répète en grille de la même façon (même position relative par
   cellule, Std Part par copie, ADR 0044).
9. **Suivre le redimensionnement** s'applique **axe par axe** : chaque ligne devient
   « nombre sur une longueur » dont `Span*` est la cote de l'ensemble sur son axe (`Width`, `Depth`,
   `Height`) moins les retraits d'aujourd'hui, et `Step*` en découle. Refus traduit hors ensemble,
   comme avant.
10. **Chevauchement.** Signalé par axe (pas inférieur à la cote des sources sur l'axe), puis sur la
    grille complète (deux éléments quelconques dont les boîtes se recouvrent sur les trois axes).
    Avertissement non bloquant.
11. **Panneau.** Un seul sélecteur de mode ; trois lignes X, Y, Z (case d'activation, nombre
    d'éléments, pas ou longueur selon le mode, « Inverser ») ; aperçu en direct de toutes les
    copies ; total affiché ; refus au-delà de 100. Ctrl + glisser est inchangé (une copie, un axe).

## Conséquences

- Nouveau contrat de persistance : dix propriétés facultatives de `Repeat` et `RepeatCell` sur les
  copies (voir 4). `COPY_PROPERTY_NAMES` (qui définit une copie) n'est pas modifié : `RepeatCell`
  n'est pas exigée.
- Le rang `RepeatIndex` d'une copie conservée peut changer à une modification de la grille
  (affichage seulement) ; seule la cellule identifie.
- Mode « pas sur une longueur » : l'axe est toujours actif (son nombre est calculé) ; un axe ne se
  désactive que par la case du panneau.
- La cote des sources qui sert aux modes « sur une longueur » est lue par axe.
- Limites inchangées : cercle et trajet réservés, 100 copies, pièces en bois à forme libre
  refusées.
- Le rang d'une copie dans les libellés (« Barreau 5 ») dépend de l'ordre X, Y, Z ; il a été jugé
  plus lisible que « Barreau 1-2 ». À confirmer par jv avec le reste de la décision.

## Questions pour jv

- La lecture « grille » est-elle la bonne (et non, par exemple, un tracé en diagonale ou une
  répétition d'une répétition) ?
- Le nombre d'un axe compte l'original (4 × 3 = 11 copies) ; le champ « nombre de copies » d'un
  axe seul du panneau devient « Nombre » (copies + 1). Convient-il ?
