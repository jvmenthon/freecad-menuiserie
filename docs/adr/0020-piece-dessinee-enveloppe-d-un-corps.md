# ADR 0020 — La pièce dessinée, enveloppe d'un corps FreeCAD

- Statut : **proposé** (issue #73)
- Date : 2026-10-25
- Spécification : [docs/specs/piece-dessinee.md](../specs/piece-dessinee.md), § 4.1
- ADR liés : [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md)

## Contexte

jv veut « importer un corps » dessiné avec Sketcher ou PartDesign comme pièce de menuiserie :
matériau, sens du fil, repère, liste de débit sur l'encombrement. Le corps doit rester
modifiable avec les outils de FreeCAD, et la pièce doit suivre.

Contraintes :

- ADR 0003 : `WoodPart` est un contrat figé dont la forme est le parallélépipède de ses trois
  cotes ; `execute()` ne lit que ces cotes.
- ADR 0007 : on ne modifie pas les objets des autres ateliers ; tout objet géométrique de
  l'atelier est un `Part::FeaturePython` avec un solide enregistré ; seule exception de
  visibilité admise jusqu'ici : la brute masquée sous sa pièce usinée.
- CONTRIBUTING : `execute()` ne fait que reconstruire `obj.Shape`.
- La liste de débit (J2) lit des `PartRecord` ; elle ne doit pas savoir d'où vient la pièce.

## Options

1. **`WoodPart` à forme facultative** (propriété `Source` ; boîte si vide, forme sinon) : change
   le sens de `Length`/`Width`/`Thickness` (saisies ou calculées selon le cas), oblige à revoir
   assemblages, ensembles, accrochage et aperçu qui supposent une boîte, et demande une
   migration de tous les documents. Rejetée.
2. **Propriétés de menuiserie ajoutées au corps PartDesign** (`addProperty` sur le `Body`) :
   modifie un objet d'un autre atelier, données sans proxy ni `Version` donc sans migration
   possible, propriétés perdues ou en conflit si un autre addon fait de même. Contraire à
   l'ADR 0007. Rejetée.
3. **Copie figée** (`Part::Feature` dont la forme est copiée une fois) : perd le suivi du corps,
   contraire à la demande (« continuer à dessiner »). Rejetée.
4. **`App::Link` vers le corps** avec nos propriétés : pas de forme propre enregistrée (un
   document lu sans l'atelier ou par un autre outil voit un lien), placement et sélection
   partagés avec la cible, repère de pièce impossible à porter sans transformer le lien.
   Rejetée.
5. **Nouvel objet `ShapedPart` qui enveloppe la source.** Retenue.

## Décision

1. **Objet** : `Part::FeaturePython`, proxy `ShapedPart` (type `Menuiserie::ShapedPart`), créé
   dans le même conteneur que la source, qu'il lie par `Source` (`App::PropertyLink`). Graphe de
   recalcul : source → pièce dessinée, sans cycle ; l'atelier n'écrit jamais dans la source.
2. **Forme** : le solide de la source (corps : forme de son `Tip` ; esquisse plane fermée :
   extrudée de `ProfileThickness`), exprimé dans le **repère de la pièce** ; `Placement` =
   placement de la source × repère de la pièce. Une pièce dessinée occupe [0, L] × [0, l] ×
   [0, e] dans son repère, comme une pièce de bois : texture (ADR 0004), accrochage (J6) et
   liste de débit s'appliquent sans cas particulier.
3. **Repère de la pièce** (`SourceAxes`, dans le repère de la source) : calculé une fois à la
   conversion par `core/shaped` (boîte englobante de volume minimal parmi des candidats tirés
   des faces planes et des arêtes droites, puis X = plus grande étendue, Z = plus petite),
   modifiable par quarts de tour, **gardé** quand la forme change.
4. **Cotes = encombrement**, calculé à la lecture (boîte englobante exacte dans le repère de la
   pièce), jamais stocké. `record_of` rend un `PartRecord` ordinaire.
5. **Propriétés de menuiserie partagées avec `WoodPart`** (mêmes noms, types, énumérations et
   synchronisation du matériau), par composition dans un module commun extrait de
   `wood_part_schema.py` / `wood_part.py`, sans changer le comportement ni la `Version` de
   `WoodPart`.
6. **Visibilité** : la source est masquée et apparaît sous la pièce dessinée dans l'arbre ;
   supprimer la pièce dessinée la réaffiche. C'est la **deuxième exception** à l'ADR 0007 § 3
   (après la brute sous sa pièce usinée) ; aucune autre propriété de la source n'est touchée.
7. **Persistance** : règles de l'ADR 0003 (chemins figés
   `freecad.menuiserie.features.shaped_part.ShapedPart` et
   `freecad.menuiserie.gui.view_providers.shaped_part.ViewProviderShapedPart`, proxy sans état,
   `Version` = 1, réouverture contrôlée).
8. **Périmètre** : une pièce dessinée n'est ni hôte ni invitée d'un assemblage, ni membre d'un
   ensemble (refus explicite) ; le prédicat `is_wood_part` garde son sens strict, un prédicat
   `is_timber` couvre les deux sortes de pièces là où c'est voulu.

## Conséquences

- Aucun document existant ne change ; `WoodPart` reste le modèle paramétrique de référence.
- Le menuisier garde Sketcher et PartDesign pour les formes, l'atelier ajoute la menuiserie
  autour : pas de modeleur concurrent à maintenir.
- Une pièce dessinée compte deux objets (source masquée, enveloppe visible), comme une pièce
  usinée.
- Assemblages sur forme quelconque : demanderait de repérer parement, chant et bout sur une
  forme libre ; décision reportée, l'ADR 0006 n'est pas touché.
- L'encombrement, calculé à la lecture, n'est pas utilisable dans une expression ; si jv le
  demande, trois propriétés de sortie en lecture seule écrites au recalcul seront une exception
  documentée à la règle d'`execute()`.
