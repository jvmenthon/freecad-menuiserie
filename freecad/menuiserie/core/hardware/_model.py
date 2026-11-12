# SPDX-License-Identifier: LGPL-2.1-or-later
"""Références et catalogue de quincaillerie : objets valeur immuables (ADR 0033)."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from freecad.menuiserie.core._validation import FrozenMapping, nfc

__all__ = ["Catalog", "HardwareItem", "UnknownHardwareError"]


class UnknownHardwareError(KeyError):
    """Identifiant absent du catalogue."""


@dataclass(frozen=True)
class HardwareItem:
    """Une référence du commerce : fabricant, référence, famille générique et cotes (mm).

    ``manufacturer`` et ``reference`` sont vides pour une pièce générique sans marque.
    """

    id: str
    family: str
    label: str
    params: FrozenMapping
    source: str
    manufacturer: str = ""
    reference: str = ""
    distributor_reference: str = ""

    def param(self, name: str) -> float:
        """Cote ``name`` en mm ; ``KeyError`` si la famille ne la porte pas."""
        return float(self.params[name])

    @property
    def title(self) -> str:
        """Libellé complet : « Blum 71B3550 — … » ou le libellé seul sans fabricant."""
        brand = " ".join(part for part in (self.manufacturer, self.reference) if part)
        return f"{brand} — {self.label}" if brand else self.label

    @property
    def purchase_reference(self) -> str:
        """Référence à commander : celle du fabricant, ou l'identifiant du catalogue sans marque."""
        return self.reference or self.id

    def matches(self, text: str) -> bool:
        """Vrai si chaque mot de ``text`` figure (sans casse) dans le titre, l'id ou la famille."""
        haystack = nfc(f"{self.title} {self.id} {self.family}").casefold()
        return all(word in haystack for word in nfc(text).casefold().split())


@dataclass(frozen=True)
class Catalog:
    """Références uniques par ``id``, dans l'ordre de lecture."""

    items: tuple[HardwareItem, ...] = ()

    def __post_init__(self) -> None:
        ids = [item.id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("identifiants de quincaillerie en double")

    def __iter__(self) -> Iterator[HardwareItem]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def get(self, item_id: str) -> HardwareItem:
        """Référence ``item_id`` ; :class:`UnknownHardwareError` si elle est absente."""
        for item in self.items:
            if item.id == item_id:
                return item
        raise UnknownHardwareError(item_id)

    def find(self, item_id: str) -> HardwareItem | None:
        """Référence ``item_id`` ou ``None``."""
        return next((item for item in self.items if item.id == item_id), None)

    def of_family(self, family: str) -> tuple[HardwareItem, ...]:
        """Références de la famille ``family``."""
        return tuple(item for item in self.items if item.family == family)

    def search(self, text: str, family: str | None = None) -> tuple[HardwareItem, ...]:
        """Références dont le titre contient tous les mots de ``text``, filtrées par famille."""
        found: Sequence[HardwareItem] = self.items if family is None else self.of_family(family)
        return tuple(item for item in found if item.matches(text))
