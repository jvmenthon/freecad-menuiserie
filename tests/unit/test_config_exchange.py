# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export et import générique des réglages : aller-retour, lecture stricte, aperçu (ADR 0069)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.kit.config import exchange
from freecad.menuiserie.kit.config.catalog import Catalog, Reason, Relation, SettingError, Value
from freecad.menuiserie.kit.config.exchange import (
    MAX_FILE_BYTES,
    Change,
    ExchangeError,
    ExchangeReason,
)
from freecad.menuiserie.kit.config.store import MemoryStore, Settings
from tests.unit.aides_config import length_setting, sample_catalog


def _validate_note(raw: dict[str, Any]) -> str:
    text = raw.get("text")
    if not isinstance(text, str):
        raise ValueError("texte attendu")
    return text


SECTIONS = {"note": _validate_note}


def _file(tmp_path: Path, content: str | bytes) -> Path:
    path = tmp_path / "atelier.json"
    if isinstance(content, str):
        content = content.encode("utf-8")
    path.write_bytes(content)
    return path


def _document(settings: object, **more: object) -> str:
    return json.dumps({"format": 1, "settings": settings, **more})


def _refused(path: Path) -> ExchangeError:
    with pytest.raises(ExchangeError) as info:
        exchange.read_import(path, sample_catalog(), SECTIONS)
    return info.value


def _settings() -> Settings:
    return Settings(sample_catalog(), MemoryStore())


def test_aller_retour(tmp_path: Path) -> None:
    source = _settings()
    source.set("Jeu", 5.5)
    source.set("Nombre", 7)
    source.set("Profil", "Chamfer")
    source.set_remember_last("Jeu", True)
    path = tmp_path / "dossier" / "atelier.json"
    payload = exchange.export_payload(source.catalog, source, {"note": {"text": "bonjour"}})
    exchange.write_export(path, payload)
    assert json.loads(path.read_text(encoding="utf-8"))["settings"]["JeuRememberLast"] is True
    result = exchange.read_import(path, sample_catalog(), SECTIONS)
    assert result.ignored == ()
    assert result.sections == {"note": "bonjour"}
    target = _settings()
    exchange.apply(target, result)
    for setting in target.catalog:
        assert target.value(setting.key) == source.value(setting.key)
        assert target.remembers_last(setting.key) == source.remembers_last(setting.key)


def test_export_contient_tous_les_reglages_et_les_cases() -> None:
    settings = _settings()
    payload = exchange.export_payload(settings.catalog, settings)
    assert payload["format"] == 1
    values = payload["settings"]
    assert isinstance(values, dict)
    assert {"Jeu", "Debouchant", "Nombre", "Profil"} <= set(values)
    assert "Dossier" not in values  # chemin propre à la machine
    assert values["JeuRememberLast"] is False
    assert "NombreRememberLast" not in values


def test_ecriture_impossible_est_une_erreur_d_echange(tmp_path: Path) -> None:
    blocker = tmp_path / "fichier"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(ExchangeError) as info:
        exchange.write_export(blocker / "atelier.json", {"format": 1})
    assert info.value.reason is ExchangeReason.NOT_WRITTEN


def test_fichier_absent(tmp_path: Path) -> None:
    assert _refused(tmp_path / "absent.json").reason is ExchangeReason.UNREADABLE


def test_fichier_trop_gros(tmp_path: Path) -> None:
    pad = " " * MAX_FILE_BYTES
    assert _refused(_file(tmp_path, _document({}) + pad)).reason is ExchangeReason.TOO_LARGE
    exact = _document({}).encode() + b" " * (MAX_FILE_BYTES - len(_document({})))
    assert len(exact) == MAX_FILE_BYTES
    assert exchange.read_import(_file(tmp_path, exact), sample_catalog()).values == {}


