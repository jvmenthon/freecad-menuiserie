# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Convertir en pièce en bois » : une pièce en bois par source sélectionnée (D1, D6).

La sélection est lue avant d'ouvrir la transaction (comme « Pièce de bois », J6d) : les objets
entiers sont les sources, les faces, arêtes et sommets d'autres objets sont les éléments contre
lesquels poser la pièce. Toutes les conversions tiennent dans UNE transaction ; les sources
refusées sont listées dans la boîte de refus de l'atelier (:func:`.report_refusal`), les autres
sont converties. Quand une seule pièce est créée, son panneau s'ouvre dans cette transaction
(« OK » la valide, « Annuler » la défait) ; sinon la transaction est validée aussitôt, chaque
pièce se modifie ensuite par double-clic.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.api import make_shaped_parts
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.picked import PickedElement
from freecad.menuiserie.features.placement import SnapSession, snap_part
from freecad.menuiserie.features.shaped_create import converted_part_of
from freecad.menuiserie.features.shaped_sources import is_workshop_object
from freecad.menuiserie.features.snap_targets import TargetReading, new_session, read_targets
from freecad.menuiserie.features.wood_part_record import dimensions_of
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.selection import picked_elements, view_direction
from freecad.menuiserie.gui.task_panels.base import aborted_on_error, close_transaction
from freecad.menuiserie.gui.task_panels.shaped_part import show_panel

COMMAND_NAME: Final = "Menuiserie_ShapedPart"
ICON: Final = "Menuiserie_ShapedPart.svg"
TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Convertir en pièce en bois")
EMPTY_LIBRARY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Aucun matériau dans la bibliothèque : impossible de créer une pièce en bois. Vérifiez le "
    "fichier de matériaux (vue rapport).",
)
REFUSAL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Conversion en pièce en bois refusée pour {count} sélection(s) :\n{reasons}"
)


def is_candidate(obj: DocumentObject | None) -> bool:
    """Vrai si ``obj`` peut a priori devenir une pièce en bois : forme Part (dont corps et
    fonctions PartDesign) ou esquisse, qui n'est ni un objet de l'atelier ni déjà convertie.
    Contrôle léger (``IsActive``) : le détail (forme vide, esquisse ouverte…) est refusé à la
    conversion."""
    if obj is None or is_workshop_object(obj) or not obj.isDerivedFrom("Part::Feature"):
        return False
    return converted_part_of(obj) is None


def split_selection(
    elements: list[PickedElement],
) -> tuple[list[DocumentObject], list[PickedElement]]:
    """Sources et éléments d'accrochage de la sélection : les objets entiers sont les sources ;
    les faces, arêtes et sommets d'un autre objet sont les éléments contre lesquels poser la pièce
    (D6). Sans objet entier, l'objet qui porte des éléments choisis est la source (aucun
    accrochage)."""
    whole = _unique(e.owner() for e in elements if not e.is_subelement())
    if whole:
        keys = {_key(obj) for obj in whole}
        targets = [e for e in elements if e.is_subelement() and _key(e.owner()) not in keys]
        return whole, targets
    return _unique(e.owner() for e in elements if e.is_subelement()), []


def _key(obj: DocumentObject) -> tuple[str, str]:
    return obj.Document.Name, obj.Name


def _unique(objects: Iterable[DocumentObject]) -> list[DocumentObject]:
    """Objets sans doublon, dans l'ordre de la sélection."""
    seen: dict[tuple[str, str], DocumentObject] = {}
    for obj in objects:
        seen.setdefault(_key(obj), obj)
    return list(seen.values())


def convert_sources(
    sources: list[DocumentObject],
) -> tuple[list[DocumentObject], list[str]]:
    """Convertit chaque source (``api.make_shaped_parts``, dans la transaction ouverte) : les
    pièces créées et les messages de refus traduits des sources refusées (aucun objet créé pour
    elles)."""
    parts: list[DocumentObject] = []
    refusals: list[str] = []
    for source in sources:
        try:
            parts += make_shaped_parts(source)
        except (TypeError, ValueError) as error:
            refusals.append(str(error))
    return parts, refusals


def snap_converted(part: DocumentObject, reading: TargetReading) -> SnapSession | None:
    """Pose la pièce convertie contre les éléments sélectionnés en plus de la source (J6d, D6) :
    même accrochage que « Pièce de bois », cotes jamais étirées (elles viennent du dessin),
    placement exprimé dans le conteneur de la pièce. ``None`` sans élément retenu."""
    if not reading.targets:
        return None
    session = new_session(reading, dimensions_of(part))
    session.stretch = False
    session.furniture = None  # l'entrée dans un ensemble relève du panneau de l'ensemble
    session.container = part.getParentGeoFeatureGroup()
    snap_part(part, session)
    return session


def refusal_message(refusals: list[str]) -> str:
    """Message de la boîte de refus : une ligne par source refusée."""
    reasons = "\n".join(f"- {reason}" for reason in refusals)
    return translated(REFUSAL, {"count": str(len(refusals)), "reasons": reasons})


class ConvertToShapedPartCommand:
    """Convertit en pièce en bois les corps, formes et esquisses sélectionnés, sans les modifier
    (ils sont masqués sous la pièce). Les éléments choisis en plus sont ceux contre lesquels la
    pièce est posée (J6d)."""

    def GetResources(self) -> dict[str, str]:
        """Icône, libellé et infobulle (traduits par FreeCAD, contexte = nom de la commande)."""
        return {
            "Pixmap": icon_path(ICON),
            "MenuText": QT_TRANSLATE_NOOP("Menuiserie_ShapedPart", "Convertir en pièce en bois"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Menuiserie_ShapedPart",
                "Fait d'un corps PartDesign, d'une forme Part ou d'une esquisse fermée une pièce "
                "en bois : matériau, sens du fil, repère et liste de débit. La forme d'origine "
                "n'est pas modifiée ; la pièce suit ses changements.",
            ),
        }

    def IsActive(self) -> bool:
        """Active s'il y a un document, au moins un matériau, aucun panneau de tâche et une
        source acceptable dans la sélection."""
        if App.ActiveDocument is None or Gui.Control.activeDialog() or not len(get_library()):
            return False
        sources, _targets = split_selection(picked_elements())
        return any(is_candidate(source) for source in sources)

    def Activated(self) -> None:
        """Sélection lue avant tout, puis une pièce par source dans la transaction « Convertir en
        pièce en bois » (un seul panneau pour une seule pièce créée). Une exception ne laisse ni
        pièce ni transaction."""
        if not len(get_library()):
            report_warning(translated(EMPTY_LIBRARY))
            return
        sources, extras = split_selection(picked_elements())
        reading = read_targets(extras, view_direction())
        doc: Document = App.ActiveDocument
        doc.openTransaction(translated(TRANSACTION))
        transaction = App.getActiveTransaction()
        with aborted_on_error(transaction):
            parts, refusals = convert_sources(sources)
            session = snap_converted(parts[0], reading) if len(parts) == 1 else None
        if refusals:
            report_refusal(refusal_message(refusals))
        if len(parts) == 1:
            show_panel(parts[0], creating=True, session=session)
        else:
            close_transaction(transaction, abort=not parts)


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, ConvertToShapedPartCommand())
