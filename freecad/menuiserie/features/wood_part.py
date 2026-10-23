# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce de bois paramétrique : proxy ``WoodPart`` du FeaturePython et fonctions utilitaires.

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe ``WoodPart``,
les noms des propriétés et les valeurs des énumérations sont écrits dans les documents ; ils
ne changent jamais. Toute évolution passe par ``Version`` et :meth:`WoodPart._migrate`.

Les propriétés et leurs valeurs par défaut sont décrites dans :mod:`.wood_part_schema`, les
contrôles de la réouverture dans :mod:`.wood_part_restore`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import ClassVar, Final

import Part

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialLibrary
from freecad.menuiserie.core.naming import mark_from_label
from freecad.menuiserie.core.part_model import (
    Dimensions,
    GrainDirection,
    allowances_after_material_change,
    grain_after_material_change,
    material_has_grain,
    remembered_grain,
)
from freecad.menuiserie.features.freecad_types import (
    Document,
    DocumentObject,
    StatelessProxy,
    proxy_is,
    restoring_or_undoing,
)
from freecad.menuiserie.features.furniture import (
    MEMBER_OPTIONS,
    remember_before_change,
    take_previous,
)
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.features.part_labels import make_label_unique, sync_dependent_labels
from freecad.menuiserie.features.part_names import (
    default_label,
    label_of_mark,
    mark_is_bound,
    warn_mark_bound,
)
from freecad.menuiserie.features.schema import warn
from freecad.menuiserie.features.wood_part_record import (
    GRAIN_BY_VALUE,
    UnsupportedPartError,
    allowances_of,
    dimensions_of,
    known_value,
    newer_version_error,
    record_of,
)
from freecad.menuiserie.features.wood_part_restore import (
    EMPTY_LIBRARY_MIGRATION,
    migration_material,
    remove_mistyped_properties,
    restore_enumerations,
    restore_material_choices,
    restored_version,
    stored_material,
)
from freecad.menuiserie.features.wood_part_schema import (
    CATEGORIES,
    CATEGORY_BY_KIND,
    DEFAULT_DIMENSIONS,
    GRAIN_DIRECTIONS,
    KIND_BY_CATEGORY,
    MODEL_VERSION,
    add_missing_properties,
    apply_editor_modes,
    density_quantity,
    is_from_newer_version,
    material_choices,
    part_kind,
    select_label,
    show_grain_direction,
)

__all__ = [
    "CATEGORIES",
    "CATEGORY_BY_KIND",
    "GRAIN_DIRECTIONS",
    "OBJECT_NAME",
    "UnsupportedPartError",
    "WoodPart",
    "allowances_of",
    "create_wood_part",
    "dimensions_of",
    "is_wood_part",
    "record_of",
    "set_material",
    "shows_grain",
    "validated_arguments",
]

OBJECT_NAME: Final = "WoodPart"

_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas une pièce de bois."
)


