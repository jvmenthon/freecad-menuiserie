# SPDX-License-Identifier: LGPL-2.1-or-later
"""Base des assemblages du document (Template Method) et lecture de leurs pièces brutes.

:class:`JointFeature` fixe le squelette commun : propriétés ``HostPart``, ``GuestPart`` et
``Version``, ``execute`` (plan d'usinage de la stratégie de ``core``), réouverture et
sérialisation. Chaque type fournit ``KIND``, ``TYPE``, ``PROPERTIES`` et :meth:`params`.
Les paramètres de ``core`` (``tenon_thickness``) s'écrivent dans des propriétés aux noms en
CamelCase (``TenonThickness``) : :func:`property_name`. Contrat de persistance (ADR 0003) :
chemins des modules, noms des classes et des propriétés figés.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields
from typing import Any, ClassVar, Final, TypeVar

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointError, JointKind, JointPlan, strategy_for
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import DocumentObject, proxy_is
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.schema import PropertySpec, version_spec
from freecad.menuiserie.features.solids import inserts_shape, rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of, is_wood_part

__all__ = [
    "COMMON_PROPERTIES",
    "JointFeature",
    "is_joint",
    "params_from",
    "placed_blank",
    "plan_for",
    "property_name",
    "resolved_for",
    "write_params",
]

MODEL_VERSION: Final = 1
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Assemblage")
P = TypeVar("P")

_MISSING_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Assemblage incomplet : une des deux pièces a été supprimée."
)
_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas une pièce de bois brute."
)

COMMON_PROPERTIES: Final = (
    PropertySpec(
        "HostPart",
        "App::PropertyLink",
        "Assemblage",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Pièce qui reçoit l'assemblage : mortaise, rainure, feuillure, ou premier côté percé.",
        ),
    ),
    PropertySpec(
        "GuestPart",
        "App::PropertyLink",
        "Assemblage",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Pièce qui porte le tenon ou la languette, se loge dans la feuillure, ou second "
            "côté percé.",
        ),
    ),
    version_spec(
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de l'assemblage, utilisée pour migrer les anciens "
            "fichiers.",
        ),
        MODEL_VERSION,
    ),
)


class JointFeature:
    """Proxy commun des assemblages (Template Method). Sans état : tout est dans les
    propriétés de l'objet."""

    KIND: ClassVar[JointKind]
    TYPE: ClassVar[str]
    OBJECT_NAME: ClassVar[str]  # nom interne des objets créés (ADR 0007 : ni « Joint » nu)
    LABEL: ClassVar[str]  # libellé par défaut, gabarit traduisible
    VERSION: ClassVar[int] = MODEL_VERSION
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = ()

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés communes puis celles du type, à leurs valeurs par défaut."""
        obj.Proxy = self
        schema.add_missing_properties(obj, self.specs())
        schema.apply_editor_modes(obj, self.specs())

    @classmethod
    def specs(cls) -> tuple[PropertySpec, ...]:
        """Propriétés communes puis propres au type."""
        return COMMON_PROPERTIES + cls.PROPERTIES

    def params(self, obj: DocumentObject) -> Any:
        """Paramètres de ``core`` lus dans les propriétés : étape fournie par chaque type."""
        raise NotImplementedError

    def execute(self, obj: DocumentObject) -> None:
        """Forme = pièces rapportées du plan (vide sinon), au ``Placement`` de l'hôte ;
        ``ValueError`` traduite si l'assemblage est impossible."""
        plan = plan_for(obj)
        obj.Shape = inserts_shape(plan.inserts)
        obj.Placement = obj.HostPart.Placement

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types des propriétés contrôlés, migration, modes d'édition (ADR 0003)."""
        schema.restore_schema(obj, self.specs(), self.VERSION, NOUN)

    def dumps(self) -> None:
        """Proxy sans état : rien à enregistrer."""
        return None

    def loads(self, state: object) -> None:
        """Proxy sans état : rien à relire."""
        del state


def is_joint(obj: object) -> bool:
    """Vrai si ``obj`` est un assemblage de l'atelier (faux pour un objet supprimé)."""
    return proxy_is(obj, JointFeature)


def property_name(field_name: str) -> str:
    """Nom de la propriété d'un paramètre de ``core`` : ``tenon_thickness`` → ``TenonThickness``."""
    return "".join(word.capitalize() for word in field_name.split("_"))


def write_params(obj: DocumentObject, params: object) -> None:
    """Écrit chaque paramètre de ``params`` (objet valeur de ``core``) dans sa propriété."""
    for item in fields(params):  # type: ignore[arg-type]
        setattr(obj, property_name(item.name), getattr(params, item.name))


def params_from(obj: DocumentObject, params_type: Callable[..., P]) -> P:
    """Objet valeur ``params_type`` lu dans les propriétés de ``obj`` (``Quantity`` en mm) ;
    une valeur refusée lève ``JointError`` qui cite le nom de la propriété."""
    values = {}
    for item in fields(params_type):  # type: ignore[arg-type]
        value = getattr(obj, property_name(item.name))
        values[item.name] = getattr(value, "Value", value)
    try:
        return params_type(**values)
    except JointError as error:
        renamed = dict(error.params)
        renamed["field"] = property_name(renamed.get("field", ""))
        raise JointError(error.template, renamed) from error


def placed_blank(obj: DocumentObject | None) -> PlacedBlock:
    """Pièce brute vue par ``core`` (cotes et placement) ; ``ValueError`` traduite si elle
    manque ou n'est pas une pièce de bois, ``InvalidDimensionsError`` si une cote est invalide."""
    if obj is None:
        raise ValueError(translated(_MISSING_PART))
    if not is_wood_part(obj):
        raise ValueError(translated(_NOT_A_WOOD_PART, {"label": quoted_value(obj.Label)}))
    return PlacedBlock(dimensions_of(obj), rigid_transform(obj.Placement))


def _inputs(joint: DocumentObject) -> tuple[Any, PlacedBlock, PlacedBlock, Any]:
    """Stratégie, brutes (hôte, invitée) et paramètres de l'assemblage ``joint``."""
    proxy: JointFeature = joint.Proxy
    host = placed_blank(joint.HostPart)
    guest = placed_blank(joint.GuestPart)
    return strategy_for(proxy.KIND), host, guest, proxy.params(joint)


def plan_for(joint: DocumentObject) -> JointPlan:
    """Plan d'usinage de l'assemblage ``joint`` (``ValueError`` traduite s'il est impossible)."""
    with translated_errors():
        strategy, host, guest, params = _inputs(joint)
        plan: JointPlan = strategy.plan(host, guest, params)
    return plan


def resolved_for(joint: DocumentObject) -> object:
    """Valeurs effectives (automatiques résolues) de l'assemblage, pour le panneau (J3e)."""
    with translated_errors():
        strategy, host, guest, params = _inputs(joint)
        values: object = strategy.resolve(host, guest, params)
    return values
