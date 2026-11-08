# 🐳 Corrections Docker - PYTHONPATH

## Problème

Le warning suivant était affiché lors de l'exécution de Docker Compose :
```
WARN[0000] The "PYTHONPATH" variable is not set. Defaulting to a blank string.
```

**Cause** : Dans `docker-compose.yml`, la ligne :
```yaml
- PYTHONPATH=/opt/conda/lib:${PYTHONPATH}
```

Essayait d'utiliser la variable d'environnement `PYTHONPATH` du **shell hôte**, qui n'était pas définie. Dans Docker Compose, la syntaxe `${VAR}` fait référence aux variables du shell hôte, pas du conteneur.

## Solution

### 1. ✅ Supprimer PYTHONPATH de docker-compose.yml
**Fichier** : `docker-compose.yml`

**Avant** :
```yaml
environment:
  - TZ=${TZ:-Europe/Paris}
  - FREECAD_USER_HOME=/tmp/freecad-home
  - QT_QPA_PLATFORM=offscreen
  - PYTHONPATH=/opt/conda/lib:${PYTHONPATH}  # ❌ Problème
```

**Après** :
```yaml
environment:
  - TZ=${TZ:-Europe/Paris}
  - FREECAD_USER_HOME=/tmp/freecad-home
  - QT_QPA_PLATFORM=offscreen
  # ✅ PYTHONPATH supprimée (définie dans Dockerfile)
```

### 2. ✅ Simplifier PYTHONPATH dans Dockerfile
**Fichier** : `Dockerfile` (ligne ~140)

**Avant** :
```dockerfile
ENV PYTHONPATH="$CONDA_PREFIX/lib:$PYTHONPATH"
```

**Après** :
```dockerfile
ENV PYTHONPATH="$CONDA_PREFIX/lib"
```

**Raison** : `$PYTHONPATH` n'est pas définie lors de la construction de l'image, donc elle était vide. La chaîne résultante était `/opt/conda/lib:` (avec un `: ` final inutile).

### 3. ✅ Simplifier docker-entrypoint.sh
**Fichier** : `docker-entrypoint.sh`

**Supprimé** : Toutes les redéfinitions redondantes de PYTHONPATH
- Lignes 89, 97 : Supprimées (dans `run_tests` pour integration et gui)
- Ligne 209 : Supprimée (dans le cas `pytest`)

**Ajouté** : Une seule définition initiale
```bash
# Ajouter le workspace au PYTHONPATH pour les imports du code source
if [ -d "/workspace/freecad-menuiserie" ]; then
    export PYTHONPATH="/workspace:$PYTHONPATH"
fi
```

**Résultat** : PYTHONPATH est maintenant définie comme :
1. `/opt/conda/lib` (depuis Dockerfile)
2. `/workspace:/opt/conda/lib` (depuis docker-entrypoint.sh, si /workspace existe)

## Configuration Finale

### Dockerfile (ligne ~140)
```dockerfile
ENV PYTHONPATH="$CONDA_PREFIX/lib"
```

### docker-entrypoint.sh (ligne 16-18)
```bash
# Ajouter le workspace au PYTHONPATH pour les imports du code source
if [ -d "/workspace/freecad-menuiserie" ]; then
    export PYTHONPATH="/workspace:$PYTHONPATH"
fi
```

### docker-compose.yml
```yaml
environment:
  - TZ=${TZ:-Europe/Paris}
  - FREECAD_USER_HOME=/tmp/freecad-home
  - QT_QPA_PLATFORM=offscreen
  # PYTHONPATH est définie dans Dockerfile, pas ici
```

## Vérification

Pour vérifier que le warning a disparu :
```bash
cd freecad-menuiserie
docker-compose config
```

Le warning **ne devrait plus apparaître**.

Pour tester le conteneur :
```bash
docker-compose run --rm shell
echo $PYTHONPATH
# Doit afficher : /workspace:/opt/conda/lib
```

## Avantages

✅ **Warning résolu** : Plus de message d'avertissement Docker Compose  
✅ **Configuration simplifiée** : PYTHONPATH définie une seule fois de manière claire  
✅ **Cohérence** : Pas de redéfinitions redondantes  
✅ **Flexibilité** : Le workspace est ajouté automatiquement si présent  
✅ **Compatibilité** : Fonctionne avec et sans montage de volume  

---

**Date** : 2026-11-07  
**Fichiers modifiés** : 
- `docker-compose.yml`
- `Dockerfile`
- `docker-entrypoint.sh`
