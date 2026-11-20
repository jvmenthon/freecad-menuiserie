# ADR 0032 — Gabarits composés : une porte ou un tiroir se construit dans l'ouverture d'un meuble

- Statut : **proposé** (en attente de la réponse de jv à la question Q8 de la spécification)
- Date : 2026-11-05
- Spécification : [docs/specs/gabarits-meubles.md](../specs/gabarits-meubles.md), § 4
- ADR liés : [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi des pièces par expressions natives](0009-suivi-par-expressions-natives.md),
  [0010 — Gabarits générateurs](0010-gabarits-generateurs.md)

## Contexte

Une porte ou un tiroir n'a de sens que dans un caisson : ses cotes se déduisent du vide qu'il
ferme, moins des jeux. L'ADR 0010 fait de chaque gabarit un générateur autonome. Il faut décider
comment un gabarit apprend les cotes d'un meuble existant, et comment il les suit ensuite.

Options étudiées :

1. **Gabarits indépendants**, cotes saisies à la main par le menuisier. Simple, mais la porte ne
   suit pas le caisson et les erreurs de jeu sont fréquentes. Rejetée comme seule option.
2. **Ouverture calculée, gabarit sous-ensemble** : une fonction pure calcule l'ouverture
   (`Opening`) depuis le `Layout` du caisson ; le gabarit crée un sous-ensemble du caisson (ADR
   0008, Q2 de J4) dont les cotes suivent les cotes du caisson par expressions (ADR 0009).
   Retenue.
3. **Gabarit persistant** qui se recalcule quand le caisson change. Écarté par l'ADR 0010.

## Décision

1. `core/templates/opening.py` définit `Opening` (objet valeur : coin avant gauche bas, largeur,
   hauteur, profondeur) et des fonctions pures qui la déduisent d'un `Layout` (`carcass_opening`)
   ou de pièces choisies. Aucun import de FreeCAD.
2. Un gabarit « dans une ouverture » reçoit l'`Opening` et ses jeux comme paramètres explicites ;
   il reste une fonction pure `…_layout(params) → Layout`.
3. `features/templates.py` crée le résultat comme **sous-ensemble** du meuble hôte (option
   `parent`, déjà prévue pour K5). Les cotes du sous-ensemble suivent celles de l'hôte par les
   expressions d'ensemble de l'ADR 0009, avec les options « fixe » du gabarit.
4. Si le vide change de façon que la porte ou le tiroir ne tienne plus, l'ensemble applique son
   refus habituel (`FurnitureError`) ; aucun mécanisme nouveau.
5. Un gabarit sans ouverture choisie reste autonome (option 1).

## Conséquences

- Un seul nouveau concept, `Opening`, pur et testable sans FreeCAD ; aucun objet persistant en
  plus, aucune migration.
- Le tiroir et la porte suivent le caisson ; les retouches de l'utilisateur ne sont pas écrasées.
- Contrepartie acceptée : l'ouverture se calcule à la création ; si l'utilisateur déplace une
  étagère à la main, il choisit l'ouverture sur la nouvelle position (ou la retouche).
- Les gabarits suivants (volet, cache-pot…) réutilisent `Opening` sans nouvelle décision.
