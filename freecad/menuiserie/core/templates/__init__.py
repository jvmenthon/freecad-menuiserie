# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarits générateurs (J4d, ADR 0010) : description pure des pièces et des assemblages.

Un gabarit est une fonction pure (``carcass_layout``…) : paramètres validés → :class:`Layout`.
Le ``Layout`` décrit des pièces (:class:`PieceSpec`, avec leur mode et leurs options « fixe »
**explicites**, jamais celles par défaut) et des assemblages (:class:`JointSpec`). Un seul
constructeur, ``features/templates.py``, l'instancie en objets ordinaires : pièces de bois,
assemblages de J3 et Ensemble. Aucun objet « gabarit » n'est gardé dans le document.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, is_dataclass

from freecad.menuiserie.core.furniture import Edge, FurnitureBox, InteriorMode
from freecad.menuiserie.core.geometry import PlacedBlock, Vec3
from freecad.menuiserie.core.joints import JointKind

__all__ = ["JointSpec", "Layout", "PieceSpec"]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


@dataclass(frozen=True)
class PieceSpec:
    """Pièce de bois d'un gabarit.

    ``key`` : clé de la pièce dans le gabarit ; ``label`` : libellé, gabarit français marqué
    pour la traduction ; ``block`` : cotes finies et placement **relatifs à l'``Origin`` de
    l'ensemble** ; ``mode`` et ``fixed`` : mode et distances fixes du membre, donnés
    explicitement (ADR 0010).
    """

    key: str
    label: str
    block: PlacedBlock
    material_id: str
    fixed: frozenset[Edge]
    mode: InteriorMode = InteriorMode.STAY

    def __post_init__(self) -> None:
        _require(_is_text(self.key), "PieceSpec.key : texte non vide")
        _require(_is_text(self.label), "PieceSpec.label : texte non vide")
        _require(isinstance(self.block, PlacedBlock), "PieceSpec.block : PlacedBlock attendu")
        _require(_is_text(self.material_id), "PieceSpec.material_id : texte non vide")
        fixed_ok = isinstance(self.fixed, frozenset) and all(
            isinstance(e, Edge) for e in self.fixed
        )
        _require(fixed_ok, "PieceSpec.fixed : frozenset d'Edge attendu")
        _require(isinstance(self.mode, InteriorMode), "PieceSpec.mode : InteriorMode attendu")


@dataclass(frozen=True)
class JointSpec:
    """Assemblage de J3 entre deux pièces du gabarit (clés), paramètres déjà validés
    (``DowelParams``, ``RabbetParams``…)."""

    kind: JointKind
    host: str
    guest: str
    params: object

    def __post_init__(self) -> None:
        _require(isinstance(self.kind, JointKind), "JointSpec.kind : JointKind attendu")
        _require(_is_text(self.host) and _is_text(self.guest), "JointSpec : clés non vides")
        _require(self.host != self.guest, "JointSpec : deux pièces distinctes attendues")
        params_ok = is_dataclass(self.params) and not isinstance(self.params, type)
        _require(params_ok, "JointSpec.params : objet valeur attendu")


@dataclass(frozen=True)
class Layout:
    """Résultat d'un gabarit : l'ensemble (cotes, ``Origin``, libellé traduisible, nom du
    gabarit enregistré dans ``Template``), ses pièces et ses assemblages."""

    template: str
    label: str
    box: FurnitureBox
    origin: Vec3
    pieces: tuple[PieceSpec, ...]
    joints: tuple[JointSpec, ...] = ()

    def __post_init__(self) -> None:
        _require(_is_text(self.template) and _is_text(self.label), "Layout : textes non vides")
        _require(isinstance(self.box, FurnitureBox), "Layout.box : FurnitureBox attendu")
        _require(isinstance(self.origin, Vec3), "Layout.origin : Vec3 attendu")
        object.__setattr__(self, "pieces", tuple(self.pieces))
        object.__setattr__(self, "joints", tuple(self.joints))
        keys = [piece.key for piece in self.pieces]
        _require(bool(keys) and len(set(keys)) == len(keys), "Layout.pieces : clés uniques")
        known = set(keys)
        _require(
            all({joint.host, joint.guest} <= known for joint in self.joints),
            "Layout.joints : pièces du gabarit attendues",
        )

    def piece(self, key: str) -> PieceSpec:
        """Pièce de clé ``key`` (``KeyError`` si elle n'existe pas)."""
        return {piece.key: piece for piece in self.pieces}[key]

    def joints_of(self, kind: JointKind) -> Sequence[JointSpec]:
        """Assemblages d'un type, dans l'ordre du gabarit."""
        return [joint for joint in self.joints if joint.kind is kind]
