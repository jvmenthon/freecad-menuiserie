# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu de la pièce en création : transparence posée le temps du panneau (J6c, ADR 0011).

L'aperçu est l'objet réel, dans la transaction du panneau ; seul son affichage change.
:class:`PreviewStyle` mémorise la transparence d'origine et la rétablit avant la validation, si
bien que rien de l'aperçu n'est enregistré. Texture et couleur du matériau ne sont pas touchées
(``show_diffuse`` conserve l'alpha).

:class:`PartsPreview` fait de même pour les pièces d'un assemblage tant que son panneau est
ouvert : les objets affichés des pièces sont transparents (l'usinage se voit à l'intérieur) et
retrouvent leur transparence d'origine à la fermeture. Seules des propriétés du ViewObject sont
écrites : le document n'enregistre ni entrée d'annulation ni modification. Une teinte
(``tint``) peut s'ajouter à la transparence : la couleur diffuse est alors changée le temps du
panneau (pièces d'origine d'une répétition), puis l'apparence d'origine est rétablie.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Final

PREVIEW_TRANSPARENCY: Final = 60  # pour cent

ViewObject = Any
Rgb = tuple[int, int, int]


def _show_tint(vobj: ViewObject, tint: Rgb) -> None:
    """Couleur diffuse de chaque matériau d'affichage = ``tint`` (0 à 255), transparence gardée ;
    rien n'est écrit si elle est déjà affichée (même règle que ``part_appearance.show_diffuse``,
    sans dépendre de FreeCAD ici)."""
    wanted = tuple(component / 255 for component in tint)
    appearance = list(vobj.ShapeAppearance)
    if all(_rounded(m.DiffuseColor[:3]) == _rounded(wanted) for m in appearance):
        return
    for material in appearance:
        material.DiffuseColor = wanted + tuple(material.DiffuseColor)[3:]
    vobj.ShapeAppearance = appearance


def _rounded(color: tuple[float, ...]) -> tuple[int, ...]:
    return tuple(round(component * 255) for component in color)


class PreviewStyle:
    """Transparence d'aperçu de ``vobj`` (``None`` : pas d'interface, sans effet), et sa couleur
    diffuse ``tint`` si elle est donnée."""

    def __init__(self, vobj: ViewObject | None, tint: Rgb | None = None) -> None:
        self._vobj = vobj
        self._tint = tint
        self._original: int | None = None
        self._appearance: list[Any] = []
        if vobj is not None:
            self._original = int(vobj.Transparency)
            if tint is not None:
                self._appearance = list(vobj.ShapeAppearance)
            self.ensure()

    def ensure(self) -> None:
        """Transparence (et teinte) reposées si elles ont été perdues, par exemple par une
        transaction abandonnée ; rien n'est écrit si elles sont déjà affichées."""
        vobj = self._vobj
        if vobj is None:
            return
        if int(vobj.Transparency) != PREVIEW_TRANSPARENCY:
            vobj.Transparency = PREVIEW_TRANSPARENCY
        if self._tint is not None:
            _show_tint(vobj, self._tint)

    def restore(self) -> None:
        """Remet la transparence (et l'apparence) d'origine ; sans effet si l'objet a disparu ou
        déjà rétabli."""
        vobj, original, appearance = self._vobj, self._original, self._appearance
        self._vobj = self._original = None
        self._appearance = []
        if vobj is None or original is None:
            return
        try:
            if appearance:
                vobj.ShapeAppearance = appearance
            vobj.Transparency = original
        except (ReferenceError, RuntimeError, TypeError):
            return  # objet supprimé (annulation, document fermé) : plus rien à rétablir


class PartsPreview:
    """Transparence d'aperçu des objets affichés de plusieurs pièces (``shown`` les donne à
    chaque appel), appliquée à l'ouverture et à chaque :meth:`sync`, rétablie par
    :meth:`restore`. ``alive(obj)`` dit si un objet existe encore dans son document : la
    transparence n'est jamais rétablie sur un objet supprimé."""

    def __init__(
        self,
        shown: Callable[[], Iterable[Any]],
        alive: Callable[[Any], bool],
        tint: Rgb | None = None,
    ) -> None:
        self._shown = shown
        self._alive = alive
        self._tint = tint
        self._styles: dict[str, tuple[Any, PreviewStyle]] = {}
        self._released = False
        self.sync()

    def sync(self) -> None:
        """Objets affichés relus : transparence posée sur ceux qui le deviennent (pièce usinée
        créée par un recalcul), rétablie sur ceux qui ne le sont plus. Sans effet une fois
        :meth:`restore` appelée."""
        if self._released:
            return
        current = self._current()
        for name, (obj, style) in list(self._styles.items()):
            if not self._alive(obj):
                del self._styles[name]  # supprimé : rien à rétablir
            elif name not in current:
                del self._styles[name]
                style.restore()
            else:
                style.ensure()
        for name, obj in current.items():
            if name not in self._styles:
                vobj = getattr(obj, "ViewObject", None)
                self._styles[name] = (obj, PreviewStyle(vobj, self._tint))

    def restore(self) -> None:
        """Transparence d'origine rétablie sur les objets qui existent encore ; idempotent,
        et l'aperçu ne se rétablit plus ensuite."""
        self._released = True
        styles, self._styles = self._styles, {}
        for obj, style in styles.values():
            try:
                if self._alive(obj):
                    style.restore()
            except (ReferenceError, RuntimeError, TypeError):
                continue  # objet disparu pendant la fermeture : rien à rétablir

    def _current(self) -> dict[str, Any]:
        """Objets affichés qui existent, par nom ; aucun si les pièces sont illisibles."""
        try:
            return {obj.Name: obj for obj in self._shown() if self._alive(obj)}
        except (ReferenceError, RuntimeError, TypeError):
            return {}
