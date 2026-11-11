# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pose et restauration de l'affichage temporaire des objets (ADR 0046).

Les propriétés du ViewObject (transparence, couleur diffuse) sont enregistrées dans le fichier :
tout aspect temporaire doit être rendu à toutes les sorties. :class:`DisplayLayers` est le seul
endroit qui les écrit pour cela ; il s'appuie sur ``core/display_layers`` (état d'origine retenu
une fois, calque le plus prioritaire affiché).

- FreeCAD enregistre une propriété du ViewObject modifiée dans la transaction ouverte et la rejoue
  à Ctrl+Z / Ctrl+Y. Un calque ``deferrable`` (la sélection) est écrit tout de suite dans la
  transaction d'un panneau de l'atelier (``controlled``), puis retiré par :meth:`withdraw` avant sa
  validation ; Ctrl+Z / Ctrl+Y rejouent alors une valeur du moment, corrigée par :meth:`undone`.
  Hors d'un panneau de l'atelier (``in_transaction``), la demande attend :meth:`flush`.
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
from functools import partial
from typing import Any, Final

from freecad.menuiserie.core.display_layers import LayerStack, Look
from freecad.menuiserie.gui import display_io as io
from freecad.menuiserie.gui.display_io import (
    GONE,
    AppObservers,
    Key,
    Observers,
    Original,
    PartObject,
    ViewObject,
    object_alive,
)
from freecad.menuiserie.gui.display_watcher import DocumentWatcher

__all__ = ["DISPLAY", "DisplayLayers", "Observers", "object_alive"]


