# SPDX-License-Identifier: LGPL-2.1-or-later
"""Page de préférences construite d'après un catalogue de réglages (ADR 0069, maquette B).

Qt par la couche ``PySide`` de FreeCAD, sans texte propre à un atelier : libellés, infobulles,
groupes et unités viennent du catalogue, traduits par la fonction injectée. Une seule zone qui
défile, un groupe repliable par groupe du catalogue, recherche, case « Afficher les réglages
avancés », « Rétablir » par ligne et « Rétablir tout ». Les valeurs ne sont écrites qu'à
:meth:`SettingsPage.saveSettings` (OK, Appliquer de FreeCAD) ; l'interface attendue d'une page de
FreeCAD est ``form``, ``saveSettings`` et ``loadSettings``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import Any, Final

from PySide import QtCore, QtGui

from . import import_model
from . import page_model as model
from .catalog import Catalog, Setting, SettingError
from .page_dialogs import plain_message
from .page_extra import ExtraLine
from .page_rows import Row, ignoring_arguments
from .store import Settings

__all__ = ["SettingsPage"]

_ARROW_OPEN: Final = QtCore.Qt.ArrowType.DownArrow
_ARROW_CLOSED: Final = QtCore.Qt.ArrowType.RightArrow
_SUMMARY_STYLE: Final = "color: gray;"


class _Group:
    """Groupe repliable : titre, résumé quand il est replié, grille des lignes."""

    def __init__(
        self,
        title: str,
        rows: list[Row],
        extras: list[ExtraLine],
        on_toggle: Callable[[_Group], None],
    ) -> None:
        self.rows = rows
        self.extras = extras
        self.frame = QtGui.QFrame()
        outer = QtGui.QVBoxLayout(self.frame)
        outer.setContentsMargins(0, 4, 0, 4)
        self.header = QtGui.QToolButton()
        self.header.setText(title)
        self.header.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setAutoRaise(True)
        font = self.header.font()
        font.setBold(True)
        self.header.setFont(font)
        self.summary = QtGui.QLabel()
        self.summary.setStyleSheet(_SUMMARY_STYLE)
        top = QtGui.QHBoxLayout()
        top.addWidget(self.header)
        top.addWidget(self.summary)
        top.addStretch(1)
        outer.addLayout(top)
        self.body = QtGui.QWidget()
        grid = QtGui.QGridLayout(self.body)
        grid.setColumnStretch(1, 1)
        lines: list[Row | ExtraLine] = [*rows, *extras]
        for index, row in enumerate(lines):
            for column, widget in enumerate(row.widgets()):
                if widget is not None:
                    grid.addWidget(widget, index, column)
        outer.addWidget(self.body)
        self.expanded = True
        self.header.clicked.connect(ignoring_arguments(partial(on_toggle, self)))
        self.show_state()

    def show_state(self) -> None:
        """Flèche, corps et résumé d'après l'état déplié ou replié."""
        self.header.setArrowType(_ARROW_OPEN if self.expanded else _ARROW_CLOSED)
        self.body.setVisible(self.expanded)
        self.summary.setVisible(not self.expanded)


class SettingsPage:
    """Page « réglages » d'un atelier : ``form`` à donner à FreeCAD, valeurs lues et écrites par
    ``loadSettings`` et ``saveSettings``.

    ``translate`` traduit tous les textes (catalogue et page) ; ``choices`` (clé → couples
    valeur, libellé traduit) donne des listes déroulantes à des réglages, par exemple les
    matériaux d'une bibliothèque pour un texte. ``extras`` ajoute des lignes propres à l'atelier
    (:class:`~.page_model.ExtraRow`), dans un groupe du catalogue ou dans un groupe nouveau.
    ``notify`` reçoit le message d'un enregistrement refusé (par défaut, une boîte de message).
    """

    def __init__(
        self,
        catalog: Catalog,
        settings: Settings,
        *,
        translate: model.Translate = model.identity,
        choices: model.Choices | None = None,
        extras: Sequence[model.ExtraRow] = (),
        notify: Callable[[str], None] | None = None,
    ) -> None:
        self.catalog = catalog
        self.settings = settings
        self._translate = translate
        self._choices = choices or {}
        self._notify = notify or self._warn
        self._extras = [ExtraLine(extra, translate) for extra in extras]
        self._rows: dict[str, Row] = {}
        self._groups: dict[str, _Group] = {}
        self.form = QtGui.QWidget()
        self.form.setObjectName("SettingsPage")
        layout = QtGui.QVBoxLayout(self.form)
        layout.addLayout(self._top_bar())
        layout.addWidget(self._scroll_area(), 1)
        layout.addLayout(self._bottom_bar())
        self.loadSettings()

    # --- Construction ---------------------------------------------------------------------

    def _top_bar(self) -> QtGui.QHBoxLayout:
        bar = QtGui.QHBoxLayout()
        self.search = QtGui.QLineEdit()
        self.search.setObjectName("search")
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText(self._translate(model.SEARCH))
        self.advanced = QtGui.QCheckBox(self._translate(model.ADVANCED))
        self.advanced.setObjectName("advanced")
        self.search.textChanged.connect(ignoring_arguments(self._refresh))
        self.advanced.toggled.connect(ignoring_arguments(self._refresh))
        bar.addWidget(self.search, 1)
        bar.addWidget(self.advanced)
        return bar

    def _scroll_area(self) -> QtGui.QScrollArea:
        area = QtGui.QScrollArea()
        area.setWidgetResizable(True)
        content = QtGui.QWidget()
        column = QtGui.QVBoxLayout(content)
        for title in model.group_order(self.catalog.groups(), [x.extra for x in self._extras]):
            rows = [self._row(s) for s in self.catalog if s.group == title]
            extras = [x for x in self._extras if x.extra.group == title]
            group = _Group(self._translate(title), rows, extras, self._toggle)
            self._groups[title] = group
            column.addWidget(group.frame)
        self.nothing = QtGui.QLabel(self._translate(model.NOTHING_FOUND))
        self.nothing.setVisible(False)
        column.addWidget(self.nothing)
        column.addStretch(1)
        area.setWidget(content)
        return area

    def _row(self, setting: Setting) -> Row:
        row = Row(setting, self._translate, self._choices.get(setting.key, ()), self._refresh)
        self._rows[setting.key] = row
        return row

    def _bottom_bar(self) -> QtGui.QHBoxLayout:
        bar = QtGui.QHBoxLayout()
        button = QtGui.QPushButton(self._translate(model.RESET_ALL))
        button.setObjectName("resetAll")
        button.setToolTip(self._translate(model.RESET_ALL_TIP))
        button.clicked.connect(ignoring_arguments(self.reset_all))
        bar.addWidget(button)
        bar.addStretch(1)
        return bar

    # --- Affichage ------------------------------------------------------------------------

    def _toggle(self, group: _Group) -> None:
        group.expanded = not group.expanded
        group.show_state()

    def _values(self) -> dict[str, Any]:
        return {key: row.value() for key, row in self._rows.items()}

    def _refresh(self) -> None:
        """Lignes filtrées, groupes sans ligne masqués, résumés des groupes à jour."""
        query, advanced = self.search.text(), self.advanced.isChecked()
        shown = set(model.shown_keys(self.catalog, query, advanced, self._translate))
        eligible = set(model.shown_keys(self.catalog, "", advanced, self._translate))
        values = self._values()
        for key, row in self._rows.items():
            for widget in row.all_widgets():
                widget.setVisible(key in shown)
        anything = bool(shown)
        for group in self._groups.values():
            found = self._refresh_group(group, shown, eligible, values)
            anything = anything or found
        self.nothing.setVisible(not anything)

    def _refresh_group(
        self, group: _Group, shown: set[str], eligible: set[str], values: Mapping[str, Any]
    ) -> bool:
        """Résumé et visibilité d'un groupe ; vrai s'il a une ligne trouvée."""
        query = self.search.text()
        keys = [row.setting.key for row in group.rows]
        mine = [key for key in keys if key in eligible]
        modified = model.count_modified(self.catalog, values, mine)
        total = len(mine) + len(group.extras)
        group.summary.setText(model.group_summary(total, modified, self._translate))
        found_keys = [key for key in keys if key in shown]
        found_extras = [line for line in group.extras if line.matches(query)]
        for line in group.extras:
            for widget in line.all_widgets():
                widget.setVisible(line in found_extras)
        found = bool(found_keys or found_extras)
        group.frame.setVisible(found)
        if query.strip() and found:
            group.expanded = True  # une recherche ouvre les groupes où elle trouve
            group.show_state()
        return found

    # --- Interface d'une page de préférences de FreeCAD -----------------------------------

    def loadSettings(self) -> None:
        """Affiche les valeurs enregistrées (défaut si absente ou invalide)."""
        for key, row in self._rows.items():
            row.load(self.settings.value(key), self.settings.remembers_last(key))
        for line in self._extras:
            line.extra.load()
        self._refresh()

    def saveSettings(self) -> None:
        """Écrit les lignes modifiées : une valeur par défaut efface le paramètre. Une ligne non
        touchée n'est pas réécrite ; une valeur refusée par le catalogue n'est pas écrite et la
        ligne retrouve sa valeur enregistrée."""
        refused = self._refuse_inconsistent()
        for key, row in self._rows.items():
            if not row.dirty:
                continue
            if key in refused:
                row.load(self.settings.value(key), self.settings.remembers_last(key))
                continue
            try:
                self._save(key, row)
            except SettingError:
                row.load(self.settings.value(key), self.settings.remembers_last(key))
        for line in self._extras:
            line.extra.save()
        self._refresh()

    def _refuse_inconsistent(self) -> set[str]:
        """Clés des réglages touchés dont les valeurs, ensemble, violent une relation du
        catalogue ; elles ne sont pas écrites et l'utilisateur en est averti."""
        keys: set[str] = set()
        for relation in self.catalog.violations(self._values()):
            keys.update(key for key in relation.keys if self._rows[key].dirty)
        if keys:
            names = ", ".join(self._translate(self.catalog.get(key).label) for key in sorted(keys))
            self._notify(model.format_text(self._translate(model.INCONSISTENT), names=names))
        return keys

    def _warn(self, text: str) -> None:
        title = self._translate(import_model.EXCHANGE_LABEL)
        plain_message(self.form, title, text, error=True)

    def _save(self, key: str, row: Row) -> None:
        value = row.setting.check(row.value())
        if value == row.setting.default:
            self.settings.reset(key)  # efface aussi « Dernier utilisé » : reposé ci-dessous
        else:
            self.settings.set(key, value)
        if row.remember is not None:
            self.settings.set_remember_last(key, row.remembers())
        row.dirty = False

    def reset_all(self) -> None:
        """Toutes les lignes à leur valeur par défaut (écrit à l'enregistrement de la page)."""
        for row in self._rows.values():
            row.reset()

    def has_pending(self) -> bool:
        """Vrai si la page a des modifications pas encore écrites (lignes touchées ou reprises
        d'un import, lignes supplémentaires)."""
        return any(row.dirty for row in self._rows.values()) or any(
            line.extra.pending() for line in self._extras
        )

    def set_pending(self, values: Mapping[str, Any]) -> None:
        """Reprend ``values`` (clés du fichier d'échange : ``<clé>`` et ``<clé>RememberLast``)
        dans les champs, sans rien écrire : les lignes touchées apparaissent modifiées et sont
        écrites avec les autres à :meth:`saveSettings`. Les clés inconnues sont ignorées."""
        for key, row in self._rows.items():
            merged = model.merge_pending(key, values, row.value(), row.remembers())
            if merged is not None:
                row.load(merged[0], merged[1], dirty=True)
        self._refresh()
