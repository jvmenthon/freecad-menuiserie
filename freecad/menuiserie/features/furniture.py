# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensemble : objet de cotes hors conteneur (ADR 0008), propriétés de ses membres (ADR 0009).

L'ensemble (``App::FeaturePython``, nom interne ``Furniture``) porte ``Width``, ``Depth``,
``Height`` et ``Origin`` ; il n'a ni forme ni lien vers ses membres. Chaque membre (pièce brute
ou sous-ensemble) porte un lien ``Furniture``, son mode, ses six options « fixe » et
``FurnitureBindings``. Les liaisons sont écrites par :mod:`.furniture_bindings`.

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe ``Furniture``,
les noms des propriétés et les valeurs de ``PositionMode`` sont écrits dans les documents ; ils
ne changent jamais.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import ClassVar, Final

import FreeCAD as App

from freecad.menuiserie.core.furniture import Edge, FurnitureBox, InteriorMode
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import (
    HIDDEN,
    READ_ONLY,
    Document,
    DocumentObject,
    StatelessProxy,
    has_expression,
    proxy_is,
    restoring_or_undoing,
)
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.schema import LENGTH, PropertySpec, version_spec

__all__ = [
    "DIMENSIONS",
    "FURNITURE_PROPERTIES",
    "MEMBER_OPTIONS",
    "MEMBER_PROPERTIES",
    "MODES",
    "NOUN",
    "OBJECT_NAME",
    "OPTIONS",
    "Furniture",
    "box_of",
    "create_furniture",
    "follows_user_changes",
    "furniture_of",
    "has_member_properties",
    "is_furniture",
    "is_member",
    "option_name",
    "origin_of",
    "workshop_writes",
    "writing",
]

OBJECT_NAME: Final = "Furniture"
MODEL_VERSION: Final = 1
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ensemble")
DEFAULT_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ensemble")
DIMENSIONS: Final = ("Width", "Depth", "Height")
MODES: Final = tuple(mode.value for mode in InteriorMode)  # ordre figé, ajouts en fin
GROUP: Final = "Ensemble"
# Drapeau (transitoire) d'une écriture de l'atelier lui-même : ``onChanged`` ne réagit pas.
_WRITING: Final = "furniture_writing"


def option_name(edge: Edge) -> str:
    """Propriété de l'option « fixe » d'un bord : ``FixedLeft``… ``FixedTop`` (noms figés)."""
    return f"Fixed{edge.value}"


OPTIONS: Final = tuple(option_name(edge) for edge in Edge)
MEMBER_OPTIONS: Final = ("PositionMode", *OPTIONS)  # réglages du membre, relié s'ils changent

_TOOLTIPS: Final = {
    "Width": QT_TRANSLATE_NOOP(
        "App::Property",
        "Largeur de l'ensemble (axe X de son repère). Les pièces liées suivent par leurs "
        "expressions.",
    ),
    "Depth": QT_TRANSLATE_NOOP("App::Property", "Profondeur de l'ensemble (axe Y)."),
    "Height": QT_TRANSLATE_NOOP("App::Property", "Hauteur de l'ensemble (axe Z)."),
}

FURNITURE_PROPERTIES: Final = (
    *(PropertySpec(name, LENGTH, GROUP, _TOOLTIPS[name]) for name in DIMENSIONS),
    PropertySpec(
        "Origin",
        "App::PropertyVectorDistance",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Coin de départ de l'ensemble (avant, gauche, bas) dans le repère de son conteneur.",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Template",
        "App::PropertyString",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Gabarit qui a créé l'ensemble (information seulement)."
        ),
        default="",
        mode=READ_ONLY,
    ),
    version_spec(
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de l'ensemble, utilisée pour migrer les anciens "
            "fichiers.",
        ),
        MODEL_VERSION,
    ),
)

