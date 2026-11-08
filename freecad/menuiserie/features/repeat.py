# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition : objet de cotes sans forme (ADR 0043), propriétés de ses copies.

La répétition (``App::FeaturePython``, nom interne ``Repeat``) décrit comment une ou plusieurs
pièces sources sont répétées : ``Source``, ``Mode``, ``Spacing``, ``Axis``, ``Count`` (copies en
plus de chaque source), ``Step``, ``Span``, ``Reverse``, ``CopyJoints``, ``FollowResize``. Elle n'a
pas de forme. Chaque copie est une vraie pièce de bois qui porte ``Repeat`` (lien vers la
répétition), ``RepeatSource`` (la source dont elle est la copie) et ``RepeatIndex`` (rang, à
partir de 1), en lecture seule. Les expressions qui lient la copie à sa source sont écrites par
:mod:`.repeat_links` et :mod:`.repeat_copies`, jamais ici ni pendant un recalcul.

Modifiable dans l'éditeur de propriétés : ``Step`` (les copies suivent) et ``Reverse`` (le sens
est lu par les expressions des copies). Les autres propriétés sont en lecture seule : leur
changement réécrit des expressions, ce que seule l'API (:mod:`freecad.menuiserie.api`) fait, dans
une transaction. ``Count`` ne change donc que par l'API (``edit_repeat``).

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe ``Repeat``, les
noms des propriétés (de la répétition et des copies) et les valeurs de ``Mode``, ``Spacing`` et
``Axis`` (celles de ``core.repeat``) sont écrits dans les documents ; ils ne changent jamais.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping
from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import (
    RepeatAxis,
    RepeatMode,
    RepeatParams,
    Resolved,
    SpacingMode,
)
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import (
    READ_ONLY,
    Document,
    DocumentObject,
    StatelessProxy,
    expressions_of,
    proxy_is,
)
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.schema import LENGTH, PropertySpec, version_spec

__all__ = [
    "COPY_PROPERTIES",
    "COPY_PROPERTY_NAMES",
    "OBJECT_NAME",
    "REPEAT_PROPERTIES",
    "Repeat",
    "cites",
    "copies_of",
    "copy_thicknesses",
    "create_repeat",
    "is_copy",
    "is_inner_copy",
    "is_repeat",
    "member_flags",
    "repeat_of",
    "repeated_properties",
    "sources_of",
    "write_params",
]

OBJECT_NAME: Final = "Repeat"
MODEL_VERSION: Final = 1
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répétition")
GROUP: Final = "Répétition"
# Listes de choix des énumérations : valeurs de ``core.repeat`` (stables), ajouts en fin.
CHOICES: Final = {
    "Mode": [mode.value for mode in RepeatMode],
    "Spacing": [spacing.value for spacing in SpacingMode],
    "Axis": [axis.value for axis in RepeatAxis],
}

REPEAT_PROPERTIES: Final = (
    PropertySpec(
        "Source",
        "App::PropertyLinkList",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Pièces répétées (chacune a ses propres copies)."),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Mode",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Genre de répétition : Linear ; Circular et Path sont réservés."
        ),
        default=RepeatMode.LINEAR.value,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Spacing",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Manière de saisir la répétition : CountAndStep (nombre et pas), CountOnSpan (nombre "
            "sur une longueur) ou StepOnSpan (pas sur une longueur).",
        ),
        default=SpacingMode.COUNT_AND_STEP.value,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Axis",
        "App::PropertyEnumeration",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Axe global de la répétition linéaire."),
        default=RepeatAxis.X.value,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Count",
        "App::PropertyInteger",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Nombre de copies en plus de chaque source. Il ne change que par la commande "
            "« Modifier la répétition » (les copies se créent et se suppriment hors recalcul).",
        ),
        default=0,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Step",
        LENGTH,
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Pas entre deux copies, mesuré sur l'axe. Les copies suivent quand il change ; en "
            "mode « sur une longueur », la prochaine modification de la répétition le recalcule.",
        ),
        default=100.0,
    ),
    PropertySpec(
        "Span",
        LENGTH,
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Longueur à remplir (modes CountOnSpan et StepOnSpan), source comprise.",
        ),
        default=0.0,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Reverse",
        "App::PropertyBool",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Répète dans le sens négatif de l'axe ; les copies suivent."
        ),
        default=False,
    ),
    PropertySpec(
        "CopyJoints",
        "App::PropertyBool",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Recopie les assemblages de la source sur chaque copie."
        ),
        default=True,
        mode=READ_ONLY,
    ),
    PropertySpec(
        "FollowResize",
        "App::PropertyBool",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Suit le redimensionnement de l'ensemble : le pas se recalcule pour garder la "
            "longueur.",
        ),
        default=False,
        mode=READ_ONLY,
    ),
    version_spec(
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la répétition, utilisée pour migrer les anciens "
            "fichiers.",
        ),
        MODEL_VERSION,
    ),
)

COPY_PROPERTIES: Final = (
    PropertySpec(
        "Repeat",
        "App::PropertyLink",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Répétition dont la pièce est une copie liée."),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "RepeatSource",
        "App::PropertyLink",
        GROUP,
        QT_TRANSLATE_NOOP("App::Property", "Pièce dont celle-ci est la copie."),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "RepeatIndex",
        "App::PropertyInteger",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Rang de la copie (1 pour la première copie après la source)."
        ),
        default=1,
        mode=READ_ONLY,
    ),
)
COPY_PROPERTY_NAMES: Final = tuple(spec.name for spec in COPY_PROPERTIES)


