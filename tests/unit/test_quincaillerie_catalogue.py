# SPDX-License-Identifier: LGPL-2.1-or-later
"""Catalogue de quincaillerie (issue #159, ADR 0033) : lecture stricte, fusion, recherche."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core.hardware import (
    FAMILIES,
    MAX_ITEMS,
    Catalog,
    CatalogSource,
    UnknownHardwareError,
    load_catalog,
    merge_catalogs,
    parse_catalog,
    read_catalog_file,
)
from freecad.menuiserie.core.materials import Severity

DATA = Path(__file__).parents[2] / "freecad" / "menuiserie" / "data" / "quincaillerie.json"


def _item(**changes: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "tourillon-8x35",
        "family": "dowel",
        "label": "Tourillon Ø8",
        "params": {"diameter": 8, "length": 35},
        "source": "test",
    }
    item.update(changes)
    return item


def _parse(*items: dict[str, Any]) -> Any:
    return parse_catalog({"format": 1, "items": list(items)}, "test")


def test_catalogue_integre_valide_et_complet() -> None:
    catalog, issues = load_catalog(DATA)
    assert [i.format() for i in issues if i.severity is not Severity.INFO] == []
    families = {item.family for item in catalog}
    assert {"dowel", "loose-tenon", "biscuit", "wood-screw"} <= families
    assert catalog.get("tourillon-8x35").param("length") == 35.0
    assert catalog.get("domino-8x50").manufacturer == "Festool"
    assert all(item.family in FAMILIES for item in catalog)
    assert all(item.source for item in catalog)


def test_entree_valide() -> None:
    items, issues = _parse(_item(manufacturer="Acme", reference="A-1"))
    assert issues == []
    assert items[0].title == "Acme A-1 — Tourillon Ø8"
    assert items[0].param("diameter") == 8.0


def test_titre_sans_fabricant() -> None:
    items, _ = _parse(_item())
    assert items[0].title == "Tourillon Ø8"


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "Bad Id"},
        {"id": 3},
        {"family": ""},
        {"label": None},
        {"source": "‮"},
        {"manufacturer": 5},
        {"params": []},
        {"params": {"diameter": 8}},
        {"params": {"diameter": 8, "length": 35, "extra": 1}},
        {"params": {"diameter": "8", "length": 35}},
        {"params": {"diameter": True, "length": 35}},
        {"params": {"diameter": 0, "length": 35}},
        {"params": {"diameter": 8, "length": 99999}},
        {"params": {"diameter": float("inf"), "length": 35}},
    ],
)
def test_entree_invalide_ignoree_sans_perdre_les_autres(changes: dict[str, Any]) -> None:
    other = _item(id="autre")
    items, issues = _parse(_item(**changes), other)
    assert [item.id for item in items] == ["autre"]
    assert len(issues) == 1
    assert issues[0].severity is Severity.ERROR
    assert "test" in issues[0].format()


def test_famille_inconnue_gardee_sans_forme() -> None:
    items, issues = _parse(_item(family="futur", params={"x": 3}))
    assert [item.family for item in items] == ["futur"]
    assert [i.severity for i in issues] == [Severity.INFO]
    bad, bad_issues = _parse(_item(family="futur", params={"x": -3}))
    assert bad == [] and bad_issues[0].severity is Severity.ERROR


def test_identifiant_en_double_garde_le_premier() -> None:
    items, issues = _parse(_item(label="premier"), _item(label="second"))
    assert [item.label for item in items] == ["premier"]
    assert issues[0].severity is Severity.WARNING


def test_cle_en_double_dans_une_entree(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    text = json.dumps({"format": 1, "items": [_item()]}).replace(
        '"family": "dowel"', '"family": "dowel", "family": "biscuit"'
    )
    path.write_text(text, encoding="utf-8")
    result = read_catalog_file(CatalogSource(path, "c"))
    assert result is not None
    items, issues = result
    assert items == [] and "double" in issues[0].format()


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"format": 2, "items": []},
        {"format": True, "items": []},
        {"format": 1},
        {"format": 1, "items": {}},
    ],
)
def test_racine_invalide(document: Any) -> None:
    items, issues = parse_catalog(document, "test")
    assert items == [] and len(issues) == 1 and issues[0].severity is Severity.ERROR


def test_entree_non_objet_et_trop_de_references() -> None:
    items, issues = parse_catalog({"format": 1, "items": [3, _item()]}, "test")
    assert len(items) == 1 and "n° 1" in issues[0].format()
    many = [_item(id=f"t{i}") for i in range(MAX_ITEMS + 1)]
    items, issues = parse_catalog({"format": 1, "items": many}, "test")
    assert len(items) == MAX_ITEMS and "trop de références" in issues[0].format()


def test_fusion_la_source_la_plus_proche_l_emporte() -> None:
    builtin, _ = _parse(_item(label="intégré"), _item(id="b"))
    user, _ = _parse(_item(label="personnel"), _item(id="c"))
    catalog, issues = merge_catalogs([("perso", user), ("intégrée", builtin)])
    assert catalog.get("tourillon-8x35").label == "personnel"
    assert [item.id for item in catalog] == ["tourillon-8x35", "b", "c"]
    assert [i.severity for i in issues] == [Severity.INFO]


def test_chargement_fichier_absent_illisible_ou_manquant(tmp_path: Path) -> None:
    assert read_catalog_file(CatalogSource(tmp_path / "absent.json", "x")) is None
    catalog, issues = load_catalog(tmp_path / "absent.json")
    assert len(catalog) == 0 and issues[0].severity is Severity.ERROR
    broken = tmp_path / "casse.json"
    broken.write_text("{", encoding="utf-8")
    catalog, issues = load_catalog(DATA, [CatalogSource(broken, "casse")])
    assert len(catalog) > 0 and any("casse" in i.format() for i in issues)


def test_chargement_avec_catalogue_personnel(tmp_path: Path) -> None:
    perso = tmp_path / "perso.json"
    perso.write_text(
        json.dumps({"format": 1, "items": [_item(id="tourillon-8x35", label="Mon tourillon")]}),
        encoding="utf-8",
    )
    catalog, _ = load_catalog(DATA, [CatalogSource(perso, str(perso))])
    assert catalog.get("tourillon-8x35").label == "Mon tourillon"


def test_recherche_et_acces() -> None:
    catalog, _ = load_catalog(DATA)
    assert {i.id for i in catalog.search("domino 8")} == {"domino-8x40", "domino-8x50"}
    assert [i.id for i in catalog.search("DOMINO", "biscuit")] == []
    assert catalog.find("absent") is None
    with pytest.raises(UnknownHardwareError):
        catalog.get("absent")
    assert len(catalog.of_family("biscuit")) == 3
    with pytest.raises(ValueError, match="double"):
        Catalog((catalog.items[0], catalog.items[0]))


def test_reference_vers_parametres_d_assemblage() -> None:
    from freecad.menuiserie.core.hardware import joint_kind_of, joint_params
    from freecad.menuiserie.core.i18n import TemplatedError
    from freecad.menuiserie.core.joints import JointKind

    catalog, _ = load_catalog(DATA)
    dowel, domino, biscuit = (
        catalog.get(i) for i in ("tourillon-8x35", "domino-8x50", "biscuit-20")
    )
    assert joint_params(dowel, JointKind.DOWELS) == {"diameter": 8.0, "dowel_length": 35.0}
    assert joint_params(domino, JointKind.LOOSE_TENON) == {"size": "8x50"}
    assert joint_params(biscuit, JointKind.BISCUIT) == {"size": "20"}
    assert joint_kind_of(catalog.get("vis-bois-4x40")) is None
    with pytest.raises(TemplatedError, match="ne convient pas"):
        joint_params(domino, JointKind.BISCUIT)
    with pytest.raises(TemplatedError, match="ne se pose pas"):
        joint_params(catalog.get("vis-bois-4x40"), JointKind.DOWELS)
