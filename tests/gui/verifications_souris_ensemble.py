# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la taille et de l'orientation d'un ensemble à la souris (EN-c,
ADR 0038, critères C1 à C4).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Comme pour
``verifications_souris.py``, aucun clic ni mouvement Qt réel (ils font planter FreeCAD hors
écran) : le geste est simulé par les méthodes de la session (``press``, ``move``, ``release``,
``escape``). Hors écran, ``getPoint`` et ``getPointOnScreen`` n'ont pas la même échelle : on vise
le rayon de la souris, ce que la session lit.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie.features.furniture_container import std_part_of
from freecad.menuiserie.features.furniture_drag import turn_refusal
from freecad.menuiserie.gui.drag import events
from tests.gui.verifications_double_clic import vue_3d_active
from tests.gui.verifications_panneau import annuler, ecarts
from tests.gui.verifications_panneau_ensemble import bureau_regroupe, ouvrir
from tests.gui.verifications_souris import (
    noeuds_incrustes,
    preparer,
    proche,
    selection_dessinee,
    souris,
    sur_la_poignee,
    tirer,
)
from tests.gui.verifications_souris_rotation import (
    saisir_anneau,
    tourner_de,
    vue_isometrique,
)
from tests.integration.bureau import Bureau

REDIMENSIONNER = "Redimensionner l'ensemble"
DEPLACER = "Déplacer l'ensemble"
TOURNER = "Tourner l'ensemble"
TOLERANCE = 5.0  # mm : écart toléré sur une cote obtenue par la souris (pixels entiers)
Point = tuple[int, int]
FACES = ("-X", "+X", "-Y", "+Y", "-Z", "+Z")


def cotes(ensemble: Any) -> tuple[float, float, float]:
    return (
        round(ensemble.Width.Value, 3),
        round(ensemble.Depth.Value, 3),
        round(ensemble.Height.Value, 3),
    )


def proches(nom: str, obtenu: tuple[float, ...], attendu: tuple[float, ...]) -> list[str]:
    """Écarts, à :data:`TOLERANCE` près, entre deux triplets de mm."""
    return [
        p
        for i, (o, a) in enumerate(zip(obtenu, attendu, strict=True))
        for p in proche(f"{nom} [{i}]", o, a, TOLERANCE)
    ]


def base(ensemble: Any) -> tuple[float, float, float]:
    """Position du Std Part de l'ensemble (mm)."""
    p = std_part_of(ensemble).Placement.Base
    return round(p.x, 3), round(p.y, 3), round(p.z, 3)


def lacet(ensemble: Any) -> float:
    return float(std_part_of(ensemble).Placement.Rotation.getYawPitchRoll()[0])


def centre(ensemble: Any) -> tuple[float, float, float]:
    """Centre de la boîte de l'ensemble dans le document (mm)."""
    local = App.Vector(
        ensemble.Width.Value / 2, ensemble.Depth.Value / 2, ensemble.Height.Value / 2
    )
    o = ensemble.Origin
    p = std_part_of(ensemble).Placement.multVec(local + App.Vector(o.x, o.y, o.z))
    return round(p.x, 3), round(p.y, 3), round(p.z, 3)


@contextmanager
def ensemble_selectionne(nom: str) -> Iterator[tuple[Bureau, Any]]:
    """Bureau regroupé, ensemble sélectionné seul, vue isométrique ; renvoie le bureau et la
    session du glissement. Historique d'annulation vidé."""
    with bureau_regroupe(nom) as bureau:
        session = preparer(bureau.doc)
        vue_isometrique()
        bureau.doc.clearUndos()
        selection_dessinee(bureau.furniture)
        yield bureau, session


def echapper(session: Any) -> bool:
    """Échap, puis le relâchement du bouton qui le suit (consommé par la session)."""
    consomme = bool(session.escape())
    return consomme and bool(session.release((0, 0)))


