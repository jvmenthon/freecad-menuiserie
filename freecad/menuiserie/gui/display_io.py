# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture et écriture de l'affichage d'un objet, et dépendances FreeCAD de ``display_layers``.

Ce module regroupe ce qui touche directement FreeCAD (importé à l'usage : il reste importable hors
de FreeCAD) et l'écriture des propriétés du ViewObject (transparence, couleur diffuse).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol

from freecad.menuiserie.core.colors import Rgb, from_bytes, to_bytes
from freecad.menuiserie.core.display_layers import Look

__all__ = [
    "GONE",
    "AppObservers",
    "Key",
    "Observers",
    "Original",
    "PartObject",
    "ViewObject",
    "in_controlled_transaction",
    "in_foreign_transaction",
    "key",
    "later",
    "never",
    "now",
    "object_alive",
    "read",
    "report",
    "show",
    "target_diffuse",
]

ViewObject = Any
PartObject = Any  # objet FreeCAD (ce module n'importe pas ``features`` : il reste léger)
Key = tuple[str, str]  # (nom du document, nom de l'objet)
GONE: Final = (ReferenceError, RuntimeError, TypeError)  # objet supprimé ou document fermé


@dataclass(frozen=True)
class Original:
    """Affichage d'origine d'un objet : transparence et couleur diffuse de chaque matériau."""

    transparency: int
    diffuse: tuple[Rgb, ...]


class Observers(Protocol):
    """Pose et retrait d'un observateur de document (``App.addDocumentObserver``)."""

    def add(self, watcher: object) -> None:
        """Pose ``watcher``."""

    def remove(self, watcher: object) -> None:
        """Retire ``watcher``."""


class AppObservers:
    """Observateurs de l'application FreeCAD (importée à l'usage : ce module reste importable
    hors de FreeCAD)."""

    def add(self, watcher: object) -> None:
        import FreeCAD as App

        App.addDocumentObserver(watcher)

    def remove(self, watcher: object) -> None:
        import FreeCAD as App

        App.removeDocumentObserver(watcher)


def object_alive(obj: PartObject) -> bool:
    """Vrai si ``obj`` existe encore dans un document ouvert (faux pour un objet supprimé ou
    dont le document est fermé)."""
    import FreeCAD as App

    try:
        doc = obj.Document
        return bool(doc.Name in App.listDocuments() and doc.getObject(obj.Name) == obj)
    except GONE:
        return False


def in_controlled_transaction() -> bool:
    """Vrai si la transaction ouverte est celle d'un panneau de tâche de l'atelier, qui retire
    l'affichage temporaire avant de la solder."""
    import FreeCAD as App

    from freecad.menuiserie.gui.task_panels import active

    return App.getActiveTransaction() is not None and active.current() is not None


def in_foreign_transaction() -> bool:
    """Vrai si une transaction est ouverte sans que l'atelier la maîtrise (autre atelier,
    commande) : rien d'éphémère n'y est écrit."""
    import FreeCAD as App

    return App.getActiveTransaction() is not None and not in_controlled_transaction()


def later(callback: Callable[[], None]) -> None:
    from PySide import QtCore

    QtCore.QTimer.singleShot(0, callback)


def report(text: str) -> None:
    import FreeCAD as App

    App.Console.PrintError(text)


def never() -> bool:
    return False


def now(callback: Callable[[], None]) -> None:
    callback()


def key(obj: PartObject) -> Key:
    """Clé ``(document, nom)`` de ``obj`` (document vide si l'objet n'en a pas)."""
    return str(getattr(getattr(obj, "Document", None), "Name", "")), str(obj.Name)


def read(vobj: ViewObject) -> Original:
    materials = getattr(vobj, "ShapeAppearance", ())
    return Original(int(vobj.Transparency), tuple(to_bytes(m.DiffuseColor) for m in materials))


def target_diffuse(look: Look, original: Original) -> tuple[Rgb, ...]:
    if look.tint is None:
        return original.diffuse
    return tuple(look.tint for _ in original.diffuse)


def write_diffuse(vobj: ViewObject, wanted: tuple[Rgb, ...]) -> None:
    """Couleur diffuse de chaque matériau (transparence inchangée) ; rien d'écrit si égale."""
    materials = list(getattr(vobj, "ShapeAppearance", ()))
    if (
        len(materials) != len(wanted)
        or tuple(to_bytes(m.DiffuseColor) for m in materials) == wanted
    ):
        return
    for material, rgb in zip(materials, wanted, strict=True):
        material.DiffuseColor = from_bytes(rgb) + tuple(material.DiffuseColor)[3:]
    vobj.ShapeAppearance = materials


def show(vobj: ViewObject, transparency: int, diffuse: tuple[Rgb, ...]) -> None:
    write_diffuse(vobj, diffuse)
    if int(vobj.Transparency) != transparency:
        vobj.Transparency = transparency
