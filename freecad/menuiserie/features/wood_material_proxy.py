# SPDX-License-Identifier: LGPL-2.1-or-later
"""Comportement de matériau et de repère partagé par les proxys ``WoodPart`` et ``ShapedPart``.

Squelette commun (Méthode patron, CONTRIBUTING) : :class:`MaterialProxy` fixe la réaction aux
changements de matériau, de fil, de repère et de libellé (J6b, ADR 0011), en s'appuyant sur les
fonctions de :mod:`.wood_material` ; chaque sous-classe fournit sa ``VERSION``, sa bibliothèque
(:meth:`MaterialProxy.library`) et sa langue (:meth:`MaterialProxy.language`). Le drapeau
``_syncing`` est lu avec ``getattr`` car ``__init__`` n'est pas rappelé à la réouverture d'un
document.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import ClassVar

from freecad.menuiserie.core.materials import Material, MaterialLibrary
from freecad.menuiserie.core.naming import mark_from_label
from freecad.menuiserie.features.freecad_types import (
    DocumentObject,
    StatelessProxy,
    restoring_or_undoing,
)
from freecad.menuiserie.features.part_labels import sync_dependent_labels
from freecad.menuiserie.features.part_names import (
    default_label,
    label_of_mark,
    mark_is_bound,
    warn_mark_bound,
)
from freecad.menuiserie.features.schema import warn
from freecad.menuiserie.features.wood_material import (
    apply_material,
    is_newer_version,
    material_choices,
    newer_version_error,
    remember_grain,
    select_label,
    show_grain_direction,
    shows_grain,
)
from freecad.menuiserie.features.wood_part_restore import (
    EMPTY_LIBRARY_MIGRATION,
    migration_material,
)

__all__ = ["MaterialProxy"]


class MaterialProxy(StatelessProxy):
    """Base des proxys de pièces : matériau, fil, repère et libellé de la pièce (sans état)."""

    VERSION: ClassVar[int]

    def library(self) -> MaterialLibrary:
        """Bibliothèque de matériaux de la session (fournie par la sous-classe)."""
        raise NotImplementedError

    def language(self) -> str:
        """Langue des libellés de matériaux (fournie par la sous-classe)."""
        raise NotImplementedError

    def add_properties(
        self, obj: DocumentObject, library: MaterialLibrary, material: Material | None
    ) -> None:
        """Ajoute les propriétés absentes de ``obj``, aux valeurs par défaut déduites de
        ``material`` (fournie par la sous-classe)."""
        raise NotImplementedError

    def onChanged(self, obj: DocumentObject, prop: str) -> None:
        """Choix d'un matériau dans la liste : recopie son identifiant, sa catégorie, sa masse
        volumique, et ajuste le fil et les surcotes (règles de ``core.part_model``). Choix d'un
        sens du fil : mémorisé (ADR 0005). Changement de matériau, annulation comprise : le fil
        est masqué ou affiché dans l'éditeur de propriétés. Repère ou libellé modifié : l'autre
        suit (J6b, ADR 0011). Pièce d'un document plus récent (``Version`` > ``VERSION``) : le
        choix du matériau n'est pas suivi (R1)."""
        if prop in ("MaterialId", "Category") and "Restore" not in obj.State:
            show_grain_direction(obj, shows_grain(obj, self.library()))
        if not self._follows_user_changes(obj):
            return
        if prop == "Material":
            self._follow_material_choice(obj)
        elif prop == "GrainDirection":
            remember_grain(obj)
        elif prop == "Mark":
            self.sync_label(obj)
        elif prop == "Label":
            self._adopt_typed_mark(obj)

    def _follow_material_choice(self, obj: DocumentObject) -> None:
        """Recopie le matériau choisi dans la liste ; sans effet pour une pièce d'un document
        plus récent, dont le matériau reste tel qu'enregistré."""
        if is_newer_version(obj, self.VERSION):
            return
        material = self.library().find_by_name(obj.Material, self.language())
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

    def select_material(self, obj: DocumentObject, material: Material) -> None:
        """Sélectionne ``material`` dans la liste et recopie ses valeurs dans la pièce.
        ``UnsupportedPartError`` si la pièce vient d'un document plus récent ou porte une valeur
        inconnue : rien n'est écrit."""
        if is_newer_version(obj, self.VERSION):
            raise newer_version_error(obj)
        with self._synchronizing():
            label = material.name(self.language())
            apply_material(obj, material)
            select_label(obj, material_choices(self.library(), label), label)
            show_grain_direction(obj, material.has_grain)

    def _migrate(
        self, obj: DocumentObject, library: MaterialLibrary, from_version: int, *, repair: bool
    ) -> None:
        """Version antérieure à ``VERSION`` (0 si absente) : ajoute les propriétés manquantes avec
        leurs défauts, déduits du matériau de la pièce (``MaterialId``), dont
        ``PreferredGrainDirection`` d'après le fil (ADR 0005). Aboutit même si la bibliothèque est
        vide.

        ``repair`` : à toute version, recrée de même les propriétés supprimées à la réouverture
        (type inattendu), sans changer la ``Version``."""
        outdated = from_version < self.VERSION
        if not (outdated or repair):
            return
        if not len(library):
            warn(obj, EMPTY_LIBRARY_MIGRATION)
        self.add_properties(obj, library, migration_material(obj, library))
        if outdated:
            obj.Version = self.VERSION

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
