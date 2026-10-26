# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit vivante : l'objet ``Menuiserie::CutList`` (J2f, ADR 0013, critères V1 à V4).

L'objet (``App::FeaturePython``, nom interne ``CutList``, sans forme) lie la feuille qu'il
réécrit (``Sheet``), les objets choisis (``Scope``, vide = tout le document) et les objets lus au
dernier calcul (``Sources``). ``Sources`` est un lien **dans le graphe de dépendances** : FreeCAD
recalcule donc la liste après les pièces, dès que l'une change. (Un lien « caché » ne crée pas
de dépendance : essayé, la liste ne suivait plus les cotes.) Une pièce ajoutée
n'est dans le graphe de personne : ``mustExecute`` compare les objets du document à ``Sources``
quand la portée est tout le document.

La feuille reste un ``Spreadsheet::Sheet`` ordinaire sans proxy (ADR 0007) : ouvert sans
l'atelier, le document garde ses valeurs. Nul ne dépend de ``CutList`` : aucun cycle possible ;
l'objet n'écrit que dans lui-même et dans sa feuille.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe ``CutListProxy``,
noms des propriétés et type ``Menuiserie::CutList`` sont écrits dans les documents.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Final

from freecad.menuiserie.core.cutlist import CutList
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import cutlist_sheet, schema
from freecad.menuiserie.features.cutlist_collect import collect_cut_list, is_source
from freecad.menuiserie.features.freecad_types import (
    HIDDEN,
    READ_ONLY,
    Document,
    DocumentObject,
    StatelessProxy,
    proxy_is,
    restoring_or_undoing,
)
from freecad.menuiserie.features.furniture_bindings import notice_messages
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.schema import PropertySpec, version_spec

__all__ = [
    "MODEL_VERSION",
    "OBJECT_NAME",
    "CutListProxy",
    "ensure_cut_list",
    "find_cut_list",
    "is_cut_list",
    "refresh",
]

OBJECT_NAME: Final = "CutList"
MODEL_VERSION: Final = 1
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Liste de débit")
DEFAULT_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Mise à jour de la liste de débit")
GROUP: Final = "Liste de débit"
_FOREIGN_SHEET: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » : la feuille liée n'est pas la feuille de liste de débit de ce document ; "
    "elle n'est pas réécrite (relancer « Liste de débit » pour en créer une).",
)
_Computed = tuple[CutList, Sequence[DocumentObject]]  # liste et objets lus pour la dresser

PROPERTIES: Final = (
    PropertySpec(
        "Sheet",
        "App::PropertyLink",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property", "Feuille de calcul que la liste de débit réécrit à chaque recalcul."
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Scope",
        "App::PropertyLinkListHidden",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Objets dont la liste est dressée (pièces, ensembles, groupes) ; vide : tout le "
            "document.",
        ),
    ),
    PropertySpec(
        "Sources",
        "App::PropertyLinkList",
        GROUP,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Objets lus au dernier calcul, pour que FreeCAD recalcule la liste après eux. Écrit "
            "par l'atelier.",
        ),
        mode=HIDDEN,
    ),
    version_spec(
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la liste de débit, utilisée pour migrer les "
            "anciens fichiers.",
        ),
        MODEL_VERSION,
    ),
)


class CutListProxy(StatelessProxy):
    """Proxy de la liste de débit vivante (sans état enregistré)."""

    TYPE: ClassVar[str] = "Menuiserie::CutList"
    VERSION: ClassVar[int] = MODEL_VERSION

    def __init__(self, obj: DocumentObject) -> None:
        """Ajoute les propriétés de l'objet, à leurs valeurs par défaut."""
        obj.Proxy = self
        schema.add_missing_properties(obj, PROPERTIES)
        schema.apply_editor_modes(obj, PROPERTIES)

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Version et types contrôlés (ADR 0003), propriétés manquantes recréées."""
        schema.restore_schema(obj, PROPERTIES, self.VERSION, NOUN)

    def mustExecute(self, obj: DocumentObject) -> bool:
        """Vrai quand un objet que la liste lirait a été ajouté ou supprimé depuis le dernier
        calcul (comparaison des noms), pour que la création ou la suppression d'une pièce soit
        vue sans qu'aucun lien ne la désigne encore. Une portée choisie ne change pas ainsi :
        ses objets, eux, sont dans ``Sources``. Faux sans feuille de l'atelier valide (voir
        :func:`refresh`), ou pour un document plus récent que l'atelier."""
        if (
            not _writable(obj)
            or obj.Version > MODEL_VERSION
            or obj.Scope
            or restoring_or_undoing(obj)
        ):
            return False
        known = _names([o for o in obj.Sources if is_source(o)])
        return known != {o.Name for o in obj.Document.Objects if is_source(o)}

    def execute(self, obj: DocumentObject) -> None:
        """Réécrit la feuille d'après le document (:func:`refresh`)."""
        refresh(obj)


