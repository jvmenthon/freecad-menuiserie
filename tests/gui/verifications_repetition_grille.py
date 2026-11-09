# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la répétition en grille (ADR 0045) : panneau « Répéter » à un seul
mode de saisie et trois lignes X, Y, Z, aperçu en direct de toutes les copies, total affiché,
refus au-delà de 100 copies, « Modifier la répétition » prérempli. Module importé par
``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification renvoie la liste de
ses problèmes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from freecad.menuiserie import api
from freecad.menuiserie.features import repeat
from tests.gui.verifications_ensemble import lancer
from tests.gui.verifications_panneau import (
    avec_document,
    choisir,
    ecarts,
    saisir,
    valider,
)
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_panneau_ensemble import bouton_ok
from tests.gui.verifications_repetition import MODIFIER, REPETER, panneau, source

X, Y = api.RepeatAxis.X, api.RepeatAxis.Y


def copies_de(rep: Any) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep)
    return found


def positions(rep: Any) -> list[tuple[float, float]]:
    """Position (x, y) de chaque copie, arrondie, dans l'ordre des rangs."""
    return [(round(c.Placement.Base.x, 3), round(c.Placement.Base.y, 3)) for c in copies_de(rep)]


def grille(nx: int, ny: int, pas_x: float, pas_y: float) -> list[tuple[float, float]]:
    """Positions attendues d'une grille nx x ny (X en premier), sans l'original."""
    return [(pas_x * i, pas_y * j) for j in range(ny) for i in range(nx) if (i, j) != (0, 0)]


def ouvrir(doc: Any) -> tuple[Any, Any]:
    """Panneau « Répéter » ouvert sur un barreau de 300 x 40 x 22 ; sa répétition d'aperçu."""
    lancer(REPETER, source(doc))
    return panneau(), doc.getObject("Repeat")


def _grille_4_x_3(doc: Any) -> list[str]:
    form, rep = ouvrir(doc)
    if form is None or rep is None:
        return ["panneau « Répéter » non ouvert"]
    problemes = [
        *ecarts("trois lignes", [widget(form, f"axis{a}") is not None for a in "XYZ"], [True] * 3),
        *ecarts(
            "un seul mode de saisie",
            len(form.findChildren(type(widget(form, "spacing")), "spacing")),
            1,
        ),
        *ecarts(
            "X seul à l'ouverture",
            [widget(form, f"axis{a}").isChecked() for a in "XYZ"],
            [True, False, False],
        ),
    ]
    widget(form, "axisY").setChecked(True)
    widget(form, "countY").setValue(3)
    saisir(widget(form, "stepX"), 350.0)
    saisir(widget(form, "stepY"), 100.0)
    resume = widget(form, "summaryLabel")
    problemes += [
        *ecarts("aperçu : 4 x 3", positions(rep), grille(4, 3, 350.0, 100.0)),
        *ecarts("total affiché", "11 copies" in resume.text() and "4 x 3" in resume.text(), True),
        *ecarts("une seule répétition", len(doc.findObjects("App::FeaturePython", "Repeat*")), 1),
    ]
    apercu = [c.Name for c in copies_de(rep)]
    valider()
    rep = doc.getObject("Repeat")
    problemes += [
        *ecarts("panneau fermé", panneau() is None, True),
        *ecarts("copies = aperçu", [c.Name for c in copies_de(rep)], apercu),
        *ecarts("nombres de copies par axe", (rep.Count, rep.Count2), (3, 2)),
        *ecarts("entrées", doc.UndoNames, ["Répéter"]),
    ]
    doc.undo()
    return problemes + ecarts("annulé en un bloc", len(doc.Objects), 1)


def verifier_grille_apercu_et_validation() -> list[str]:
    """Exemple de jv : 4 x 3 sur X et Y, pas 350 et 100 mm = 11 copies, une entrée « Répéter »."""
    return avec_document("VerifGrilleApercu", _grille_4_x_3)


