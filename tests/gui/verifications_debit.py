# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la liste de débit (J2d, critères G1 à G3 de
``docs/specs/J2-liste-de-debit.md``) : commandes, feuille ouverte dans un onglet, portée
(sélection ou document), mise à jour, export CSV (boîte d'enregistrement remplacée par un
double), refus, recalcul préalable, sélection intacte, liste vivante (J2f : l'objet de mise à jour
suit les cotes sans relancer la commande), export PDF et numérotation des repères
(J2g). Module importé par
``verifier_atelier.py`` (lancé par FreeCAD hors écran). Le bureau de référence de J4 (quatre
pièces, tourillons, ensemble) vient de ``tests/integration/bureau.py``.
"""

from __future__ import annotations

import gc
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api
from tests.commandes_debit import COMMANDES_DEBIT
from tests.gui.verifications_assemblages import selectionner
from tests.gui.verifications_ensemble import boite_de_refus, pieces_du_bureau, regrouper
from tests.gui.verifications_panneau import ecarts, emplacements, nouveau_document
from tests.integration.bureau import Bureau

LISTE = "Menuiserie_CutList"
EXPORT = "Menuiserie_CutListExport"
PDF = "Menuiserie_CutListPdf"
NUMEROTER = "Menuiserie_NumberMarks"
APERCU = "Menuiserie_CutListPreview"
MARQUE = "MenuiserieCutList"
COLONNES = "ABCDEFGHIJKLMNO"
LIGNES = 80
BOM = b"\xef\xbb\xbf"


def feuilles(doc: Any) -> list[Any]:
    return [obj for obj in doc.Objects if obj.TypeId == "Spreadsheet::Sheet"]


def cellule(feuille: Any, adresse: str) -> str:
    """Contenu d'une cellule, sans l'apostrophe des textes littéraux."""
    contenu = str(feuille.getContents(adresse))
    return contenu[1:] if contenu.startswith("'") else contenu


def tableau(feuille: Any, colonnes: str = COLONNES) -> list[list[str]]:
    return [[cellule(feuille, f"{c}{n}") for c in colonnes] for n in range(1, LIGNES + 1)]


def reperes(feuille: Any) -> list[str]:
    """Repères de la colonne A (cellules non vides) ; une ligne regroupe ses repères « M1, M3 »."""
    cellules = [ligne[0] for ligne in tableau(feuille, "A") if ligne[0]]
    return [repere for cellule in cellules for repere in cellule.split(", ")]


def a_recalculer(doc: Any) -> list[str]:
    return [obj.Name for obj in doc.Objects if "Touched" in obj.State]


def noms_selectionnes() -> list[str]:
    return [obj.Name for obj in Gui.Selection.getSelection()]


def onglets() -> int:
    """Nombre de vues (onglets) de la fenêtre principale."""
    return len(Gui.getMainWindow().findChildren(QtGui.QMdiSubWindow))


@contextmanager
def boite_d_enregistrement(reponse: str) -> Iterator[list[tuple[str, str, str]]]:
    """Remplace la boîte d'enregistrement de Qt : elle répond ``reponse`` (« » = annulée) et
    note (titre, nom proposé, filtre) de chaque appel ; rétablie en sortie."""
    appels: list[tuple[str, str, str]] = []
    origine = QtGui.QFileDialog.getSaveFileName

    def double(_parent: Any, titre: str, proposition: str, filtre: str) -> tuple[str, str]:
        appels.append((titre, proposition, filtre))
        return reponse, filtre

    QtGui.QFileDialog.getSaveFileName = double
    try:
        yield appels
    finally:
        QtGui.QFileDialog.getSaveFileName = origine


def avec_bureau(nom: str, verification: Callable[[Bureau], list[str]]) -> list[str]:
    """Bureau assemblé (tourillons) regroupé en ensemble, historique d'annulation vidé."""
    with pieces_du_bureau(nom, assemble=True) as bureau:
        regrouper(bureau)
        Gui.Selection.clearSelection()
        return verification(bureau)


# --- G1, G2 : commandes, barre d'outils, menu --------------------------------------------


