# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce usinée : pièce de bois brute après ses assemblages (ADR 0006).

Forme = boîte de la brute plus ajouts, moins enlèvements des assemblages, placée au ``Placement`` de
la brute. La brute est masquée sous sa pièce usinée. Contrat de persistance (ADR 0003) : le
chemin de ce module, le nom de la classe ``MachinedPart`` et les noms des propriétés sont écrits
dans les documents ; ils ne changent jamais.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import Solid
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import InvalidDimensionsError
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import HIDDEN, READ_ONLY, DocumentObject
from freecad.menuiserie.features.i18n import templated_message, translated
from freecad.menuiserie.features.joints.base import is_joint, plan_for
from freecad.menuiserie.features.schema import PropertySpec
from freecad.menuiserie.features.solids import machined_shape
from freecad.menuiserie.features.wood_part import dimensions_of, is_wood_part

__all__ = [
    "MachinedPart",
    "blank_of",
    "create_machined_part",
    "ensure_machined_part",
    "is_machined_part",
    "machined_part_of",
    "remove_machined_part",
]

OBJECT_NAME: Final = "MachinedPart"
MODEL_VERSION: Final = 1
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce usinée")

_NO_BLANK: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Pièce usinée sans pièce de bois brute : sa pièce a été supprimée."
)
_NOT_A_JOINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas un assemblage de l'atelier Menuiserie."
)
_NOT_A_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est ni une pièce de bois ni une pièce usinée."
)
_STILL_JOINED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La pièce usinée « {label} » porte encore des assemblages : supprimez-les d'abord.",
)

PROPERTIES: Final = (
    PropertySpec(
        "Base",
        "App::PropertyLink",
        "Pièce",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Pièce de bois brute (cotes, matériau, fil) dont cette pièce est usinée.",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Joints",
        "App::PropertyLinkList",
        "Pièce",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Assemblages qui usinent cette pièce (tenons, mortaises, rainures, perçages).",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Version",
        "App::PropertyInteger",
        "Base",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la pièce usinée, utilisée pour migrer les anciens "
            "fichiers.",
        ),
        default=MODEL_VERSION,
        mode=HIDDEN,
    ),
)


class MachinedPart:
    """Proxy du FeaturePython « pièce usinée ». Chemin de module figé (ADR 0003).

    Sans état : le drapeau ``_in_execute`` (lu avec ``getattr``, ``__init__`` n'étant pas rappelé
    à la réouverture) distingue le ``Placement`` posé par :meth:`execute` d'un déplacement par
    l'utilisateur.
    """

    TYPE: ClassVar[str] = "Menuiserie::MachinedPart"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés de la pièce usinée, à leurs valeurs par défaut."""
        obj.Proxy = self
        schema.add_missing_properties(obj, PROPERTIES)
        schema.apply_editor_modes(obj, PROPERTIES)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types des propriétés contrôlés, migration, modes d'édition (ADR 0003)."""
        schema.restore_schema(obj, PROPERTIES, self.VERSION, NOUN)

    def onChanged(self, obj: DocumentObject, prop: str) -> None:
        """Déplacement de la pièce usinée par l'utilisateur : reporté sur sa brute (Q4), dans la
        transaction de l'appelant ; jamais pendant un recalcul, une restauration ou une
        annulation."""
        if prop != "Placement" or not self._follows_user_changes(obj):
            return
        blank: DocumentObject = getattr(obj, "Base", None)
        if is_wood_part(blank) and blank.Placement != obj.Placement:
            blank.Placement = obj.Placement

    def execute(self, obj: DocumentObject) -> None:
        """Forme = brute plus ajouts, moins enlèvements de ses assemblages, au ``Placement`` de la
        brute. ``ValueError`` traduite si la brute ou un assemblage est invalide."""
        blank = _checked_blank(obj)
        try:
            dimensions = dimensions_of(blank)
        except InvalidDimensionsError as error:
            raise ValueError(templated_message(error)) from error
        additions, cuts = _machining_of(obj, blank)
        shape = machined_shape(dimensions, additions, cuts)
        shape.Placement = blank.Placement
        with self._executing():
            obj.Shape = shape

    def dumps(self) -> None:
        """Proxy sans état : rien à enregistrer."""
        return None

    def loads(self, state: object) -> None:
        """Proxy sans état : rien à relire."""
        del state

    def _follows_user_changes(self, obj: DocumentObject) -> bool:
        executing: bool = getattr(self, "_in_execute", False)
        return not executing and "Restore" not in obj.State and not obj.Document.Transacting

    @contextmanager
    def _executing(self) -> Iterator[None]:
        self._in_execute = True
        try:
            yield
        finally:
            self._in_execute = False