def saisir_poignee(session: Any, face: str, *, shift: bool = False) -> bool:
    """Survole puis saisit la poignée de la face ``face`` (``-X``, ``+X``…)."""
    point = sur_la_poignee(session, "XYZ".index(face[1]), face[0] == "+")
    session.move(point)
    return bool(session.press(point, shift))


def _etat(session: Any) -> tuple[str, str | None]:
    return type(session.state).__name__, session.state.key


# --- C1 : dessin et survol ------------------------------------------------------------------


def _dessin(bureau: Bureau, session: Any) -> list[str]:
    layout = session.layout
    problemes = [
        *ecarts("cible : l'ensemble", session.part, bureau.furniture),
        *ecarts("six poignées", len(layout.handles), 6),
        *ecarts("trois flèches", [a.axis for a in layout.arrows], [0, 1, 2]),
        *ecarts("trois anneaux", [r.axis for r in layout.rings], [0, 1, 2]),
        *ecarts("boîte dessinée", (layout.shows_box, layout.double_handles), (True, True)),
        *ecarts("un seul nœud d'incrustation", noeuds_incrustes(), 1),
        *ecarts("incrustation dessinée", session.overlay.shows(), True),
        *ecarts("boîte de l'ensemble", layout.box.size(0), bureau.furniture.Width.Value),
    ]
    for face in FACES:
        session.move(sur_la_poignee(session, "XYZ".index(face[1]), face[0] == "+"))
        problemes += ecarts(f"survol de {face}", _etat(session)[0], "Hover")
    session.move((5, 5))
    return [*problemes, *ecarts("souris ailleurs", _etat(session)[0], "Idle")]


def verifier_souris_ensemble_dessin() -> list[str]:
    """C1 : ensemble sélectionné seul : boîte, six poignées, trois flèches, trois anneaux, un
    nœud d'incrustation ; survol des faces."""
    with ensemble_selectionne("VerifSourisEnsembleDessin") as (bureau, session):
        return _dessin(bureau, session)


def _piece_membre(bureau: Bureau, session: Any) -> list[str]:
    piece = bureau.shown("JG")
    selection_dessinee(piece)
    return [
        *ecarts("pièce membre : sa brute", session.part, bureau.parts["JG"]),
        *ecarts("pièce membre : pas de poignée", session.layout.handles, ()),
        *ecarts("pièce membre : flèches de la pièce", len(session.layout.arrows) > 0, True),
        *ecarts("pièce membre : ni boîte ni double flèche", session.layout.shows_box, False),
        *ecarts("pièce membre : un nœud", noeuds_incrustes(), 1),
    ]


def verifier_souris_ensemble_piece_membre_inchangee() -> list[str]:
    """C3 : une pièce membre sélectionnée seule garde ses propres flèches (rien de l'ensemble)."""
    with ensemble_selectionne("VerifSourisEnsemblePieceMembre") as (bureau, session):
        return _piece_membre(bureau, session)


# --- C2 : taille ----------------------------------------------------------------------------


def _taille(bureau: Bureau, session: Any) -> list[str]:
    ensemble, doc = bureau.furniture, bureau.doc
    pris = saisir_poignee(session, "+X")
    problemes = [
        *ecarts("poignée +X saisie", pris, True),
        *ecarts("état Resizing", _etat(session), ("Resizing", "handle0e")),
        *ecarts("cadence de 10 Hz", session.target.resize_rate, 10),
    ]
    tirer(session, 100.0, shift=True)
    problemes += [
        *proches("largeur +100", cotes(ensemble), (1300.0, 600.0, 750.0)),
        *ecarts("Origin et Std Part fixes", base(ensemble), (0.0, 0.0, 0.0)),
        *proche("plateau étiré", bureau.parts["P"].Length.Value, cotes(ensemble)[0], 1e-3),
        *ecarts(
            "cote écrite près de la souris",
            session.state.note.text,
            f"{cotes(ensemble)[0]:.1f} mm",
        ),
        *ecarts("incrustation : un seul nœud", noeuds_incrustes(), 1),
    ]
    arrivee = tirer(session, 100.0, shift=True)
    problemes += [
        *ecarts("relâchement consommé", session.release(arrivee), True),
        *ecarts("geste fini", session.dragging, False),
        *ecarts("une transaction", doc.UndoNames, [REDIMENSIONNER]),
        *proches("largeur gardée", cotes(ensemble), (1300.0, 600.0, 750.0)),
        *proche("boîte redessinée", session.layout.box.size(0), cotes(ensemble)[0], 1e-3),
    ]
    doc.undo()
    return [
        *problemes,
        *ecarts("Ctrl+Z : un seul pas", cotes(ensemble), (1200.0, 600.0, 750.0)),
        *ecarts("Ctrl+Z : plateau", round(bureau.parts["P"].Length.Value, 3), 1200.0),
    ]


