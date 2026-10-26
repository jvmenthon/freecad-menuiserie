# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du glissement à la souris (SM-c, issue #65, critères C1 à C7).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Hors écran, tout clic
ou mouvement traité par FreeCAD le fait planter (cube de navigation) : les vérifications
appellent directement la session (``DragSession.press``, ``move``, ``release``, ``escape``) ou le
filtre d'évènements pour les seuls évènements qu'il consomme ou qu'il rend (appel direct de
``eventFilter``, jamais ``sendEvent``). Le critère C8 est une recette manuelle.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.gui.drag import events, overlay
from tests.gui.verifications_assemblages import selectionner
from tests.gui.verifications_double_clic import vue_3d_active
from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    choisir,
    creer_par_la_commande,
    ecarts,
    formulaire,
    ouvrir_par_double_clic,
    piece_validee,
    valeur,
    valider,
)

ATELIER = "MenuiserieWorkbench"
AUCUN_ATELIER = "NoneWorkbench"
TRANSACTION = "Déplacer la pièce"
LARGEUR = 2.0  # écart toléré, en pixels de l'écran, sur une position obtenue par la souris
Point = tuple[int, int]


def preparer(doc: Any) -> Any:
    """Atelier actif, vue 3D de ``doc`` active et cadrée ; renvoie la session du glissement."""
    Gui.activateWorkbench(ATELIER)
    vue_3d_active(doc)
    Gui.activeView().fitAll()
    QtGui.QApplication.processEvents()
    return events.current_session()


def cadrer() -> None:
    """Vue cadrée sur le contenu du document (les flèches ont alors une taille lisible)."""
    Gui.activeView().fitAll()
    QtGui.QApplication.processEvents()


def selection_dessinee(*objets: Any) -> None:
    """Sélectionne ``objets``, laisse l'observateur dessiner (sa notification est différée)."""
    cadrer()
    selectionner(*objets)
    QtGui.QApplication.processEvents()


def noeuds_incrustes() -> int:
    """Nombre de nœuds d'incrustation du glissement dans la vue 3D active."""
    from pivy import coin

    recherche = coin.SoSearchAction()
    recherche.setName(overlay.NODE_NAME)
    recherche.setInterest(coin.SoSearchAction.ALL)
    recherche.apply(Gui.activeView().getSceneGraph())
    return int(recherche.getPaths().getLength())


def pixel(session: Any, x: float, y: float, z: float) -> Point:
    px, py = session.port.project(type(session.layout.frame.origin)(x, y, z))
    return round(px), round(py)


def sur_la_fleche(session: Any, axe: int, distance: float) -> Point:
    """Pixel du point de la flèche ``axe`` à ``distance`` mm de son départ."""
    f = next(a for a in session.layout.arrows if a.axis == axe)
    s, e = _xyz(f.start), _xyz(f.end)
    longueur = sum((e[i] - s[i]) ** 2 for i in range(3)) ** 0.5
    return pixel(session, *(s[i] + (e[i] - s[i]) * distance / longueur for i in range(3)))


def sur_la_poignee(session: Any, axe: int, fin: bool) -> Point:
    """Pixel de la poignée (``axe``, ``fin``)."""
    point = next(p for h, p in session.layout.handles if (h.axis, h.at_end) == (axe, fin))
    return pixel(session, *_xyz(point))


def _xyz(v: Any) -> tuple[float, float, float]:
    return float(v.x), float(v.y), float(v.z)


def _parametre(session: Any, ligne: Any, point: Point) -> float:
    from freecad.menuiserie.core.magnet import axis_param

    valeur = axis_param(session.ray(point), ligne)
    if valeur is None:
        raise ValueError("rayon parallèle à l'axe")
    return float(valeur)


