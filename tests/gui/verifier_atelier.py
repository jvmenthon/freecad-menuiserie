# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifie l'atelier dans l'interface de FreeCAD : chargement, puis affichage des pièces.

Exécuté par FreeCAD lui-même (pas par pytest), l'atelier étant installé dans le
dossier ``Mod`` de ``FREECAD_USER_HOME`` :

    QT_QPA_PLATFORM=offscreen RESULTAT=resultat.txt freecad tests/gui/verifier_atelier.py

Chaque vérification renvoie la liste de ses problèmes ; le rapport les agrège. Il est écrit
dans le fichier ``RESULTAT`` car la sortie standard est captée par la console de FreeCAD.
Le code de retour vaut 0 si tout est correct.
"""

import os
import tempfile
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

ATELIER = "MenuiserieWorkbench"
VIEW_PROVIDER = "freecad.menuiserie.gui.view_providers.wood_part.ViewProviderWoodPart"
OAK_RGB = (184, 135, 90)
BEECH_RGB = (217, 180, 138)
WALNUT_RGB = (107, 74, 51)
OLD_DIFFUSE_RGB = (10, 120, 200)


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


VERIFICATIONS: tuple[Callable[[], list[str]], ...] = (
    verifier_atelier,
    verifier_piece_de_bois,
    verifier_reouverture,
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
        rapport.write("\n".join(problemes or ["OK : atelier chargé et pièces affichées"]) + "\n")
    # Quitte immédiatement, sans boîte de dialogue ni boucle d'événements.
    os._exit(1 if problemes else 0)


main()
