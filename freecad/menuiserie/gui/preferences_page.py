# SPDX-License-Identifier: LGPL-2.1-or-later
"""Page « Menuiserie » d'Édition > Préférences : réglages de l'atelier (ADR 0031, 0069).

Branche la page générique :class:`~freecad.menuiserie.kit.config.page.SettingsPage` sur le
catalogue de l'atelier (:data:`~freecad.menuiserie.features.settings.CATALOG`), ses traductions et
les listes de choix : matériaux de la bibliothèque, profils d'arête. Enregistrée par
``Gui.addPreferencePage`` dans ``init_gui.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features import dimensions_edit
from freecad.menuiserie.features.edge_profile import FAMILY_LABELS
from freecad.menuiserie.features.i18n import format_text, report_warning, translate_text
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.features.settings import (
    CATALOG,
    EDGE_PROFILE,
    MATERIAL,
    STORAGE,
    settings,
)
from freecad.menuiserie.gui.dimensions_row import DimensionsRow
from freecad.menuiserie.gui.preferences_exchange import actions
from freecad.menuiserie.kit.config.catalog import Value
from freecad.menuiserie.kit.config.import_model import ImportRow
from freecad.menuiserie.kit.config.page import SettingsPage
from freecad.menuiserie.kit.config.page_exchange import ExchangeRow
from freecad.menuiserie.kit.config.page_model import Choices

__all__ = ["GROUP_NAME", "IMPORT_TEXTS", "PAGE_TEXTS", "TITLE", "MenuiseriePreferencePage"]

GROUP_NAME: Final = "Menuiserie"  # entrée de la liste des pages (nom du paramètre d'icône)
TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Réglages de l'atelier")
LIBRARY_UNAVAILABLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Bibliothèque de matériaux illisible : {error}"
)
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
    QT_TRANSLATE_NOOP("Menuiserie", "{value} (absente)"),
    QT_TRANSLATE_NOOP("Menuiserie", "vide"),
    QT_TRANSLATE_NOOP("Menuiserie", "oui"),
    QT_TRANSLATE_NOOP("Menuiserie", "non"),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} réglage"),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} réglages"),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} modifié"),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} modifiés"),
)

# Textes de l'aperçu et de l'échange de la page générique (``kit.config.import_model``).
IMPORT_TEXTS: Final = (
    QT_TRANSLATE_NOOP("Menuiserie", "Importer les réglages de l'atelier"),
    QT_TRANSLATE_NOOP("Menuiserie", "Réglages de l'atelier"),
    QT_TRANSLATE_NOOP("Menuiserie", "Exporte ou importe les réglages dans un fichier JSON."),
    QT_TRANSLATE_NOOP("Menuiserie", "Exporter…"),
    QT_TRANSLATE_NOOP("Menuiserie", "Importer…"),
    QT_TRANSLATE_NOOP("Menuiserie", "Exporter les réglages de l'atelier"),
    QT_TRANSLATE_NOOP("Menuiserie", "Choisir le fichier des réglages à importer"),
    QT_TRANSLATE_NOOP("Menuiserie", "Fichiers JSON (*.json)"),
    QT_TRANSLATE_NOOP("Menuiserie", "Réglages exportés dans {path}."),
    QT_TRANSLATE_NOOP("Menuiserie", "Les modifications non enregistrées ne sont pas exportées."),
    QT_TRANSLATE_NOOP("Menuiserie", "Aucun réglage à changer."),
    QT_TRANSLATE_NOOP("Menuiserie", "Fichier : {path} · {count} réglage changé"),
    QT_TRANSLATE_NOOP("Menuiserie", "Fichier : {path} · {count} réglages changés"),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} réglage inconnu ignoré : {names}."),
    QT_TRANSLATE_NOOP("Menuiserie", "{count} réglages inconnus ignorés : {names}."),
    QT_TRANSLATE_NOOP(
        "Menuiserie",
        "Les réglages cochés sont repris dans la page. Ils sont enregistrés avec OK ou Appliquer.",
    ),
    QT_TRANSLATE_NOOP("Menuiserie", "Reprendre la sélection"),
    QT_TRANSLATE_NOOP("Menuiserie", "Annuler"),
    QT_TRANSLATE_NOOP("Menuiserie", "Groupe"),
    QT_TRANSLATE_NOOP("Menuiserie", "Réglage"),
    QT_TRANSLATE_NOOP("Menuiserie", "Actuel"),
    QT_TRANSLATE_NOOP("Menuiserie", "Importé"),
    QT_TRANSLATE_NOOP("Menuiserie", "Reprendre ce réglage"),
)


def material_choices() -> list[tuple[Value, str]]:
    """Matériaux de la bibliothèque (identifiant, nom), précédés du choix « premier matériau »
    (identifiant vide) ; seul ce choix reste si la bibliothèque ne peut pas être lue."""
    first: tuple[Value, str] = ("", translate_text(FIRST_MATERIAL))
    try:
        language = display_language()
        library = [(material.id, material.name(language)) for material in get_library()]
    except (OSError, ValueError) as error:  # bibliothèque illisible : la page s'ouvre quand même
        report_warning(format_text(translate_text(LIBRARY_UNAVAILABLE), error=error))
        library = []
    return [first, *library]


def profile_choices() -> list[tuple[Value, str]]:
    """Familles de profil d'arête (valeur enregistrée, libellé traduit)."""
    return [(family.value, translate_text(label)) for family, label in FAMILY_LABELS.items()]


def choices() -> Choices:
    """Listes déroulantes de la page, par clé de réglage."""
    return {MATERIAL: material_choices(), EDGE_PROFILE: profile_choices()}


class MenuiseriePreferencePage(SettingsPage):
    """Page de préférences de l'atelier : ``form``, ``loadSettings`` et ``saveSettings``, comme
    FreeCAD les attend d'une page ajoutée par ``Gui.addPreferencePage``.

    Ajoute à la page générique le groupe « Épaisseurs et formats » (éditeur de
    ``dimensions.json``) et, dans « Stockage », l'export et l'import des réglages. Un import
    reprend les réglages cochés dans les champs : ils ne sont écrits qu'à OK ou Appliquer.
    """

    def __init__(self) -> None:
        page_choices = choices()
        self._dimensions = DimensionsRow(dimensions_edit.ROW_GROUP, STORAGE)
        self._exchange = ExchangeRow(
            actions(page_choices, self.take_import, self.has_pending), STORAGE, translate_text
        )
        extras = [self._dimensions.extra_row(), self._exchange.extra_row()]
        super().__init__(
            CATALOG, settings(), translate=translate_text, choices=page_choices, extras=extras
        )
        self.form.setWindowTitle(translate_text(TITLE))

    def take_import(self, rows: Sequence[ImportRow]) -> None:
        """Reprend les lignes cochées de l'aperçu : réglages dans les champs, dimensions dans
        l'éditeur ; rien n'est écrit avant OK ou Appliquer."""
        values = {row.key: row.value for row in rows if row.key != dimensions_edit.DIMENSIONS_KEY}
        self.set_pending(values)
        for row in rows:
            if row.key == dimensions_edit.DIMENSIONS_KEY:
                self._dimensions.set_pending(row.value)
