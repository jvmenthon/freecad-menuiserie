# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nom de la pièce = repère : synchronisation des proxys ``WoodPart`` et ``MachinedPart``
(critères L3 à L6 de J6b), sur des objets simulés qui rejouent l'ordre d'appel de FreeCAD
(``allowDuplicateLabel``, ``onBeforeChangeLabel``, puis ``onChanged``). L'objet réel est vérifié
par ``tests/integration/test_nom_repere.py``."""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

DEFAULT = "Pièce de bois"


class _Stub(types.ModuleType):
    """Module FreeCAD de remplacement : tout attribut inconnu est un ``MagicMock``."""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        value = MagicMock(name=name)
        setattr(self, name, value)
        return value


@pytest.fixture
def parts(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.SimpleNamespace]:
    """``features.wood_part`` et ``features.machined_part`` importés sur un FreeCAD simulé,
    puis retirés de ``sys.modules`` (les autres tests ne doivent pas les voir)."""
    report: list[str] = []
    freecad: Any = _Stub("FreeCAD")
    freecad.Qt = types.SimpleNamespace(translate=lambda _context, text: text)
    freecad.Console = types.SimpleNamespace(PrintWarning=report.append)
    before = set(sys.modules)
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    monkeypatch.setitem(sys.modules, "Part", _Stub("Part"))
    from freecad.menuiserie.features import machined_part, part_labels, wood_part

    yield types.SimpleNamespace(
        wood=wood_part, machined=machined_part, labels=part_labels, report=report
    )
    for name in set(sys.modules) - before:
        if name.startswith("freecad.menuiserie.features") or name == "freecad.menuiserie.api":
            del sys.modules[name]
    features = sys.modules.get("freecad.menuiserie")
    if features is not None and hasattr(features, "features"):
        delattr(features, "features")


class FakeDocument:
    """Document minimal : objets, état d'annulation."""

    def __init__(self) -> None:
        self.Objects: list[FakeObject] = []
        self.Transacting = False


class FakeObject:
    """Objet FreeCAD minimal : ``Label`` et ``Mark`` rejouent les rappels du proxy comme
    FreeCAD (``DuplicateLabels`` interdit par défaut)."""

    def __init__(self, doc: FakeDocument, name: str, proxy: Any, label: str = "") -> None:
        self.Document = doc
        self.Name = name
        self.Proxy = proxy
        self.State: list[str] = []
        self.ExpressionEngine: list[tuple[str, str]] = []
        self.InList: list[FakeObject] = []
        self.Base: FakeObject | None = None
        self.changes: list[tuple[str, str]] = []
        self.raw_label = label or name
        self.raw_mark = ""
        doc.Objects.append(self)

    @property
    def Label(self) -> str:
        return self.raw_label

    @Label.setter
    def Label(self, value: str) -> None:
        label = value
        if not self.Proxy.allowDuplicateLabel(self):  # unicité de FreeCAD
            taken = {o.Label for o in self.Document.Objects if o is not self}
            while label in taken:
                label += "1001"
        if "Restore" not in self.State and not self.Document.Transacting:
            label = self.Proxy.onBeforeChangeLabel(self, label) or label
        self.raw_label = label
        self.changes.append(("Label", label))
        self.Proxy.onChanged(self, "Label")

    @property
    def Mark(self) -> str:
        return self.raw_mark

    @Mark.setter
    def Mark(self, value: str) -> None:
        self.raw_mark = value
        self.changes.append(("Mark", value))
        self.Proxy.onChanged(self, "Mark")


@pytest.fixture
def document() -> FakeDocument:
    return FakeDocument()


def blank(parts: types.SimpleNamespace, doc: FakeDocument, name: str = "WoodPart") -> FakeObject:
    """Pièce de bois brute, créée comme ``create_wood_part`` (libellé posé sans rappel)."""
    obj = FakeObject(doc, name, parts.wood.WoodPart.__new__(parts.wood.WoodPart))
    with obj.Proxy.synchronizing():
        obj.Label = DEFAULT
    return obj