def verifier_souris_ensemble_taille() -> list[str]:
    """C2 : tirer la face +X change la largeur, les pièces suivent, transaction « Redimensionner
    l'ensemble », un Ctrl+Z."""
    with ensemble_selectionne("VerifSourisEnsembleTaille") as (bureau, session):
        return _taille(bureau, session)


def _face_avant(bureau: Bureau, session: Any) -> list[str]:
    ensemble, doc = bureau.furniture, bureau.doc
    pris = saisir_poignee(session, "-Y")
    tirer(session, -50.0, shift=True)  # vers l'avant : la profondeur croît
    arrivee = tirer(session, -50.0, shift=True)
    problemes = [
        *ecarts("poignée -Y saisie", pris, True),
        *proches("profondeur +50", cotes(ensemble), (1200.0, 650.0, 750.0)),
        *proches("Std Part avancé", base(ensemble), (0.0, -50.0, 0.0)),
        *proche("face arrière fixe", base(ensemble)[1] + cotes(ensemble)[1], 600.0, 1e-3),
        *ecarts("Origin fixe", tuple(ensemble.Origin), (0.0, 0.0, 0.0)),
        *ecarts("relâchement consommé", session.release(arrivee), True),
        *ecarts("une transaction", doc.UndoNames, [REDIMENSIONNER]),
    ]
    doc.undo()
    return [
        *problemes,
        *ecarts("Ctrl+Z : cotes", cotes(ensemble), (1200.0, 600.0, 750.0)),
        *ecarts("Ctrl+Z : Std Part", base(ensemble), (0.0, 0.0, 0.0)),
    ]


def verifier_souris_ensemble_face_avant() -> list[str]:
    """C2 : tirer la face avant décale le Std Part, la face arrière reste en place."""
    with ensemble_selectionne("VerifSourisEnsembleAvant") as (bureau, session):
        return _face_avant(bureau, session)


def _refus(bureau: Bureau, session: Any) -> list[str]:
    ensemble, doc = bureau.furniture, bureau.doc
    saisir_poignee(session, "+X")
    tirer(session, -1190.0, shift=True)  # la cote voudrait tomber à 10 mm : les joues s'y opposent
    session.state.flush(session)
    note = session.state.note
    largeur = cotes(ensemble)[0]
    problemes = [
        *ecarts("arrêt avant la cote minimale", 0.0 < largeur < 1200.0, True),
        *ecarts("message près de la souris", note is not None and "\n" in note.text, True),
        *ecarts("message en rouge", note is not None and note.color[0] > 0.8, True),
        *proche("les pièces suivent la dernière cote permise", bureau.sizes("P")[0], largeur, 1e-3),
    ]
    session.release(tirer(session, -1190.0, shift=True))
    problemes += [
        *ecarts("relâchement : valeur permise", 0.0 < cotes(ensemble)[0] < 1200.0, True),
        *ecarts("une transaction", doc.UndoNames, [REDIMENSIONNER]),
    ]
    doc.undo()
    return [*problemes, *ecarts("Ctrl+Z", cotes(ensemble), (1200.0, 600.0, 750.0))]


