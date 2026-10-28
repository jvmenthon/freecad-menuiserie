# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifie l'atelier dans l'interface de FreeCAD : chargement, affichage des pièces, textures,
puis commande et panneau de tâche (``verifications_panneau.py``), assemblages et ensembles
(``verifications_ensemble.py``, ``verifications_panneau_ensemble.py``).

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
import struct
import tempfile
import traceback
import zipfile
import zlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from tests.gui.aides_panneau import DEFAUTS_CONSTATES
from tests.gui.verifications_apercu import VERIFICATIONS_APERCU
from tests.gui.verifications_aronde_relachement import VERIFICATIONS_ARONDE_RELACHEMENT
from tests.gui.verifications_assemblages import VERIFICATIONS_ASSEMBLAGES
from tests.gui.verifications_caisson import VERIFICATIONS_CAISSON
from tests.gui.verifications_debit import VERIFICATIONS_DEBIT
from tests.gui.verifications_distance import VERIFICATIONS_DISTANCE
from tests.gui.verifications_distance_gardee import VERIFICATIONS_DISTANCE_GARDEE
from tests.gui.verifications_double_clic import VERIFICATIONS_DOUBLE_CLIC
from tests.gui.verifications_ensemble import VERIFICATIONS_ENSEMBLE
from tests.gui.verifications_fil import VERIFICATIONS_FIL
from tests.gui.verifications_onglet import VERIFICATIONS_ONGLET
from tests.gui.verifications_panneau import VERIFICATIONS_PANNEAU
from tests.gui.verifications_panneau_assemblage import VERIFICATIONS_PANNEAU_ASSEMBLAGE
from tests.gui.verifications_panneau_ensemble import VERIFICATIONS_PANNEAU_ENSEMBLE
from tests.gui.verifications_panneau_limites import VERIFICATIONS_LIMITES
from tests.gui.verifications_panneau_verrous import VERIFICATIONS_PANNEAU_VERROUS
from tests.gui.verifications_piece_en_bois import VERIFICATIONS_PIECE_EN_BOIS
from tests.gui.verifications_piece_en_bois_ensemble import VERIFICATIONS_PIECE_EN_BOIS_ENSEMBLE
from tests.gui.verifications_piece_en_bois_limites import VERIFICATIONS_PIECE_EN_BOIS_LIMITES
from tests.gui.verifications_queue_aronde import VERIFICATIONS_QUEUE_ARONDE
from tests.gui.verifications_robustesse import VERIFICATIONS_ROBUSTESSE
from tests.gui.verifications_selection import VERIFICATIONS_SELECTION
from tests.gui.verifications_souris import VERIFICATIONS_SOURIS
from tests.gui.verifications_souris_document import VERIFICATIONS_SOURIS_DOCUMENT
from tests.gui.verifications_souris_piece_en_bois import VERIFICATIONS_SOURIS_PIECE_EN_BOIS
from tests.gui.verifications_transparence_assemblage import VERIFICATIONS_TRANSPARENCE_ASSEMBLAGE
from tests.gui.verifications_usinage_deplacement import VERIFICATIONS_USINAGE_DEPLACEMENT

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
    """``MaterialColor`` vaut ``attendu`` ; la couleur diffuse aussi, sauf si une texture est
    affichée (blanc de base, ADR 0004) : les matériaux intégrés ont leur photo."""
    switch = commutateur(vobj)
    texture = switch is not None and switch.whichChild.getValue() == 0
    return [
        *ecarts(f"{etape}, MaterialColor", rgb(vobj.MaterialColor), attendu),
        *ecarts(f"{etape}, couleur diffuse", diffuse_rgb(vobj), WHITE_RGB if texture else attendu),
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
def bibliotheque(*materiaux: dict[str, object], nom_du_dossier: str = "") -> Iterator[Path]:
    """Bibliothèque utilisateur temporaire (``UserLibraryPath``), dans le sous-dossier
    ``nom_du_dossier`` d'un dossier temporaire s'il est donné ; renvoie son fichier, dont le
    dossier accueille les images. Paramètre et bibliothèque sont restaurés à la fin."""
    from freecad.menuiserie.features.library import (
        PARAM_PATH,
        USER_LIBRARY_PARAM,
        reload_library,
    )

    parametres = App.ParamGet(PARAM_PATH)
    precedent = parametres.GetString(USER_LIBRARY_PARAM, "")
    fichier = Path(tempfile.mkdtemp()) / nom_du_dossier / "materiaux.json"
    fichier.parent.mkdir(exist_ok=True)
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


def avertissements_de_test(**bornes: int) -> list[str]:
    """Nouveau cache de textures (``bornes`` : ``max_entries``, ``max_bytes``) dont les
    avertissements sont recueillis dans la liste."""
    from freecad.menuiserie.gui.textures import reset_texture_cache

    messages: list[str] = []
    reset_texture_cache(warn=messages.append, **bornes)
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
    from freecad.menuiserie.features.wood_part_schema import MODEL_VERSION

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
            *ecarts("Version", piece.Version, MODEL_VERSION),
            *ecarts("propriétés de la pièce", sorted(piece.PropertiesList), attendues),
        ]
        image.unlink()
        doc = rouvrir(doc)
        problemes += couleur_de_repli("rouverte sans image", doc.getObject(nom).ViewObject)
        App.closeDocument(doc.Name)
    return problemes


