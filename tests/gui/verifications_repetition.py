# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la répétition (lot R-c de ``docs/specs/repetition.md``) : commandes
« Répéter », « Modifier la répétition » et « Dissocier la copie », panneau avec aperçu en direct,
refus affichés, ViewProvider de la répétition.

R14 : l'aperçu montre les copies que « OK » crée ; R15 : un refus s'affiche en rouge et grise
« OK » ; R16 : changer le nombre par le panneau d'une répétition existante. Module importé par
``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification renvoie la liste de
ses problèmes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie import api, icon_path
from freecad.menuiserie.features import repeat
from tests.commandes_repetition import COMMANDES_REPETITION
from tests.gui.verifications_ensemble import lancer, pieces_du_bureau
from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    choisir,
    ecarts,
    emplacements,
    emplacements_attendus,
    formulaire,
    formulaire_nomme,
    saisir,
    valider,
)
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_panneau_ensemble import bouton_ok

REPETER = "Menuiserie_Repeat"
MODIFIER = "Menuiserie_RepeatEdit"
DISSOCIER = "Menuiserie_RepeatDissociate"
FORM = "RepeatTaskPanel"
VP_REPETITION = "freecad.menuiserie.gui.view_providers.repeat.ViewProviderRepeat"
PAR_DEFAUT = 3  # copies proposées à l'ouverture


def source(doc: Any, mark: str = "Barreau") -> Any:
    """Barreau de chêne 300 x 40 x 22 (selon X), recalculé ; historique d'annulation vidé."""
    part = api.make_wood_part(300, 40, 22, "chene", mark=mark, doc=doc)
    doc.recompute()
    doc.clearUndos()
    return part


def copies_de(rep: Any) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep)
    return found


def positions_x(rep: Any) -> list[float]:
    return [round(c.Placement.Base.x, 3) for c in copies_de(rep)]


def panneau() -> Any:
    """Formulaire de la répétition ouvert (``None`` s'il n'y en a pas)."""
    return formulaire_nomme(FORM)


def declaration_classe(obj: Any) -> str:
    proxy = obj.ViewObject.Proxy
    return f"{type(proxy).__module__}.{type(proxy).__qualname__}"


# --- Commandes -----------------------------------------------------------------------------


def verifier_commandes_de_repetition() -> list[str]:
    """Libellés, infobulles, icônes générées, barre d'outils et menu ; activation selon la
    sélection (pièce, copie, rien)."""
    problemes = []
    for nom, (libelle, _transaction) in COMMANDES_REPETITION.items():
        commande = Gui.Command.get(nom)
        if commande is None:
            problemes.append(f"{nom} non enregistrée")
            continue
        infos = commande.getInfo()
        problemes += [
            *ecarts(f"{nom}, libellé", infos["menuText"], libelle),
            *ecarts(f"{nom}, infobulle", bool(infos["toolTip"].strip()), True),
            *ecarts(f"{nom}, icône", infos["pixmap"], icon_path(f"{nom}.svg")),
            *ecarts(f"{nom}, icône affichée", commande.getAction()[0].icon().isNull(), False),
            # Sans doublon : les vérifications précédentes ont réactivé l'atelier, dont le menu a
            # été reconstruit plusieurs fois.
            *ecarts(
                f"{nom}, emplacements",
                sorted(set(emplacements(nom))),
                emplacements_attendus(nom),
            ),
        ]
    return problemes + avec_document("VerifRepetitionCommandes", _activation)


def _activation(doc: Any) -> list[str]:
    def actives() -> list[bool]:
        return [Gui.Command.get(nom).isActive() for nom in COMMANDES_REPETITION]

    barreau = source(doc)
    rep = api.make_repeat([barreau], api.RepeatParams(count=2, step=400.0))
    doc.clearUndos()
    copie = copies_de(rep)[0]
    problemes = []
    for etape, objets, attendu in (
        ("rien", (), [False, False, False]),
        ("pièce", (barreau,), [True, False, False]),
        ("copie", (copie,), [False, True, True]),
        ("répétition", (rep,), [False, True, False]),
        ("pièce et copie", (barreau, copie), [False, False, False]),
    ):
        Gui.Selection.clearSelection()
        for obj in objets:
            Gui.Selection.addSelection(obj)
        problemes += ecarts(f"activation, sélection : {etape}", actives(), attendu)
    Gui.Selection.clearSelection()
    return problemes