def verifier_commandes_du_debit() -> list[str]:
    """G1, G2 : libellés, infobulles, icônes, barre d'outils et menu après les ensembles ;
    actives avec un document, inactives sans document."""
    from freecad.menuiserie import icon_path

    problemes: list[str] = list(ecarts("documents ouverts", list(App.listDocuments()), []))
    for nom, libelle in COMMANDES_DEBIT.items():
        commande = Gui.Command.get(nom)
        if commande is None:
            problemes.append(f"commande {nom} absente")
            continue
        infos = commande.getInfo()
        problemes += [
            *ecarts(f"{nom} libellé", infos["menuText"], libelle),
            *ecarts(f"{nom} infobulle renseignée", bool(infos["toolTip"].strip()), True),
            *ecarts(f"{nom} icône", infos["pixmap"], icon_path(f"{nom}.svg")),
            *ecarts(
                f"{nom} icône affichée", [a.icon().isNull() for a in commande.getAction()], [False]
            ),
            *ecarts(
                f"{nom} emplacements",
                sorted(emplacements(nom)),
                [("QMenu", "&Menuiserie"), ("QToolBar", "Menuiserie")],
            ),
            *ecarts(f"{nom} active sans document", commande.isActive(), False),
        ]

    def actives(_bureau: Bureau) -> list[str]:
        return [
            probleme
            for nom in COMMANDES_DEBIT
            for probleme in ecarts(f"{nom} active", Gui.Command.get(nom).isActive(), True)
        ]

    return problemes + avec_bureau("VerifDebitCommandes", actives)


# --- G1 : liste de débit ----------------------------------------------------------------


