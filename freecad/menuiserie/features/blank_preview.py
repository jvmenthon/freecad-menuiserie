# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu de brutes pendant un geste, sans recalcul du document (SM-b, RO-c, ADR 0060).

Chaque brute est recalculée, puis ses assemblages qui tiennent et sa pièce usinée, montrée à ses
cotes du moment avec les seuls usinages de ces assemblages : la pièce change de taille à l'écran
même quand un assemblage ne tient plus. Celui-ci n'est pas recalculé (sa trace serait imprimée à
chaque image) : le recalcul du document au relâchement le reprend et prévient. Un assemblage
partagé par deux brutes n'est recalculé qu'une fois par aperçu. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Iterable

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joints.base import plan_for
from freecad.menuiserie.features.machined_part import machined_part_of

__all__ = ["preview_blanks", "recompute_blank"]


def _holds(joint: DocumentObject) -> bool:
    try:
        plan_for(joint)  # plan gardé en cache : le recalcul qui suit le reprend sans le refaire
    except ValueError:
        return False
    return True


def preview_blanks(raws: Iterable[DocumentObject]) -> None:
    """Aperçu des brutes ``raws`` (une fois chacune) et de leurs pièces usinées."""
    unique = list({raw.Name: raw for raw in raws}.values())
    for raw in unique:
        raw.recompute()
    done: set[str] = set()
    for raw in unique:
        machined = machined_part_of(raw)
        if machined is None:
            continue
        for joint in getattr(machined, "Joints", ()):
            if joint.Name not in done and _holds(joint):
                done.add(joint.Name)
                joint.recompute()
        try:
            machined.Proxy.preview(machined)
        except (ValueError, RuntimeError):  # brute invalide, forme OCC : le relâchement le dira
            continue


def recompute_blank(raw: DocumentObject) -> None:
    """Aperçu de la seule brute ``raw`` (et de sa pièce usinée) pendant un geste : ce que font la
    poignée de taille et le champ d'angle du panneau (RO-c)."""
    preview_blanks((raw,))