# --- Cas limites des textures (testeur, lot J1d) -----------------------------------------


def reecrire_bibliotheque(fichier: Path, *materiaux: dict[str, object]) -> None:
    """Remplace le contenu de la bibliothèque temporaire puis la relit."""
    from freecad.menuiserie.features.library import reload_library

    contenu = {"format": 1, "materials": list(materiaux)}
    fichier.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    reload_library()


def materiau_de_taille(
    identifiant: str, image: str, taille: tuple[float, float]
) -> dict[str, object]:
    """Comme :func:`materiau`, avec une texture couvrant ``taille`` mm."""
    entree = materiau(identifiant, identifiant, image)
    entree["texture"] = {"image": image, "size": list(taille)}
    return entree


def directions(vobj: Any) -> tuple[tuple[float, ...], tuple[float, ...]]:
    plan = commutateur(vobj).getChild(0).getChild(0)
    return plan.directionS.getValue().getValue(), plan.directionT.getValue().getValue()


def etat_texture(vobj: Any) -> tuple[object, ...]:
    """Switch actif, en-tête de l'image branchée (ou ``None``) et couleur diffuse."""
    switch = commutateur(vobj)
    if switch is None:
        return ("switch absent",)
    actif = switch.whichChild.getValue() == 0
    noeud = noeud_texture(vobj)
    return actif, entete_image(noeud)[:2] if actif and noeud else None, diffuse_rgb(vobj)


def texture_visible(etape: str, vobj: Any, pixels: tuple[int, int]) -> list[str]:
    return ecarts(f"{etape}, état", etat_texture(vobj), (True, pixels, WHITE_RGB))


def repli_visible(etape: str, vobj: Any, couleur: tuple[int, ...] = MAPLE_RGB) -> list[str]:
    return ecarts(f"{etape}, état", etat_texture(vobj), (False, None, couleur))


def nombre_de_switchs(vobj: Any) -> int:
    racine = vobj.RootNode
    noms = (racine.getChild(i).getName().getString() for i in range(racine.getNumChildren()))
    return sum(1 for nom in noms if nom == "MenuiserieTexture")


def verifier_texture_annuler_retablir() -> list[str]:
    """Création, suppression, changement de matériau (texturé ↔ uni, texture A → B) et sens du
    fil : texture et couleur suivent annuler et rétablir, un seul switch par pièce."""
    from freecad.menuiserie.api import make_wood_part

    avertissements = avertissements_de_test()
    materiaux = (
        materiau("erable", "Érable", "textures/erable.png"),
        materiau("tilleul", "Tilleul", "textures/tilleul.png"),
        materiau("platane", "Platane"),
    )
    with bibliotheque(*materiaux) as fichier:
        ecrire_image(fichier.parent / "textures" / "erable.png")
        ecrire_image(fichier.parent / "textures" / "tilleul.png", (32, 16))
        doc = App.newDocument("VerifTextureAnnuler")
        doc.UndoMode = 1

        def transaction(nom: str, action: Callable[[], object]) -> None:
            doc.openTransaction(nom)
            action()
            doc.commitTransaction()

        transaction("Créer", lambda: make_wood_part(material_id="erable", doc=doc))
        nom = doc.Objects[0].Name
        doc.undo()
        doc.redo()
        problemes = texture_visible(
            "création rétablie", doc.getObject(nom).ViewObject, IMAGE_PIXELS
        )
        transaction("Supprimer", lambda: doc.removeObject(nom))
        doc.undo()
        piece = doc.getObject(nom)
        problemes += texture_visible("suppression annulée", piece.ViewObject, IMAGE_PIXELS)
        transaction("Uni", lambda: setattr(piece, "Material", "Platane"))
        problemes += repli_visible("texturé → uni", piece.ViewObject)
        doc.undo()
        problemes += texture_visible("uni annulé", piece.ViewObject, IMAGE_PIXELS)
        doc.redo()
        problemes += repli_visible("uni rétabli", piece.ViewObject)
        doc.undo()
        transaction("Autre texture", lambda: setattr(piece, "Material", "Tilleul"))
        problemes += texture_visible("texture A → B", piece.ViewObject, (32, 16))
        doc.undo()
        problemes += texture_visible("texture B annulée", piece.ViewObject, IMAGE_PIXELS)
        transaction("Fil", lambda: setattr(piece, "GrainDirection", "Width"))
        doc.undo()
        doc.redo()
        problemes += [
            *texture_affichee("fil rétabli", piece.ViewObject, "Width"),
            *ecarts("switchs par pièce", nombre_de_switchs(piece.ViewObject), 1),
            *ecarts("avertissements", avertissements, []),
        ]
        App.closeDocument(doc.Name)
    return problemes


