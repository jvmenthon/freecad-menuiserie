# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pose et restauration de l'affichage temporaire des objets (ADR 0046).

Les propriétés du ViewObject (transparence, couleur diffuse) sont enregistrées dans le fichier :
tout aspect temporaire doit être rendu à toutes les sorties. :class:`DisplayLayers` est le seul
endroit qui les écrit pour cela ; il s'appuie sur ``core/display_layers`` (état d'origine retenu
une fois, calque le plus prioritaire affiché). Il est écrit hors transaction
(``task_panels.active.quiet_view_writes``), rend l'origine avant un enregistrement du document et
oublie les objets supprimés ou le document fermé. Une propriété que quelqu'un d'autre a modifiée
pendant le calque devient la nouvelle origine : elle n'est jamais écrasée par une ancienne valeur.
Les observateurs de document ne sont posés que tant qu'un calque existe (ADR 0007).
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Final, Protocol

from freecad.menuiserie.core.display_layers import LayerStack, Look, Rgb
from freecad.menuiserie.gui.task_panels.active import quiet_view_writes

__all__ = ["DISPLAY", "DisplayLayers", "Observers", "object_alive"]

ViewObject = Any
PartObject = Any  # objet FreeCAD (ce module n'importe pas ``features`` : il reste léger)
_GONE: Final = (ReferenceError, RuntimeError, TypeError)  # objet supprimé ou document fermé


@dataclass(frozen=True)
class Original:
    """Affichage d'origine d'un objet : transparence et couleur diffuse de chaque matériau."""

    transparency: int
    diffuse: tuple[Rgb, ...]


_COLOR_SCALE: Final = 255


class Observers(Protocol):
    """Pose et retrait d'un observateur de document (``App.addDocumentObserver``)."""

    def add(self, watcher: object) -> None:
        """Pose ``watcher``."""

    def remove(self, watcher: object) -> None:
        """Retire ``watcher``."""


class _AppObservers:
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
    except _GONE:
        return False


def _key(obj: PartObject) -> str:
    """Clé ``Document/Nom`` de ``obj`` (le nom seul si l'objet n'a pas de document)."""
    document = getattr(getattr(obj, "Document", None), "Name", "")
    return f"{document}/{obj.Name}"


def _to_bytes(color: Iterable[float]) -> Rgb:
    red, green, blue = (round(c * _COLOR_SCALE) for c in tuple(color)[:3])
    return red, green, blue


def _from_bytes(color: Rgb) -> tuple[float, ...]:
    return tuple(c / _COLOR_SCALE for c in color)


def _read(vobj: ViewObject) -> Original:
    materials = getattr(vobj, "ShapeAppearance", ())
    return Original(int(vobj.Transparency), tuple(_to_bytes(m.DiffuseColor) for m in materials))


def _target_diffuse(look: Look, original: Original) -> tuple[Rgb, ...]:
    if look.tint is None:
        return original.diffuse
    return tuple(look.tint for _ in original.diffuse)


def _write_diffuse(vobj: ViewObject, wanted: tuple[Rgb, ...]) -> None:
    """Couleur diffuse de chaque matériau (transparence inchangée) ; rien d'écrit si égale."""
    materials = list(getattr(vobj, "ShapeAppearance", ()))
    if (
        len(materials) != len(wanted)
        or tuple(_to_bytes(m.DiffuseColor) for m in materials) == wanted
    ):
        return
    for material, rgb in zip(materials, wanted, strict=True):
        material.DiffuseColor = _from_bytes(rgb) + tuple(material.DiffuseColor)[3:]
    vobj.ShapeAppearance = materials


def _show(vobj: ViewObject, transparency: int, diffuse: tuple[Rgb, ...]) -> None:
    _write_diffuse(vobj, diffuse)
    if int(vobj.Transparency) != transparency:
        vobj.Transparency = transparency


class _Watcher:
    """Observateur de document posé tant qu'un calque existe."""

    def __init__(self, layers: DisplayLayers) -> None:
        self._layers = layers

    def slotStartSaveDocument(self, doc: Any, _filename: str) -> None:
        """Avant l'enregistrement : l'affichage d'origine est rendu, rien d'éphémère n'est écrit."""
        self._layers.suspend(doc.Name)

    def slotFinishSaveDocument(self, doc: Any, _filename: str) -> None:
        """Après l'enregistrement : les calques sont reposés."""
        self._layers.resume(doc.Name)

    def slotDeletedObject(self, obj: Any) -> None:
        self._layers.forget(_key(obj))

    def slotDeletedDocument(self, doc: Any) -> None:
        self._layers.forget_document(doc.Name)


