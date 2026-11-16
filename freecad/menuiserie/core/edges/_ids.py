# SPDX-License-Identifier: LGPL-2.1-or-later
"""Les 12 arêtes d'une pièce, désignées par leurs deux faces dans le repère local (ADR 0029).

Module privé : la façade ``core.edges`` ré-exporte l'API publique. Une arête a un code
(``"Z+Y-"``) et un nom français (``"dessus-avant"``) ; les faces sont toujours écrites dans
l'ordre Z, Y, X. Le code est la seule référence conservée dans le document : jamais de numéro
d'arête de la forme.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Axis
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.text import quoted_value

__all__ = [
    "FACE_CODES",
    "FACE_NAMES",
    "EdgeError",
    "EdgeId",
    "all_edges",
    "edge_code",
    "face_code",
    "face_edges",
    "loop_edges",
    "parse_edge",
    "parse_face",
]

UNKNOWN_EDGE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Arête inconnue : {text}.")
UNKNOWN_FACE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Face inconnue : {text}.")

# Face (axe signé) → nom français : « dessus » = Z+, « avant » = Y-, « gauche » = X-.
FACE_NAMES: Final = {
    Axis.Z_POS: "dessus",
    Axis.Z_NEG: "dessous",
    Axis.Y_NEG: "avant",
    Axis.Y_POS: "arrière",
    Axis.X_NEG: "gauche",
    Axis.X_POS: "droite",
}
_FACE_BY_NAME: Final = {name: face for face, name in FACE_NAMES.items()}
_FACE_ORDER: Final = (2, 1, 0)  # indices d'axe dans l'ordre d'écriture : Z, Y, X
# Les six faces : dessus, dessous, avant, arrière, gauche, droite.
FACE_CODES: Final = ("Z+", "Z-", "Y-", "Y+", "X-", "X+")


class EdgeError(TemplatedError):
    """Arête, face ou cote de profil refusée ; gabarit français traduisible rempli."""


def face_code(face: Axis) -> str:
    """Code d'une face : ``"Z+"``, ``"Y-"``."""
    return face.value[1] + face.value[0]


@dataclass(frozen=True)
class EdgeId:
    """Arête entre deux faces perpendiculaires, écrites dans l'ordre Z, Y, X (``ValueError``
    sinon). La troisième direction est celle de l'arête (:attr:`along`)."""

    first: Axis
    second: Axis

    def __post_init__(self) -> None:
        if self.first.index == self.second.index:
            raise ValueError("arête : deux faces parallèles")
        if _FACE_ORDER.index(self.first.index) > _FACE_ORDER.index(self.second.index):
            raise ValueError("arête : faces dans l'ordre Z, Y, X attendu")

    @classmethod
    def between(cls, one: Axis, other: Axis) -> EdgeId:
        """Arête entre deux faces, dans n'importe quel ordre."""
        if _FACE_ORDER.index(one.index) <= _FACE_ORDER.index(other.index):
            return cls(one, other)
        return cls(other, one)

    @property
    def along(self) -> int:
        """Indice de l'axe (0, 1, 2) le long duquel court l'arête."""
        return 3 - self.first.index - self.second.index

    @property
    def code(self) -> str:
        """Code stable, par exemple ``"Z+Y-"``."""
        return face_code(self.first) + face_code(self.second)

    @property
    def name(self) -> str:
        """Nom français, par exemple ``"dessus-avant"``."""
        return f"{FACE_NAMES[self.first]}-{FACE_NAMES[self.second]}"


def edge_code(edge: EdgeId) -> str:
    """Code de l'arête : ``edge_code(parse_edge(code)) == code``."""
    return edge.code


def _face_of_code(text: str) -> Axis | None:
    if len(text) == 2 and text[0] in "XYZ" and text[1] in "+-":
        return Axis(text[1] + text[0])
    return None


def parse_face(text: str) -> Axis:
    """Face désignée par son code (``"Z+"``) ou son nom (``"dessus"``) ; ``EdgeError`` sinon."""
    face = _face_of_code(text) or _FACE_BY_NAME.get(text)
    if face is None:
        raise EdgeError(UNKNOWN_FACE, {"text": quoted_value(text)})
    return face


def _faces_of(text: str) -> tuple[Axis | None, Axis | None]:
    if len(text) == 4:
        return _face_of_code(text[:2]), _face_of_code(text[2:])
    parts = text.split("-")
    if len(parts) == 2:
        return _FACE_BY_NAME.get(parts[0]), _FACE_BY_NAME.get(parts[1])
    return None, None


def parse_edge(text: str) -> EdgeId:
    """Arête désignée par son code (``"Z+Y-"``) ou son nom (``"dessus-avant"``) ; ``EdgeError``
    pour toute autre chaîne ou pour des faces qui ne sont pas dans l'ordre canonique."""
    first, second = _faces_of(text) if isinstance(text, str) else (None, None)
    if first is not None and second is not None:
        try:
            return EdgeId(first, second)
        except ValueError:
            pass
    raise EdgeError(UNKNOWN_EDGE, {"text": quoted_value(text)})


def face_edges(face: Axis) -> tuple[EdgeId, ...]:
    """Les 4 arêtes d'une face."""
    others = [axis for axis in Axis if axis.index != face.index]
    return tuple(EdgeId.between(face, other) for other in others)


def all_edges() -> tuple[EdgeId, ...]:
    """Les 12 arêtes, dans un ordre fixe (dessus, dessous, puis les quatre montants)."""
    seen: dict[str, EdgeId] = {}
    for face in (Axis.Z_POS, Axis.Z_NEG, Axis.Y_NEG, Axis.Y_POS):
        for edge in face_edges(face):
            seen.setdefault(edge.code, edge)
    return tuple(seen.values())


def loop_edges(face: str) -> tuple[EdgeId, ...]:
    """Les 4 arêtes du pourtour de la face désignée par son code ou son nom
    (``loop_edges("Z+")`` ou ``loop_edges("dessus")`` : le dessus)."""
    return face_edges(parse_face(face))
