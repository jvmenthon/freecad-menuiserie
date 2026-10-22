# SPDX-License-Identifier: LGPL-2.1-or-later
"""Libellés qui dépendent de celui d'une pièce brute : sa pièce usinée et ses assemblages, et le
libellé unique d'une pièce copiée (J6, ADR 0011)."""

from __future__ import annotations

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joint_names import sync_joint_labels
from freecad.menuiserie.features.part_names import (
    imported_label_off_mark,
    label_of_mark,
    unique_label_after_copy,
)

__all__ = ["make_label_unique", "sync_dependent_labels"]


def sync_dependent_labels(blank: DocumentObject) -> None:
    """Libellés de la pièce usinée et des assemblages de la brute ``blank`` d'après le sien."""
    from freecad.menuiserie.features.machined_part import sync_machined_label

    sync_machined_label(blank)
    sync_joint_labels(blank)


def make_label_unique(blank: DocumentObject) -> None:
    """Brute restaurée avec le libellé d'un autre objet (copier-coller, Std Dupliquer, fusion de
    documents) : libellé rendu unique (« M1 (2) »), puis ceux de sa pièce usinée et de ses
    assemblages. Une pièce fusionnée que FreeCAD a renommée à sa façon (« M001 ») reprend un
    libellé tiré de son repère. Le repère est inchangé ; sans effet si le libellé est déjà
    unique et conforme."""
    label = unique_label_after_copy(blank)
    if label is None and imported_label_off_mark(blank):
        label = label_of_mark(blank, str(blank.Mark))  # fusion : « M001 » redevient « M1 (2) »
    if label is None:
        return
    with blank.Proxy.synchronizing():
        blank.Label = label
    sync_dependent_labels(blank)