# --- R14 : aperçu et validation ------------------------------------------------------------


def _apercu_puis_ok(doc: Any) -> list[str]:
    barreau = source(doc)
    lancer(REPETER, barreau)
    form = panneau()
    rep = doc.getObject("Repeat")
    if form is None or rep is None:
        return ["panneau « Répéter » non ouvert ou aperçu absent"]
    problemes = [
        *ecarts("titre", form.windowTitle(), "Répéter « Barreau »"),
        *ecarts("aperçu à l'ouverture", positions_x(rep), [300.0 * k for k in (1, 2, 3)]),
        *ecarts("assemblages recopiés cochée", widget(form, "copyJoints").isChecked(), True),
        *ecarts("suivi décoché", widget(form, "followResize").isChecked(), False),
        *ecarts("erreur masquée", widget(form, "errorLabel").isHidden(), True),
        *ecarts("maximum de copies", widget(form, "count").maximum(), 100),
    ]
    widget(form, "count").setValue(5)
    saisir(widget(form, "step"), 400.0)
    apercu = [c.Name for c in copies_de(rep)]
    problemes += [
        *ecarts("aperçu en direct, positions", positions_x(rep), [400.0 * k for k in range(1, 6)]),
        *ecarts(
            "aperçu en direct, une seule répétition",
            len(doc.findObjects("App::FeaturePython", "Repeat*")),
            1,
        ),
    ]
    valider()
    rep = doc.getObject("Repeat")
    problemes += [
        *ecarts("panneau fermé", panneau() is None, True),
        *ecarts("copies créées = aperçu", [c.Name for c in copies_de(rep)], apercu),
        *ecarts("nombre", rep.Count, 5),
        *ecarts("entrées", doc.UndoNames, ["Répéter"]),
        *ecarts("ViewProvider", declaration_classe(rep), VP_REPETITION),
        *ecarts("objets invalides", [o.Name for o in doc.Objects if not o.isValid()], []),
    ]
    doc.undo()
    return problemes + ecarts("annulé en un bloc", [o.Name for o in doc.Objects], [barreau.Name])


def verifier_apercu_et_validation() -> list[str]:
    """R14 : copies de l'aperçu = copies créées par « OK » ; une entrée « Répéter »."""
    return avec_document("VerifRepetitionApercu", _apercu_puis_ok)


def _annule(doc: Any) -> list[str]:
    barreau = source(doc)
    lancer(REPETER, barreau)
    form = panneau()
    if form is None:
        return ["panneau « Répéter » non ouvert"]
    widget(form, "count").setValue(4)
    annuler()
    return [
        *ecarts("aucune copie", [o.Name for o in doc.Objects], [barreau.Name]),
        *ecarts("aucune entrée", doc.UndoNames, []),
        *ecarts("panneau fermé", panneau() is None, True),
    ]


def verifier_annulation() -> list[str]:
    """« Annuler » : aucune copie, aucune répétition, aucune entrée d'annulation."""
    return avec_document("VerifRepetitionAnnule", _annule)


# --- R15 : refus et avertissement -----------------------------------------------------------


def _refus(doc: Any) -> list[str]:
    barreau = source(doc)
    lancer(REPETER, barreau)
    form = panneau()
    if form is None:
        return ["panneau « Répéter » non ouvert"]
    erreur = widget(form, "errorLabel")
    saisir(widget(form, "step"), 0.0)
    problemes = [
        *ecarts("refus affiché", erreur.isHidden(), False),
        *ecarts("champ cité", "pas" in erreur.text(), True),
        *ecarts("« OK » grisé", bouton_ok().isEnabled(), False),
        *ecarts("aperçu gardé", len(copies_de(doc.getObject("Repeat"))), PAR_DEFAUT),
    ]
    valider()  # sans effet : le panneau reste ouvert
    problemes += ecarts("panneau resté ouvert", panneau() is not None, True)
    choisir(widget(form, "spacing"), "CountOnSpan")
    saisir(widget(form, "span"), 200.0)  # plus courte que la pièce (300 mm)
    problemes += [
        *ecarts("longueur trop courte refusée", erreur.isHidden(), False),
        *ecarts("longueur citée", "longueur" in erreur.text(), True),
    ]
    saisir(widget(form, "span"), 1275.0)
    rep = doc.getObject("Repeat")
    problemes += [
        *ecarts("refus effacé", erreur.isHidden(), True),
        *ecarts("« OK » rétabli", bouton_ok().isEnabled(), True),
        *ecarts("pas calculé", positions_x(rep), [325.0 * k for k in (1, 2, 3)]),
    ]
    valider()
    return problemes + ecarts("entrées", doc.UndoNames, ["Répéter"])