@pytest.mark.parametrize("content", ["", "{", "[" * 10000, b"\xff\xfe", '{"format": 1e}'])
def test_json_invalide(tmp_path: Path, content: str | bytes) -> None:
    assert _refused(_file(tmp_path, content)).reason is ExchangeReason.NOT_JSON


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_constantes_non_finies_refusees(tmp_path: Path, constant: str) -> None:
    text = '{"format": 1, "settings": {"Jeu": ' + constant + "}}"
    assert _refused(_file(tmp_path, text)).reason is ExchangeReason.NOT_STRICT


def test_cles_en_double_refusees(tmp_path: Path) -> None:
    text = '{"format": 1, "settings": {"Jeu": 1, "Jeu": 2}}'
    error = _refused(_file(tmp_path, text))
    assert (error.reason, error.detail) == (ExchangeReason.DUPLICATE_KEY, "Jeu")


@pytest.mark.parametrize("content", ["[]", '"x"', "3"])
def test_racine_non_objet(tmp_path: Path, content: str) -> None:
    assert _refused(_file(tmp_path, content)).reason is ExchangeReason.NOT_AN_OBJECT


def test_format_plus_recent_refuse(tmp_path: Path) -> None:
    path = _file(tmp_path, '{"format": 2, "settings": {}}')
    assert _refused(path).reason is ExchangeReason.NEWER_FORMAT


@pytest.mark.parametrize("version", ["0", "true", '"1"', "1.0", "null"])
def test_format_invalide(tmp_path: Path, version: str) -> None:
    path = _file(tmp_path, '{"format": ' + version + ', "settings": {}}')
    assert _refused(path).reason is ExchangeReason.BAD_FORMAT
    assert _refused(_file(tmp_path, "{}")).reason is ExchangeReason.BAD_FORMAT


@pytest.mark.parametrize(
    ("key", "value", "reason"),
    [
        ("Jeu", 21, Reason.ABOVE_MAXIMUM),
        ("Jeu", -1, Reason.BELOW_MINIMUM),
        ("Jeu", "2", Reason.WRONG_TYPE),
        ("Nombre", 2.5, Reason.WRONG_TYPE),
        ("Profil", "Autre", Reason.NOT_A_CHOICE),
        ("JeuRememberLast", "oui", Reason.WRONG_TYPE),
    ],
)
def test_valeur_refusee_refuse_tout_le_fichier(
    tmp_path: Path, key: str, value: object, reason: Reason
) -> None:
    path = _file(tmp_path, _document({"Nombre": 4, key: value}))
    error = _refused(path)
    assert error.reason is ExchangeReason.INVALID_SETTING
    assert error.detail == key
    assert error.cause is not None
    assert error.cause.reason is reason


def test_cle_inconnue_ignoree_avec_avertissement(tmp_path: Path) -> None:
    settings = {"Nombre": 4, "Nouveau": 1, "NombreRememberLast": True}
    path = _file(tmp_path, _document(settings, autre={"a": 1}))
    result = exchange.read_import(path, sample_catalog(), SECTIONS)
    assert result.values == {"Nombre": 4}
    assert result.ignored == ("Nouveau", "NombreRememberLast", "autre")


def test_reglages_ou_section_qui_ne_sont_pas_des_objets(tmp_path: Path) -> None:
    error = _refused(_file(tmp_path, _document([1])))
    assert (error.reason, error.detail) == (ExchangeReason.NOT_AN_OBJECT, "settings")
    error = _refused(_file(tmp_path, _document({}, note=[])))
    assert (error.reason, error.detail) == (ExchangeReason.NOT_AN_OBJECT, "note")


def test_section_invalide_refusee(tmp_path: Path) -> None:
    error = _refused(_file(tmp_path, _document({"Nombre": 4}, note={"text": 3})))
    assert error.reason is ExchangeReason.INVALID_SECTION
    assert error.detail.startswith("note")


def test_section_absente_permise(tmp_path: Path) -> None:
    result = exchange.read_import(_file(tmp_path, _document({})), sample_catalog(), SECTIONS)
    assert result.sections == {}


