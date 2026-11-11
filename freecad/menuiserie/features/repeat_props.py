# SPDX-License-Identifier: LGPL-2.1-or-later
"""Propriétés de la répétition et de ses copies (ADR 0043 et 0045), décrites par des données.

Une répétition a une ou plusieurs **lignes** (une par axe actif de la grille, ADR 0045) : la
première ligne garde les noms historiques (``Axis``, ``Count``, ``Step``, ``Span``, ``Reverse``),
les deux suivantes portent le suffixe ``2`` et ``3`` (``Axis2``, ``Count2``, ``Step2``…). Dans
chaque ligne, ``Count`` est le nombre de copies **en plus de l'original le long de l'axe** (soit
le nombre d'éléments moins un). Une ligne 2 ou 3 sans axe a ``Axis2`` = ``None``.

Contrat de persistance (ADR 0003 et 0045) : ces noms de propriétés et les valeurs de ``Mode``,
``Spacing`` et ``Axis`` ne changent jamais ; les propriétés des lignes 2 et 3 et ``RepeatCell``
sont facultatives (un document plus ancien ne les a pas : voir :mod:`.repeat`).
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import RepeatAxis, RepeatMode, SpacingMode
from freecad.menuiserie.features.freecad_types import READ_ONLY
from freecad.menuiserie.features.schema import LENGTH, PropertySpec, version_spec

__all__ = [
    "CELL_PROPERTY",
    "CELL_SPEC",
    "CHOICES",
    "COPY_PROPERTIES",
    "COPY_PROPERTY_NAMES",
    "GRID_PROPERTIES",
    "LINE_COUNT",
    "MODEL_VERSION",
    "NOUN",
    "REPEAT_PROPERTIES",
    "line_name",
]

MODEL_VERSION: Final = 1
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répétition")
GROUP: Final = "Répétition"
# Listes de choix des énumérations : valeurs de ``core.repeat`` (stables), ajouts en fin.
NO_AXIS: Final = "None"  # ligne 2 ou 3 inutilisée
LINE_COUNT: Final = 3  # lignes au plus : une par axe
CHOICES: Final = {
    "Mode": [mode.value for mode in RepeatMode],
    "Spacing": [spacing.value for spacing in SpacingMode],
    "Axis": [axis.value for axis in RepeatAxis],
    "Axis2": [NO_AXIS, *(axis.value for axis in RepeatAxis)],
    "Axis3": [NO_AXIS, *(axis.value for axis in RepeatAxis)],
}


def line_name(field: str, line: int) -> str:
    """Nom de la propriété ``field`` (``Axis``, ``Count``, ``Step``, ``Span`` ou ``Reverse``) de la
    ligne ``line`` (0, 1 ou 2) : le nom historique pour la première, suffixé de 2 ou 3 ensuite."""
    return field if line == 0 else f"{field}{line + 1}"


REPEAT_PROPERTIES: Final = (
    PropertySpec(
        "Source",
        "App::PropertyLinkListGlobal",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Pièces répétées (chacune a ses propres copies)."),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Mode",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Genre de répétition : Linear ; Circular et Path sont réservés."
        ),
        default=RepeatMode.LINEAR.value,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Spacing",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Manière de saisir la répétition : CountAndStep (nombre et pas), CountOnSpan (nombre "
            "sur une longueur) ou StepOnSpan (pas sur une longueur).",
        ),
        default=SpacingMode.COUNT_AND_STEP.value,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Axis",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Axe global de la répétition linéaire."),
        default=RepeatAxis.X.value,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Count",
        "App::PropertyInteger",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Nombre de copies en plus de la source le long de l'axe (grille : voir Count2 et "
            "Count3 ; le total est le produit des (nombre + 1) moins un). Il ne change que par la "
            "commande « Modifier la répétition » (les copies se créent et se suppriment hors "
            "recalcul).",
        ),
        default=0,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Step",
        LENGTH,
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Pas entre deux copies, mesuré sur l'axe. Les copies suivent quand il change ; en "
            "mode « sur une longueur », la prochaine modification de la répétition le recalcule.",
        ),
        default=100.0,
    ),
    PropertySpec(
        "Span",
        LENGTH,
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Longueur à remplir (modes CountOnSpan et StepOnSpan), source comprise.",
        ),
        default=0.0,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Reverse",
        "App::PropertyBool",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Répète dans le sens négatif de l'axe ; les copies suivent."
        ),
        default=False,
    ),
    PropertySpec(
        "CopyJoints",
        "App::PropertyBool",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Recopie les assemblages de la source sur chaque copie."
        ),
        default=True,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "FollowResize",
        "App::PropertyBool",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Suit le redimensionnement de l'ensemble : le pas se recalcule pour garder la "
            "longueur.",
        ),
        default=False,
        mode=READ_ONLY,
    ),
    version_spec(
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la répétition, utilisée pour migrer les anciens "
            "fichiers.",
        ),
        MODEL_VERSION,
    ),
)

COPY_PROPERTIES: Final = (
    PropertySpec(
        "Repeat",
        "App::PropertyLinkGlobal",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Répétition dont la pièce est une copie liée."),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "RepeatSource",
        "App::PropertyLinkGlobal",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Pièce dont celle-ci est la copie."),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "RepeatIndex",
        "App::PropertyInteger",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Rang de la copie (1 pour la première copie après la source)."
        ),
        default=1,
        mode=READ_ONLY,
    ),
)
COPY_PROPERTY_NAMES: Final = tuple(spec.name for spec in COPY_PROPERTIES)
CELL_PROPERTY: Final = "RepeatCell"
CELL_SPEC: Final = PropertySpec(
    CELL_PROPERTY,
    "App::PropertyIntegerList",
    GROUP,
    QT_TRANSLATE_NOOP(
        "App::Property",
        "Cellule de la copie dans la grille : rangs sur X, Y et Z (0, 0, 0 est l'original). Elle "
        "identifie la copie quand le nombre d'un axe change.",
    ),
    default=None,
    mode=READ_ONLY,
)


def _line_specs(line: int, tips: tuple[str, str, str, str, str]) -> tuple[PropertySpec, ...]:
    axis, count, step, span, reverse = tips
    return (
        PropertySpec(
            line_name("Axis", line),
            "App::PropertyEnumeration",
            GROUP,
            axis,
            default=NO_AXIS,
            mode=READ_ONLY,
        ),
        PropertySpec(
            line_name("Count", line), "App::PropertyInteger", GROUP, count, 0, mode=READ_ONLY
        ),
        PropertySpec(line_name("Step", line), LENGTH, GROUP, step, default=100.0),
        PropertySpec(line_name("Span", line), LENGTH, GROUP, span, default=0.0, mode=READ_ONLY),
        PropertySpec(line_name("Reverse", line), "App::PropertyBool", GROUP, reverse, False),
    )


# Lignes 2 et 3 de la grille (ADR 0045) ; la ligne 1 est décrite par REPEAT_PROPERTIES.
GRID_PROPERTIES: Final = (
    *_line_specs(
        1,
        (
            QT_TRANSLATE_NOOP(
                "App::Property", "Axe de la deuxième ligne de la grille (None : inutilisée)."
            ),
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Nombre de copies en plus de la source le long de l'axe de la deuxième ligne.",
            ),
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Pas entre deux copies sur l'axe de la deuxième ligne ; les copies suivent.",
            ),
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Longueur à remplir sur l'axe de la deuxième ligne, source comprise.",
            ),
            QT_TRANSLATE_NOOP(
                "App::Property", "Répète dans le sens négatif de l'axe de la deuxième ligne."
            ),
        ),
    ),
    *_line_specs(
        2,
        (
            QT_TRANSLATE_NOOP(
                "App::Property", "Axe de la troisième ligne de la grille (None : inutilisée)."
            ),
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Nombre de copies en plus de la source le long de l'axe de la troisième ligne.",
            ),
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Pas entre deux copies sur l'axe de la troisième ligne ; les copies suivent.",
            ),
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Longueur à remplir sur l'axe de la troisième ligne, source comprise.",
            ),
            QT_TRANSLATE_NOOP(
                "App::Property", "Répète dans le sens négatif de l'axe de la troisième ligne."
            ),
        ),
    ),
)
