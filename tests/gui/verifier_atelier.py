# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifie l'atelier dans l'interface de FreeCAD : chargement, affichage des pièces, textures.

Exécuté par FreeCAD lui-même (pas par pytest), l'atelier étant installé dans le
dossier ``Mod`` de ``FREECAD_USER_HOME`` :

    QT_QPA_PLATFORM=offscreen RESULTAT=resultat.txt freecad tests/gui/verifier_atelier.py

Chaque vérification renvoie la liste de ses problèmes ; le rapport les agrège. Il est écrit
dans le fichier ``RESULTAT`` car la sortie standard est captée par la console de FreeCAD.
Le code de retour vaut 0 si tout est correct.
"""

import json
import math
import os
import tempfile
import traceback
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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
MAPLE_RGB = (232, 210, 168)
FALLBACK_RGB = (204, 204, 204)
WHITE_RGB = (255, 255, 255)
TEXTURE_SIZE = (600.0, 200.0)
IMAGE_PIXELS = (64, 32)
IMAGE_RGB = (150, 100, 50)
SO_SWITCH_NONE = -1


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


def materiau(identifiant: str, nom: str, image: str | None = None) -> dict[str, object]:
    """Entrée de bibliothèque d'un bois massif couleur érable, texturée si ``image``."""
    entree: dict[str, object] = {
        "id": identifiant,
        "kind": "solid",
        "name": nom,
        "density": 650,
        "thicknesses": [22],
        "color": "#E8D2A8",
    }
    if image is not None:
        entree["texture"] = {"image": image, "size": list(TEXTURE_SIZE)}
    return entree


@contextmanager
def bibliotheque(*materiaux: dict[str, object]) -> Iterator[Path]:
    """Bibliothèque utilisateur temporaire (``UserLibraryPath``) ; renvoie son fichier, dont le
    dossier accueille les images. Paramètre et bibliothèque sont restaurés à la fin."""
    from freecad.menuiserie.features.library import (
        PARAM_PATH,
        USER_LIBRARY_PARAM,
        reload_library,
    )

    parametres = App.ParamGet(PARAM_PATH)
    precedent = parametres.GetString(USER_LIBRARY_PARAM, "")
    fichier = Path(tempfile.mkdtemp()) / "materiaux.json"
    contenu = {"format": 1, "materials": list(materiaux)}
    fichier.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    parametres.SetString(USER_LIBRARY_PARAM, str(fichier))
    try:
        reload_library()
        yield fichier
    finally:
        if precedent:
            parametres.SetString(USER_LIBRARY_PARAM, precedent)
        else:
            parametres.RemString(USER_LIBRARY_PARAM)
        reload_library()


def verifier_materiau_inconnu_et_documents_multiples() -> list[str]:
    """B8 : couleur enregistrée conservée si le matériau a disparu ; deux documents ouverts
    restent indépendants."""
    from freecad.menuiserie.api import make_wood_part
    from freecad.menuiserie.features.library import reload_library
    from freecad.menuiserie.features.wood_part import set_material

    with bibliotheque(materiau("erable", "Érable")) as fichier:
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
    return problemes


class VueSansApparence:
    """ViewObject minimal à ``ShapeAppearance`` vide : l'interface ne permet pas de vider cette
    liste, mais un document altéré peut la fournir."""

    def __init__(self, obj: Any) -> None:
        from pivy import coin

        self.Object = obj
        self.SwitchNode = coin.SoSwitch()
        self.RootNode = coin.SoSeparator()
        self.RootNode.addChild(self.SwitchNode)
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


# --- Textures (D4 à D6) ------------------------------------------------------------------


def ecrire_image(
    chemin: Path, taille: tuple[int, int] = IMAGE_PIXELS, format_: str = "PNG"
) -> None:
    """Image unie produite par Qt (le format peut différer de l'extension)."""
    from PySide import QtGui

    image = QtGui.QImage(*taille, QtGui.QImage.Format.Format_RGB888)
    image.fill(QtGui.QColor(*IMAGE_RGB))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(chemin), format_):
        raise OSError(f"image non écrite : {chemin}")


def commutateur(vobj: Any) -> Any:
    """Le ``SoSwitch`` « MenuiserieTexture » de ``vobj.RootNode``, ou ``None``."""
    racine = vobj.RootNode
    for index in range(racine.getNumChildren()):
        enfant = racine.getChild(index)
        if enfant.getName().getString() == "MenuiserieTexture":
            return enfant
    return None


