# SPDX-License-Identifier: LGPL-2.1-or-later
"""Captures d'écran de l'atelier pour les PR : vue 3D et fenêtre complète de FreeCAD.

Exécuté par FreeCAD lui-même, avec un serveur X virtuel (le rendu 3D a besoin d'OpenGL),
l'atelier étant installé dans le dossier ``Mod`` de ``FREECAD_USER_HOME`` :

    CAPTURES=dossier LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=softpipe \
        xvfb-run -a -s "-screen 0 1600x1000x24" freecad tools/captures_interface.py

Le pilote logiciel ``softpipe`` est nécessaire : avec ``llvmpipe`` (par défaut), la vue 3D
hors écran sort blanche ou tronquée.

Les images PNG sont écrites dans le dossier ``CAPTURES`` ; le fichier ``CAPTURES/OK`` signale
la réussite (la sortie standard est captée par la console de FreeCAD).
"""

import os
import tempfile
import traceback
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui

# (longueur, largeur, épaisseur, matériau, repère, position en mm) : un petit caisson.
PIECES = (
    (800.0, 400.0, 22.0, "chene", "Dessus", (0.0, 0.0, 600.0)),
    (600.0, 400.0, 22.0, "chene", "Côté gauche", (22.0, 0.0, 0.0)),
    (600.0, 400.0, 22.0, "chene", "Côté droit", (800.0, 0.0, 0.0)),
    (756.0, 380.0, 19.0, "mdf", "Étagère", (22.0, 10.0, 280.0)),
    (756.0, 580.0, 8.0, "cp-bouleau", "Fond", (22.0, 400.0, 0.0)),
)
TAILLE = (1600, 1000)


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
    afficher_la_vue_du_document(doc.Name)
    Gui.Selection.clearSelection()


def afficher_la_vue_du_document(nom_document: str) -> None:
    """Met la vue 3D du document au premier plan, devant la page d'accueil."""
    from PySide import QtWidgets

    zone = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for fenetre in zone.subWindowList():
        if fenetre.windowTitle().startswith(nom_document):
            zone.setActiveSubWindow(fenetre)
    Gui.updateGui()


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


def fenetre_complete(fenetre, vue):
    """Capture de la fenêtre où la zone OpenGL, que ``grab()`` laisse vide, est remplacée
    par un rendu de la vue 3D à la même taille."""
    from PySide import QtCore, QtGui

    image = fenetre.grab()
    zone_3d = vue.graphicsView()
    origine = zone_3d.mapTo(fenetre, QtCore.QPoint(0, 0))
    with tempfile.TemporaryDirectory() as dossier:
        rendu = os.path.join(dossier, "vue.png")
        vue.saveImage(rendu, zone_3d.width(), zone_3d.height(), "Current")
        peintre = QtGui.QPainter(image)
        peintre.drawImage(origine, QtGui.QImage(rendu))
        peintre.end()
    return image


def main() -> None:
    dossier = Path(os.environ.get("CAPTURES", "captures")).resolve()
    dossier.mkdir(parents=True, exist_ok=True)
    try:
        Gui.activateWorkbench("MenuiserieWorkbench")
        construire()
        capturer(dossier)
        (dossier / "OK").write_text("OK\n", encoding="utf-8")
    except Exception:
        (dossier / "ERREUR").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        # Sortie immédiate : fermer la fenêtre demanderait d'enregistrer le document.
        os._exit(0)


main()