def machine(parts: types.SimpleNamespace, doc: FakeDocument, base: FakeObject) -> FakeObject:
    """Pièce usinée de ``base`` : libellé « {brute} (usinée) »."""
    machined = FakeObject(
        doc, "MachinedPart", parts.machined.MachinedPart.__new__(parts.machined.MachinedPart)
    )
    machined.Base = base
    base.InList.append(machined)
    with machined.Proxy.synchronizing():
        machined.Label = f"{base.Label} (usinée)"
    return machined


# --- L3 : repère -> nom --------------------------------------------------------------------


def test_changer_le_repere_change_le_libelle(parts: Any, document: FakeDocument) -> None:
    piece = blank(parts, document)
    piece.Mark = "M1"
    assert piece.Label == "M1"
    piece.Mark = ""
    assert piece.Label == DEFAULT
    piece.Mark = "Joue gauche"
    assert piece.Label == "Joue gauche"


def test_la_piece_usinee_suit_le_repere(parts: Any, document: FakeDocument) -> None:
    piece = blank(parts, document)
    machined = machine(parts, document, piece)
    piece.Mark = "E2"
    assert (piece.Label, machined.Label) == ("E2", "E2 (usinée)")


def test_ecriture_du_libelle_par_l_atelier_ne_relit_pas_le_repere(
    parts: Any, document: FakeDocument
) -> None:
    """Un repère « A (2) » saisi dans le panneau est gardé tel quel (limite de L2)."""
    piece = blank(parts, document)
    piece.Mark = "A (2)"
    assert (piece.Mark, piece.Label) == ("A (2)", "A (2)")


# --- L4 : nom -> repère --------------------------------------------------------------------


def test_renommer_dans_l_arborescence_change_le_repere(parts: Any, document: FakeDocument) -> None:
    piece = blank(parts, document)
    piece.Label = "Traverse"
    assert (piece.Mark, piece.Label) == ("Traverse", "Traverse")


def test_renommer_en_pieces_de_bois_vide_le_repere(parts: Any, document: FakeDocument) -> None:
    piece = blank(parts, document)
    piece.Mark = "M1"
    piece.Label = DEFAULT
    assert (piece.Mark, piece.Label) == ("", DEFAULT)


def test_renommer_la_brute_renomme_l_usinee(parts: Any, document: FakeDocument) -> None:
    piece = blank(parts, document)
    machined = machine(parts, document, piece)
    piece.Label = "Montant"
    assert (piece.Mark, piece.Label, machined.Label) == ("Montant", "Montant", "Montant (usinée)")


def test_renommer_l_usinee_change_le_repere_de_la_brute(parts: Any, document: FakeDocument) -> None:
    piece = blank(parts, document)
    machined = machine(parts, document, piece)
    machined.Label = "Pied (usinée)"
    assert (piece.Mark, piece.Label, machined.Label) == ("Pied", "Pied", "Pied (usinée)")
    machined.Label = "Barreau"  # sans le suffixe saisi
    assert (piece.Mark, piece.Label, machined.Label) == ("Barreau", "Barreau", "Barreau (usinée)")


def test_repere_pilote_par_une_expression_ne_change_pas(parts: Any, document: FakeDocument) -> None:
    piece = blank(parts, document)
    piece.Mark = "M1"
    piece.ExpressionEngine = [(".Mark", "'M1'")]
    piece.Label = "Autre"
    assert (piece.Mark, piece.Label) == ("M1", "M1")
    assert any("piloté par une expression" in line for line in parts.report)


def test_repere_pilote_la_brute_de_l_usinee_ne_change_pas(
    parts: Any, document: FakeDocument
) -> None:
    piece = blank(parts, document)
    piece.Mark = "M1"
    machined = machine(parts, document, piece)
    piece.ExpressionEngine = [(".Mark", "'M1'")]
    machined.Label = "Autre (usinée)"
    assert (piece.Mark, piece.Label, machined.Label) == ("M1", "M1", "M1 (usinée)")
    assert parts.report


