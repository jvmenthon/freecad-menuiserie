# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sélection par ensemble dans la vue 3D (ADR 0047).

- clic simple sur une pièce membre d'un ensemble : l'ensemble de plus haut niveau est sélectionné
  (la sélection ne change pas si l'élément déjà sélectionné contient la pièce) ;
- double-clic sur une pièce : descente d'un niveau (ensemble, sous-ensemble, pièce) ;
- double-clic dans le vide : remontée d'un niveau.

Ctrl+clic, Maj+clic, les clics dans l'arbre et tout ce qui se passe pendant qu'un panneau de tâche
est ouvert gardent le comportement natif de FreeCAD. Le filtre est posé sur l'application **tant
que l'atelier est actif** (ADR 0007), après celui du double-clic (ADR 0018) : Qt appelle d'abord le
dernier posé, qui décide de la descente avant l'ouverture du panneau. Le clic simple n'est jamais
consommé : la sélection native a lieu, puis elle est remplacée (``QTimer`` à zéro). Rien n'est
écrit dans le document.
"""

from __future__ import annotations

import traceback
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.selection_chain import click_target, double_click_target, up_target
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.selection_chain import chain_of, normalized
from freecad.menuiserie.gui.double_click import Installation, is_viewport_3d, view_point
from freecad.menuiserie.gui.drag.events import current_session

__all__ = ["descend_at", "install", "installed", "uninstall"]

View = Any
CLICK_SLOP_PX: Final = 4  # au-delà, c'est un déplacement de la vue (rotation, panoramique)


def picked_object(view: View, point: tuple[int, int]) -> DocumentObject | None:
    """Objet sous le point ``point`` de ``view`` (pixels de FreeCAD), ``None`` dans le vide."""
    if not hasattr(view, "getObjectInfo"):
        return None
    info = view.getObjectInfo(point)
    if not info:
        return None
    doc = App.listDocuments().get(info.get("Document", ""))
    return doc.getObject(info.get("Object", "")) if doc is not None else None


def selected_object() -> DocumentObject | None:
    """Objet de la sélection quand il n'y en a qu'un seul (normalisé), sinon ``None``."""
    selection = Gui.Selection.getSelection()
    return normalized(selection[0]) if len(selection) == 1 else None


def select(obj: DocumentObject) -> None:
    """Remplace la sélection par ``obj``, avec son chemin dans les Std Part qui le contiennent."""
    groups: list[DocumentObject] = []
    parent = obj.getParentGeoFeatureGroup()
    while parent is not None and parent not in groups:
        groups.insert(0, parent)
        parent = parent.getParentGeoFeatureGroup()
    Gui.Selection.clearSelection()
    if not groups:
        Gui.Selection.addSelection(obj.Document.Name, obj.Name)
        return
    path = ".".join([*(group.Name for group in groups[1:]), obj.Name]) + "."
    Gui.Selection.addSelection(obj.Document.Name, groups[0].Name, path)


def _trace(message: str) -> None:
    """Trace dans la vue rapport (messages « journal », à activer dans ses options)."""
    App.Console.PrintLog(f"Menuiserie, sélection 3D : {message}\n")


def _label(obj: DocumentObject | None) -> str:
    return "rien" if obj is None else f"{obj.Name} ({obj.Label})"


def _names(chain: list[DocumentObject]) -> list[str]:
    return [item.Name for item in chain]


def _by_name(chain: list[DocumentObject], name: str | None) -> DocumentObject | None:
    return next((item for item in chain if item.Name == name), None)


def retarget_click(picked: DocumentObject, before: DocumentObject | None) -> None:
    """Après le clic simple sur ``picked`` (``before`` : sélection d'avant le clic) : l'élément de
    la chaîne voulu remplace la sélection native, sauf si c'est la pièce, déjà sélectionnée."""
    chain = chain_of(picked)
    name = click_target(_names(chain), None if before is None else before.Name)
    target = _by_name(chain, name)
    _trace(
        f"clic sur {_label(picked)}, avant {_label(before)}, chaîne {_names(chain)}, "
        f"sélection native {[o.Name for o in Gui.Selection.getSelection()]}, choix {name}"
    )
    if target is not None and target is not chain[-1]:
        select(target)


def descend_at(view: View, point: tuple[int, int], before: DocumentObject | None = None) -> bool:
    """Double-clic au point ``point`` de ``view`` : descente ou remontée d'un niveau. Vrai
    (évènement consommé) si la sélection a changé ; faux si la pièce est déjà sélectionnée (son
    panneau s'ouvre ailleurs), si l'objet n'est pas membre d'un ensemble ou si rien ne change.
    ``before`` : sélection d'avant le premier clic, repli dans le vide (FreeCAD la vide)."""
    picked = picked_object(view, point)
    current = selected_object() or before
    _trace(f"double-clic sur {_label(picked)}, sélection {_label(current)}")
    if picked is None:
        chain = [] if current is None else chain_of(current)
        parent = _by_name(chain, up_target(_names(chain)))
        if parent is None:
            return False
        select(parent)
        return True
    chain = chain_of(picked)
    name = double_click_target(_names(chain), None if current is None else current.Name)
    target = _by_name(chain, name)
    _trace(f"double-clic : chaîne {_names(chain)}, choix {name}")
    if target is None:
        return False
    if target is chain[-1]:
        target = picked  # la pièce visible (usinée), comme la sélection native
    select(target)
    return True


class _ClickFilter(QtCore.QObject):  # type: ignore[misc]
    """Filtre d'application : clic gauche simple et double-clic dans la zone d'affichage d'une vue
    3D. Tout autre évènement est rendu aussitôt (une comparaison de type)."""

    def __init__(self) -> None:
        super().__init__()
        self._press: tuple[QtCore.QPointF, DocumentObject | None, DocumentObject | None] | None = (
            None
        )
        self._before: DocumentObject | None = None
        self._before_ms = 0

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        kind = event.type()
        if kind not in (
            QtCore.QEvent.MouseButtonPress,
            QtCore.QEvent.MouseButtonRelease,
            QtCore.QEvent.MouseButtonDblClick,
        ):
            return False
        try:
            return self._mouse(kind, watched, event)
        except RuntimeError:  # widget Qt détruit : clic ignoré
            return False
        except Exception:  # pylint: disable=broad-exception-caught
            App.Console.PrintError(traceback.format_exc())
            return False

    def _mouse(self, kind: QtCore.QEvent.Type, watched: QtCore.QObject, event: Any) -> bool:
        if event.button() != QtCore.Qt.LeftButton or not is_viewport_3d(watched):
            return False
        if Gui.Control.activeDialog():  # panneau de tâche ouvert : sélection native
            return False
        position = event.position() if hasattr(event, "position") else event.pos()  # Qt 6/5
        point = view_point(watched, position.x(), position.y())
        if kind == QtCore.QEvent.MouseButtonDblClick:
            return self._double_click(point, event)
        if kind == QtCore.QEvent.MouseButtonPress:
            self._pressed(point, event, position)
        else:
            self._released(position)
        return False

    def _double_click(self, point: tuple[int, int], event: Any) -> bool:
        if event.modifiers() != QtCore.Qt.NoModifier:
            return False
        recent = QtCore.QDateTime.currentMSecsSinceEpoch() - self._before_ms
        before = self._before if recent < 2 * QtGui.QApplication.doubleClickInterval() else None
        return descend_at(Gui.activeView(), point, before)

    def _pressed(self, point: tuple[int, int], event: Any, position: QtCore.QPointF) -> None:
        self._press = None
        if event.modifiers() != QtCore.Qt.NoModifier:
            return
        self._before = selected_object()
        self._before_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        picked = picked_object(Gui.activeView(), point)
        handle = self._on_handle(point)
        _trace(f"appui sur {_label(picked)}, avant {_label(self._before)}, poignée {handle}")
        if picked is not None and not handle:
            self._press = (QtCore.QPointF(position), picked, self._before)

    @staticmethod
    def _on_handle(point: tuple[int, int]) -> bool:
        """Vrai si le point est sur une flèche, poignée ou anneau : le glissement a la priorité."""
        session = current_session()
        return session is not None and session.active and session.target_at(point) is not None

    def _released(self, position: QtCore.QPointF) -> None:
        pressed, self._press = self._press, None
        if pressed is None:
            return
        start, picked, before = pressed
        moved = position - start
        if abs(moved.x()) > CLICK_SLOP_PX or abs(moved.y()) > CLICK_SLOP_PX:
            return
        QtCore.QTimer.singleShot(0, lambda: _retarget_later(picked, before))


def _retarget_later(picked: DocumentObject, before: DocumentObject | None) -> None:
    """Après la sélection native du clic ; sans effet si un panneau s'est ouvert entre-temps ou
    si l'objet a été supprimé."""
    try:
        if not Gui.Control.activeDialog() and picked.Document is not None:
            retarget_click(picked, before)
    except Exception:  # pylint: disable=broad-exception-caught
        App.Console.PrintError(traceback.format_exc())


_INSTALLATION: Final = Installation(_ClickFilter)


def install() -> None:
    """Pose le filtre (atelier activé, après celui du double-clic)."""
    _INSTALLATION.install()


def installed() -> bool:
    """Vrai si le filtre est posé (atelier actif)."""
    return _INSTALLATION.filter is not None


def uninstall() -> None:
    """Retire le filtre (atelier désactivé)."""
    _INSTALLATION.uninstall()