_OPTION_TOOLTIPS: Final = (
    QT_TRANSLATE_NOOP(
        "App::Property",
        "Distance fixe au bord gauche de l'ensemble : la pièce garde cette distance quand la "
        "largeur change.",
    ),
    QT_TRANSLATE_NOOP(
        "App::Property",
        "Distance fixe au bord droit : la pièce suit ce bord quand la largeur change.",
    ),
    QT_TRANSLATE_NOOP("App::Property", "Distance fixe au bord avant."),
    QT_TRANSLATE_NOOP(
        "App::Property",
        "Distance fixe au bord arrière : la pièce suit ce bord quand la profondeur change.",
    ),
    QT_TRANSLATE_NOOP("App::Property", "Distance fixe au bas de l'ensemble."),
    QT_TRANSLATE_NOOP(
        "App::Property",
        "Distance fixe au haut de l'ensemble : la pièce suit ce bord quand la hauteur change.",
    ),
)

MEMBER_PROPERTIES: Final = (
    PropertySpec(
        "Furniture",
        "App::PropertyLink",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Ensemble dont la pièce suit les cotes."),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "PositionMode",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Faces dont la distance au bord n'est pas fixe : Stay, elles ne bougent pas ; "
            "Proportional, elles gardent leur proportion de la cote. Sans effet sur une "
            "position pilotée par une formule.",
        ),
        default=InteriorMode.STAY.value,
    ),
    *(
        PropertySpec(name, "App::PropertyBool", GROUP, tooltip)
        for name, tooltip in zip(OPTIONS, _OPTION_TOOLTIPS, strict=True)
    ),
    PropertySpec(
        "FurnitureBindings",
        "App::PropertyMap",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Expressions posées par l'atelier (propriété → texte), pour les distinguer des "
            "formules de l'utilisateur.",
        ),
        mode=HIDDEN,
    ),
)


@contextmanager
def writing(obj: DocumentObject) -> Iterator[None]:
    """Écriture de l'atelier dans ``obj`` : son ``onChanged`` ne réagit pas (options, cotes)."""
    proxy = obj.Proxy
    previous: bool = getattr(proxy, _WRITING, False)
    setattr(proxy, _WRITING, True)
    try:
        yield
    finally:
        setattr(proxy, _WRITING, previous)


def workshop_writes(obj: DocumentObject) -> bool:
    """Vrai pendant une écriture de l'atelier dans ``obj`` (:func:`writing`)."""
    return bool(getattr(getattr(obj, "Proxy", None), _WRITING, False))


def follows_user_changes(obj: DocumentObject) -> bool:
    """Faux pendant une restauration, une annulation, un recalcul ou une écriture de
    l'atelier : seules les saisies de l'utilisateur (éditeur de propriétés, script) comptent."""
    recomputing = bool(getattr(obj.Document, "Recomputing", False))
    return not (recomputing or restoring_or_undoing(obj) or workshop_writes(obj))