def _liste_du_document(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    doc.clearUndos()
    avant = onglets()
    Gui.Command.get(LISTE).run()
    [feuille] = feuilles(doc) or [None]
    if feuille is None:
        return ["aucune feuille créée"]
    attendus = ["Plateau", "Joue gauche", "Joue droite", "Voile"]
    return [
        *ecarts("nom interne", feuille.Name, MARQUE),
        *ecarts("libellé", feuille.Label, "Liste de débit"),
        *ecarts("marque", getattr(feuille, MARQUE, None), True),
        *ecarts("pièces listées", sorted(set(attendus) & set(reperes(feuille))), sorted(attendus)),
        *ecarts("une entrée d'annulation", doc.UndoNames, ["Liste de débit"]),
        *ecarts("ouverte dans un onglet", onglets(), avant + 1),
        *ecarts("rien à recalculer", a_recalculer(doc), []),
    ]


def verifier_liste_du_document() -> list[str]:
    """G1 : sans sélection, la feuille couvre tout le document, est ouverte dans un onglet, une
    seule entrée d'annulation."""
    return avec_bureau("VerifDebitDocument", _liste_du_document)


def _liste_de_la_selection(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    joue, voile = bureau.shown("JG"), bureau.shown("V")
    # La joue est sélectionnée par deux faces : un seul objet dans la portée.
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(joue, "Face1")
    Gui.Selection.addSelection(joue, "Face2")
    Gui.Selection.addSelection(voile)
    avant = noms_selectionnes()
    Gui.Command.get(LISTE).run()
    [feuille] = feuilles(doc)
    contenu = [cellule(feuille, f"{c}{n}") for n in range(1, 8) for c in "ABC"]
    return [
        *ecarts("portée citée", "Sélection : 2 objets" in contenu, True),
        *ecarts("pièces listées", sorted(set(reperes(feuille)) & {"Plateau", "Voile"}), ["Voile"]),
        *ecarts("sélection intacte", noms_selectionnes(), avant),
    ]


def verifier_liste_de_la_selection() -> list[str]:
    """G1, G3 : sélection de pièces (doublons écartés) = portée de la liste ; sélection
    inchangée."""
    return avec_bureau("VerifDebitSelection", _liste_de_la_selection)


def _liste_d_un_ensemble(bureau: Bureau) -> list[str]:
    selectionner(bureau.furniture)
    Gui.Command.get(LISTE).run()
    [feuille] = feuilles(bureau.doc)
    attendus = ["Plateau", "Joue gauche", "Joue droite", "Voile"]
    return [
        *ecarts(
            "pièces de l'ensemble", sorted(set(attendus) & set(reperes(feuille))), sorted(attendus)
        ),
        *ecarts("ensemble resté sélectionné", noms_selectionnes(), [bureau.furniture.Name]),
    ]


def verifier_liste_d_un_ensemble() -> list[str]:
    """G1 : un ensemble seul sélectionné donne la liste de toutes ses pièces."""
    return avec_bureau("VerifDebitEnsemble", _liste_d_un_ensemble)


def _liste_avec_lien(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    lien = doc.addObject("App::Link", "LienPlateau")
    lien.LinkedObject = bureau.shown("P")
    doc.recompute()
    Gui.Command.get(LISTE).run()
    [feuille] = feuilles(doc)
    ligne = next((ligne for ligne in tableau(feuille) if ligne[0] == "Plateau"), None)
    return ["ligne du plateau absente"] if ligne is None else ecarts("quantité", ligne[1], "2")


def verifier_liste_avec_un_lien() -> list[str]:
    """G1 : une pièce vue par un ``App::Link`` compte une fois de plus."""
    return avec_bureau("VerifDebitLien", _liste_avec_lien)


def _mise_a_jour(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    Gui.Command.get(LISTE).run()
    [feuille] = feuilles(doc)
    feuille.set("P2", "ma note")
    doc.recompute()
    doc.clearUndos()
    selectionner(bureau.shown("V"))
    Gui.Command.get(LISTE).run()
    problemes = [
        *ecarts("toujours une seule feuille", [f.Name for f in feuilles(doc)], [MARQUE]),
        *ecarts("colonne P gardée", cellule(feuille, "P2"), "ma note"),
        *ecarts("pièces écrites", sorted(set(reperes(feuille)) & {"Plateau", "Voile"}), ["Voile"]),
        *ecarts("entrée d'annulation", doc.UndoNames, ["Liste de débit"]),
    ]
    doc.undo()
    return problemes + ecarts("annulation : liste précédente", "Plateau" in reperes(feuille), True)


def verifier_mise_a_jour_et_annulation() -> list[str]:
    """G1 : relancer la commande réécrit la feuille (colonne P gardée) ; Annuler la restaure."""
    return avec_bureau("VerifDebitMiseAJour", _mise_a_jour)


def _recalcul_prealable(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    bureau.shown("P").touch()
    problemes = ecarts("objet à recalculer", bool(a_recalculer(doc)), True)
    Gui.Command.get(LISTE).run()
    return problemes + ecarts("document recalculé", a_recalculer(doc), [])


def verifier_recalcul_avant_le_calcul() -> list[str]:
    """G1 : un objet « Touched » est recalculé avant le calcul de la liste."""
    return avec_bureau("VerifDebitRecalcul", _recalcul_prealable)


def _liste_vivante(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    Gui.Command.get(LISTE).run()
    Gui.Command.get(LISTE).run()  # relancée : retrouve la feuille et l'objet, n'en crée pas
    [feuille] = feuilles(doc)
    objets = [o for o in doc.Objects if o.Name == "CutList"]
    problemes = [
        *ecarts("un seul objet de mise à jour", len(objets), 1),
        *ecarts("relié à la feuille", [o.Sheet for o in objets], [feuille]),
        *ecarts(
            "pièces lues",
            {p.Name for p in bureau.parts.values()} <= {o.Name for o in objets[0].Sources},
            True,
        ),
    ]
    doc.clearUndos()
    bureau.furniture.Width = 1400  # sans relancer la commande : le recalcul suffit
    doc.recompute()
    plateau = next((ligne for ligne in tableau(feuille) if ligne[0] == "Plateau"), ["", "", ""])
    return [
        *problemes,
        *ecarts("plateau suit la largeur", plateau[2], "1400"),
        *ecarts("rien à recalculer", a_recalculer(doc), []),
        *ecarts("aucun objet en erreur", [o.Name for o in doc.Objects if "Invalid" in o.State], []),
    ]


def verifier_liste_vivante() -> list[str]:
    """J2f : après la commande, un recalcul du document suffit à mettre la feuille à jour ; un
    seul objet de mise à jour, même si la commande est relancée."""
    return avec_bureau("VerifDebitVivante", _liste_vivante)


def _suppression_sans_avertissement(bureau: Bureau) -> list[str]:
    from freecad.menuiserie import api
    from freecad.menuiserie.gui.view_providers.cutlist import ViewProviderCutList

    doc = bureau.doc
    extra = api.make_wood_part(500, 100, 20, "chene", mark="Extra", doc=doc)
    Gui.Command.get(LISTE).run()
    objet = doc.getObject("CutList")
    if objet is None:
        return ["objet de mise à jour absent"]
    etranger = doc.addObject("Part::Box", "Etranger")
    proxy = objet.ViewObject.Proxy
    problemes = [
        *ecarts("ViewProvider posé", isinstance(proxy, ViewProviderCutList), True),
        *ecarts("canDelete d'une pièce lue", proxy.canDelete(extra), True),
        *ecarts("canDelete d'un objet étranger", proxy.canDelete(etranger), False),
        *ecarts("icône", proxy.getIcon().endswith("Menuiserie_CutList.svg"), True),
    ]
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(extra)
    Gui.runCommand("Std_Delete")  # une boîte d'avertissement bloquerait ici (délai de la CI)
    Gui.Selection.clearSelection()
    doc.recompute()
    return [
        *problemes,
        *ecarts("pièce supprimée", doc.getObject("Extra") is None, True),
        *ecarts("liste sans la pièce", "Extra" in reperes(feuilles(doc)[0]), False),
        *ecarts("liste conservée", doc.getObject("CutList") is not None, True),
        *ecarts("aucun objet en erreur", [o.Name for o in doc.Objects if "Invalid" in o.State], []),
        *ecarts("rien à recalculer", a_recalculer(doc), []),
    ]


def verifier_suppression_sans_avertissement() -> list[str]:
    """J2f : le ViewProvider de la liste laisse supprimer une pièce lue sans l'avertissement
    « objets référencés » ; la liste se recalcule sans elle."""
    return avec_bureau("VerifDebitSuppression", _suppression_sans_avertissement)


# --- G2, G3 : export CSV ------------------------------------------------------------------


def _export(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    with tempfile.TemporaryDirectory() as dossier:
        document = Path(dossier) / "bureau.FCStd"
        doc.saveAs(str(document))
        doc.clearUndos()
        cible = Path(dossier) / "debit.csv"
        selectionner(bureau.shown("V"))
        avant = (noms_selectionnes(), [o.Name for o in doc.Objects], doc.UndoNames)
        with boite_d_enregistrement(str(cible)) as appels:
            Gui.Command.get(EXPORT).run()
        octets = cible.read_bytes() if cible.exists() else b""
        message = Gui.getMainWindow().statusBar().currentMessage()
        proposition = appels[0][1] if appels else ""
        return [
            *ecarts("une boîte d'enregistrement", len(appels), 1),
            *ecarts(
                "nom proposé", proposition, str(Path(dossier) / f"{doc.Label} - liste de débit.csv")
            ),
            *ecarts("filtre", "*.csv" in appels[0][2] if appels else None, True),
            *ecarts("BOM UTF-8", octets.startswith(BOM), True),
            *ecarts("pièce exportée", "Voile" in octets.decode("utf-8-sig"), True),
            *ecarts("portée : plateau absent", "Plateau" in octets.decode("utf-8-sig"), False),
            *ecarts("confirmation dans la barre d'état", str(cible) in message, True),
            *ecarts("document inchangé", ([o.Name for o in doc.Objects], doc.UndoNames), avant[1:]),
            *ecarts("aucune feuille créée", feuilles(doc), []),
            *ecarts("sélection intacte", noms_selectionnes(), avant[0]),
            *ecarts("rien à recalculer", a_recalculer(doc), []),
        ]


def verifier_export_csv() -> list[str]:
    """G2, G3 : boîte d'enregistrement (nom proposé à côté du document, filtre CSV), fichier
    écrit, confirmation dans la barre d'état, document et sélection inchangés."""
    return avec_bureau("VerifDebitExport", _export)


def verifier_export_sans_extension() -> list[str]:
    """G2 : document non enregistré = nom proposé dans le dossier personnel ; « .csv » est
    ajouté à un nom saisi sans extension."""
    with pieces_du_bureau("VerifDebitSansExtension") as bureau:
        with boite_d_enregistrement("") as appels:
            Gui.Command.get(EXPORT).run()
        propose = Path(appels[0][1]) if appels else Path()
        problemes = [
            *ecarts("document non enregistré", bureau.doc.FileName, ""),
            *ecarts("dossier personnel", propose.parent, Path.home()),
            *ecarts("nom", propose.name, f"{bureau.doc.Label} - liste de débit.csv"),
        ]
        with tempfile.TemporaryDirectory() as dossier:
            with boite_d_enregistrement(str(Path(dossier) / "sans")):
                Gui.Command.get(EXPORT).run()
            return problemes + ecarts(
                "extension ajoutée", (Path(dossier) / "sans.csv").is_file(), True
            )


def refus_visible() -> bool:
    """Boîte de refus affichée (elle est réutilisée : une boîte masquée ne compte pas)."""
    boite = boite_de_refus()
    return boite is not None and boite.isVisible()


def _export_annule_ou_refuse(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    doc.clearUndos()
    with tempfile.TemporaryDirectory() as dossier:
        with boite_d_enregistrement("") as appels:
            Gui.Command.get(EXPORT).run()
        problemes = [
            *ecarts("boîte ouverte", len(appels), 1),
            *ecarts("annulé : aucun fichier", list(Path(dossier).iterdir()), []),
            *ecarts("annulé : pas de refus", refus_visible(), False),
        ]
        refuse = Path(dossier) / "debit.txt"
        with boite_d_enregistrement(str(refuse)):
            Gui.Command.get(EXPORT).run()
        boite = boite_de_refus()
        problemes += [
            *ecarts("refus : aucun fichier", refuse.exists(), False),
            *ecarts("refus : boîte affichée", boite is not None and boite.isVisible(), True),
            *ecarts("refus : cite .csv", boite is not None and ".csv" in boite.text(), True),
            *ecarts("refus : document inchangé", doc.UndoNames, []),
        ]
        if boite is not None:
            boite.hide()
    return problemes


def verifier_export_annule_ou_refuse() -> list[str]:
    """G2 : boîte annulée = rien ; chemin refusé (extension) = boîte d'avertissement."""
    return avec_bureau("VerifDebitRefus", _export_annule_ou_refuse)


def _export_recalcule(bureau: Bureau) -> list[str]:
    bureau.shown("P").touch()
    with (
        tempfile.TemporaryDirectory() as dossier,
        boite_d_enregistrement(str(Path(dossier) / "debit.csv")),
    ):
        Gui.Command.get(EXPORT).run()
    return ecarts("document recalculé", a_recalculer(bureau.doc), [])


def verifier_export_recalcule_le_document() -> list[str]:
    """G2 : un objet « Touched » est recalculé avant l'export (seule modification permise)."""
    return avec_bureau("VerifDebitExportRecalcul", _export_recalcule)


def _export_pdf(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    with tempfile.TemporaryDirectory() as dossier:
        doc.saveAs(str(Path(dossier) / "bureau.FCStd"))
        doc.clearUndos()
        cible = Path(dossier) / "debit.pdf"
        selectionner(bureau.shown("V"))
        avant = (noms_selectionnes(), [o.Name for o in doc.Objects], doc.UndoNames)
        with boite_d_enregistrement(str(cible)) as appels:
            Gui.Command.get(PDF).run()
        octets = cible.read_bytes() if cible.exists() else b""
        message = Gui.getMainWindow().statusBar().currentMessage()
        # Écriture atomique : aucun fichier temporaire ne reste.
        restes = [p.name for p in Path(dossier).iterdir() if p.suffix == ".tmp"]
        return [
            *ecarts("une boîte d'enregistrement", len(appels), 1),
            *ecarts(
                "nom proposé",
                appels[0][1] if appels else "",
                str(Path(dossier) / f"{doc.Label} - liste de débit.pdf"),
            ),
            *ecarts("filtre", "*.pdf" in appels[0][2] if appels else None, True),
            *ecarts("le PDF existe et commence par %PDF", octets[:4], b"%PDF"),
            *ecarts("PDF non vide", len(octets) > 1000, True),
            *ecarts("aucun temporaire", restes, []),
            *ecarts("confirmation dans la barre d'état", str(cible) in message, True),
            *ecarts("document inchangé", ([o.Name for o in doc.Objects], doc.UndoNames), avant[1:]),
            *ecarts("sélection intacte", noms_selectionnes(), avant[0]),
        ]


def verifier_export_pdf() -> list[str]:
    """P2 : boîte d'enregistrement (filtre PDF, nom proposé), PDF valide écrit, confirmation,
    document et sélection inchangés."""
    return avec_bureau("VerifDebitPdf", _export_pdf)


def _export_pdf_sans_extension_ou_refuse(bureau: Bureau) -> list[str]:
    with tempfile.TemporaryDirectory() as dossier:
        with boite_d_enregistrement(str(Path(dossier) / "sans")):
            Gui.Command.get(PDF).run()
        problemes = list(ecarts("extension ajoutée", (Path(dossier) / "sans.pdf").is_file(), True))
        refuse = Path(dossier) / "debit.csv"
        with boite_d_enregistrement(str(refuse)):
            Gui.Command.get(PDF).run()
        boite = boite_de_refus()
        problemes += [
            *ecarts("refus : aucun fichier", refuse.exists(), False),
            *ecarts("refus : boîte affichée", boite is not None and boite.isVisible(), True),
            *ecarts("refus : cite .pdf", boite is not None and ".pdf" in boite.text(), True),
        ]
        if boite is not None:
            boite.hide()
        with boite_d_enregistrement("") as appels:
            Gui.Command.get(PDF).run()
        return problemes + ecarts("annulé : boîte ouverte une fois", len(appels), 1)


def verifier_export_pdf_extension_et_refus() -> list[str]:
    """P2 : « .pdf » ajouté à un nom sans extension ; une autre extension est refusée en boîte."""
    return avec_bureau("VerifDebitPdfRefus", _export_pdf_sans_extension_ou_refuse)


def _repere(piece: Any) -> str:
    return str(piece.Mark)


def verifier_numerotation_des_reperes() -> list[str]:
    """N1 : sans sélection, les pièces sans repère reçoivent M1… sans trou (deux pièces
    identiques partagent leur repère), une seule entrée d'annulation, message dans la barre
    d'état ; un second lancement ne change rien ; la sélection est numérotée seule."""
    doc = nouveau_document("VerifDebitNumerotation")
    nom_du_document = doc.Name
    try:
        grande = api.make_wood_part(800.0, 100.0, 22.0, "chene", doc=doc)
        jumelle = api.make_wood_part(800.0, 100.0, 22.0, "chene", doc=doc)
        petite = api.make_wood_part(300.0, 100.0, 22.0, "chene", doc=doc)
        doc.recompute()
        doc.clearUndos()
        Gui.Selection.clearSelection()
        Gui.Command.get(NUMEROTER).run()
        message = Gui.getMainWindow().statusBar().currentMessage()
        reperes_obtenus = sorted({_repere(p) for p in (grande, jumelle, petite)})
        problemes = [
            *ecarts("repères sans trou", reperes_obtenus, ["M1", "M2"]),
            *ecarts("identiques : même repère", _repere(grande), _repere(jumelle)),
            *ecarts("la plus grande d'abord", _repere(grande), "M1"),
            *ecarts("une entrée d'annulation", doc.UndoNames, ["Numéroter les repères"]),
            *ecarts("message dans la barre d'état", "2" in message, True),
            *ecarts("rien à recalculer", a_recalculer(doc), []),
        ]
        avant = [_repere(p) for p in (grande, jumelle, petite)]
        Gui.Command.get(NUMEROTER).run()
        problemes += ecarts(
            "relancer : inchangé", [_repere(p) for p in (grande, jumelle, petite)], avant
        )
        autre = api.make_wood_part(500.0, 100.0, 22.0, "chene", doc=doc)
        neuve = api.make_wood_part(450.0, 100.0, 22.0, "chene", doc=doc)
        doc.recompute()
        selectionner(neuve)
        Gui.Command.get(NUMEROTER).run()
        return [
            *problemes,
            *ecarts("sélection : pièce choisie numérotée", _repere(neuve), "M3"),
            *ecarts("sélection : l'autre inchangée", _repere(autre), ""),
        ]
    finally:
        Gui.Selection.clearSelection()
        if nom_du_document in App.listDocuments():
            App.closeDocument(nom_du_document)


# --- Aperçu avant l'export (demande de jv du 2026-10-22, critères A1 à A4) ---------------------

NOMS_APERCU = {
    "fenetre": "MenuiserieCutListPreview",
    "navigateur": "MenuiserieCutListPreviewBrowser",
    "actualiser": "MenuiserieCutListPreviewRefresh",
    "pdf": "MenuiserieCutListPreviewPdf",
    "csv": "MenuiserieCutListPreviewCsv",
    "fermer": "MenuiserieCutListPreviewClose",
}
LIBELLES_APERCU = {
    "actualiser": "Actualiser",
    "pdf": "Exporter en PDF…",
    "csv": "Exporter en CSV…",
    "fermer": "Fermer",
}
SOURCE_IMAGE = 'src="data:image/svg+xml;base64,'


def widgets_apercu() -> dict[str, Any]:
    """Fenêtre d'aperçu, son navigateur et ses boutons par clé (absents si la fenêtre est
    fermée). Cherchés parmi ``allWidgets()``, ramasse-miettes suspendu : ``findChild`` sur la
    fenêtre principale garderait l'enveloppe Python de la fenêtre après sa fermeture."""
    gc.collect()
    gc.disable()
    try:
        noms = {nom: cle for cle, nom in NOMS_APERCU.items()}
        return {
            noms[w.objectName()]: w
            for w in QtGui.QApplication.allWidgets()
            if w.objectName() in noms
        }
    finally:
        gc.enable()


def fermer_les_apercus() -> None:
    """Ferme toute fenêtre d'aperçu ouverte et laisse Qt la détruire (suppression différée)."""
    trouves = widgets_apercu()
    if "fenetre" in trouves:
        trouves["fenetre"].close()
    trouves.clear()
    gc.collect()
    QtGui.QApplication.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def pixels_de_bois(navigateur: Any) -> int:
    """Pixels brun clair du rendu du navigateur : les miniatures (matériau chêne, ombré) sont
    dessinées. Les bordures et fonds du tableau sont gris, le texte noir."""
    QtGui.QApplication.processEvents()
    image = navigateur.viewport().grab().toImage()
    compte = 0
    for y in range(image.height()):
        for x in range(image.width()):
            couleur = QtGui.QColor(image.pixel(x, y))
            rouge, vert, bleu = couleur.red(), couleur.green(), couleur.blue()
            if rouge > vert > bleu and rouge - bleu > 50 and rouge > 100:
                compte += 1
    return compte


def etat_du_document(doc: Any) -> tuple[Any, ...]:
    return ([o.Name for o in doc.Objects], doc.UndoNames, a_recalculer(doc), noms_selectionnes())


def _ouverture_de_l_apercu(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    doc.clearUndos()
    avant = etat_du_document(doc)
    lignes = api.cut_list_of(doc).lines
    Gui.Command.get(APERCU).run()
    trouves = widgets_apercu()
    problemes = ecarts("éléments de la fenêtre", sorted(trouves), sorted(NOMS_APERCU))
    if problemes:
        fermer_les_apercus()
        return problemes
    fenetre, navigateur = trouves["fenetre"], trouves["navigateur"]
    html = navigateur.toHtml()
    problemes = [
        *ecarts("fenêtre visible", fenetre.isVisible(), True),
        *ecarts("fenêtre non modale", fenetre.isModal(), False),
        *ecarts("aucune boîte modale", QtGui.QApplication.activeModalWidget(), None),
        *ecarts("titre", fenetre.windowTitle().startswith("Aperçu de la liste de débit"), True),
        *ecarts("titre : document", doc.Label in fenetre.windowTitle(), True),
        *ecarts("une image par ligne", html.count("<img"), len(lignes)),
        *ecarts("miniatures en data:", html.count(SOURCE_IMAGE), len(lignes)),
        *ecarts("aucune ressource externe", "http" in html.replace("http://www.w3.org", ""), False),
        *ecarts("miniatures dessinées", pixels_de_bois(navigateur) > 500, True),
        *ecarts("colonne Miniature", "Miniature" in navigateur.toPlainText(), True),
        *ecarts("pièces listées", "Voile" in navigateur.toPlainText(), True),
        *ecarts("liens non suivis", navigateur.openLinks(), False),
    ]
    for cle, libelle in LIBELLES_APERCU.items():
        problemes += ecarts(f"bouton {cle}", trouves[cle].text(), libelle)
        problemes += ecarts(f"bouton {cle} actif", trouves[cle].isEnabled(), True)
    problemes += ecarts("lecture seule : document inchangé", etat_du_document(doc), avant)
    del fenetre, navigateur, trouves
    fermer_les_apercus()
    return [*problemes, *ecarts("fermée : plus de widget", sorted(widgets_apercu()), [])]


def verifier_apercu_ouverture() -> list[str]:
    """A1, A2 : commande d'aperçu, fenêtre non modale avec navigateur (une image ``data:`` par
    ligne, réellement dessinée) et quatre boutons ; document et sélection inchangés ; la
    fermeture détruit la fenêtre."""
    return avec_bureau("VerifDebitApercu", _ouverture_de_l_apercu)


def _exports_depuis_l_apercu(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    with tempfile.TemporaryDirectory() as dossier:
        doc.saveAs(str(Path(dossier) / "bureau.FCStd"))
        doc.clearUndos()
        Gui.Command.get(APERCU).run()
        trouves = widgets_apercu()
        if "pdf" not in trouves:
            fermer_les_apercus()
            return ["aperçu non ouvert"]
        avant = etat_du_document(doc)
        nombre_de_lignes = len(api.cut_list_of(doc).lines)
        pdf, csv = Path(dossier) / "debit.pdf", Path(dossier) / "debit.csv"
        with boite_d_enregistrement(str(pdf)) as appels_pdf:
            trouves["pdf"].click()
        with boite_d_enregistrement(str(csv)) as appels_csv:
            trouves["csv"].click()
        octets = pdf.read_bytes() if pdf.exists() else b""
        texte = csv.read_bytes().decode("utf-8-sig") if csv.exists() else ""
        with boite_d_enregistrement("") as annule:
            trouves["pdf"].click()
        trouves["actualiser"].click()
        html = trouves["navigateur"].toHtml()
        problemes = [
            *ecarts("PDF : une boîte", len(appels_pdf), 1),
            *ecarts("PDF : filtre", "*.pdf" in appels_pdf[0][2] if appels_pdf else None, True),
            *ecarts("PDF : valide", octets[:4], b"%PDF"),
            *ecarts("PDF : images des miniatures", octets.count(b"/Subtype /Image") >= 1, True),
            *ecarts("CSV : une boîte", len(appels_csv), 1),
            *ecarts("CSV : écrit", texte.startswith("Repère,"), True),
            *ecarts("export annulé : une boîte", len(annule), 1),
            *ecarts("actualisé : une image par ligne", html.count("<img"), nombre_de_lignes),
            *ecarts("fenêtre toujours ouverte", "fenetre" in widgets_apercu(), True),
            *ecarts("aucune boîte modale", QtGui.QApplication.activeModalWidget(), None),
            *ecarts("document inchangé", etat_du_document(doc), avant),
        ]
        del trouves
        fermer_les_apercus()
        return problemes


def verifier_apercu_exports() -> list[str]:
    """A3, A4 : depuis l'aperçu, « Exporter en PDF… » écrit un PDF qui contient les images,
    « Exporter en CSV… » le CSV, une annulation ne fait rien, « Actualiser » garde les
    miniatures ; la fenêtre reste ouverte et le document inchangé."""
    return avec_bureau("VerifDebitApercuExports", _exports_depuis_l_apercu)


def _apercu_de_la_selection(bureau: Bureau) -> list[str]:
    selectionner(bureau.shown("V"))
    avant = noms_selectionnes()
    Gui.Command.get(APERCU).run()
    trouves = widgets_apercu()
    if "navigateur" not in trouves:
        return ["aperçu non ouvert"]
    texte, html = trouves["navigateur"].toPlainText(), trouves["navigateur"].toHtml()
    problemes = [
        *ecarts("portée : une seule ligne", html.count("<img"), 1),
        *ecarts("portée : voile listé", "Voile" in texte, True),
        *ecarts("portée : plateau absent", "Plateau" in texte, False),
        *ecarts("sélection intacte", noms_selectionnes(), avant),
    ]
    del trouves
    fermer_les_apercus()
    return problemes


def verifier_apercu_de_la_selection() -> list[str]:
    """A1 : la portée de l'aperçu est la sélection (une miniature par ligne retenue)."""
    return avec_bureau("VerifDebitApercuSelection", _apercu_de_la_selection)


VERIFICATIONS_DEBIT: tuple[Callable[[], list[str]], ...] = (
    verifier_commandes_du_debit,
    verifier_liste_du_document,
    verifier_liste_de_la_selection,
    verifier_liste_d_un_ensemble,
    verifier_liste_avec_un_lien,
    verifier_mise_a_jour_et_annulation,
    verifier_recalcul_avant_le_calcul,
    verifier_liste_vivante,
    verifier_suppression_sans_avertissement,
    verifier_export_csv,
    verifier_export_sans_extension,
    verifier_export_annule_ou_refuse,
    verifier_export_recalcule_le_document,
    verifier_export_pdf,
    verifier_export_pdf_extension_et_refus,
    verifier_numerotation_des_reperes,
    verifier_apercu_ouverture,
    verifier_apercu_exports,
    verifier_apercu_de_la_selection,
)
