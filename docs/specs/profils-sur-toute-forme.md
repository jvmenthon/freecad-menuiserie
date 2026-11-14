# Profils d'arête sur toute pièce de bois dessinée

- Issue : #5 (finition des chants), suite du jalon 1 « Profils d'arête » (PR #149)
- Statut : **proposée** : en attente du choix de maquette et du « go » de jv (§ 9). Aucun code écrit.
- Demande de jv (2026-11-14, carte « Comment étendre les profils… ») : option **« Toute forme,
  arêtes FreeCAD natives »**. Le jalon 1 refuse (à raison) une pièce dessinée dans un corps
  PartDesign (9 faces, 31 % de sa boîte) parce que les arêtes y sont désignées par les 12 codes
  d'une boîte (« Z+Y- »).
- ADR : **[0058 — Profils d'arête sur arêtes natives](../adr/0058-profils-sur-aretes-natives.md)**
  (proposé). ADR liés : 0029 (profils par balayage, complété), 0006, 0056 (cartes d'éléments de la
  pièce usinée), 0057 (solide retrouvé par ses faces), 0007 (compatibilité).
- Dépendance : le code se fonde sur le jalon 1, donc sur la fusion de la PR #149. Cette
  branche ne porte que la spécification, l'ADR et les maquettes.

## 1. Contexte

- Le jalon 1 calcule la coupe d'un profil dans le repère d'une **boîte** : l'arête est l'une des 12
  de la boîte, l'angle est toujours droit, la longueur est une cote de la pièce.
- Une pièce dessinée (corps PartDesign, `ShapedPart`) peut avoir des arêtes en nombre quelconque,
  des faces obliques, des arcs.
- FreeCAD ≥ 1.0 ne renumérote plus les arêtes à chaque recalcul : un `App::PropertyLinkSub`
  (sous-élément nommé, porteur du nom cartographié) suit son arête quand le corps change. Sonde en
  CI (FreeCAD 1.1, 2026-11-14) : corps en L → pièce dessinée → pièce usinée gardent leurs cartes
  d'éléments ; après une encoche dans l'esquisse, **16 liens sur 16** suivent la bonne arête alors
  que 12 arêtes changent de numéro.
- Limites mesurées (mémoire du projet) : sans carte d'éléments (forme importée, composé Python),
  le lien garde le **numéro** et peut désigner une autre arête après modification ; une arête
  coupée en deux par une fonction du corps est perdue ; supprimer une fonction du corps peut
  tout perdre.

## 2. Objectif

Donner un profil (les 6 familles du jalon 1) à toute arête d'une pièce en bois dessinée, choisie à
la souris dans la vue 3D, et que ce choix **survive aux modifications du corps** (cotes, esquisse,
fonctions ajoutées) sans que jv ait à recommencer, ou avec un message clair quand l'arête a disparu.

## 3. Critères d'acceptation

### P-a — Règles pures (`core/edges/`, aucun import de FreeCAD)

- A1 `EdgeFrame` : repère d'une arête quelconque droite entre deux faces planes (origine, sens de
  l'arête, direction de chaque face à partir de l'arête, angle dièdre, longueur). Pour une boîte, le
  repère construit ne change pas la coupe du jalon 1 (tests de non-régression : mêmes volumes).
- A2 `edge_cut_in_frame(frame, famille, a, b)` rend l'`Extrusion` de la coupe. Au dièdre de 90°,
  résultat identique à `edge_cut`.
- A3 Au dièdre α ≠ 90° (arête **saillante**, 30° ≤ α ≤ 150° pour la matière) : chanfrein (cotes sur
  chaque face), quart de rond (arc tangent aux deux faces) et gorge sont calculés ; les autres
  familles (demi-rond, bec-de-corbin, doucine) sont **refusées** avec un message qui dit pourquoi
  (« exigent une arête à angle droit »).
- A4 Une arête **rentrante** (matière > 180°) est refusée (rien à enlever), message clair.
- A5 Bornes : cotes ≥ 0,1 mm ; encombrement au plus la moitié de la largeur de chaque face voisine
  mesurée perpendiculairement à l'arête.

### P-b — Objet et usinage (`features/edge_profile.py`, `features/machined_part.py`)

- B1 `EdgeProfile` gagne `EdgeRefs` (`App::PropertyLinkSub` vers la brute, un sous-élément par
  arête). `Edges` (codes de boîte) et `EdgeRefs` sont exclusifs ; `Version` passe à 2, un profil
  du jalon 1 s'ouvre sans changement.
