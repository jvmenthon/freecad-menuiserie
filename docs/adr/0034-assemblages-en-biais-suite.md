# ADR 0034 — Assemblages en biais, suite : feuillure, mi-bois, onglet, tourillons, queue d'aronde

- Statut : **proposé** (issue #78, jv « Go pour 78 » le 2026-11-06 ; aucune question bloquante)
- Date : 2026-11-06
- ADR liés : [0024](0024-assemblages-entre-pieces-en-biais.md) (socle polyèdre / `relation()`),
  [0014](0014-assemblages-par-superposition-au-contact.md), [0016](0016-assemblages-au-contact-entre-pieces-qui-se-chevauchent.md),
  [0027](0027-sens-de-la-feuillure-filante.md), [0007](0007-compatibilite-avec-les-autres-ateliers.md)
- Spec : [assemblages-en-biais-suite.md](../specs/assemblages-en-biais-suite.md)

## Contexte

L'ADR 0024 a ouvert tenon-mortaise et rainure-languette au biais (`Polyhedron`, `relation()`,
`ObliqueContact`). Cinq assemblages refusent encore le biais (`SQUARE_ONLY`) : feuillure, mi-bois,
onglet, tourillons, queue d'aronde. Ils se répartissent en deux familles de calcul.

## Décision

1. **Pas de nouveau modèle géométrique**, sauf un cylindre à axe quelconque (`SlantedCylinder`,
   ajouté à `PlanSolid`) pour les tourillons.
2. **Famille « chevauchement »** (feuillure, mi-bois, onglet) : le solide enlevé est une
   `Polyhedron` (boîte dans un repère quelconque coupée par des demi-espaces) : intersection de
   deux boîtes (feuillure, mi-bois) ou demi-espace du plan d'onglet (onglet). Une fonction
   commune `core/joints/_overlap.py` calcule l'intersection de deux pièces en biais ; elle remplace
   `square_relation` dans ces trois stratégies, qui gardent leur chemin d'équerre au bit près.
3. **Famille « contact »** (tourillons, queue d'aronde) : elles passent par `ObliqueFrame`
   (ADR 0024) ; la queue d'aronde est une boîte coupée par deux plans de flanc et le plan
   d'épaulement ; les tourillons sont des `SlantedCylinder` d'axe celui de l'invitée, centres
   projetés sur le plan d'épaulement.
4. **Périmètres réduits assumés** (refus par un message dédié, jamais un usinage faux) :
   mi-bois en biais = rotation autour de l'épaisseur seulement (pièces à fleur) ; onglet en biais
   = rotation autour de l'arête du coin seulement (cadre ou coin de caisson non rectangulaire,
   pas d'onglet à double inclinaison) ; feuillure, mi-bois, onglet en biais seulement entre
   pièces qui se chevauchent (pièces au contact en biais : lot ultérieur, issue à ouvrir).
5. La borne `MAX_OBLIQUE_DEG` = 70° et le refus `EDGE_HIT` de l'ADR 0024 s'appliquent partout.
6. **Tailles de tourillon** : inchangées (valeurs de jv attendues) ; le biais ne change que
   l'axe, pas le diamètre ni la longueur automatiques (la longueur est mesurée sur l'axe).

## Conséquences

Le message `SQUARE_ONLY` disparaît des cinq types (remplacé par des refus ciblés). Aucun
changement de `Version` de document : pas de nouvelle propriété. Tests purs par volumes
analytiques, comparaison volume `core` / volume OCC en intégration. Compatibilité : formes
`Part` standard uniquement.