def verifier_souris_ensemble_refus() -> list[str]:
    """B3, C2 : cote refusée : arrêt à la dernière valeur permise, message près de la souris,
    rien d'invalide écrit."""
    with ensemble_selectionne("VerifSourisEnsembleRefus") as (bureau, session):
        return _refus(bureau, session)


def _aimant(bureau: Bureau, session: Any) -> list[str]:
    boite = bureau.doc.addObject("Part::Box", "Voisine")
    boite.Length, boite.Width, boite.Height = 100, 100, 100
    boite.Placement.Base = App.Vector(1300, 0, 0)  # face gauche à x = 1300
    bureau.doc.recompute()
    selection_dessinee(bureau.furniture)
    saisir_poignee(session, "+X")
    tolerance = session.state.tolerance
    tirer(session, 100.0 - tolerance / 2)
    problemes = proche("aimant : la face va à 1300", cotes(bureau.furniture)[0], 1300.0, 1e-6)
    problemes += ecarts("guide allumé", len(session.lit), 1)
    session.state.shift_changed(session, True)
    tirer(session, 100.0 - tolerance / 2, shift=True)
    session.state.flush(session)
    problemes += proche(
        "Maj : sans aimant", cotes(bureau.furniture)[0], 1300.0 - tolerance / 2, TOLERANCE
    )
    echapper(session)
    return problemes


def verifier_souris_ensemble_aimant() -> list[str]:
    """C1 : la face tirée s'aimante sur un objet voisin (10 px), Maj coupe l'aimant ; les pièces
    de l'ensemble ne le guident pas."""
    with ensemble_selectionne("VerifSourisEnsembleAimant") as (bureau, session):
        return _aimant(bureau, session)


# --- Déplacement ----------------------------------------------------------------------------


def _deplacement(bureau: Bureau, session: Any) -> list[str]:
    ensemble, doc = bureau.furniture, bureau.doc
    fleche = next(a for a in session.layout.arrows if a.axis == 0)
    point = session.port.project(fleche.end)
    session.move((round(point[0]), round(point[1])))
    pris = session.press((round(point[0]), round(point[1])))
    problemes = [
        *ecarts("flèche X saisie", pris, True),
        *ecarts("état", _etat(session), ("Moving", "arrow0")),
    ]
    tirer(session, 150.0, shift=True)
    arrivee = tirer(session, 150.0, shift=True)
    problemes += [
        *proches("Std Part déplacé", base(ensemble), (150.0, 0.0, 0.0)),
        *ecarts("cotes inchangées", cotes(ensemble), (1200.0, 600.0, 750.0)),
        *ecarts("relâchement consommé", session.release(arrivee), True),
        *ecarts("une transaction", doc.UndoNames, [DEPLACER]),
    ]
    doc.undo()
    return [*problemes, *ecarts("Ctrl+Z", base(ensemble), (0.0, 0.0, 0.0))]


def verifier_souris_ensemble_deplacement() -> list[str]:
    """Q5 : une flèche déplace le Std Part, transaction « Déplacer l'ensemble », un Ctrl+Z."""
    with ensemble_selectionne("VerifSourisEnsembleDeplacement") as (bureau, session):
        return _deplacement(bureau, session)


# --- Rotation -------------------------------------------------------------------------------


def _rotation(bureau: Bureau, session: Any) -> list[str]:
    ensemble, doc = bureau.furniture, bureau.doc
    avant = centre(ensemble)
    pris, depart = saisir_anneau(session, 2)
    problemes = [
        *ecarts("anneau Z saisi", pris, True),
        *ecarts("état", _etat(session), ("Rotating", "ring2")),
    ]
    arrivee = tourner_de(session, 2, 34.0, depart)
    problemes += [
        *proche("aimant : 34° donne 30°", lacet(ensemble), 30.0, 0.01),
        *ecarts("angle écrit près de la souris", session.state.sweep.angle, 30.0),
        *ecarts("centre immobile", centre(ensemble), avant),
        *ecarts("cotes inchangées", cotes(ensemble), (1200.0, 600.0, 750.0)),
    ]
    tourner_de(session, 2, 34.0, depart, shift=True)
    problemes += proche("Maj : angle libre", lacet(ensemble), 34.0, 2.0)
    session.shift_changed(False)
    problemes += [
        *proche("Maj relâchée : aimant", lacet(ensemble), 30.0, 0.01),
        *ecarts("relâchement consommé", session.release(arrivee), True),
        *ecarts("une transaction", doc.UndoNames, [TOURNER]),
        *ecarts(
            "plateau tourné avec l'ensemble",
            round(bureau.parts["P"].Placement.Rotation.Angle, 3) == 0.0,
            True,
        ),
    ]
    doc.undo()
    return [*problemes, *proche("Ctrl+Z", lacet(ensemble), 0.0, 1e-6)]


