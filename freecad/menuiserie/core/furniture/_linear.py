# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fonction affine de la cote de l'ensemble et des épaisseurs des pièces (ADR 0019, § 1.6).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

NEGLIGIBLE: Final = 5e-10  # un coefficient plus petit s'écrit « 0 » (9 décimales)


@dataclass(frozen=True)
class Linear:
    """Coordonnée ou cote affine : ``coef * C + const + somme(t_k * Thickness_k)``.

    ``C`` est la cote de l'ensemble sur l'axe ; ``thickness`` associe la clé d'une pièce au
    coefficient de son épaisseur, triée par clé. Sert à écrire les expressions (``bindings_for``)
    et à calculer l'aperçu (:meth:`at`).
    """

    coef: float
    const: float
    thickness: tuple[tuple[str, float], ...] = ()

    @classmethod
    def of(cls, coef: float, const: float, terms: Mapping[str, float] | None = None) -> Linear:
        """Fonction affine dont les coefficients d'épaisseur négligeables sont retirés (et un
        coefficient négligeable de la cote ramené à 0), triés par clé."""
        kept = sorted((key, c) for key, c in (terms or {}).items() if abs(c) >= NEGLIGIBLE)
        return cls(0.0 if abs(coef) < NEGLIGIBLE else coef, const, tuple(kept))

    def at(self, size: float, thicknesses: Mapping[str, float] | None = None) -> float:
        """Valeur pour une cote d'ensemble ``size`` et les épaisseurs ``thicknesses`` (clé de
        pièce → mm) ; ``KeyError`` si une épaisseur citée manque."""
        values = thicknesses or {}
        return (
            self.coef * size + self.const + sum(coef * values[key] for key, coef in self.thickness)
        )

    def plus(self, other: Linear) -> Linear:
        """Somme de deux fonctions affines."""
        return self._combine(other, 1.0)

    def minus(self, other: Linear) -> Linear:
        """Différence de deux fonctions affines."""
        return self._combine(other, -1.0)

    def scaled(self, factor: float) -> Linear:
        """Produit par un nombre."""
        terms = {key: coef * factor for key, coef in self.thickness}
        return Linear.of(self.coef * factor, self.const * factor, terms)

    def _combine(self, other: Linear, sign: float) -> Linear:
        terms = dict(self.thickness)
        for key, coef in other.thickness:
            terms[key] = terms.get(key, 0.0) + sign * coef
        return Linear.of(self.coef + sign * other.coef, self.const + sign * other.const, terms)

    def frozen(self, values: Mapping[str, float]) -> Linear:
        """Fonction affine dont les termes d'épaisseur des pièces de ``values`` (clé → mm) sont
        remplacés par leur valeur : constante, ne suit plus l'épaisseur."""
        kept = {key: coef for key, coef in self.thickness if key not in values}
        const = self.const + sum(
            coef * values[key] for key, coef in self.thickness if key in values
        )
        return Linear.of(self.coef, const, kept)

    @property
    def keys(self) -> frozenset[str]:
        """Clés des pièces dont l'épaisseur intervient."""
        return frozenset(key for key, _ in self.thickness)

    @property
    def constant(self) -> bool:
        """Vrai si la valeur ne dépend ni de la cote ni d'une épaisseur (aucune liaison utile)."""
        return abs(self.coef) < NEGLIGIBLE and not self.thickness

    @property
    def proportional(self) -> bool:
        """Vrai si la valeur suit une part de la cote (ni 0, ni 1 : elle garde sa proportion)."""
        return abs(self.coef) >= NEGLIGIBLE and abs(self.coef - 1.0) >= NEGLIGIBLE
