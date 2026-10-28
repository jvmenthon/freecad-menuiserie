# SPDX-License-Identifier: LGPL-2.1-or-later
"""Transparence des pièces pendant le panneau d'un assemblage : parties vérifiables sans FreeCAD
(:class:`PartsPreview` avec des doubles ; câblage du panneau par analyse statique)."""

from __future__ import annotations

import ast
from typing import Any

from freecad.menuiserie.gui.task_panels.preview import PREVIEW_TRANSPARENCY, PartsPreview
from tests.unit.aides import ROOT

PANELS = ROOT / "freecad/menuiserie/gui/task_panels"


class FakeViewObject:
    def __init__(self, transparency: int) -> None:
        self.Transparency = transparency


class FakeObject:
    def __init__(self, name: str, transparency: int = 0, *, gui: bool = True) -> None:
        self.Name = name
        if gui:
            self.ViewObject = FakeViewObject(transparency)

    @property
    def transparency(self) -> int:
        return int(self.ViewObject.Transparency)


class Scene:
    """Objets affichés (modifiables) et objets supprimés, comme le document les voit."""

    def __init__(self, *shown: Any) -> None:
        self.shown = list(shown)
        self.dead: list[Any] = []
        self.unreadable = False

    def _shown(self) -> list[Any]:
        if self.unreadable:
            raise ReferenceError("Cannot access attribute of deleted object")
        return list(self.shown)

    def preview(self) -> PartsPreview:
        return PartsPreview(self._shown, lambda obj: obj not in self.dead)


def test_pieces_transparentes_puis_transparence_d_origine_retablie() -> None:
    host, guest = FakeObject("Host", 0), FakeObject("Guest", 25)
    preview = Scene(host, guest).preview()
    assert [host.transparency, guest.transparency] == [PREVIEW_TRANSPARENCY] * 2
    assert PREVIEW_TRANSPARENCY == 60
    preview.restore()
    assert [host.transparency, guest.transparency] == [0, 25]


def test_une_piece_deja_a_60_retrouve_sa_valeur() -> None:
    piece = FakeObject("Piece", 60)
    preview = Scene(piece).preview()
    piece.ViewObject.Transparency = 80
    preview.restore()
    assert piece.transparency == 60


def test_objet_affiche_qui_change_pendant_l_edition() -> None:
    blank, guest = FakeObject("Blank", 10), FakeObject("Guest", 0)
    scene = Scene(blank, guest)
    preview = scene.preview()
    machined = FakeObject("Machined", 0)
    scene.shown[0] = machined  # pièce usinée créée au recalcul, brute masquée
    preview.sync()
    assert [blank.transparency, machined.transparency, guest.transparency] == [10, 60, 60]
    preview.sync()  # idempotent : la transparence d'origine n'est pas écrasée
    assert [blank.transparency, machined.transparency, guest.transparency] == [10, 60, 60]
    preview.restore()
    assert [blank.transparency, machined.transparency, guest.transparency] == [10, 0, 0]


def test_jamais_de_restauration_sur_un_objet_supprime() -> None:
    host, guest = FakeObject("Host", 5), FakeObject("Guest", 7)
    scene = Scene(host, guest)
    preview = scene.preview()
    scene.dead.append(host)
    host.ViewObject.Transparency = 99  # trace : toute écriture ultérieure serait visible
    preview.sync()
    preview.restore()
    assert host.transparency == 99
    assert guest.transparency == 7


def test_objet_supprime_puis_remplace_sous_le_meme_nom() -> None:
    old, new = FakeObject("Piece", 5), FakeObject("Piece", 30)
    scene = Scene(old)
    preview = scene.preview()
    scene.dead.append(old)
    scene.shown[0] = new
    preview.sync()
    assert (old.transparency, new.transparency) == (60, 60)  # l'ancien n'est pas touché
    preview.restore()
    assert (old.transparency, new.transparency) == (60, 30)


def test_pieces_illisibles_l_ancien_affichage_est_retabli() -> None:
    piece = FakeObject("Piece", 15)
    scene = Scene(piece)
    preview = scene.preview()
    scene.unreadable = True  # assemblage supprimé : ses pièces ne se lisent plus
    preview.sync()
    assert piece.transparency == 15


def test_restauration_idempotente_et_apercu_clos() -> None:
    piece = FakeObject("Piece", 20)
    preview = Scene(piece).preview()
    preview.restore()
    piece.ViewObject.Transparency = 45
    preview.restore()
    preview.sync()  # fermé : plus aucune écriture
    assert piece.transparency == 45


def test_sans_interface_graphique_aucun_effet() -> None:
    preview = Scene(FakeObject("Piece", gui=False)).preview()
    preview.sync()
    preview.restore()


def test_le_panneau_d_assemblage_rend_les_pieces_transparentes() -> None:
    """Câblage : aperçu créé par le panneau, relu après chaque aperçu, rétabli à la fermeture
    (``_release_display`` appelée par ``base`` pour « OK », « Annuler » et fermeture forcée)."""
    joint = ast.parse((PANELS / "joint.py").read_text(encoding="utf-8"))
    panel = next(
        n for n in joint.body if isinstance(n, ast.ClassDef) and n.name == "JointTaskPanel"
    )
    methods = {n.name: ast.unparse(n) for n in panel.body if isinstance(n, ast.FunctionDef)}
    assert "PartsPreview(self._shown_parts, object_alive)" in methods["__init__"]
    assert "shown_object" in methods["_shown_parts"]
    assert "super().preview()" in methods["preview"]
    assert "_transparency.sync()" in methods["preview"]
    assert "_transparency.restore()" in methods["_release_display"]

    base = ast.parse((PANELS / "base.py").read_text(encoding="utf-8"))
    callers = {
        f.name
        for c in base.body
        if isinstance(c, ast.ClassDef) and c.name == "TransactionTaskPanel"
        for f in c.body
        if isinstance(f, ast.FunctionDef) and "self._release_display()" in ast.unparse(f)
    }
    assert callers == {"_finish", "_on_closed_by_freecad"}