def _refus_au_dela_de_cent(doc: Any) -> list[str]:
    form, rep = ouvrir(doc)
    if form is None or rep is None:
        return ["panneau « Répéter » non ouvert"]
    erreur = widget(form, "errorLabel")
    widget(form, "axisY").setChecked(True)
    widget(form, "countY").setValue(3)
    widget(form, "countX").setValue(11)
    avant = [c.Name for c in copies_de(rep)]  # 11 x 3 : 32 copies, dernier réglage accepté
    widget(form, "countY").setValue(10)
    problemes = [
        *ecarts("refus affiché", erreur.isHidden(), False),
        *ecarts(
            "refus expliqué", "109 copies" in erreur.text() and "maximum" in erreur.text(), True
        ),
        *ecarts("« OK » grisé", bouton_ok().isEnabled(), False),
        *ecarts("aperçu gardé", [c.Name for c in copies_de(rep)][: len(avant)], avant),
    ]
    widget(form, "countY").setValue(9)  # 11 x 9 = 99 éléments : 98 copies
    problemes += [
        *ecarts("refus effacé", erreur.isHidden(), True),
        *ecarts("« OK » rétabli", bouton_ok().isEnabled(), True),
        *ecarts("98 copies", len(copies_de(rep)), 98),
    ]
    widget(form, "axisX").setChecked(False)
    widget(form, "axisY").setChecked(False)
    problemes += [
        *ecarts("aucun axe : refus", "aucun axe" in erreur.text(), True),
        *ecarts("aucun axe : « OK » grisé", bouton_ok().isEnabled(), False),
    ]
    widget(form, "axisZ").setChecked(True)
    return problemes + ecarts("un axe suffit", erreur.isHidden(), True)


def verifier_refus_au_dela_de_cent_copies() -> list[str]:
    """Total refusé au-delà de 100 copies (message en rouge, « OK » grisé, aperçu inchangé) ;
    refus aussi sans aucun axe actif."""
    return avec_document("VerifGrilleRefus", _refus_au_dela_de_cent)


def _modes_et_sens(doc: Any) -> list[str]:
    form, rep = ouvrir(doc)
    if form is None or rep is None:
        return ["panneau « Répéter » non ouvert"]
    widget(form, "axisY").setChecked(True)
    widget(form, "countY").setValue(3)
    choisir(widget(form, "spacing"), "CountOnSpan")
    saisir(widget(form, "spanX"), 1500.0)  # 4 éléments de 300 mm : pas (1500 - 300) / 3
    saisir(widget(form, "spanY"), 140.0)  # 3 éléments de 40 mm : pas (140 - 40) / 2
    problemes = [
        *ecarts("nombre sur une longueur", positions(rep), grille(4, 3, 400.0, 50.0)),
        *ecarts(
            "champs du mode",
            [widget(form, n).isHidden() for n in ("stepX", "spanX")],
            [True, False],
        ),
    ]
    choisir(widget(form, "spacing"), "StepOnSpan")
    saisir(widget(form, "stepX"), 450.0)
    saisir(widget(form, "spanX"), 1300.0)  # floor((1300 - 300) / 450) = 2 copies
    saisir(widget(form, "stepY"), 25.0)
    saisir(widget(form, "spanY"), 140.0)  # floor((140 - 40) / 25) = 4 copies
    problemes += [
        *ecarts("pas sur une longueur", positions(rep), grille(3, 5, 450.0, 25.0)),
        *ecarts(
            "nombre calculé",
            (widget(form, "countX").value(), widget(form, "countY").value()),
            (3, 5),
        ),
        *ecarts("champ nombre masqué", widget(form, "countX").isHidden(), True),
    ]
    choisir(widget(form, "spacing"), "CountAndStep")
    widget(form, "reverseY").setChecked(True)
    problemes += [
        *ecarts("sens par axe", positions(rep)[-1], (900.0, -100.0)),
        *ecarts("X dans le sens positif", positions(rep)[0], (450.0, 0.0)),
    ]
    valider()
    rep = doc.getObject("Repeat")
    return problemes + ecarts("sens écrit", (rep.Reverse, rep.Reverse2), (False, True))