def verifier_refus_affiche() -> list[str]:
    """R15 : pas nul puis longueur trop courte affichés en rouge, « OK » grisé et sans effet,
    aperçu inchangé ; une saisie valide efface le refus."""
    return avec_document("VerifRepetitionRefus", _refus)


def _chevauchement(doc: Any) -> list[str]:
    barreau = source(doc)
    lancer(REPETER, barreau)
    form = panneau()
    if form is None:
        return ["panneau « Répéter » non ouvert"]
    avertissement = widget(form, "warningLabel")
    saisir(widget(form, "step"), 100.0)
    problemes = [
        *ecarts("avertissement affiché", avertissement.isHidden(), False),
        *ecarts("avertissement, texte", "chevauchent" in avertissement.text(), True),
        *ecarts("« OK » reste actif", bouton_ok().isEnabled(), True),
        *ecarts("copies créées", len(copies_de(doc.getObject("Repeat"))), PAR_DEFAUT),
    ]
    saisir(widget(form, "step"), 400.0)
    return problemes + ecarts("avertissement effacé", avertissement.isHidden(), True)


def verifier_chevauchement_signale() -> list[str]:
    """Pas inférieur à la cote : avertissement non bloquant (« OK » reste actif)."""
    return avec_document("VerifRepetitionChevauchement", _chevauchement)


def _axe_et_sens(doc: Any) -> list[str]:
    barreau = source(doc)
    lancer(REPETER, barreau)
    form = panneau()
    if form is None:
        return ["panneau « Répéter » non ouvert"]
    rep = doc.getObject("Repeat")
    widget(form, "axisY").setChecked(True)
    problemes = ecarts("axe Y : pas = cote sur Y", rep.Axis, "Y")
    problemes += ecarts(
        "axe Y : positions", [round(c.Placement.Base.y) for c in copies_de(rep)], [40, 80, 120]
    )
    widget(form, "reverse").setChecked(True)
    problemes += ecarts(
        "inversé", [round(c.Placement.Base.y) for c in copies_de(rep)], [-40, -80, -120]
    )
    widget(form, "copyJoints").setChecked(False)
    problemes += ecarts("assemblages non recopiés", bool(rep.CopyJoints), False)
    valider()
    return problemes


def verifier_axe_sens_et_assemblages() -> list[str]:
    """Axe Y (pas = cote de la pièce sur Y tant qu'il n'est pas saisi), « Inverser », case
    « Recopier les assemblages »."""
    return avec_document("VerifRepetitionAxe", _axe_et_sens)


# --- Recopier les assemblages ---------------------------------------------------------------


def _assemblages_recopies(doc: Any) -> list[str]:
    def assemblages() -> int:
        return sum(hasattr(obj, "HostPart") for obj in doc.Objects)

    def placee(marque: str, taille: tuple[float, float, float], ou: Any) -> Any:
        part = api.make_wood_part(*taille, "chene", mark=marque, doc=doc)
        part.Placement = ou
        doc.recompute()
        return part

    basse = placee("Basse", (600, 60, 22), App.Placement())
    haute = placee("Haute", (600, 60, 22), App.Placement(App.Vector(0, 340, 0), App.Rotation()))
    barreau = placee(
        "Barreau",
        (280, 40, 22),
        App.Placement(App.Vector(140, 60, 0), App.Rotation(App.Vector(0, 0, 1), 90)),
    )
    api.make_mortise_tenon(basse, barreau)
    api.make_mortise_tenon(haute, barreau)
    doc.recompute()
    doc.clearUndos()
    lancer(REPETER, api.machined_part_of(barreau))  # la pièce visible (usinée) est acceptée
    form = panneau()
    if form is None:
        return ["panneau « Répéter » non ouvert sur la pièce usinée"]
    saisir(widget(form, "step"), 100.0)
    widget(form, "count").setValue(4)
    problemes = ecarts("assemblages recopiés (2 + 4 x 2)", assemblages(), 10)
    widget(form, "copyJoints").setChecked(False)
    problemes += ecarts("case décochée : assemblages enfants retirés", assemblages(), 2)
    widget(form, "copyJoints").setChecked(True)
    problemes += ecarts("case recochée", assemblages(), 10)
    valider()
    problemes += ecarts("entrées", doc.UndoNames, ["Répéter"])
    doc.undo()
    return problemes + ecarts("annulé en un bloc", assemblages(), 2)