class DisplayLayers:
    """Calques d'affichage des objets de tous les documents (voir ``core/display_layers``)."""

    def __init__(
        self,
        alive: Callable[[PartObject], bool] = object_alive,
        observers: Observers | None = None,
        quiet: Callable[[], AbstractContextManager[None]] = quiet_view_writes,
    ) -> None:
        self._alive = alive
        self._observers = observers
        self._quiet = quiet
        self._stack: LayerStack[Original] = LayerStack()
        self._objects: dict[str, PartObject] = {}
        self._written: dict[str, Look] = {}
        self._watcher: _Watcher | None = None

    def tracked(self) -> list[str]:
        """Objets qui portent un calque (``Document/Nom``)."""
        return self._stack.tracked()

    def look_of(self, obj: PartObject) -> Look | None:
        """Aspect affiché pour ``obj`` (``None`` : celui d'origine)."""
        return self._stack.effective(_key(obj))

    # --- Calques --------------------------------------------------------------------------

    def show(self, owner: Hashable, objects: Iterable[PartObject], look: Look) -> None:
        """Le calque ``look`` de ``owner`` est posé sur ``objects``, retiré de tout autre objet."""
        wanted = {_key(obj): obj for obj in objects if self._alive(obj)}
        if self._already_shown(owner, wanted, look):
            return  # rien à écrire : ni contournement de transaction, ni écriture
        with self._quiet():
            for key in self._stack.keys_of(owner):
                if key not in wanted:
                    self._drop(key, owner)
            for key, obj in wanted.items():
                self._put(key, obj, owner, look)
        self._watch()

    def _already_shown(self, owner: Hashable, wanted: dict[str, PartObject], look: Look) -> bool:
        """Vrai si ``owner`` a déjà ``look`` sur exactement ces objets (les mêmes du document)."""
        if sorted(self._stack.keys_of(owner)) != sorted(wanted):
            return False
        return all(
            self._stack.layer(key, owner) == look and self._objects.get(key) == obj
            for key, obj in wanted.items()
        )

    def release(self, owner: Hashable) -> None:
        """Tous les calques de ``owner`` sont retirés ; l'origine revient sur les objets qui
        n'ont plus de calque. Sans effet sur un objet supprimé."""
        with self._quiet():
            for key in self._stack.keys_of(owner):
                self._drop(key, owner)
        self._watch()

    def release_all(self) -> None:
        """Tous les calques de tous les propriétaires sont retirés."""
        with self._quiet():
            for key in self._stack.tracked():
                self._restore(key)
                self._stack.forget(key)
                self._objects.pop(key, None)
        self._watch()

    # --- Observateur de document ----------------------------------------------------------

    def suspend(self, document: str) -> None:
        """Origine rendue aux objets de ``document`` (enregistrement), calques gardés."""
        with self._quiet():
            for key in self._document_keys(document):
                self._restore(key)

    def resume(self, document: str) -> None:
        """Calques reposés sur les objets de ``document`` après l'enregistrement."""
        with self._quiet():
            for key in self._document_keys(document):
                self._apply(key)

    def forget(self, key: str) -> None:
        """Objet supprimé : rien à rétablir."""
        self._stack.forget(key)
        self._objects.pop(key, None)
        self._written.pop(key, None)
        self._watch()

    def forget_document(self, document: str) -> None:
        """Document fermé : rien à rétablir."""
        for key in self._document_keys(document):
            self.forget(key)

    def _document_keys(self, document: str) -> list[str]:
        return [key for key in self._stack.tracked() if key.startswith(f"{document}/")]

    def _watch(self) -> None:
        """Observateur posé tant qu'il reste un calque, retiré ensuite."""
        if self._observers is None:
            return
        if len(self._stack) and self._watcher is None:
            self._watcher = _Watcher(self)
            self._observers.add(self._watcher)
        elif not len(self._stack) and self._watcher is not None:
            watcher, self._watcher = self._watcher, None
            self._observers.remove(watcher)

    # --- Écriture -------------------------------------------------------------------------

    def _vobj(self, key: str) -> ViewObject | None:
        obj = self._objects.get(key)
        if obj is None or not self._alive(obj):
            return None
        return getattr(obj, "ViewObject", None)

    def _put(self, key: str, obj: PartObject, owner: Hashable, look: Look) -> None:
        vobj = getattr(obj, "ViewObject", None)
        if vobj is None or not hasattr(vobj, "Transparency"):
            return  # pas d'interface, ou objet sans transparence (Distance…) : rien à afficher
        try:
            known = key in self._stack
            if known:
                self._adopt(key, vobj)
            original = self._stack.original(key) if known else _read(vobj)
            self._objects[key] = obj
            self._stack.put(key, owner, look, original)
            self._apply(key)
        except _GONE:
            self.forget(key)

    def _drop(self, key: str, owner: Hashable) -> None:
        try:
            vobj = self._vobj(key)
            if vobj is not None:
                self._adopt(key, vobj)
            update = self._stack.drop(key, owner)
            if update is None:
                return
            if update.look is None:
                self._restore_with(key, vobj, update.original)
                self._objects.pop(key, None)
                self._written.pop(key, None)
            else:
                self._apply(key)
        except _GONE:
            self.forget(key)

    def _apply(self, key: str) -> None:
        """Aspect effectif écrit sur l'objet (le dernier calque posé, le plus prioritaire)."""
        vobj, look = self._vobj(key), self._stack.effective(key)
        if vobj is None or look is None:
            return
        original = self._stack.original(key)
        _show(vobj, look.transparency, _target_diffuse(look, original))
        self._written[key] = look

    def _restore(self, key: str) -> None:
        """Origine écrite sans retirer les calques (enregistrement)."""
        try:
            vobj = self._vobj(key)
            if vobj is not None:
                self._adopt(key, vobj)
                self._restore_with(key, vobj, self._stack.original(key))
        except _GONE:
            self.forget(key)

    def _restore_with(self, key: str, vobj: ViewObject | None, original: Original) -> None:
        if vobj is not None:
            _show(vobj, original.transparency, original.diffuse)
        self._written.pop(key, None)

    def _adopt(self, key: str, vobj: ViewObject) -> None:
        """Propriété modifiée par un tiers depuis notre dernière écriture : elle devient
        l'origine (jamais écrasée à la restauration)."""
        look = self._written.get(key)
        if look is None:
            return
        original, current = self._stack.original(key), _read(vobj)
        transparency = original.transparency
        if current.transparency != look.transparency:
            transparency = current.transparency
        diffuse = original.diffuse
        if current.diffuse != _target_diffuse(look, original):
            diffuse = current.diffuse
        self._stack.rebase(key, Original(transparency, diffuse))


# Cache explicite et réinitialisable (``release_all``) : les calques de l'édition et de la
# sélection doivent partager le « avant » de chaque objet.
DISPLAY: Final = DisplayLayers(observers=_AppObservers())
