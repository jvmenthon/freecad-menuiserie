# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pose et restauration de l'affichage temporaire des objets (ADR 0046).

Les propriétés du ViewObject (transparence, couleur diffuse) sont enregistrées dans le fichier :
tout aspect temporaire doit être rendu à toutes les sorties. :class:`DisplayLayers` est le seul
endroit qui les écrit pour cela ; il s'appuie sur ``core/display_layers`` (état d'origine retenu
une fois, calque le plus prioritaire affiché).

- FreeCAD enregistre une propriété du ViewObject modifiée dans la transaction ouverte : un calque
  ``deferrable`` (la sélection de ligne) n'est donc ni posé ni retiré tant qu'une transaction est
  ouverte ; la demande est mémorisée et jouée par :meth:`DisplayLayers.flush` à la fin de la
  transaction (fermeture d'une tâche) ou à la demande suivante.
- L'origine est rendue avant un enregistrement du document (chaque objet isolément : une erreur
  est écrite dans le rapport sans interrompre les autres) et les calques reposés après.
- Un objet supprimé reçoit son origine avant d'être oublié (la transaction de suppression
  conserve son ViewObject : Ctrl+Z ne doit pas le recréer teinté) ; un document fermé est oublié.
- Une propriété que quelqu'un d'autre a modifiée pendant le calque devient la nouvelle origine :
  elle n'est jamais écrasée par une ancienne valeur.
- Les observateurs de document ne sont posés que tant qu'un calque existe (ADR 0007) ; leur retrait
  est différé hors de la notification en cours.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Any, Final, Protocol

from freecad.menuiserie.core.colors import Rgb, from_bytes, to_bytes
from freecad.menuiserie.core.display_layers import LayerStack, Look

__all__ = ["DISPLAY", "DisplayLayers", "Observers", "object_alive"]

ViewObject = Any
PartObject = Any  # objet FreeCAD (ce module n'importe pas ``features`` : il reste léger)
Key = tuple[str, str]  # (nom du document, nom de l'objet)
_GONE: Final = (ReferenceError, RuntimeError, TypeError)  # objet supprimé ou document fermé


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


def _in_transaction() -> bool:
    import FreeCAD as App

    return App.getActiveTransaction() is not None


def _later(callback: Callable[[], None]) -> None:
    from PySide import QtCore

    QtCore.QTimer.singleShot(0, callback)


def _report(text: str) -> None:
    import FreeCAD as App

    App.Console.PrintError(text)


def _never() -> bool:
    return False


def _now(callback: Callable[[], None]) -> None:
    callback()


def _key(obj: PartObject) -> Key:
    """Clé ``(document, nom)`` de ``obj`` (document vide si l'objet n'en a pas)."""
    return str(getattr(getattr(obj, "Document", None), "Name", "")), str(obj.Name)


def _read(vobj: ViewObject) -> Original:
    materials = getattr(vobj, "ShapeAppearance", ())
    return Original(int(vobj.Transparency), tuple(to_bytes(m.DiffuseColor) for m in materials))


def _target_diffuse(look: Look, original: Original) -> tuple[Rgb, ...]:
    if look.tint is None:
        return original.diffuse
    return tuple(look.tint for _ in original.diffuse)


def _write_diffuse(vobj: ViewObject, wanted: tuple[Rgb, ...]) -> None:
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
        self._layers.object_deleted(obj)

    def slotDeletedDocument(self, doc: Any) -> None:
        self._layers.forget_document(doc.Name)


