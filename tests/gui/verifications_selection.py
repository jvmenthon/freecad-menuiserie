# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de l'accrochage à la sélection (J6d, critères T1 à T8).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification
renvoie la liste de ses problèmes. La sélection est faite comme par un script
(``Gui.Selection.addSelection``) puis la commande est lancée ; l'ordre des widgets se lit dans
les dispositions du formulaire (la géométrie n'est pas calculée hors écran).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
import Part

from freecad.menuiserie import api
from tests.gui.verifications_apercu import BOUTONS, cliquer, memes_placements
from tests.gui.verifications_panneau import (
    CREATE,
    annuler,
    avec_document,
    creer_par_la_commande,
    ecarts,
    formulaire,
    saisir,
    valeur,
    valider,
)
from tests.gui.verifications_panneau_ensemble import bureau_regroupe, vue_rapport

TOLERANCE = 0.01


def cube(doc: Any, taille: tuple[float, float, float], position: tuple[float, float, float]) -> Any:
    obj = doc.addObject("Part::Box", "Bloc")
    obj.Length, obj.Width, obj.Height = taille
    obj.Placement = App.Placement(App.Vector(*position), App.Rotation())
    doc.recompute()
    return obj


def face(obj: Any, normale: tuple[float, float, float], coordonnee: float) -> str:
    """``FaceN`` plane de ``obj`` de normale sortante ``normale``, dont le centre a pour produit
    scalaire ``coordonnee`` avec la normale (position du plan le long de la normale)."""
    voulue = App.Vector(*normale)
    for rang, candidate in enumerate(obj.Shape.Faces, start=1):
        if not isinstance(candidate.Surface, Part.Plane):
            continue
        u, v = candidate.Surface.parameter(candidate.CenterOfMass)
        plan = candidate.CenterOfMass.dot(voulue)
        if candidate.normalAt(u, v).getAngle(voulue) < 1e-6 and abs(plan - coordonnee) < 1e-6:
            return f"Face{rang}"
    raise AssertionError(f"aucune face de normale {normale} dans {obj.Label}")


def selectionner_elements(*elements: tuple[Any, str]) -> None:
    """Sélection par script de sous-éléments (objet, chemin), dans cet ordre."""
    Gui.Selection.clearSelection()
    for obj, chemin in elements:
        Gui.Selection.addSelection(obj.Document.Name, obj.Name, chemin)


def selection_courante() -> list[tuple[str, list[str]]]:
    return [(s.ObjectName, list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx("", 0)]


def distance(piece: Any, autre: Any) -> float:
    return float(piece.Shape.distToShape(autre.Shape)[0])


def lancer_sur(*elements: tuple[Any, str]) -> Any:
    """Sélectionne ``elements`` puis lance la commande ; renvoie la pièce créée."""
    selectionner_elements(*elements)
    return creer_par_la_commande(elements[0][0].Document)


def verifier_accrochage_a_une_face() -> list[str]:
    """T1, T3, T6, T7, T8 + V1, V3 : la pièce touche la face, l'aperçu suit chaque saisie, la
    sélection reste, « OK » laisse une seule entrée d'annulation."""

    def verification(doc: Any) -> list[str]:
        bloc = cube(doc, (600, 300, 100), (0, 0, 0))
        selectionner_elements((bloc, face(bloc, (0, 0, 1), 100)))
        avant = selection_courante()
        piece = creer_par_la_commande(doc)
        form = formulaire()
        texte = form.snapLabel.text()
        problemes = [
            *ecarts("Contre : …", texte.startswith("Contre : ") and "Bloc" in texte, True),
            *ecarts("ligne visible", form.snapLabel.isHidden(), False),
            *ecarts("pas d'ensemble", form.furnitureCheck.isHidden(), True),
            *ecarts("touche la face", distance(piece, bloc) <= TOLERANCE, True),
            *ecarts("transparence", piece.ViewObject.Transparency, 60),
            *ecarts("sélection gardée", selection_courante(), avant),
        ]
        saisir(form.lengthEdit, 450.0)  # aperçu en direct, accrochage recalculé (T7)
        etendue = piece.Shape.BoundBox
        problemes += [
            *ecarts("longueur en direct", max(etendue.XLength, etendue.YLength), 450.0),
            *ecarts("touche encore", distance(piece, bloc) <= TOLERANCE, True),
        ]
        valider()
        return [
            *problemes,
            *ecarts("transparence rétablie", piece.ViewObject.Transparency, 0),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE]),
            *ecarts("sélection gardée après OK", selection_courante(), avant),
        ]

    return avec_document("VerifAccrochageFace", verification)