- B2 Un profil d'arêtes natives n'est accepté que si la forme de la brute **a une carte
  d'éléments** ; sinon refus à la création et erreur au recalcul (« forme sans noms d'éléments
  stables : arêtes impossibles à suivre »).
- B3 À chaque recalcul : chaque lien est résolu ; une arête perdue est signalée (§ 4.5, Q3) ; la
  liste des arêtes tangentes enchaînées (suite d'arêtes de même profil bout à bout) donne une coupe
  continue.
- B4 La coupe est soustraite dans la pièce usinée, avant les ajouts et enlèvements des assemblages
  (ordre du jalon 1) ; le solide obtenu est valide (`isValid`) et son volume baisse, sinon erreur
  traduite (jamais de plantage).
- B5 Bouts : le balayage dépasse l'arête de 0,01 mm **seulement** si son prolongement sort du
  solide ; sinon il s'arrête au sommet (pas d'entaille dans la face voisine, § 7).
- B6 Un profil sur arête courbe (cercle, ellipse) ou entre faces non planes est refusé au lot 1
  (message « arête courbe : prévue au lot suivant » ou voir Q2).
- B7 Chaque profil créé par le panneau l'est dans une transaction (annuler/rétablir, règle du projet).

### P-c — Interface (`gui/`) : à coder **après** le choix de jv sur les maquettes

- C1 La commande « Finition des chants » accepte une pièce dessinée : clic sur une arête dans la
  vue 3D ou sélection FreeCAD préalable ; mise en valeur 3D par couleur de pièce (incrustation du
  jalon 1, rien dans le document).
- C2 Le panneau garde « Pièces concernées » (une carte par pièce) ; une pièce en boîte garde son
  dessin à bascule du jalon 1, une pièce dessinée affiche la liste de ses arêtes (longueur,
  angle) à la place.
- C3 Arête non profilable (courbe, rentrante, angle hors bornes) : affichée grisée avec la raison.
- C4 Arêtes perdues : carte rouge, bouton « Choisir à nouveau ».
- C5 Aucune case à cocher (règle de jv) ; peu d'options.

### P-d — Finitions

- D1 Icône : celle du jalon 1 (aucune icône nouvelle, sauf si jv en demande une).
- D2 Captures CI et recette : pièce en L profilée, encoche ajoutée dans l'esquisse (le profil suit),
  arête perdue, Ctrl+Z, ouverture du fichier **sans** l'atelier (formes ordinaires visibles).

## 4. Conception

### 4.1 Principe (ADR 0058)

Un profil reste une **section 2D balayée** (ADR 0029). Ce qui change : le **repère** de la coupe
n'est plus celui d'une boîte mais celui de l'arête, calculé à partir de la forme de la brute.

```
core/edges/_frame.py      EdgeFrame, angle dièdre, repère ; Python pur
core/edges/_sections.py   sections avec angle (chanfrein, quart de rond, gorge)
core/edges/_cut.py        + edge_cut_in_frame
features/edge_frames.py   lit la forme FreeCAD : arête, deux faces voisines, repère, convexité
features/edge_profile.py  + EdgeRefs, résolution et suivi
gui/…                     voir P-c
```

La frontière FreeCAD est mince : `features/edge_frames.py` extrait des nombres (`Vec3`) ; tout le
calcul de coupe reste testable sans FreeCAD.

### 4.2 Repère d'une arête

