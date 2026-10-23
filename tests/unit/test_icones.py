# SPDX-License-Identifier: LGPL-2.1-or-later
"""Icônes SVG de l'atelier : format attendu par FreeCAD et synchronisation avec le générateur."""

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType

import pytest

from freecad.menuiserie import ICONS_DIR

ROOT = Path(__file__).resolve().parents[2]
SVG = "{http://www.w3.org/2000/svg}"
ICONES = sorted(ICONS_DIR.glob("*.svg"))


def _generateur(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """``tools/generer_icones.py`` importé comme lancé en script : son dossier, qui contient le
    moteur ``icones_svg.py``, en tête de ``sys.path``."""
    chemin = ROOT / "tools" / "generer_icones.py"
    monkeypatch.syspath_prepend(str(chemin.parent))
    spec = importlib.util.spec_from_file_location("generer_icones", chemin)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_toutes_les_icones_viennent_du_generateur(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generees = _generateur(monkeypatch).generer(tmp_path)
    assert sorted(p.name for p in generees) == [p.name for p in ICONES]
    for chemin in generees:
        attendu = (ICONS_DIR / chemin.name).read_text(encoding="utf-8")
        assert chemin.read_text(encoding="utf-8") == attendu, (
            f"{chemin.name} diffère du générateur : relancer python tools/generer_icones.py"
        )


@pytest.mark.parametrize("chemin", ICONES, ids=lambda p: p.name)
def test_icone_64_px_autonome(chemin: Path) -> None:
    racine = ET.parse(chemin).getroot()  # noqa: S314 (fichier du dépôt)
    assert racine.tag == f"{SVG}svg"
    assert racine.get("viewBox") == "0 0 64 64"
    assert (racine.get("width"), racine.get("height")) == ("64", "64")
    # Ni script, ni texte (police absente), ni ressource externe.
    balises = {e.tag.removeprefix(SVG) for e in racine.iter()}
    assert balises.isdisjoint({"script", "text", "image", "foreignObject", "style"})
    for e in racine.iter():
        for nom, valeur in e.attrib.items():
            assert not nom.endswith("href"), f"{chemin.name} : lien {valeur}"
            assert not nom.startswith("on"), f"{chemin.name} : attribut {nom}"
