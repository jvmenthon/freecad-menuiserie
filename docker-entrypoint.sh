#!/bin/bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Point d'entrée pour le conteneur Docker de test freecad-menuiserie

# Ne pas arrêter sur erreur pour les commandes interactives
# set -e

# ============================================================================
# Configuration initiale
# ============================================================================

export FREECAD_USER_HOME="${FREECAD_USER_HOME:-/tmp/freecad-home}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"

# Ajouter le workspace au PYTHONPATH pour les imports du code source
# /workspace/freecad-menuiserie est copié dans l'image ou monté en volume
if [ -d "/workspace/freecad-menuiserie" ]; then
    export PYTHONPATH="/workspace:$PYTHONPATH"
fi

# Ajouter les bibliothèques FreeCAD au PYTHONPATH pour pouvoir importer FreeCAD
# Les modules .so de FreeCAD sont dans /opt/conda/lib
if [ -d "/opt/conda/lib" ]; then
    export PYTHONPATH="/opt/conda/lib:$PYTHONPATH"
fi

# Créer les répertoires si ils n'existent pas
mkdir -p "${FREECAD_USER_HOME}/Mod"
mkdir -p "${FREECAD_USER_HOME}/templates"

# ============================================================================
# Lien symbolique vers le code source
# ============================================================================

# Créer le répertoire Mod s'il n'existe pas
mkdir -p "${FREECAD_USER_HOME}/Mod"

# Si /workspace/freecad-menuiserie existe, créer un lien vers Mod/Menuiserie
# Utiliser ln -sf ou copier les fichiers si ln échoue (volume en lecture seule)
if [ -d "/workspace/freecad-menuiserie" ]; then
    # Essayer de créer un lien symbolique
    ln -sf /workspace/freecad-menuiserie "${FREECAD_USER_HOME}/Mod/Menuiserie" 2>/dev/null || \
    # Si le lien échoue (volume en lecture seule ou autre), copier les fichiers
    cp -rf /workspace/freecad-menuiserie "${FREECAD_USER_HOME}/Mod/Menuiserie" 2>/dev/null || \
    echo "⚠️  Impossible de lier ou copier /workspace/freecad-menuiserie vers Mod/Menuiserie"
fi

# Si le répertoire courant contient freecad-menuiserie, l'utiliser
if [ -d "./freecad-menuiserie" ]; then
    ln -sf ./freecad-menuiserie "${FREECAD_USER_HOME}/Mod/Menuiserie" 2>/dev/null || \
    cp -rf ./freecad-menuiserie "${FREECAD_USER_HOME}/Mod/Menuiserie" 2>/dev/null || \
    echo "⚠️  Impossible de lier ou copier ./freecad-menuiserie vers Mod/Menuiserie"
fi

# ============================================================================
# Affichage des informations (version rapide sans import FreeCAD)
# ============================================================================

echo "=========================================="
echo "Environnement de test freecad-menuiserie"
echo "=========================================="
echo ""
echo "Python version:"
python --version
echo "  Path: $(which python)"

echo ""
echo "PYTHONPATH:"
echo "  ${PYTHONPATH}"

echo ""
echo "FREECAD_USER_HOME:"
echo "  ${FREECAD_USER_HOME}"

echo ""
echo "=========================================="
echo ""

# ============================================================================
# Fonctions utilitaires
# ============================================================================

