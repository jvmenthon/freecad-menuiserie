# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce en bois : proxy ``ShapedPart`` du FeaturePython qui enveloppe la forme d'un corps FreeCAD.

Contrat de persistance (ADR 0003, ADR 0020) : le chemin de ce module, le nom de la classe
``ShapedPart``, les noms des propriétés et les valeurs des énumérations sont écrits dans les
documents ; ils ne changent jamais. Toute évolution passe par ``Version`` et
:meth:`.MaterialProxy._migrate`.

La pièce lie sa source (``Source``) sans jamais la modifier et en recopie le solide dans son propre
repère (origine au coin minimal de l'encombrement, X = longueur, Y = largeur, Z = épaisseur) ; son
``Placement`` est libre, comme celui d'une pièce de bois. ``execute()`` ne lit que ``Source``,
``SourceAxes``, ``ProfileThickness`` et le solide désigné (``SolidIndex``, ``SolidSignature``).
Exception documentée à la règle « ``execute()`` ne fait que reconstruire ``obj.Shape`` » (ADR 0020,
décision 5) : il écrit aussi les trois cotes d'encombrement **de son propre objet**, en statut
``Output`` et seulement si elles changent ; il n'écrit jamais dans un autre objet.

Les propriétés sont décrites dans :mod:`.shaped_part_schema`, la lecture des sources dans
:mod:`.shaped_sources`, le repère dans :mod:`.shaped_frame`, la création dans :mod:`.shaped_create`.
"""

from __future__ import annotations

from typing import Any, ClassVar, Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialLibrary
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.shaped import ShapeSignature
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression, proxy_is
from freecad.menuiserie.features.furniture import MEMBER_OPTIONS, furniture_of
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.features.part_labels import make_label_unique
from freecad.menuiserie.features.shaped_frame import LocalForm, local_form, placement_axes
from freecad.menuiserie.features.shaped_part_schema import (
    DIMENSION_NAMES,
    MODEL_VERSION,
    NOUN,
    PROPERTIES,
    add_missing_properties,
    apply_editor_modes,
    is_from_newer_version,
)
from freecad.menuiserie.features.shaped_sources import picked_solid, read_source
from freecad.menuiserie.features.wood_material import shows_grain
from freecad.menuiserie.features.wood_material_proxy import MaterialProxy
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.features.wood_part_record import dimensions_of, record_of
from freecad.menuiserie.features.wood_part_restore import (
    restore_enumerations,
    restore_material_choices,
)

__all__ = [
    "OBJECT_NAME",
    "ShapedPart",
    "base_shape_of",
    "dimensions_of",
    "is_profile",
    "is_shaped_part",
    "is_timber",
    "record_of",
    "shaped_form",
    "signature_of",
    "source_solid",
]

OBJECT_NAME: Final = "ShapedPart"

_NO_SOURCE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce en bois « {label} » sans forme : la source a été supprimée ; supprimez la pièce ou "
    "annulez la suppression.",
)
_AXES_UNREADABLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce en bois « {label} » : le repère de la pièce est illisible ; utilisez « Repère "
    "automatique ».",
)
_DRAWN_SIZE_CHANGED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les cotes dessinées de « {label} » ont changé : relancez « Relier les pièces » sur son "
    "ensemble pour que les pièces voisines en tiennent compte.",
)
_DIMENSION_EXPRESSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les cotes de « {label} » viennent du dessin : l'expression posée sur {property} est "
    "refusée ; modifiez le dessin.",
)


def is_shaped_part(obj: object) -> bool:
    """Vrai si ``obj`` est une pièce en bois de l'atelier (faux pour un objet supprimé)."""
    return proxy_is(obj, ShapedPart)


def is_timber(obj: object) -> bool:
    """Vrai si ``obj`` est une pièce de bois (boîte paramétrique) **ou** une pièce en bois
    (forme dessinée) : les deux ont les mêmes cotes et propriétés de matériau."""
    return is_wood_part(obj) or is_shaped_part(obj)


def is_profile(obj: DocumentObject) -> bool:
    """Vrai si la source de la pièce en bois ``obj`` est une esquisse extrudée (mode profil)."""
    source = getattr(obj, "Source", None)
    return source is not None and bool(source.isDerivedFrom("Part::Part2DObject"))


class ShapedPart(MaterialProxy):
    """Proxy du FeaturePython « pièce en bois ». Chemin de module figé (ADR 0003, ADR 0020).

    Le proxy ne porte aucun état : tout est dans les propriétés de l'objet. Matériau, fil, repère
    et libellé sont gérés par :class:`.MaterialProxy`, partagé avec la pièce de bois.
    """

    TYPE: ClassVar[str] = "Menuiserie::ShapedPart"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés de la pièce, aux valeurs du matériau par défaut de la
        bibliothèque. :func:`.shaped_create.create_shaped_parts` valide la source avant de
        l'appeler. Appelé avec une bibliothèque vide, il lève ``UnknownMaterialError`` (une
        ``KeyError``) : aucune propriété n'est ajoutée, c'est à l'appelant de supprimer l'objet."""
        obj.Proxy = self
        library = get_library()
        material = library.default_material()
        with self._synchronizing():
            self.add_properties(obj, library, material)
            apply_editor_modes(obj, profile=is_profile(obj))

    def library(self) -> MaterialLibrary:
        """Bibliothèque de matériaux de la session."""
        return get_library()

    def language(self) -> str:
        """Langue des libellés de matériaux."""
        return display_language()

    def add_properties(
        self, obj: DocumentObject, library: MaterialLibrary, material: Material | None
    ) -> None:
        """Ajoute les propriétés absentes de la pièce en bois (schéma ADR 0020)."""
        add_missing_properties(obj, library, material)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types des propriétés contrôlés, énumérations canoniques, migration, modes
        d'édition (``Material`` en lecture seule si le document est plus récent), puis liste des
        matériaux de la bibliothèque locale ; libellé rendu unique après une copie."""
        library = get_library()
        with self._synchronizing():
            version = schema.restored_version(obj, MODEL_VERSION, NOUN)
            mistyped = schema.remove_mistyped_properties(obj, PROPERTIES, NOUN)
            restore_enumerations(obj, library, keep_unknown=version > self.VERSION)
            self._migrate(obj, library, version, repair=bool(mistyped))
            apply_editor_modes(
                obj,
                show_grain=shows_grain(obj, library),
                material_read_only=is_from_newer_version(obj),
                profile=is_profile(obj),
            )
            restore_material_choices(obj, library)
        from freecad.menuiserie.features.furniture_restore import restore_member

        restore_member(obj)  # membre d'un ensemble (J4) ; sans effet sinon
        make_label_unique(obj)  # copie, duplication, fusion (J6, L5 bis)

    def onChanged(self, obj: DocumentObject, prop: str) -> None:
        """Matériau, fil, repère et libellé : voir :meth:`.MaterialProxy.onChanged`. Une
        expression posée sur une cote d'encombrement est refusée (elles viennent du dessin)."""
        super().onChanged(obj, prop)
        if prop == "ExpressionEngine" and self._follows_user_changes(obj):
            self._refuse_dimension_expressions(obj)
        if prop in MEMBER_OPTIONS and self._follows_user_changes(obj):
            from freecad.menuiserie.features.furniture_edits import member_changed

            member_changed(obj, prop)  # membre d'ensemble (J4) : ses cotes restent fixes (F1)

    def unsetupObject(self, obj: DocumentObject) -> None:
        """Pièce supprimée : ses voisines d'ensemble sont reliées sans elle (même transaction)."""
        from freecad.menuiserie.features.furniture_relink import member_removed

        member_removed(obj)

    def _refuse_dimension_expressions(self, obj: DocumentObject) -> None:
        """Retire, avec un avertissement traduit, l'expression posée sur ``Length``, ``Width``
        ou ``Thickness`` (propriétés de sortie)."""
        for name in DIMENSION_NAMES:
            if has_expression(obj, name):
                obj.setExpression(name, None)
                schema.warn(obj, _DIMENSION_EXPRESSION, property=name)

    def execute(self, obj: DocumentObject) -> None:
        """Reconstruit la forme depuis la source, dans le repère de la pièce, sans toucher au
        ``Placement`` ; écrit les cotes d'encombrement (propriétés de sortie) si elles changent,
        et avertit si c'est un membre d'ensemble. ``ValueError`` ou ``TypeError`` traduite si la
        source manque, a changé ou est refusée."""
        form = shaped_form(obj)
        placement = obj.Placement
        obj.Shape = form.shape
        obj.Placement = placement
        changed = False
        for name, value in zip(DIMENSION_NAMES, form.extents, strict=True):
            old = getattr(obj, name).Value
            if old != value:
                changed = changed or old > 0.0
                setattr(obj, name, value)
        if changed and furniture_of(obj) is not None:
            # Les voisines gardent leurs constantes figées (ADR 0019) : simple avertissement,
            # la pièce n'écrit pas dans un autre objet.
            schema.warn(obj, _DRAWN_SIZE_CHANGED)