Pour l'arête `E` (segment) de la brute : `ancestorsOfType(E, Face)` donne les deux faces voisines
(refus s'il y en a une seule ou plus de deux, ou si l'une n'est pas plane). `along` = sens de `E` ;
`u`, `v` = directions unitaires, dans chaque face, perpendiculaires à `along` et dirigées vers
l'intérieur de la face ; `α` = angle de `u` à `v`. Convexité : le point `milieu + ε(u + v)` est
**dans** le solide pour une arête saillante. Tout est exprimé dans le repère de la brute, sans
`Placement` (comme le jalon 1).

### 4.3 Arêtes désignées par lien

`EdgeProfile.EdgeRefs` : `App::PropertyLinkSub` ; objet = la brute, sous-éléments = `"Edge7"` ou le
nom cartographié que FreeCAD y écrit. Le lien est lu par `obj.EdgeRefs` ; l'arête par
`brute.Shape.getElement(nom)`. La brute est déjà la source du graphe : le lien ne crée **aucun
cycle** (brute → profil → pièce usinée). Les codes de boîte restent pour les pièces en boîte
(indépendants de la forme, utiles quand un ensemble étire la pièce).

### 4.4 Chaînes tangentes

Une arête cliquée peut entraîner toute la **chaîne tangente** (le contour d'une face arrondie) :
choix de l'interface (Q4), pas du modèle (les arêtes se stockent une à une).

### 4.5 Arête perdue

À la résolution, un lien peut échouer (arête coupée en deux, fonction supprimée) ou, sans carte
d'éléments, désigner une autre arête. Parades : B2 (carte obligatoire) et message explicite.
Comportement retenu : Q3.

### 4.6 Design patterns

Strategy + registre des familles (inchangés) ; Adapter : `features/edge_frames.py` isole FreeCAD ;
Façade : `core.edges`.

### 4.7 Sécurité

Noms d'éléments lus comme des chaînes **non interprétées** (validés par motif avant
`getElement`) ; au plus 64 arêtes par profil ; réels finis et bornés ; aucun fichier nouveau.

### 4.8 Compatibilité avec les autres ateliers (ADR 0007)

Aucun objet étranger n'est modifié ; le lien ne pointe que vers la brute de l'atelier. Les formes
produites sont des solides `Part` ordinaires.

## 5. Découpage en PR et impact

Branche unique de jalon, lots squashés vers elle ; une PR vers `main` en fin de jalon (revue
complète). Ce qui précède n'est que la PR de spécification (brouillon).

| Lot | Contenu | Dépend de |
|-----|---------|-----------|
| P-0 | Sonde → vrais tests : liens suivis, arête coupée, carte absente | PR #149 |
| P-a | `core/edges/_frame.py`, sections avec angle, tests unitaires | P-0 |
| P-b | `EdgeRefs`, `edge_frames.py`, usinage, erreurs | P-a |
| P-c | panneau (maquette choisie par jv), mise en valeur 3D | P-b, choix jv |
| P-d | captures, recette, CHANGELOG | P-c |

Fichiers existants touchés : `core/edges/*`, `features/edge_profile*.py`,
`features/machined_part.py`, `features/box_parts.py` (refus levé), `_api/edges.py`,
`gui/task_panels/edge_*.py`, `gui/pick_edge.py`, `CHANGELOG.md`, `CONTRIBUTING.md`.

## 6. Compatibilité des documents

`EdgeProfile` `Version` 1 → 2 (propriété `EdgeRefs` vide à la migration, `onDocumentRestored`). Un
fichier enregistré avec des arêtes natives s'ouvre dans une version plus ancienne en refusant le
profil (version inconnue, message clair, ADR 0003). Aucun ancien document n'est touché.

## 7. Risques

- Arêtes perdues ou ambiguës après une modification du corps (§ 4.5) : message clair, test CI sur
  encoche, suppression de fonction, scission d'arête.
- Entaille au bout d'une arête qui rejoint une face voisine : B5 ; sonde CI sur L, T et U.
- Booléennes OCC sur formes quelconques plus fragiles que sur une boîte : validité testée (B4),
  erreurs OCC converties en erreurs traduites.
- Fichiers de FreeCAD 1.0 : abandonnés (ADR 0023) ; tout repose sur 1.1.
- Dépendance à l'issue #257 (corps à plusieurs solides) : profils refusés sur un composé tant que
  son ADR 0057 n'est pas fait.

## 8. Hors périmètre

- Arêtes courbes (sauf décision Q2) et faces non planes ; arrondi de coin ; profils personnels ;
  bande de chant (jalon 2, CH-d à CH-f) ; configuration de l'atelier (issue #148).
- Profil sur une forme importée sans carte d'éléments (refusée) ; sur un composé de plusieurs
  solides (issue #257).

## 9. Questions pour jv

★ = recommandation.

- Q1 **Maquette du panneau.** 3 propositions en image (voir le fil) : A liste d'arêtes + clic 3D,
  B sélection FreeCAD préalable, C faces et contours. ★ À trancher par jv avant tout code.
- Q2 **Arêtes courbes** (table ronde, congé). ★ Plus tard, en lot séparé : chanfrein et quart de
  rond par les outils OCC, autres familles refusées. Sinon : inclus d'emblée (balayage le long
  de l'arête, plus risqué).
- Q3 **Arête perdue.** ★ Le profil passe en erreur **sur lui-même seulement** ; la pièce usinée
  ignore ce profil avec un avertissement visible (le meuble reste utilisable). Sinon : erreur de
  la pièce usinée (bloque tout l'ensemble).
- Q4 **Chaîne tangente.** ★ Un clic prend toute la chaîne tangente, Alt+clic une seule arête.
  Sinon : une arête par clic.
- Q5 **Angles autres que 90°.** ★ Chanfrein, quart de rond et gorge seulement ; les autres
  familles à angle droit. Sinon : angle droit uniquement (plus simple, refuse les pièces en biais).