def test_apercu_sans_changement_est_vide(tmp_path: Path) -> None:
    settings = _settings()
    path = tmp_path / "atelier.json"
    exchange.write_export(path, exchange.export_payload(settings.catalog, settings))
    result = exchange.read_import(path, settings.catalog)
    assert exchange.preview(settings.catalog, settings, result) == []


def test_apercu_liste_seulement_les_differences(tmp_path: Path) -> None:
    settings = _settings()
    settings.set("Nombre", 5)
    values = {"Nombre": 5, "Jeu": 4.0, "Profil": "Chamfer", "JeuRememberLast": True}
    result = exchange.read_import(_file(tmp_path, _document(values)), settings.catalog)
    assert exchange.preview(settings.catalog, settings, result) == [
        Change("Jeu", 2.0, 4.0),
        Change("JeuRememberLast", False, True),
        Change("Profil", "Round", "Chamfer"),
    ]
    assert settings.value("Jeu") == 2.0  # l'aperçu n'écrit rien


def test_apply_ecrit_dans_le_stockage(tmp_path: Path) -> None:
    store = MemoryStore()
    settings = Settings(sample_catalog(), store)
    values = {"Jeu": 3.0, "JeuRememberLast": True, "Debouchant": True}
    result = exchange.read_import(_file(tmp_path, _document(values)), settings.catalog)
    exchange.apply(settings, result)
    assert settings.value("Jeu") == 3.0
    assert settings.value("Debouchant") is True
    assert settings.remembers_last("Jeu")
    assert store.values[("Float", "Jeu")] == 3.0


def test_chemin_importe_est_ignore(tmp_path: Path) -> None:
    path = _file(tmp_path, _document({"Dossier": "/ailleurs", "Jeu": 1.5}))
    result = exchange.read_import(path, sample_catalog(), SECTIONS)
    assert "Dossier" not in result.values
    assert "Dossier" in result.ignored


def test_export_non_serialisable_est_une_erreur_d_echange(tmp_path: Path) -> None:
    for payload in ({"format": 1, "x": float("nan")}, {"format": 1, "x": {1, 2}}):
        with pytest.raises(ExchangeError) as info:
            exchange.write_export(tmp_path / "atelier.json", payload)
        assert info.value.reason is ExchangeReason.NOT_WRITTEN
    assert not (tmp_path / "atelier.json").exists()


def _paired_catalog() -> Catalog:
    def ordered(values: Mapping[str, Value]) -> bool:
        return float(values["Jeu"]) <= float(values["Autre"])

    return Catalog(
        [length_setting(), length_setting("Autre", 5.0, remember=False)],
        [Relation(("Jeu", "Autre"), ordered)],
    )


def test_relation_violee_par_l_import_refusee(tmp_path: Path) -> None:
    catalog = _paired_catalog()
    settings = Settings(catalog, MemoryStore())
    path = _file(tmp_path, _document({"Jeu": 8.0}))  # « Autre » reste à 5 : jeu > autre
    result = exchange.read_import(path, catalog)
    with pytest.raises(ExchangeError) as info:
        exchange.check_relations(catalog, settings, result)
    assert info.value.reason is ExchangeReason.INCONSISTENT
    assert info.value.detail == "Jeu, Autre"


def test_relation_respectee_acceptee(tmp_path: Path) -> None:
    catalog = _paired_catalog()
    result = exchange.read_import(_file(tmp_path, _document({"Jeu": 4.0})), catalog)
    exchange.check_relations(catalog, Settings(catalog, MemoryStore()), result)


def test_relation_sur_cle_inconnue_est_une_erreur_de_catalogue() -> None:
    def always(_values: Mapping[str, Value]) -> bool:
        return True

    with pytest.raises(SettingError):
        Catalog([length_setting()], [Relation(("Jeu", "Absent"), always)])