def verifier_assemblages_recopies() -> list[str]:
    """Case « Recopier les assemblages » : une pièce usinée est acceptée, ses assemblages sont
    recopiés en direct, retirés quand la case est décochée."""
    return avec_document("VerifRepetitionAssemblages", _assemblages_recopies)


# --- Suivre le redimensionnement ----------------------------------------------------------------


def verifier_suivi_grise_hors_ensemble() -> list[str]:
    """La case « Suivre le redimensionnement » est grisée, infobulle explicative, quand la pièce
    n'est dans aucun ensemble ; active pour un membre d'ensemble."""

    def hors_ensemble(doc: Any) -> list[str]:
        lancer(REPETER, source(doc))
        form = panneau()
        if form is None:
            return ["panneau « Répéter » non ouvert"]
        case = widget(form, "followResize")
        return [
            *ecarts("grisée", case.isEnabled(), False),
            *ecarts("infobulle", "aucun ensemble" in case.toolTip(), True),
        ]

    problemes = avec_document("VerifRepetitionSuivi", hors_ensemble)
    with pieces_du_bureau("VerifRepetitionSuiviEnsemble") as bureau:
        from tests.gui.verifications_ensemble import regrouper

        regrouper(bureau)
        lancer(REPETER, bureau.doc.getObject(bureau.parts["V"].Name))
        form = panneau()
        if form is None:
            return [*problemes, "panneau « Répéter » non ouvert (membre d'ensemble)"]
        case = widget(form, "followResize")
        problemes += [
            *ecarts("active pour un membre", case.isEnabled(), True),
            *ecarts("infobulle du suivi", "redimensionné" in case.toolTip(), True),
        ]
    return problemes


# --- R16 : modifier la répétition ---------------------------------------------------------


def _repetition_existante(doc: Any) -> tuple[Any, Any]:
    barreau = source(doc)
    rep = api.make_repeat([barreau], api.RepeatParams(count=4, step=400.0, axis=api.RepeatAxis.X))
    doc.clearUndos()
    return barreau, rep


def _modifier_le_nombre(doc: Any) -> list[str]:
    _barreau, rep = _repetition_existante(doc)
    lancer(MODIFIER, copies_de(rep)[1])  # depuis une copie
    form = panneau()
    if form is None:
        return ["panneau « Modifier la répétition » non ouvert"]
    problemes = [
        *ecarts("titre", form.windowTitle(), "Modifier « Répétition »"),
        *ecarts("nombre prérempli", widget(form, "count").value(), 4),
        *ecarts("pas prérempli", round(float(widget(form, "step").property("rawValue")), 3), 400.0),
        *ecarts("axe prérempli", widget(form, "axisX").isChecked(), True),
        *ecarts("assemblages prérempli", widget(form, "copyJoints").isChecked(), True),
        *ecarts("entrées avant saisie", doc.UndoNames, []),
    ]
    widget(form, "count").setValue(6)
    problemes += ecarts(
        "aperçu : copies ajoutées", positions_x(rep), [400.0 * k for k in range(1, 7)]
    )
    widget(form, "count").setValue(2)
    problemes += ecarts("aperçu : dernières copies retirées", positions_x(rep), [400.0, 800.0])
    widget(form, "count").setValue(6)
    valider()
    return [
        *problemes,
        *ecarts("panneau fermé", panneau() is None, True),
        *ecarts("copies", len(copies_de(rep)), 6),
        *ecarts("nombre", rep.Count, 6),
        *ecarts("entrées", doc.UndoNames, ["Modifier la répétition"]),
        *ecarts("objets invalides", [o.Name for o in doc.Objects if not o.isValid()], []),
    ]


def verifier_modifier_le_nombre() -> list[str]:
    """R16 : le panneau d'une répétition existante est prérempli ; changer le nombre ajoute ou
    retire des copies en direct ; « OK » = une entrée « Modifier la répétition »."""
    return avec_document("VerifRepetitionModifie", _modifier_le_nombre)