def verifier_souris_ensemble_rotation() -> list[str]:
    """C1, B4 : un anneau tourne le Std Part autour du centre de la boîte, aimant à 15°, Maj
    libre, transaction « Tourner l'ensemble », un Ctrl+Z."""
    with ensemble_selectionne("VerifSourisEnsembleRotation") as (bureau, session):
        return _rotation(bureau, session)


def _std_part_tourne(bureau: Bureau, session: Any) -> list[str]:
    ensemble, doc = bureau.furniture, bureau.doc
    std = std_part_of(ensemble)
    std.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    doc.recompute()
    doc.clearUndos()
    selection_dessinee(ensemble)
    problemes = ecarts("repère du Std Part tourné", session.layout.frame.x.y, 1.0)
    saisir_poignee(session, "+X")
    tirer(session, 80.0, shift=True)
    arrivee = tirer(session, 80.0, shift=True)
    problemes += [
        *proches("largeur +80", cotes(ensemble), (1280.0, 600.0, 750.0)),
        *ecarts(
            "Std Part tourné gardé", round(std.Placement.Rotation.Angle, 4), round(math.pi / 2, 4)
        ),
        *ecarts("relâchement consommé", session.release(arrivee), True),
    ]
    saisir_poignee(session, "-X")
    tirer(session, -30.0, shift=True)
    arrivee = tirer(session, -30.0, shift=True)
    session.release(arrivee)
    # face gauche tirée de 30 mm : le Std Part avance de 30 mm sur son axe X (le Y du document)
    problemes += [
        *proches("face gauche : largeur", cotes(ensemble), (1310.0, 600.0, 750.0)),
        *proches("face gauche : Std Part décalé", base(ensemble), (0.0, -30.0, 0.0)),
    ]
    doc.undo()
    doc.undo()
    session.sync()  # la souris bouge après un Ctrl+Z : la disposition est remise à jour
    problemes += ecarts("Ctrl+Z (deux pas)", cotes(ensemble), (1200.0, 600.0, 750.0))
    pris, depart = saisir_anneau(session, 2)
    tourner_de(session, 2, 45.0, depart)
    problemes += [
        *ecarts("anneau saisi sur un Std Part tourné", pris, True),
        *proche("rotation sur un Std Part tourné : 90° + 45°", lacet(ensemble), 135.0, 0.01),
    ]
    echapper(session)
    return [*problemes, *proche("Échap", lacet(ensemble), 90.0, 0.01)]


def verifier_souris_ensemble_std_part_tourne() -> list[str]:
    """C4 : ensemble dans un Std Part tourné : tailles (faces droite et gauche) et rotation dans le
    repère du Std Part."""
    with ensemble_selectionne("VerifSourisEnsembleStdTourne") as (bureau, session):
        return _std_part_tourne(bureau, session)


# --- Échap ----------------------------------------------------------------------------------


