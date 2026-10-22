# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce usinée : pièce de bois brute après ses assemblages (ADR 0006).

Forme = boîte de la brute plus ajouts, moins enlèvements des assemblages, placée au ``Placement`` de
la brute. La brute est masquée sous sa pièce usinée. Contrat de persistance (ADR 0003) : le
chemin de ce module, le nom de la classe ``MachinedPart`` et les noms des propriétés sont écrits
dans les documents ; ils ne changent jamais.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import Solid
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.naming import label_for_mark, mark_from_label
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import (
    READ_ONLY,
    DocumentObject,
    StatelessProxy,
    proxy_is,
    restoring_or_undoing,
)
from freecad.menuiserie.features.i18n import report_warning, translated, translated_errors
from freecad.menuiserie.features.joints.base import is_joint, parts_mismatch, plan_for
from freecad.menuiserie.features.part_labels import make_label_unique
from freecad.menuiserie.features.part_names import (
    default_label,
    is_importing,
    label_of_mark,
    mark_is_bound,
    other_labels,
    unique_label_after_copy,
    warn_mark_bound,
)
from freecad.menuiserie.features.schema import PropertySpec, version_spec
from freecad.menuiserie.features.solids import machined_shape
from freecad.menuiserie.features.wood_part import dimensions_of, is_wood_part

__all__ = [
    "MachinedPart",
    "blank_of",
    "create_machined_part",
    "ensure_machined_part",
    "is_machined_part",
    "machined_part_of",
    "removal_refusal",
    "remove_machined_part",
    "show_blank",
    "sync_machined_label",
]

OBJECT_NAME: Final = "MachinedPart"
MODEL_VERSION: Final = 1
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce usinée")

_MACHINED_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "{label} (usinée)")
_NO_BLANK: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Pièce usinée sans pièce de bois brute : sa pièce a été supprimée."
)
_NOT_A_JOINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas un assemblage de l'atelier Menuiserie."
)
_NOT_A_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est ni une pièce de bois ni une pièce usinée."
)
_PLACEMENT_BOUND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est placée par une expression ({property}) : déplacement refusé ; modifiez "
    "l'expression, l'ensemble qui la pilote, ou retirez la pièce de l'ensemble.",
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
    version_spec(
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la pièce usinée, utilisée pour migrer les anciens "
            "fichiers.",
        ),
        MODEL_VERSION,
    ),
)


def _quoted(obj: DocumentObject) -> dict[str, str]:
    return {"label": quoted_value(obj.Label)}


def _placement_expression(blank: DocumentObject) -> str | None:
    """Chemin de la première expression qui pilote le ``Placement`` de ``blank`` (liaison d'un
    ensemble ou formule de l'utilisateur), ``None`` s'il n'y en a pas."""
    paths = (path.lstrip(".") for path, _ in blank.ExpressionEngine)
    return next((path for path in sorted(paths) if path.split(".")[0] == "Placement"), None)


