# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche de la pièce en bois : après la conversion (commande) et au double-clic (D2).

Même formulaire que la pièce de bois (``wood_part.ui``, lignes communes de :mod:`.timber_rows`),
dans l'ordre Identification, Matériau, Repère de la pièce (:mod:`.shaped_part_frame`), Encombrement
(L, l et e en lecture seule, relus à chaque recalcul), Rotation, Surcotes, Épaisseur du profil
(esquisse seulement) et bouton « Modifier le dessin ». Chaque saisie est écrite aussitôt dans
l'objet puis la pièce est recalculée (aperçu en direct) ; « OK » valide la transaction ouverte par
la commande ou par :func:`start_editing`, « Annuler » l'abandonne (la conversion disparaît, ou les
valeurs reviennent à l'état d'avant). Pendant le panneau, le repère de la pièce (trièdre L / l / e
et fil) est dessiné dans la vue 3D (:mod:`.shaped_part_axes`), retiré à la fermeture ; ses flèches
de glissement à la souris restent actives (:class:`.PanelDrag`, ADR 0021), sans poignée : les cotes
viennent du dessin.
"""

from __future__ import annotations

from functools import partial
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM, MIN_DIMENSION_MM
from freecad.menuiserie.core.snap import Turn
from freecad.menuiserie.features.drag_joints import rotate_checked
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.placement import SnapSession, snap_part
from freecad.menuiserie.features.shaped_part import is_profile
from freecad.menuiserie.features.shaped_part_schema import DIMENSION_NAMES, is_from_newer_version
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    ObjectTaskPanel,
    UpdateGuard,
    connect,
    panel_title,
)
from freecad.menuiserie.gui.task_panels.furniture_widgets import quantity_field
from freecad.menuiserie.gui.task_panels.shaped_part_axes import AxesView
from freecad.menuiserie.gui.task_panels.shaped_part_frame import FrameRows
from freecad.menuiserie.gui.task_panels.timber_rows import (
    AllowanceRows,
    MaterialRows,
    bind_field,
    connect_rotations,
    setup_rotation_buttons,
)
from freecad.menuiserie.gui.task_panels.wood_part import ALLOWANCE_FIELDS, UI_FILE
from freecad.menuiserie.gui.task_panels.wood_part_drag import PanelDrag
from freecad.menuiserie.gui.task_panels.wood_part_snap import SnapRows
from freecad.menuiserie.gui.view_providers.shaped_part import ICON

FORM_NAME: Final = "ShapedPartTaskPanel"
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier une pièce en bois")
_CREATE_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Nouvelle pièce en bois")
_ENVELOPE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Encombrement")
_ENVELOPE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cotes du plus petit parallélépipède qui contient la forme, dans le repère de la pièce. Elles "
    "viennent du dessin : modifiez le dessin pour les changer.",
)
_PROFILE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur du profil")
_PROFILE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Épaisseur de la pièce tirée de l'esquisse, selon la normale de l'esquisse."
)
_EDIT_DRAWING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier le dessin")
_EDIT_DRAWING_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Valide le panneau, puis ouvre l'édition de la dernière fonction du corps (Tip) ou de "
    "l'esquisse.",
)
_NO_DRAWING_EDITOR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Cette forme se modifie avec l'outil qui l'a créée."
)
_DRAWING_REFUSED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'édition du dessin de « {label} » n'a pas pu être ouverte."
)
_DIMENSION_WIDGETS: Final = ("lengthEdit", "widthEdit", "thicknessEdit")


def drawing_target(part: DocumentObject) -> DocumentObject | None:
    """Objet à éditer pour modifier le dessin de la pièce en bois ``part`` : la fonction ``Tip``
    du corps (le corps lui-même sans ``Tip``) ou l'esquisse ; ``None`` pour une autre forme."""
    source = part.Source
    if source is None:
        return None
    if source.isDerivedFrom("PartDesign::Body"):
        return source.Tip or source
    if source.isDerivedFrom("Part::Part2DObject"):
        return source
    return None


def open_drawing_editor(document_name: str, object_name: str) -> None:
    """Ouvre l'édition de l'objet ``object_name`` : comme un double-clic dans l'arbre (qui active
    le corps de PartDesign), à défaut le mode d'édition 0. Un échec est signalé dans la vue
    rapport."""
    document = App.listDocuments().get(document_name)
    target = document.getObject(object_name) if document is not None else None
    if target is None:
        return
    vobj = target.ViewObject
    opened = False
    double_click = getattr(vobj, "doubleClicked", None)
    if callable(double_click):
        opened = bool(double_click())
    if not opened:
        opened = bool(Gui.getDocument(document_name).setEdit(target, 0))
    if not opened:
        report_warning(translated(_DRAWING_REFUSED, {"label": str(target.Label)}))


