# Contribuer

## Environnement de développement

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Vérifications à lancer avant chaque PR (la CI fait de même) :

```sh
ruff check . && ruff format --check .
mypy freecad tests
pylint freecad tests tools   # code dupliqué uniquement
pytest tests/unit --cov
bandit -c pyproject.toml -r freecad
```

Les tests d'intégration (`tests/integration`) nécessitent FreeCAD ; ils sont ignorés
automatiquement s'il n'est pas importable et tournent dans la CI sur FreeCAD 1.1.
La CI vérifie aussi que l'atelier se charge et s'active dans l'interface de FreeCAD
(`tests/gui/verifier_atelier.py`, mode d'affichage `offscreen`).

## Organisation du code

```
freecad/menuiserie/
├── __init__.py      version et chemins, rien de lourd
├── init_gui.py      enregistrement de l'atelier dans l'interface
├── core/            logique métier pure : aucun import FreeCAD ni Qt
├── features/        objets du document (FeaturePython) : aucun import FreeCADGui ni Qt
├── gui/             commandes, ViewProviders, panneaux de tâche
├── data/            essences et panneaux (JSON)
└── resources/       icônes SVG et traductions
```

Les icônes sont générées par `tools/generer_icones.py` (un dessin par icône), avec le moteur
`tools/icones_svg.py` (volumes projetés en isométrie, style commun) : on modifie le script puis
on relance `python tools/generer_icones.py`. Un test vérifie que les SVG du dépôt correspondent
au script.

## Conception et design patterns

Contrôlé automatiquement par la CI :

- **Code dupliqué** : `pylint` (règle `duplicate-code`, 6 lignes identiques ou plus, hors
  imports, docstrings et signatures). Une duplication se corrige en factorisant (fonction,
  classe de base, fixture pytest), jamais en désactivant la règle.
- **Complexité** : ruff, complexité cyclomatique ≤ 10, au plus 6 arguments (hors `self`),
  12 branches, 6 `return` et 50 instructions par fonction. Au-delà, découper.

Vérifié par l'architecte (dans la spécification) et par le reviewer (dans la revue) :

| Besoin | Pattern attendu | Où |
|---|---|---|
| Objet paramétrique du document | **Proxy** FeaturePython (`execute`, `onChanged`, `dumps`/`loads`) + ViewProvider séparé | `features/`, `gui/view_providers/` |
| Action de l'utilisateur | **Command** FreeCAD (`GetResources`, `IsActive`, `Activated`), une classe par commande | `gui/commands/` |
| Création d'objets | **Fabrique** unique par type (`create_…`), utilisée par les commandes, les scripts et les tests | `api.py`, `features/` |
| Familles interchangeables (assemblages, profils de chant, finitions) | **Strategy** + registre : une classe par variante derrière une interface commune, pas de chaînes de `if type == …` | `core/` |
| Squelette commun de plusieurs objets | **Template Method** (classe de base qui fixe l'ordre, sous-classes qui fournissent les étapes) — seulement si au moins deux variantes existent | `features/` |
| Réaction aux événements du document | **Observer** (`DocumentObserver`, `onChanged`) plutôt que des appels croisés | `gui/` |
| Données métier | objets **valeur** immuables (`dataclass(frozen=True)`), validés à la construction | `core/` |

Règles générales : pas de singleton ni d'état global hors caches explicites et réinitialisables ;
composition plutôt qu'héritage ; dépendances dirigées `gui → features → core`, jamais l'inverse ;
pas de pattern « pour le principe » : un pattern se justifie par au moins deux usages ou un
point d'extension prévu par la feuille de route.

## Règles FreeCAD

1. **Séparation App / Gui** : un document doit s'ouvrir et se recalculer dans `freecadcmd`.
   Un test vérifie automatiquement les imports de `core/` et `features/`.
2. **FeaturePython** : propriétés groupées avec infobulles, `execute()` déterministe qui ne
   fait que reconstruire `obj.Shape`, sérialisation du proxy par `dumps`/`loads`, propriété
   `Version` et migration dans `onDocumentRestored`. Exception (ADR 0020) : `execute()` peut
   écrire les cotes de sortie de son propre objet (`Length`, `Width`, `Thickness` de la pièce
   en bois à forme libre), déclarées `Output` et en lecture seule, seulement si leur valeur a
   changé et jamais dans un autre objet.
3. **Annuler / rétablir** : chaque commande encadrée par `openTransaction` / `commitTransaction`.
4. **Chargement léger** : imports différés dans `Initialize()`.
5. **Qt** : toujours `from PySide import QtCore, QtGui` (couche de compatibilité FreeCAD),
   jamais `PySide2` ni `PySide6`.
6. **Traductions** : toute chaîne visible passe par `translate()` ou `QT_TRANSLATE_NOOP`.
7. **Unités** : mm en interne, propriétés `App::PropertyLength` pour les cotes.

## Compatibilité avec les autres ateliers

Exigence de jv : l'atelier reste compatible avec les autres ateliers et addons de FreeCAD
(détails : [ADR 0007](docs/adr/0007-compatibilite-avec-les-autres-ateliers.md)).

1. Tout objet géométrique est un `Part::FeaturePython` dont `Shape` est un solide valide,
   enregistré dans le document : utilisable par TechDraw, Assembly, BIM, CAM, `Part::Cut`, STEP,
   et visible sans l'atelier.
2. Aucune modification globale : pas de monkey-patching, pas de préférences hors de
   `Mod/Menuiserie`, pas d'observateur global laissé en place hors d'une opération de l'atelier.
3. Tout est dans notre espace de noms : `freecad.menuiserie`, commandes `Menuiserie_…`, types
   `Menuiserie::…` ; aucun nom qui imite un atelier existant (Woodworking, Assembly…).
4. Aucune dépendance Python à l'exécution hors de FreeCAD et de la bibliothèque standard.
5. Liens paramétriques entre objets par les expressions natives de FreeCAD (`ExpressionEngine`).

## Sécurité

La CI de sécurité lance Bandit, Semgrep (règles communautaires Python, secrets et
GitHub Actions, figées sur un commit), gitleaks, et CodeQL lorsque le dépôt est public.
Pour lancer Semgrep en local :

```sh
pip install semgrep
git clone --depth 1 https://github.com/semgrep/semgrep-rules .semgrep-rules
semgrep scan --metrics=off --error --exclude .semgrep-rules \
  --config .semgrep-rules/python/lang --config .semgrep-rules/generic/secrets
```

Pas de `eval`/`exec`, pas de `pickle`, aucun accès réseau, chemins d'export validés. Les
fichiers de données utilisateur sont lus en JSON uniquement.

## Git

- `main` est protégée : on y entre uniquement par pull request, CI verte et revue validée.
- Une branche par lot : `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- Messages au format [Conventional Commits](https://www.conventionalcommits.org/fr/).
- Versions [SemVer](https://semver.org/lang/fr/) ; la version est la même dans
  `package.xml`, `pyproject.toml` et `freecad/menuiserie/__init__.py` (vérifié par un test).
- Toute évolution notable est ajoutée à `CHANGELOG.md`.

## Agents

Le développement est organisé en cinq rôles (architecte, dev, testeur, sécurité, reviewer),
définis dans [.claude/agents](.claude/agents). Enchaînement d'un lot :

```
Architecte (issue + spec, ADR)  →  Dev (branche + PR)  →  Testeur ∥ Sécurité  →  Reviewer  →  merge humain
```
