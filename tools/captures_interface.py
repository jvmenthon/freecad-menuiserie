# SPDX-License-Identifier: LGPL-2.1-or-later
"""Captures d'écran de l'atelier pour les PR : vue 3D, fenêtre complète, gros plan texture,
panneau de tâche de la pièce de bois et panneau d'un assemblage (``panneau-assemblage.png``).

Exécuté par FreeCAD lui-même, avec un serveur X virtuel (le rendu 3D a besoin d'OpenGL),
l'atelier étant installé dans le dossier ``Mod`` de ``FREECAD_USER_HOME`` :

    CAPTURES=dossier LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=softpipe \
        xvfb-run -a -s "-screen 0 1600x1000x24" freecad tools/captures_interface.py

Le pilote logiciel ``softpipe`` est nécessaire : avec ``llvmpipe`` (par défaut), la vue 3D
hors écran sort blanche ou tronquée.

Les images PNG sont écrites dans le dossier ``CAPTURES`` ; le fichier ``CAPTURES/OK`` signale
la réussite (la sortie standard est captée par la console de FreeCAD).

La scène utilise une bibliothèque utilisateur temporaire (paramètre ``UserLibraryPath``, rétabli
à la fin) qui ajoute un chêne muni d'une texture de test produite par le script : un quadrillage
tous les 100 mm, veiné dans le sens du fil (la largeur de l'image) et marqué « fil → ». Les
carreaux doivent mesurer 100 mm sur toutes les pièces, quelles que soient leurs cotes (gros plan
``texture.png``). Le meuble de ``vue-3d.png`` montre les photos des matériaux intégrés ; à côté,
un cadre (cadre de référence de la spécification J3) est assemblé par quatre tenons-mortaises,
traversants dans le montant de devant pour que leurs bouts soient visibles.
"""

import json
import os
import tempfile
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

QUADRILLE = "chene-quadrille"
# (longueur, largeur, épaisseur, matériau, repère, position en mm) : un petit caisson.
PIECES = (
    (800.0, 400.0, 22.0, "chene", "Dessus", (0.0, 0.0, 600.0)),
    (600.0, 400.0, 22.0, "chene", "Côté gauche", (22.0, 0.0, 0.0)),
    (600.0, 400.0, 22.0, "chene", "Côté droit", (800.0, 0.0, 0.0)),
    (756.0, 380.0, 19.0, "mdf", "Étagère", (22.0, 10.0, 280.0)),
    (756.0, 580.0, 8.0, "cp-bouleau", "Fond", (22.0, 400.0, 0.0)),
)
# Cadre assemblé : (repère, longueur, position x, y en mm, rotation autour de Z en degrés).
CADRE = (
    ("Montant avant", 600.0, 1000.0, 0.0, 0.0),
    ("Montant arrière", 600.0, 1000.0, 340.0, 0.0),
    ("Traverse gauche", 280.0, 1060.0, 60.0, 90.0),
    ("Traverse droite", 280.0, 1600.0, 60.0, 90.0),
)
# Tenons-mortaises (mortaise, tenon, traversant) du cadre.
TENONS = (
    ("Montant avant", "Traverse gauche", True),
    ("Montant avant", "Traverse droite", True),
    ("Montant arrière", "Traverse gauche", False),
    ("Montant arrière", "Traverse droite", False),
)
# Gros plan : deux planches de 800 sur 200 mm, fil en long puis en travers (décalage en Y).
PLANCHES = (("Length", 0.0), ("Width", 300.0))
TAILLE = (1600, 1000)
# Pièce ouverte dans le panneau de tâche : contreplaqué de 8 mm, hors épaisseur standard, pour
# montrer aussi l'avertissement.
PIECE_DU_PANNEAU = "Fond"
# Assemblage dont le panneau est capturé (premier tenon-mortaise du cadre, traversant).
ASSEMBLAGE_DU_PANNEAU = "Tenon-mortaise"
ATTENTE_DU_VOLET_MS = 1500
TEXTURE_MM = (600, 200)  # largeur (sens du fil) et hauteur couvertes par l'image
PIXELS_PAR_MM = 2
PAS_MM = 100
PARAMETRES = "User parameter:BaseApp/Preferences/Mod/Menuiserie"


