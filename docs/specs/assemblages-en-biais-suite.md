# Assemblages en biais, suite (feuillure, mi-bois, onglet, tourillons, queue d'aronde)

- Issue : #78 (priorité basse, jv « Go » 2026-11-06). Suite de #114 (spec
  [assemblages-en-biais.md](assemblages-en-biais.md), ADR 0024 ; tenon-mortaise et
  rainure-languette livrés). ADR : [0034](../adr/0034-assemblages-en-biais-suite.md).
- Branche de jalon `jalon/biais-suite` ; lots **S-a → S-b → S-c** (sous-branches squashées, CI
  seule) puis une PR de jalon vers `main` avec revue complète. Compatibilité avec le jalon
  quincaillerie (#159, tourillons) : S-c passe en dernier et ne touche que le calcul d'axe.

## 1. Critères d'acceptation

**Socle (S-a).**
- **S1** `core/joints/_overlap.py` : `overlap_of(host, guest)` renvoie, pour deux pièces qui se
  chevauchent, soit le résultat d'équerre actuel, soit un `ObliqueOverlap` (guest dans le repère
  de l'hôte, `Polyhedron` commun, angle de rotation). Refus : `TOO_OBLIQUE` (> 70°),
  `SEPARATED`. Pièces au contact en biais : refus `OBLIQUE_OVERLAP_ONLY` (« En biais, dessinez
  les pièces qui se chevauchent. »).
- **S2** `SlantedCylinder(base, direction, radius, height)` dans `core/geometry`, accepté par
  `moved`, par `PlanSolid` et par `features/solids.py` (`Part.makeCylinder` orienté).
- **S3** Tous les plans d'équerre sont identiques au bit près (tests de non-régression existants).

**Feuillure (S-a).**
- **R1** Biais quelconque (angles composés compris) : la feuillure enlevée à l'hôte est la boîte
  de l'invitée (`Polyhedron` sans plan) prolongée de `CUT_OVERRUN_MM` à chaque bout de son axe de
  longueur ; l'option « filante » n'a pas d'effet en biais (documentée dans le panneau).
- **R2** Refus `NO_MATERIAL_LEFT` si le volume restant de l'hôte est inférieur à la tolérance ;
  la validité du solide (un seul morceau) est de toute façon contrôlée avant écriture.
- **R3** Volume OCC égal au volume `core` (1e-6 relatif) ; hôte et invitée pièces de bois.

**Mi-bois (S-b).**
- **H1** Rotation autour de l'épaisseur seulement, pièces de même épaisseur et à fleur (règles
  d'équerre actuelles) ; sinon refus `NOT_FLUSH` (existant).
- **H2** Boîte commune = hôte coupé par les quatre plans latéraux de l'invitée
  (`Polyhedron`) ; entaille de l'hôte = partie haute (ou basse, `flip_side`) de profondeur
  `depth`, entaille de l'invitée = le reste, chacune dans son repère par `moved`. Profondeur
  automatique : moitié de l'épaisseur (inchangé).
- **H3** Croix de Saint-André à 60° : volumes des deux entailles égaux et somme = volume commun.

**Onglet (S-b).**
- **M1** Rotation autour de l'arête du coin seulement (pièces à fleur sur cet axe) ; sinon refus
  `MITER_COMPOUND` (« Onglet : les deux pièces doivent pivoter autour de l'arête du coin. »).
- **M2** Dans le plan perpendiculaire à l'arête : parallélogramme commun aux deux largeurs ;
  plan d'onglet = plan contenant l'arête et les deux sommets extrêmes du parallélogramme le long
  de a + b (a, b = sens dans lesquels hôte et invitée se prolongent). Chaque pièce perd son
  demi-espace du côté de l'autre (un seul plan, faces coïncidentes). À 90° : plans actuels.
- **M3** Angles de coupe de la liste de débit : angle entre le plan et la coupe d'équerre de
  chaque pièce, au centième de degré (formule générale ; 45° pour deux largeurs égales à 90°).

**Tourillons (S-c).**
- **D1** En biais (contact bout contre face, `ObliqueContact`) : perçages et tourillons sont des
  `SlantedCylinder` d'axe celui de l'invitée ; centres sur la face de l'invitée, placés comme
  aujourd'hui (largeur, nombre, bord) ; diamètre et longueur automatiques inchangés (longueur
  mesurée sur l'axe) ; profondeurs vérifiées au point le plus profond.
- **D2** Refus `NO_WALL` / `TOO_DEEP` comme en équerre ; tourillons rapportés (`inserts`).

**Queue d'aronde (S-c).**
- **Q1** En biais (`ObliqueContact`) : queue = boîte (largeur du trapèze) coupée par deux plans de
  flanc d'angle `Angle` et par le plan d'épaulement ; embrèvement de l'hôte = même volume prolongé
  du jeu, repère de l'hôte par `moved`. Angle, nombre, tailles : paramètres actuels.
- **Q2** Volume OCC égal au volume `core` ; biais simples de 10° et 30°, angle composé 8° / 8°.

**Transversal.**
- **T1** `SQUARE_ONLY` supprimé ; refus ciblés par type (S1, H1, M1).
- **T2** `core/furniture/_check.py` : les assemblages de ces types en biais ne lèvent plus
  `NOT_SQUARE` (B7 de la spec #114 étendu).
- **T3** Panneau : ligne « Biais : α° » en lecture seule pour les cinq types.
- **T4** Corrections mineures b1/b2 de `docs/corrections-mineures.md` traitées au passage si les
  fichiers sont touchés.

## 2. Découpage

| Lot | Contenu | Dépend de |
|---|---|---|
| **S-a** | S1 à S3, feuillure R1 à R3, T1/T2 pour la feuillure | — |
| **S-b** | mi-bois H1 à H3, onglet M1 à M3, liste de débit (angles) | S-a |
| **S-c** | tourillons D1 D2, queue d'aronde Q1 Q2, T3, nettoyage `SQUARE_ONLY` | S-a ; en dernier pour éviter les conflits avec la quincaillerie |

## 3. Risques

| Risque | Parade |
|---|---|
| Plan d'onglet faux quand l'angle est aigu | borne 70°, test des sommets extrêmes, comparaison au cas d'équerre à 90° |
| Entaille de mi-bois non convexe | boîte commune toujours convexe (intersection de deux boîtes), tests de volumes |
| Conflit avec le jalon quincaillerie (`dowels.py`) | S-c en dernier ; message au fil quincaillerie avant de toucher `dowels.py` |
| Booléenne OCC délicate sur cylindre incliné | test d'intégration volume, forme valide |

## 4. Hors périmètre (issues à ouvrir si jv le souhaite)

Feuillure, mi-bois et onglet entre pièces **au contact** en biais ; mi-bois à double
inclinaison ; onglet composé (dièdre) ; tailles de tourillon (valeurs de jv).
