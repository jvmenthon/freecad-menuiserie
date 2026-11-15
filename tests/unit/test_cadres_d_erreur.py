# SPDX-License-Identifier: LGPL-2.1-or-later
"""La dernière erreur affichée ne garde pas en vie le panneau qui l'a provoquée."""

from __future__ import annotations

import sys
import weakref

import pytest

from freecad.menuiserie.core.error_frames import release_last_error_frames


class Panel:
    """Double d'un panneau : son signal lance un recalcul qui échoue."""

    def on_changed(self) -> BaseException:
        return self._recompute()

    def _recompute(self) -> BaseException:
        try:
            _execute()
        except ValueError as error:  # FreeCAD affiche l'erreur du recalcul et continue
            return error
        raise AssertionError


def _execute() -> None:
    raise ValueError("Queues trop étroites")


def _shown_error(monkeypatch: pytest.MonkeyPatch) -> weakref.ref[Panel]:
    """Erreur levée sous le signal d'un panneau puis affichée (``sys.last_traceback``), comme
    après ``PyErr_Print`` ; le panneau est ensuite fermé (plus aucune autre référence)."""
    panel = Panel()
    error = panel.on_changed()
    monkeypatch.setattr(sys, "last_traceback", error.__traceback__, raising=False)
    return weakref.ref(panel)


def test_l_erreur_affichee_garde_le_panneau_en_vie(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le défaut corrigé : sans rien faire, la trace retient le panneau par ses cadres."""
    assert _shown_error(monkeypatch)() is not None


def test_les_cadres_vides_liberent_le_panneau(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = _shown_error(monkeypatch)
    release_last_error_frames()
    assert panel() is None


def test_sans_erreur_affichee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "last_traceback", raising=False)
    release_last_error_frames()
    monkeypatch.setattr(sys, "last_traceback", None, raising=False)
    release_last_error_frames()
