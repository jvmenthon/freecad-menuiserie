# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture sûre d'un fichier de matériaux : descripteur unique, taille bornée, JSON strict."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Final

from freecad.menuiserie.core.materials._entry import json_object
from freecad.menuiserie.core.materials._issues import LibraryFormatError, LibraryIssue, file_error
from freecad.menuiserie.core.materials._messages import (
    FILE_INVALID_JSON,
    FILE_NON_FINITE,
    FILE_NOT_REGULAR,
    FILE_NOT_UTF8,
    FILE_TOO_DEEP,
    FILE_TOO_LARGE,
    FILE_UNREADABLE,
)
from freecad.menuiserie.core.materials._model import Material
from freecad.menuiserie.core.materials._parser import parse_materials

MAX_FILE_BYTES: Final = 1_048_576
# Ouverture sans blocage (tube nommé) ni héritage par un processus fils ; binaire sous Windows.
_OPEN_FLAGS: Final = (
    os.O_RDONLY
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_BINARY", 0)
)


def _unreadable(source: str, error: OSError) -> LibraryFormatError:
    return file_error(source, FILE_UNREADABLE, error=error.strerror or type(error).__name__)


def _read_at_most(descriptor: int, limit: int) -> bytes:
    """Lit au plus ``limit`` octets du descripteur (jusqu'à la fin du fichier)."""
    chunks: list[bytes] = []
    remaining = limit
    while remaining > 0:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_regular_file(descriptor: int, source: str) -> bytes:
    """Vérifie le type et la taille du fichier ouvert, puis le lit (lecture bornée)."""
    status = os.fstat(descriptor)
    if not stat.S_ISREG(status.st_mode):
        raise file_error(source, FILE_NOT_REGULAR)
    limit = str(MAX_FILE_BYTES)
    if status.st_size > MAX_FILE_BYTES:
        raise file_error(source, FILE_TOO_LARGE, size=str(status.st_size), max=limit)
    content = _read_at_most(descriptor, MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise file_error(source, FILE_TOO_LARGE, size=f"> {limit}", max=limit)
    return content


def _read_bytes(path: Path, source: str) -> bytes:
    """Lit au plus ``MAX_FILE_BYTES`` octets ; ``FileNotFoundError`` si le fichier est absent.

    Type et taille sont vérifiés sur le descripteur ouvert (``fstat``), puis la lecture se fait
    sur ce même descripteur : le fichier ne peut pas être remplacé entre contrôle et lecture.
    """
    try:
        descriptor = os.open(path, _OPEN_FLAGS)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise _unreadable(source, error) from error
    except ValueError as error:  # octet nul dans le chemin
        raise file_error(source, FILE_UNREADABLE, error=str(error)) from error
    try:
        return _read_regular_file(descriptor, source)
    except OSError as error:
        raise _unreadable(source, error) from error
    finally:
        os.close(descriptor)


class _NonFiniteConstantError(ValueError):
    """Constante JSON ``NaN``, ``Infinity`` ou ``-Infinity`` rencontrée."""

    def __init__(self, constant: str) -> None:
        super().__init__(constant)
        self.constant = constant


def _reject_constant(constant: str) -> object:
    raise _NonFiniteConstantError(constant)


def _decode_json(content: bytes, source: str) -> object:
    """Décode du JSON UTF-8 strict (BOM initial toléré) ; :class:`LibraryFormatError` sinon.

    Les objets à clés en double sont marqués (:class:`_JsonObject`) pour être signalés.
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise file_error(source, FILE_NOT_UTF8) from error
    try:
        return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=json_object)
    except _NonFiniteConstantError as error:
        raise file_error(source, FILE_NON_FINITE, value=error.constant) from error
    except ValueError as error:
        raise file_error(source, FILE_INVALID_JSON, error=str(error)) from error
    except RecursionError as error:
        raise file_error(source, FILE_TOO_DEEP) from error


def read_materials_file(
    path: Path, source: str | None = None
) -> tuple[list[Material], list[LibraryIssue]]:
    """Lit et valide un fichier de matériaux ; un fichier absent renvoie ``([], [])``.

    La taille est vérifiée avant lecture et seul ``json.loads`` est utilisé : aucune autre
    forme de désérialisation. ``source`` (chemin du fichier par défaut) est cité dans les
    anomalies.
    """
    label = str(path) if source is None else source
    result = read_existing_file(path, label)
    return ([], []) if result is None else result


def read_existing_file(path: Path, label: str) -> tuple[list[Material], list[LibraryIssue]] | None:
    """Comme :func:`read_materials_file`, mais ``None`` si le fichier est absent."""
    try:
        data = _decode_json(_read_bytes(path, label), label)
    except FileNotFoundError:
        return None
    except LibraryFormatError as error:
        return [], [error.issue]
    return parse_materials(data, label, path.parent)