def verifier_texture_recalcul() -> list[str]:
    """Recalcul après chaque propriété : texture et projection inchangées ; les coordonnées de la
    forme affichée restent locales (origine de l'image au coin de la pièce)."""
    from pivy import coin

    from freecad.menuiserie.api import make_wood_part

    avertissements_de_test()
    with bibliotheque(materiau("erable", "Érable", "textures/erable.png")) as fichier:
        ecrire_image(fichier.parent / "textures" / "erable.png")
        doc = App.newDocument("VerifTextureRecalcul")
        piece = make_wood_part(material_id="erable", doc=doc)
        placement = App.Placement(App.Vector(1e5, -2e5, 30), App.Rotation(30, 45, 60))
        modifications = [
            ("Length", 10_000.0),
            ("Width", 1.0),
            ("Thickness", 300.0),
            ("LengthAllowance", 5.0),
            ("Mark", "A1"),
            ("Placement", placement),
        ]
        problemes: list[str] = []
        for propriete, valeur in modifications:
            setattr(piece, propriete, valeur)
            doc.recompute()
            problemes += texture_affichee(f"{propriete} modifiée", piece.ViewObject, "Length")
        recherche = coin.SoSearchAction()
        recherche.setType(coin.SoCoordinate3.getClassTypeId())
        recherche.setInterest(coin.SoSearchAction.ALL)
        recherche.apply(piece.ViewObject.RootNode)
        chemins = recherche.getPaths()
        points = [
            chemins[i].getTail().point[j].getValue()
            for i in range(chemins.getLength())
            for j in range(chemins[i].getTail().point.getNum())
        ]
        boite = [(min(p[k] for p in points), max(p[k] for p in points)) for k in range(3)]
        attendue = [(0.0, 10_000.0), (0.0, 1.0), (0.0, 300.0)]
        if not points or not all(
            math.isclose(a, b, abs_tol=1e-6)
            for obtenu, voulu in zip(boite, attendue, strict=True)
            for a, b in zip(obtenu, voulu, strict=True)
        ):
            problemes.append(f"coordonnées affichées non locales : {boite!r}")
        App.closeDocument(doc.Name)
    return problemes


def bloc_png(type_: bytes, donnees: bytes) -> bytes:
    """Bloc PNG : longueur, type, contenu, CRC."""
    crc = struct.pack(">I", zlib.crc32(type_ + donnees))
    return struct.pack(">I", len(donnees)) + type_ + donnees + crc


def png_fabrique(taille: tuple[int, int], idat: bytes, entrelace: int = 0) -> bytes:
    """PNG RVB 8 bits fabriqué octet par octet : en-tête ``taille``, un bloc ``IDAT`` donné."""
    ihdr = struct.pack(">IIBBBBB", *taille, 8, 2, 0, 0, entrelace)
    return (
        b"\x89PNG\r\n\x1a\n"
        + bloc_png(b"IHDR", ihdr)
        + bloc_png(b"IDAT", idat)
        + bloc_png(b"IEND", b"")
    )


def verifier_texture_fichiers_pieges() -> list[str]:
    """Images piégées : en-tête géant pour quelques octets, hauteur > 4 096, dimensions nulles,
    image tronquée, BMP nommé .png, PNG nommé .jpg, tube nommé .png → couleur, sans exception,
    un avertissement chacune ; JPEG .jpg, 4 096 x 4 096, 1 x 1, largeur impaire (bourrage de
    Qt) et lien symbolique interne → texture affichée."""
    from freecad.menuiserie.api import make_wood_part

    def png_annonce(largeur: int, hauteur: int) -> bytes:
        return png_fabrique((largeur, hauteur), zlib.compress(b""))

    avertissements = avertissements_de_test()
    refusees = (
        "bombe.png",
        "haute.png",
        "nulle.png",
        "tronquee.png",
        "bmp.png",
        "png.jpg",
        "tube.png",
    )
    acceptees = {
        "vraie.jpg": (64, 32),
        "max.png": (4096, 4096),
        "pixel.png": (1, 1),
        "impaire.png": (63, 31),
        "lien.png": (64, 32),
    }
    noms = (*refusees, *acceptees)
    materiaux = [materiau(f"b{i}", f"Bois {nom}", f"textures/{nom}") for i, nom in enumerate(noms)]
    with bibliotheque(*materiaux) as fichier:
        dossier = fichier.parent / "textures"
        ecrire_image(dossier / "cible.png")
        (dossier / "lien.png").symlink_to(dossier / "cible.png")
        (dossier / "bombe.png").write_bytes(png_annonce(100_000, 100_000))
        (dossier / "nulle.png").write_bytes(png_annonce(0, 0))
        ecrire_image(dossier / "haute.png", (8, 4097))
        (dossier / "tronquee.png").write_bytes((dossier / "cible.png").read_bytes()[:60])
        ecrire_image(dossier / "bmp.png", format_="BMP")
        ecrire_image(dossier / "png.jpg")
        os.mkfifo(dossier / "tube.png")
        ecrire_image(dossier / "vraie.jpg", format_="JPEG")
        ecrire_image(dossier / "max.png", (4096, 4096))
        ecrire_image(dossier / "pixel.png", (1, 1))
        ecrire_image(dossier / "impaire.png", (63, 31))
        reecrire_bibliotheque(fichier, *materiaux)  # liens résolus au chargement
        doc = App.newDocument("VerifPieges")
        problemes: list[str] = []
        for i, nom in enumerate(noms):
            vobj = make_wood_part(material_id=f"b{i}", doc=doc).ViewObject
            if nom in acceptees:
                problemes += texture_visible(nom, vobj, acceptees[nom])
            else:
                problemes += repli_visible(nom, vobj)
        for nom in refusees:
            cites = [m for m in avertissements if f"/{nom} »" in m]
            problemes += ecarts(f"avertissements pour {nom}", len(cites), 1)
        problemes += ecarts("avertissements", len(avertissements), len(refusees))
        App.closeDocument(doc.Name)
    return problemes


