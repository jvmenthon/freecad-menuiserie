# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifie l'atelier dans l'interface de FreeCAD : chargement, affichage des pièces, puis
commande et panneau de tâche (``verifications_panneau.py``).

Exécuté par FreeCAD lui-même (pas par pytest), l'atelier étant installé dans le
dossier ``Mod`` de ``FREECAD_USER_HOME`` :

    QT_QPA_PLATFORM=offscreen RESULTAT=resultat.txt freecad tests/gui/verifier_atelier.py

Chaque vérification renvoie la liste de ses problèmes ; le rapport les agrège. Il est écrit
dans le fichier ``RESULTAT`` car la sortie standard est captée par la console de FreeCAD.
Le code de retour vaut 0 si tout est correct.
"""

import json
import os
import tempfile
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from tests.gui.verifications_fil import VERIFICATIONS_FIL
from tests.gui.verifications_panneau import VERIFICATIONS_PANNEAU
from tests.gui.verifications_panneau_limites import DEFAUTS_CONSTATES, VERIFICATIONS_LIMITES

ATELIER = "MenuiserieWorkbench"
VIEW_PROVIDER = "freecad.menuiserie.gui.view_providers.wood_part.ViewProviderWoodPart"
OAK_RGB = (184, 135, 90)
BEECH_RGB = (217, 180, 138)
WALNUT_RGB = (107, 74, 51)
OLD_DIFFUSE_RGB = (10, 120, 200)
MAPLE_RGB = (232, 210, 168)
FALLBACK_RGB = (204, 204, 204)


def verifier_atelier() -> list[str]:
    """L'atelier est listé, s'active et a une icône."""
    if ATELIER not in Gui.listWorkbenches():
        return [f"{ATELIER} absent de la liste des ateliers"]
    Gui.activateWorkbench(ATELIER)
    actif = Gui.activeWorkbench()
    if actif.name() != ATELIER:
        return [f"atelier actif inattendu : {actif.name()}"]
    if not os.path.isfile(actif.Icon):
        return [f"icône introuvable : {actif.Icon}"]
    return []


def rgb(color: tuple[float, ...]) -> tuple[int, ...]:
    return tuple(round(component * 255) for component in color[:3])


def diffuse_rgb(vobj: Any) -> tuple[int, ...]:
    return rgb(vobj.ShapeAppearance[0].DiffuseColor)


def ecarts(nom: str, obtenu: object, attendu: object) -> list[str]:
    return [] if obtenu == attendu else [f"{nom} : {obtenu!r} au lieu de {attendu!r}"]


def couleurs(etape: str, vobj: Any, attendu: tuple[int, ...]) -> list[str]:
    """``MaterialColor`` et couleur diffuse affichée valent ``attendu``."""
    return [
        *ecarts(f"{etape}, MaterialColor", rgb(vobj.MaterialColor), attendu),
        *ecarts(f"{etape}, couleur diffuse", diffuse_rgb(vobj), attendu),
    ]


def classe_du_proxy(vobj: Any) -> str:
    return f"{type(vobj.Proxy).__module__}.{type(vobj.Proxy).__qualname__}"


def rouvrir(doc: Any) -> Any:
    """Enregistre ``doc`` dans un dossier temporaire, le ferme et le rouvre."""
    path = Path(tempfile.mkdtemp()) / f"{doc.Name}.FCStd"
    doc.saveAs(str(path))
    App.closeDocument(doc.Name)
    return App.openDocument(str(path))


def verifier_piece_de_bois() -> list[str]:
    """B13 : icône, ``MaterialColor`` et couleur diffuse d'une pièce créée par l'API."""
    from freecad.menuiserie import icon_path
    from freecad.menuiserie.api import make_wood_part
    from freecad.menuiserie.features.wood_part import set_material

    doc = App.newDocument("VerifPieceDeBois")
    obj = make_wood_part(800, 200, 22, "chene", doc=doc)
    vobj = obj.ViewObject
    icone = vobj.Proxy.getIcon()
    problemes = [
        *ecarts("ViewProvider", classe_du_proxy(vobj), VIEW_PROVIDER),
        *ecarts("icône", icone, icon_path("Menuiserie_WoodPart.svg")),
        *ecarts("icône présente", os.path.isfile(icone), True),
        *ecarts("icône de l'arbre chargée", vobj.Icon.isNull(), False),
        *ecarts("MaterialColor masquée", vobj.getEditorMode("MaterialColor"), ["Hidden"]),
        *ecarts("groupe de MaterialColor", vobj.getGroupOfProperty("MaterialColor"), "Matériau"),
        *couleurs("chêne", vobj, OAK_RGB),
    ]
    set_material(obj, "hetre")
    problemes += couleurs("hêtre (set_material)", vobj, BEECH_RGB)
    obj.Material = "Noyer"
    problemes += couleurs("noyer (propriété Material)", vobj, WALNUT_RGB)
    App.closeDocument(doc.Name)
    return problemes


def verifier_reouverture() -> list[str]:
    """``MaterialColor`` relue sans modifier le document ; recréée si elle manque."""
    from freecad.menuiserie.api import make_wood_part

    doc = App.newDocument("VerifReouverture")
    actuelle = make_wood_part(material_id="hetre", doc=doc)
    ancienne = make_wood_part(material_id="chene", doc=doc)
    ancienne.ViewObject.removeProperty("MaterialColor")
    ancienne.ViewObject.ShapeColor = tuple(c / 255 for c in OLD_DIFFUSE_RGB)
    noms = actuelle.Name, ancienne.Name
    doc = rouvrir(doc)
    actuelle, ancienne = (doc.getObject(nom) for nom in noms)
    problemes = [
        *ecarts("ViewProvider rouvert", classe_du_proxy(actuelle.ViewObject), VIEW_PROVIDER),
        *couleurs("pièce rouverte", actuelle.ViewObject, BEECH_RGB),
        *couleurs("pièce sans MaterialColor rouverte", ancienne.ViewObject, OLD_DIFFUSE_RGB),
        *ecarts("document modifié à la réouverture", Gui.getDocument(doc.Name).Modified, False),
    ]
    App.closeDocument(doc.Name)
    return problemes


def verifier_annuler_retablir() -> list[str]:
    """B10 + B13 : couleurs suivies à l'annulation d'un matériau et de la création."""
    from freecad.menuiserie.api import make_wood_part

    doc = App.newDocument("VerifAnnuler")
    doc.UndoMode = 1
    doc.openTransaction("Créer")
    obj = make_wood_part(material_id="chene", doc=doc)
    doc.commitTransaction()
    nom = obj.Name
    doc.openTransaction("Matériau")
    obj.Material = "Noyer"
    doc.commitTransaction()
    doc.undo()
    problemes = couleurs("matériau annulé", obj.ViewObject, OAK_RGB)
    doc.redo()
    problemes += couleurs("matériau rétabli", obj.ViewObject, WALNUT_RGB)
    doc.undo()
    doc.undo()
    problemes += ecarts("création annulée", doc.getObject(nom), None)
    doc.redo()
    obj = doc.getObject(nom)
    problemes += [
        *ecarts("ViewProvider rétabli", classe_du_proxy(obj.ViewObject), VIEW_PROVIDER),
        *couleurs("création rétablie", obj.ViewObject, OAK_RGB),
    ]
    App.closeDocument(doc.Name)
    return problemes


def verifier_transparence() -> list[str]:
    """La transparence choisie par l'utilisateur survit au changement de matériau et à la
    réouverture (seule la couleur diffuse appartient au ViewProvider)."""
    from freecad.menuiserie.api import make_wood_part

    doc = App.newDocument("VerifTransparence")
    obj = make_wood_part(material_id="chene", doc=doc)
    apparence = obj.ViewObject.ShapeAppearance[0]
    apparence.Transparency = 0.5
    obj.ViewObject.ShapeAppearance = [apparence]
    obj.Material = "Hêtre"
    problemes = [
        *ecarts("transparence après changement", obj.ViewObject.Transparency, 50),
        *couleurs("hêtre transparent", obj.ViewObject, BEECH_RGB),
    ]
    nom = obj.Name
    doc = rouvrir(doc)
    vobj = doc.getObject(nom).ViewObject
    problemes += [
        *ecarts("transparence rouverte", vobj.Transparency, 50),
        *couleurs("hêtre rouvert", vobj, BEECH_RGB),
        *ecarts("document modifié à la réouverture", Gui.getDocument(doc.Name).Modified, False),
    ]
    App.closeDocument(doc.Name)
    return problemes


def verifier_materiau_inconnu_et_documents_multiples() -> list[str]:
    """B8 : couleur enregistrée conservée si le matériau a disparu ; deux documents ouverts
    restent indépendants."""
    from freecad.menuiserie.api import make_wood_part
    from freecad.menuiserie.features.library import (
        PARAM_PATH,
        USER_LIBRARY_PARAM,
        reload_library,
    )
    from freecad.menuiserie.features.wood_part import set_material

    parametres = App.ParamGet(PARAM_PATH)
    precedent = parametres.GetString(USER_LIBRARY_PARAM, "")
    fichier = Path(tempfile.mkdtemp()) / "materiaux.json"
    erable = {
        "id": "erable",
        "kind": "solid",
        "name": "Érable",
        "density": 650,
        "thicknesses": [22],
        "color": "#E8D2A8",
    }
    fichier.write_text(json.dumps({"format": 1, "materials": [erable]}), encoding="utf-8")
    parametres.SetString(USER_LIBRARY_PARAM, str(fichier))
    try:
        reload_library()
        doc = App.newDocument("VerifInconnu")
        nom = make_wood_part(material_id="erable", doc=doc).Name
        fichier.unlink()
        reload_library()
        doc = rouvrir(doc)
        autre = App.newDocument("VerifAutre")
        piece = make_wood_part(material_id="chene", doc=autre)
        set_material(piece, "noyer")
        vobj = doc.getObject(nom).ViewObject
        problemes = [
            *couleurs("matériau absent rouvert", vobj, MAPLE_RGB),
            *ecarts("document modifié à la réouverture", Gui.getDocument(doc.Name).Modified, False),
            *couleurs("autre document", piece.ViewObject, WALNUT_RGB),
        ]
        App.closeDocument(autre.Name)
        App.closeDocument(doc.Name)
    finally:
        if precedent:
            parametres.SetString(USER_LIBRARY_PARAM, precedent)
        else:
            parametres.RemString(USER_LIBRARY_PARAM)
        reload_library()
    return problemes


class VueSansApparence:
    """ViewObject minimal à ``ShapeAppearance`` vide : l'interface ne permet pas de vider cette
    liste, mais un document altéré peut la fournir."""

    def __init__(self, obj: Any) -> None:
        self.Object = obj
        self.PropertiesList: list[str] = []
        self.ShapeAppearance: list[Any] = []
        self.MaterialColor: tuple[float, ...] = ()  # écrite par le ViewProvider

    def addProperty(self, _type_id: str, name: str, *_args: str) -> None:
        self.PropertiesList.append(name)

    def setEditorMode(self, _name: str, _mode: int) -> None:
        """Modes d'édition sans objet pour cette vue factice."""


