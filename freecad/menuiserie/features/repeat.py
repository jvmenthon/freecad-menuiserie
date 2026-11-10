# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition : objet de cotes sans forme (ADR 0043), propriétés de ses copies.

La répétition (``App::FeaturePython``, nom interne ``Repeat``) décrit comment une ou plusieurs
pièces sources sont répétées : ``Source``, ``Mode``, ``Spacing``, une ligne par axe actif de la
grille (``Axis``, ``Count`` en copies le long de l'axe, ``Step``, ``Span``, ``Reverse`` ; suffixe
``2`` et ``3`` pour les lignes suivantes, voir :mod:`.repeat_props`), ``CopyJoints``,
``FollowResize``, ``DeductThickness`` et, par ligne, la butée (``Stop``, ``StopLabel`` :
:mod:`.repeat_stop_props`). Elle n'a pas de forme. Chaque copie est une vraie pièce de bois qui
porte ``Repeat`` (lien vers la répétition), ``RepeatSource`` (la source dont elle est la copie),
``RepeatIndex`` (rang linéaire, à partir de 1, pour l'ordre d'affichage) et ``RepeatCell`` (sa
cellule ``(i, j, k)`` dans la grille, qui l'identifie), en lecture seule. Les expressions qui lient
la copie à sa source sont écrites par :mod:`.repeat_links` et :mod:`.repeat_copies`, jamais ici ni
pendant un recalcul.

Modifiable dans l'éditeur de propriétés : les pas (``Step``, ``Step2``, ``Step3``) et les sens
(``Reverse``…) : les copies suivent. Les autres propriétés sont en lecture seule : leur changement
réécrit des expressions, ce que seule l'API (:mod:`freecad.menuiserie.api`) fait, dans une
transaction. Les nombres ne changent donc que par l'API (``edit_repeat``).

Contrat de persistance (ADR 0003 et 0045) : le chemin de ce module, le nom de la classe
``Repeat``, les noms des propriétés (de la répétition et des copies) et les valeurs de ``Mode``,
``Spacing`` et ``Axis`` (celles de ``core.repeat``) sont écrits dans les documents ; ils ne
changent jamais. Un document d'avant la grille n'a ni lignes 2 et 3 ni ``RepeatCell`` : la
première ligne suffit, et la cellule d'une copie se déduit de son rang (``cell_of``).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping
from typing import ClassVar, Final

from freecad.menuiserie.core.repeat import (
    AxisRepeat,
    Cell,
    RepeatAxis,
    RepeatParams,
    ResolvedGrid,
    SpacingMode,
    axis_index,
)
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import (
    Document,
    DocumentObject,
    StatelessProxy,
    proxy_is,
)
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_container import member_expressions, std_part_of
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.repeat_props import (
    CELL_PROPERTY,
    CELL_SPEC,
    CHOICES,
    COPY_PROPERTIES,
    COPY_PROPERTY_NAMES,
    GRID_PROPERTIES,
    LINE_COUNT,
    MODEL_VERSION,
    NO_AXIS,
    NOUN,
    REPEAT_PROPERTIES,
    line_name,
)
from freecad.menuiserie.features.repeat_stop_props import (
    DEDUCT_PROPERTY,
    GAP_PROPERTY,
    STOP_PROPERTIES,
)

__all__ = [
    "COPY_PROPERTIES",
    "COPY_PROPERTY_NAMES",
    "OBJECT_NAME",
    "REPEAT_PROPERTIES",
    "Repeat",
    "cell_of",
    "cited_names",
    "cites",
    "copies_of",
    "copy_thicknesses",
    "create_repeat",
    "ensure_lines",
    "is_copy",
    "is_inner_copy",
    "is_repeat",
    "member_flags",
    "repeat_of",
    "repeated_properties",
    "sources_of",
    "stored_dims",
    "stored_lines",
    "stored_params",
    "write_cell",
    "write_params",
]

OBJECT_NAME: Final = "Repeat"
_LINE_FIELDS: Final = ("Axis", "Count", "Step", "Span", "Reverse")


class Repeat(StatelessProxy):
    """Proxy de la répétition. Chemin de module figé (ADR 0043) ; sans état enregistré.

    Sans forme : ``execute`` ne suit que les butées (ADR 0047) ; les copies lisent ``Step`` et
    ``Reverse`` par leurs expressions.
    """

    TYPE: ClassVar[str] = "Menuiserie::Repeat"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés de la répétition, à leurs valeurs par défaut."""
        obj.Proxy = self
        for specs in (REPEAT_PROPERTIES, GRID_PROPERTIES, STOP_PROPERTIES):
            schema.add_missing_properties(obj, specs, choices=CHOICES)
            schema.apply_editor_modes(obj, specs)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types contrôlés, propriétés manquantes recréées (ADR 0003)."""
        schema.restore_schema(obj, REPEAT_PROPERTIES, self.VERSION, NOUN, CHOICES)
        # Lignes 2 et 3, butées : absentes d'un document plus ancien (même version du modèle).
        ensure_lines(obj)
        from freecad.menuiserie.features.repeat_stop_raw import restore_raw_stops

        restore_raw_stops(obj)  # butée sur une pièce usinée : cycle, elle vise la brute

    def execute(self, obj: DocumentObject) -> None:
        """Recalcul : la longueur d'une ligne qui a une butée suit la butée (ADR 0047) ; sans
        forme, la répétition n'écrit que sa longueur et son pas calculés, ses propres sorties."""
        from freecad.menuiserie.features.repeat_stop import follow_stops

        follow_stops(obj)

    def unsetupObject(self, obj: DocumentObject) -> None:
        """Répétition supprimée (``removeObject``, interface comprise) : ses copies sont
        supprimées dans la même transaction (une seule annulation les fait revenir)."""
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


def cited_names(obj: DocumentObject) -> set[str]:
    """Noms que les expressions de liaison de la copie ``obj`` citent : sa répétition, sa source
    et, pour un ensemble source, le Std Part de celui-ci (ADR 0044, « Std Part »)."""
    items = [obj.Repeat, obj.RepeatSource]
    if is_furniture(obj.RepeatSource):
        items.append(std_part_of(obj.RepeatSource))
    return {item.Name for item in items if item is not None}


def repeated_properties(obj: DocumentObject) -> frozenset[str]:
    """Propriétés de la copie ``obj`` dont l'expression cite sa source ou sa répétition (le
    ``Placement`` du Std Part d'un ensemble compris)."""
    if not is_copy(obj):
        return frozenset()
    names = cited_names(obj)
    found = member_expressions(obj)
    return frozenset(path for path, text in found.items() if cites(text, names))


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


def create_repeat(
    doc: Document, sources: list[DocumentObject], container: DocumentObject | None = None
) -> DocumentObject:
    """Crée une répétition vide des ``sources`` (sans transaction ni recalcul) ; ses réglages
    sont écrits ensuite par :func:`write_params`. ``container`` : conteneur ``App::Part`` des
    sources, où la répétition est rangée comme leurs copies (sans quoi les liens des copies
    sortiraient de la portée de leur conteneur)."""
    obj = doc.addObject("App::FeaturePython", OBJECT_NAME)
    Repeat(obj)
    if container is not None:
        container.addObject(obj)
    obj.Label = translated(NOUN)
    obj.Source = sources
    return obj


def ensure_lines(repeat: DocumentObject) -> None:
    """Propriétés des lignes 2 et 3 de la grille et des butées, ajoutées si le document est d'avant
    la grille ou d'avant les butées."""
    for specs in (GRID_PROPERTIES, STOP_PROPERTIES):
        schema.add_missing_properties(repeat, specs, choices=CHOICES)
        schema.apply_editor_modes(repeat, specs)


def stored_lines(repeat: DocumentObject) -> tuple[AxisRepeat, ...]:
    """Lignes de la grille telles que la répétition les garde (valeurs brutes, non contrôlées) :
    une par axe actif, X avant Y avant Z. ``count`` en éléments (copies le long de l'axe plus un).
    Les lignes 2 et 3 d'un document d'avant la grille n'existent pas : elles sont sautées."""
    lines = []
    for index in range(LINE_COUNT):
        axis = str(getattr(repeat, line_name("Axis", index), NO_AXIS))
        if axis == NO_AXIS:
            continue
        value = {name: getattr(repeat, line_name(name, index)) for name in _LINE_FIELDS}
        lines.append(
            AxisRepeat(
                RepeatAxis(axis),
                int(value["Count"]) + 1,
                float(value["Step"].Value),
                float(value["Span"].Value),
                bool(value["Reverse"]),
            )
        )
    return tuple(lines)


def stored_params(repeat: DocumentObject) -> RepeatParams:
    """Réglage de la répétition, tel que l'écrit :func:`write_params` (``RepeatError`` si les
    valeurs gardées sont refusées par le noyau)."""
    return RepeatParams(
        spacing=SpacingMode(str(repeat.Spacing)),
        grid=stored_lines(repeat),
        copy_joints=bool(repeat.CopyJoints),
        follow_resize=bool(repeat.FollowResize),
        deduct_thickness=bool(getattr(repeat, DEDUCT_PROPERTY, True)),
        end_gap=bool(getattr(repeat, GAP_PROPERTY, False)),
    )


def stored_dims(repeat: DocumentObject) -> Cell:
    """Nombre d'éléments sur X, Y et Z de la grille que garde la répétition (1 : axe inactif)."""
    dims = [1, 1, 1]
    for line in stored_lines(repeat):
        dims[axis_index(line.axis)] = line.count
    return (dims[0], dims[1], dims[2])


def cell_of(copy: DocumentObject) -> Cell:
    """Cellule ``(i, j, k)`` de la copie ``copy`` dans la grille de sa répétition. Une copie d'avant
    la grille (sans ``RepeatCell``) est sur l'axe de la première ligne, à son rang."""
    value = list(getattr(copy, CELL_PROPERTY, ()) or ())
    if len(value) == 3:
        return (int(value[0]), int(value[1]), int(value[2]))
    cell = [0, 0, 0]
    cell[axis_index(RepeatAxis(str(copy.Repeat.Axis)))] = int(copy.RepeatIndex)
    return (cell[0], cell[1], cell[2])


def write_cell(copy: DocumentObject, cell: Cell) -> None:
    """Écrit ``RepeatCell`` (ajoutée pour une copie d'avant la grille), si elle change."""
    schema.add_missing_properties(copy, (CELL_SPEC,))
    schema.apply_editor_modes(copy, (CELL_SPEC,))
    if tuple(getattr(copy, CELL_PROPERTY)) != cell:
        setattr(copy, CELL_PROPERTY, list(cell))


def write_params(repeat: DocumentObject, params: RepeatParams, grid: ResolvedGrid) -> None:
    """Écrit les réglages, le nombre et le pas effectifs de chaque ligne dans la répétition
    (propriétés écrites seulement si elles changent, pour ne pas toucher l'objet pour rien). Les
    lignes 2 et 3 sans axe sont marquées ``None``."""
    ensure_lines(repeat)
    values: dict[str, object] = {
        "Mode": params.mode.value,
        "Spacing": params.spacing.value,
        "CopyJoints": params.copy_joints,
        "FollowResize": params.follow_resize,
        DEDUCT_PROPERTY: params.deduct_thickness,
        GAP_PROPERTY: params.end_gap,
    }
    spans = {line.axis: line for line in params.lines}
    for index in range(LINE_COUNT):
        names = {name: line_name(name, index) for name in _LINE_FIELDS}
        if index < len(grid.axes):
            resolved = grid.axes[index]
            line = spans[resolved.axis]
            values[names["Axis"]] = resolved.axis.value
            values[names["Count"]] = resolved.count
            values[names["Step"]] = resolved.step
            values[names["Span"]] = line.span
            values[names["Reverse"]] = line.reverse
        elif index > 0:
            values[names["Axis"]] = NO_AXIS
            values[names["Count"]] = 0
    for name, value in values.items():
        current = getattr(repeat, name)
        if getattr(current, "Value", current) != value:
            setattr(repeat, name, value)
