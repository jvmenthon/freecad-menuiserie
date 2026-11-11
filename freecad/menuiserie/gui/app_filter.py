# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pose et retrait d'un filtre d'évènements Qt sur l'application, tant que l'atelier est actif
(ADR 0007, § 3 : rien de permanent). Commun au double-clic (ADR 0018) et à la sélection par
ensemble (ADR 0048)."""

from __future__ import annotations

from collections.abc import Callable

from PySide import QtCore, QtGui

__all__ = ["Installation"]


class Installation:
    """Filtre d'application unique, posé pendant que l'atelier est actif (``factory`` le crée)."""

    def __init__(self, factory: Callable[[], QtCore.QObject]) -> None:
        self._factory = factory
        self.filter: QtCore.QObject | None = None

    def install(self) -> None:
        application = QtGui.QApplication.instance()
        if self.filter is not None or application is None:
            return
        self.filter = self._factory()
        application.installEventFilter(self.filter)

    def uninstall(self) -> None:
        application = QtGui.QApplication.instance()
        if self.filter is None:
            return
        if application is not None:
            application.removeEventFilter(self.filter)
        self.filter = None
