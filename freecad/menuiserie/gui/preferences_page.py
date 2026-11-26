# SPDX-License-Identifier: LGPL-2.1-or-later
"""Page « Menuiserie » d'Édition > Préférences : réglages de l'atelier (ADR 0031, 0069).

Branche la page générique :class:`~freecad.menuiserie.kit.config.page.SettingsPage` sur le
catalogue de l'atelier (:data:`~freecad.menuiserie.features.settings.CATALOG`), ses traductions et
les listes de choix : matériaux de la bibliothèque, profils d'arête. Enregistrée par
``Gui.addPreferencePage`` dans ``init_gui.py``.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.edge_profile import FAMILY_LABELS
from freecad.menuiserie.features.i18n import translate_text
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.features.settings import CATALOG, EDGE_PROFILE, MATERIAL, settings
from freecad.menuiserie.kit.config.catalog import Value
from freecad.menuiserie.kit.config.page import SettingsPage
from freecad.menuiserie.kit.config.page_model import Choices

__all__ = ["GROUP_NAME", "TITLE", "MenuiseriePreferencePage"]

GROUP_NAME: Final = "Menuiserie"  # entrée de la liste des pages (nom du paramètre d'icône)
TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Réglages de l'atelier")
FIRST_MATERIAL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Premier matériau de la bibliothèque")

# Textes de la page générique (``kit.config.page_model.PAGE_TEXTS``), déclarés ici pour la
# traduction : le paquet ``kit`` ne connaît pas le contexte de l'atelier. Un test les compare.
PAGE_TEXTS: Final = (
    QT_TRANSLATE_NOOP("Menuiserie", "Rechercher un réglage"),
    QT_TRANSLATE_NOOP("Menuiserie", "Afficher les réglages avancés"),
    QT_TRANSLATE_NOOP("Menuiserie", "Dernier utilisé"),
    QT_TRANSLATE_NOOP("Menuiserie", "Retient la valeur utilisée lors de la dernière création."),
    QT_TRANSLATE_NOOP("Menuiserie", "Rétablir"),
    QT_TRANSLATE_NOOP("Menuiserie", "Rétablir la valeur par défaut"),
    QT_TRANSLATE_NOOP("Menuiserie", "Rétablir tout"),
    QT_TRANSLATE_NOOP(
        "Menuiserie", "Rétablit tous les réglages à leur valeur par défaut (à valider par OK)."
    ),
    QT_TRANSLATE_NOOP("Menuiserie", "Choisir un dossier"),
    QT_TRANSLATE_NOOP("Menuiserie", "Aucun réglage ne correspond à la recherche."),
    QT_TRANSLATE_NOOP("Menuiserie", "Par défaut : {value}"),
    QT_TRANSLATE_NOOP("Menuiserie", "vide"),
    QT_TRANSLATE_NOOP("Menuiserie", "oui"),
    QT_TRANSLATE_NOOP("Menuiserie", "non"),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} réglage"),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} réglages"),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} modifié"),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} modifiés"),
)


def material_choices() -> list[tuple[Value, str]]:
    """Matériaux de la bibliothèque (identifiant, nom), précédés du choix « premier matériau »
    (identifiant vide)."""
    language = display_language()
    first: tuple[Value, str] = ("", translate_text(FIRST_MATERIAL))
    return [first, *((material.id, material.name(language)) for material in get_library())]


def profile_choices() -> list[tuple[Value, str]]:
    """Familles de profil d'arête (valeur enregistrée, libellé traduit)."""
    return [(family.value, translate_text(label)) for family, label in FAMILY_LABELS.items()]


def choices() -> Choices:
    """Listes déroulantes de la page, par clé de réglage."""
    return {MATERIAL: material_choices(), EDGE_PROFILE: profile_choices()}


class MenuiseriePreferencePage(SettingsPage):
    """Page de préférences de l'atelier : ``form``, ``loadSettings`` et ``saveSettings``, comme
    FreeCAD les attend d'une page ajoutée par ``Gui.addPreferencePage``."""

    def __init__(self) -> None:
        super().__init__(CATALOG, settings(), translate=translate_text, choices=choices())
        self.form.setWindowTitle(translate_text(TITLE))
