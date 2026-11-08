# Docker pour freecad-menuiserie

Ce répertoire contient la configuration pour exécuter les tests de **freecad-menuiserie** dans un conteneur Docker, permettant une exécution reproductible et isolée en environnement local.

## Prérequis

- [Docker](https://www.docker.com/) (version 20.10 ou supérieure)
- [Docker Compose](https://docs.docker.com/compose/) (inclus avec Docker Desktop)
- Git (optionnel, pour cloner le dépôt)

## Structure

```
.
├── Dockerfile                    # Image Docker de base
├── docker-entrypoint.sh         # Script d'entrée du conteneur
├── docker-compose.yml           # Configuration Docker Compose
├── docker-compose.dev.yml       # Override pour le développement
├── Makefile                     # Commandes utiles
└── DOCKER.md                    # Ce fichier
```

## Installation

### 1. Cloner le dépôt

```bash
cd /path/vers/votre/workspace
git clone https://github.com/jevadim/freecad-menuiserie.git
cd freecad-menuiserie
```

### 2. Construire l'image Docker

```bash
# Avec make
docker-compose build

# Ou directement
docker build -t freecad-menuiserie-test .
```

> **Note** : La première construction peut prendre plusieurs minutes (téléchargement de FreeCAD et dépendances).

## Utilisation

### Commandes de base

| Commande | Description |
|----------|-------------|
| `make build` | Construit l'image Docker |
| `make test` | Exécute tous les tests |
| `make test-unit` | Exécute seulement les tests unitaires |
| `make test-integration` | Exécute seulement les tests d'intégration |
| `make lint` | Exécute ruff (lint) |
| `make type-check` | Exécute mypy (vérification de typage) |
| `make shell` | Démarre un shell interactif |
| `make clean` | Supprime l'image et les fichiers temporaires |

### Docker Compose

```bash
# Exécuter tous les tests
docker-compose run --rm test

# Exécuter les tests unitaires
docker-compose run --rm test-unit

# Exécuter les tests d'intégration
docker-compose run --rm test-integration

# Démarrer un shell interactif
docker-compose run --rm shell

# Exécuter ruff (lint)
docker-compose run --rm lint

# Exécuter mypy (typage)
docker-compose run --rm type-check
```

### Docker directement

```bash
# Exécuter tous les tests
docker run -it --rm freecad-menuiserie-test test

# Exécuter les tests unitaires
docker run -it --rm freecad-menuiserie-test test unit

# Démarrer un shell
docker run -it --rm freecad-menuiserie-test bash

# Monter le code local (pour développement)
docker run -it --rm \
  -v $(pwd):/workspace/freecad-menuiserie \
  freecad-menuiserie-test test
```

## Développement avec montage de volume

Pour développer avec un rechargement automatique du code :

```bash
# Utiliser les deux fichiers compose
make build
make test

# Ou directement
docker-compose -f docker-compose.yml -f docker-compose.dev.yml run --rm test
```

Cela monte votre code local dans le conteneur, permettant de :
- Modifier le code sans reconstruire l'image
- Voir les changements immédiatement dans le conteneur
- Utiliser votre éditeur de code préféré

## Types de tests

### Tests unitaires

- **Répertoire** : `tests/unit/`
- **Exécution** : `make test-unit` ou `docker-compose run test-unit`
- **Description** : Tests qui ne nécessitent pas FreeCAD (logique métier, calculs géométriques, etc.)
- **Durée** : Rapide (quelques secondes)

### Tests d'intégration

- **Répertoire** : `tests/integration/`
- **Exécution** : `make test-integration` ou `docker-compose run test-integration`
- **Description** : Tests qui nécessitent FreeCAD (création de documents, manipulation de pièces, etc.)
- **Durée** : Plus longue (plusieurs minutes)

### Tests GUI

- **Répertoire** : `tests/gui/`
- **Exécution** : Inclus dans `test all` ou via `docker run freecad-menuiserie-test test gui`
- **Description** : Tests de l'interface graphique (nécessite `QT_QPA_PLATFORM=offscreen`)
- **Durée** : Variable

## Configuration avancée

### Variables d'environnement

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `FREECAD_USER_HOME` | Répertoire utilisateur FreeCAD | `/tmp/freecad-home` |
| `QT_QPA_PLATFORM` | Plateforme Qt pour les tests GUI | `offscreen` |
| `TZ` | Timezone | `Europe/Paris` |
| `PYTHONPATH` | Chemin Python | `/opt/conda/lib:$PYTHONPATH` |

### Exemple avec variables personnalisées

```bash
docker run -it --rm \
  -e TZ=America/New_York \
  -e FREECAD_USER_HOME=/custom/freecad-home \
  -v $(pwd):/workspace/freecad-menuiserie \
  freecad-menuiserie-test test
```

## Résolution des problèmes

### Problème : FreeCAD non trouvé

```
ImportError: No module named 'FreeCAD'
```

**Solution** : 
- Vérifiez que l'image a bien été construite
- Assurez-vous que FreeCAD est installé dans le conteneur
- Exécutez `docker run freecad-menuiserie-test python -c "import FreeCAD; print(FreeCAD.Version())"`

### Problème : Tests GUI échouent

```
QStandardPaths: XDG_RUNTIME_DIR not set
```

**Solution** : 
- Ajoutez `-e XDG_RUNTIME_DIR=/tmp` à votre commande Docker
- Ou utilisez `QT_QPA_PLATFORM=offscreen` (déjà configuré par défaut)

### Problème : Problèmes de permissions

```
Permission denied
```

**Solution** : 
- Ajoutez `--user $(id -u):$(id -g)` à votre commande Docker
- Ou changez les permissions des fichiers temporaires

### Problème : Manque de mémoire

Si la construction échoue avec des erreurs de mémoire :

```bash
# Limiter l'utilisation mémoire
docker build --memory=4g --memory-swap=4g -t freecad-menuiserie-test .
```

Ou dans docker-compose :

```yaml
services:
  test:
    deploy:
      resources:
        limits:
          memory: 4G
```

## Performance

Pour améliorer les performances :

1. **Cache Docker** : Utilisez le cache Docker pour éviter de télécharger à chaque fois
2. **Volume montage** : Montez seulement les fichiers nécessaires
3. **BuildKit** : Utilisez BuildKit pour des constructions plus rapides

```bash
# Activer BuildKit
export DOCKER_BUILDKIT=1

# Construire avec cache
docker build --cache-from freecad-menuiserie-test -t freecad-menuiserie-test .
```

## Architecture Docker

L'image Docker contient :

1. **Ubuntu 24.04** : Système de base
2. **MicroMamba** : Gestionnaire de paquets conda léger
3. **FreeCAD** : Installe depuis conda-forge
4. **Python 3.10+** : Avec toutes les dépendances de développement
5. **Outils** : pytest, ruff, mypy, pylint, etc.

## Mise à jour

Pour mettre à jour l'image après un changement :

```bash
# Reconstruire l'image
make clean
make build

# Ou
docker-compose build --no-cache
```

## Contribution

Si vous modifiez la configuration Docker :

1. Testez localement
2. Vérifiez que tous les tests passent
3. Mettez à jour la documentation
4. Soumettez une PR

## Licence

Ce fichier fait partie de **freecad-menuiserie** et est distribué sous la licence **LGPL-2.1-or-later**.
