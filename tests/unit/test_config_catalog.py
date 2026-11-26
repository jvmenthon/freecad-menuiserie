# SPDX-License-Identifier: LGPL-2.1-or-later
"""Catalogue de réglages ``kit/config.catalog`` (ADR 0069) : validation bornée."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.kit.config.catalog import (
    MAX_TEXT_LENGTH,
    REMEMBER_SUFFIX,
    Catalog,
    Kind,
    Reason,
    Setting,
    SettingError,
    coerce,
)
from tests.unit.aides_config import length_setting, sample_catalog

# --- catalogue --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("2", Reason.WRONG_TYPE),
        (True, Reason.WRONG_TYPE),
        (math.nan, Reason.NOT_FINITE),
        (math.inf, Reason.NOT_FINITE),
        (-0.001, Reason.BELOW_MINIMUM),
        (20.001, Reason.ABOVE_MAXIMUM),
    ],
)
def test_nombre_refuse(value: object, reason: Reason) -> None:
    with pytest.raises(SettingError) as refus:
        length_setting().check(value)
    assert refus.value.reason is reason
    assert refus.value.key == "Jeu"


@pytest.mark.parametrize("value", [0, 0.0, 20, 2.5])
def test_nombre_accepte_aux_bornes_et_entier_devenu_reel(value: float) -> None:
    checked = length_setting().check(value)
    assert checked == value
    assert isinstance(checked, float)


def test_entier_refuse_un_reel_et_un_booleen() -> None:
    setting = sample_catalog().get("Nombre")
    assert setting.check(1) == 1
    for value in (2.0, True, 0, 10):
        with pytest.raises(SettingError):
            setting.check(value)


def test_case_a_cocher_n_accepte_qu_un_booleen() -> None:
    setting = sample_catalog().get("Debouchant")
    assert setting.check(True) is True
    with pytest.raises(SettingError, match="wrong_type"):
        setting.check(1)


def test_choix_et_textes() -> None:
    catalog = sample_catalog()
    assert catalog.get("Profil").check("Chamfer") == "Chamfer"
    with pytest.raises(SettingError) as refus:
        catalog.get("Profil").check("Ogee")
    assert refus.value.reason is Reason.NOT_A_CHOICE
    path = catalog.get("Dossier")
    assert path.check("D:\\Atelier") == "D:\\Atelier"
    for value, reason in (
        ("a" * (MAX_TEXT_LENGTH + 1), Reason.TEXT_TOO_LONG),
        ("ligne\nsuivante", Reason.FORBIDDEN_CHARACTER),
        ("\u202edossier", Reason.FORBIDDEN_CHARACTER),
    ):
        with pytest.raises(SettingError) as refus:
            path.check(value)
        assert refus.value.reason is reason
    assert path.check("a" * MAX_TEXT_LENGTH)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"key": "1clé"},
        {"key": "a" * 65},
        {"key": "avec.point"},
        {"default": 25.0},
        {"minimum": 5.0, "maximum": 1.0, "default": 3.0},
    ],
)
def test_catalogue_mal_ecrit_refuse_a_la_construction(kwargs: dict[str, object]) -> None:
    fields: dict[str, object] = {
        "key": "Jeu",
        "kind": Kind.FLOAT,
        "default": 2.0,
        "label": "Jeu",
        "tooltip": "Jeu.",
        "group": "G",
        "minimum": 0.0,
        "maximum": 20.0,
    }
    fields.update(kwargs)
    with pytest.raises(ValueError):
        Setting(**fields)  # type: ignore[arg-type]


def test_choix_sans_valeurs_refuse() -> None:
    with pytest.raises(ValueError, match="sans valeurs"):
        Setting("Profil", Kind.CHOICE, "Round", "Profil", "Profil.", "Chants")


def test_coerce_rend_la_valeur_par_defaut_si_absente_ou_abimee() -> None:
    setting = length_setting()
    assert coerce(setting, None) == 2.0
    assert coerce(setting, "abîmé") == 2.0
    assert coerce(setting, 50.0) == 2.0
    assert coerce(setting, 3.0) == 3.0


def test_catalogue_cles_uniques_inconnue_et_groupes() -> None:
    with pytest.raises(ValueError, match="double"):
        Catalog([length_setting(), length_setting()])
    catalog = sample_catalog()
    assert len(catalog) == 5
    assert "Jeu" in catalog
    assert "Inconnu" not in catalog
    with pytest.raises(SettingError) as refus:
        catalog.get("Inconnu")
    assert refus.value.reason is Reason.UNKNOWN_KEY
    assert catalog.groups() == ("Assemblages", "Chants", "Stockage")


def test_entier_trop_grand_pour_un_reel_est_refuse_proprement() -> None:
    """Un entier hors de portée d'un ``float`` doit être un refus codé, pas ``OverflowError``
    (sinon ``coerce`` et ``record_used`` laissent passer l'exception)."""
    setting = length_setting()
    with pytest.raises(SettingError) as refus:
        setting.check(10**400)
    assert refus.value.reason is Reason.ABOVE_MAXIMUM
    with pytest.raises(SettingError):
        setting.check(-(10**400))
    assert coerce(setting, 10**400) == setting.default


def test_cle_reservee_au_dernier_utilise_refusee() -> None:
    """Une clé ``…RememberLast`` entrerait en collision avec la case « Dernier utilisé »."""
    with pytest.raises(ValueError, match="réservée"):
        Catalog([length_setting(key=f"Cote{REMEMBER_SUFFIX}")])
