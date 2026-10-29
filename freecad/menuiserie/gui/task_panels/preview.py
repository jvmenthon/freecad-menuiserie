# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu de la pièce en création : transparence posée le temps du panneau (J6c, ADR 0011).

L'aperçu est l'objet réel, dans la transaction du panneau ; seul son affichage change.
:class:`PreviewStyle` mémorise la transparence d'origine et la rétablit avant la validation, si
bien que rien de l'aperçu n'est enregistré. Texture et couleur du matériau ne sont pas touchées
(``show_diffuse`` conserve l'alpha).

:class:`PartsPreview` fait de même pour les pièces d'un assemblage tant que son panneau est
ouvert : les objets affichés des pièces sont transparents (l'usinage se voit à l'intérieur) et
retrouvent leur transparence d'origine à la fermeture. Seules des propriétés du ViewObject sont
écrites : le document n'enregistre ni entrée d'annulation ni modification.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Final

PREVIEW_TRANSPARENCY: Final = 60  # pour cent

ViewObject = Any


class PreviewStyle:
    """Transparence d'aperçu de ``vobj`` (``None`` : pas d'interface, sans effet)."""

    def __init__(self, vobj: ViewObject | None) -> None:
        self._vobj = vobj
        self._original: int | None = None
        if vobj is not None:
            self._original = int(vobj.Transparency)
            vobj.Transparency = PREVIEW_TRANSPARENCY

    def restore(self) -> None:
        """Remet la transparence d'origine ; sans effet si l'objet a disparu ou déjà rétabli."""
        vobj, original = self._vobj, self._original
        self._vobj = self._original = None
        if vobj is None or original is None:
            return
        try:
            vobj.Transparency = original
        except (ReferenceError, RuntimeError):
            return  # objet supprimé (annulation, document fermé) : plus rien à rétablir


class PartsPreview:
    """Transparence d'aperçu des objets affichés de plusieurs pièces (``shown`` les donne à
    chaque appel), appliquée à l'ouverture et à chaque :meth:`sync`, rétablie par
    :meth:`restore`. ``alive(obj)`` dit si un objet existe encore dans son document : la
    transparence n'est jamais rétablie sur un objet supprimé."""

    def __init__(self, shown: Callable[[], Iterable[Any]], alive: Callable[[Any], bool]) -> None:
        self._shown = shown
        self._alive = alive
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
        for name, obj in current.items():
            if name not in self._styles:
                self._styles[name] = (obj, PreviewStyle(getattr(obj, "ViewObject", None)))

    def restore(self) -> None:
        """Transparence d'origine rétablie sur les objets qui existent encore ; idempotent,
        et l'aperçu ne se rétablit plus ensuite."""
        self._released = True
        styles, self._styles = self._styles, {}
        for obj, style in styles.values():
            if self._alive(obj):
                style.restore()

    def _current(self) -> dict[str, Any]:
        """Objets affichés qui existent, par nom ; aucun si les pièces sont illisibles."""
        try:
            return {obj.Name: obj for obj in self._shown() if self._alive(obj)}
        except (ReferenceError, RuntimeError):
            return {}