def _checked_blank(obj: DocumentObject) -> DocumentObject:
    blank = getattr(obj, "Base", None)
    if blank is None:
        raise ValueError(translated(_NO_BLANK))
    if not is_wood_part(blank):
        raise ValueError(translated(_NOT_A_PART, {"label": str(blank.Label)}))
    return blank


def _machining_of(obj: DocumentObject, blank: DocumentObject) -> tuple[list[Solid], list[Solid]]:
    """Ajouts et enlèvements de ``blank`` d'après les plans de chacun de ses assemblages."""
    additions: list[Solid] = []
    cuts: list[Solid] = []
    for joint in obj.Joints:
        if not is_joint(joint):
            raise ValueError(translated(_NOT_A_JOINT, {"label": str(joint.Label)}))
        plan = plan_for(joint)
        if joint.HostPart == blank:
            additions.extend(plan.host_additions)
            cuts.extend(plan.host_cuts)
        if joint.GuestPart == blank:
            additions.extend(plan.guest_additions)
            cuts.extend(plan.guest_cuts)
    return additions, cuts


def is_machined_part(obj: object) -> bool:
    """Vrai si ``obj`` est une pièce usinée de l'atelier (faux pour un objet supprimé)."""
    try:
        proxy = getattr(obj, "Proxy", None)
    except ReferenceError:  # objet FreeCAD supprimé du document
        return False
    return isinstance(proxy, MachinedPart)


def blank_of(obj: DocumentObject) -> DocumentObject:
    """Brute d'une pièce : la pièce de bois elle-même, ou la ``Base`` d'une pièce usinée.
    ``TypeError`` traduite pour tout autre objet."""
    if is_wood_part(obj):
        return obj
    if is_machined_part(obj) and is_wood_part(obj.Base):
        return obj.Base
    raise TypeError(translated(_NOT_A_PART, {"label": str(getattr(obj, "Label", obj))}))


def machined_part_of(blank: DocumentObject) -> DocumentObject | None:
    """Pièce usinée de la brute ``blank`` (d'après ``blank.InList``), ``None`` s'il n'y en a pas."""
    for parent in blank.InList:
        if is_machined_part(parent) and parent.Base == blank:
            return parent
    return None


def create_machined_part(blank: DocumentObject) -> DocumentObject:
    """Crée la pièce usinée de ``blank`` (sans transaction ni recalcul), dans le même conteneur,
    au même libellé et au même ``Placement`` ; la brute est masquée (après avoir été liée, pour
    que l'annulation la réaffiche)."""
    obj = blank.Document.addObject("Part::FeaturePython", OBJECT_NAME)
    MachinedPart(obj)
    container = blank.getParentGeoFeatureGroup()
    if container is not None:
        container.addObject(obj)
    obj.Base = blank
    obj.Label = blank.Label
    obj.Placement = blank.Placement
    blank.Visibility = False
    return obj


def ensure_machined_part(blank: DocumentObject) -> DocumentObject:
    """Pièce usinée de ``blank``, créée si elle n'existe pas encore (une seule par brute)."""
    existing = machined_part_of(blank)
    return existing if existing is not None else create_machined_part(blank)


def remove_machined_part(machined: DocumentObject) -> None:
    """Supprime une pièce usinée sans assemblage et réaffiche sa brute ; ``ValueError``
    traduite s'il lui reste des assemblages, ``TypeError`` si ce n'est pas une pièce usinée."""
    if not is_machined_part(machined):
        raise TypeError(translated(_NOT_A_PART, {"label": str(machined.Label)}))
    if machined.Joints:
        raise ValueError(translated(_STILL_JOINED, {"label": str(machined.Label)}))
    blank = machined.Base
    machined.Document.removeObject(machined.Name)
    if blank is not None:
        blank.Visibility = True