def _modification_annulee(doc: Any) -> list[str]:
    _barreau, rep = _repetition_existante(doc)
    lancer(MODIFIER, rep)  # depuis la répétition
    form = panneau()
    if form is None:
        return ["panneau « Modifier la répétition » non ouvert"]
    widget(form, "count").setValue(2)
    saisir(widget(form, "step"), 500.0)
    annuler()
    rep = doc.getObject("Repeat")
    return [
        *ecarts("copies rétablies", positions_x(rep), [400.0 * k for k in range(1, 5)]),
        *ecarts("nombre rétabli", rep.Count, 4),
        *ecarts("aucune entrée", doc.UndoNames, []),
    ]


def verifier_modification_annulee() -> list[str]:
    """« Annuler » dans « Modifier la répétition » : les copies et le pas sont rétablis."""
    return avec_document("VerifRepetitionModifieAnnule", _modification_annulee)


# --- Dissocier -----------------------------------------------------------------------------


def _dissocier(doc: Any) -> list[str]:
    _barreau, rep = _repetition_existante(doc)
    copie = copies_de(rep)[1]
    lancer(DISSOCIER, copie)
    return [
        *ecarts("copie libre", repeat.is_copy(copie), False),
        *ecarts("autres copies liées", len(copies_de(rep)), 3),
        *ecarts("nombre gardé", rep.Count, 4),
        *ecarts("entrées", doc.UndoNames, ["Dissocier la copie"]),
        *ecarts("valeurs gardées", round(copie.Placement.Base.x, 3), 800.0),
    ]


def verifier_dissocier_la_copie() -> list[str]:
    """« Dissocier la copie » : la copie devient libre en une entrée d'annulation."""
    return avec_document("VerifRepetitionDissocie", _dissocier)


# --- ViewProvider --------------------------------------------------------------------------


def _double_clic(doc: Any) -> list[str]:
    _barreau, rep = _repetition_existante(doc)
    vobj = rep.ViewObject
    from freecad.menuiserie.gui.view_providers.repeat import ensure_view_provider

    ensure_view_provider(rep)  # répétition créée par l'api : ViewProvider posé à la demande
    problemes = [
        *ecarts("ViewProvider", declaration_classe(rep), VP_REPETITION),
        *ecarts("icône", vobj.Proxy.getIcon(), icon_path("Menuiserie_RepeatObject.svg")),
        *ecarts("icône de l'arbre chargée", vobj.Icon.isNull(), False),
    ]
    problemes += ecarts("double-clic sur la répétition", bool(vobj.Proxy.doubleClicked(vobj)), True)
    problemes += ecarts("panneau de la répétition", panneau() is not None, True)
    annuler()
    copie = copies_de(rep)[0]
    copie_vobj = copie.ViewObject
    problemes += ecarts(
        "double-clic sur une copie", bool(copie_vobj.Proxy.doubleClicked(copie_vobj)), True
    )
    problemes += [
        *ecarts("copie : panneau de la pièce", formulaire() is not None, True),
        *ecarts("copie : pas le panneau de la répétition", panneau() is None, True),
    ]
    return problemes


def verifier_double_clic() -> list[str]:
    """Double-clic sur la répétition : « Modifier la répétition » ; sur une copie : le panneau de
    la pièce de bois."""
    return avec_document("VerifRepetitionDoubleClic", _double_clic)


def verifier_document_ferme_panneau_ouvert() -> list[str]:
    """Document fermé, panneau ouvert : le panneau se ferme, la transaction est soldée."""
    doc = App.newDocument("VerifRepetitionFerme")
    doc.UndoMode = 1
    lancer(REPETER, source(doc))
    App.closeDocument(doc.Name)
    QtGui.QApplication.processEvents()
    return [
        *ecarts("panneau fermé", panneau() is None, True),
        *ecarts("aucun panneau actif", bool(Gui.Control.activeDialog()), False),
    ]


VERIFICATIONS_REPETITION: tuple[Callable[[], list[str]], ...] = (
    verifier_commandes_de_repetition,
    verifier_apercu_et_validation,
    verifier_annulation,
    verifier_refus_affiche,
    verifier_chevauchement_signale,
    verifier_axe_sens_et_assemblages,
    verifier_assemblages_recopies,
    verifier_suivi_grise_hors_ensemble,
    verifier_modifier_le_nombre,
    verifier_modification_annulee,
    verifier_dissocier_la_copie,
    verifier_double_clic,
    verifier_document_ferme_panneau_ouvert,
)