class WoodPart(StatelessProxy):
    """Proxy du FeaturePython « pièce de bois ». Chemin de module figé (ADR 0003).

    Le proxy ne porte aucun état : tout est dans les propriétés de l'objet. Le drapeau de
    resynchronisation ``_syncing`` est lu avec ``getattr`` car ``__init__`` n'est pas rappelé
    à la réouverture d'un document.
    """

    TYPE: ClassVar[str] = "Menuiserie::WoodPart"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés de la pièce, aux valeurs du matériau par défaut de la
        bibliothèque. :func:`create_wood_part` valide cotes et matériau avant de l'appeler.

        Appelé directement avec une bibliothèque vide, il lève ``UnknownMaterialError`` (une
        ``KeyError``) : ``obj.Proxy`` est déjà assigné mais aucune propriété n'est ajoutée,
        l'objet est inutilisable et c'est à l'appelant de le supprimer du document.
        """
        obj.Proxy = self
        library = get_library()
        with self._synchronizing():
            add_missing_properties(obj, library, library.default_material())
            apply_editor_modes(obj)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types des propriétés contrôlés, énumérations canoniques, migration, modes
        d'édition (``Material`` en lecture seule si le document est plus récent), puis liste des
        matériaux de la bibliothèque locale ; propriétés de membre d'un ensemble contrôlées de
        même (J4)."""
        library = get_library()
        with self._synchronizing():
            version = restored_version(obj)
            mistyped = remove_mistyped_properties(obj)
            restore_enumerations(obj, library, keep_unknown=version > self.VERSION)
            self._migrate(obj, library, version, repair=bool(mistyped))
            apply_editor_modes(
                obj,
                show_grain=_shows_grain(obj, library),
                material_read_only=is_from_newer_version(obj),
            )
            restore_material_choices(obj, library)
        from freecad.menuiserie.features.furniture_restore import restore_member

        restore_member(obj)  # membre d'un ensemble (J4) ; sans effet sinon
        make_label_unique(obj)  # copie, duplication, fusion (J6, L5 bis)

    def onChanged(self, obj: DocumentObject, prop: str) -> None:
        """Choix d'un matériau dans la liste : recopie son identifiant, sa catégorie, sa masse
        volumique, et ajuste le fil et les surcotes (règles de ``core.part_model``). Choix d'un
        sens du fil : mémorisé (ADR 0005). Changement de matériau, annulation comprise : le fil
        est masqué ou affiché dans l'éditeur de propriétés. Mode, option « fixe » ou verrou d'un
        membre d'ensemble : ses seules liaisons sont recalculées ; épaisseur d'un membre :
        contrôlée, appliquée avec un avertissement si elle est refusée (ADR 0019 ; sans effet
        hors ensemble). Repère ou libellé modifié par l'utilisateur : l'autre suit (J6b,
        ADR 0011). Pièce d'un document plus récent (``Version`` > ``MODEL_VERSION``) : le choix du
        matériau n'est pas suivi (R1)."""
        if prop in ("MaterialId", "Category") and "Restore" not in obj.State:
            show_grain_direction(obj, shows_grain(obj))
        if not self._follows_user_changes(obj):
            return
        if prop == "Material":
            self._follow_material_choice(obj)
        elif prop == "GrainDirection":
            _remember_grain(obj)
        elif prop == "Mark":
            self.sync_label(obj)
        elif prop == "Label":
            self._adopt_typed_mark(obj)
        elif prop in MEMBER_OPTIONS or prop == "Thickness":  # membre d'un ensemble (J4)
            self._member_changed(obj, prop)

    def onBeforeChange(self, obj: DocumentObject, prop: str) -> None:
        """Valeur d'un réglage ou de l'épaisseur d'un membre d'ensemble avant une saisie de
        l'utilisateur, pour :meth:`onChanged` (sans effet hors ensemble)."""
        remember_before_change(obj, prop)

    def _member_changed(self, obj: DocumentObject, prop: str) -> None:
        """Réglage ou épaisseur d'un membre d'ensemble changé par l'utilisateur."""
        from freecad.menuiserie.features import furniture_edits

        previous = take_previous(obj, prop)
        if prop == "Thickness":
            furniture_edits.thickness_changed(obj, previous)
        else:
            furniture_edits.member_option_changed(obj, prop, previous)

    def _follow_material_choice(self, obj: DocumentObject) -> None:
        """Recopie le matériau choisi dans la liste ; sans effet pour une pièce d'un document
        plus récent, dont le matériau reste tel qu'enregistré."""
        if is_from_newer_version(obj):
            return
        material = get_library().find_by_name(obj.Material, display_language())
        if material is not None:
            self.select_material(obj, material)

    def allowDuplicateLabel(self, obj: DocumentObject) -> bool:  # pylint: disable=unused-argument
        """Vrai : FreeCAD ne rend pas lui-même le libellé unique (« M1001 ») avant
        :meth:`onBeforeChangeLabel` ; c'est l'atelier qui le fait, par le suffixe « (2) ». Aucune
        préférence de FreeCAD n'est lue ni modifiée (ADR 0011)."""
        return True

    def onBeforeChangeLabel(self, obj: DocumentObject, label: str) -> str | None:
        """Libellé saisi (arborescence, script) : mémorise le repère qu'il désigne, que
        :meth:`onChanged` écrira, et rend le libellé unique de ce repère (« M1 (2) »). Repère
        piloté par une expression : il ne change pas, avertissement, le libellé revient à celui
        du repère. Sans effet pendant une synchronisation, une restauration ou une annulation."""
        self._typed_mark = None
        if not self._follows_user_changes(obj):
            return None
        if mark_is_bound(obj):
            warn_mark_bound(obj)
            return label_of_mark(obj, obj.Mark)
        mark = mark_from_label(label, default_label())
        self._typed_mark = mark
        return label_of_mark(obj, mark)

    def sync_label(self, obj: DocumentObject) -> None:
        """Libellé = celui du repère de la pièce, puis libellés de sa pièce usinée et de ses
        assemblages."""
        label = label_of_mark(obj, obj.Mark)
        if obj.Label != label:
            with self._synchronizing():
                obj.Label = label
        sync_dependent_labels(obj)

    def adopt_mark(self, obj: DocumentObject, mark: str) -> None:
        """Repère = ``mark`` (déduit d'un libellé saisi), puis libellés de la pièce et de sa
        pièce usinée d'après ce repère."""
        if obj.Mark != mark:
            with self._synchronizing():
                obj.Mark = mark
        self.sync_label(obj)

    def _adopt_typed_mark(self, obj: DocumentObject) -> None:
        """Libellé changé : écrit le repère mémorisé par :meth:`onBeforeChangeLabel`."""
        mark: str | None = getattr(self, "_typed_mark", None)
        self._typed_mark = None
        if mark is not None:
            self.adopt_mark(obj, mark)

    def execute(self, obj: DocumentObject) -> None:
        """Reconstruit la forme depuis les seules cotes, sans toucher au ``Placement``."""
        with translated_errors():
            dimensions = dimensions_of(obj)
        placement = obj.Placement
        obj.Shape = Part.makeBox(dimensions.length, dimensions.width, dimensions.thickness)
        obj.Placement = placement

    def select_material(self, obj: DocumentObject, material: Material) -> None:
        """Sélectionne ``material`` dans la liste et recopie ses valeurs dans la pièce.
        ``UnsupportedPartError`` si la pièce vient d'un document plus récent ou porte une valeur
        inconnue : rien n'est écrit."""
        if is_from_newer_version(obj):
            raise newer_version_error(obj)
        with self._synchronizing():
            label = material.name(display_language())
            _apply_material(obj, material)
            select_label(obj, material_choices(get_library(), label), label)
            show_grain_direction(obj, material.has_grain)

    def _follows_user_changes(self, obj: DocumentObject) -> bool:
        """Faux pendant une resynchronisation interne, une restauration ou une annulation."""
        syncing: bool = getattr(self, "_syncing", False)
        return not syncing and not restoring_or_undoing(obj)

    def synchronizing(self) -> AbstractContextManager[None]:
        """Contexte où repère et libellé ne se répercutent pas l'un sur l'autre."""
        return self._synchronizing()

    @contextmanager
    def _synchronizing(self) -> Iterator[None]:
        previous: bool = getattr(self, "_syncing", False)
        self._syncing = True
        try:
            yield
        finally:
            self._syncing = previous

    def _migrate(
        self, obj: DocumentObject, library: MaterialLibrary, from_version: int, *, repair: bool
    ) -> None:
        """Version 0 (absente) ou 1 → 2 : ajoute les propriétés manquantes avec leurs défauts,
        déduits du matériau de la pièce (``MaterialId``), dont ``PreferredGrainDirection``
        d'après le fil (ADR 0005). Aboutit même si la bibliothèque est vide.

        ``repair`` : à toute version, recrée de même les propriétés supprimées à la réouverture
        (type inattendu), sans changer la ``Version``."""
        outdated = from_version < self.VERSION
        if not (outdated or repair):
            return
        if not len(library):
            warn(obj, EMPTY_LIBRARY_MIGRATION)
        add_missing_properties(obj, library, migration_material(obj, library))
        if outdated:
            obj.Version = self.VERSION


