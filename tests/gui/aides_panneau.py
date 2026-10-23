# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aides des vérifications du panneau de la pièce de bois (cas limites, lot J1c, testeur).

Ouverture du panneau au double-clic, saisie au clavier, observation des écritures, bibliothèque
de matériaux temporaire. Un défaut constaté est une vérification décorée par
:func:`defaut_connu`, équivalent de ``pytest.mark.xfail(strict=True)`` pour ce script lancé par
FreeCAD : ses écarts sont rapportés comme défauts connus sans faire échouer le script ; s'il n'en
a plus, le script échoue pour que le marqueur soit retiré.
"""

from __future__ import annotations

import functools
import json
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import FreeCAD as App
from PySide import QtGui

from freecad.menuiserie.features import library
from tests.gui.verifications_panneau import (
    ecarts,
    formulaire,
)

Verification = Callable[[], list[str]]
# Défauts connus constatés pendant l'exécution, ajoutés au rapport après la ligne « OK ».
DEFAUTS_CONSTATES: list[str] = []
NOUVELLE = "Nouvelle pièce de bois"
VOLUME_INITIAL = 800 * 200 * 22
ERABLE = {
    "id": "erable",
    "kind": "solid",
    "name": {"fr": "Érable", "en": "Maple"},
    "density": 650,
    "thicknesses": [22],
    "color": "#E8D2A8",
}


def defaut_connu(numero: str, raison: str) -> Callable[[Verification], Verification]:
    """Marque une vérification qui échoue à cause d'un défaut du code de production.

    Comme ``xfail(strict=True)`` : écarts ou exception → défaut connu, rapporté sans échec ;
    aucun écart → échec « XPASS » (défaut corrigé : retirer le marqueur)."""

    def decorer(verification: Verification) -> Verification:
        @functools.wraps(verification)
        def attendue_en_echec() -> list[str]:
            try:
                problemes = verification()
            except Exception as erreur:  # comme xfail : une exception est un échec
                problemes = [f"{type(erreur).__name__} : {erreur}"]
            if not problemes:
                return [f"XPASS strict, {numero} corrigé ? retirer defaut_connu : {raison}"]
            DEFAUTS_CONSTATES.append(f"XFAIL {numero} : {raison} [constaté : {problemes[0]}]")
            return []

        return attendue_en_echec

    return decorer


# --- Aides --------------------------------------------------------------------------------


def taper(champ: Any, texte: str) -> None:
    """Saisie au clavier dans un champ de cote (texte analysé par le champ, unités comprises)."""
    champ.findChild(QtGui.QLineEdit).setText(texte)


def double_cliquer(obj: Any) -> bool:
    vobj = obj.ViewObject
    return bool(vobj.Proxy.doubleClicked(vobj))


def editer(obj: Any) -> None:
    """Ouvre le panneau d'édition sans garder de référence au formulaire."""
    double_cliquer(obj)


def transaction_ouverte() -> object:
    return App.getActiveTransaction()


class Ecritures:
    """Observateur de document : noms des propriétés écrites sur un objet."""

    def __init__(self, obj: Any) -> None:
        self.cible = (obj.Document.Name, obj.Name)
        self.proprietes: list[str] = []

    def slotChangedObject(self, obj: Any, prop: str) -> None:
        if (obj.Document.Name, obj.Name) == self.cible:
            self.proprietes.append(prop)


@contextmanager
def ecritures(obj: Any) -> Iterator[list[str]]:
    """Propriétés de ``obj`` écrites pendant le bloc."""
    observateur = Ecritures(obj)
    App.addDocumentObserver(observateur)
    try:
        yield observateur.proprietes
    finally:
        App.removeDocumentObserver(observateur)


@contextmanager
def bibliotheque(fichier_integre: Path | None, *materiaux: dict[str, object]) -> Iterator[Path]:
    """Bibliothèque de la session remplacée le temps du bloc : fichier utilisateur temporaire
    (``materiaux``) et, si ``fichier_integre`` est donné, bibliothèque intégrée déplacée."""
    parametres = App.ParamGet(library.PARAM_PATH)
    precedent = parametres.GetString(library.USER_LIBRARY_PARAM, "")
    integree = library.builtin_library_path
    utilisateur = Path(tempfile.mkdtemp()) / "materiaux.json"
    contenu = {"format": 1, "materials": list(materiaux)}
    utilisateur.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    parametres.SetString(library.USER_LIBRARY_PARAM, str(utilisateur))
    if fichier_integre is not None:
        library.builtin_library_path = lambda: fichier_integre
    try:
        library.reload_library()
        yield utilisateur
    finally:
        library.builtin_library_path = integree
        if precedent:
            parametres.SetString(library.USER_LIBRARY_PARAM, precedent)
        else:
            parametres.RemString(library.USER_LIBRARY_PARAM)
        library.reload_library()


def libelle_affiche_par_type(obj: Any) -> list[str]:
    """Pour chaque type du filtre : écart entre le libellé affiché et ``obj.Material``."""
    problemes: list[str] = []
    for index in range(formulaire().kindCombo.count()):
        formulaire().kindCombo.setCurrentIndex(index)
        texte = formulaire().materialCombo.currentText()
        problemes += ecarts(f"libellé affiché, type {index}", texte, obj.Material)
    formulaire().kindCombo.setCurrentIndex(0)
    return problemes