class Furniture(StatelessProxy):
    """Proxy de l'ensemble. Chemin de module figé (ADR 0008) ; sans état enregistré.

    ``previous_box`` (transitoire) : cotes lues par ``onBeforeChange``, comparées dans
    ``onChanged`` pour avertir d'un redimensionnement qui casse une pièce (Q4).
    """

    TYPE: ClassVar[str] = "Menuiserie::Furniture"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés de l'ensemble, à leurs valeurs par défaut."""
        obj.Proxy = self
        with writing(obj):
            schema.add_missing_properties(obj, FURNITURE_PROPERTIES)
            schema.apply_editor_modes(obj, FURNITURE_PROPERTIES)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types contrôlés (ADR 0003), puis ses propriétés de membre s'il est un
        sous-ensemble (:func:`.furniture_restore.restore_member`), sans réécrire les liaisons."""
        from freecad.menuiserie.features.furniture_restore import restore_member

        with writing(obj):
            schema.restore_schema(obj, FURNITURE_PROPERTIES, self.VERSION, NOUN)
        restore_member(obj)

    def onBeforeChange(self, obj: DocumentObject, prop: str) -> None:
        """Cotes avant une saisie de l'utilisateur, pour :meth:`onChanged`."""
        if prop in DIMENSIONS:
            self.previous_box = box_of(obj) if follows_user_changes(obj) else None

    def onChanged(self, obj: DocumentObject, prop: str) -> None:
        """Saisie de l'utilisateur : cote → avertissements (formules, pièce cassée : la cote
        est appliquée, Q4) ; option d'un sous-ensemble → ses liaisons. N'écrit que dans
        lui-même ; rien pendant une restauration, une annulation ou un recalcul."""
        if not follows_user_changes(obj):
            return
        from freecad.menuiserie.features import furniture_bindings

        if prop in DIMENSIONS and not has_expression(obj, prop):
            previous: FurnitureBox | None = getattr(self, "previous_box", None)
            self.previous_box = None
            current = box_of(obj)
            if previous is not None and current is not None and previous != current:
                furniture_bindings.report_resize(obj, previous, current)
        elif prop in MEMBER_OPTIONS:
            furniture_bindings.member_option_changed(obj, prop)

    def unsetupObject(self, obj: DocumentObject) -> None:
        """Suppression de l'ensemble (``removeObject``, interface comprise) : les liaisons de
        l'atelier sont retirées de ses membres, dans la même transaction, pour qu'aucune
        expression ne vise un objet absent ; les membres gardent leur géométrie et deviennent
        des orphelins (propriétés de membre sans ensemble), que ``make_furniture``,
        ``add_to_furniture`` et ``remove_from_furniture`` acceptent. Seule exception à « un
        objet n'écrit que dans lui-même » (ADR 0008 : retrait au moment de la suppression)."""
        from freecad.menuiserie.features.furniture_bindings import release_members

        release_members(obj)

    def execute(self, obj: DocumentObject) -> None:
        """Aucune forme : vérifie seulement les cotes (``ValueError`` traduite sinon)."""
        with translated_errors():
            FurnitureBox(obj.Width.Value, obj.Depth.Value, obj.Height.Value)


def is_furniture(obj: object) -> bool:
    """Vrai si ``obj`` est un ensemble de l'atelier (faux pour un objet supprimé)."""
    return proxy_is(obj, Furniture)


def is_member(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` (brute ou ensemble) est membre d'un ensemble."""
    return is_furniture(furniture_of(obj))


def has_member_properties(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` porte des propriétés de membre, même orphelin (ensemble supprimé)."""
    return any(spec.name in obj.PropertiesList for spec in MEMBER_PROPERTIES)


def furniture_of(obj: DocumentObject) -> DocumentObject | None:
    """Ensemble dont ``obj`` est membre (lien ``Furniture``), ``None`` sinon."""
    if "Furniture" not in obj.PropertiesList or "FurnitureBindings" not in obj.PropertiesList:
        return None
    link = obj.Furniture
    return link if is_furniture(link) else None


def box_of(obj: DocumentObject) -> FurnitureBox | None:
    """Cotes de l'ensemble, ``None`` si l'une est invalide."""
    try:
        return FurnitureBox(obj.Width.Value, obj.Depth.Value, obj.Height.Value)
    except ValueError:  # FurnitureError
        return None


def origin_of(obj: DocumentObject) -> Vec3:
    """``Origin`` de l'ensemble, dans le repère de son conteneur."""
    origin = obj.Origin
    return Vec3(origin.x, origin.y, origin.z)


def create_furniture(
    doc: Document, box: FurnitureBox, origin: Vec3, label: str, container: DocumentObject | None
) -> DocumentObject:
    """Crée un ensemble vide (sans transaction ni recalcul) dans ``container`` ; renvoie
    l'objet, dont le libellé peut avoir été rendu unique par FreeCAD."""
    obj = doc.addObject("App::FeaturePython", OBJECT_NAME)
    Furniture(obj)
    if container is not None:
        container.addObject(obj)
    with writing(obj):
        obj.Label = label or translated(DEFAULT_LABEL)
        obj.Width, obj.Depth, obj.Height = box.width, box.depth, box.height
        obj.Origin = App.Vector(origin.x, origin.y, origin.z)
    return obj
