# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la « Finition des chants » sur une pièce dessinée (ADR 0063).

Maquette A retenue par jv : un clic sur une face prend tout son contour, une ligne par arête de
sa propre couleur, une croix rouge qui retire une arête seule, la même couleur dans la vue 3D.
Module importé par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
import Part

from tests.gui.verifications_chants import COMMANDE, carte, formulaire
from tests.gui.verifications_panneau import annuler, avec_document, ecarts, valider
from tests.gui.verifications_panneau_assemblage import widget

L_SHAPE = ((0, 0), (400, 0), (400, 80), (150, 80), (150, 200), (0, 200))


def piece_en_l(doc: Any) -> Any:
    """Pièce dessinée dans un corps PartDesign : un L de 20 mm d'épaisseur."""
    from freecad.menuiserie import api

    body = doc.addObject("PartDesign::Body", "Corps")
    sketch = body.newObject("Sketcher::SketchObject", "Esquisse")
    for index, start in enumerate(L_SHAPE):
        end = L_SHAPE[(index + 1) % len(L_SHAPE)]
        sketch.addGeometry(Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0)), False)
    pad = body.newObject("PartDesign::Pad", "Protrusion")
    pad.Profile = sketch
    pad.Length = 20.0
    doc.recompute()
    shaped = api.make_shaped_part(body)
    doc.recompute()
    return shaped


def face_du_dessus(part: Any) -> str:
    """Nom de la face du dessus (z = 20) de la pièce en L."""
    for index, face in enumerate(part.Shape.Faces, start=1):
        if abs(face.CenterOfMass.z - 20.0) < 1e-6 and abs(face.normalAt(0, 0).z) > 0.99:
            return f"Face{index}"
    raise LookupError("face du dessus")


def _ouvrir(part: Any, sub: str) -> Any:
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(part, sub)
    Gui.Command.get(COMMANDE).run()
    return formulaire()


def _lignes(card: Any) -> list[Any]:
    from PySide import QtGui

    return [
        child
        for child in card.findChildren(QtGui.QWidget)
        if child.objectName().startswith("edge_Edge")
    ]


def _contour(doc: Any) -> list[str]:
    from freecad.menuiserie import api
    from freecad.menuiserie.gui.task_panels.edge_rows import NativeCard

    part = piece_en_l(doc)
    form = _ouvrir(part, face_du_dessus(part))
    if form is None:
        return ["panneau de finition non ouvert"]
    card = carte(form, part)
    problemes = [
        *ecarts("carte de pièce dessinée", isinstance(card, NativeCard), True),
        *ecarts("tout le contour du dessus", len(card.codes()), 6),
        *ecarts("une ligne par arête", len(_lignes(card)), 6),
        *ecarts("une couleur par arête", len(set(card.edge_colors().values())), 6),
        *ecarts("pas de dessin de boîte", widget(form, "view_row").isVisible(), False),
    ]
    retiree = card.codes()[0]
    widget(_lignes(card)[0], "remove_edge").click()  # croix rouge de la première ligne
    problemes += ecarts("arête retirée seule", retiree in card.codes(), False)
    problemes += ecarts("cinq arêtes restent", len(card.codes()), 5)
    valider()
    profils = api.edge_profiles_of(part)
    return [
        *problemes,
        *ecarts("un profil", len(profils), 1),
        *ecarts(
            "arêtes natives enregistrées",
            sorted(profils[0].EdgeRefs[1]) if profils else [],
            sorted(_sans(retiree, part)),
        ),
        *ecarts("une entrée d'annulation", doc.UndoNames, ["Finition des chants"]),
    ]


def _sans(retiree: str, part: Any) -> list[str]:
    from freecad.menuiserie.features.edge_frames import face_edge_names

    return [name for name in face_edge_names(part.Shape, face_du_dessus(part)) if name != retiree]


def verifier_contour_d_une_face() -> list[str]:
    """Clic sur une face d'une pièce dessinée : ses 6 arêtes, une couleur chacune ; la croix
    rouge en retire une ; « OK » crée le profil sur les 5 autres."""
    return avec_document("VerifChantsNatifs", _contour)


def _second_clic(doc: Any) -> list[str]:
    from PySide import QtGui

    part = piece_en_l(doc)
    face = face_du_dessus(part)
    Gui.Selection.clearSelection()
    Gui.Command.get(COMMANDE).run()  # sans sélection : on clique ensuite dans la vue 3D
    form = formulaire()
    if form is None:
        return ["panneau de finition non ouvert"]
    Gui.Selection.addSelection(part, face)  # premier clic : tout le contour
    QtGui.QApplication.processEvents()
    problemes = ecarts("contour ajouté au premier clic", len(carte(form, part).codes()), 6)
    Gui.Selection.addSelection(part, face)  # second clic sur la même face
    QtGui.QApplication.processEvents()
    problemes += ecarts("contour retiré au second clic", carte(form, part).codes(), [])
    annuler()
    return [*problemes, *ecarts("aucune entrée", doc.UndoNames, [])]


def verifier_second_clic_retire_le_contour() -> list[str]:
    """Second clic sur la même face pendant la tâche : ses arêtes quittent la liste."""
    return avec_document("VerifChantsNatifsBis", _second_clic)


VERIFICATIONS_CHANTS_NATIFS: tuple[Callable[[], list[str]], ...] = (
    verifier_contour_d_une_face,
    verifier_second_clic_retire_le_contour,
)
