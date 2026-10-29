# ADR 0027 — Sens de la feuillure filante et profondeur contre un chant

- Statut : **accepté** (décision de jv le 2026-10-29 : option « selon la pièce logée », en gardant
  la case « Feuillure filante »)
- Date : 2026-10-29
- ADR liés : [0014 — Feuillure, mi-bois et onglet entre pièces au contact](0014-assemblages-par-superposition-au-contact.md)
- Spec amendée : [J3 — Assemblages](../specs/J3-assemblages.md), critère M7 et § des paramètres
- Numéro : 0024 est pris dans main, 0025 par la PR #120 (rotation) et 0026 par la PR #111
  (pièce en bois).

## Contexte

Vérification de la feuillure demandée par jv le 2026-10-28. Deux anomalies :

1. **Majeure.** La feuillure filante (cochée par défaut) était toujours prolongée sur toute la
   longueur (X local) de l'hôte. Une étagère logée en travers d'une joue 600 × 300 × 18
   (l'étagère suit la largeur Y de la joue) amincissait alors toute la joue de moitié au lieu de
   creuser un logement de 18 mm, sans aucun message. Même chose pour une feuillure en bout.
2. **Moyenne.** Une pièce posée au contact du chant ou du bout de l'hôte (et non de sa face)
   était prolongée de la moitié de l'étendue de l'hôte dans cet axe : 150 mm dans une joue de
   300 mm de large.

## Décision

1. La feuillure filante est prolongée d'un bout à l'autre de l'hôte sur **celui de ses axes X ou
   Y où la partie commune aux deux pièces est la plus longue** : c'est le sens où la pièce logée
   occupe l'hôte. À égalité, X (comportement d'avant). Un fond le long d'une joue file donc sur
   sa longueur (inchangé), une étagère en travers file sur sa largeur (logement traversant).
   L'axe de l'épaisseur (Z) n'est jamais prolongé.
2. La case « Feuillure filante » reste ; décochée, l'enlèvement est la seule partie commune.
3. Pièce posée au contact, `Depth` = 0 : moitié de l'épaisseur de l'hôte quand elle touche sa
   face (inchangé), **épaisseur de la pièce logée** quand elle touche un chant ou un bout. Le
   refus « moins profonde » reste.

## Conséquences

- Aucun changement de propriété ni de format de fichier : les documents existants se
  recalculent avec la nouvelle règle (une feuillure filante en travers change de forme, ce qui
  est la correction voulue).
- Le gabarit Caisson n'est pas touché : ses fonds filent le long des joues, du dessus et du
  dessous comme avant.
- Une pièce logée de biais (ADR 0024) suivra la même règle, sur la partie commune calculée dans
  le repère de l'hôte.
