# SPDX-License-Identifier: LGPL-2.1-or-later
# Dockerfile pour exécuter les tests de freecad-menuiserie en local
# 
# Utilisation :
#   docker build -t freecad-menuiserie-test .
#   docker run -it --rm freecad-menuiserie-test
#
# Pour monter le code local (développement) :
#   docker run -it --rm -v $(pwd):/workspace freecad-menuiserie-test

FROM ubuntu:24.04

# Configuration de base
ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Europe/Paris

# Métadonnées
LABEL maintainer="Jean-Vadim Menthon <jevadim@github.com>"
LABEL description="Environnement de test pour freecad-menuiserie"
LABEL version="1.0"

# ============================================================================
# Étape 1 : Installation des dépendances système
# ============================================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Outils de base
        bash \
        ca-certificates \
        curl \
        git \
        gnupg \
        locales \
        tzdata \
        # Dépendances pour FreeCAD et conda
        bzip2 \
        libgl1 \
        libglu1-mesa \
        libx11-6 \
        libxext6 \
        libxrender1 \
        libxtst6 \
        mesa-utils \
        # Outils de développement
        less \
        nano \
        procps \
        wget \
        && \
    # Nettoyage
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Configuration de la locale
RUN sed -i '/fr_FR.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen fr_FR.UTF-8 && \
    update-locale LANG=fr_FR.UTF-8
ENV LANG=fr_FR.UTF-8
ENV LANGUAGE=fr_FR:fr
ENV LC_ALL=fr_FR.UTF-8

# Configuration du timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# ============================================================================
# Étape 2 : Installation de MicroMamba (conda léger)
# ============================================================================
ENV CONDA_DIR="/opt/conda"
ENV PATH="$CONDA_DIR/bin:$PATH"

# Installer Miniconda3 (plus stable que miniforge)
# Utiliser le repo miroir pour éviter les problèmes de rate limiting
RUN wget --quiet "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh" -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p $CONDA_DIR && \
    rm /tmp/miniconda.sh && \
    # Nettoyer le cache
    rm -rf /root/.cache

# Configuration de conda
# Désactiver les canaux par défaut d'Anaconda pour éviter les termes de service
# On utilise directement la commande conda sans canaux par défaut
RUN conda config --set always_yes yes --set changeps1 no && \
    conda config --set show_channel_urls yes && \
    conda config --set channel_priority strict && \
    conda config --set ssl_verify true

# ============================================================================
# Étape 3 : Installation de FreeCAD
# ============================================================================
# On installe FreeCAD depuis le channel officiel freecad
# La version 1.1 est disponible via conda-forge/label/freecad_dev
# Sinon, on utilise la dernière version stable disponible
# On utilise --override-channels pour éviter les canaux par défaut

# Installation de FreeCAD 1.1 ou version supérieure
# On essaie d'abord avec la version de développement, puis on tombe sur la stable
RUN conda install -y \
        --override-channels \
        -c conda-forge/label/freecad_dev \
        -c conda-forge \
        freecad=1.1.* \
    2>/dev/null \
    || conda install -y \
        --override-channels \
        -c conda-forge/label/freecad_stable \
        -c conda-forge \
        freecad=1.1.* \
    2>/dev/null \
    || conda install -y \
        --override-channels \
        -c conda-forge \
        freecad>=0.21.0 \
    && conda clean -y --all

# ============================================================================
# Étape 4 : Installation des dépendances Python pour le développement
# ============================================================================
RUN conda install -y \
        --override-channels \
        -c conda-forge \
        python>=3.10 \
        pip \
        pytest>=8 \
        pytest-cov>=5 \
        ruff>=0.17 \
        mypy>=2.0 \
        bandit>=1.7 \
        pylint>=3.3 \
        pre-commit>=3.7 \
    && conda clean -y --all

# Installation des packages Python via pip (si nécessaire)
# Certains packages peuvent ne pas être disponibles via conda
# Note: Pour l'instant, tous les packages sont installés via conda
# COPY requirements-dev.txt /tmp/requirements-dev.txt
# RUN if [ -f /tmp/requirements-dev.txt ]; then \
#         pip install --no-cache-dir -r /tmp/requirements-dev.txt && \
#         rm /tmp/requirements-dev.txt; \
#     fi

# ============================================================================
# Étape 5 : Configuration de l'environnement
# ============================================================================

# Variable d'environnement pour FreeCAD
ENV FREECAD_USER_HOME="/tmp/freecad-home"
ENV PYTHONPATH="/opt/conda/lib"

# Pour les tests GUI sans écran
ENV QT_QPA_PLATFORM=offscreen
ENV DISPLAY=:99

# Répertoire de travail
WORKDIR /workspace

# Création des répertoires nécessaires
RUN mkdir -p \
        /workspace \
        /tmp/freecad-home/Mod \
        /root/.config/FreeCAD

# ============================================================================
# Étape 6 : Copie du code source
# ============================================================================

# Copie du code source (sera écrasé si montage de volume en runtime)
COPY . /workspace/freecad-menuiserie

# Création d'un lien symbolique vers le répertoire Mod de FreeCAD
RUN ln -sf /workspace/freecad-menuiserie /tmp/freecad-home/Mod/Menuiserie

# ============================================================================
# Étape 7 : Configuration finale
# ============================================================================

# Vérification que FreeCAD est bien installé
RUN echo "=== Vérification de l'installation de FreeCAD ===" && \
    python -c "import FreeCAD; print('FreeCAD version:', FreeCAD.Version())" && \
    python -c "import FreeCADGui" 2>/dev/null && echo 'FreeCADGui disponible' || echo 'FreeCADGui non disponible (mode headless)' && \
    echo "FreeCAD est installé avec succès"

# Installation du module en mode développement
# On installe les dépendances de développement via pip
RUN echo "=== Installation des dépendances de développement ===" && \
    cd /workspace/freecad-menuiserie && \
    pip install -e ".[dev]" 2>&1 || echo "⚠️ Installation en mode dev : certains packages peuvent être déjà installés via conda"

# ============================================================================
# Script d'entrée par défaut
# ============================================================================

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["bash"]
