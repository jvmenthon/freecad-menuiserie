# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export CSV et PDF de la liste de débit (J2c, S5, ADR 0012 ; PDF : J2g, critère P2).

Le texte vient de :func:`freecad.menuiserie.core.cutlist.to_csv` ; ce module valide le chemin
choisi par l'utilisateur (extension ``.csv`` ou ``.pdf``, dossier existant, ni dossier ni fichier
protégé) et écrit de façon atomique : fichier temporaire du même dossier, puis remplacement. Tout
refus est une ``ValueError`` au message traduit ; le document n'est jamais modifié. Le PDF lui-même
est dessiné par ``gui/cutlist_pdf.py`` (Qt exige l'interface) ; ce module en prépare le HTML
(:func:`pdf_html`) et fournit l'écriture atomique (:func:`replace_atomically`).
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Final

from freecad.menuiserie.core.cutlist import (
    INTERNATIONAL_CSV,
    CsvDialect,
    CutList,
    to_csv,
    to_html,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import escaped_text
from freecad.menuiserie.features.cutlist_sheet import DATE_FORMAT, TITLE, scope_text
from freecad.menuiserie.features.i18n import translate_text, translated

__all__ = [
    "CSV_SUFFIX",
    "PDF_SUFFIX",
    "export_csv",
    "pdf_html",
    "proposed_file_name",
    "proposed_path",
    "replace_atomically",
    "validated_path",
    "with_csv_suffix",
    "with_suffix",
]

CSV_SUFFIX: Final = ".csv"
PDF_SUFFIX: Final = ".pdf"
_FILE_MODE: Final = 0o644  # le fichier temporaire est en 0600 : mode d'un fichier ordinaire

_FILE_NAME: Final = QT_TRANSLATE_NOOP("Menuiserie", "{document} - liste de débit")
_FORBIDDEN_IN_NAME: Final = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
_NOT_CSV: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export refusé : « {path} » n'a pas l'extension .csv."
)
_NOT_PDF: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Export refusé : « {path} » n'a pas l'extension .pdf."
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


def validated_path(path: str | os.PathLike[str], suffix: str = CSV_SUFFIX) -> Path:
    """Chemin d'export accepté ; ``ValueError`` traduite s'il n'a pas l'extension ``suffix``
    (``.csv`` par défaut, ou ``.pdf``), s'il
    désigne un dossier, si son dossier n'existe pas ou n'est pas accessible en écriture, ou si le
    fichier existe sans être accessible en écriture. Rien n'est créé."""
    target = Path(path)
    if target.suffix.lower() != suffix:
        raise _refusal(_NOT_PDF if suffix == PDF_SUFFIX else _NOT_CSV, target)
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


def replace_atomically(target: Path, produce: Callable[[Path], None]) -> None:
    """Fait écrire par ``produce`` un fichier temporaire du dossier de ``target`` (créé vide et
    fermé), puis le substitue à ``target``. Le temporaire disparaît en cas d'échec : ``target``
    reste alors intact."""
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=f".{target.stem}-", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)  # fichier fermé à la sortie du bloc
    try:
        produce(temporary)
        if target.exists():
            shutil.copymode(target, temporary)
        else:
            temporary.chmod(_FILE_MODE)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _write_atomically(target: Path, text: str, dialect: CsvDialect) -> None:
    """Écrit ``text`` dans un fichier temporaire du dossier de ``target``, puis le substitue."""

    def produce(temporary: Path) -> None:
        with temporary.open("w", encoding=dialect.encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

    replace_atomically(target, produce)


def export_csv(
    cut_list: CutList, path: str | os.PathLike[str], dialect: CsvDialect = INTERNATIONAL_CSV
) -> Path:
    """Écrit ``cut_list`` en CSV dans ``path`` (dialecte international par défaut : ``,``,
    point décimal, UTF-8 avec BOM, CRLF) et renvoie le chemin. Refus : ``ValueError`` traduite
    (:func:`validated_path`, ou échec d'écriture, le fichier existant restant alors intact)."""
    target = validated_path(path)
    text = to_csv(cut_list, dialect, translate_text)
    try:
        _write_atomically(target, text, dialect)
    except OSError as error:
        params = {"path": escaped_text(str(target)), "reason": error.strerror or "?"}
        raise ValueError(translated(_WRITE_FAILED, params)) from error
    return target


def proposed_file_name(label: str, suffix: str = CSV_SUFFIX) -> str:
    """Nom de fichier proposé pour l'export : « <label> - liste de débit.csv » (ou ``.pdf``). Les
    caractères interdits dans un nom de fichier (barres, deux-points, ``* ? " < > |``, contrôles)
    du libellé du document sont remplacés par « _ » ; un libellé vide donne « Document »."""
    cleaned = _FORBIDDEN_IN_NAME.sub("_", label).strip().rstrip(".").strip()
    return translated(_FILE_NAME, {"document": cleaned or "Document"}) + suffix


def proposed_path(
    label: str, file_name: str, home: Path | None = None, suffix: str = CSV_SUFFIX
) -> Path:
    """Chemin proposé pour l'export : à côté du fichier du document (``file_name``, vide s'il
    n'est pas enregistré), sinon dans le dossier personnel (``home``, par défaut celui de
    l'utilisateur)."""
    folder = Path(file_name).parent if file_name else (home or Path.home())
    return folder / proposed_file_name(label, suffix)


def with_suffix(path: str, suffix: str) -> str:
    """``path`` complété de ``suffix`` s'il n'a aucune extension (la boîte d'enregistrement de Qt
    n'en ajoute pas) ; inchangé sinon, et validé ensuite par :func:`validated_path`."""
    return path if Path(path).suffix else path + suffix


def with_csv_suffix(path: str) -> str:
    """``path`` complété de « .csv » s'il n'a aucune extension (voir :func:`with_suffix`)."""
    return with_suffix(path, CSV_SUFFIX)


def pdf_html(
    cut_list: CutList,
    label: str,
    selection_count: int | None,
    now: datetime | None = None,
) -> str:
    """HTML de la liste de débit pour le PDF : titre « Liste de débit - <label> », date, portée
    (tout le document, ou ``selection_count`` objets) et tableaux (``core.cutlist.to_html``)."""
    title = f"{translated(TITLE)} - {label}" if label else translated(TITLE)
    stamp = (now or datetime.now()).strftime(DATE_FORMAT)
    return to_html(cut_list, translate_text, title, scope_text(selection_count), stamp)
