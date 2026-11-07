# SPDX-License-Identifier: LGPL-2.1-or-later
"""Classe de base pour les stratégies d'assemblage par mortaises plates.

Ce module contient la classe _SlotStrategy qui implémente la logique commune
aux faux tenons et biscuits.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    JointError,
    PlacedBlock,
    Prism,
    moved,
)
from freecad.menuiserie.core.joints._base import JointKind, JointPlan
from freecad.menuiserie.core.joints._profile import ContactFrame, contact_frame
from freecad.menuiserie.core.joints.dowels import MAX_DOWEL_COUNT, positions

from ._params import SlotParams, SlotSize, SlotValues, AUTO_SIZE
from ._utils import (
    _auto_count,
    _check_depths,
    _check_section,
    _check_spacing,
    _fits,
)


class _SlotStrategy(ABC):
    """Mortaises plates centrées sur le contact.

    Les sous-classes doivent fournir :
    - kind : Le type d'assemblage (JointKind)
    - sizes : Les tailles du commerce disponibles
    - custom_allowed : Si les tailles personnalisées sont autorisées
    - _solid() : La méthode de création des solides (Prism)

    La logique commune (résolution, plan, validation) est implémentée ici.
    """

    kind: ClassVar[JointKind]
    sizes: ClassVar[tuple[SlotSize, ...]]  # du plus petit au plus grand
    custom_allowed: ClassVar[bool]

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: SlotParams) -> SlotValues:
        """Calcule les valeurs effectives : taille, nombre et positions.

        Args:
            host: La pièce hôte
            guest: La pièce invitée
            params: Les paramètres de l'assemblage

        Returns:
            SlotValues: Les valeurs calculées (taille, nombre, positions, etc.)
        """
        frame = contact_frame(host, guest, end_only=False, face_ok=True)
        return self._checked(frame, params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: SlotParams) -> JointPlan:
        """Génère le plan d'usinage : mortaises dans les deux pièces et pièce rapportée.

        Args:
            host: La pièce hôte
            guest: La pièce invitée
            params: Les paramètres de l'assemblage

        Returns:
            JointPlan: Le plan contenant les mortaises (host_cuts, guest_cuts) et
            les pièces rapportées (inserts), exprimé dans le repère de l'hôte.
        """
        frame = contact_frame(host, guest, end_only=False, face_ok=True)
        values = self._checked(frame, params)
        host_cuts, guest_cuts, inserts = [], [], []

        for position in values.positions:
            # Mortaise dans l'hôte (repère de l'hôte)
            host_cuts.append(moved(self._solid(frame, values, position, "host"), frame.to_host))
            # Mortaise dans l'invité (repère de l'invité, puis converti)
            guest_cuts.append(self._solid(frame, values, position, "guest"))
            # Pièce rapportée (repère de l'invité, puis converti vers hôte)
            inserts.append(moved(self._solid(frame, values, position, "insert"), frame.to_host))

        plan = JointPlan(
            host_cuts=tuple(host_cuts),
            guest_cuts=tuple(guest_cuts),
            inserts=tuple(inserts),
        )
        return frame.bridge.plan(plan)

    @abstractmethod
    def _solid(
        self, frame: ContactFrame, values: SlotValues, position: float, role: str
    ) -> Prism:
        """Crée un solide (Prism) pour une mortaise ou une pièce rapportée.

        Args:
            frame: Le cadre de contact
            values: Les valeurs calculées
            position: Position le long du contact
            role: Rôle ('host', 'guest' ou 'insert')

        Returns:
            Prism: Le solide créé
        """
        raise NotImplementedError

    def _size(self, frame: ContactFrame, guest: PlacedBlock, params: SlotParams) -> SlotSize:
        """Détermine la taille à utiliser.

        Priorité :
        1. Taille personnalisée (si autorisée et demandée)
        2. Taille automatique (la plus grande qui tient)
        3. Taille sélectionnée dans la liste

        Args:
            frame: Le cadre de contact
            guest: La pièce invitée
            params: Les paramètres

        Returns:
            SlotSize: La taille déterminée

        Raises:
            JointError: Si la taille sélectionnée est inconnue
        """
        # Taille personnalisée si autorisée et demandée
        if self.custom_allowed and params.custom_size:
            if params.thickness and params.along and params.total_depth:
                # Toutes les dimensions sont fournies
                return SlotSize("", params.thickness, params.along, params.total_depth)
            # Compléter avec la plus grande taille qui tient
            size = self._largest_fitting(frame, guest, params)
            return SlotSize(
                "",
                params.thickness or size.thickness,
                params.along or size.along,
                params.total_depth or size.total_depth,
            )

        # Taille automatique
        if params.size == AUTO_SIZE:
            return self._largest_fitting(frame, guest, params)

        # Taille sélectionnée dans la liste
        for size in self.sizes:
            if size.id == params.size:
                return size

        # Taille inconnue
        text = {"size": params.size, "sizes": ", ".join(s.id for s in self.sizes)}
        from freecad.menuiserie.core.joints import JointError
        from ._params import UNKNOWN_SIZE
        raise JointError(UNKNOWN_SIZE, text)

    def _largest_fitting(
        self, frame: ContactFrame, guest: PlacedBlock, params: SlotParams
    ) -> SlotSize:
        """Trouve la plus grande taille du commerce qui tient dans les pièces.

        Args:
            frame: Le cadre de contact
            guest: La pièce invitée
            params: Les paramètres

        Returns:
            SlotSize: La plus grande taille qui tient

        Raises:
            JointError: Si aucune taille ne convient
        """
        # Épaisseur minimale de la plus fine des deux pièces
        shortest = min(frame.contact.host_depth, guest.local_box().size(frame.normal))
        # Épaisseur maximale de la pièce rapportée : au plus un tiers de l'épaisseur au contact
        slim = max(frame.contact_thickness / 3, self.sizes[0].thickness)

        # Filtrer les tailles qui tiennent
        fitting = [
            s
            for s in self.sizes
            if s.thickness <= slim + CONTACT_TOLERANCE_MM
            and _fits(frame, s, shortest, params.hole_clearance)
        ]

        if not fitting:
            from freecad.menuiserie.core.joints import JointError
            from ._params import NO_SIZE_FITS, mm_text
            text = {
                "contact_thickness": mm_text(frame.contact_thickness),
                "depth": mm_text(shortest),
            }
            raise JointError(NO_SIZE_FITS, text)

        # Retourner la plus grande
        return fitting[-1]

    def _checked(self, frame: ContactFrame, params: SlotParams) -> SlotValues:
        """Calcule et valide les valeurs effectives.

        Args:
            frame: Le cadre de contact
            params: Les paramètres

        Returns:
            SlotValues: Les valeurs validées
        """
        guest = frame.guest
        size = self._size(frame, guest, params)

        # Distance au bord (50mm par défaut, mais pas plus que la moitié du contact)
        edge = params.edge_distance or min(AUTO_EDGE_MM, frame.contact_width / 2)

        # Nombre de mortaises (automatique si 0)
        count = params.count or _auto_count(frame.contact_width, edge, size.along)

        custom = self.custom_allowed and params.custom_size

        values = SlotValues(
            thickness=size.thickness,
            along=size.along,
            total_depth=size.total_depth,
            count=count,
            edge_distance=edge,
            thickness_offset=params.thickness_offset,
            hole_clearance=params.hole_clearance,
            positions=positions(frame.contact_width, edge, count),
            size=size.id,
            custom_size=custom,
            custom_allowed=self.custom_allowed,
        )

        # Validations
        _check_section(frame, values)
        _check_depths(frame, guest, values)
        _check_spacing(frame, values)

        return values