class Repeat(StatelessProxy):
    """Proxy de la répétition. Chemin de module figé (ADR 0043) ; sans état enregistré.

    Sans forme : ``execute`` n'existe pas, les copies lisent ``Step`` et ``Reverse`` par leurs
    expressions.
    """

    TYPE: ClassVar[str] = "Menuiserie::Repeat"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés de la répétition, à leurs valeurs par défaut."""
        obj.Proxy = self
        schema.add_missing_properties(obj, REPEAT_PROPERTIES, choices=CHOICES)
        schema.apply_editor_modes(obj, REPEAT_PROPERTIES)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types contrôlés, propriétés manquantes recréées (ADR 0003)."""
        schema.restore_schema(obj, REPEAT_PROPERTIES, self.VERSION, NOUN, CHOICES)

    def unsetupObject(self, obj: DocumentObject) -> None:
        """Répétition supprimée (``removeObject``, interface comprise) : ses copies sont
        dissociées dans la même transaction, elles restent comme pièces libres et gardent leurs
        valeurs ; aucune expression ne vise un objet absent."""
        from freecad.menuiserie.features.repeat_links import repeat_removed

        repeat_removed(obj)


def is_repeat(obj: object) -> bool:
    """Vrai si ``obj`` est une répétition de l'atelier (faux pour un objet supprimé)."""
    return proxy_is(obj, Repeat)


def is_copy(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` est une copie liée à une répétition."""
    return all(name in obj.PropertiesList for name in COPY_PROPERTY_NAMES) and is_repeat(obj.Repeat)


def is_inner_copy(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` est la copie d'un membre, rangée dans l'ensemble copie de la même
    répétition (spécification § 2 bis) : ses cotes pilotées par l'ensemble viennent des liaisons
    de cet ensemble, les autres suivent le membre source."""
    parent = furniture_of(obj) if is_copy(obj) else None
    return parent is not None and is_copy(parent) and parent.Repeat == obj.Repeat


def cites(text: str, names: Collection[str]) -> bool:
    """Vrai si l'expression ``text`` cite l'un des objets ``names`` (``Nom.propriété``)."""
    return any(re.search(rf"(?<![\w.]){re.escape(name)}\.", text) for name in names)


def repeated_properties(obj: DocumentObject) -> frozenset[str]:
    """Propriétés de la copie ``obj`` dont l'expression cite sa source ou sa répétition."""
    if not is_copy(obj):
        return frozenset()
    names = {item.Name for item in (obj.Repeat, obj.RepeatSource) if item is not None}
    return frozenset(path for path, text in expressions_of(obj).items() if cites(text, names))


def member_flags(obj: DocumentObject) -> dict[str, object]:
    """Ce que ``core.furniture`` doit savoir de ``obj`` en tant que membre : ``linked`` (copie qui
    suit sa source, sans liaison d'ensemble) et ``repeated`` (propriétés qui la suivent)."""
    return {
        "linked": is_copy(obj) and not is_inner_copy(obj),
        "repeated": repeated_properties(obj),
    }


def copy_thicknesses(
    objects: Iterable[DocumentObject], thicknesses: Mapping[str, float] | None
) -> Mapping[str, float] | None:
    """``thicknesses`` (nom → épaisseur à venir) complétées : une copie liée prend l'épaisseur que
    prend sa source."""
    if not thicknesses:
        return thicknesses
    found = dict(thicknesses)
    for obj in objects:
        source = obj.RepeatSource if is_copy(obj) and not is_inner_copy(obj) else None
        if source is not None and source.Name in thicknesses:
            found[obj.Name] = thicknesses[source.Name]
    return found


def repeat_of(obj: DocumentObject) -> DocumentObject | None:
    """Répétition de ``obj`` : lui-même si c'est une répétition, celle dont il est une copie
    liée, ``None`` sinon (une source n'a pas une répétition mais peut en avoir plusieurs)."""
    if is_repeat(obj):
        return obj
    return obj.Repeat if is_copy(obj) else None


def sources_of(repeat: DocumentObject) -> list[DocumentObject]:
    """Pièces sources de la répétition, dans l'ordre de ``Source``."""
    return list(repeat.Source)


def copies_of(repeat: DocumentObject, source: DocumentObject | None = None) -> list[DocumentObject]:
    """Copies liées de la répétition (de la seule ``source`` si elle est donnée), par source puis
    par rang."""
    found = {
        obj.Name: obj
        for obj in repeat.InList  # un objet y figure autant de fois qu'il cite la répétition
        if is_copy(obj) and obj.Repeat == repeat and (source is None or obj.RepeatSource == source)
    }
    return sorted(
        found.values(), key=lambda copy: (getattr(copy.RepeatSource, "Name", ""), copy.RepeatIndex)
    )


def create_repeat(doc: Document, sources: list[DocumentObject]) -> DocumentObject:
    """Crée une répétition vide des ``sources`` (sans transaction ni recalcul) ; ses réglages
    sont écrits ensuite par :func:`write_params`."""
    obj = doc.addObject("App::FeaturePython", OBJECT_NAME)
    Repeat(obj)
    obj.Label = translated(NOUN)
    obj.Source = sources
    return obj


def write_params(repeat: DocumentObject, params: RepeatParams, resolved: Resolved) -> None:
    """Écrit les réglages, le nombre et le pas effectifs dans la répétition (propriétés écrites
    seulement si elles changent, pour ne pas toucher l'objet pour rien)."""
    values: dict[str, object] = {
        "Mode": params.mode.value,
        "Spacing": params.spacing.value,
        "Axis": params.axis.value,
        "Count": resolved.count,
        "Step": resolved.step,
        "Span": params.span,
        "Reverse": params.reverse,
        "CopyJoints": params.copy_joints,
        "FollowResize": params.follow_resize,
    }
    for name, value in values.items():
        current = getattr(repeat, name)
        if getattr(current, "Value", current) != value:
            setattr(repeat, name, value)