def verifier_accrochage_annule() -> list[str]:
    """V3 + T8 : « Annuler » avec une sélection ne laisse ni pièce ni entrée d'annulation."""

    def verification(doc: Any) -> list[str]:
        bloc = cube(doc, (600, 300, 100), (0, 0, 0))
        doc.clearUndos()
        lancer_sur((bloc, face(bloc, (0, 0, 1), 100)))
        annuler()
        return [
            *ecarts("objets", [o.Name for o in doc.Objects], [bloc.Name]),
            *ecarts("entrées d'annulation", doc.UndoCount, 0),
            *ecarts("sélection gardée", len(selection_courante()), 1),
        ]

    return avec_document("VerifAccrochageAnnule", verification)


def verifier_deux_joues() -> list[str]:
    """T6, Q2 : la tablette est étirée à l'écart des joues ; la saisie du menuisier l'emporte ;
    les boutons X, Y, Z gardent la pièce contre la première joue."""

    def verification(doc: Any) -> list[str]:
        gauche = cube(doc, (22, 560, 700), (0, 0, 0))
        droite = cube(doc, (22, 560, 700), (578, 0, 0))
        piece = lancer_sur(
            (gauche, face(gauche, (1, 0, 0), 22)), (droite, face(droite, (-1, 0, 0), -578))
        )
        form = formulaire()
        problemes = [
            *ecarts("étirée", valeur(form.lengthEdit), 556.0),
            *ecarts("épaisseur", valeur(form.thicknessEdit), 22.0),
            *ecarts("deux éléments cités", form.snapLabel.text().count("Face"), 2),
            *ecarts("touche à gauche", distance(piece, gauche) <= TOLERANCE, True),
            *ecarts("touche à droite", distance(piece, droite) <= TOLERANCE, True),
            *ecarts("horizontale", round(piece.Shape.BoundBox.ZLength, 6), 22.0),
        ]
        saisir(form.lengthEdit, 400.0)
        problemes += [
            *ecarts("saisie conservée", piece.Length.Value, 400.0),
            *ecarts("touche encore la première", distance(piece, gauche) <= TOLERANCE, True),
        ]
        for nom in BOUTONS:
            cliquer(form, nom)
            problemes += ecarts(f"{nom} garde l'appui", distance(piece, gauche) <= TOLERANCE, True)
        valider()
        return problemes

    return avec_document("VerifAccrochageJoues", verification)


def verifier_boutons_autour_des_axes_du_document() -> list[str]:
    """Q1 : quatre clics sur un même bouton ramènent la pièce au départ, contre une face
    verticale dont le repère d'appui est permuté par rapport au document."""

    def verification(doc: Any) -> list[str]:
        bloc = cube(doc, (600, 300, 100), (0, 0, 0))
        piece = lancer_sur((bloc, face(bloc, (0, -1, 0), 0)))
        form = formulaire()
        depart = piece.Placement.copy()
        problemes = ecarts("touche", distance(piece, bloc) <= TOLERANCE, True)
        for nom in BOUTONS:
            cliquer(form, nom)
            problemes += ecarts(f"{nom} garde l'appui", distance(piece, bloc) <= TOLERANCE, True)
            for _ in range(3):
                cliquer(form, nom)
            problemes += ecarts(f"{nom} x4", memes_placements(piece.Placement, depart), True)
        annuler()
        return problemes

    return avec_document("VerifAccrochageBoutons", verification)


def verifier_elements_ignores() -> list[str]:
    """T1 : un objet entier est ignoré avec un message ; sans cible, la pièce est à l'origine."""

    def verification(doc: Any) -> list[str]:
        bloc = cube(doc, (600, 300, 100), (50, 50, 50))
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(doc.Name, bloc.Name)
        piece = creer_par_la_commande(doc)
        form = formulaire()
        problemes = [
            *ecarts("message affiché", "Bloc" in form.snapNotices.text(), True),
            *ecarts("notice visible", form.snapNotices.isHidden(), False),
            *ecarts("ligne Contre masquée", form.snapLabel.isHidden(), True),
            *ecarts("à l'origine", piece.Placement.Base.isEqual(App.Vector(0, 0, 0), 1e-9), True),
        ]
        annuler()
        return problemes

    return avec_document("VerifAccrochageIgnore", verification)


def verifier_std_part_tourne() -> list[str]:
    """T4 : la pièce entre dans le Std Part du premier élément (tourné et déplacé) et le touche
    en coordonnées globales."""

    def verification(doc: Any) -> list[str]:
        meuble = doc.addObject("App::Part", "Meuble")
        meuble.Placement = App.Placement(
            App.Vector(1000, 500, 0), App.Rotation(App.Vector(0, 0, 1), 90)
        )
        bloc = cube(doc, (200, 100, 150), (0, 0, 0))
        meuble.addObject(bloc)
        doc.recompute()
        piece = lancer_sur((meuble, f"Bloc.{face(bloc, (0, 0, 1), 150)}"))
        problemes = [
            *ecarts("conteneur", piece.getParentGeoFeatureGroup() == meuble, True),
            *ecarts("touche (global)", distance_globale(piece, bloc) <= TOLERANCE, True),
        ]
        valider()
        return [*problemes, *ecarts("entrées d'annulation", doc.UndoNames, [CREATE])]

    return avec_document("VerifAccrochagePart", verification)