def verifier_mode_commun_et_sens_par_axe() -> list[str]:
    """Un seul mode de saisie pour tous les axes (nombre sur une longueur, pas sur une longueur) ;
    « Inverser » propre à chaque axe."""
    return avec_document("VerifGrilleModes", _modes_et_sens)


def _chevauchement(doc: Any) -> list[str]:
    form, rep = ouvrir(doc)
    if form is None or rep is None:
        return ["panneau « Répéter » non ouvert"]
    avertissement = widget(form, "warningLabel")
    widget(form, "axisY").setChecked(True)
    saisir(widget(form, "stepX"), 400.0)
    saisir(widget(form, "stepY"), 100.0)  # la pièce a 40 mm sur Y
    problemes = ecarts("aucun chevauchement", avertissement.isHidden(), True)
    saisir(widget(form, "stepY"), 20.0)
    problemes += [
        *ecarts("chevauchement signalé", avertissement.isHidden(), False),
        *ecarts(
            "sur l'axe Y",
            "axe Y" in avertissement.text() and "axe X" not in avertissement.text(),
            True,
        ),
        *ecarts("« OK » reste actif", bouton_ok().isEnabled(), True),
    ]
    saisir(widget(form, "stepX"), 100.0)
    texte = avertissement.text()
    return problemes + ecarts(
        "deux axes + grille complète",
        "axe X" in texte and "axe Y" in texte and "grille" in texte,
        True,
    )


def verifier_chevauchement_par_axe_et_grille() -> list[str]:
    """Chevauchement signalé par axe, puis pour la grille complète (non bloquant)."""
    return avec_document("VerifGrilleChevauchement", _chevauchement)


def _modifier_une_grille(doc: Any) -> list[str]:
    lignes = (api.AxisRepeat(X, 4, 350.0), api.AxisRepeat(Y, 3, 100.0))
    rep = api.make_repeat([source(doc)], api.RepeatParams(grid=lignes))
    doc.clearUndos()
    avant = {repeat.cell_of(c): c.Name for c in copies_de(rep)}
    lancer(MODIFIER, copies_de(rep)[4])
    form = panneau()
    if form is None:
        return ["panneau « Modifier la répétition » non ouvert"]
    problemes = [
        *ecarts(
            "axes prérempli",
            [widget(form, f"axis{a}").isChecked() for a in "XYZ"],
            [True, True, False],
        ),
        *ecarts(
            "nombres préremplis",
            (widget(form, "countX").value(), widget(form, "countY").value()),
            (4, 3),
        ),
        *ecarts(
            "pas préremplis",
            (
                round(float(widget(form, "stepX").property("rawValue")), 3),
                round(float(widget(form, "stepY").property("rawValue")), 3),
            ),
            (350.0, 100.0),
        ),
        *ecarts("entrées avant saisie", doc.UndoNames, []),
    ]
    widget(form, "countX").setValue(5)
    widget(form, "countY").setValue(3)
    saisir(widget(form, "stepY"), 100.0)
    rep = doc.getObject("Repeat")
    apres = {repeat.cell_of(c): c.Name for c in copies_de(rep)}
    problemes += [
        *ecarts("5 x 3 : 14 copies", len(apres), 14),
        *ecarts(
            "les cellules conservées gardent leur copie",
            {c: n for c, n in apres.items() if c in avant},
            avant,
        ),
    ]
    valider()
    return problemes + ecarts("entrées", doc.UndoNames, ["Modifier la répétition"])


def verifier_modifier_une_grille() -> list[str]:
    """Le panneau d'une grille existante est prérempli ; changer un nombre ajoute les cellules sans
    refaire les copies conservées."""
    return avec_document("VerifGrilleModifie", _modifier_une_grille)


VERIFICATIONS_REPETITION_GRILLE: tuple[Callable[[], list[str]], ...] = (
    verifier_grille_apercu_et_validation,
    verifier_refus_au_dela_de_cent_copies,
    verifier_mode_commun_et_sens_par_axe,
    verifier_chevauchement_par_axe_et_grille,
    verifier_modifier_une_grille,
)