def _names(objects: Sequence[DocumentObject]) -> set[str]:
    return {obj.Name for obj in objects}


def _writable(obj: DocumentObject) -> bool:
    """Vrai si ``Sheet`` est une feuille de liste de débit de l'atelier, du même document."""
    return obj.Sheet is not None and cutlist_sheet.is_workshop_sheet(obj.Sheet, obj.Document)


def is_cut_list(obj: object) -> bool:
    """Vrai si ``obj`` est une liste de débit de l'atelier (faux pour un objet supprimé)."""
    return proxy_is(obj, CutListProxy)


def find_cut_list(doc: Document) -> DocumentObject | None:
    """Liste de débit vivante du document, ``None`` s'il n'y en a pas (supprimée, ou document
    ouvert sans l'atelier : l'objet n'a alors pas de proxy)."""
    return next((obj for obj in doc.Objects if is_cut_list(obj)), None)


def refresh(obj: DocumentObject, computed: _Computed | None = None) -> None:
    """Réécrit la feuille de ``obj`` d'après le document (ou ``computed`` : liste et objets lus
    déjà calculés), puis met ``Sources`` à jour si les objets lus ont changé. Sans feuille
    (supprimée) ou pour un document plus récent que l'atelier, ne fait rien. ``Sheet`` n'est
    utilisée que si c'est un ``Spreadsheet::Sheet`` marqué ``MenuiserieCutList`` du même
    document (un document hostile peut lier n'importe quel objet) ; sinon rien n'est réécrit et
    un avertissement va dans la vue rapport (choix : ne pas recréer de feuille en silence pendant
    un recalcul ; ``make_cut_list`` rebranche la feuille propre)."""
    sheet = obj.Sheet
    if sheet is None or obj.Version > MODEL_VERSION:
        return
    if not _writable(obj):
        report_warning(translated(_FOREIGN_SHEET, {"label": quoted_value(obj.Label)}))
        return
    scope = list(obj.Scope)
    cut_list, sources = computed or collect_cut_list(obj.Document, scope or None)
    messages = notice_messages(cut_list.warnings)
    cutlist_sheet.rewrite_sheet(sheet, cut_list, messages, len(scope) or None)
    if _names(sources) != _names(obj.Sources):
        obj.Sources = list(sources)


def _create(doc: Document) -> DocumentObject:
    obj = doc.addObject("App::FeaturePython", OBJECT_NAME)
    CutListProxy(obj)
    obj.Label = translated(DEFAULT_LABEL)
    return obj


def ensure_cut_list(
    doc: Document, objects: Sequence[DocumentObject] | None = None
) -> tuple[DocumentObject, tuple[str, ...]]:
    """Crée ou retrouve la feuille et l'objet ``CutList`` de ``doc``, fixe leur portée
    (``objects``, ``None`` ou vide : tout le document) et écrit la liste. Une seule transaction
    « Liste de débit ». Renvoie la feuille et les avertissements traduits. ``ValueError``
    traduite, avant toute modification, pour un objet d'un autre document."""
    computed = collect_cut_list(doc, objects)
    doc.openTransaction(translated(cutlist_sheet.TITLE))
    try:
        sheet = cutlist_sheet.find_sheet(doc) or cutlist_sheet.create_sheet(doc)
        obj = find_cut_list(doc) or _create(doc)
        if obj.Sheet != sheet:
            obj.Sheet = sheet
        obj.Scope = list(objects or ())
        refresh(obj, computed)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    obj.purgeTouched()  # la liste vient d'être écrite : rien à recalculer
    return sheet, notice_messages(computed[0].warnings)