def verifier_texture_orientation_des_pixels() -> list[str]:
    """Pixels du ``SoTexture2`` : ligne du bas de l'image en premier (origine de Coin en bas à
    gauche), de gauche à droite, sans le bourrage de fin de ligne (largeur 3 en RVB)."""
    from PySide import QtGui

    from freecad.menuiserie.api import make_wood_part

    avertissements_de_test()
    with bibliotheque(materiau("erable", "Érable", "textures/erable.png")) as fichier:
        image = QtGui.QImage(3, 2, QtGui.QImage.Format.Format_RGB888)
        for x in range(3):
            image.setPixelColor(x, 0, QtGui.QColor(255, 0, x))  # ligne du haut
            image.setPixelColor(x, 1, QtGui.QColor(0, 0, 250 + x))  # ligne du bas
        (fichier.parent / "textures").mkdir()
        image.save(str(fichier.parent / "textures" / "erable.png"), "PNG")
        doc = App.newDocument("VerifPixels")
        noeud = noeud_texture(make_wood_part(material_id="erable", doc=doc).ViewObject)
        texte = noeud.image.get().getString().split() if noeud else []
        attendu = ["3", "2", "3", "0xfa", "0xfb", "0xfc", "0xff0000", "0xff0001", "0xff0002"]
        App.closeDocument(doc.Name)
    return ecarts("pixels du SoTexture2", texte, attendu)


def verifier_texture_image_remplacee() -> list[str]:
    """Image supprimée en cours de session puis rendue, puis remplacée par une autre taille :
    couleur puis texture ; la nouvelle image est relue (nouvelle pièce, réouverture)."""
    from freecad.menuiserie.api import make_wood_part

    avertissements = avertissements_de_test()
    with bibliotheque(materiau("erable", "Érable", "textures/erable.png")) as fichier:
        image = fichier.parent / "textures" / "erable.png"
        ecrire_image(image)
        doc = App.newDocument("VerifImageRemplacee")
        piece = make_wood_part(material_id="erable", doc=doc)
        image.rename(image.with_suffix(".bak"))
        piece.GrainDirection = "Width"
        problemes = repli_visible("image supprimée", piece.ViewObject)
        piece.GrainDirection = "Length"
        problemes += ecarts("avertissements image supprimée", len(avertissements), 1)
        image.with_suffix(".bak").rename(image)
        piece.GrainDirection = "Width"
        problemes += texture_visible("image rendue", piece.ViewObject, IMAGE_PIXELS)
        ecrire_image(image, (16, 8))
        os.utime(image, ns=(1, 1))  # date différente même sur un système de fichiers grossier
        nouvelle = make_wood_part(material_id="erable", doc=doc)
        problemes += texture_visible(
            "image remplacée, nouvelle pièce", nouvelle.ViewObject, (16, 8)
        )
        nom = piece.Name
        doc = rouvrir(doc)
        problemes += [
            *texture_visible(
                "image remplacée, réouverture", doc.getObject(nom).ViewObject, (16, 8)
            ),
            *ecarts("document modifié à la réouverture", Gui.getDocument(doc.Name).Modified, False),
            *ecarts("avertissements", len(avertissements), 1),
        ]
        App.closeDocument(doc.Name)
    return problemes