class DisplayLayers:
    """Calques d'affichage des objets de tous les documents (voir ``core/display_layers``).
    Les dépendances de FreeCAD sont injectées (``alive``, ``observers``, ``in_transaction``,
    ``later``, ``report``) : les défauts conviennent aux tests sans FreeCAD."""

    def __init__(
        self,
        alive: Callable[[PartObject], bool] = object_alive,
        observers: Observers | None = None,
        in_transaction: Callable[[], bool] = io.never,
        controlled: Callable[[], bool] = io.never,
        later: Callable[[Callable[[], None]], None] = io.now,
        report: Callable[[str], None] = io.report,
    ) -> None:
        self._alive = alive
        self._observers = observers
        self._in_transaction = in_transaction
        self._controlled = controlled
        self._later = later
        self._report = report
        self._stack: LayerStack[Original] = LayerStack()
        self._objects: dict[Hashable, PartObject] = {}
        self._written: dict[Hashable, Look] = {}
        self._deferred: dict[Hashable, tuple[list[PartObject], Look]] = {}
        self._requests: dict[Hashable, tuple[list[PartObject], Look]] = {}  # calques différables
        self._in_tx: set[Hashable] = set()  # objets dont le calque est écrit dans la transaction
        self._tainted: dict[Key, Original] = {}  # écrits dans une transaction (Ctrl+Z/Y les rejoue)
        self._undeleted: dict[Key, Original] = {}  # origine des objets supprimés avec un calque
        self._watcher: DocumentWatcher | None = None

    def tracked(self) -> list[Hashable]:
        """Objets qui portent un calque (``(document, nom)``)."""
        return self._stack.tracked()

    def pending(self) -> list[Hashable]:
        """Propriétaires dont la demande attend la fin de la transaction ouverte."""
        return list(self._deferred)

    def look_of(self, obj: PartObject) -> Look | None:
        """Aspect affiché pour ``obj`` (``None`` : celui d'origine)."""
        return self._stack.effective(io.key(obj))

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
        :meth:`flush` ; dans la transaction d'un panneau de l'atelier le calque est écrit
        aussitôt (et retiré par :meth:`withdraw`)."""
        objs = list(objects)
        if deferrable and self._in_transaction():
            self._deferred[owner] = (objs, look)
            return
        self._deferred.pop(owner, None)
        in_task = deferrable and self._controlled()
        if deferrable:
            self._requests[owner] = (objs, look)
        wanted = {io.key(obj): obj for obj in objs if self._alive(obj)}
        if self._already_shown(owner, wanted, look):
            return  # rien à écrire
        fresh = {key for key in wanted if key not in self._stack}
        kept = self._drop_others(owner, wanted, in_task)
        for key, obj in wanted.items():
            self._put(key, obj, owner, look)
        if in_task:
            self._enter_task(fresh)
        if kept:
            self._deferred[owner] = (objs, look)
        self._watch()

    def _drop_others(self, owner: Hashable, wanted: dict[Key, PartObject], in_task: bool) -> bool:
        """Calque de ``owner`` retiré des objets qu'il n'a plus ; vrai si l'un d'eux, écrit avant
        la tâche, reste (son retrait serait enregistré dans la transaction : il attend la fin)."""
        kept = False
        for key in self._stack.keys_of(owner):
            if key in wanted:
                continue
            if in_task and key not in self._in_tx:
                kept = True
            else:
                self._drop(key, owner)
        return kept

    def _enter_task(self, fresh: set[Key]) -> None:
        """Objets écrits dans la transaction du panneau : retirés par :meth:`withdraw`, et corrigés
        par :meth:`undone` (FreeCAD rejoue leur valeur à Ctrl+Z et Ctrl+Y)."""
        self._in_tx |= fresh
        for key in fresh:
            if key in self._stack:
                self._tainted[key] = self._stack.original(key)

    def withdraw(self) -> bool:
        """Calques de sélection écrits dans la transaction du panneau retirés (l'origine revient,
        toujours dans cette transaction) juste avant sa validation ou son abandon ; la demande est
        rejouée par :meth:`flush` une fois la transaction close. Vrai si un calque a été retiré."""
        withdrawn = False
        for owner, request in list(self._requests.items()):
            keys = [key for key in self._stack.keys_of(owner) if key in self._in_tx]
            for key in keys:
                self._drop(key, owner)
            if keys:
                self._deferred[owner] = request
                withdrawn = True
        self._in_tx.clear()
        self._watch()
        return withdrawn

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

    def reapply(self, owner: Hashable) -> None:
        """Calques de ``owner`` réécrits sur leurs objets : une transaction abandonnée a pu
        rétablir l'affichage d'origine (ce qu'un tiers a changé devient l'origine)."""
        self._each(self._stack.keys_of(owner), self._reapply)

    def _reapply(self, key: Hashable) -> None:
        vobj = self._vobj(key)
        if vobj is not None:
            self._adopt(key, vobj)
            self._apply(key)

    def release(self, owner: Hashable) -> None:
        """Tous les calques de ``owner`` sont retirés ; l'origine revient sur les objets qui
        n'ont plus de calque. Sans effet sur un objet supprimé."""
        self._deferred.pop(owner, None)
        self._requests.pop(owner, None)
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
        self._requests.clear()
        self._in_tx.clear()
        self._tainted.clear()
        self._undeleted.clear()
        self._watch()

    def suspend(self, document: str) -> None:
        """Origine rendue aux objets de ``document`` (enregistrement), calques gardés."""
        self._each(self._document_keys(document), self._restore)

    def resume(self, document: str) -> None:
        """Calques reposés sur les objets de ``document`` après l'enregistrement."""
        self._each(self._document_keys(document), self._apply)

    def object_deleted(self, obj: PartObject) -> None:
        """Objet supprimé : son origine lui est rendue tant que son ViewObject existe (la
        transaction de suppression le garde ; Ctrl+Z le recréerait teinté), puis il est oublié."""
        key = io.key(obj)
        if key in self._stack:
            self._undeleted[key] = self._stack.original(key)
            self._each([key], self._restore_deleted(obj))
        self.forget(key)

    def undone(self, document: Any) -> None:
        """Après Ctrl+Z ou Ctrl+Y : la transaction a recréé l'objet supprimé avec l'affichage qu'il
        avait (teinté) ou rejoué une valeur d'affichage ; l'origine (ou le calque) est rendue hors
        transaction, une fois l'opération terminée."""
        self._later(partial(self._repair_undeleted, document))

    def _repair_undeleted(self, document: Any) -> None:
        try:
            name = document.Name
        except GONE:
            return  # document fermé entre-temps
        for key in [k for k in self._undeleted if k[0] == name]:
            vobj = getattr(document.getObject(key[1]), "ViewObject", None)
            if vobj is not None:  # sinon l'objet n'est pas (encore) recréé : l'origine reste
                original = self._undeleted.pop(key)
                self._each([key], partial(self._write_original, vobj, original))
        self._repair_tainted(document, name)
        self._watch()

    def _repair_tainted(self, document: Any, name: str) -> None:
        """Ctrl+Z ou Ctrl+Y a rejoué les valeurs enregistrées dans la transaction : le calque
        voulu (ou l'origine, sans calque) est réécrit, hors transaction."""
        for key in [k for k in self._tainted if k[0] == name]:
            vobj = getattr(document.getObject(key[1]), "ViewObject", None)
            if vobj is None:
                continue
            if key in self._stack:
                self._written.pop(key, None)
                self._each([key], self._apply)
            else:
                self._each([key], partial(self._write_original, vobj, self._tainted[key]))

    @staticmethod
    def _write_original(vobj: ViewObject, original: Original, _unused: Hashable) -> None:
        io.show(vobj, original.transparency, original.diffuse)

    def _restore_deleted(self, obj: PartObject) -> Callable[[Hashable], None]:
        def restore(key: Hashable) -> None:
            try:
                vobj = getattr(obj, "ViewObject", None)
                if vobj is not None:
                    self._adopt(key, vobj)
                    self._restore_with(key, vobj, self._stack.original(key))
            except GONE:
                return  # ViewObject déjà détruit : rien à rendre

        return restore

    def forget(self, key: Hashable) -> None:
        """Objet supprimé : rien à rétablir."""
        self._stack.forget(key)
        self._objects.pop(key, None)
        self._written.pop(key, None)
        self._in_tx.discard(key)
        self._tainted.pop(key, None)  # type: ignore[call-overload]
        self._later(self._watch)

    def forget_document(self, document: str) -> None:
        """Document fermé : rien à rétablir."""
        for undeleted in [k for k in self._undeleted if k[0] == document]:
            del self._undeleted[undeleted]
        for tainted in [k for k in self._tainted if k[0] == document]:
            del self._tainted[tainted]
        for key in self._document_keys(document):
            self.forget(key)
        self._watch()

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
        wanted = bool(len(self._stack) or self._undeleted or self._tainted)
        if wanted and self._watcher is None:
            self._watcher = DocumentWatcher(self)
            self._observers.add(self._watcher)
        elif not wanted and self._watcher is not None:
            watcher, self._watcher = self._watcher, None
            self._observers.remove(watcher)

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
            original = self._stack.original(key) if known else io.read(vobj)
            self._objects[key] = obj
            self._stack.put(key, owner, look, original)
            self._apply(key)
        except GONE:
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
        except GONE:
            self.forget(key)

    def _apply(self, key: Hashable) -> None:
        """Aspect effectif écrit sur l'objet (le dernier calque posé, le plus prioritaire)."""
        vobj, look = self._vobj(key), self._stack.effective(key)
        if vobj is None or look is None:
            return
        original = self._stack.original(key)
        io.show(vobj, look.transparency, io.target_diffuse(look, original))
        self._written[key] = look

    def _restore(self, key: Hashable) -> None:
        """Origine écrite sans retirer les calques (enregistrement)."""
        try:
            vobj = self._vobj(key)
            if vobj is not None:
                self._adopt(key, vobj)
                self._restore_with(key, vobj, self._stack.original(key))
        except GONE:
            self.forget(key)

    def _restore_with(self, key: Hashable, vobj: ViewObject | None, original: Original) -> None:
        if vobj is not None:
            io.show(vobj, original.transparency, original.diffuse)
        self._written.pop(key, None)

    def _adopt(self, key: Hashable, vobj: ViewObject) -> None:
        """Propriété modifiée par un tiers depuis notre dernière écriture : elle devient
        l'origine (jamais écrasée à la restauration)."""
        look = self._written.get(key)
        if look is None:
            return
        self._stack.rebase(key, io.adopted(self._stack.original(key), io.read(vobj), look))


# Cache explicite et réinitialisable (``release_all``) : les calques de l'édition et de la
# sélection doivent partager le « avant » de chaque objet.
DISPLAY: Final = DisplayLayers(
    observers=AppObservers(),
    in_transaction=io.in_foreign_transaction,
    controlled=io.in_controlled_transaction,
    later=io.later,
)