# --- L5 : doublons -------------------------------------------------------------------------


def test_deux_pieces_de_meme_repere(parts: Any, document: FakeDocument) -> None:
    first, second = blank(parts, document, "A"), blank(parts, document, "B")
    first.Mark = "M1"
    second.Mark = "M1"
    assert (first.Label, second.Label) == ("M1", "M1 (2)")
    assert (first.Mark, second.Mark) == ("M1", "M1")
    third = blank(parts, document, "C")
    third.Mark = "M1"
    assert third.Label == "M1 (3)"


def test_renommer_le_doublon_en_son_repere_ne_change_rien(
    parts: Any, document: FakeDocument
) -> None:
    first, second = blank(parts, document, "A"), blank(parts, document, "B")
    first.Mark = second.Mark = "M1"
    second.Label = "M1"
    assert (second.Mark, second.Label) == ("M1", "M1 (2)")
    assert (first.Mark, first.Label) == ("M1", "M1")


def test_renommer_en_libelle_pris_garde_le_repere_saisi(parts: Any, document: FakeDocument) -> None:
    """Le libellé saisi arrive tel quel (pas de « M1001 ») : le repère est celui qu'on a tapé."""
    first, second = blank(parts, document, "A"), blank(parts, document, "B")
    first.Mark = "M1"
    second.Label = "M1"
    assert (second.Mark, second.Label) == ("M1", "M1 (2)")


def test_libelle_d_un_autre_objet_est_pris_en_compte(parts: Any, document: FakeDocument) -> None:
    other = FakeObject(document, "Sheet", parts.wood.WoodPart.__new__(parts.wood.WoodPart), "M1")
    piece = blank(parts, document)
    piece.Mark = "M1"
    assert piece.Label == "M1 (2)"
    assert other.Label == "M1"


# --- L6 : restauration et annulation -------------------------------------------------------


def test_aucune_synchronisation_pendant_la_restauration(parts: Any, document: FakeDocument) -> None:
    piece = blank(parts, document)
    piece.State.append("Restore")
    piece.Mark = "M1"
    piece.Label = "Autre"
    assert (piece.Mark, piece.Label) == ("M1", "Autre")


def test_aucune_synchronisation_pendant_une_annulation(parts: Any, document: FakeDocument) -> None:
    piece = blank(parts, document)
    machined = machine(parts, document, piece)
    document.Transacting = True
    piece.Mark = "M1"
    piece.Label = "Autre"
    machined.Label = "Encore (usinée)"
    assert (piece.Mark, piece.Label, machined.Label) == ("M1", "Autre", "Encore (usinée)")


def test_reouverture_sans_changement(parts: Any, document: FakeDocument) -> None:
    """Q5 : ni ``onDocumentRestored`` ni un chargement n'écrivent le libellé ou le repère."""
    source = Path(str(parts.wood.__file__))
    text = source.read_text(encoding="utf-8")
    restored = text.split("def onDocumentRestored", 1)[1].split("def onChanged", 1)[0]
    assert "Label" not in restored and "Mark" not in restored
    assert "make_label_unique(obj)" in restored  # seule écriture : un doublon (L5 bis)


# --- L5 bis (J6) : copie, duplication, fusion ----------------------------------------------


def copy_of(parts: Any, doc: FakeDocument, original: FakeObject, name: str) -> FakeObject:
    """Copie de ``original`` telle que FreeCAD la restaure : même libellé et même repère."""
    copy = blank(parts, doc, name)
    copy.raw_label, copy.raw_mark = original.raw_label, original.raw_mark
    copy.changes.clear()
    return copy