def verifier_texture_bibliotheque_modifiee() -> list[str]:
    """Bibliothèque modifiée entre deux sessions : taille changée (10 et 10 000 mm), texture
    retirée, texture ajoutée à un matériau uni, matériau supprimé ; jamais de document modifié."""
    from freecad.menuiserie.api import make_wood_part
    from freecad.menuiserie.core.appearance import texture_mapping
    from freecad.menuiserie.core.part_model import GrainDirection

    avertissements_de_test()
    erable = materiau("erable", "Érable", "textures/erable.png")
    with bibliotheque(erable, materiau("tilleul", "Tilleul")) as fichier:
        ecrire_image(fichier.parent / "textures" / "erable.png")
        doc = App.newDocument("VerifBibliothequeModifiee")
        texturee = make_wood_part(material_id="erable", doc=doc).Name
        unie = make_wood_part(material_id="tilleul", doc=doc).Name
        etapes = [
            (
                "taille extrême",
                (
                    materiau_de_taille("erable", "textures/erable.png", (10.0, 10_000.0)),
                    materiau("tilleul", "Tilleul"),
                ),
                True,
                False,
            ),
            (
                "texture retirée",
                (materiau("erable", "Érable"), materiau("tilleul", "Tilleul")),
                False,
                False,
            ),
            (
                "texture ajoutée",
                (erable, materiau("tilleul", "Tilleul", "textures/erable.png")),
                True,
                True,
            ),
            ("matériaux supprimés", (), False, False),
        ]
        problemes: list[str] = []
        for etape, materiaux, avec_texture, unie_texturee in etapes:
            reecrire_bibliotheque(fichier, *materiaux)
            doc = rouvrir(doc)
            vobj, vobj_unie = doc.getObject(texturee).ViewObject, doc.getObject(unie).ViewObject
            if avec_texture:
                problemes += texture_visible(etape, vobj, IMAGE_PIXELS)
            else:
                problemes += repli_visible(etape, vobj)
            if unie_texturee:
                problemes += texture_visible(f"{etape}, pièce unie", vobj_unie, IMAGE_PIXELS)
            else:
                problemes += repli_visible(f"{etape}, pièce unie", vobj_unie)
            problemes += ecarts(
                f"{etape}, document modifié", Gui.getDocument(doc.Name).Modified, False
            )
            if etape == "taille extrême":
                voulu = texture_mapping((10.0, 10_000.0), GrainDirection.LENGTH)
                obtenu = directions(vobj)
                if not (
                    proches(obtenu[0], voulu.direction_s) and proches(obtenu[1], voulu.direction_t)
                ):
                    problemes.append(f"{etape}, projection : {obtenu!r}")
        App.closeDocument(doc.Name)
    return problemes


def verifier_texture_documents_multiples() -> list[str]:
    """Deux documents partagent le nœud de l'image ; fermer l'un n'affecte pas l'autre ; une
    copie dans l'autre document et un ``App::Link`` affichent la texture ; un nouveau cache
    (nœuds précédents libérés par Python) laisse les nœuds affichés intacts."""
    import gc

    from freecad.menuiserie.api import make_wood_part

    avertissements_de_test()
    with bibliotheque(materiau("erable", "Érable", "textures/erable.png")) as fichier:
        ecrire_image(fichier.parent / "textures" / "erable.png")
        premier, second = App.newDocument("VerifMultiA"), App.newDocument("VerifMultiB")
        a = make_wood_part(material_id="erable", doc=premier)
        b = make_wood_part(1200, 200, 22, "erable", doc=second)
        copie = second.copyObject(a)
        lien = second.addObject("App::Link", "Lien")
        lien.LinkedObject = b
        second.recompute()
        problemes = [
            *ecarts(
                "nœud partagé entre documents",
                noeud_texture(a.ViewObject) == noeud_texture(b.ViewObject),
                True,
            ),
            *texture_visible("copie dans l'autre document", copie.ViewObject, IMAGE_PIXELS),
        ]
        recherche_lien = Gui.getDocument(second.Name).getObject(lien.Name).RootNode
        problemes += ecarts(
            "lien : switch de texture présent", commutateur_sous(recherche_lien), True
        )
        App.closeDocument(premier.Name)
        avertissements_de_test()  # nouveau cache : l'ancien et ses nœuds sont libérés par Python
        gc.collect()
        problemes += texture_affichee("après fermeture de l'autre document", b.ViewObject, "Length")
        problemes += texture_visible(
            "nouvelle pièce, nouveau cache",
            make_wood_part(material_id="erable", doc=second).ViewObject,
            IMAGE_PIXELS,
        )
        App.closeDocument(second.Name)
    return problemes