def viser(session: Any, ligne: Any, valeur: float, depart: Point) -> Point:
    """Pixel dont le rayon de la souris coupe ``ligne`` au paramètre ``valeur`` (Newton depuis
    ``depart``). Hors écran, ``getPoint`` et ``getPointOnScreen`` n'ont pas la même échelle (pas
    de contexte OpenGL) : on vise le rayon, qui est ce que le glissement lit."""
    x, y = depart
    for _ in range(5):
        base = _parametre(session, ligne, (x, y))
        gx = _parametre(session, ligne, (x + 1, y)) - base
        gy = _parametre(session, ligne, (x, y + 1)) - base
        norme = gx * gx + gy * gy
        if norme == 0:
            break
        x, y = round(x - (base - valeur) * gx / norme), round(y - (base - valeur) * gy / norme)
    return x, y


def saisir(session: Any, cle_pixel: Point) -> bool:
    """Clic gauche enfoncé au pixel (la session lit ensuite l'axe et le point saisis)."""
    return bool(session.press(cle_pixel))


def tirer(session: Any, mm: float, *, shift: bool = False, deplacer: bool = True) -> Point:
    """Souris placée pour que la cible saisie soit tirée de ``mm`` mm depuis le point saisi."""
    etat = session.state
    point = viser(session, etat.line, etat.origin + mm, etat.cursor)
    if deplacer:
        session.move(point, shift)
    return point


def px_en_mm(session: Any) -> float:
    return float(session.port.mm(session.layout.frame.origin, 1.0))


def place(piece: Any) -> tuple[float, float, float]:
    base = piece.Placement.Base
    return round(base.x, 3), round(base.y, 3), round(base.z, 3)


def proche(nom: str, obtenu: float, attendu: float, tolerance: float) -> list[str]:
    ok = abs(obtenu - attendu) <= tolerance
    return [] if ok else [f"{nom} : {obtenu:.3f} au lieu de {attendu:.3f} (± {tolerance:.3f})"]


def souris(
    viewport: Any,
    type_: Any,
    point: Point,
    bouton: Any = QtCore.Qt.LeftButton,
    modifs: Any = QtCore.Qt.NoModifier,
) -> Any:
    """Évènement de souris au pixel de FreeCAD ``point`` de ``viewport``. Les boutons enfoncés
    sont ceux de l'évènement (aucun pour un mouvement sans bouton)."""
    qx, qy = point[0], viewport.height() - 1 - point[1]
    boutons = QtCore.Qt.NoButton if type_ == QtCore.QEvent.MouseButtonRelease else bouton
    if type_ == QtCore.QEvent.MouseMove:
        bouton = QtCore.Qt.NoButton
    return QtGui.QMouseEvent(
        type_,
        QtCore.QPointF(qx, qy),
        QtCore.QPointF(viewport.mapToGlobal(QtCore.QPoint(qx, qy))),
        bouton,
        boutons,
        modifs,
    )


# --- C1 : filtre, observateur, flèches --------------------------------------------------


def _fleches_suivent_la_selection(doc: Any) -> list[str]:
    session = preparer(doc)
    if session is None:
        return ["session absente : atelier actif sans filtre de glissement"]
    piece = piece_validee(doc)
    autre = piece_validee(doc)
    problemes = [*ecarts("filtre et observateur posés", events.installed(), True)]
    selection_dessinee(piece)
    problemes += [
        *ecarts("une pièce : flèches actives", session.active, True),
        *ecarts("une pièce : trois flèches", len(session.layout.arrows), 3),
        *ecarts("hors panneau : aucune poignée", len(session.layout.handles), 0),
        *ecarts("nœud posé dans la vue", noeuds_incrustes(), 1),
    ]
    selection_dessinee(piece, autre)
    problemes += ecarts("deux pièces : pas de flèches", session.active, False)
    problemes += ecarts("deux pièces : nœud retiré", noeuds_incrustes(), 0)
    selection_dessinee(piece)
    Gui.Selection.clearSelection()
    QtGui.QApplication.processEvents()
    problemes += ecarts("sélection vidée : flèches enlevées", session.active, False)
    selection_dessinee(piece)
    Gui.activateWorkbench(AUCUN_ATELIER)
    try:
        problemes += [
            *ecarts("atelier quitté : filtre retiré", events.installed(), False),
            *ecarts("atelier quitté : plus de session", events.current_session() is None, True),
            *ecarts("atelier quitté : nœud retiré", noeuds_incrustes(), 0),
        ]
    finally:
        Gui.activateWorkbench(ATELIER)
    return [*problemes, *ecarts("atelier repris : filtre posé", events.installed(), True)]


