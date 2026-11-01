# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fabrique et suppression des profils d'arête du document (issue #5, ADR 0029).

La fabrique valide tout avant de créer quoi que ce soit (pièce de bois, arêtes, famille, cotes,
arêtes déjà profilées), crée le profil, puis la pièce usinée de la brute si besoin. Ni transaction
ni recalcul : c'est à l'appelant de les faire.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from freecad.menuiserie.core.edges import EdgeFamily
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.edge_profile import (
    OBJECT_NAME,
    EdgeProfile,
    checked_codes,
    family_of,
    is_edge_profile,
    profile_cuts,
)
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.machined_part import (
    ensure_machined_part,
    is_machined_part,
    machined_part_of,
    remove_machined_part,
)
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.features.wood_part_record import dimensions_of

__all__ = ["create_edge_profile", "edge_profiles_of", "remove_edge_profile", "update_edge_profile"]

_PROFILE_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Profil d'arête")
_SHAPED_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est une pièce en bois (forme dessinée) : les profils d'arête ne s'appliquent "
    "qu'aux pièces de bois (boîtes).",
)
_NOT_A_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est ni une pièce de bois ni sa pièce usinée."
)
_NOT_A_PROFILE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas un profil d'arête de l'atelier Menuiserie."
)
_ALREADY_PROFILED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Ces arêtes ont déjà un profil : {edges}. Remplacez-le ou choisissez d'autres arêtes.",
)


def edge_profiles_of(part: DocumentObject) -> list[DocumentObject]:
    """Profils d'arête de la pièce ``part`` (brute ou usinée), vide s'il n'y en a pas."""
    blank = part.Base if is_machined_part(part) else part
    machined = None if blank is None else machined_part_of(blank)
    if machined is None:
        return []
    return [finish for finish in machined.Finishes if is_edge_profile(finish)]


def _blank_of(part: DocumentObject) -> DocumentObject:
    """Pièce de bois (boîte) de ``part``, brute ou usinée ; ``ValueError`` traduite sinon."""
    blank = part.Base if is_machined_part(part) else part
    label = quoted_value(getattr(part, "Label", part))
    if is_shaped_part(blank):
        raise ValueError(translated(_SHAPED_PART, {"label": label}))
    if not is_wood_part(blank):
        raise TypeError(translated(_NOT_A_PART, {"label": label}))
    return blank


def _free_edges(
    existing: Iterable[DocumentObject], codes: list[str], replace: bool
) -> list[DocumentObject]:
    """Profils existants qui partagent des arêtes avec ``codes`` : ``ValueError`` traduite
    sauf si ``replace``."""
    shared = [profile for profile in existing if set(profile.Edges) & set(codes)]
    if shared and not replace:
        names = sorted({code for profile in shared for code in profile.Edges if code in codes})
        raise ValueError(translated(_ALREADY_PROFILED, {"edges": ", ".join(names)}))
    return shared


def _strip(document: Document, shared: list[DocumentObject], codes: list[str]) -> None:
    """Retire ``codes`` des profils ``shared`` ; un profil sans arête est supprimé."""
    for old in shared:
        remaining = [code for code in old.Edges if code not in codes]
        if remaining:
            old.Edges = remaining
        else:
            document.removeObject(old.Name)


def create_edge_profile(
    part: DocumentObject,
    edges: object,
    family: EdgeFamily | str,
    size_a: float,
    size_b: float = 0.0,
    *,
    replace: bool = False,
) -> DocumentObject:
    """Crée un profil ``family`` de cotes ``size_a`` et ``size_b`` (mm) sur les arêtes ``edges``
    (codes ``"Z+Y-"``, noms ``"dessus-avant"`` ou ``EdgeId``) de la pièce de bois ``part``
    (brute ou usinée), puis sa pièce usinée si besoin.

    ``TypeError`` ou ``ValueError`` traduites avant toute création si la pièce n'est pas une pièce
    de bois (boîte), si les arêtes, la famille ou les cotes sont refusées, ou si une arête a déjà
    un profil. Avec ``replace``, les arêtes déjà profilées sont reprises par le nouveau profil
    (l'ancien profil est supprimé s'il n'en garde aucune).
    """
    blank = _blank_of(part)
    codes = checked_codes(edges)
    kind = family_of(family.value if isinstance(family, EdgeFamily) else family)
    with translated_errors():
        dimensions = dimensions_of(blank)
    profile_cuts(str(blank.Label), dimensions, codes, kind, size_a, size_b)
    document = blank.Document
    _strip(document, _free_edges(edge_profiles_of(blank), codes, replace), codes)
    obj = document.addObject("Part::FeaturePython", OBJECT_NAME)
    EdgeProfile(obj)
    container = blank.getParentGeoFeatureGroup()
    if container is not None:
        container.addObject(obj)
    obj.Part = blank
    obj.Edges = codes
    obj.Family = kind.value
    obj.SizeA = size_a
    obj.SizeB = size_b
    obj.Label = translated(_PROFILE_LABEL)
    machined = ensure_machined_part(blank)
    machined.Finishes = [*machined.Finishes, obj]
    return obj


def remove_edge_profile(profile: DocumentObject) -> None:
    """Supprime le profil ``profile`` ; la pièce usinée disparaît aussi (et la brute est
    réaffichée) quand il ne lui reste ni assemblage ni finition. Sans transaction ni recalcul.
    ``TypeError`` traduite si ``profile`` n'est pas un profil d'arête."""
    if not is_edge_profile(profile):
        raise TypeError(translated(_NOT_A_PROFILE, {"label": quoted_value(profile.Label)}))
    blank = profile.Part
    machined = None if blank is None else machined_part_of(blank)
    profile.Document.removeObject(profile.Name)
    if machined is not None and not machined.Joints and not machined.Finishes:
        remove_machined_part(machined)


def update_edge_profile(
    profile: DocumentObject,
    edges: object,
    family: EdgeFamily | str,
    size_a: float,
    size_b: float = 0.0,
    *,
    replace: bool = False,
) -> None:
    """Change les arêtes, la famille et les cotes de ``profile`` (mêmes validations et mêmes
    refus que :func:`create_edge_profile`, avant toute écriture). Sans recalcul ni transaction.
    ``TypeError`` traduite si ``profile`` n'est pas un profil d'arête."""
    if not is_edge_profile(profile):
        raise TypeError(translated(_NOT_A_PROFILE, {"label": quoted_value(profile.Label)}))
    blank = _blank_of(profile.Part)
    codes = checked_codes(edges)
    kind = family_of(family.value if isinstance(family, EdgeFamily) else family)
    with translated_errors():
        dimensions = dimensions_of(blank)
    profile_cuts(str(blank.Label), dimensions, codes, kind, size_a, size_b)
    others = [other for other in edge_profiles_of(blank) if other != profile]
    _strip(blank.Document, _free_edges(others, codes, replace), codes)
    profile.Edges = codes
    profile.Family = kind.value
    profile.SizeA = size_a
    profile.SizeB = size_b
