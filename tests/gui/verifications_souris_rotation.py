# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface des anneaux de rotation (RO-d, issue #117, critères D1 à D7).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Comme pour
``verifications_souris.py``, aucun clic Qt réel : la session est appelée directement
(``press``, ``move``, ``release``, ``escape``) et le filtre d'évènements pour les seuls
évènements qu'il consomme ou rend (appel direct de ``eventFilter``). Hors écran, ``getPoint`` et
``getPointOnScreen`` n'ont pas la même échelle : on vise le rayon de la souris, ce que la session
lit (méthode de ``viser`` dans ``verifications_souris.py``).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie import api
from freecad.menuiserie.core.rotation import plane_point
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.drag import events
from freecad.menuiserie.gui.drag.rings import angle_label, ring_basis, ring_ray
from tests.gui.verifications_aronde_relachement import Choix
from tests.gui.verifications_double_clic import vue_3d_active
from tests.gui.verifications_ensemble import pieces_du_bureau
from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    ecarts,
    ouvrir_par_double_clic,
    piece_validee,
)
from tests.gui.verifications_souris import (
    noeuds_incrustes,
    preparer,
    proche,
    selection_dessinee,
    souris,
)

TRANSACTION = "Tourner la pièce"
DEPART = 30.0  # angle (degrés, dans le plan de l'anneau) où l'on saisit l'anneau
TOLERANCE = 2.0  # écart toléré, en degrés, sur un angle obtenu par la souris (pixels entiers)
Point = tuple[int, int]


def anneau(session: Any, axe: int) -> Any:
    return next(r for r in session.layout.rings if r.axis == axe)


def _plan(ring: Any, point: Any) -> tuple[float, float]:
    """Coordonnées (u, v) de ``point`` dans le plan de l'anneau, centre en origine."""
    u, v = ring_basis(ring.normal)
    d = (point.x - ring.center.x, point.y - ring.center.y, point.z - ring.center.z)
    return (
        d[0] * u.x + d[1] * u.y + d[2] * u.z,
        d[0] * v.x + d[1] * v.y + d[2] * v.z,
    )


def _lire(session: Any, ring: Any, pixel: Point) -> tuple[float, float] | None:
    point = plane_point(ring_ray(session.ray(pixel), ring), ring)
    return None if point is None else _plan(ring, point)


def viser_anneau(session: Any, axe: int, degres: float, depart: Point | None = None) -> Point:
    """Pixel dont le rayon de la souris coupe le plan de l'anneau ``axe`` au point de l'anneau
    d'angle ``degres`` (mesuré depuis le premier vecteur du plan ; Newton depuis ``depart``)."""
    ring = anneau(session, axe)
    cible = (
        ring.radius * math.cos(math.radians(degres)),
        ring.radius * math.sin(math.radians(degres)),
    )
    centre = session.port.project(ring.center)
    x, y = depart if depart is not None else (round(centre[0]), round(centre[1]))
    for _ in range(12):
        base = _lire(session, ring, (x, y))
        droite = _lire(session, ring, (x + 1, y))
        haut = _lire(session, ring, (x, y + 1))
        if base is None or droite is None or haut is None:
            break
        a, b = droite[0] - base[0], haut[0] - base[0]
        c, d = droite[1] - base[1], haut[1] - base[1]
        det = a * d - b * c
        if abs(det) < 1e-9:
            break
        ex, ey = cible[0] - base[0], cible[1] - base[1]
        x, y = round(x + (d * ex - b * ey) / det), round(y + (a * ey - c * ex) / det)
    return x, y


def lacet(piece: Any) -> float:
    """Angle autour de Z (degrés) du ``Placement`` de la pièce."""
    return float(piece.Placement.Rotation.getYawPitchRoll()[0])


def centre(piece: Any) -> tuple[float, float, float]:
    """Centre de la boîte de la pièce dans le document (mm)."""
    local = App.Vector(piece.Length.Value / 2, piece.Width.Value / 2, piece.Thickness.Value / 2)
    p = piece.Placement.multVec(local)
    return round(p.x, 3), round(p.y, 3), round(p.z, 3)


def vue_isometrique() -> None:
    Gui.activeView().viewIsometric()
    Gui.activeView().fitAll()
    QtCore.QCoreApplication.processEvents()


def saisir_anneau(session: Any, axe: int, *, shift: bool = False) -> tuple[bool, Point]:
    """Survole puis saisit l'anneau ``axe`` au point d'angle :data:`DEPART` ; renvoie la réponse
    de la session et le pixel."""
    depart = viser_anneau(session, axe, DEPART)
    session.move(depart)
    return bool(session.press(depart, shift)), depart