class ShapedPartTaskPanel(ObjectTaskPanel):
    """Panneau de tâche d'une pièce en bois, après sa conversion (``creating``) ou en modification.

    ``session`` : accrochage de la pièce convertie contre des éléments sélectionnés en plus de la
    source (D6) ; sans cible, les boutons de rotation la tournent sur place."""

    def __init__(
        self, obj: DocumentObject, *, creating: bool, session: SnapSession | None = None
    ) -> None:
        super().__init__(obj, creating=creating)
        self._guard = UpdateGuard()
        self._session = session if creating and session is not None and session.targets else None
        self.form = Gui.PySideUic.loadUi(str(UI_FILE))
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(panel_title(str(obj.Label), creating, _CREATE_TITLE))
        self._material = MaterialRows(self.form, obj, self._guard, self._on_material, self.preview)
        self._allowances = AllowanceRows(
            self.form, obj, self._guard, ALLOWANCE_FIELDS, self._recompute
        )
        self._frame = FrameRows(obj, self._on_frame_changed)
        self._bindings: list[Any] = []  # liaisons d'expressions, gardées en vie avec le panneau
        self._profile_group, self._profile = self._make_profile_group(obj)
        self._edit_button = self._make_edit_button(obj)
        self._arrange_form()
        self._material.fill_choices()
        self._material.fill_materials()
        self._allowances.fold(False)
        self._material.lock(is_from_newer_version(obj))
        setup_rotation_buttons(self.form, obj)
        self._connect_signals()
        self._show_values()
        self._snap = SnapRows(self.form, obj, self._session)
        self._axes = AxesView(obj)
        connect(self.form, "destroyed()", self._axes.remove)
        self._drag = PanelDrag(self)  # flèches dans la vue 3D, pas de poignées (ADR 0021)
        if self._session is not None:
            self._recompute()

    # --- Construction du formulaire -------------------------------------------------------

    def _make_profile_group(self, obj: DocumentObject) -> tuple[Any, Any]:
        """Groupe de l'épaisseur du profil : champ d'unité lié à ``ProfileThickness``, visible
        seulement pour une pièce tirée d'une esquisse. Rend le groupe et son champ."""
        group = QtGui.QGroupBox(translated(_PROFILE))
        group.setObjectName("profileGroup")
        group.setToolTip(translated(_PROFILE_TIP))
        field = quantity_field("profileThicknessEdit", MIN_DIMENSION_MM)
        field.setKeyboardTracking(True)  # chaque frappe s'affiche en direct
        QtGui.QVBoxLayout(group).addWidget(field)
        self._bindings.append(bind_field(field, obj, "ProfileThickness", MIN_DIMENSION_MM))
        group.setVisible(is_profile(obj))
        return group, field

    def _make_edit_button(self, obj: DocumentObject) -> Any:
        """Bouton « Modifier le dessin » ; inactif pour une forme sans éditeur propre."""
        button = QtGui.QPushButton(translated(_EDIT_DRAWING))
        button.setObjectName("editDrawingButton")
        button.setAutoDefault(False)
        enabled = drawing_target(obj) is not None
        button.setEnabled(enabled)
        button.setToolTip(translated(_EDIT_DRAWING_TIP if enabled else _NO_DRAWING_EDITOR))
        return button

    def _arrange_form(self) -> None:
        """Ordre des groupes du formulaire de la pièce de bois, adapté à la pièce en bois : cotes
        en lecture seule sous le titre « Encombrement », outils d'épaisseur masqués."""
        form = self.form
        form.dimensionsGroup.setTitle(translated(_ENVELOPE))
        form.dimensionsGroup.setToolTip(translated(_ENVELOPE_TIP))
        for name in _DIMENSION_WIDGETS:
            field = getattr(form, name)
            field.setProperty("minimum", 0.0)
            field.setProperty("maximum", MAX_DIMENSION_MM)
            field.setProperty("readOnly", True)
        for widget in (form.standardThicknessButton, form.thicknessWarning, form.unlockHost):
            widget.setVisible(False)
        layout = form.layout()
        ordered = (
            form.identificationGroup,
            form.newerVersionNotice,
            form.materialGroup,
            self._frame.group,
            form.dimensionsGroup,
            form.rotationGroup,
            form.allowancesToggle,
            form.allowancesBox,
            self._profile_group,
            self._edit_button,
        )
        for widget in ordered:
            layout.removeWidget(widget)
            layout.addWidget(widget)

    def _connect_signals(self) -> None:
        connect_rotations(self.form, self._on_rotate)
        self._material.connect_signals()
        self._allowances.connect_signals()
        self._frame.connect_signals()
        connect(self._profile, "valueChanged(double)", self._on_profile_changed)
        connect(self._edit_button, "clicked()", self._on_edit_drawing)

    # --- Affichage ------------------------------------------------------------------------

    def _show_values(self) -> None:
        """Valeurs de l'objet dans les champs : repère, fil, encombrement (relu à chaque
        recalcul), épaisseur du profil, surcotes."""
        self._material.show()
        with self._guard:
            for widget, name in zip(_DIMENSION_WIDGETS, DIMENSION_NAMES, strict=True):
                getattr(self.form, widget).setProperty("rawValue", getattr(self.obj, name).Value)
            self._profile.setProperty("rawValue", self.obj.ProfileThickness.Value)
        self._allowances.show()

    def _on_material(self) -> None:
        """Nouveau matériau : le fil et les surcotes suivent, aperçu recalculé."""
        self._show_values()
        self._recompute()

    def _recompute(self) -> None:
        """Pièce reposée par l'accrochage (conversion contre des éléments), aperçu (la pièce, ses
        assemblages et sa pièce usinée), cotes relues et repère redessiné."""
        if self._session is not None:
            snap_part(self.obj, self._session)
        self.preview()
        self._show_values()
        self._snap.show()
        self._axes.refresh()

    # --- Saisies --------------------------------------------------------------------------

    def after_drag(self) -> None:
        """Pièce déplacée à la souris : l'accrochage de la conversion ne la repose plus (il la
        ramènerait là où elle a été posée) et le repère dessiné suit la pièce."""
        self._session = None
        self._show_values()
        self._axes.refresh()

    def _on_frame_changed(self) -> None:
        """Repère changé : la pièce n'est plus posée par l'accrochage (il la déplacerait), aperçu
        recalculé."""
        self._session = None
        self._recompute()

    def _on_profile_changed(self, value: float) -> None:
        if self._guard.active or has_expression(self.obj, "ProfileThickness"):
            return
        if self.obj.ProfileThickness.Value != value:
            self.obj.ProfileThickness = value
            self._recompute()

    def _on_rotate(self, turn: Turn) -> None:
        """Quart de tour de la pièce autour de l'axe X, Y ou Z du document : accrochée si elle a
        été posée contre des éléments, sinon sur place."""
        if rotate_checked(self.obj, turn, self._session, joint_choice.choose):
            self._recompute()

    def _on_edit_drawing(self) -> None:
        """« Modifier le dessin » : le panneau est validé puis l'édition s'ouvre, hors du signal du
        bouton (la fermeture détruit le formulaire)."""
        QtCore.QTimer.singleShot(0, self._validate_and_edit_drawing)

    def _validate_and_edit_drawing(self) -> None:
        if self.closed:
            return
        target = drawing_target(self.obj)
        if target is None:
            return
        names = (self.doc.Name, target.Name)
        self.accept()
        open_drawing_editor(*names)

    def _finish(self, *, abort: bool) -> None:
        """Repère retiré de la vue, puis fermeture (voir :class:`.TransactionTaskPanel`)."""
        self._axes.remove()
        super()._finish(abort=abort)


def start_editing(obj: DocumentObject) -> bool:
    """Ouvre le panneau sur une pièce en bois existante, dans la transaction « Modifier une pièce
    en bois ». Faux si un autre panneau de tâche est déjà ouvert."""
    build = partial(_build, obj, creating=False)
    return base.start_editing(obj.Document, EDIT_TRANSACTION, build, obj)


def show_panel(obj: DocumentObject, *, creating: bool, session: SnapSession | None = None) -> None:
    """Construit puis affiche le panneau, dans la transaction déjà ouverte (voir
    :func:`base.show_panel`) ; ``session`` : accrochage de la pièce convertie."""
    base.show_panel(partial(_build, obj, creating=creating, session=session))


def _build(
    obj: DocumentObject, *, creating: bool, session: SnapSession | None = None
) -> ShapedPartTaskPanel:
    """Panneau de ``obj`` (classe lue à l'appel : remplaçable par les vérifications)."""
    return ShapedPartTaskPanel(obj, creating=creating, session=session)