def verifier_texture_confinement() -> list[str]:
    """Audit, point 2 : l'image est ouverte une fois, confinée au dossier de la bibliothèque à
    chaque ouverture. Un lien vers l'extérieur créé après le chargement est refusé (un
    avertissement) ; un lien interne et une bibliothèque lue par un lien vers son dossier sont
    acceptés."""
    from freecad.menuiserie.api import make_wood_part
    from freecad.menuiserie.features.library import (
        PARAM_PATH,
        USER_LIBRARY_PARAM,
        reload_library,
    )

    avertissements = avertissements_de_test()
    materiaux = (
        materiau("erable", "Érable", "textures/erable.png"),
        materiau("tilleul", "Tilleul", "textures/tilleul.png"),
    )
    with bibliotheque(*materiaux) as fichier:
        dossier = fichier.parent / "textures"
        ecrire_image(dossier / "erable.png")
        ecrire_image(dossier / "tilleul.png", (16, 8))
        lien = fichier.parent.with_name(fichier.parent.name + "-lien")
        lien.symlink_to(fichier.parent)
        App.ParamGet(PARAM_PATH).SetString(USER_LIBRARY_PARAM, str(lien / fichier.name))
        reload_library()
        doc = App.newDocument("VerifConfinement")
        problemes = texture_visible(
            "bibliothèque lue par un lien",
            make_wood_part(material_id="erable", doc=doc).ViewObject,
            IMAGE_PIXELS,
        )
        exterieur = Path(tempfile.mkdtemp()) / "secret.png"
        ecrire_image(exterieur, (8, 4))
        (dossier / "erable.png").unlink()
        (dossier / "erable.png").symlink_to(exterieur)
        problemes += repli_visible(
            "lien vers l'extérieur", make_wood_part(material_id="erable", doc=doc).ViewObject
        )
        (dossier / "tilleul.png").rename(dossier / "autre.png")
        (dossier / "tilleul.png").symlink_to(dossier / "autre.png")
        problemes += texture_visible(
            "lien interne", make_wood_part(material_id="tilleul", doc=doc).ViewObject, (16, 8)
        )
        cites = [m for m in avertissements if "erable.png" in m and "sorti du dossier" in m]
        problemes += [
            *ecarts("avertissement du lien vers l'extérieur", len(cites), 1),
            *ecarts("avertissements", len(avertissements), 1),
        ]
        App.closeDocument(doc.Name)
    return problemes


def jpeg_progressif(chemin: Path, balayages_ajoutes: int) -> None:
    """JPEG progressif produit par Qt, dont le dernier balayage est répété
    ``balayages_ajoutes`` fois (Qt le décoderait, en avertissant)."""
    from PySide import QtCore, QtGui

    image = QtGui.QImage(*IMAGE_PIXELS, QtGui.QImage.Format.Format_RGB888)
    image.fill(QtGui.QColor(*IMAGE_RGB))
    tampon = QtCore.QBuffer()
    tampon.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    redacteur = QtGui.QImageWriter(tampon, b"jpeg")
    redacteur.setProgressiveScanWrite(True)
    if not redacteur.write(image):
        raise OSError("JPEG progressif non écrit")
    octets = bytes(tampon.data())
    fin = octets.rfind(b"\xff\xd9")
    dernier = octets[octets.rfind(b"\xff\xda") : fin]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(octets[:fin] + dernier * balayages_ajoutes + octets[fin:])


def verifier_texture_jpeg_balayages() -> list[str]:
    """Audit, point 1 : un JPEG progressif de plus de 100 balayages est refusé avant décodage
    (couleur, un avertissement qui cite le nombre de balayages) ; un JPEG progressif ordinaire
    est affiché."""
    from freecad.menuiserie.api import make_wood_part

    avertissements = avertissements_de_test()
    materiaux = (
        materiau("progressif", "Progressif", "textures/progressif.jpg"),
        materiau("balayages", "Balayages", "textures/balayages.jpg"),
    )
    with bibliotheque(*materiaux) as fichier:
        jpeg_progressif(fichier.parent / "textures" / "progressif.jpg", 0)
        jpeg_progressif(fichier.parent / "textures" / "balayages.jpg", 150)
        doc = App.newDocument("VerifBalayages")
        problemes = texture_visible(
            "JPEG progressif",
            make_wood_part(material_id="progressif", doc=doc).ViewObject,
            IMAGE_PIXELS,
        )
        for _ in range(2):
            vobj = make_wood_part(material_id="balayages", doc=doc).ViewObject
            problemes += repli_visible("JPEG de 160 balayages", vobj)
        cites = [m for m in avertissements if "balayages.jpg" in m and "160 balayages" in m]
        problemes += [
            *ecarts("avertissement des balayages", len(cites), 1),
            *ecarts("avertissements", len(avertissements), 1),
        ]
        App.closeDocument(doc.Name)
    return problemes


def zeros_compresses(taille: int) -> bytes:
    """``taille`` octets nuls compressés par zlib, par morceaux de 1 Mio."""
    compresseur = zlib.compressobj(9)
    pas = 1 << 20
    morceaux = (
        compresseur.compress(bytes(min(pas, taille - fait))) for fait in range(0, taille, pas)
    )
    return b"".join(morceaux) + compresseur.flush()


