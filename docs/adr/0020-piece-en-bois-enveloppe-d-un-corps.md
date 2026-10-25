# ADR 0020 — La pièce en bois, enveloppe d'un corps FreeCAD

- Statut : **proposé** (issue #73 ; réponses de jv du 2026-10-25 intégrées : nom « Pièce en
  bois », assemblages, ensembles et cotes visibles inclus)
- Date : 2026-10-25
- Spécification : [docs/specs/piece-en-bois.md](../specs/piece-en-bois.md), § 4.1
- ADR liés : [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md) (complété),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md) (complété),
  [0019 — Rangées et épaisseurs fixes](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md)

## Contexte

jv veut « importer un corps » dessiné avec Sketcher ou PartDesign comme pièce de menuiserie :
matériau, sens du fil, repère, liste de débit sur l'encombrement ; puis (2026-10-25) pouvoir
l'assembler, la mettre dans un ensemble et lire ses cotes dans l'éditeur de propriétés. Le corps
doit rester modifiable avec les outils de FreeCAD, et la pièce doit suivre.

Contraintes :

- ADR 0003 : `WoodPart` est un contrat figé dont la forme est le parallélépipède de ses trois
  cotes ; `execute()` ne lit que ces cotes.
- ADR 0006 : les assemblages lisent des pièces brutes et la pièce usinée porte la forme coupée ;
  le graphe est sans cycle.
- ADR 0007 : on ne modifie pas les objets des autres ateliers ; tout objet géométrique de
  l'atelier est un `Part::FeaturePython` avec un solide enregistré ; seule exception de
  visibilité admise jusqu'ici : la brute masquée sous sa pièce usinée.
- ADR 0008 / 0009 : un ensemble pilote ses membres par des expressions natives sur leurs cotes
  et leur `Placement`.
- CONTRIBUTING : `execute()` ne fait que reconstruire `obj.Shape`.

## Options

1. **`WoodPart` à forme facultative** (propriété `Source` ; boîte si vide, forme sinon) : change
   le sens de `Length`/`Width`/`Thickness` (saisies ou calculées selon le cas), oblige à revoir
   tout ce qui suppose une boîte saisie (aperçu, gabarits, étirement par l'ensemble) et demande
   une migration de tous les documents. Rejetée.
2. **Propriétés de menuiserie ajoutées au corps PartDesign** (`addProperty` sur le `Body`) :
   modifie un objet d'un autre atelier, données sans proxy ni `Version` donc sans migration
   possible ; un ensemble devrait poser ses expressions sur le corps. Contraire à l'ADR 0007.
   Rejetée.
3. **Copie figée** (`Part::Feature` dont la forme est copiée une fois) : perd le suivi du corps.
   Rejetée.
4. **`App::Link` vers le corps** avec nos propriétés : pas de forme propre enregistrée,
   placement partagé avec la cible, repère de pièce impossible à porter. Rejetée.
5. **Enveloppe au placement de la source** (la pièce suit la position du corps) : assemblages,
   ensembles, accrochage et rotation devraient écrire le `Placement` du corps, objet d'un autre
   atelier, parfois dans un `App::Part`. Rejetée.
6. **Nouvel objet `ShapedPart` qui enveloppe la forme de la source, avec son propre
   `Placement`.** Retenue.

## Décision

1. **Objet** : `Part::FeaturePython`, proxy `ShapedPart` (type `Menuiserie::ShapedPart`, nom
   affiché « Pièce en bois »), créé dans le même conteneur que la source, qu'il lie par `Source`
   (`App::PropertyLink`). Graphe : source → pièce en bois, sans cycle ; l'atelier n'écrit
   jamais dans la source.
2. **Forme** : le solide de la source (corps : forme de son `Tip` ; esquisse plane fermée :
   extrudée de `ProfileThickness`), **placement de la source défait**, exprimé dans le repère de
   la pièce (origine au coin minimal de l'encombrement, X = L, Y = l, Z = e).
3. **Placement libre**, comme une `WoodPart` : initialisé à la conversion pour que la pièce soit
   à la place de la source, puis indépendant d'elle. Accrochage, rotation, ensembles et pièce
   usinée l'utilisent sans cas particulier.
4. **Repère de la pièce** (`SourceAxes`, dans le repère de la source) : calculé une fois à la
   conversion par `core/shaped` (boîte englobante de volume minimal parmi des candidats tirés
   des faces planes et des arêtes droites, puis X = plus grande étendue, Z = plus petite),
   modifiable par quarts de tour, **gardé** quand la forme change.
5. **Cotes = encombrement**, dans les propriétés `Length`, `Width`, `Thickness` (mêmes noms que
   `WoodPart`), en lecture seule, statut `Output`, **écrites par `execute()`** : exception
   documentée à la règle « `execute()` ne fait que reconstruire `obj.Shape` » ; l'objet n'écrit
   que dans lui-même, jamais dans un autre. Une expression posée sur ces cotes est refusée.
6. **Propriétés de menuiserie partagées avec `WoodPart`** (mêmes noms, types, énumérations et
   synchronisation du matériau), par composition dans un module commun extrait de
   `wood_part_schema.py` / `wood_part.py`, sans changer le comportement ni la `Version` de
   `WoodPart`.
7. **Assemblages (complète l'ADR 0006)** : une pièce en bois est une pièce brute au sens de
   l'ADR 0006. Les stratégies d'assemblage calculent leur plan sur sa boîte d'encombrement, sans
   changement ; la pièce usinée part de la forme dessinée au lieu de la boîte ; un contrôle
   avertit quand l'usinage tombe hors de la matière réelle (face courbe). Graphe : source →
   pièce en bois → assemblage → pièce usinée, sans cycle.
8. **Ensembles (complète l'ADR 0008)** : une pièce en bois suit l'ensemble par son `Placement` ;
   ses trois cotes sont toujours fixes (mécanisme des cotes bloquées de l'ADR 0019) ; l'atelier
   ne pose jamais d'expression dans le dessin.
9. **Visibilité** : la source est masquée et apparaît sous la pièce en bois dans l'arbre ;
   supprimer la pièce en bois la réaffiche. C'est la **deuxième exception** à l'ADR 0007 § 3
   (après la brute sous sa pièce usinée) ; aucune autre propriété de la source n'est touchée.
10. **Persistance** : règles de l'ADR 0003 (chemins figés
    `freecad.menuiserie.features.shaped_part.ShapedPart` et
    `freecad.menuiserie.gui.view_providers.shaped_part.ViewProviderShapedPart`, proxy sans état,
    `Version` = 1, réouverture contrôlée). `MachinedPart` et les assemblages gardent leur
    `Version`.

## Conséquences

- Aucun document existant ne change ; `WoodPart` reste le modèle paramétrique de référence et
  les formes usinées actuelles sont identiques.
- Le menuisier garde Sketcher et PartDesign pour les formes, l'atelier ajoute la menuiserie
  autour : pas de modeleur concurrent à maintenir.
- Une pièce en bois compte deux objets (source masquée, enveloppe visible), trois si elle est
  assemblée (plus la pièce usinée).
- Le corps masqué reste à sa place d'origine : réaffiché ou ouvert en édition, il peut être
  ailleurs que la pièce déplacée.
- Un assemblage sur une face courbe est placé sur la boîte d'encombrement (averti, pas refusé) ;
  reconnaître les faces réelles d'une forme libre est reporté.
- Un ensemble déplace une pièce en bois mais ne l'étire jamais ; l'utilisateur peut piloter son
  dessin par ses propres expressions natives.
- `CONTRIBUTING.md` mentionne l'exception des cotes de sortie (décision 5).