def tourner_de(
    session: Any, axe: int, degres: float, depart: Point, *, shift: bool = False
) -> Point:
    """Souris placée pour tourner de ``degres`` depuis le point saisi ; vrai mouvement envoyé."""
    arrivee = viser_anneau(session, axe, DEPART + degres, depart)
    session.move(arrivee, shift)
    return arrivee


# --- D1, D2, D5, D6 : anneaux, survol, tranche, expression --------------------------------


def _anneaux_et_survol(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    vue_isometrique()
    selection_dessinee(piece)
    problemes = [
        *ecarts("trois flèches", len(session.layout.arrows), 3),
        *ecarts("trois anneaux", [r.axis for r in session.layout.rings], [0, 1, 2]),
        *ecarts("un seul nœud d'incrustation", noeuds_incrustes(), 1),
        *ecarts("incrustation dessinée", session.overlay.shows(), True),
    ]
    for axe in range(3):
        session.move(viser_anneau(session, axe, DEPART))
        etat = type(session.state).__name__, session.state.key
        problemes += ecarts(f"survol de l'anneau {axe}", etat, ("Hover", f"ring{axe}"))
    session.move((5, 5))
    problemes += ecarts("souris ailleurs", type(session.state).__name__, "Idle")
    # une flèche l'emporte sur un anneau
    f = session.layout.arrows[0]
    session.move(session.port.project(f.end))
    problemes += ecarts("flèche prioritaire", session.state.key, "arrow0")
    return problemes


def verifier_rotation_anneaux_et_survol() -> list[str]:
    """D1, D2 : trois anneaux autour de la pièce sélectionnée, survol (état Hover)."""
    return avec_document("VerifRotationAnneaux", _anneaux_et_survol)


def _anneau_de_tranche(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    Gui.activeView().viewTop()
    selection_dessinee(piece)
    viewport = vue_3d_active(doc)
    trouves = set()
    for x in range(0, viewport.width(), 12):
        for y in range(0, viewport.height(), 12):
            cle = session.target_at((x, y))
            if cle is not None and cle.startswith("ring"):
                trouves.add(cle)
    problemes = ecarts("vu de dessus : seul l'anneau Z est proposé", sorted(trouves), ["ring2"])
    return [*problemes, *ecarts("clic ailleurs rendu", session.press((5, 5)), False)]


def verifier_rotation_anneau_de_tranche() -> list[str]:
    """D5 : un anneau vu par la tranche n'est pas proposé au survol."""
    return avec_document("VerifRotationTranche", _anneau_de_tranche)


def _piece_pilotee(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    piece.setExpression("Placement.Base.x", "100 mm")
    doc.recompute()
    vue_isometrique()
    selection_dessinee(piece)
    return [
        *ecarts("pièce pilotée : flèches gardées", session.active, True),
        *ecarts("pièce pilotée : aucun anneau", session.layout.rings, ()),
        *ecarts("pièce pilotée : nœud des flèches posé", noeuds_incrustes(), 1),
    ]


def verifier_rotation_piece_pilotee() -> list[str]:
    """D6 : une expression sur le ``Placement`` supprime les anneaux."""
    return avec_document("VerifRotationPilotee", _piece_pilotee)


# --- D2, D3, D4 : le geste ---------------------------------------------------------------


def _geste_hors_panneau(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    vue_isometrique()
    selection_dessinee(piece)
    avant, centre_avant = App.Placement(piece.Placement), centre(piece)
    pris, depart = saisir_anneau(session, 2)
    etat = type(session.state).__name__, session.state.key
    problemes = [
        *ecarts("clic sur l'anneau Z consommé", pris, True),
        *ecarts("état Rotating", etat, ("Rotating", "ring2")),
        *ecarts("geste en cours", session.dragging, True),
    ]
    arrivee = tourner_de(session, 2, 34.0, depart)
    # aimant tous les 15° : 34° donne 30°
    problemes += proche("aimant : 34° donne 30°", lacet(piece), 30.0, 0.01)
    sweep = session.state.sweep
    problemes += [
        *ecarts("secteur et angle gardés", sweep is not None and sweep.angle, 30.0),
        *ecarts("angle écrit", angle_label(30.0), "30°"),
        *ecarts("incrustation : un seul nœud", noeuds_incrustes(), 1),
        *ecarts("anneaux gardés pendant le geste", len(session.layout.rings), 3),
    ]
    problemes += ecarts("centre immobile", centre(piece), centre_avant)
    tourner_de(session, 2, 34.0, depart, shift=True)
    problemes += proche("Maj : angle libre", lacet(piece), 34.0, TOLERANCE)
    session.shift_changed(False)
    problemes += proche("Maj relâchée : aimant", lacet(piece), 30.0, 0.01)
    problemes += ecarts("relâchement consommé", session.release(arrivee), True)
    problemes += [
        *ecarts("geste fini", session.dragging, False),
        *ecarts("une transaction", doc.UndoNames, [TRANSACTION]),
        *ecarts("centre immobile après relâchement", centre(piece), centre_avant),
        *ecarts("seul le Placement a tourné", round(piece.Length.Value, 3), 800.0),
    ]
    doc.undo()
    problemes += ecarts("Ctrl+Z : un seul pas", piece.Placement == avant, True)
    return problemes


def verifier_rotation_geste_hors_panneau() -> list[str]:
    """D2 à D4 : clic sur l'anneau, aimant à 15°, Maj libre, centre fixe, transaction
    « Tourner la pièce », un Ctrl+Z."""
    return avec_document("VerifRotationGeste", _geste_hors_panneau)


def _geste_dans_le_panneau(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    vue_isometrique()
    Gui.Selection.clearSelection()
    ouvrir_par_double_clic(piece)
    QtCore.QCoreApplication.processEvents()
    avant, transaction = App.Placement(piece.Placement), App.getActiveTransaction()
    relectures: list[int] = []
    panneau = session.panel
    session.panel = dataclasses.replace(panneau, refresh=lambda: relectures.append(1))
    pris, depart = saisir_anneau(session, 2)
    arrivee = tourner_de(session, 2, 45.0, depart)
    problemes = [
        *ecarts("clic sur l'anneau consommé", pris, True),
        *proche("pièce tournée de 45°", lacet(piece), 45.0, 0.01),
        *ecarts("le panneau relit ses champs", len(relectures) > 0, True),
    ]
    problemes += ecarts("relâchement consommé", session.release(arrivee), True)
    problemes += [
        *ecarts("transaction du panneau", App.getActiveTransaction(), transaction),
        *ecarts("pas de transaction propre", TRANSACTION in doc.UndoNames, False),
    ]
    session.panel = panneau  # clear_panel compare l'identité du contexte
    annuler()
    return [*problemes, *ecarts("« Annuler » ramène la pièce", piece.Placement == avant, True)]


def verifier_rotation_geste_dans_le_panneau() -> list[str]:
    """D4 : panneau ouvert, le geste écrit dans la transaction du panneau, qui relit ses champs."""
    return avec_document("VerifRotationPanneau", _geste_dans_le_panneau)


def _echap(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    vue_isometrique()
    selection_dessinee(piece)
    avant = App.Placement(piece.Placement)
    _, depart = saisir_anneau(session, 0)
    arrivee = tourner_de(session, 0, 60.0, depart)
    problemes = ecarts("pièce tournée avant Échap", piece.Placement == avant, False)
    problemes += [
        *ecarts("Échap consommé", session.escape(), True),
        *ecarts("pièce revenue", piece.Placement == avant, True),
        *ecarts("geste fini", session.dragging, False),
        *ecarts("mouvement suivant consommé", session.move(arrivee), True),
        *ecarts("relâchement consommé", session.release(arrivee), True),
        *ecarts("puis rendu à FreeCAD", session.release(arrivee), False),
        *ecarts("historique inchangé", doc.UndoNames, []),
    ]
    return problemes


def verifier_rotation_echap() -> list[str]:
    """Échap ramène la pièce au début du geste, sans entrée d'annulation."""
    return avec_document("VerifRotationEchap", _echap)


# --- Le reste est rendu à FreeCAD --------------------------------------------------------


def _evenements_rendus(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    vue_isometrique()
    selection_dessinee(piece)
    viewport, filtre = vue_3d_active(doc), events._INSTALLATION.filter
    if viewport is None or filtre is None:
        return ["vue 3D ou filtre absents"]
    sur = viser_anneau(session, 1, DEPART)
    gauche, droit = QtCore.Qt.LeftButton, QtCore.Qt.RightButton
    press, move, release = (
        QtCore.QEvent.MouseButtonPress,
        QtCore.QEvent.MouseMove,
        QtCore.QEvent.MouseButtonRelease,
    )
    rendus = [
        ("clic gauche ailleurs", souris(viewport, press, (5, 5))),
        ("clic droit sur l'anneau", souris(viewport, press, sur, droit)),
        (
            "Ctrl + clic sur l'anneau",
            souris(viewport, press, sur, gauche, QtCore.Qt.ControlModifier),
        ),
        ("relâchement sans geste", souris(viewport, release, sur)),
        ("mouvement sans geste", souris(viewport, move, sur)),
    ]
    problemes = []
    for nom, evenement in rendus:
        problemes += ecarts(f"{nom} rendu", bool(filtre.eventFilter(viewport, evenement)), False)
    problemes += ecarts("aucun geste commencé", session.dragging, False)
    pris = filtre.eventFilter(viewport, souris(viewport, press, sur))
    problemes += ecarts("clic gauche sur l'anneau consommé", bool(pris), True)
    arrivee = viser_anneau(session, 1, DEPART + 50.0, sur)
    problemes += ecarts(
        "mouvement du geste consommé",
        filtre.eventFilter(viewport, souris(viewport, move, arrivee)),
        True,
    )
    problemes += ecarts(
        "relâchement consommé",
        filtre.eventFilter(viewport, souris(viewport, release, arrivee)),
        True,
    )
    problemes += ecarts("geste terminé", session.dragging, False)
    doc.undo()
    return problemes


def verifier_rotation_evenements_rendus() -> list[str]:
    """D2 : seul le clic gauche sur un anneau est consommé ; clic ailleurs, autre bouton, Ctrl,
    mouvements sans geste : rendus à FreeCAD."""
    return avec_document("VerifRotationRendus", _evenements_rendus)


# --- ADR 0026 : assemblage défait par une rotation ---------------------------------------


def _assemblage_defait(nom: str, supprimer: bool) -> list[str]:
    """Le voile, assemblé par tourillons à la joue gauche, tourné de 30° : la fenêtre de choix
    s'ouvre au relâchement (fonction de choix injectée) ; refus : la pièce revient, accord :
    l'assemblage disparaît et la rotation reste."""
    with pieces_du_bureau(nom) as bureau:
        doc = bureau.doc
        voile = bureau.parts["V"]
        joint = api.make_dowels(bureau.parts["JG"], voile)
        doc.recompute()
        session = preparer(doc)
        libelle, identifiant = joint.Label, joint.Name
        doc.clearUndos()
        vue_isometrique()
        avant = App.Placement(voile.Placement)
        selection_dessinee(bureau.shown("V"))
        pris, depart = saisir_anneau(session, 2)
        arrivee = tourner_de(session, 2, 30.0, depart)
        choix, original = Choix(supprimer), joint_choice.chooser
        problemes = [
            *ecarts("anneau saisi", pris, True),
            *ecarts("tirage : assemblage gardé", doc.getObject(identifiant) is not None, True),
        ]
        joint_choice.chooser = choix
        try:
            problemes += ecarts("relâchement consommé", session.release(arrivee), True)
        finally:
            joint_choice.chooser = original
        problemes += ecarts("fenêtre : assemblage cité", choix.recus, [[f"« {libelle} »"]])
        problemes += ecarts(
            "assemblage supprimé ou gardé", doc.getObject(identifiant) is None, supprimer
        )
        problemes += ecarts(
            "aucun objet en erreur", [o.Name for o in doc.Objects if "Invalid" in o.State], []
        )
        if supprimer:
            problemes += [
                *ecarts("rotation gardée", voile.Placement == avant, False),
                *ecarts("une seule transaction", doc.UndoNames, [TRANSACTION]),
            ]
            doc.undo()
            problemes += ecarts("Ctrl+Z : voile revenu", voile.Placement == avant, True)
        else:
            problemes += [
                *ecarts("pièce revenue", voile.Placement == avant, True),
                *ecarts("aucune transaction", TRANSACTION in doc.UndoNames, False),
            ]
        return [*problemes, *ecarts("session libre", session.dragging, False)]


def verifier_rotation_assemblage_defait() -> list[str]:
    """ADR 0026 : une rotation qui défait un assemblage passe par la fenêtre Annuler/Supprimer."""
    return [
        *_assemblage_defait("VerifRotationJointA", supprimer=False),
        *_assemblage_defait("VerifRotationJointB", supprimer=True),
    ]


VERIFICATIONS_SOURIS_ROTATION: tuple[Callable[[], list[str]], ...] = (
    verifier_rotation_anneaux_et_survol,
    verifier_rotation_anneau_de_tranche,
    verifier_rotation_piece_pilotee,
    verifier_rotation_geste_hors_panneau,
    verifier_rotation_geste_dans_le_panneau,
    verifier_rotation_echap,
    verifier_rotation_evenements_rendus,
    verifier_rotation_assemblage_defait,
)