def distance_globale(piece: Any, autre: Any) -> float:
    forme = piece.Shape.copy()
    forme.Placement = piece.getGlobalPlacement()
    cible = autre.Shape.copy()
    cible.Placement = autre.getGlobalPlacement()
    return float(forme.distToShape(cible)[0])


def faces_internes(bureau: Any) -> tuple[tuple[Any, str], tuple[Any, str]]:
    gauche, droite = bureau.shown("JG"), bureau.shown("JD")
    return (gauche, face(gauche, (1, 0, 0), 22)), (droite, face(droite, (-1, 0, 0), -1178))


def verifier_case_ensemble() -> list[str]:
    """T5 : case « Ajouter à l'ensemble » cochée ; à « OK » la pièce entre dans l'ensemble, dans
    la même transaction, et suit ses cotes."""
    with bureau_regroupe("VerifAccrochageEnsemble") as bureau:
        piece = lancer_sur(*faces_internes(bureau))
        form = formulaire()
        problemes = [
            *ecarts("case visible", form.furnitureCheck.isHidden(), False),
            *ecarts("case cochée", form.furnitureCheck.isChecked(), True),
            *ecarts("nom de l'ensemble", "Bureau" in form.furnitureCheck.text(), True),
        ]
        valider()
        bureau.doc.recompute()
        problemes += [
            *ecarts("ensemble", getattr(piece, "Furniture", None) == bureau.furniture, True),
            *ecarts("une seule transaction", bureau.doc.UndoNames, [CREATE]),
        ]
        longueur = piece.Length.Value
        api.resize_furniture(bureau.furniture, width=1300.0)
        bureau.doc.recompute()
        return [*problemes, *ecarts("suit l'ensemble", piece.Length.Value, longueur + 100.0)]


def verifier_case_ensemble_decochee() -> list[str]:
    """T5 : case décochée, la pièce reste hors de l'ensemble."""
    with bureau_regroupe("VerifAccrochageDecochee") as bureau:
        piece = lancer_sur(*faces_internes(bureau))
        formulaire().furnitureCheck.setChecked(False)
        valider()
        return ecarts("hors ensemble", getattr(piece, "Furniture", None) is None, True)


def verifier_notices_apres_rotation() -> list[str]:
    """Revue finale de J6 : un quart de tour recalcule aussitôt la ligne « Contre : … » et les
    notices (texte périmé posé à la main, réécrit par le clic)."""

    def verification(doc: Any) -> list[str]:
        bloc = cube(doc, (600, 300, 100), (0, 0, 0))
        creation = lancer_sur((bloc, face(bloc, (0, 0, 1), 100)))
        form = formulaire()
        form.snapNotices.setText("périmé")
        form.snapLabel.setText("périmé")
        cliquer(form, "rotateXButton")
        problemes = [
            *ecarts("notices recalculées", form.snapNotices.text() != "périmé", True),
            *ecarts("Contre recalculé", form.snapLabel.text().startswith("Contre : "), True),
            *ecarts("pièce tournée", creation.Placement.Rotation.isNull(), False),
        ]
        annuler()
        return problemes

    return avec_document("VerifNoticesRotation", verification)


def verifier_ensemble_supprime_avant_ok() -> list[str]:
    """Revue finale de J6 : ensemble supprimé pendant que le panneau est ouvert, case cochée ;
    « OK » écrit un avertissement, crée la pièce hors de l'ensemble, rétablit la transparence et
    ne laisse qu'une entrée d'annulation."""
    with bureau_regroupe("VerifEnsembleSupprime") as bureau, vue_rapport() as messages:
        piece = lancer_sur(*faces_internes(bureau))
        form = formulaire()
        problemes = ecarts("case cochée", form.furnitureCheck.isChecked(), True)
        bureau.doc.removeObject(bureau.furniture.Name)
        valider()
        problemes += [
            *ecarts("avertissement", any("hors de l'ensemble" in m for m in messages), True),
            *ecarts("pièce créée", piece in bureau.doc.Objects, True),
            *ecarts("hors ensemble", getattr(piece, "Furniture", None) is None, True),
            *ecarts("transparence rétablie", piece.ViewObject.Transparency, 0),
            *ecarts("une seule transaction", bureau.doc.UndoNames[-1:], [CREATE]),
        ]
        return problemes


VERIFICATIONS_SELECTION: tuple[Callable[[], list[str]], ...] = (
    verifier_accrochage_a_une_face,
    verifier_accrochage_annule,
    verifier_deux_joues,
    verifier_boutons_autour_des_axes_du_document,
    verifier_elements_ignores,
    verifier_std_part_tourne,
    verifier_case_ensemble,
    verifier_case_ensemble_decochee,
    verifier_notices_apres_rotation,
    verifier_ensemble_supprime_avant_ok,
)
