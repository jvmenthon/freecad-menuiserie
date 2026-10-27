# SPDX-License-Identifier: LGPL-2.1-or-later
"""Erreur d'un recalcul (recette de jv, assemblage défait par un glissement) : FreeCAD imprime la
trace de toute exception levée par ``execute()`` avec ses causes ; le message d'un assemblage
impossible ne doit donc y figurer qu'une fois (pas de chaînage gabarit puis texte traduit)."""

from __future__ import annotations

import traceback
from collections.abc import Iterator
from types import ModuleType

import pytest

from freecad.menuiserie.core.i18n import TemplatedError
from tests.unit.aides_freecad import simulated_freecad

TEMPLATE = "Queue d'aronde : la pièce à griffes doit arriver à fleur de la face extérieure."


@pytest.fixture
def i18n(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import i18n as module

        yield module


def printed(error: BaseException) -> str:
    """Texte de la trace comme FreeCAD l'imprime (causes et contextes compris)."""
    return "".join(traceback.format_exception(error))


def test_le_message_d_un_assemblage_impossible_n_est_imprime_qu_une_fois(i18n: ModuleType) -> None:
    with pytest.raises(ValueError, match="fleur") as raised, i18n.translated_errors():
        raise TemplatedError(TEMPLATE, {})
    assert raised.value.__cause__ is None and raised.value.__suppress_context__
    assert printed(raised.value).count(TEMPLATE) == 1


def test_les_autres_erreurs_passent_sans_changement(i18n: ModuleType) -> None:
    with pytest.raises(KeyError), i18n.translated_errors():
        raise KeyError("x")
