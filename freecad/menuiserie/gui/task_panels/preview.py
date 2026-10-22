# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu de la pièce en création : transparence posée le temps du panneau (J6c, ADR 0011).

L'aperçu est l'objet réel, dans la transaction du panneau ; seul son affichage change.
:class:`PreviewStyle` mémorise la transparence d'origine et la rétablit avant la validation, si
bien que rien de l'aperçu n'est enregistré. Texture et couleur du matériau ne sont pas touchées
(``show_diffuse`` conserve l'alpha).
"""

from __future__ import annotations

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