def create_wood_part(
    doc: Document,
    *,
    length: float = DEFAULT_DIMENSIONS.length,
    width: float = DEFAULT_DIMENSIONS.width,
    thickness: float = DEFAULT_DIMENSIONS.thickness,
    material_id: str | None = None,
    mark: str = "",
) -> DocumentObject:
    """Crée une pièce de bois dans ``doc`` (sans ViewProvider ni transaction ni recalcul).

    Cotes en mm ; ``material_id`` vaut par défaut le matériau par défaut de la bibliothèque.
    ``InvalidDimensionsError`` ou ``UnknownMaterialError`` sont levées avant toute création.
    """
    dimensions, material = validated_arguments(length, width, thickness, material_id)
    obj = doc.addObject("Part::FeaturePython", OBJECT_NAME)
    proxy = WoodPart(obj)
    proxy.select_material(obj, material)
    obj.Length = dimensions.length
    obj.Width = dimensions.width
    obj.Thickness = dimensions.thickness
    with proxy.synchronizing():  # le libellé est celui du repère (J6b), posé une seule fois
        obj.Mark = mark
        obj.Label = label_of_mark(obj, mark)
    return obj


def validated_arguments(
    length: float, width: float, thickness: float, material_id: str | None
) -> tuple[Dimensions, Material]:
    """Cotes et matériau d'une future pièce, sans rien créer : ``InvalidDimensionsError`` ou
    ``UnknownMaterialError`` (matériau inconnu, bibliothèque vide) s'ils sont refusés."""
    dimensions = Dimensions(length, width, thickness)
    library = get_library()
    material = library.default_material() if material_id is None else library.get(material_id)
    return dimensions, material


