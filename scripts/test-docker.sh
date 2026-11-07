#!/bin/bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Script pour tester la construction Docker en local

set -e

echo "=========================================="
echo "Test de la construction Docker"
echo "=========================================="
echo ""

# Vérifier que Docker est installé
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Veuillez installer Docker d'abord."
    echo "   https://www.docker.com/"
    exit 1
fi

# Vérifier que Docker est en cours d'exécution
if ! docker info &> /dev/null; then
    echo "❌ Docker n'est pas en cours d'exécution. Veuillez démarrer Docker."
    exit 1
fi

echo "✅ Docker est installé et en cours d'exécution"
echo ""

# Récupérer le répertoire du script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Répertoire du projet : $PROJECT_DIR"
echo ""

# Construire l'image
cd "$PROJECT_DIR"

echo "🐳 Construction de l'image Docker..."
echo ""

docker build \
    --progress=plain \
    -t freecad-menuiserie-test \
    -f Dockerfile \
    .

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Image construite avec succès !"
    echo ""
    echo "Pour exécuter les tests :"
    echo "  docker run -it --rm freecad-menuiserie-test test"
    echo ""
    echo "Pour démarrer un shell :"
    echo "  docker run -it --rm freecad-menuiserie-test bash"
else
    echo ""
    echo "❌ La construction a échoué"
    exit 1
fi