def source_solid(obj: DocumentObject) -> Any:
    """Solide de la source de la pièce en bois ``obj``, dans le repère propre de la source
    (placement défait). ``ValueError`` ou ``TypeError`` traduite si la source manque, est
    refusée ou n'a plus le solide converti (forme importée remplacée)."""
    source = obj.Source
    if source is None:
        raise ValueError(translated(_NO_SOURCE, {"label": quoted_value(obj.Label)}))
    reading = read_source(source, obj.ProfileThickness.Value)
    return picked_solid(reading, obj.SolidIndex, obj.SolidSignature)


def shaped_form(obj: DocumentObject) -> LocalForm:
    """Forme de la pièce en bois ``obj`` dans son repère et cotes d'encombrement, d'après sa
    source et ``SourceAxes`` (jamais recalculé ici). ``ValueError`` traduite si une cote sort de
    ``[MIN_DIMENSION_MM, MAX_DIMENSION_MM]`` ou si le repère est illisible."""
    raw = source_solid(obj)
    try:
        axes = placement_axes(obj.SourceAxes)
    except ValueError as error:
        raise ValueError(
            translated(_AXES_UNREADABLE, {"label": quoted_value(obj.Label)})
        ) from error
    form = local_form(raw, axes)
    with translated_errors():
        Dimensions(*form.extents)
    return form


def signature_of(obj: DocumentObject) -> ShapeSignature:
    """Empreinte de forme de la pièce en bois (volume, aire, nombre de faces, dans son repère),
    pour le regroupement de la liste de débit (C4)."""
    shape = obj.Shape
    return ShapeSignature(shape.Volume, shape.Area, len(shape.Faces))


def base_shape_of(obj: DocumentObject) -> Any:
    """Forme de la pièce en bois dans son repère (placement défait) : la forme de base de sa
    pièce usinée (ADR 0006, ADR 0020)."""
    shape = obj.Shape.copy()
    shape.Placement = App.Placement()
    return shape