def is_wood_part(obj: object) -> bool:
    """Vrai si ``obj`` est une pièce de bois de l'atelier (faux pour un objet supprimé)."""
    return proxy_is(obj, WoodPart)


def set_material(obj: DocumentObject, material_id: str) -> None:
    """Change le matériau de la pièce (``UnknownMaterialError`` si l'identifiant est inconnu)."""
    if not is_wood_part(obj):
        raise TypeError(translated(_NOT_A_WOOD_PART, {"label": str(obj.Label)}))
    obj.Proxy.select_material(obj, get_library().get(material_id))


def shows_grain(obj: DocumentObject) -> bool:
    """Vrai si le fil de la pièce est visible : son matériau (ou, inconnu localement, sa
    famille) a un fil."""
    return _shows_grain(obj, get_library())


def _apply_material(obj: DocumentObject, material: Material) -> None:
    """Recopie le matériau dans la pièce ; fil et surcotes suivent les règles de ``core``."""
    old_kind = known_value(obj, "Category", KIND_BY_CATEGORY)
    grain = grain_after_material_change(
        material, known_value(obj, "GrainDirection", GRAIN_BY_VALUE), _preferred_grain(obj)
    )
    allowances = allowances_after_material_change(old_kind, material.kind, allowances_of(obj))
    obj.MaterialId = material.id
    obj.Category = CATEGORY_BY_KIND[material.kind]
    obj.Density = density_quantity(material.density)
    obj.GrainDirection = grain.value
    obj.LengthAllowance = allowances.length
    obj.WidthAllowance = allowances.width
    obj.ThicknessAllowance = allowances.thickness


def _shows_grain(obj: DocumentObject, library: MaterialLibrary) -> bool:
    """Visibilité du fil d'après le matériau de la pièce dans ``library``."""
    material = stored_material(obj, library)
    return material_has_grain(material, part_kind(obj, material))


def _preferred_grain(obj: DocumentObject) -> GrainDirection:
    """Sens mémorisé de la pièce ; ``LENGTH`` s'il est absent ou inconnu (jamais d'erreur)."""
    value = getattr(obj, "PreferredGrainDirection", None)
    if value == GrainDirection.WIDTH.value:
        return GrainDirection.WIDTH
    return GrainDirection.LENGTH


def _remember_grain(obj: DocumentObject) -> None:
    """Mémorise le sens du fil choisi (``Length`` ou ``Width``) ; « Sans fil » ne l'efface pas.
    Écrit dans la transaction de l'appelant, seulement si la mémoire change."""
    if "PreferredGrainDirection" not in obj.PropertiesList:
        return
    try:
        grain = GrainDirection(obj.GrainDirection)
    except ValueError:  # valeur d'une version plus récente, gardée à la réouverture
        return
    if grain is GrainDirection.NONE:  # la mémoire reste telle quelle, même illisible
        return
    remembered = remembered_grain(grain, _preferred_grain(obj)).value
    if obj.PreferredGrainDirection != remembered:
        obj.PreferredGrainDirection = remembered
