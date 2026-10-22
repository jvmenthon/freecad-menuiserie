# ADR 0010 — Gabarits générateurs : un gabarit crée des objets ordinaires puis disparaît

- Statut : **accepté** (jv, 2026-10-21 ; question Q5 : seul le caisson est livré en J4)
- Date : 2026-10-21
- Spécification : [docs/specs/J4-ensembles.md](../specs/J4-ensembles.md), § 4.7, critères K1 à K7
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi des pièces par expressions natives](0009-suivi-par-expressions-natives.md)

## Contexte

Le plan prévoit des gabarits (caisson en J4, puis étagère, cadre, tiroir) : « un caisson complet
en quelques clics ». Après sa création, le menuisier veut modifier les cotes du caisson et
retoucher une pièce (changer le matériau du fond, ajouter une traverse). La liste de débit (J2)
lira le résultat.

Options étudiées :

1. **Objet gabarit persistant** qui régénère ses pièces à chaque changement de paramètre (nombre
   d'étagères, épaisseur). Il devrait créer et supprimer des objets pendant le recalcul, ce que
   FreeCAD n'autorise pas proprement. Il écraserait les retouches du menuisier. Il ajouterait un
   second mécanisme de cotes globales à côté de l'Ensemble. Rejetée.
2. **Gabarit générateur** : une fonction pure décrit les pièces et les assemblages ; l'atelier
   crée des pièces, des assemblages J3 et un Ensemble ordinaires ; aucun objet gabarit n'est
   gardé. Retenue.

## Décision

1. Un gabarit est une fonction pure de `core/templates/` : paramètres validés (objet valeur) →
   `Layout`, c'est-à-dire des pièces (`PieceSpec`, avec leur mode et leurs options de distance
   **explicites** : fixe ou non pour chaque bord, ADR 0009) et des assemblages (`JointSpec`). Elle
   se teste sans FreeCAD. Un gabarit ne compte pas sur les options par défaut, qui laisseraient
   non fixes les jeux et les retraits (étagère à 1 mm des côtés, fond en feuillure).
2. Un seul constructeur, `features/templates.py`, instancie n'importe quel `Layout`. Il utilise les
   fabriques existantes (`create_wood_part`, fabriques d'assemblage J3, `create_furniture`), dans
   une transaction et un recalcul.
3. Le résultat est un Ensemble ordinaire. Le menuisier le redimensionne comme tout ensemble, le
   retouche et y ajoute des pièces. `Template` (`Carcass`) n'est qu'une information.
4. Changer la structure (nombre d'étagères, type de fond) revient à relancer le gabarit ou à
   modifier les pièces à la main. Il n'y a pas de régénération.

## Conséquences

- Aucun nouveau type d'objet persistant pour les gabarits : rien à migrer. Un gabarit amélioré ne
  change pas les documents existants.
- Les retouches du menuisier ne sont jamais écrasées.
- Les gabarits suivants (étagère, cadre, tiroir) ne demandent qu'une fonction `…_layout`, un
  panneau et une commande.
- Contrepartie acceptée : on ne peut pas passer de une à trois étagères en changeant un nombre
  après la création. Si jv le demande, un lot « régénérer » ajoutera les pièces manquantes sans
  toucher aux autres, avec son propre ADR.
