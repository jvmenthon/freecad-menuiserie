# SPDX-License-Identifier: LGPL-2.1-or-later
"""Calques d'affichage (ADR 0046) : transparence d'édition et de sélection qui coexistent.

Logique pure (``core/display_layers``) et pose sur des doubles de ViewObject
(``gui/display_layers``, importable sans FreeCAD : les dépendances y sont injectées).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from freecad.menuiserie.core.display_layers import (
    EDIT_LOOK,
    EDIT_TRANSPARENCY,
    SELECTION_LOOK,
    SELECTION_TINT,
    SELECTION_TRANSPARENCY,
    LayerStack,
    Look,
)
from freecad.menuiserie.gui.display_layers import DisplayLayers

EDIT, SELECTION = "edit", "selection"
WOOD = (184, 135, 90)


class Material:
    def __init__(self, rgb: tuple[int, int, int]) -> None:
        self.DiffuseColor = (*(c / 255 for c in rgb), 1.0)


class FakeView:
    def __init__(self, transparency: int = 0, rgb: tuple[int, int, int] = WOOD) -> None:
        self.Transparency = transparency
        self.ShapeAppearance = [Material(rgb)]
        self.writes = 0

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"Transparency", "ShapeAppearance"} and name in self.__dict__:
            self.__dict__["writes"] += 1
        super().__setattr__(name, value)

    @property
    def rgb(self) -> tuple[int, ...]:
        return tuple(round(c * 255) for c in self.ShapeAppearance[0].DiffuseColor[:3])


class Piece:
    def __init__(self, name: str, transparency: int = 0) -> None:
        self.Name = name
        self.ViewObject = FakeView(transparency)

    @property
    def view(self) -> FakeView:
        return self.ViewObject


class Observers:
    def __init__(self) -> None:
        self.posed: list[object] = []

    def add(self, watcher: object) -> None:
        self.posed.append(watcher)

    def remove(self, watcher: object) -> None:
        self.posed.remove(watcher)


@contextmanager
def no_transaction() -> Iterator[None]:
    yield


def layers(dead: list[Any] | None = None) -> tuple[DisplayLayers, Observers]:
    gone = dead if dead is not None else []
    observers = Observers()
    return DisplayLayers(lambda obj: obj not in gone, observers, no_transaction), observers


# --- Logique pure -----------------------------------------------------------------------


def test_teintes_et_niveaux_distincts_et_nommes() -> None:
    assert EDIT_LOOK.tint is None  # l'édition ne teinte pas
    assert SELECTION_LOOK.tint == SELECTION_TINT
    assert EDIT_LOOK.transparency == EDIT_TRANSPARENCY == 60
    assert SELECTION_LOOK.transparency == SELECTION_TRANSPARENCY
    assert EDIT_LOOK.priority > SELECTION_LOOK.priority


def test_pile_origine_retenue_une_fois_et_rendue_au_dernier_calque() -> None:
    stack: LayerStack[str] = LayerStack()
    assert stack.put("a", SELECTION, SELECTION_LOOK, "origine").look == SELECTION_LOOK
    assert stack.put("a", EDIT, EDIT_LOOK, "autre").original == "origine"  # pas réécrite
    assert stack.effective("a") == EDIT_LOOK  # l'édition prime
    assert stack.drop("a", EDIT) is not None
    assert stack.effective("a") == SELECTION_LOOK
    last = stack.drop("a", SELECTION)
    assert last is not None
    assert (last.look, last.original) == (None, "origine")
    assert "a" not in stack
    assert stack.drop("a", SELECTION) is None


def test_a_priorite_egale_le_calque_le_plus_recent_gagne() -> None:
    stack: LayerStack[int] = LayerStack()
    first, second = Look(10, None, 1), Look(20, None, 1)
    stack.put("a", "x", first, 0)
    stack.put("a", "y", second, 0)
    assert stack.effective("a") == second
    stack.put("a", "x", first, 0)  # re-posé : redevient le plus récent
    assert stack.effective("a") == first


# --- Pose sur des ViewObject ------------------------------------------------------------


def test_selection_transparente_et_teintee_puis_origine_rendue() -> None:
    display, _ = layers()
    piece = Piece("P", 10)
    display.show(SELECTION, [piece], SELECTION_LOOK)
    assert piece.view.Transparency == SELECTION_TRANSPARENCY
    assert piece.view.rgb == SELECTION_TINT
    display.release(SELECTION)
    assert (piece.view.Transparency, piece.view.rgb) == (10, WOOD)


def test_edition_et_selection_sur_le_meme_objet_l_edition_prime() -> None:
    display, _ = layers()
    piece = Piece("P", 10)
    display.show(SELECTION, [piece], SELECTION_LOOK)
    display.show(EDIT, [piece], EDIT_LOOK)
    assert (piece.view.Transparency, piece.view.rgb) == (EDIT_TRANSPARENCY, WOOD)
    display.release(EDIT)  # l'édition finie : la sélection reste visible
    assert (piece.view.Transparency, piece.view.rgb) == (SELECTION_TRANSPARENCY, SELECTION_TINT)
    display.release(SELECTION)
    assert (piece.view.Transparency, piece.view.rgb) == (10, WOOD)  # origine, pas l'édition


def test_selection_posee_pendant_l_edition_puis_retiree_avant_elle() -> None:
    display, _ = layers()
    piece = Piece("P", 10)
    display.show(EDIT, [piece], EDIT_LOOK)
    display.show(SELECTION, [piece], SELECTION_LOOK)
    assert piece.view.Transparency == EDIT_TRANSPARENCY
    display.release(SELECTION)
    assert piece.view.Transparency == EDIT_TRANSPARENCY  # l'édition n'est pas restaurée
    display.release(EDIT)
    assert (piece.view.Transparency, piece.view.rgb) == (10, WOOD)


def test_deux_mecanismes_sur_des_objets_differents_sont_independants() -> None:
    display, _ = layers()
    edited, selected = Piece("E", 5), Piece("S", 15)
    display.show(EDIT, [edited], EDIT_LOOK)
    display.show(SELECTION, [selected], SELECTION_LOOK)
    display.release(EDIT)
    assert edited.view.Transparency == 5
    assert selected.view.Transparency == SELECTION_TRANSPARENCY
    display.release(SELECTION)
    assert selected.view.Transparency == 15


def test_changer_la_selection_retire_l_ancien_objet() -> None:
    display, _ = layers()
    first, second = Piece("A", 1), Piece("B", 2)
    display.show(SELECTION, [first], SELECTION_LOOK)
    display.show(SELECTION, [second], SELECTION_LOOK)
    assert first.view.Transparency == 1
    assert second.view.Transparency == SELECTION_TRANSPARENCY


def test_meme_calque_deja_pose_n_ecrit_rien() -> None:
    display, _ = layers()
    piece = Piece("P")
    display.show(SELECTION, [piece], SELECTION_LOOK)
    writes = piece.view.writes
    display.show(SELECTION, [piece], SELECTION_LOOK)
    assert piece.view.writes == writes


def test_valeur_changee_par_un_tiers_devient_l_origine() -> None:
    display, _ = layers()
    piece = Piece("P", 10)
    display.show(SELECTION, [piece], SELECTION_LOOK)
    piece.view.Transparency = 77
    material = piece.view.ShapeAppearance[0]
    material.DiffuseColor = (0.2, 0.4, 0.6, 1.0)
    display.release(SELECTION)
    assert piece.view.Transparency == 77
    assert piece.view.rgb == (51, 102, 153)


def test_objet_supprime_ou_sans_interface_ne_leve_rien() -> None:
    dead: list[Any] = []
    display, _ = layers(dead)
    piece, headless = Piece("P"), Piece("H")
    del headless.ViewObject
    display.show(SELECTION, [piece, headless], SELECTION_LOOK)
    dead.append(piece)
    display.release(SELECTION)  # supprimé : rien n'est écrit sur lui
    assert piece.view.Transparency == SELECTION_TRANSPARENCY
    assert display.tracked() == []


def test_objet_sans_transparence_est_ignore() -> None:
    display, _ = layers()
    distance = Piece("D")
    del distance.view.__dict__["Transparency"]
    display.show(SELECTION, [distance], SELECTION_LOOK)
    assert display.tracked() == []


class DeletedView(FakeView):
    def __setattr__(self, name: str, value: Any) -> None:
        if name == "Transparency" and "Transparency" in self.__dict__ and value == 10:
            raise ReferenceError("Cannot access attribute of deleted object")
        super().__setattr__(name, value)


def test_objet_qui_disparait_pendant_la_restauration() -> None:
    display, _ = layers()
    piece = Piece("P", 10)
    piece.ViewObject = DeletedView(10)
    display.show(SELECTION, [piece], SELECTION_LOOK)
    display.release(SELECTION)  # TypeError / ReferenceError avalés
    assert display.tracked() == []


def test_enregistrement_rend_l_origine_puis_repose_les_calques() -> None:
    display, observers = layers()
    piece = Piece("P", 10)
    display.show(SELECTION, [piece], SELECTION_LOOK)
    (watcher,) = observers.posed
    document = type("Doc", (), {"Name": ""})()
    watcher.slotStartSaveDocument(document, "f.FCStd")  # type: ignore[attr-defined]
    assert (piece.view.Transparency, piece.view.rgb) == (10, WOOD)  # rien d'éphémère enregistré
    watcher.slotFinishSaveDocument(document, "f.FCStd")  # type: ignore[attr-defined]
    assert piece.view.Transparency == SELECTION_TRANSPARENCY
    assert piece.view.rgb == SELECTION_TINT


def test_suppression_et_fermeture_du_document_oublient_les_objets() -> None:
    display, observers = layers()
    piece, other = Piece("P"), Piece("Q")
    display.show(SELECTION, [piece, other], SELECTION_LOOK)
    (watcher,) = observers.posed
    watcher.slotDeletedObject(piece)  # type: ignore[attr-defined]
    assert display.tracked() == ["/Q"]
    watcher.slotDeletedDocument(type("Doc", (), {"Name": ""})())  # type: ignore[attr-defined]
    assert display.tracked() == []
    assert observers.posed == []  # observateur retiré avec le dernier calque


def test_observateur_pose_seulement_tant_qu_un_calque_existe() -> None:
    display, observers = layers()
    piece = Piece("P")
    assert observers.posed == []
    display.show(SELECTION, [piece], SELECTION_LOOK)
    display.show(EDIT, [piece], EDIT_LOOK)
    assert len(observers.posed) == 1
    display.release(EDIT)
    assert len(observers.posed) == 1
    display.release(SELECTION)
    assert observers.posed == []


def test_release_all_rend_tout() -> None:
    display, observers = layers()
    first, second = Piece("A", 3), Piece("B", 4)
    display.show(SELECTION, [first], SELECTION_LOOK)
    display.show(EDIT, [second], EDIT_LOOK)
    display.release_all()
    assert (first.view.Transparency, second.view.Transparency) == (3, 4)
    assert observers.posed == []
