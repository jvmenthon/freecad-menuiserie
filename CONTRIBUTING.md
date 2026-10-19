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
pytest tests/unit --cov
bandit -c pyproject.toml -r freecad
```

Les tests d'intégration (`tests/integration`) nécessitent FreeCAD ; ils sont ignorés
automatiquement s'il n'est pas importable et tournent dans la CI sur FreeCAD 1.0 et 1.1.
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

## Règles FreeCAD

1. **Séparation App / Gui** : un document doit s'ouvrir et se recalculer dans `freecadcmd`.
   Un test vérifie automatiquement les imports de `core/` et `features/`.
2. **FeaturePython** : propriétés groupées avec infobulles, `execute()` déterministe qui ne
   fait que reconstruire `obj.Shape`, sérialisation du proxy par `dumps`/`loads`, propriété
   `Version` et migration dans `onDocumentRestored`.
3. **Annuler / rétablir** : chaque commande encadrée par `openTransaction` / `commitTransaction`.
4. **Chargement léger** : imports différés dans `Initialize()`.
5. **Qt** : toujours `from PySide import QtCore, QtGui` (couche de compatibilité FreeCAD),
   jamais `PySide2` ni `PySide6`.
6. **Traductions** : toute chaîne visible passe par `translate()` ou `QT_TRANSLATE_NOOP`.
7. **Unités** : mm en interne, propriétés `App::PropertyLength` pour les cotes.

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
