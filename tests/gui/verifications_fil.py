# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ligne « Sens du fil » et filtre « Type » du panneau de la pièce de bois (lot J1c).

Critères C11 et C12 de ``docs/specs/J1-piece-de-bois.md`` (exigences de jv : fil masqué pour un
matériau sans fil, filtre qui applique le premier matériau du type). Module importé par
``verifier_atelier.py``. Aucune référence à un formulaire n'est gardée au-delà de son panneau.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.gui.aides_panneau import ERABLE, bibliotheque, editer
from tests.gui.verifications_panneau import (
    CREATE,
    EDIT,
    annuler,
    avec_document,
    choisir,
    creer_par_la_commande,
    donnees,
    ecarts,
    formulaire,
    valeurs,
    valider,
)

# Index du filtre « Type » : Tous, Massif, Contreplaqué, MDF, Mélaminé.
TOUS, MASSIF, CONTREPLAQUE, MDF, MELAMINE = range(5)


def piece_reglee(doc: Any, material_id: str, fil: str) -> Any:
    """Pièce créée par la commande, matériau et fil choisis dans le panneau, puis « OK »."""
    obj = creer_par_la_commande(doc)
    choisir(formulaire().materialCombo, material_id)
    choisir(formulaire().grainCombo, fil)
    valider()
    return obj


def ligne_du_fil_masquee() -> tuple[bool, bool]:
    form = formulaire()
    return form.grainLabel.isHidden(), form.grainCombo.isHidden()


def surcotes(obj: Any) -> tuple[float, float, float]:
    return (
        obj.LengthAllowance.Value,
        obj.WidthAllowance.Value,
        obj.ThicknessAllowance.Value,
    )


def etat(obj: Any) -> tuple[object, ...]:
    """Matériau, fil, sens mémorisé, surcotes et ligne du fil masquée."""
    masquee = ligne_du_fil_masquee()[1]
    return obj.MaterialId, obj.GrainDirection, obj.PreferredGrainDirection, surcotes(obj), masquee


def verifier_ligne_du_fil() -> list[str]:
    """C11 : choisir « MDF » masque la ligne du fil, « Chêne » la réaffiche avec « Largeur » ;
    ouvert sur une pièce en MDF, le panneau la masque dès l'ouverture."""

    def verification(doc: Any) -> list[str]:
        chene = piece_reglee(doc, "chene", "Width")
        editer(chene)
        problemes = ecarts("ouverture en chêne", ligne_du_fil_masquee(), (False, False))
        choisir(formulaire().materialCombo, "mdf")
        problemes += ecarts("MDF choisi", ligne_du_fil_masquee(), (True, True))
        choisir(formulaire().materialCombo, "chene")
        problemes += ecarts("chêne rechoisi", ligne_du_fil_masquee(), (False, False))
        problemes += ecarts("fil affiché", formulaire().grainCombo.currentText(), "Largeur")
        annuler()
        mdf = piece_reglee(doc, "mdf", "None")
        editer(mdf)
        problemes += ecarts("ouverture en MDF", ligne_du_fil_masquee(), (True, True))
        annuler()
        return problemes

    return avec_document("VerifLigneDuFil", verification)


PARCOURS: tuple[tuple[int, tuple[object, ...]], ...] = (
    (MDF, ("mdf", "None", "Width", (0.0, 0.0, 0.0), True)),
    (CONTREPLAQUE, ("cp-bouleau", "Width", "Width", (0.0, 0.0, 0.0), False)),
    (MASSIF, ("chene", "Width", "Width", (20.0, 5.0, 0.0), False)),
    (TOUS, ("chene", "Width", "Width", (20.0, 5.0, 0.0), False)),
)


def parcourir_les_types(obj: Any) -> list[str]:
    """Chaque type du parcours de C12, avec l'état attendu de la pièce."""
    problemes: list[str] = []
    for index, attendu in PARCOURS:
        formulaire().kindCombo.setCurrentIndex(index)
        problemes += ecarts(f"type {index}", etat(obj), attendu)
    return problemes


def verifier_filtre_applique_le_premier_du_type() -> list[str]:
    """C12 : un type qui exclut le matériau applique le premier de ce type (fil mémorisé,
    surcotes A7) ; « Annuler » rétablit tout ; « OK » donne une seule entrée d'annulation."""

    def verification(doc: Any) -> list[str]:
        obj = piece_reglee(doc, "hetre", "Width")
        avant = valeurs(obj)
        editer(obj)
        problemes = parcourir_les_types(obj)
        annuler()
        problemes += ecarts("valeurs rétablies", valeurs(obj), avant)
        editer(obj)
        parcourir_les_types(obj)
        valider()
        return problemes + ecarts("entrées d'annulation", doc.UndoNames, [EDIT, CREATE])

    return avec_document("VerifFiltreType", verification)


def verifier_type_sans_materiau() -> list[str]:
    """C12 : un type sans aucun matériau laisse la liste vide et la pièce inchangée."""

    def verification(doc: Any) -> list[str]:
        with bibliotheque(Path(tempfile.mkdtemp()) / "absente.json", ERABLE):
            obj = creer_par_la_commande(doc)
            avant = valeurs(obj)
            formulaire().kindCombo.setCurrentIndex(MELAMINE)
            problemes = [
                *ecarts("liste du type vide", donnees(formulaire().materialCombo), []),
                *ecarts("pièce inchangée", valeurs(obj), avant),
            ]
            valider()
        return problemes + ecarts("matériau validé", obj.MaterialId, "erable")

    return avec_document("VerifTypeVide", verification)


VERIFICATIONS_FIL: tuple[Callable[[], list[str]], ...] = (
    verifier_ligne_du_fil,
    verifier_filtre_applique_le_premier_du_type,
    verifier_type_sans_materiau,
)
