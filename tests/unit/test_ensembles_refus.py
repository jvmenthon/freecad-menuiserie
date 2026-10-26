# SPDX-License-Identifier: LGPL-2.1-or-later
"""Refus de cote ou d'épaisseur tels que les panneaux les montrent (ADR 0019, critères G2 et
G3), sans FreeCAD : texte traduit et pièces verrouillées à proposer de déverrouiller."""

from __future__ import annotations

from collections.abc import Iterator
from types import ModuleType, SimpleNamespace

import pytest

from freecad.menuiserie.core.furniture import BlockedRowError, FurnitureError
from tests.unit.aides_freecad import simulated_freecad


@pytest.fixture
def locks(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """``features.furniture_locks`` importé dans le bloc qui isole ``features/``."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import furniture_locks

        yield furniture_locks


def pieces(*names: str) -> tuple[SimpleNamespace, ...]:
    return tuple(SimpleNamespace(Name=name) for name in names)


def test_refus_d_une_rangee_bloquee_propose_les_pieces_verrouillees(locks: ModuleType) -> None:
    from freecad.menuiserie.features.furniture_bindings import LockedPiecesError

    voile, joue = pieces("V", "JG")
    error = LockedPiecesError("Impossible de changer la largeur.", (voile,), (joue, voile))
    assert locks.refusal_of(error) == ("Impossible de changer la largeur.", (voile,))


def test_refus_d_une_rangee_bloquee_sans_piece_verrouillee(locks: ModuleType) -> None:
    """Deux épaisseurs qui remplissent la cote : rien à déverrouiller, le refus seul."""
    error = BlockedRowError(
        "Rangée « {members} » bloquée.", {"members": "A, B"}, locked=(), members=("A", "B")
    )
    assert locks.refusal_of(error) == ("Rangée « A, B » bloquée.", ())


def test_refus_d_un_controle_de_core(locks: ModuleType) -> None:
    error = FurnitureError("« {label} » deviendrait trop petite.", {"label": "Voile"})
    assert locks.refusal_of(error) == ("« Voile » deviendrait trop petite.", ())


def test_refus_deja_traduit(locks: ModuleType) -> None:
    assert locks.refusal_of(ValueError("Épaisseur invalide.")) == ("Épaisseur invalide.", ())