run_tests() {
    local test_type="${1:-all}"
    local verbose="${2:-}"
    
    case "$test_type" in
        unit|units|unitaire|unitaires)
            echo "Exécution des tests unitaires..."
            cd /workspace/freecad-menuiserie
            pytest tests/unit --cov --cov-report=term-missing ${verbose}
            ;;
        integration|int|intégration)
            echo "Exécution des tests d'intégration..."
            cd /workspace/freecad-menuiserie
            export FREECAD_USER_HOME="${FREECAD_USER_HOME}"
            pytest tests/integration -m integration ${verbose}
            ;;
        gui)
            echo "Exécution des tests GUI..."
            cd /workspace/freecad-menuiserie-
            export QT_QPA_PLATFORM=offscreen
            export FREECAD_USER_HOME="${FREECAD_USER_HOME}"
            # Les tests GUI nécessitent un affichage, même en mode offscreen
            pytest tests/gui ${verbose}
            ;;
        lint|ruff)
            echo "Exécution de ruff (lint)..."
            cd /workspace/freecad-menuiserie
            ruff check --output-format=github .
            ;;
        format)
            echo "Vérification du formatage..."
            cd /workspace/freecad-menuiserie
            ruff format --check .
            ;;
        mypy)
            echo "Exécution de mypy (typage)..."
            cd /workspace/freecad-menuiserie
            mypy freecad tests
            ;;
        pylint)
            echo "Exécution de pylint (code dupliqué)..."
            cd /workspace/freecad-menuiserie
            pylint freecad tests tools
            ;;
        all|*|"")
            echo "Exécution de tous les tests..."
            cd /workspace/freecad-menuiserie
            
            # Tests unitaires
            echo ""
            echo "=== TESTS UNITAIRES ==="
            pytest tests/unit --cov --cov-report=term-missing ${verbose} || echo "⚠️  Certains tests unitaires ont échoué"
            
            # Tests d'intégration
            echo ""
            echo "=== TESTS D'INTÉGRATION ==="
            export FREECAD_USER_HOME="${FREECAD_USER_HOME}"
            pytest tests/integration -m integration ${verbose} || echo "⚠️  Certains tests d'intégration ont échoué"
            
            # Tests GUI (optionnel, peut nécessiter plus de configuration)
            echo ""
            echo "=== TESTS GUI (optionnels) ==="
            export QT_QPA_PLATFORM=offscreen
            pytest tests/gui ${verbose} || echo "⚠️  Certains tests GUI ont échoué"
            ;;
    esac
}

# ============================================================================
# Traitement des arguments
# ============================================================================

# Si aucun argument, afficher l'aide
if [ $# -eq 0 ]; then
    cat << 'EOF'

Utilisation :
  docker run -it --rm freecad-menuiserie-test [COMMANDE] [OPTIONS]

Commandes disponibles :
  bash, sh           - Démarre un shell interactif
  test [type]        - Exécute les tests
  tests [type]       - Alias de 'test'
  pytest [args]      - Exécute pytest directement
  ruff               - Exécute ruff (lint)
  mypy               - Exécute mypy (typage)
  pylint             - Exécute pylint

Types de tests :
  all (par défaut)   - Tous les tests
  unit              - Tests unitaires uniquement
  integration       - Tests d'intégration uniquement
  gui               - Tests GUI uniquement

Exemples :
  # Démarrer un shell
  docker run -it --rm freecad-menuiserie-test bash
  
  # Exécuter tous les tests
  docker run -it --rm freecad-menuiserie-test test
  
  # Exécuter seulement les tests unitaires
  docker run -it --rm freecad-menuiserie-test test unit
  
  # Exécuter les tests avec verbose
  docker run -it --rm freecad-menuiserie-test test unit -v
  
  # Monter le code local pour développement
  docker run -it --rm -v $(pwd):/workspace freecad-menuiserie-test test
  
  # Exécuter pytest directement
  docker run -it --rm freecad-menuiserie-test pytest tests/unit/test_tourillons.py -v

Variables d'environnement utiles :
  FREECAD_USER_HOME  - Répertoire utilisateur FreeCAD (défaut: /tmp/freecad-home)
  QT_QPA_PLATFORM    - Plateforme Qt (défaut: offscreen)

EOF
    exit 0
fi

# Traitement des commandes
case "$1" in
    bash|sh|zsh|/bin/bash|/bin/sh)
        exec "$@"
        ;;
    test|tests)
        shift
        run_tests "$@"
        ;;
    pytest)
        shift
        cd /workspace/freecad-menuiserie
        export FREECAD_USER_HOME="${FREECAD_USER_HOME}"
        export QT_QPA_PLATFORM=offscreen
        exec pytest "$@"
        ;;
    ruff)
        shift
        cd /workspace/freecad-menuiserie
        exec ruff "$@"
        ;;
    mypy)
        shift
        cd /workspace/freecad-menuiserie
        exec mypy "$@"
        ;;
    pylint)
        shift
        cd /workspace/freecad-menuiserie
        exec pylint "$@"
        ;;
    *)
        # Essayer d'exécuter la commande directement
        exec "$@"
        ;;
esac