def verifier_souris_fleches_et_filtre() -> list[str]:
    """C1 : filtre et observateur posés avec l'atelier et retirés avec lui ; flèches de la seule
    pièce sélectionnée."""
    return avec_document("VerifSourisFleches", _fleches_suivent_la_selection)


def _poignees_du_panneau(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    Gui.Selection.clearSelection()
    cadrer()
    ouvrir_par_double_clic(piece)
    QtGui.QApplication.processEvents()
    form = formulaire()
    problemes = [
        *ecarts("panneau : flèches", len(session.layout.arrows), 3),
        *ecarts("massif : six poignées", len(session.layout.handles), 6),
        *ecarts(
            "massif : poignées d'épaisseur",
            sorted((h.axis, h.at_end) for h, _ in session.layout.handles if h.axis == 2),
            [(2, False), (2, True)],
        ),
    ]
    choisir(form.materialCombo, "mdf")
    session.sync()
    problemes += [
        *ecarts("panneau MDF : quatre poignées", len(session.layout.handles), 4),
        *ecarts(
            "panneau MDF : aucune poignée d'épaisseur",
            [h for h, _ in session.layout.handles if h.axis == 2],
            [],
        ),
    ]
    choisir(form.materialCombo, "hetre")
    session.sync()
    problemes += ecarts("massif de nouveau : six poignées", len(session.layout.handles), 6)
    annuler()
    QtGui.QApplication.processEvents()
    problemes += ecarts(
        "panneau fermé : poignées enlevées",
        session.layout is None or not session.layout.handles,
        True,
    )
    return problemes


def verifier_souris_poignees_du_panneau() -> list[str]:
    """C1 : panneau de la pièce ouvert, flèches et poignées (six pour le massif, quatre pour un
    panneau de MDF) ; fermé, poignées enlevées."""
    return avec_document("VerifSourisPoignees", _poignees_du_panneau)


# --- C2, C7 : déplacer par une flèche ----------------------------------------------------


def _deplacement_hors_panneau(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    avant = place(piece)
    selection_dessinee(piece)
    pas = px_en_mm(session)
    survol = sur_la_fleche(session, 0, 40.0)
    session.move(survol)
    etat = type(session.state).__name__, session.state.key
    problemes_survol = ecarts("survol de la flèche X", etat, ("Hover", "arrow0"))
    session.move((5, 5))
    problemes_survol += ecarts("souris ailleurs", type(session.state).__name__, "Idle")
    consomme = saisir(session, survol)
    voulu = tirer(session, 150.0, deplacer=False)
    suit = session.move(voulu)
    mid = place(piece)
    problemes = [
        *problemes_survol,
        *ecarts("clic sur la flèche X consommé", consomme, True),
        *ecarts("mouvement consommé", suit, True),
        *proche("la pièce suit la flèche (x)", mid[0], avant[0] + 150.0, 3 * pas),
        *ecarts("sur l'axe seulement (y, z)", (mid[1], mid[2]), (avant[1], avant[2])),
    ]
    problemes += ecarts("relâchement consommé", session.release(voulu), True)
    problemes += ecarts("une transaction", doc.UndoNames, [TRANSACTION])
    doc.undo()
    return [*problemes, *ecarts("Ctrl+Z : en une étape", place(piece), avant)]


def verifier_souris_deplacer_hors_panneau() -> list[str]:
    """C2, C7 : flèche tirée hors panneau, transaction « Déplacer la pièce », un seul Ctrl+Z."""
    return avec_document("VerifSourisDeplacer", _deplacement_hors_panneau)


def _deplacement_dans_le_panneau(doc: Any, valider_puis_annuler: bool) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    avant = place(piece)
    Gui.Selection.clearSelection()
    cadrer()
    ouvrir_par_double_clic(piece)
    QtGui.QApplication.processEvents()
    transaction = App.getActiveTransaction()
    pas = px_en_mm(session)
    problemes = [*ecarts("flèche saisie", saisir(session, sur_la_fleche(session, 0, 40.0)), True)]
    voulu = tirer(session, 100.0)
    problemes += proche("pièce déplacée", place(piece)[0], avant[0] + 100.0, 3 * pas)
    problemes += ecarts("relâchement consommé", session.release(voulu), True)
    problemes += ecarts("transaction du panneau", App.getActiveTransaction(), transaction)
    problemes += ecarts("pas de transaction propre", TRANSACTION in doc.UndoNames, False)
    if valider_puis_annuler:
        valider()
        problemes += ecarts("OK : une étape", len(doc.UndoNames), 1)
        doc.undo()
    else:
        annuler()
    return [*problemes, *ecarts("retour à l'état d'avant le panneau", place(piece), avant)]


def verifier_souris_deplacer_dans_le_panneau() -> list[str]:
    """C2, C7 : panneau ouvert, même geste dans la transaction du panneau ; « Annuler »
    ramène la pièce."""
    return [
        *avec_document("VerifSourisPanneauA", lambda d: _deplacement_dans_le_panneau(d, False)),
        *avec_document("VerifSourisPanneauB", lambda d: _deplacement_dans_le_panneau(d, True)),
    ]


# --- C3 : le reste est rendu à FreeCAD -------------------------------------------------


def _evenements_rendus(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    selection_dessinee(piece)
    viewport = vue_3d_active(doc)
    filtre = events._INSTALLATION.filter
    if viewport is None or filtre is None:
        return ["vue 3D ou filtre absents"]
    sur = sur_la_fleche(session, 0, 40.0)
    loin = (5, 5)
    gauche, droit, milieu = QtCore.Qt.LeftButton, QtCore.Qt.RightButton, QtCore.Qt.MiddleButton
    press, move, release = (
        QtCore.QEvent.MouseButtonPress,
        QtCore.QEvent.MouseMove,
        QtCore.QEvent.MouseButtonRelease,
    )
    rendus = [
        ("clic gauche ailleurs", souris(viewport, press, loin)),
        ("mouvement sans glissement", souris(viewport, move, loin)),
        ("clic droit sur la flèche", souris(viewport, press, sur, droit)),
        ("clic du milieu sur la flèche", souris(viewport, press, sur, milieu)),
        (
            "Ctrl + clic sur la flèche",
            souris(viewport, press, sur, gauche, QtCore.Qt.ControlModifier),
        ),
        ("relâchement sans glissement", souris(viewport, release, loin)),
    ]
    problemes = []
    for nom, evenement in rendus:
        problemes += ecarts(f"{nom} rendu", bool(filtre.eventFilter(viewport, evenement)), False)
    problemes += ecarts("pas de glissement commencé", session.dragging, False)
    pris = filtre.eventFilter(viewport, souris(viewport, press, sur))
    problemes += ecarts("clic gauche sur la flèche consommé", bool(pris), True)
    voulu = tirer(session, 50.0, deplacer=False)
    problemes += ecarts(
        "mouvement du glissement consommé",
        filtre.eventFilter(viewport, souris(viewport, move, voulu)),
        True,
    )
    problemes += ecarts(
        "relâchement consommé", filtre.eventFilter(viewport, souris(viewport, release, voulu)), True
    )
    problemes += ecarts("glissement terminé", session.dragging, False)
    doc.undo()
    return problemes


def verifier_souris_evenements_rendus() -> list[str]:
    """C3 : clic ailleurs, autres boutons, Ctrl, mouvements sans glissement : rendus à FreeCAD
    (le filtre répond faux) ; seul le clic gauche sur une flèche est pris."""
    return avec_document("VerifSourisRendus", _evenements_rendus)


# --- C4 : poignées -----------------------------------------------------------------------


def _poignee(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = creer_par_la_commande(doc)
    Gui.activeView().fitAll()
    QtGui.QApplication.processEvents()
    session.sync()
    form = formulaire()
    pas = px_en_mm(session)
    longueur = piece.Length.Value
    origine = place(piece)
    problemes = [
        *ecarts("poignée de fin saisie", saisir(session, sur_la_poignee(session, 0, True)), True)
    ]
    arret = tirer(session, 60.0)
    problemes += proche("longueur étirée", piece.Length.Value, longueur + 60.0, 3 * pas)
    problemes += proche("champ de la longueur", valeur(form.lengthEdit), piece.Length.Value, 0.01)
    problemes += ecarts("début immobile", place(piece), origine)
    problemes += ecarts("aperçu à 60 %", piece.ViewObject.Transparency, 60)
    session.release(arret)
    longueur = piece.Length.Value
    problemes += ecarts(
        "poignée de début saisie", saisir(session, sur_la_poignee(session, 0, False)), True
    )
    arret = tirer(session, 40.0)
    problemes += proche("longueur raccourcie", piece.Length.Value, longueur - 40.0, 3 * pas)
    problemes += proche("origine décalée", piece.Placement.Base.x, origine[0] + 40.0, 3 * pas)
    problemes += proche(
        "bout fixe", piece.Placement.Base.x + piece.Length.Value, origine[0] + longueur, 0.01
    )
    session.release(arret)
    problemes += ecarts("aperçu toujours à 60 %", piece.ViewObject.Transparency, 60)
    problemes += ecarts("épaisseur intacte", round(piece.Thickness.Value, 3), 22.0)
    return [*problemes, *_poignee_d_epaisseur(session, piece, form)]


def _poignee_d_epaisseur(session: Any, piece: Any, form: Any) -> list[str]:
    """Massif (chêne) : la poignée du dessus change l'épaisseur, la face du dessous reste et le
    champ du panneau suit ; Échap la rétablit. La vue est isométrique : en vue de dessus, l'axe
    de l'épaisseur est vu de bout et ses poignées ne se saisissent pas (comme une flèche vue de
    bout)."""
    Gui.activeView().viewIsometric()
    cadrer()
    pas = px_en_mm(session)
    epaisseur, dessous = piece.Thickness.Value, piece.Placement.Base.z
    pris = saisir(session, sur_la_poignee(session, 2, True))
    problemes = ecarts("poignée du dessus saisie", pris, True)
    if not pris:
        return problemes
    tirer(session, 8.0)
    problemes += proche("épaisseur étirée", piece.Thickness.Value, epaisseur + 8.0, 3 * pas)
    problemes += proche(
        "champ de l'épaisseur", valeur(form.thicknessEdit), piece.Thickness.Value, 0.01
    )
    problemes += proche("face du dessous immobile", piece.Placement.Base.z, dessous, 0.01)
    problemes += ecarts("Échap consommé", session.escape(), True)
    problemes += proche("épaisseur rétablie", piece.Thickness.Value, epaisseur, 0.01)
    problemes += proche("champ rétabli", valeur(form.thicknessEdit), epaisseur, 0.01)
    return problemes


def verifier_souris_poignees() -> list[str]:
    """C4 : poignée tirée, la cote et son champ suivent, l'autre bout reste, aperçu posé ;
    poignée d'épaisseur du massif."""
    return avec_document("VerifSourisPoignee", _poignee)


# --- C5 : aimant et guides ---------------------------------------------------------------


def _aimant(doc: Any) -> list[str]:
    from freecad.menuiserie.api import make_wood_part

    session = preparer(doc)
    piece = piece_validee(doc)
    voisine = make_wood_part(300, 200, 22, "chene", doc=doc)
    voisine.Placement = App.Placement(App.Vector(850, 0, 0), App.Rotation())
    doc.recompute()
    Gui.activeView().fitAll()
    selection_dessinee(piece)
    tolerance = float(session.port.mm(session.layout.frame.origin, 10.0))
    pas = px_en_mm(session)
    # Le bout de la pièce (800) est à 50 mm de la voisine (850) : tirée de 50 - 0,4 tolérance, il
    # se colle à 850.
    demande = 50.0 - 0.4 * tolerance
    problemes = [*ecarts("flèche saisie", saisir(session, sur_la_fleche(session, 0, 40.0)), True)]
    voulu = tirer(session, demande)
    problemes += proche("face collée à la voisine", place(piece)[0], 50.0, 0.01)
    problemes += ecarts("guide en surbrillance", len(session.lit) > 0, True)
    tirer(session, demande, shift=True)
    problemes += proche("Maj : pas d'aimant", place(piece)[0], demande, 3 * pas)
    problemes += ecarts("Maj : aucun guide dessiné", len(session.lit), 0)
    session.shift_changed(False)
    problemes += proche("Maj relâchée : l'aimant revient", place(piece)[0], 50.0, 0.01)
    session.release(voulu)
    doc.undo()
    return problemes


def verifier_souris_aimant() -> list[str]:
    """C5 : face aimantée contre la voisine, guide allumé ; Maj coupe l'aimant et le dessin."""
    return avec_document("VerifSourisAimant", _aimant)


# --- C6 : Échap --------------------------------------------------------------------------


def _echap(doc: Any, panneau: bool) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    avant = place(piece)
    if panneau:
        Gui.Selection.clearSelection()
        cadrer()
        ouvrir_par_double_clic(piece)
    else:
        selection_dessinee(piece)
    QtGui.QApplication.processEvents()
    annulations = list(doc.UndoNames)
    problemes = [*ecarts("flèche Y saisie", saisir(session, sur_la_fleche(session, 1, 40.0)), True)]
    voulu = tirer(session, 100.0)
    problemes += ecarts("pièce déplacée avant Échap", place(piece) != avant, True)
    problemes += ecarts("Échap consommé", session.escape(), True)
    problemes += ecarts("pièce revenue", place(piece), avant)
    problemes += ecarts("glissement fini", session.dragging, False)
    problemes += ecarts("mouvement suivant consommé", session.move(voulu), True)
    problemes += ecarts("relâchement consommé", session.release(voulu), True)
    problemes += ecarts("puis rendu à FreeCAD", session.release(voulu), False)
    problemes += ecarts("historique inchangé", TRANSACTION in doc.UndoNames, False)
    if not panneau:
        problemes += ecarts("historique : rien de plus", len(doc.UndoNames), len(annulations))
    problemes += ecarts("panneau", bool(Gui.Control.activeDialog()), panneau)
    if panneau:
        annuler()
    return problemes


def verifier_souris_echap() -> list[str]:
    """C6 : Échap ramène la pièce là où elle était, hors panneau et panneau ouvert."""
    return [
        *avec_document("VerifSourisEchapA", lambda d: _echap(d, False)),
        *avec_document("VerifSourisEchapB", lambda d: _echap(d, True)),
    ]


VERIFICATIONS_SOURIS: tuple[Callable[[], list[str]], ...] = (
    verifier_souris_fleches_et_filtre,
    verifier_souris_poignees_du_panneau,
    verifier_souris_deplacer_hors_panneau,
    verifier_souris_deplacer_dans_le_panneau,
    verifier_souris_evenements_rendus,
    verifier_souris_poignees,
    verifier_souris_aimant,
    verifier_souris_echap,
)