def verifier_texture_bombe_png() -> list[str]:
    """Audit, point 4 : un PNG de 1 pixel dont l'IDAT se décompresse en 64 Mio est refusé avant
    décodage (un avertissement) ; un PNG entrelacé (Adam7) aux données exactes et un PNG RVBA
    16 bits sont affichés."""
    from PySide import QtGui

    from freecad.menuiserie.api import make_wood_part

    avertissements = avertissements_de_test()
    noms = ("bombe", "adam7", "rvba16")
    materiaux = [materiau(nom, nom, f"textures/{nom}.png") for nom in noms]
    with bibliotheque(*materiaux) as fichier:
        dossier = fichier.parent / "textures"
        dossier.mkdir()
        (dossier / "bombe.png").write_bytes(png_fabrique((1, 1), zeros_compresses(64 << 20)))
        # 13 x 11 pixels en Adam7, passes 1 à 7 : lignes x (octet de filtre + 3 octets par
        # pixel) = 2 x 7, 2 x 7, 1 x 13, 3 x 10, 3 x 22, 6 x 19 et 5 x 40 octets, tous nuls.
        brut = 14 + 14 + 13 + 30 + 66 + 114 + 200
        (dossier / "adam7.png").write_bytes(png_fabrique((13, 11), zlib.compress(bytes(brut)), 1))
        image = QtGui.QImage(*IMAGE_PIXELS, QtGui.QImage.Format.Format_RGBA64)
        image.fill(QtGui.QColor(*IMAGE_RGB))
        image.save(str(dossier / "rvba16.png"), "PNG")
        doc = App.newDocument("VerifBombePng")
        problemes: list[str] = []
        for _ in range(2):
            vobj = make_wood_part(material_id="bombe", doc=doc).ViewObject
            problemes += repli_visible("bombe IDAT", vobj)
        problemes += texture_visible(
            "PNG entrelacé", make_wood_part(material_id="adam7", doc=doc).ViewObject, (13, 11)
        )
        problemes += texture_visible(
            "PNG RVBA 16 bits",
            make_wood_part(material_id="rvba16", doc=doc).ViewObject,
            IMAGE_PIXELS,
        )
        cites = [m for m in avertissements if "bombe.png" in m and "décompressées" in m]
        problemes += [
            *ecarts("avertissement de la bombe", len(cites), 1),
            *ecarts("avertissements", len(avertissements), 1),
        ]
        App.closeDocument(doc.Name)
    return problemes


def verifier_texture_budget_memoire() -> list[str]:
    """Audit, point 3 : les images décodées encore affichées comptent dans le budget même
    oubliées par le cache ; au-delà, couleur et un seul avertissement ; une texture masquée
    libère sa place. Deux liens physiques vers la même image partagent un nœud."""
    from freecad.menuiserie.api import make_wood_part
    from freecad.menuiserie.features.wood_part import set_material

    octets = IMAGE_PIXELS[0] * IMAGE_PIXELS[1] * 3
    avertissements = avertissements_de_test(max_entries=1, max_bytes=2 * octets)
    noms = ("a", "b", "c", "d", "physique")
    with bibliotheque(*(materiau(n, n, f"textures/{n}.png") for n in noms)) as fichier:
        dossier = fichier.parent / "textures"
        for nom in noms[:4]:
            ecrire_image(dossier / f"{nom}.png")
        os.link(dossier / "a.png", dossier / "physique.png")
        doc = App.newDocument("VerifBudget")
        a, b = (make_wood_part(material_id=n, doc=doc) for n in ("a", "b"))
        problemes = [
            *texture_visible("a", a.ViewObject, IMAGE_PIXELS),
            *texture_visible("b", b.ViewObject, IMAGE_PIXELS),
            *repli_visible(
                "c au-delà du budget", make_wood_part(material_id="c", doc=doc).ViewObject
            ),
            *repli_visible(
                "d au-delà du budget", make_wood_part(material_id="d", doc=doc).ViewObject
            ),
        ]
        physique = make_wood_part(material_id="physique", doc=doc)
        problemes += [
            *texture_visible("lien physique", physique.ViewObject, IMAGE_PIXELS),
            *ecarts(
                "lien physique : nœud partagé",
                noeud_texture(physique.ViewObject) == noeud_texture(a.ViewObject),
                True,
            ),
        ]
        set_material(a, "chene")
        set_material(physique, "chene")
        problemes += [
            *ecarts("texture masquée retirée", noeud_texture(a.ViewObject), None),
            *texture_visible(
                "c, place libérée",
                make_wood_part(material_id="c", doc=doc).ViewObject,
                IMAGE_PIXELS,
            ),
        ]
        cites = [m for m in avertissements if "Mio d'images décodées" in m and "c.png" in m]
        problemes += [
            *ecarts("avertissement du budget", len(cites), 1),
            *ecarts("avertissements", len(avertissements), 1),
        ]
        App.closeDocument(doc.Name)
    return problemes


