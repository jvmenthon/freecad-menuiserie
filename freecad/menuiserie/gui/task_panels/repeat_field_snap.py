# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aimant des flèches des champs « Pas » et « Longueur » du panneau « Répéter » (jv, 2026-11-16,
ADR 0058).

Une valeur obtenue par les flèches du champ, la molette ou les touches haut et bas qui tombe à
moins de 1 mm d'une valeur qui met une copie au ras d'une face voisine prend cette valeur. La
valeur « brute » (sans aimant) est gardée : le pas suivant repart d'elle (17,2 ; 18,2 ; 19,2 →
20 ; 21,2). Une valeur saisie au clavier n'est jamais modifiée.
"""

from __future__ import annotations

import contextlib
import math
from collections.abc import Callable, Iterable
from dataclasses import replace
from functools import partial
from typing import Any, Final

from PySide import QtCore

from freecad.menuiserie.core.repeat import RepeatAxis, RepeatParams
from freecad.menuiserie.gui.task_panels.base import Widget

__all__ = ["FieldSnap", "StepWatch", "with_field"]

_QEvent = QtCore.QEvent
_STEP_KEYS: Final = (
    QtCore.Qt.Key_Up,
    QtCore.Qt.Key_Down,
    QtCore.Qt.Key_PageUp,
    QtCore.Qt.Key_PageDown,
)
Snap = Callable[[float], "float | None"]
_EPSILON: Final = 1e-9


class StepWatch(QtCore.QObject):  # type: ignore[misc]  # PySide sans annotations
    """Filtre d'évènements des ``fields`` : dit si un champ change par ses flèches (clic tenu),
    la molette ou les touches haut et bas, et non par une saisie au clavier. Les champs sont
    reconnus par leur nom d'objet Qt : ``ValueError`` si un nom est vide ou en double."""

    def __init__(self, fields: Iterable[Widget]) -> None:
        super().__init__()
        self._fields = list(fields)
        names = [str(field.objectName()) for field in self._fields]
        if "" in names or len(set(names)) != len(names):
            raise ValueError(f"StepWatch : noms de champs vides ou en double : {names}")
        self._active: set[str] = set()
        for field in self._fields:
            field.installEventFilter(self)

    def eventFilter(self, watched: Any, event: Any) -> bool:  # nom imposé par Qt
        """Note le début (et la fin) d'un pas ; l'évènement est toujours rendu au champ."""
        kind = event.type()
        name = str(watched.objectName())
        if kind == _QEvent.MouseButtonPress:
            self._active.add(name)  # les flèches sont dans le champ, le texte dans son enfant
        elif kind in (_QEvent.MouseButtonRelease, _QEvent.FocusOut, _QEvent.Hide):
            self._active.discard(name)  # relâchement perdu (champ grisé, caché) : pas fini
        elif kind == _QEvent.Wheel or (kind == _QEvent.KeyPress and event.key() in _STEP_KEYS):
            self._active.add(name)
            QtCore.QTimer.singleShot(0, partial(self._active.discard, name))
        return False

    def stepping(self, field: Widget) -> bool:
        """Vrai si ``field`` change en ce moment par un pas (flèche, molette, touche)."""
        return str(field.objectName()) in self._active

    def close(self) -> None:
        """Filtres retirés des champs (fermeture du panneau)."""
        for field in self._fields:
            with contextlib.suppress(RuntimeError):  # champ déjà détruit avec le panneau
                field.removeEventFilter(self)
        self._fields.clear()
        self._active.clear()


def _bounds(field: Widget) -> tuple[float, float]:
    """Bornes ``minimum`` et ``maximum`` du champ (sans borne si le champ n'en dit rien)."""
    low, high = field.property("minimum"), field.property("maximum")
    return (
        -math.inf if low is None else float(low),
        math.inf if high is None else float(high),
    )


def _crossed(previous: float, raw: float, snapped: float) -> bool:
    """Vrai si ``snapped`` est franchie en allant de ``previous`` (exclue) à ``raw`` (incluse) :
    19,2 → 20,2 franchit 20, 18,2 → 19,2 non (jv : 17,2 ; 18,2 ; 19,2 → 20 ; 21,2)."""
    if raw >= previous:
        return previous + _EPSILON < snapped <= raw + _EPSILON
    return raw - _EPSILON <= snapped < previous - _EPSILON


class FieldSnap:
    """Valeur à garder dans un champ après un changement : aimantée pour un pas, inchangée pour une
    saisie ; retient la valeur brute et la dernière valeur affichée de chaque champ."""

    def __init__(self, fields: Iterable[Widget]) -> None:
        self._watch = StepWatch(fields)
        self._raw: dict[str, float] = {}
        self._shown: dict[str, float] = {}

    def note(self, field: Widget, value: float) -> None:
        """``value`` est écrite dans ``field`` par le panneau ou au clavier : elle devient la valeur
        brute."""
        name = str(field.objectName())
        self._raw[name] = self._shown[name] = value

    def target(self, field: Widget, value: float, snap: Snap) -> float:
        """Valeur à afficher dans ``field`` qui vient de passer à ``value`` : pour un pas, la valeur
        brute avancée du même pas, aimantée par ``snap`` si la valeur au ras est franchie par ce
        pas (entre la valeur affichée, exclue, et la valeur brute) ; sinon ``value``. Une erreur
        de ``snap`` laisse la valeur brute."""
        name = str(field.objectName())
        previous = self._shown.get(name)
        if previous is None or not self._watch.stepping(field):
            self.note(field, value)
            return value
        low, high = _bounds(field)
        raw = min(max(self._raw.get(name, previous) + (value - previous), low), high)
        try:
            snapped = snap(raw)
        except Exception:  # aimant facultatif : jamais d'exception dans la boucle Qt
            snapped = None
        kept = snapped is not None and low <= snapped <= high and _crossed(previous, raw, snapped)
        result = snapped if kept and snapped is not None else raw
        self._raw[name], self._shown[name] = raw, result
        return result

    def close(self) -> None:
        """Fin du panneau : filtres retirés."""
        self._watch.close()


def with_field(params: RepeatParams, axis: RepeatAxis, kind: str, value: float) -> RepeatParams:
    """``params`` dont le pas (``kind`` = ``step``) ou la longueur (``span``) de la ligne ``axis``
    vaut ``value`` (validé à nouveau : ``ValueError`` si refusé)."""
    lines = tuple(
        (replace(line, step=value) if kind == "step" else replace(line, span=value))
        if line.axis is axis
        else line
        for line in params.grid
    )
    return replace(params, grid=lines)