def proches(obtenu: tuple[float, ...], attendu: tuple[float, ...]) -> bool:
    paires = zip(obtenu, attendu, strict=True)
    return all(math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-12) for a, b in paires)


def projection(etape: str, plan: Any, grain: str) -> list[str]:
    """Directions du ``SoTextureCoordinatePlane`` conformes au critère D1."""
    from pivy import coin

    from freecad.menuiserie.core.appearance import texture_mapping
    from freecad.menuiserie.core.part_model import GrainDirection

    attendu = texture_mapping(TEXTURE_SIZE, GrainDirection(grain))
    obtenu = (plan.directionS.getValue().getValue(), plan.directionT.getValue().getValue())
    problemes = ecarts(
        f"{etape}, nœud de projection",
        plan.isOfType(coin.SoTextureCoordinatePlane.getClassTypeId()),
        True,
    )
    if not (proches(obtenu[0], attendu.direction_s) and proches(obtenu[1], attendu.direction_t)):
        problemes.append(f"{etape}, projection : {obtenu!r} au lieu de {attendu!r}")
    return problemes


def entete_image(texture: Any) -> tuple[object, ...]:
    """Largeur, hauteur, composantes et premier pixel du ``SoTexture2``, lus dans sa forme
    texte (``getValue`` de pivy décode les pixels comme de l'UTF-8 et échoue)."""
    largeur, hauteur, composantes, pixel = texture.image.get().getString().split(maxsplit=4)[:4]
    valeur = int(pixel, 16)
    return int(largeur), int(hauteur), int(composantes), tuple(valeur.to_bytes(3, "big"))


def noeud_texture(vobj: Any) -> Any:
    """Le ``SoTexture2`` branché sous le switch de ``vobj`` (``None`` s'il n'y en a pas)."""
    groupe = commutateur(vobj).getChild(0)
    return groupe.getChild(1) if groupe.getNumChildren() > 1 else None


def texture_affichee(etape: str, vobj: Any, grain: str) -> list[str]:
    """D4 : switch actif avant ``SwitchNode``, projection, ``SoTexture2`` et couleurs."""
    from pivy import coin

    switch = commutateur(vobj)
    if switch is None or noeud_texture(vobj) is None:
        return [f"{etape} : nœuds de texture absents"]
    texture = noeud_texture(vobj)
    racine = vobj.RootNode
    return [
        *ecarts(
            f"{etape}, avant SwitchNode",
            racine.findChild(switch) < racine.findChild(vobj.SwitchNode),
            True,
        ),
        *ecarts(f"{etape}, switch actif", switch.whichChild.getValue(), 0),
        *projection(etape, switch.getChild(0).getChild(0), grain),
        *ecarts(f"{etape}, modèle", texture.model.getValue(), coin.SoTexture2.MODULATE),
        *ecarts(f"{etape}, répétition S", texture.wrapS.getValue(), coin.SoTexture2.REPEAT),
        *ecarts(f"{etape}, répétition T", texture.wrapT.getValue(), coin.SoTexture2.REPEAT),
        *ecarts(f"{etape}, image", entete_image(texture), (*IMAGE_PIXELS, 3, IMAGE_RGB)),
        *ecarts(f"{etape}, couleur diffuse", diffuse_rgb(vobj), WHITE_RGB),
        *ecarts(f"{etape}, MaterialColor", rgb(vobj.MaterialColor), MAPLE_RGB),
    ]


def couleur_de_repli(etape: str, vobj: Any) -> list[str]:
    """D5 : switch présent mais inactif, couleur diffuse = ``MaterialColor``."""
    switch = commutateur(vobj)
    if switch is None:
        return [f"{etape} : switch MenuiserieTexture absent"]
    return [
        *ecarts(f"{etape}, switch inactif", switch.whichChild.getValue(), SO_SWITCH_NONE),
        *couleurs(etape, vobj, MAPLE_RGB),
    ]


def avertissements_de_test() -> list[str]:
    """Nouveau cache de textures dont les avertissements sont recueillis dans la liste."""
    from freecad.menuiserie.gui.textures import reset_texture_cache

    messages: list[str] = []
    reset_texture_cache(warn=messages.append)
    return messages


