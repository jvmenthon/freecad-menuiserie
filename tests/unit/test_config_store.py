# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stockage des réglages ``kit/config.store`` (ADR 0069) : valeurs, « Dernier utilisé »."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.kit.config.catalog import Kind, Reason, SettingError
from freecad.menuiserie.kit.config.store import FreeCADStore, MemoryStore, Settings
from tests.unit.aides_config import sample_catalog
from tests.unit.aides_reglages import FakeParamGroup

# --- stockage et « Dernier utilisé » -------------------------------------------------------------


def test_valeur_par_defaut_puis_enregistree_puis_retablie() -> None:
    settings = Settings(sample_catalog(), MemoryStore())
    assert settings.value("Jeu") == 2.0
    assert not settings.is_modified("Jeu")
    assert settings.set("Jeu", 3) == 3.0
    assert settings.value("Jeu") == 3.0
    assert settings.is_modified("Jeu")
    settings.reset("Jeu")
    assert settings.value("Jeu") == 2.0


def test_valeur_refusee_n_est_pas_ecrite() -> None:
    store = MemoryStore()
    settings = Settings(sample_catalog(), store)
    with pytest.raises(SettingError):
        settings.set("Jeu", 99.0)
    assert store.values == {}


def test_valeur_abimee_dans_le_stockage_donne_le_defaut() -> None:
    store = MemoryStore()
    store.write("Jeu", Kind.FLOAT, 1e9)
    assert Settings(sample_catalog(), store).value("Jeu") == 2.0


def test_dernier_utilise() -> None:
    settings = Settings(sample_catalog(), MemoryStore())
    assert not settings.remembers_last("Jeu")
    assert not settings.record_used("Jeu", 4.0)  # case décochée : rien n'est retenu
    assert settings.value("Jeu") == 2.0
    settings.set_remember_last("Jeu", True)
    assert settings.remembers_last("Jeu")
    assert settings.record_used("Jeu", 4.0)
    assert settings.value("Jeu") == 4.0
    assert not settings.record_used("Jeu", -1.0)  # valeur refusée : ignorée
    assert settings.value("Jeu") == 4.0
    settings.reset("Jeu")  # « Rétablir » décoche aussi la case
    assert not settings.remembers_last("Jeu")
    assert settings.value("Jeu") == 2.0


def test_dernier_utilise_non_prevu() -> None:
    settings = Settings(sample_catalog(), MemoryStore())
    with pytest.raises(ValueError, match="non prévu"):
        settings.set_remember_last("Nombre", True)
    assert not settings.remembers_last("Nombre")


def test_tout_retablir() -> None:
    settings = Settings(sample_catalog(), MemoryStore())
    settings.set("Jeu", 5.0)
    settings.set("Profil", "Chamfer")
    settings.set_remember_last("Debouchant", True)
    settings.reset_all()
    assert [settings.is_modified(s.key) for s in settings.catalog] == [False] * 5
    assert not settings.remembers_last("Debouchant")
    assert settings.catalog.get("Jeu").unit == "mm"


def test_stockage_freecad() -> None:
    group = FakeParamGroup()
    paths: list[str] = []

    def param_get(path: str) -> FakeParamGroup:
        paths.append(path)
        return group

    settings = Settings(sample_catalog(), FreeCADStore(param_get, "User parameter:Test"))
    assert settings.value("Jeu") == 2.0
    settings.set("Jeu", 3.5)
    settings.set("Nombre", 4)
    settings.set("Debouchant", True)
    settings.set("Profil", "Chamfer")
    assert group.values == {
        ("Float", "Jeu"): 3.5,
        ("Integer", "Nombre"): 4,
        ("Boolean", "Debouchant"): True,
        ("String", "Profil"): "Chamfer",
    }
    assert settings.value("Nombre") == 4
    settings.reset("Jeu")
    assert ("Float", "Jeu") not in group.values
    assert set(paths) == {"User parameter:Test"}


def test_stockage_freecad_ignore_une_cle_d_un_autre_type() -> None:
    group = FakeParamGroup()
    group.values[("String", "Jeu")] = "3"
    settings = Settings(sample_catalog(), FreeCADStore(lambda _path: group, "p"))
    assert settings.value("Jeu") == 2.0


def test_dernier_utilise_dans_les_parametres_freecad() -> None:
    group = FakeParamGroup()
    settings = Settings(sample_catalog(), FreeCADStore(lambda _path: group, "p"))
    assert group.GetContents() is None  # FreeCAD rend ``None`` pour un groupe vide
    assert settings.value("Jeu") == 2.0
    settings.set_remember_last("Jeu", True)
    assert group.values == {("Boolean", "JeuRememberLast"): True}
    assert settings.record_used("Jeu", 7.0)
    assert group.values[("Float", "Jeu")] == 7.0
    settings.reset("Jeu")
    assert group.GetContents() is None


def test_valeur_refusee_ne_modifie_pas_le_stockage_ni_la_valeur_precedente() -> None:
    settings = Settings(sample_catalog(), MemoryStore())
    settings.set("Jeu", 5.0)
    for bad in (-0.001, 20.001, math.nan, "5", None):
        with pytest.raises(SettingError):
            settings.set("Jeu", bad)
    assert settings.value("Jeu") == 5.0
    with pytest.raises(SettingError) as refus:
        settings.set("Inconnu", 1)
    assert refus.value.reason is Reason.UNKNOWN_KEY


def test_valeur_enregistree_hors_bornes_ou_non_finie_donne_le_defaut() -> None:
    store = MemoryStore()
    settings = Settings(sample_catalog(), store)
    for raw in (20.001, math.nan, math.inf, -0.5):
        store.write("Jeu", Kind.FLOAT, raw)
        assert settings.value("Jeu") == 2.0
