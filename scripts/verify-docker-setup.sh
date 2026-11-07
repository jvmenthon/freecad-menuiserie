#!/bin/bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Script pour vérifier que la configuration Docker est complète

echo "=========================================="
echo "Vérification de la configuration Docker"
echo "=========================================="
echo ""

# Récupérer le répertoire du script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Répertoire du projet : $PROJECT_DIR"
echo ""

# Fichiers requis pour Docker
REQUIRED_FILES=(
    "Dockerfile"
    "docker-entrypoint.sh"
    "docker-compose.yml"
    "docker-compose.dev.yml"
    "DOCKER.md"
    "Makefile"
    ".dockerignore"
)

# Fichiers optionnels
OPTIONAL_FILES=(
    "requirements-dev.txt"
    "scripts/test-docker.sh"
    "tests/docker/test_j4c_bureau.py"
    "tests/docker/__init__.py"
    ".gitattributes"
)

ALL_OK=true

# Vérifier les fichiers requis
echo "Vérification des fichiers requis..."
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (manquant)"
        ALL_OK=false
    fi
done

echo ""
echo "Vérification des fichiers optionnels..."
for file in "${OPTIONAL_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ⚠️  $file (optionnel)"
    fi
done

echo ""

# Vérifier le contenu du Dockerfile
echo "Vérification du contenu du Dockerfile..."
if grep -q "FROM ubuntu:24.04" "$PROJECT_DIR/Dockerfile" && \
   grep -q "mamba install.*freecad" "$PROJECT_DIR/Dockerfile" && \
   grep -q "ENTRYPOINT.*docker-entrypoint.sh" "$PROJECT_DIR/Dockerfile"; then
    echo "  ✅ Dockerfile semble correct"
else
    echo "  ❌ Dockerfile semble incomplet"
    ALL_OK=false
fi

# Vérifier le script d'entrée
echo ""
echo "Vérification du script d'entrée..."
if grep -q "run_tests" "$PROJECT_DIR/docker-entrypoint.sh" && \
   grep -q "FREECAD_USER_HOME" "$PROJECT_DIR/docker-entrypoint.sh"; then
    echo "  ✅ docker-entrypoint.sh semble correct"
else
    echo "  ❌ docker-entrypoint.sh semble incomplet"
    ALL_OK=false
fi

# Vérifier docker-compose
echo ""
echo "Vérification de docker-compose.yml..."
if grep -q "freecad-menuiserie-test" "$PROJECT_DIR/docker-compose.yml" && \
   grep -q "test:" "$PROJECT_DIR/docker-compose.yml"; then
    echo "  ✅ docker-compose.yml semble correct"
else
    echo "  ❌ docker-compose.yml semble incomplet"
    ALL_OK=false
fi

echo ""
if [ "$ALL_OK" = true ]; then
    echo "=========================================="
    echo "✅ Toutes les vérifications ont réussi !"
    echo "=========================================="
    echo ""
    echo "Vous pouvez maintenant construire l'image Docker avec :"
    echo "  cd $PROJECT_DIR"
    echo "  docker-compose build"
    echo ""
    echo "Ou utiliser make :"
    echo "  make build"
    echo ""
    exit 0
else
    echo "=========================================="
    echo "❌ Certaines vérifications ont échoué"
    echo "=========================================="
    exit 1
fi