class MachinedPart(StatelessProxy):
    """Proxy du FeaturePython « pièce usinée ». Chemin de module figé (ADR 0003).

    Sans état : le drapeau ``_in_execute`` (lu avec ``getattr``, ``__init__`` n'étant pas rappelé
    à la réouverture) distingue le ``Placement`` posé par :meth:`execute` d'un déplacement par
    l'utilisateur, et ``_syncing`` le libellé écrit par la brute (J6b) d'un renommage.
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
        self._make_label_unique(obj)  # copie, duplication, fusion (J6, L5 bis)

    def _make_label_unique(self, obj: DocumentObject) -> None:
        """Pièce usinée restaurée avec le libellé d'un autre objet : sa brute est d'abord rendue
        unique, puis le libellé devient « {libellé de la brute} (usinée) » ; sans brute, suffixe
        « (2) ». Sans effet si le libellé est déjà unique."""
        blank: DocumentObject = getattr(obj, "Base", None)
        if is_wood_part(blank):
            make_label_unique(blank)
        label = unique_label_after_copy(obj)
        if is_wood_part(blank) and (label is not None or is_importing(obj)):
            expected = _machined_label(obj, str(blank.Label))
            label = None if expected == str(obj.Label) else expected
        if label is None:
            return
        with self._synchronizing():
            obj.Label = label

    def onChanged(self, obj: DocumentObject, prop: str) -> None:
        """Déplacement de la pièce usinée par l'utilisateur : reporté sur sa brute (Q4), dans la
        transaction de l'appelant ; jamais pendant un recalcul, une restauration ou une
        annulation. Refusé, avec un avertissement, si une expression pilote le ``Placement`` de
        la brute (ensemble J4 : la brute y reviendrait au recalcul suivant). Libellé changé par
        l'utilisateur : le repère de la brute suit (J6b, ADR 0011)."""
        if not self._follows_user_changes(obj):
            return
        if prop == "Label":
            self._adopt_typed_mark(obj)
        elif prop == "Placement":
            self._follow_placement(obj)

    def allowDuplicateLabel(self, obj: DocumentObject) -> bool:  # pylint: disable=unused-argument
        """Vrai : le libellé est rendu unique par l'atelier (:meth:`onBeforeChangeLabel`)."""
        return True

    def onBeforeChangeLabel(self, obj: DocumentObject, label: str) -> str | None:
        """Libellé saisi : le repère de la brute est celui qu'il désigne (suffixe « (usinée) »
        retiré), mémorisé pour :meth:`onChanged` ; le libellé devient « {libellé de la brute}
        (usinée) ». Repère de la brute piloté par une expression : il ne change pas,
        avertissement, le libellé revient à celui de la brute."""
        self._typed_mark = None
        blank: DocumentObject = getattr(obj, "Base", None)
        if not self._follows_user_changes(obj) or not is_wood_part(blank):
            return None
        if mark_is_bound(blank):
            warn_mark_bound(blank)
            return _machined_label(obj, str(blank.Label))
        suffix = translated(_MACHINED_LABEL, {"label": ""})
        mark = mark_from_label(label.removesuffix(suffix), default_label())
        self._typed_mark = mark
        return _machined_label(obj, label_of_mark(blank, mark))

    def synchronizing(self) -> AbstractContextManager[None]:
        """Contexte où le libellé écrit par la brute n'est pas lu comme un renommage."""
        return self._synchronizing()

    def _adopt_typed_mark(self, obj: DocumentObject) -> None:
        """Libellé changé : écrit, dans la brute, le repère mémorisé par
        :meth:`onBeforeChangeLabel`."""
        mark: str | None = getattr(self, "_typed_mark", None)
        self._typed_mark = None
        blank: DocumentObject = getattr(obj, "Base", None)
        if mark is not None and is_wood_part(blank):
            blank.Proxy.adopt_mark(blank, mark)

    def _follow_placement(self, obj: DocumentObject) -> None:
        blank: DocumentObject = getattr(obj, "Base", None)
        if not is_wood_part(blank) or blank.Placement == obj.Placement:
            return
        bound = _placement_expression(blank)
        if bound is not None:  # J4, N6 : refus explicite, aucune écriture perdue en silence
            report_warning(translated(_PLACEMENT_BOUND, {**_quoted(blank), "property": bound}))
            return
        blank.Placement = obj.Placement

    def execute(self, obj: DocumentObject) -> None:
        """Forme = brute plus ajouts, moins enlèvements de ses assemblages, au ``Placement`` de la
        brute. ``ValueError`` traduite si la brute ou un assemblage est invalide."""
        blank = _checked_blank(obj)
        with translated_errors():
            dimensions = dimensions_of(blank)
        additions, cuts = _machining_of(obj, blank)
        shape = machined_shape(dimensions, additions, cuts)
        # Part::Feature impose son Placement à la forme affectée : il est donc posé d'abord,
        # sous le drapeau qui évite de le reporter sur la brute (Q4).
        with self._executing():
            obj.Placement = blank.Placement
            obj.Shape = shape

    def _follows_user_changes(self, obj: DocumentObject) -> bool:
        executing: bool = getattr(self, "_in_execute", False)
        syncing: bool = getattr(self, "_syncing", False)
        return not (executing or syncing) and not restoring_or_undoing(obj)

    @contextmanager
    def _synchronizing(self) -> Iterator[None]:
        previous: bool = getattr(self, "_syncing", False)
        self._syncing = True
        try:
            yield
        finally:
            self._syncing = previous

    @contextmanager
    def _executing(self) -> Iterator[None]:
        self._in_execute = True
        try:
            yield
        finally:
            self._in_execute = False


