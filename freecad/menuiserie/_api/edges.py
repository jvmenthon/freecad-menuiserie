# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profils d'arête de la façade publique (issue #5, ADR 0029).

Module privé : importer par :mod:`freecad.menuiserie.api`, la façade publique.
"""

from __future__ import annotations

import FreeCAD as App

from freecad.menuiserie.core.edges import EdgeFamily
from freecad.menuiserie.features.edge_profile_checks import profile_warnings
from freecad.menuiserie.features.edge_profile_create import (
    create_edge_profile,
    edge_profiles_of,
)
from freecad.menuiserie.features.edge_profile_create import (
    remove_edge_profile as _remove_edge_profile,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture_bindings import report
from freecad.menuiserie.features.machined_part import machined_part_of

__all__ = ["add_edge_profile", "edge_profiles_of", "remove_edge_profile"]


def add_edge_profile(
    part: DocumentObject,
    edges: object,
    family: EdgeFamily | str,
    size_a: float,
    size_b: float = 0.0,
    *,
    replace: bool = False,
) -> tuple[DocumentObject, tuple[str, ...]]:
    """Donne un profil aux arêtes ``edges`` d'une pièce de bois (brute ou usinée) et recalcule le
    document : crée le profil et, si besoin, la pièce usinée.

    ``edges`` : codes locaux (``"Z+Y-"`` : dessus-avant), noms (``"dessus-avant"``) ou
    ``EdgeId`` ; ``family`` : ``EdgeFamily`` ou sa valeur (``"Chamfer"``, ``"Round"``,
    ``"Cove"``, ``"Bullnose"``, ``"Beak"``, ``"Ogee"``) ; ``size_a`` et ``size_b`` en mm
    (``size_b`` 0 : égale à ``size_a`` pour le chanfrein et le quart de rond ; une arête cassée
    est un quart de rond de 1 mm). Une arête qui a déjà un profil est refusée, sauf avec
    ``replace``. Refus avant toute création (``TypeError`` ou ``ValueError`` traduites). Renvoie
    le profil et les avertissements traduits (aussi dans la vue rapport), par exemple « le profil
    touche l'assemblage X ». Aucune transaction n'est ouverte : c'est à l'appelant de le faire
    pour pouvoir annuler.
    """
    profile = create_edge_profile(part, edges, family, size_a, size_b, replace=replace)
    _show_machined_part(profile)
    profile.Document.recompute()
    messages = profile_warnings(profile)
    report(messages)
    return profile, messages


def remove_edge_profile(profile: DocumentObject) -> tuple[str, ...]:
    """Supprime un profil d'arête et recalcule le document ; la pièce usinée disparaît aussi
    quand il ne lui reste ni assemblage ni finition. Renvoie les avertissements traduits (aucun
    aujourd'hui, mais le contrat est celui de :func:`add_edge_profile`). Aucune transaction."""
    document = profile.Document
    _remove_edge_profile(profile)
    document.recompute()
    return ()


def _show_machined_part(profile: DocumentObject) -> None:
    """Pose le ViewProvider de la pièce usinée du profil si l'interface est chargée."""
    if App.GuiUp:
        from freecad.menuiserie.gui.view_providers.machined_part import (
            ViewProviderMachinedPart,
        )

        machined = machined_part_of(profile.Part)
        if machined is not None and not isinstance(
            machined.ViewObject.Proxy, ViewProviderMachinedPart
        ):
            ViewProviderMachinedPart(machined.ViewObject)
