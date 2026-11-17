# ADR 0064 — Fermer un caisson autour d'une pièce existante

- Statut : **proposé** (Q1 à Q4 et Q8 tranchées par jv le 2026-11-17 ; restent Q5 à Q7 et Q9)
- Date : 2026-11-17
- Spécification : [docs/specs/fermer-le-caisson.md](../specs/fermer-le-caisson.md)
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0010 — Gabarits générateurs](0010-gabarits-generateurs.md),
  [0037 — Sous-ensemble créé depuis des pièces déjà membres](0037-sous-ensemble-depuis-des-membres.md),
  [0038 — Ensemble à la souris](0038-ensemble-a-la-souris.md)

## Contexte

jv (2026-11-17) : « en sélectionnant le dessous ou le dessus, les côtés sont générés ainsi que le
dessus ou le dessous ». Le menuisier a déjà dessiné une pièce (le dessous d'un meuble, posé où il
veut, avec son matériau et son épaisseur) et veut « fermer » la boîte autour d'elle : choisir la
hauteur, retirer les éléments qu'il ne veut pas (pas de façade, pas de dessus) et choisir les
assemblages.

Le gabarit « Caisson » (ADR 0010) crée déjà un caisson complet, mais à partir de rien : il
crée toutes ses pièces, dessous compris, à l'endroit et aux cotes saisies dans le panneau.

Options étudiées :

1. **Rouvrir le gabarit Caisson pré-rempli** avec les cotes de la pièce sélectionnée, puis
   supprimer la pièce d'origine. Rejetée : la pièce du menuisier (son nom, ses finitions de
   chants, ses assemblages déjà faits, ses liaisons dans un ensemble) serait perdue.
2. **Objet « caisson fermé » persistant** qui régénère ses pièces quand on change la hauteur.
   Rejetée pour les raisons de l'ADR 0010 (création d'objets pendant le recalcul, retouches
   écrasées, second mécanisme de cotes à côté de l'Ensemble).
3. **Gabarit générateur ancré sur une pièce existante** : une fonction pure décrit les pièces à
   ajouter et les assemblages **dans le repère de la pièce sélectionnée** ; la pièce existante
   entre dans le `Layout` comme une pièce « ancre », jamais recréée ni redimensionnée. Retenue.

## Décision

1. **Ancre.** La pièce sélectionnée (pièce brute, ou sa pièce usinée qui renvoie à la brute)
   doit être une pièce de bois rectangulaire (`WoodPart`, pas une pièce dessinée). Elle n'est
   **ni déplacée, ni redimensionnée, ni recréée** : seuls les assemblages l'usinent (pièce
   usinée, ADR 0006).
2. **Repère.** Le caisson est construit dans le repère de l'ancre : X le long de sa longueur,
   Y le long de sa largeur, Z le long de son épaisseur, orienté vers l'intérieur du caisson.
   Toute rotation de l'ancre est donc admise (ADR 0025) : l'ensemble créé porte la même
   rotation dans son Std Part (ADR 0038).
3. **Fonction pure.** `core/templates/closing.py` : `ClosingParams` (rôle de l'ancre, hauteur,
   éléments actifs, épaisseurs, matériaux, assemblages par jonction) + cotes de l'ancre →
   `Layout`. Le `Layout` gagne un champ `anchor` (clé de la pièce existante) : son `PieceSpec`
   décrit l'ancre telle qu'elle est (mode et options « fixe » dans l'ensemble), mais le
   constructeur ne la crée pas.
4. **Constructeur.** `build_layout` reçoit les pièces existantes (`existing={clé: objet}`) et ne
   crée que les autres. Les assemblages utilisent les fabriques J3 existantes (ajout des classes
   nécessaires à `JOINT_CLASSES` : queue d'aronde, onglet, rainure-languette, en plus des
   tourillons et de la feuillure).
5. **Ensemble.** Un nouvel Ensemble (`Template = "ClosedCarcass"`) reçoit l'ancre et les pièces
   créées. Si l'ancre était membre d'un ensemble, elle en sort et le nouvel ensemble devient un
   sous-ensemble de celui-ci, comme dans l'ADR 0037 (une seule transaction).
6. **Pas de régénération.** Comme pour tout gabarit (ADR 0010), changer après coup la hauteur
   passe par l'Ensemble (cote `Height`) ; ajouter un élément oublié se fait à la main ou en
   annulant puis relançant la commande.

## Conséquences

- Aucun nouveau type d'objet persistant : rien à migrer, les pièces créées sont des pièces de bois
  ordinaires, utilisables par les autres ateliers FreeCAD (contrainte de compatibilité de jv).
- Le travail déjà fait sur l'ancre (nom, finitions, assemblages existants) est conservé.
- Le même mécanisme d'ancre servira aux gabarits suivants qui partent d'une pièce existante
  (cadre autour d'un panneau, tiroir dans une niche).
- `Layout` et `build_layout` évoluent : le gabarit Caisson existant passe `anchor=None` et ne
  change pas de comportement (test de non-régression).
- Contrepartie : si l'ancre est ensuite supprimée, le caisson perd son dessous comme toute
  pièce supprimée d'un ensemble ; rien n'est recréé.
