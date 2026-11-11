# SPDX-License-Identifier: LGPL-2.1-or-later
"""Observateur de document des calques d'affichage (ADR 0046) : enregistrement, suppression,
annulation et rétablissement. Posé par ``DisplayLayers`` tant qu'un calque existe (ADR 0007)."""

from __future__ import annotations

from typing import Any

__all__ = ["DocumentWatcher"]


class DocumentWatcher:
    """Relaie les notifications de document à ``layers`` (un ``DisplayLayers``)."""

    def __init__(self, layers: Any) -> None:
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

    def slotUndoDocument(self, doc: Any) -> None:
        """Après Ctrl+Z : un objet supprimé puis recréé retrouve son affichage d'origine ; une
        valeur d'affichage rejouée est corrigée."""
        self._layers.undone(doc)

    def slotRedoDocument(self, doc: Any) -> None:
        """Après Ctrl+Y : une valeur d'affichage rejouée par la transaction est corrigée."""
        self._layers.undone(doc)

    def slotCreatedObject(self, obj: Any) -> None:
        """Un objet recréé par l'annulation d'une suppression retrouve son affichage d'origine."""
        self._layers.undone(obj.Document)
