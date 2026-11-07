# Tenon d'angle (coin franc)

- Issue : #174 (priorité moyenne, demande de jv le 2026-11-07). ADR : [0041](../adr/0041-tenon-d-angle.md).
- Statut : **proposé** (spec à valider par jv ; questions Q1 à Q4 avec recommandation ★).
- Dépend du socle en biais de la PR #165 (issue #78) : la branche d'implémentation part de `main`
  une fois #165 fusionnée.

## 1. Problème

Deux pièces de même section qui se rejoignent par un coin franc (exemple de jv : 800 × 218 × 114
à 30°) : le tenon centré sur le bout perce la paroi du côté du coin. Le calcul refuse
(`NO_WALL`, « Le logement ne laisse pas de paroi de matière de chaque côté… »). En atelier, on
résout ce cas par un **tenon d'angle** : tenon plus étroit, décalé vers l'intérieur, avec un
épaulement du côté du coin ; la mortaise garde une paroi (ou une corne) à l'extérieur.

## 2. Critères d'acceptation

- **A1** Option « Tenon d'angle » (`CornerMode`) de la mortaise-tenon : *Refuser* (actuel, défaut),
  *Auto*. En *Auto*, si `check_walls` échoue seulement du côté du coin, le tenon est recalculé :
  largeur réduite et décalage vers l'intérieur pour laisser à l'hôte une paroi d'au moins
  `paroi mini` (défaut : un tiers de la largeur du logement, au moins 6 mm) ; l'épaulement
  côté coin est conservé sur l'invitée (épaulement dissymétrique).
- **A2** Les cotes effectives (largeur, décalage) sont affichées comme les autres cotes visibles ;
  la valeur manuelle (≠ 0) l'emporte sur l'auto (règle « 0 = auto » de l'ADR 0006).
- **A3** Pas de coin franc, ou refus sur les deux côtés (pièce trop étroite) : comportement
  actuel, `NO_WALL` ; le message ajoute « Choisissez le tenon d'angle ».
- **A4** En droit et en biais (cadre `ObliqueFrame`) ; mêmes plans `JointPlan`, aucun nouveau
  solide : le volume OCC égale le volume `core` (1e-6 relatif).
- **A5** Corne (Q2) : propriété `Horn` (mm, défaut 0) de la pièce hôte, longueur conservée au-delà
  du coin pour l'assemblage, à recouper après collage ; elle n'enlève rien à l'hôte.
- **A6** Panneau : case « Tenon d'angle » dans le formulaire de la mortaise-tenon, aperçu en direct.
- **A7** Compatibilité : propriétés dans l'espace `Menuiserie`, formes Part standard.

## 3. Questions pour jv

- **Q1** Auto par défaut ? ★ *Non* : refus par défaut, case à cocher (pas de surprise).
- **Q2** Corne ? ★ Oui, simple prolongement de l'hôte (propriété `Horn`), 0 par défaut.
- **Q3** Paroi mini ? ★ un tiers du logement, 6 mm mini, modifiable.
- **Q4** Tenon d'angle aussi pour la rainure-languette ? ★ Non, plus tard.

## 4. Lots

**T-a** `core` : détection du côté franc, calcul largeur/décalage, tests. **T-b** feature +
propriétés + corne + panneau. Branche de jalon `jalon/tenon-d-angle`, CI seule sur les lots,
revue complète sur la PR de jalon.