def dessiner_quadrillage(chemin: Path) -> None:
    """Image de test : fond bois, veinage dans le sens de la largeur, quadrillage tous les
    100 mm et mention « fil → » dans le premier carreau."""
    from PySide import QtCore, QtGui

    largeur, hauteur = (cote * PIXELS_PAR_MM for cote in TEXTURE_MM)
    pas = PAS_MM * PIXELS_PAR_MM
    image = QtGui.QImage(largeur, hauteur, QtGui.QImage.Format.Format_RGB888)
    image.fill(QtGui.QColor("#E3C595"))
    peintre = QtGui.QPainter(image)
    peintre.setPen(QtGui.QPen(QtGui.QColor("#B98A57"), 2))
    for y in range(6, hauteur, 14):
        peintre.drawLine(0, y, largeur, y)
    peintre.setPen(QtGui.QPen(QtGui.QColor("#4A2C14"), 6))
    for x in range(0, largeur + 1, pas):
        peintre.drawLine(x, 0, x, hauteur)
    for y in range(0, hauteur + 1, pas):
        peintre.drawLine(0, y, largeur, y)
    peintre.setFont(QtGui.QFont("Sans", 36, QtGui.QFont.Weight.Bold))
    peintre.drawText(QtCore.QRect(0, 0, pas, pas), QtCore.Qt.AlignmentFlag.AlignCenter, "fil →")
    peintre.end()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(chemin), "PNG"):
        raise OSError(f"image non écrite : {chemin}")


@contextmanager
def bibliotheque_de_captures() -> Iterator[None]:
    """Bibliothèque utilisateur temporaire avec le chêne quadrillé ; rétablie à la fin."""
    from freecad.menuiserie.features.library import USER_LIBRARY_PARAM, reload_library

    parametres = App.ParamGet(PARAMETRES)
    precedent = parametres.GetString(USER_LIBRARY_PARAM, "")
    with tempfile.TemporaryDirectory() as dossier:
        fichier = Path(dossier) / "materiaux.json"
        dessiner_quadrillage(fichier.parent / "textures" / "quadrillage.png")
        quadrille = {
            "id": QUADRILLE,
            "kind": "solid",
            "name": "Chêne quadrillé (texture de test)",
            "density": 710,
            "thicknesses": [22],
            "color": "#B8875A",
            "texture": {"image": "textures/quadrillage.png", "size": list(TEXTURE_MM)},
        }
        contenu = {"format": 1, "materials": [quadrille]}
        fichier.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
        parametres.SetString(USER_LIBRARY_PARAM, str(fichier))
        try:
            reload_library()
            yield
        finally:
            parametres.SetString(USER_LIBRARY_PARAM, precedent)
            reload_library()


def construire() -> None:
    """Crée le document et ses pièces avec l'API publique de l'atelier."""
    from freecad.menuiserie import api

    doc = App.newDocument("Captures")
    for longueur, largeur, epaisseur, materiau, repere, position in PIECES:
        piece = api.make_wood_part(longueur, largeur, epaisseur, materiau, mark=repere, doc=doc)
        piece.Label = repere
        if repere in ("Côté gauche", "Côté droit"):
            # Les côtés sont debout : longueur verticale, largeur en profondeur.
            rotation = App.Rotation(App.Vector(0, 1, 0), -90)
            piece.Placement = App.Placement(App.Vector(*position), rotation)
        elif repere == "Fond":
            rotation = App.Rotation(App.Vector(1, 0, 0), 90)
            piece.Placement = App.Placement(App.Vector(*position), rotation)
        else:
            piece.Placement.Base = App.Vector(*position)
    doc.recompute()
    construire_le_cadre(doc)
    afficher_la_vue_du_document(doc.Name)
    Gui.Selection.clearSelection()


def construire_le_cadre(doc: Any) -> None:
    """Cadre à plat assemblé par quatre tenons-mortaises (fabrique de l'api)."""
    from freecad.menuiserie import api

    pieces = {}
    for repere, longueur, x, y, angle in CADRE:
        piece = api.make_wood_part(longueur, 60.0, 22.0, "chene", mark=repere, doc=doc)
        piece.Label = repere
        rotation = App.Rotation(App.Vector(0, 0, 1), angle)
        piece.Placement = App.Placement(App.Vector(x, y, 0.0), rotation)
        pieces[repere] = piece
    doc.recompute()
    for mortaise, tenon, traversant in TENONS:
        api.make_mortise_tenon(pieces[mortaise], pieces[tenon], through=traversant)


def afficher_la_vue_du_document(nom_document: str) -> None:
    """Met la vue 3D du document au premier plan, devant la page d'accueil."""
    from PySide import QtWidgets

    zone = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for fenetre in zone.subWindowList():
        if fenetre.windowTitle().startswith(nom_document):
            zone.setActiveSubWindow(fenetre)
    Gui.updateGui()


def construire_gros_plan() -> None:
    """Document « Texture » : deux planches quadrillées, fil en long puis en travers."""
    from freecad.menuiserie import api

    doc = App.newDocument("Texture")
    for fil, y in PLANCHES:
        planche = api.make_wood_part(800.0, 200.0, 22.0, QUADRILLE, mark=f"Fil {fil}", doc=doc)
        planche.Label = f"Fil {fil}"
        planche.GrainDirection = fil
        planche.Placement.Base = App.Vector(0.0, y, 0.0)
    doc.recompute()
    afficher_la_vue_du_document(doc.Name)
    Gui.Selection.clearSelection()