def _machined_label(machined: DocumentObject, blank_label: str) -> str:
    """« {libellé de la brute} (usinée) », unique dans le document de ``machined``."""
    text = translated(_MACHINED_LABEL, {"label": blank_label})
    return label_for_mark(text, text, other_labels(machined))


def sync_machined_label(blank: DocumentObject) -> None:
    """Libellé de la pièce usinée de ``blank`` d'après celui de la brute (J6b, L3). Seule
    écriture de la brute dans un autre objet (exception documentée de l'ADR 0011) ; sans effet
    si la brute n'a pas de pièce usinée."""
    machined = machined_part_of(blank)
    if machined is None:
        return
    label = _machined_label(machined, str(blank.Label))
    if machined.Label != label:
        with machined.Proxy.synchronizing():
            machined.Label = label


def _checked_blank(obj: DocumentObject) -> DocumentObject:
    blank = getattr(obj, "Base", None)
    if blank is None:
        raise ValueError(translated(_NO_BLANK))
    if not is_wood_part(blank):
        raise ValueError(translated(_NOT_A_PART, {"label": quoted_value(blank.Label)}))
    return blank


def _machining_of(obj: DocumentObject, blank: DocumentObject) -> tuple[list[Solid], list[Solid]]:
    """Ajouts et enlèvements de ``blank`` d'après les plans de chacun de ses assemblages ;
    ``ValueError`` traduite si un assemblage ne relie plus ``blank`` (pièce modifiée par un
    script)."""
    additions: list[Solid] = []
    cuts: list[Solid] = []
    for joint in obj.Joints:
        if not is_joint(joint):
            raise ValueError(translated(_NOT_A_JOINT, {"label": quoted_value(joint.Label)}))
        if blank not in (joint.HostPart, joint.GuestPart):
            raise parts_mismatch(joint)
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
    return proxy_is(obj, MachinedPart)


def blank_of(obj: DocumentObject) -> DocumentObject:
    """Brute d'une pièce : la pièce de bois elle-même, ou la ``Base`` d'une pièce usinée.
    ``TypeError`` traduite pour tout autre objet."""
    if is_wood_part(obj):
        return obj
    if is_machined_part(obj) and is_wood_part(obj.Base):
        return obj.Base
    raise TypeError(translated(_NOT_A_PART, {"label": quoted_value(getattr(obj, "Label", obj))}))


def machined_part_of(blank: DocumentObject) -> DocumentObject | None:
    """Pièce usinée de la brute ``blank`` (d'après ``blank.InList``), ``None`` s'il n'y en a pas."""
    for parent in blank.InList:
        if is_machined_part(parent) and parent.Base == blank:
            return parent
    return None


def create_machined_part(blank: DocumentObject) -> DocumentObject:
    """Crée la pièce usinée de ``blank`` (sans transaction ni recalcul), dans le même conteneur,
    au libellé « <brute> (usinée) » et au même ``Placement`` ; la brute est masquée (après
    avoir été liée, pour que l'annulation la réaffiche)."""
    obj = blank.Document.addObject("Part::FeaturePython", OBJECT_NAME)
    MachinedPart(obj)
    container = blank.getParentGeoFeatureGroup()
    if container is not None:
        container.addObject(obj)
    obj.Base = blank
    with obj.Proxy.synchronizing():
        obj.Label = _machined_label(obj, str(blank.Label))
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
        raise TypeError(translated(_NOT_A_PART, {"label": quoted_value(machined.Label)}))
    refusal = removal_refusal(machined)
    if refusal is not None:
        raise ValueError(refusal)
    blank = machined.Base
    machined.Document.removeObject(machined.Name)
    show_blank(blank)


def show_blank(blank: DocumentObject | None) -> None:
    """Réaffiche la brute d'une pièce usinée supprimée (seule visibilité modifiée, ADR 0007)."""
    if blank is not None:
        blank.Visibility = True


def removal_refusal(machined: DocumentObject) -> str | None:
    """Message traduit si la pièce usinée ``machined`` porte encore des assemblages (sa
    suppression est alors refusée), ``None`` sinon."""
    if not machined.Joints:
        return None
    return translated(_STILL_JOINED, {"label": quoted_value(machined.Label)})