def _echap(bureau: Bureau, session: Any) -> list[str]:
    ensemble, doc = bureau.furniture, bureau.doc
    problemes: list[str] = []
    saisir_poignee(session, "-Z")
    arrivee = tirer(session, -120.0, shift=True)
    problemes += [
        *proche("hauteur +120 avant Échap", cotes(ensemble)[2], 870.0, TOLERANCE),
        *ecarts("Échap consommé", session.escape(), True),
        *ecarts("cotes revenues", cotes(ensemble), (1200.0, 600.0, 750.0)),
        *ecarts("Std Part revenu", base(ensemble), (0.0, 0.0, 0.0)),
        *ecarts("plateau revenu", round(bureau.parts["P"].Placement.Base.z, 3), 720.0),
        *ecarts("mouvement suivant consommé", session.move(arrivee), True),
        *ecarts("relâchement consommé", session.release(arrivee), True),
        *ecarts("puis rendu à FreeCAD", session.release(arrivee), False),
        *ecarts("historique inchangé", doc.UndoNames, []),
        *ecarts("liaisons gardées", "Length" in bureau.parts["P"].ExpressionEngine.__str__(), True),
    ]
    _, depart = saisir_anneau(session, 0)
    tourner_de(session, 0, 60.0, depart)
    problemes += [
        *ecarts("Échap (anneau) consommé", echapper(session), True),
        *proche(
            "rotation annulée", float(std_part_of(ensemble).Placement.Rotation.Angle), 0.0, 1e-9
        ),
        *ecarts("historique inchangé après l'anneau", doc.UndoNames, []),
    ]
    return problemes


def verifier_souris_ensemble_echap() -> list[str]:
    """C2 : Échap pendant le geste ramène l'ensemble au début, sans entrée d'annulation."""
    with ensemble_selectionne("VerifSourisEnsembleEchap") as (bureau, session):
        return _echap(bureau, session)


# --- Sans Std Part propre -------------------------------------------------------------------


def _sans_std_part_propre(bureau: Bureau, session: Any) -> list[str]:
    ensemble, doc = bureau.furniture, bureau.doc
    std = std_part_of(ensemble)
    etranger = doc.addObject("Part::Box", "Etranger")
    std.addObject(etranger)  # le Std Part contient autre chose que l'ensemble
    doc.recompute()
    doc.clearUndos()
    selection_dessinee(ensemble)
    layout = session.layout
    problemes = [
        *ecarts("raison du refus", turn_refusal(ensemble) is not None, True),
        *ecarts("sans Std Part propre : six poignées", len(layout.handles), 6),
        *ecarts("sans Std Part propre : aucune flèche", layout.arrows, ()),
        *ecarts("sans Std Part propre : aucun anneau", layout.rings, ()),
    ]
    saisir_poignee(session, "-Y")
    tirer(session, -40.0, shift=True)
    session.state.flush(session)
    refus = session.state.note
    problemes += [
        *ecarts("face avant refusée : profondeur gardée", cotes(ensemble), (1200.0, 600.0, 750.0)),
        *ecarts(
            "face avant refusée : message", refus is not None and "Std Part" in refus.text, True
        ),
    ]
    echapper(session)
    saisir_poignee(session, "+Y")
    tirer(session, 40.0, shift=True)
    arrivee = tirer(session, 40.0, shift=True)
    session.release(arrivee)
    problemes += proches("face arrière permise", cotes(ensemble), (1200.0, 640.0, 750.0))
    doc.undo()
    return problemes


def verifier_souris_ensemble_sans_std_part_propre() -> list[str]:
    """E5 : sans Std Part propre, ni flèches ni anneaux ; les faces avant, gauche et basse sont
    refusées avec le message, les faces arrière, droite et haute se tirent."""
    with ensemble_selectionne("VerifSourisEnsembleSansStdPart") as (bureau, session):
        return _sans_std_part_propre(bureau, session)


# --- Panneau ouvert -------------------------------------------------------------------------