class DisplayLayers:
    """Calques d'affichage des objets de tous les documents (voir ``core/display_layers``).
    Les dépendances de FreeCAD sont injectées (``alive``, ``observers``, ``in_transaction``,
    ``later``, ``report``) : les défauts conviennent aux tests sans FreeCAD."""

    def __init__(
        self,
        alive: Callable[[PartObject], bool] = object_alive,
        observers: Observers | None = None,
        in_transaction: Callable[[], bool] = _never,
        later: Callable[[Callable[[], None]], None] = _now,
        report: Callable[[str], None] = _report,
    ) -> None:
        self._alive = alive
        self._observers = observers
        self._in_transaction = in_transaction
        self._later = later
        self._report = report
        self._stack: LayerStack[Original] = LayerStack()
        self._objects: dict[Hashable, PartObject] = {}
        self._written: dict[Hashable, Look] = {}
        self._deferred: dict[Hashable, tuple[list[PartObject], Look]] = {}
        self._watcher: _Watcher | None = None

    def tracked(self) -> list[Hashable]:
        """Objets qui portent un calque (``(document, nom)``)."""
        return self._stack.tracked()

    def pending(self) -> list[Hashable]:
        """Propriétaires dont la demande attend la fin de la transaction ouverte."""
        return list(self._deferred)

    def look_of(self, obj: PartObject) -> Look | None:
        """Aspect affiché pour ``obj`` (``None`` : celui d'origine)."""
        return self._stack.effective(_key(obj))

    # --- Calques --------------------------------------------------------------------------

    def show(
        self,
        owner: Hashable,
        objects: Iterable[PartObject],
        look: Look,
        *,
        deferrable: bool = False,
    ) -> None:
        """Le calque ``look`` de ``owner`` est posé sur ``objects``, retiré de tout autre objet.
        ``deferrable`` : tant qu'une transaction est ouverte, la demande est mémorisée (écrire une
        propriété du ViewObject la ferait enregistrer dans la transaction) et jouée par
        :meth:`flush`."""
        objs = list(objects)
        if deferrable and self._in_transaction():
            self._deferred[owner] = (objs, look)
            return
        self._deferred.pop(owner, None)
        wanted = {_key(obj): obj for obj in objs if self._alive(obj)}
        if self._already_shown(owner, wanted, look):
            return  # rien à écrire
        for key in self._stack.keys_of(owner):
            if key not in wanted:
                self._drop(key, owner)
        for key, obj in wanted.items():
            self._put(key, obj, owner, look)
        self._watch()

    def flush(self) -> None:
        """Demandes différées jouées si plus aucune transaction n'est ouverte."""
        if self._in_transaction():
            return
        for owner, (objs, look) in list(self._deferred.items()):
            self.show(owner, objs, look)

    def _already_shown(self, owner: Hashable, wanted: dict[Key, PartObject], look: Look) -> bool:
        """Vrai si ``owner`` a déjà ``look`` écrit sur exactement ces objets (les mêmes du
        document) ; faux après un enregistrement qui a rendu l'origine sans être reposé."""
        if set(self._stack.keys_of(owner)) != set(wanted):
            return False
        return all(
            self._stack.layer(key, owner) == look
            and self._objects.get(key) == obj
            and key in self._written
            for key, obj in wanted.items()
        )

    def release(self, owner: Hashable) -> None:
        """Tous les calques de ``owner`` sont retirés ; l'origine revient sur les objets qui
        n'ont plus de calque. Sans effet sur un objet supprimé."""
        self._deferred.pop(owner, None)
        for key in self._stack.keys_of(owner):
            self._drop(key, owner)
        self._watch()

    def release_all(self) -> None:
        """Tous les calques de tous les propriétaires sont retirés."""
        for key in self._stack.tracked():
            self._restore(key)
            self._stack.forget(key)
        self._objects.clear()
        self._written.clear()
        self._deferred.clear()
        self._watch()

    # --- Observateur de document ----------------------------------------------------------

    def suspend(self, document: str) -> None:
        """Origine rendue aux objets de ``document`` (enregistrement), calques gardés."""
        self._each(self._document_keys(document), self._restore)

    def resume(self, document: str) -> None:
        """Calques reposés sur les objets de ``document`` après l'enregistrement."""
        self._each(self._document_keys(document), self._apply)

    def object_deleted(self, obj: PartObject) -> None:
        """Objet supprimé : son origine lui est rendue tant que son ViewObject existe (la
        transaction de suppression le garde ; Ctrl+Z le recréerait teinté), puis il est oublié."""
        key = _key(obj)
        if key in self._stack:
            self._each([key], self._restore_deleted(obj))
        self.forget(key)

    def _restore_deleted(self, obj: PartObject) -> Callable[[Hashable], None]:
        def restore(key: Hashable) -> None:
            try:
                vobj = getattr(obj, "ViewObject", None)
                if vobj is not None:
                    self._adopt(key, vobj)
                    self._restore_with(key, vobj, self._stack.original(key))
            except _GONE:
                return  # ViewObject déjà détruit : rien à rendre

        return restore

    def forget(self, key: Hashable) -> None:
        """Objet supprimé : rien à rétablir."""
        self._stack.forget(key)
        self._objects.pop(key, None)
        self._written.pop(key, None)
        self._later(self._watch)

    def forget_document(self, document: str) -> None:
        """Document fermé : rien à rétablir."""
        for key in self._document_keys(document):
            self.forget(key)

    def _each(self, keys: list[Hashable], action: Callable[[Hashable], None]) -> None:
        """``action`` sur chaque clé ; une erreur est écrite dans le rapport sans interrompre les
        autres (sans quoi FreeCAD enregistrerait la teinte restante)."""
        for key in keys:
            try:
                action(key)
            except Exception:  # pylint: disable=broad-exception-caught
                self._report(traceback.format_exc())

    def _document_keys(self, document: str) -> list[Hashable]:
        return [key for key in self._stack.tracked() if key[0] == document]  # type: ignore[index]

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

    def _vobj(self, key: Hashable) -> ViewObject | None:
        obj = self._objects.get(key)
        if obj is None or not self._alive(obj):
            return None
        return getattr(obj, "ViewObject", None)

    def _put(self, key: Key, obj: PartObject, owner: Hashable, look: Look) -> None:
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

    def _drop(self, key: Hashable, owner: Hashable) -> None:
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

    def _apply(self, key: Hashable) -> None:
        """Aspect effectif écrit sur l'objet (le dernier calque posé, le plus prioritaire)."""
        vobj, look = self._vobj(key), self._stack.effective(key)
        if vobj is None or look is None:
            return
        original = self._stack.original(key)
        _show(vobj, look.transparency, _target_diffuse(look, original))
        self._written[key] = look

    def _restore(self, key: Hashable) -> None:
        """Origine écrite sans retirer les calques (enregistrement)."""
        try:
            vobj = self._vobj(key)
            if vobj is not None:
                self._adopt(key, vobj)
                self._restore_with(key, vobj, self._stack.original(key))
        except _GONE:
            self.forget(key)

    def _restore_with(self, key: Hashable, vobj: ViewObject | None, original: Original) -> None:
        if vobj is not None:
            _show(vobj, original.transparency, original.diffuse)
        self._written.pop(key, None)

    def _adopt(self, key: Hashable, vobj: ViewObject) -> None:
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
DISPLAY: Final = DisplayLayers(
    observers=_AppObservers(), in_transaction=_in_transaction, later=_later
)