def verifier_apparence_vide() -> list[str]:
    """``ShapeAppearance`` vide : ni la création ni la réouverture ne lèvent d'exception."""
    from freecad.menuiserie.api import make_wood_part
    from freecad.menuiserie.gui.view_providers.wood_part import ViewProviderWoodPart

    doc = App.newDocument("VerifApparenceVide")
    obj = make_wood_part(material_id="chene", doc=doc)
    neuve, rouverte = VueSansApparence(obj), VueSansApparence(obj)
    ViewProviderWoodPart(neuve)
    proxy = ViewProviderWoodPart.__new__(ViewProviderWoodPart)  # comme à la réouverture
    proxy.attach(rouverte)
    proxy.finishRestoring()
    problemes = [
        *ecarts("création, MaterialColor", rgb(neuve.MaterialColor), OAK_RGB),
        *ecarts("réouverture, MaterialColor", rgb(rouverte.MaterialColor), FALLBACK_RGB),
        *ecarts("apparence laissée vide", neuve.ShapeAppearance + rouverte.ShapeAppearance, []),
    ]
    App.closeDocument(doc.Name)
    return problemes


VERIFICATIONS: tuple[Callable[[], list[str]], ...] = (
    verifier_atelier,
    verifier_piece_de_bois,
    verifier_reouverture,
    verifier_annuler_retablir,
    verifier_transparence,
    verifier_materiau_inconnu_et_documents_multiples,
    verifier_apparence_vide,
    *VERIFICATIONS_PANNEAU,
    *VERIFICATIONS_LIMITES,
    *VERIFICATIONS_FIL,
)


def verifier() -> list[str]:
    """Retourne la liste des problèmes constatés (vide si tout va bien)."""
    problemes: list[str] = []
    for verification in VERIFICATIONS:
        try:
            problemes += [f"{verification.__name__} : {p}" for p in verification()]
        except Exception:
            problemes.append(f"{verification.__name__} : {traceback.format_exc()}")
    return problemes


def main() -> None:
    with open(os.environ["RESULTAT"], "w", encoding="utf-8") as rapport:
        problemes = verifier()
        lignes = problemes or ["OK : atelier chargé et pièces affichées"]
        # Défauts connus (équivalent de xfail strict) : rapportés après le résultat.
        rapport.write("\n".join([*lignes, *DEFAUTS_CONSTATES]) + "\n")
    # Quitte immédiatement, sans boîte de dialogue ni boucle d'événements.
    os._exit(1 if problemes else 0)


main()
