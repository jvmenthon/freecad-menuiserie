# SPDX-License-Identifier: LGPL-2.1-or-later
"""Propriétés « butée » de la répétition (ADR 0047), décrites par des données.

Par ligne de la grille (même suffixe que les autres propriétés, ``line_name``) : ``Stop`` (lien
global vers la butée et son sous-élément ``FaceN`` ou ``VertexN``, vide pour une pièce entière) et
``StopLabel`` (libellé de la butée au moment du choix, lecture seule : il permet de signaler une
butée supprimée). Communs : ``StopHolders`` (conteneurs des butées hors du conteneur de la
répétition, pour que le déplacement d'un conteneur recalcule la longueur) et la case
``DeductThickness``. Ces propriétés sont facultatives :
un document d'avant la butée ne les a pas, elles sont ajoutées à l'ouverture (``DeductThickness``
vrai, comme le comportement d'alors).

Contrat de persistance (ADR 0003) : ces noms ne changent jamais.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import READ_ONLY
from freecad.menuiserie.features.repeat_props import GROUP, LINE_COUNT, line_name
from freecad.menuiserie.features.schema import PropertySpec

__all__ = ["DEDUCT_PROPERTY", "GAP_PROPERTY", "HOLDERS_PROPERTY", "STOP_PROPERTIES"]

DEDUCT_PROPERTY: Final = "DeductThickness"
HOLDERS_PROPERTY: Final = "StopHolders"
GAP_PROPERTY: Final = "EndGap"


def _line_specs(line: int) -> tuple[PropertySpec, PropertySpec]:
    return (
        PropertySpec(
            line_name("Stop", line),
            "App::PropertyLinkSubGlobal",
            GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Butée de la ligne : face, sommet ou pièce entière contre laquelle s'arrête la "
                "dernière copie. La longueur suit la butée.",
            ),
            mode=READ_ONLY,
        ),
        PropertySpec(
            line_name("StopLabel", line),
            "App::PropertyString",
            GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Libellé de la butée choisie (sert à signaler sa suppression)."
            ),
            default="",
            mode=READ_ONLY,
        ),
    )


STOP_PROPERTIES: Final = (
    *(spec for line in range(LINE_COUNT) for spec in _line_specs(line)),
    PropertySpec(
        HOLDERS_PROPERTY,
        "App::PropertyLinkListGlobal",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Conteneurs des butées qui ne contiennent pas la répétition : déplacer l'un d'eux "
            "recalcule la longueur.",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        DEDUCT_PROPERTY,
        "App::PropertyBool",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Modes sur une longueur : déduit l'épaisseur de la pièce de la longueur, la dernière "
            "copie arrive à fleur de la fin. Décochée, elle commence à la fin de la longueur.",
        ),
        default=True,
        mode=READ_ONLY,
    ),
    PropertySpec(
        GAP_PROPERTY,
        "App::PropertyBool",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Modes sur une longueur : les éléments partagent la longueur en autant d'intervalles "
            "égaux ; la dernière pièce s'arrête un intervalle avant la fin.",
        ),
        default=False,
        mode=READ_ONLY,
    ),
)
