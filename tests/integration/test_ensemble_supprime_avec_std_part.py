# SPDX-License-Identifier: LGPL-2.1-or-later
"""Std Part d'ensemble supprimé en gardant son contenu : l'objet ensemble est supprimé aussi
(ADR 0061), après la suppression de FreeCAD, dans sa propre transaction."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.test_ensemble_std_part import geometry

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
watch = pytest.importorskip("freecad.menuiserie.features.std_part_watch")


class Observer:
    """Comme l'observateur de l'atelier actif : ensembles notés, supprimés après."""

    def __init__(self) -> None:
        self.left: list[tuple[str, tuple[str, ...]]] = []

    def slotDeletedObject(self, obj: Any) -> None:
        left = watch.left_furnitures(obj)
        watch.std_part_deleted(obj)
        if left:
            self.left.append((obj.Document.Name, left))

    def finish(self) -> list[str]:
        """Ce que fait la minuterie de l'interface une fois la suppression finie."""
        messages: list[str] = []
        for document, names in self.left:
            messages += watch.remove_left_furnitures(App.getDocument(document), names)
        self.left.clear()
        return messages


@pytest.fixture
def observer() -> Any:
    found = Observer()
    App.addDocumentObserver(found)
    yield found
    App.removeDocumentObserver(found)


def delete_std_part(doc: Any, furniture: Any) -> None:
    doc.openTransaction("Supprimer")
    doc.removeObject(container.std_part_of(furniture).Name)
    doc.commitTransaction()


def test_ensemble_supprime_les_pieces_restent(bureau: Any, observer: Observer) -> None:
    furniture, doc = bureau.furniture, bureau.doc
    doc.UndoMode = 1
    assert api.move_furniture(furniture, (120.0, -40.0, 10.0))
    doc.recompute()
    before = geometry(doc)
    name = furniture.Name
    delete_std_part(doc, furniture)
    assert doc.getObject(name) is not None  # rien de supprimé pendant la suppression
    observer.finish()
    assert doc.getObject(name) is None
    assert geometry(doc) == before
    assert stale_or_invalid(doc) == []
    assert doc.UndoNames[0] == "Supprimer l'ensemble"
    doc.undo()  # l'ensemble revient, sans son Std Part
    doc.recompute()
    assert doc.getObject(name) is not None and geometry(doc) == before
    doc.undo()  # puis le Std Part
    doc.recompute()
    assert container.std_part_of(doc.getObject(name)) is not None
    assert geometry(doc) == before
    assert observer.left == []  # l'annulation ne programme aucune suppression


def test_contenu_supprime_ensemble_deja_parti(bureau: Any, observer: Observer) -> None:
    furniture, doc = bureau.furniture, bureau.doc
    part = container.std_part_of(furniture)
    names = [obj.Name for obj in part.Group]
    doc.openTransaction("Supprimer")
    for item in [*names, part.Name]:
        if doc.getObject(item) is not None:
            doc.removeObject(item)
    doc.commitTransaction()
    assert observer.finish() == []  # ensemble déjà supprimé : ignoré


def test_sous_ensemble_garde_le_sien(document: Any, observer: Observer) -> None:
    from tests.integration.bureau import build_parts
    from tests.integration.test_ensemble_membres import caisson

    desk = build_parts(document)
    sub, _parts = caisson(document)
    furniture, _ = api.make_furniture(
        [desk.parts["P"], desk.parts["JG"], desk.parts["JD"], sub], "Bureau"
    )
    document.recompute()
    before = geometry(document)
    name = furniture.Name
    delete_std_part(document, furniture)
    observer.finish()
    assert document.getObject(name) is None
    assert api.furniture_of(sub) is None and container.std_part_of(sub) is not None
    assert geometry(document) == before
    assert stale_or_invalid(document) == []