def verifier_texture_chemin_echappe() -> list[str]:
    """Audit, point 5 : le chemin cité dans l'avertissement est entier, ses caractères non
    imprimables échappés (dossier de bibliothèque nommé avec un saut de ligne et une inversion
    bidirectionnelle)."""
    from freecad.menuiserie.api import make_wood_part

    avertissements = avertissements_de_test()
    nom = "bib\u202e\nliotheque-" + "x" * 60
    with bibliotheque(materiau("erable", "Érable", "textures/absente.png"), nom_du_dossier=nom):
        doc = App.newDocument("VerifCheminEchappe")
        problemes = repli_visible(
            "image absente", make_wood_part(material_id="erable", doc=doc).ViewObject
        )
        attendu = "bib\\u202e\\nliotheque-" + "x" * 60 + "/textures/absente.png"
        problemes += [
            *ecarts("avertissements", len(avertissements), 1),
            *ecarts("chemin entier et échappé", all(attendu in m for m in avertissements), True),
            *ecarts(
                "caractères non imprimables",
                [m for m in avertissements if not m.isprintable()],
                [],
            ),
        ]
        App.closeDocument(doc.Name)
    return problemes


def commutateur_sous(noeud: Any) -> bool:
    """Vrai si un ``SoSwitch`` « MenuiserieTexture » actif est atteint sous ``noeud``."""
    from pivy import coin

    recherche = coin.SoSearchAction()
    recherche.setName(coin.SbName("MenuiserieTexture"))
    recherche.setInterest(coin.SoSearchAction.ALL)
    recherche.setSearchingAll(True)
    recherche.apply(noeud)
    chemins = recherche.getPaths()
    return any(chemins[i].getTail().whichChild.getValue() == 0 for i in range(chemins.getLength()))


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
    verifier_texture_annuler_retablir,
    verifier_texture_recalcul,
    verifier_texture_fichiers_pieges,
    verifier_texture_orientation_des_pixels,
    verifier_texture_image_remplacee,
    verifier_texture_bibliotheque_modifiee,
    verifier_texture_documents_multiples,
    verifier_texture_confinement,
    verifier_texture_jpeg_balayages,
    verifier_texture_bombe_png,
    verifier_texture_budget_memoire,
    verifier_texture_chemin_echappe,
    *VERIFICATIONS_PANNEAU,
    *VERIFICATIONS_APERCU,
    *VERIFICATIONS_SELECTION,
    *VERIFICATIONS_LIMITES,
    *VERIFICATIONS_FIL,
    *VERIFICATIONS_ROBUSTESSE,
    *VERIFICATIONS_ASSEMBLAGES,
    *VERIFICATIONS_PANNEAU_ASSEMBLAGE,
    *VERIFICATIONS_TRANSPARENCE_ASSEMBLAGE,
    *VERIFICATIONS_USINAGE_DEPLACEMENT,
    *VERIFICATIONS_QUEUE_ARONDE,
    *VERIFICATIONS_ONGLET,
    *VERIFICATIONS_ENSEMBLE,
    *VERIFICATIONS_PANNEAU_ENSEMBLE,
    *VERIFICATIONS_PANNEAU_VERROUS,
    # Gabarits (J4d)
    *VERIFICATIONS_CAISSON,
    # Liste de débit (J2d)
    *VERIFICATIONS_DEBIT,
    *VERIFICATIONS_DOUBLE_CLIC,
    # Glisser une pièce à la souris (SM-c)
    *VERIFICATIONS_SOURIS,
    *VERIFICATIONS_SOURIS_DOCUMENT,
    # Assemblage défait au relâchement (ADR 0024)
    *VERIFICATIONS_ARONDE_RELACHEMENT,
    # Distance entre deux pièces (DI-b)
    *VERIFICATIONS_DISTANCE,
    *VERIFICATIONS_DISTANCE_GARDEE,
    # Pièce en bois à forme libre (PD-d)
    *VERIFICATIONS_PIECE_EN_BOIS,
    *VERIFICATIONS_PIECE_EN_BOIS_LIMITES,
    *VERIFICATIONS_SOURIS_PIECE_EN_BOIS,
    # Pièce en bois dans un ensemble (PD-f)
    *VERIFICATIONS_PIECE_EN_BOIS_ENSEMBLE,
)


def verifier(rapport: Any = None) -> list[str]:
    """Retourne la liste des problèmes constatés (vide si tout va bien). ``rapport`` reçoit
    le nom de la vérification en cours : si FreeCAD plante, le fichier désigne la coupable."""
    problemes: list[str] = []
    for verification in VERIFICATIONS:
        if rapport is not None:
            rapport.seek(0)
            rapport.truncate()
            rapport.write(f"plantage pendant {verification.__name__}\n")
            rapport.flush()
        try:
            problemes += [f"{verification.__name__} : {p}" for p in verification()]
        except Exception:
            problemes.append(f"{verification.__name__} : {traceback.format_exc()}")
    return problemes


def main() -> None:
    with open(os.environ["RESULTAT"], "w", encoding="utf-8") as rapport:
        problemes = verifier(rapport)
        rapport.seek(0)
        rapport.truncate()
        lignes = problemes or ["OK : atelier chargé et pièces affichées"]
        # Défauts connus (équivalent de xfail strict) : rapportés après le résultat.
        rapport.write("\n".join([*lignes, *DEFAUTS_CONSTATES]) + "\n")
    # Quitte immédiatement, sans boîte de dialogue ni boucle d'événements.
    os._exit(1 if problemes else 0)


main()
