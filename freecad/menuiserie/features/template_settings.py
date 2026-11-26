# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier proposés par les formulaires des gabarits (ADR 0069).

Les valeurs ne sont que proposées à l'ouverture du formulaire du caisson ; le caisson créé les
garde, et changer un réglage ne touche aucun caisson existant. « Dernier utilisé » retient les
cotes d'un caisson validé. L'API (``make_carcass``) reste sur les valeurs de ``core``.
"""

from __future__ import annotations

from collections.abc import Mapping

from freecad.menuiserie.features import settings as config

__all__ = ["carcass_proposals", "record_carcass_used"]


def carcass_proposals() -> dict[str, float]:
    """Cotes proposées au formulaire du caisson, par champ de ``CarcassParams`` (mm) : largeur,
    profondeur, hauteur, épaisseur des panneaux, épaisseur du fond et feuillure du fond."""
    values = config.settings()
    return {name: float(values.value(key)) for name, key in config.CARCASS_FIELDS.items()}


def record_carcass_used(values: Mapping[str, object]) -> None:
    """« Dernier utilisé » : cotes du caisson validé (``values``, par champ de ``CarcassParams``),
    retenues pour les réglages dont la case est cochée ; un champ absent est ignoré."""
    settings = config.settings()
    for name, key in config.CARCASS_FIELDS.items():
        if name in values:
            settings.record_used(key, values[name])
