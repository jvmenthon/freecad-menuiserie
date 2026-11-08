# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessins des icônes de la répétition (ADR 0043) : commandes « Répéter », « Modifier la
répétition », « Dissocier la copie » et objet Répétition de l'arbre. Reliés à leur fichier par
:data:`ICONES` dans ``tools/generer_icones.py`` (même moteur ``tools/icones_svg.py``)."""

from __future__ import annotations

from icones_ensembles import pastille
from icones_svg import Icone

# Tasseaux alignés selon x, du plus loin au plus proche : l'original (plein) et ses copies
# (en transparence).
PAS = 24.0
CADRE = (2, 50, 2, 50)  # place laissée à la pastille en bas à droite


def _tasseaux(ic: Icone, copies: int = 2, ecart: float = 0.0) -> None:
    """Un tasseau debout et ``copies`` copies à ``PAS`` ; la dernière écartée de ``ecart``."""
    for rang in range(copies, -1, -1):
        x = rang * PAS + (ecart if rang == copies else 0.0)
        ic.boite((x, 0, 0), (10, 22, 40), "chene", opacite=1.0 if rang == 0 else 0.55)


def repeter() -> str:
    ic = Icone("Répéter : un tasseau et ses copies alignées, pastille « plus »")
    _tasseaux(ic)
    plus = pastille("#73d216", "#2c5e00", "M49,42 V56 M42,49 H56")
    return ic.svg(cadre=CADRE, devant=plus)


def modifier_la_repetition() -> str:
    ic = Icone("Modifier la répétition : un tasseau, ses copies et un crayon")
    _tasseaux(ic)
    crayon = pastille("#3465a4", "#204a87", "M43,56 L44,51 L54,41 L58,45 L48,55 Z M51,44 L55,48")
    return ic.svg(cadre=CADRE, devant=crayon)


def dissocier_la_copie() -> str:
    ic = Icone("Dissocier la copie : la dernière copie s'écarte, pastille de lien rompu")
    _tasseaux(ic, ecart=8.0)
    rompu = pastille("#ef2929", "#a40000", "M43,43 L55,55 M55,43 L43,55")
    return ic.svg(cadre=CADRE, devant=rompu)


def repetition() -> str:
    ic = Icone("Répétition : un tasseau, ses copies et la cote du pas entre deux")
    _tasseaux(ic)
    cote = (
        '  <path d="M4,62 H29 M4,58 V62 M29,58 V62" fill="none" stroke="#204a87" '
        'stroke-width="2" stroke-linecap="round"/>'
    )
    return ic.svg(cadre=(3, 61, 3, 55), devant=cote)