def test_copie_d_une_piece_prend_un_libelle_unique(parts: Any, document: FakeDocument) -> None:
    original = blank(parts, document, "A")
    original.Mark = "M1"
    copy = copy_of(parts, document, original, "B")
    copy.State.append("Restore")
    parts.labels.make_label_unique(copy)
    assert (original.Label, copy.Label, copy.Mark) == ("M1", "M1 (2)", "M1")
    second = copy_of(parts, document, original, "C")
    parts.labels.make_label_unique(second)
    assert second.Label == "M1 (3)"


def test_libelle_deja_unique_n_est_pas_ecrit(parts: Any, document: FakeDocument) -> None:
    """Réouverture ordinaire (L6) : aucun libellé n'est écrit."""
    piece = blank(parts, document, "A")
    piece.raw_label, piece.raw_mark = "Joue gauche", "JG"
    piece.changes.clear()
    parts.labels.make_label_unique(piece)
    assert piece.changes == [] and piece.Label == "Joue gauche"


def test_aucun_libelle_change_pendant_une_annulation(parts: Any, document: FakeDocument) -> None:
    original = blank(parts, document, "A")
    original.Mark = "M1"
    copy = copy_of(parts, document, original, "B")
    document.Transacting = True
    parts.labels.make_label_unique(copy)
    assert copy.Label == "M1"


def test_copie_de_la_brute_et_de_l_usinee(parts: Any, document: FakeDocument) -> None:
    original = blank(parts, document, "A")
    original.Mark = "M1"
    machined = machine(parts, document, original)
    blank_copy = copy_of(parts, document, original, "B")
    machined_copy = machine(parts, document, blank_copy)
    machined_copy.raw_label = machined.raw_label  # « M1 (usinée) » comme dans le modèle
    machined_copy.changes.clear()
    parts.labels.make_label_unique(blank_copy)
    assert (blank_copy.Label, machined_copy.Label) == ("M1 (2)", "M1 (2) (usinée)")
    assert (original.Label, machined.Label) == ("M1", "M1 (usinée)")


def test_usinee_restauree_avant_sa_brute(parts: Any, document: FakeDocument) -> None:
    """L'ordre de restauration n'est pas garanti : la brute est rendue unique la première."""
    original = blank(parts, document, "A")
    original.Mark = "M1"
    machine(parts, document, original)
    blank_copy = copy_of(parts, document, original, "B")
    machined_copy = machine(parts, document, blank_copy)
    machined_copy.raw_label = "M1 (usinée)"
    machined_copy.Proxy._make_label_unique(machined_copy)
    assert (blank_copy.Label, machined_copy.Label) == ("M1 (2)", "M1 (2) (usinée)")
    assert len({o.Label for o in document.Objects}) == len(document.Objects)


def test_premiere_modification_apres_reouverture(parts: Any, document: FakeDocument) -> None:
    """Libellé différent du repère à l'ouverture (J1 à J4) : la 1re modification synchronise."""
    piece = blank(parts, document)
    piece.raw_mark = "JG"
    piece.raw_label = "Joue gauche"
    assert (piece.Mark, piece.Label) == ("JG", "Joue gauche")
    assert piece.changes == [("Label", DEFAULT)]  # aucune écriture à l'ouverture
    piece.Mark = "JD"
    assert piece.Label == "JD"
    other = blank(parts, document, "Autre")
    other.raw_mark = "JG"
    other.raw_label = "Joue gauche"
    other.Label = "Joue droite"
    assert (other.Mark, other.Label) == ("Joue droite", "Joue droite")


def test_libelle_a_la_creation(parts: Any, document: FakeDocument) -> None:
    """Une nouvelle pièce prend le libellé de son repère, sans doublon avec les autres."""
    first = blank(parts, document, "A")
    first.Mark = "M1"
    taken = {o.Label for o in document.Objects if o is not first}
    assert parts.wood.label_of_mark(blank(parts, document, "B"), "M1") == "M1 (2)"
    assert "M1" not in taken
