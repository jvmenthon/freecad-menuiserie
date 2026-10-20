# ADR 0007 — Compatibilité avec les autres ateliers et addons de FreeCAD

- Statut : **proposé** (exigence de jv du 2026-10-20, à valider avec la spécification J3)
- Date : 2026-10-20
- Spécification : [docs/specs/J3-assemblages.md](../specs/J3-assemblages.md), § 4.9 et critères O13, O14
- ADR liés : [0001 — Structure](0001-structure-de-l-atelier.md),
  [0003 — Modèle de la pièce](0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md)

## Contexte

Exigence de jv, mot pour mot : « Ajoute une contrainte : il faut garder la compatibilité avec les
autres addons freecad ». Un menuisier utilise aussi TechDraw (plans), l'atelier Assembly intégré
de FreeCAD 1.x, BIM, CAM (usinage CNC), l'export STEP, et parfois d'autres addons de bois
(Woodworking…). L'atelier ne doit ni les gêner ni les rendre inutilisables sur ses objets, et un
document doit rester lisible par quelqu'un qui n'a pas l'atelier. Cette règle s'applique à tous
les jalons et coûte cher à rattraper : elle mérite un ADR.

## Décision

1. **Formes standard** : tout objet géométrique de l'atelier est un `Part::FeaturePython`
   (donc un `Part::Feature`) dont `Shape` est un solide Part valide, enregistré dans le `.FCStd`.
   Aucune géométrie n'existe seulement dans un nœud Coin ou dans le proxy. La forme d'une pièce
   assemblée est celle de la pièce usinée (ADR 0006) : un `Part::Cut`, une vue TechDraw, un export
   STEP, une opération CAM ou un lien d'Assembly s'en servent comme de n'importe quel solide.
2. **Document lisible sans l'atelier** : sans l'atelier, les objets gardent leur forme enregistrée
   (proxy introuvable signalé par FreeCAD, pas de recalcul) ; aucune donnée indispensable n'est
   seulement dans le proxy (proxies sans état, ADR 0003). Les propriétés sont de types FreeCAD
   standard (`App::Property…`).
3. **Aucune modification globale de FreeCAD** : pas de monkey-patching de modules FreeCAD, Part,
   Qt ou d'un autre atelier ; pas de modification des préférences d'autres modules (seule la
   branche `Mod/Menuiserie` est écrite) ; pas d'observateur global permanent (`App`/`Gui`) hors de
   la durée d'une opération de l'atelier (ex. panneau de tâche ouvert), et toujours retiré ensuite ;
   pas de modification de la sélection, de la vue ou de la visibilité d'objets qui ne sont pas les
   nôtres, sauf la pièce brute masquée sous sa pièce usinée.
4. **Espace de noms** : code sous `freecad.menuiserie` ; commandes préfixées `Menuiserie_` ;
   types de proxies `Menuiserie::…` ; icônes `Menuiserie_*.svg` ; contexte de traduction
   `Menuiserie` ; paramètres sous `BaseApp/Preferences/Mod/Menuiserie`. Aucun nom d'objet,
   de commande ou de type qui imite celui d'un atelier existant (par exemple pas d'objet appelé
   « Assembly », réservé à l'atelier intégré : l'ensemble de J4 s'appellera `Furniture`).
5. **Pas de dépendance Python à l'exécution** en dehors de FreeCAD et de sa bibliothèque standard
   (les outils de développement restent dans `[project.optional-dependencies]`). Une dépendance
   future demandera un ADR et devra être importée paresseusement, sans en installer de version.
6. **Expressions natives** : les liens paramétriques entre objets passent par l'`ExpressionEngine`
   de FreeCAD (ex. l'ensemble de J4), lisible et modifiable par l'utilisateur et les autres outils,
   plutôt que par un mécanisme propre caché.

## Conséquences

- Critères de test dans chaque spécification dès J3 : forme de pièce assemblée utilisée dans un
  `Part::Cut` ordinaire et dans une vue TechDraw, document ouvert sans l'atelier avec des formes
  valides, aucune commande ni module hors de l'espace de noms (test d'inventaire).
- La règle courte figure dans `CONTRIBUTING.md` (« Compatibilité avec les autres ateliers ») et
  le reviewer la vérifie.
- Pas d'intégration spécifique à un autre addon (Woodworking, Assembly) : seulement la
  coexistence ; une intégration éventuelle ferait l'objet d'un lot et d'un ADR propres.
- Contrainte acceptée : un document ouvert sans l'atelier n'est pas recalculable (limite de tout
  FeaturePython) ; le masquage de la pièce brute est la seule modification de visibilité.
