# SPDX-License-Identifier: LGPL-2.1-or-later
"""Quincaillerie : catalogue de références du commerce et familles génériques (ADR 0033).

Façade : ré-exporte l'API publique des sous-modules privés, sans logique. Le catalogue est lu
en JSON strict (format 1) ; les sources se fusionnent par ``id``, la plus proche de l'utilisateur
l'emporte. Aucun accès réseau, aucun fichier de fabricant.
"""

from __future__ import annotations

from freecad.menuiserie.core.hardware._apply import (
    HARDWARE_JOINT_KINDS,
    joint_kind_of,
    joint_params,
)
from freecad.menuiserie.core.hardware._families import FAMILIES, Family, ParamSpec, family_of
from freecad.menuiserie.core.hardware._loader import (
    CatalogSource,
    load_catalog,
    merge_catalogs,
    read_catalog_file,
)
from freecad.menuiserie.core.hardware._model import Catalog, HardwareItem, UnknownHardwareError
from freecad.menuiserie.core.hardware._parser import FORMAT_VERSION, MAX_ITEMS, parse_catalog

__all__ = [
    "FAMILIES",
    "FORMAT_VERSION",
    "HARDWARE_JOINT_KINDS",
    "MAX_ITEMS",
    "Catalog",
    "CatalogSource",
    "Family",
    "HardwareItem",
    "ParamSpec",
    "UnknownHardwareError",
    "family_of",
    "joint_kind_of",
    "joint_params",
    "load_catalog",
    "merge_catalogs",
    "parse_catalog",
    "read_catalog_file",
]