def capturer_gros_plan(dossier: Path) -> None:
    """Vue isométrique rapprochée des deux planches (texture et arêtes)."""
    vue = Gui.ActiveDocument.ActiveView
    vue.setCameraType("Orthographic")
    vue.viewIsometric()
    Gui.updateGui()
    vue.fitAll()
    Gui.updateGui()
    vue.saveImage(str(dossier / "texture.png"), TAILLE[0], TAILLE[1], "White")


def capturer(dossier: Path) -> None:
    """Vue 3D isométrique seule, puis fenêtre complète (arbre, propriétés, vue)."""
    fenetre = Gui.getMainWindow()
    fenetre.resize(*TAILLE)
    fenetre.showMaximized()
    Gui.updateGui()
    vue = Gui.ActiveDocument.ActiveView
    vue.setCameraType("Orthographic")
    vue.viewIsometric()
    Gui.updateGui()
    vue.fitAll()
    Gui.updateGui()
    vue.saveImage(str(dossier / "vue-3d.png"), TAILLE[0], TAILLE[1], "White")
    # La fenêtre montre aussi l'arbre et les propriétés de la première pièce.
    Gui.Selection.addSelection(App.ActiveDocument.Objects[0])
    Gui.updateGui()
    fenetre_complete(fenetre, vue).save(str(dossier / "fenetre.png"))
    capturer_le_panneau(dossier, fenetre, vue)


def capturer_le_panneau(dossier: Path, fenetre, vue) -> None:
    """Fenêtre complète avec le panneau de tâche ouvert sur une pièce (comme au double-clic)."""
    Gui.Selection.clearSelection()
    piece = App.ActiveDocument.getObjectsByLabel(PIECE_DU_PANNEAU)[0]
    Gui.ActiveDocument.setEdit(piece, 0)
    Gui.updateGui()
    volet = volet_des_taches(fenetre)
    fenetre_complete(fenetre, vue, devant=volet).save(str(dossier / "panneau.png"))
    Gui.Control.activeTaskDialog().reject()
    capturer_le_panneau_d_assemblage(dossier, fenetre, vue)


def capturer_le_panneau_d_assemblage(dossier: Path, fenetre, vue) -> None:
    """Fenêtre complète avec le panneau d'un tenon-mortaise du cadre (comme au double-clic)."""
    assemblage = App.ActiveDocument.getObjectsByLabel(ASSEMBLAGE_DU_PANNEAU)[0]
    Gui.ActiveDocument.setEdit(assemblage, 0)
    Gui.updateGui()
    volet = volet_des_taches(fenetre)
    image = fenetre_complete(fenetre, vue, devant=volet)
    image.save(str(dossier / "panneau-assemblage.png"))
    Gui.Control.activeTaskDialog().reject()


def volet_des_taches(fenetre):
    """Volet « Tasks », une fois affiché. FreeCAD 1.1 le place dans un panneau superposé à la
    vue 3D, qui glisse depuis le bord de la fenêtre : on laisse l'animation se terminer."""
    from PySide import QtCore, QtGui

    boucle = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ATTENTE_DU_VOLET_MS, boucle.quit)
    boucle.exec()
    return fenetre.findChild(QtGui.QDockWidget, "Tasks")


def fenetre_complete(fenetre, vue, devant=None):
    """Capture de la fenêtre où la zone OpenGL, que ``grab()`` laisse vide, est remplacée
    par un rendu de la vue 3D à la même taille ; ``devant`` (widget superposé à la vue 3D,
    comme le volet des tâches de FreeCAD 1.1) est redessiné par-dessus."""
    from PySide import QtCore, QtGui

    image = fenetre.grab()
    zone_3d = vue.graphicsView()
    origine = zone_3d.mapTo(fenetre, QtCore.QPoint(0, 0))
    with tempfile.TemporaryDirectory() as dossier:
        rendu = os.path.join(dossier, "vue.png")
        vue.saveImage(rendu, zone_3d.width(), zone_3d.height(), "Current")
        peintre = QtGui.QPainter(image)
        peintre.drawImage(origine, QtGui.QImage(rendu))
        if devant is not None:
            peintre.drawPixmap(devant.mapTo(fenetre, QtCore.QPoint(0, 0)), devant.grab())
        peintre.end()
    return image


def main() -> None:
    dossier = Path(os.environ.get("CAPTURES", "captures")).resolve()
    dossier.mkdir(parents=True, exist_ok=True)
    try:
        Gui.activateWorkbench("MenuiserieWorkbench")
        with bibliotheque_de_captures():
            construire()
            capturer(dossier)
            construire_gros_plan()
            capturer_gros_plan(dossier)
        (dossier / "OK").write_text("OK\n", encoding="utf-8")
    except Exception:
        (dossier / "ERREUR").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        # Sortie immédiate : fermer la fenêtre demanderait d'enregistrer le document.
        os._exit(0)


main()
