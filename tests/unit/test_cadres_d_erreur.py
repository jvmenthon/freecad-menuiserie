# SPDX-License-Identifier: LGPL-2.1-or-later
"""La dernière erreur affichée ne garde pas en vie le panneau qui l'a provoquée."""

from __future__ import annotations

import sys
import weakref
from collections.abc import Iterator

import pytest

from freecad.menuiserie.gui.error_frames import release_last_error_frames


class Panel:
    """Double d'un panneau : son signal lance un recalcul qui échoue."""

    def on_changed(self, chained: bool = False) -> BaseException:
        return self._recompute(chained)

    def _recompute(self, chained: bool) -> BaseException:
        try:
            _execute()
        except ValueError as error:  # FreeCAD affiche l'erreur du recalcul et continue
            return _translated(error) if chained else error
        raise AssertionError


def _execute() -> None:
    raise ValueError("Queues trop étroites")


def _translated(cause: ValueError) -> BaseException:
    """Erreur relevée « from » une autre, hors des cadres du panneau : seule la cause les tient."""
    try:
        raise RuntimeError("traduite") from cause
    except RuntimeError as error:
        return error


@pytest.fixture(autouse=True)
def _no_last_error(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("last_exc", "last_value", "last_traceback"):
        monkeypatch.setattr(sys, name, None, raising=False)


def _shown(monkeypatch: pytest.MonkeyPatch, attribute: str, chained: bool) -> weakref.ref[Panel]:
    """Erreur levée sous le signal d'un panneau puis affichée, comme après ``PyErr_Print`` ; le
    panneau est ensuite fermé (plus aucune autre référence)."""
    panel = Panel()
    error = panel.on_changed(chained)
    value = error.__traceback__ if attribute == "last_traceback" else error
    monkeypatch.setattr(sys, attribute, value, raising=False)
    return weakref.ref(panel)


def test_l_erreur_affichee_garde_le_panneau_en_vie(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le défaut corrigé : sans rien faire, la trace retient le panneau par ses cadres."""
    assert _shown(monkeypatch, "last_traceback", chained=False)() is not None


@pytest.mark.parametrize("attribute", ["last_traceback", "last_value", "last_exc"])
@pytest.mark.parametrize("chained", [False, True], ids=["simple", "chaînée"])
def test_les_cadres_vides_liberent_le_panneau(
    monkeypatch: pytest.MonkeyPatch, attribute: str, chained: bool
) -> None:
    if chained and attribute == "last_traceback":
        pytest.skip("la trace seule ne donne pas l'exception chaînée")
    panel = _shown(monkeypatch, attribute, chained)
    release_last_error_frames()
    assert panel() is None


def test_sans_erreur_affichee(monkeypatch: pytest.MonkeyPatch) -> None:
    release_last_error_frames()
    for name in ("last_exc", "last_value", "last_traceback"):
        monkeypatch.delattr(sys, name, raising=False)
    release_last_error_frames()


def test_cadre_en_cours_d_execution_intact(monkeypatch: pytest.MonkeyPatch) -> None:
    """L'erreur affichée vient d'un appel encore en cours : ses variables locales restent."""
    kept = "locale"
    try:
        _execute()
    except ValueError as error:
        monkeypatch.setattr(sys, "last_exc", error, raising=False)
        release_last_error_frames()
    assert kept == "locale"


def test_generateur_suspendu_non_ferme(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un générateur suspendu dans la pile de l'erreur n'est pas fermé (``clear`` le fermerait)."""
    closed: list[bool] = []

    def steps() -> Iterator[BaseException]:
        try:
            try:
                _execute()
            except ValueError as error:
                yield error
            yield RuntimeError("suite")
        finally:
            closed.append(True)

    generator = steps()
    monkeypatch.setattr(sys, "last_exc", next(generator), raising=False)
    release_last_error_frames()
    assert not closed
    assert isinstance(next(generator), RuntimeError)