def _panneau_ouvert(bureau: Bureau, session: Any) -> list[str]:
    ensemble, doc = bureau.furniture, bureau.doc
    Gui.Selection.clearSelection()
    form = ouvrir(ensemble)
    QtCore.QCoreApplication.processEvents()
    if form is None:
        return ["panneau non ouvert"]
    transaction = App.getActiveTransaction()
    problemes = [
        *ecarts("panneau ouvert : cible l'ensemble", session.part, ensemble),
        *ecarts("panneau ouvert : six poignées", len(session.layout.handles), 6),
    ]
    saisir_poignee(session, "+X")
    arrivee = tirer(session, 60.0, shift=True)
    largeur = form.findChild(QtCore.QObject, "Width")
    problemes += [
        *proche("largeur +60", cotes(ensemble)[0], 1260.0, TOLERANCE),
        *proche(
            "le panneau relit la largeur",
            float(largeur.property("rawValue")),
            cotes(ensemble)[0],
            1e-3,
        ),
        *ecarts("relâchement consommé", session.release(arrivee), True),
        *ecarts("transaction du panneau", App.getActiveTransaction(), transaction),
        *ecarts("pas de transaction propre", REDIMENSIONNER in doc.UndoNames, False),
    ]
    annuler()
    return [
        *problemes,
        *ecarts("« Annuler » ramène l'ensemble", cotes(ensemble), (1200.0, 600.0, 750.0)),
    ]


def verifier_souris_ensemble_panneau_ouvert() -> list[str]:
    """Panneau ouvert : le geste écrit dans la transaction du panneau, qui relit ses champs (D2) ;
    « Annuler » rétablit tout."""
    with ensemble_selectionne("VerifSourisEnsemblePanneau") as (bureau, session):
        return _panneau_ouvert(bureau, session)


# --- Le reste est rendu à FreeCAD -----------------------------------------------------------


def _evenements_rendus(bureau: Bureau, session: Any) -> list[str]:
    viewport, filtre = vue_3d_active(bureau.doc), events._INSTALLATION.filter
    if viewport is None or filtre is None:
        return ["vue 3D ou filtre absents"]
    sur = sur_la_poignee(session, 0, True)
    gauche, droit = QtCore.Qt.LeftButton, QtCore.Qt.RightButton
    press, move, release = (
        QtCore.QEvent.MouseButtonPress,
        QtCore.QEvent.MouseMove,
        QtCore.QEvent.MouseButtonRelease,
    )
    rendus = [
        ("clic gauche ailleurs", souris(viewport, press, (5, 5))),
        ("clic droit sur la poignée", souris(viewport, press, sur, droit)),
        (
            "Ctrl + clic sur la poignée",
            souris(viewport, press, sur, gauche, QtCore.Qt.ControlModifier),
        ),
        ("relâchement sans geste", souris(viewport, release, sur)),
        ("mouvement sans geste", souris(viewport, move, sur)),
    ]
    problemes = []
    for nom, evenement in rendus:
        problemes += ecarts(f"{nom} rendu", bool(filtre.eventFilter(viewport, evenement)), False)
    pris = filtre.eventFilter(viewport, souris(viewport, press, sur))
    problemes += [
        *ecarts("clic gauche sur la poignée consommé", bool(pris), True),
        *ecarts("geste commencé", session.dragging, True),
    ]
    echapper(session)
    return problemes


def verifier_souris_ensemble_evenements_rendus() -> list[str]:
    """C2 : seul le clic sur une poignée, une flèche ou un anneau est consommé."""
    with ensemble_selectionne("VerifSourisEnsembleRendus") as (bureau, session):
        return _evenements_rendus(bureau, session)


VERIFICATIONS_SOURIS_ENSEMBLE: tuple[Callable[[], list[str]], ...] = (
    verifier_souris_ensemble_dessin,
    verifier_souris_ensemble_piece_membre_inchangee,
    verifier_souris_ensemble_taille,
    verifier_souris_ensemble_face_avant,
    verifier_souris_ensemble_refus,
    verifier_souris_ensemble_aimant,
    verifier_souris_ensemble_deplacement,
    verifier_souris_ensemble_rotation,
    verifier_souris_ensemble_std_part_tourne,
    verifier_souris_ensemble_echap,
    verifier_souris_ensemble_sans_std_part_propre,
    verifier_souris_ensemble_panneau_ouvert,
    verifier_souris_ensemble_evenements_rendus,
)
