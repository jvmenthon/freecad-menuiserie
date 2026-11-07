# ADR 0041 — Pièce vide : un objet de contexte aimanté mais hors débit

- Statut : **proposé** (en attente des réponses de jv, spec § 8)
- Date : 2026-11-07
- Spécification : [docs/specs/piece-vide.md](../specs/piece-vide.md)
- ADR liés : [0007](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008](0008-ensemble-objet-de-cotes.md), [0021](0021-deplacement-a-la-souris-avec-aimantation.md)

## Contexte

jv veut créer une pièce d'habitation vide pour y positionner un meuble. Il faut un objet qui se
voit, que les meubles puissent viser, mais qui n'est pas du bois à débiter.

Options :

1. **Une pièce de bois spéciale** (flag « hors débit »). Mélange deux notions, expose des
   propriétés de bois sans sens (fil, matériau) et risque d'entrer dans la liste de débit. Rejetée.
2. **Arch / BIM (`Arch::Space`, `Arch::Wall`)**. Dépendance lourde, objets non aimantables par
   notre magnétisme, conflit possible avec d'autres ateliers. Rejetée.
3. **Objet de contexte propre `Local`** : forme Part (solides murs, sol, plafond), cotes en
   propriétés, `Proxy` dans notre espace de noms. Retenue.

## Décision (proposée)

1. `Local` est un objet Part à cotes (longueur, largeur, hauteur, épaisseur des murs). Les faces
   intérieures servent de cibles d'aimantation de priorité propre.
2. Modèle pur dans `core/room/` (validation, géométrie des murs et ouvertures), testable sans
   FreeCAD ; `features/room.py` instancie l'objet, dans une transaction.
3. Il porte une marque de contexte : la collecte de la liste de débit l'ignore par construction
   (filtre sur le type), non par une propriété modifiable.
4. Le fichier s'ouvre sans notre atelier : les solides restent visibles (ADR 0007).

## Conséquences

- Aucun impact sur les pièces de bois ni sur le débit.
- Le magnétisme gagne une catégorie de cibles « contexte » ; à tester avec le glissement existant.
- Contrepartie : un module de plus à maintenir ; pas de compatibilité IFC.