def verifier_texture_affichee() -> list[str]:
    """D4 : texture affichée, à l'échelle et dans le sens du fil, partagée entre pièces."""
    from freecad.menuiserie.api import make_wood_part

    avertissements = avertissements_de_test()
    with bibliotheque(materiau("erable", "Érable", "textures/erable.png")) as fichier:
        ecrire_image(fichier.parent / "textures" / "erable.png")
        doc = App.newDocument("VerifTexture")
        doc.UndoMode = 1
        piece = make_wood_part(1200, 200, 22, "erable", doc=doc)
        autre = make_wood_part(600, 300, 18, "erable", doc=doc)
        problemes = texture_affichee("fil en long", piece.ViewObject, "Length")
        piece.Length = 1500
        piece.Placement = App.Placement(App.Vector(10, 20, 30), App.Rotation(30, 0, 0))
        doc.recompute()
        problemes += texture_affichee("cote et placement changés", piece.ViewObject, "Length")
        doc.openTransaction("Fil")
        piece.GrainDirection = "Width"
        doc.commitTransaction()
        problemes += texture_affichee("fil en travers", piece.ViewObject, "Width")
        doc.undo()
        problemes += texture_affichee("fil annulé", piece.ViewObject, "Length")
        problemes += [
            *ecarts(
                "texture partagée",
                noeud_texture(piece.ViewObject) == noeud_texture(autre.ViewObject),
                True,
            ),
            *ecarts("avertissements", avertissements, []),
        ]
        App.closeDocument(doc.Name)
    return problemes


def verifier_texture_repli() -> list[str]:
    """D5 : image absente, illisible, d'un autre format ou trop grande : couleur, sans
    exception, un seul avertissement par image même avec deux pièces."""
    from freecad.menuiserie.api import make_wood_part

    avertissements = avertissements_de_test()
    cas = ("absente", "illisible", "jpeg", "geante")
    materiaux = [materiau(f"bois-{nom}", f"Bois {nom}", f"textures/{nom}.png") for nom in cas]
    with bibliotheque(*materiaux) as fichier:
        dossier = fichier.parent / "textures"
        ecrire_image(dossier / "jpeg.png", format_="JPEG")
        ecrire_image(dossier / "geante.png", (4097, 8))
        (dossier / "illisible.png").write_bytes(os.urandom(4096))
        doc = App.newDocument("VerifRepli")
        problemes = [
            probleme
            for nom in cas
            for _ in range(2)
            for probleme in couleur_de_repli(
                nom, make_wood_part(material_id=f"bois-{nom}", doc=doc).ViewObject
            )
        ]
        for nom in cas:
            cites = [m for m in avertissements if f"{nom}.png" in m and "non affichée" in m]
            problemes += ecarts(f"avertissements pour {nom}", len(cites), 1)
        problemes += ecarts("avertissements", len(avertissements), len(cas))
        App.closeDocument(doc.Name)
    return problemes


def images_archivees(chemin: str) -> list[str]:
    """Images de l'archive ``.FCStd``, hors vignette du document."""
    with zipfile.ZipFile(chemin) as archive:
        noms = archive.namelist()
    extensions = (".png", ".jpg", ".jpeg")
    return [n for n in noms if n.lower().endswith(extensions) and not n.startswith("thumbnails/")]


def verifier_texture_reouverture() -> list[str]:
    """D6 : texture réaffichée à la réouverture sans modifier le document ni l'archiver ;
    couleur enregistrée si l'image a disparu ; aucune propriété ajoutée à la pièce."""
    from freecad.menuiserie.api import make_wood_part

    avertissements_de_test()
    with bibliotheque(materiau("erable", "Érable", "textures/erable.png")) as fichier:
        image = fichier.parent / "textures" / "erable.png"
        ecrire_image(image)
        doc = App.newDocument("VerifTextureRouverte")
        piece = make_wood_part(material_id="erable", doc=doc)
        piece.GrainDirection = "Width"
        attendues = sorted(make_wood_part(material_id="chene", doc=doc).PropertiesList)
        nom = piece.Name
        doc = rouvrir(doc)
        piece = doc.getObject(nom)
        problemes = [
            *texture_affichee("rouverte", piece.ViewObject, "Width"),
            *ecarts("document modifié à la réouverture", Gui.getDocument(doc.Name).Modified, False),
            *ecarts("images dans l'archive", images_archivees(doc.FileName), []),
            *ecarts("Version", piece.Version, 1),
            *ecarts("propriétés de la pièce", sorted(piece.PropertiesList), attendues),
        ]
        image.unlink()
        doc = rouvrir(doc)
        problemes += couleur_de_repli("rouverte sans image", doc.getObject(nom).ViewObject)
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
    verifier_texture_affichee,
    verifier_texture_repli,
    verifier_texture_reouverture,
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
