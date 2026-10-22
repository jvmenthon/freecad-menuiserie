# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export CSV de la liste de débit (J2c, S5, ADR 0012).

Le texte vient de :func:`freecad.menuiserie.core.cutlist.to_csv` ; ce module valide le chemin
choisi par l'utilisateur (extension ``.csv``, dossier existant, ni dossier ni fichier protégé) et
écrit de façon atomique : fichier temporaire du même dossier, puis remplacement. Tout refus est
une ``ValueError`` au message traduit ; le document n'est jamais modifié.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Final

from freecad.menuiserie.core.cutlist import FRENCH_CSV, CsvDialect, CutList, to_csv
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import escaped_text
from freecad.menuiserie.features.i18n import translate_text, translated

__all__ = ["CSV_SUFFIX", "export_csv", "validated_path"]

CSV_SUFFIX: Final = ".csv"
_FILE_MODE: Final = 0o644  # le fichier temporaire est en 0600 : mode d'un fichier ordinaire

_NOT_CSV: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export refusé : « {path} » n'a pas l'extension .csv."
)
_IS_FOLDER: Final = QT_TRANSLATE_NOOP("Menuiserie", "Export refusé : « {path} » est un dossier.")
_NO_FOLDER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export refusé : le dossier de « {path} » n'existe pas."
)
_NOT_WRITABLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export refusé : « {path} » n'est pas accessible en écriture."
)
_WRITE_FAILED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export impossible : l'écriture de « {path} » a échoué ({reason})."
)


def _refusal(template: str, path: Path) -> ValueError:
    return ValueError(translated(template, {"path": escaped_text(str(path))}))


def validated_path(path: str | os.PathLike[str]) -> Path:
    """Chemin d'export accepté ; ``ValueError`` traduite s'il n'a pas l'extension ``.csv``, s'il
    désigne un dossier, si son dossier n'existe pas ou n'est pas accessible en écriture, ou si le
    fichier existe sans être accessible en écriture. Rien n'est créé."""
    target = Path(path)
    if target.suffix.lower() != CSV_SUFFIX:
        raise _refusal(_NOT_CSV, target)
    if target.is_dir():
        raise _refusal(_IS_FOLDER, target)
    folder = target.parent
    if not folder.is_dir():
        raise _refusal(_NO_FOLDER, target)
    if not os.access(folder, os.W_OK | os.X_OK) or (
        target.exists() and not os.access(target, os.W_OK)
    ):
        raise _refusal(_NOT_WRITABLE, target)
    return target


def _write_atomically(target: Path, text: str, dialect: CsvDialect) -> None:
    """Écrit ``text`` dans un fichier temporaire du dossier de ``target``, puis le substitue."""
    with tempfile.NamedTemporaryFile(
        "w",
        encoding=dialect.encoding,
        newline="",
        dir=target.parent,
        prefix=f".{target.stem}-",
        suffix=".tmp",
        delete=False,
    ) as handle:
        try:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            Path(handle.name).unlink(missing_ok=True)
            raise
    temporary = Path(handle.name)  # fichier fermé : écrit et complet
    try:
        if target.exists():
            shutil.copymode(target, temporary)
        else:
            temporary.chmod(_FILE_MODE)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def export_csv(
    cut_list: CutList, path: str | os.PathLike[str], dialect: CsvDialect = FRENCH_CSV
) -> Path:
    """Écrit ``cut_list`` en CSV dans ``path`` (dialecte français par défaut : ``;``, virgule
    décimale, UTF-8 avec BOM, CRLF) et renvoie le chemin. Refus : ``ValueError`` traduite
    (:func:`validated_path`, ou échec d'écriture, le fichier existant restant alors intact)."""
    target = validated_path(path)
    text = to_csv(cut_list, dialect, translate_text)
    try:
        _write_atomically(target, text, dialect)
    except OSError as error:
        params = {"path": escaped_text(str(target)), "reason": error.strerror or "?"}
        raise ValueError(translated(_WRITE_FAILED, params)) from error
    return target
