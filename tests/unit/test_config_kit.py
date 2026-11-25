# SPDX-License-Identifier: LGPL-2.1-or-later
"""Modules génériques de configuration ``kit/config`` (ADR 0069) : catalogue, stockage, dossier."""

from __future__ import annotations

import math
import os
from pathlib import Path

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
from freecad.menuiserie.kit.config.folder import workshop_folder, write_text_atomic
from freecad.menuiserie.kit.config.store import FreeCADStore, MemoryStore, Settings
from tests.unit.aides import ROOT, imported_modules
from tests.unit.aides_reglages import FakeParamGroup

KIT = ROOT / "freecad" / "menuiserie" / "kit"


def _length(key: str = "Jeu", default: float = 2.0, *, remember: bool = True) -> Setting:
    return Setting(
        key,
        Kind.FLOAT,
        default,
        "Jeu",
        "Jeu d'usinage.",
        "Assemblages",
        unit="mm",
        minimum=0.0,
        maximum=20.0,
        remember_last=remember,
    )


def _catalog() -> Catalog:
    return Catalog(
        [
            _length(),
            Setting(
                "Debouchant",
                Kind.BOOL,
                False,
                "Débouchant",
                "Traverse.",
                "Assemblages",
                remember_last=True,
            ),
            Setting(
                "Nombre", Kind.INT, 3, "Nombre", "Nombre.", "Assemblages", minimum=1, maximum=9
            ),
            Setting(
                "Profil",
                Kind.CHOICE,
                "Round",
                "Profil",
                "Profil.",
                "Chants",
                choices=("Round", "Chamfer"),
            ),
            Setting("Dossier", Kind.PATH, "", "Dossier", "Dossier.", "Stockage"),
        ]
    )


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
        _length().check(value)
    assert refus.value.reason is reason
    assert refus.value.key == "Jeu"


@pytest.mark.parametrize("value", [0, 0.0, 20, 2.5])
def test_nombre_accepte_aux_bornes_et_entier_devenu_reel(value: float) -> None:
    checked = _length().check(value)
    assert checked == value
    assert isinstance(checked, float)


def test_entier_refuse_un_reel_et_un_booleen() -> None:
    setting = _catalog().get("Nombre")
    assert setting.check(1) == 1
    for value in (2.0, True, 0, 10):
        with pytest.raises(SettingError):
            setting.check(value)


def test_case_a_cocher_n_accepte_qu_un_booleen() -> None:
    setting = _catalog().get("Debouchant")
    assert setting.check(True) is True
    with pytest.raises(SettingError, match="wrong_type"):
        setting.check(1)


def test_choix_et_textes() -> None:
    catalog = _catalog()
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
    setting = _length()
    assert coerce(setting, None) == 2.0
    assert coerce(setting, "abîmé") == 2.0
    assert coerce(setting, 50.0) == 2.0
    assert coerce(setting, 3.0) == 3.0


def test_catalogue_cles_uniques_inconnue_et_groupes() -> None:
    with pytest.raises(ValueError, match="double"):
        Catalog([_length(), _length()])
    catalog = _catalog()
    assert len(catalog) == 5
    assert "Jeu" in catalog
    assert "Inconnu" not in catalog
    with pytest.raises(SettingError) as refus:
        catalog.get("Inconnu")
    assert refus.value.reason is Reason.UNKNOWN_KEY
    assert catalog.groups() == ("Assemblages", "Chants", "Stockage")


# --- stockage et « Dernier utilisé » -------------------------------------------------------------


def test_valeur_par_defaut_puis_enregistree_puis_retablie() -> None:
    settings = Settings(_catalog(), MemoryStore())
    assert settings.value("Jeu") == 2.0
    assert not settings.is_modified("Jeu")
    assert settings.set("Jeu", 3) == 3.0
    assert settings.value("Jeu") == 3.0
    assert settings.is_modified("Jeu")
    settings.reset("Jeu")
    assert settings.value("Jeu") == 2.0


def test_valeur_refusee_n_est_pas_ecrite() -> None:
    store = MemoryStore()
    settings = Settings(_catalog(), store)
    with pytest.raises(SettingError):
        settings.set("Jeu", 99.0)
    assert store.values == {}


def test_valeur_abimee_dans_le_stockage_donne_le_defaut() -> None:
    store = MemoryStore()
    store.write("Jeu", Kind.FLOAT, 1e9)
    assert Settings(_catalog(), store).value("Jeu") == 2.0


def test_dernier_utilise() -> None:
    settings = Settings(_catalog(), MemoryStore())
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
    settings = Settings(_catalog(), MemoryStore())
    with pytest.raises(ValueError, match="non prévu"):
        settings.set_remember_last("Nombre", True)
    assert not settings.remembers_last("Nombre")


def test_tout_retablir() -> None:
    settings = Settings(_catalog(), MemoryStore())
    settings.set("Jeu", 5.0)
    settings.set("Profil", "Chamfer")
    settings.set_remember_last("Debouchant", True)
    settings.reset_all()
    assert [settings.is_modified(s.key) for s in settings.catalog] == [False] * 5
    assert not settings.remembers_last("Debouchant")
    assert settings.setting("Jeu").unit == "mm"


def test_stockage_freecad() -> None:
    group = FakeParamGroup()
    paths: list[str] = []

    def param_get(path: str) -> FakeParamGroup:
        paths.append(path)
        return group

    settings = Settings(_catalog(), FreeCADStore(param_get, "User parameter:Test"))
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
    settings = Settings(_catalog(), FreeCADStore(lambda _path: group, "p"))
    assert settings.value("Jeu") == 2.0


# --- dossier ------------------------------------------------------------------------------------


def test_dossier_de_l_atelier(tmp_path: Path) -> None:
    fallback = tmp_path / "Menuiserie"
    assert workshop_folder("", "", fallback) == fallback
    assert workshop_folder("  ", " ", fallback) == fallback
    legacy = tmp_path / "ancien" / "materiaux.json"
    assert workshop_folder("", str(legacy), fallback) == legacy.parent
    custom = tmp_path / "nuage"
    assert workshop_folder(f" {custom} ", str(legacy), fallback) == custom
    assert workshop_folder("~/atelier", "", fallback) == Path("~/atelier").expanduser()


def test_ecriture_atomique(tmp_path: Path) -> None:
    target = tmp_path / "sous" / "atelier.json"
    write_text_atomic(target, "un\n")
    write_text_atomic(target, "deux\n", prefix=".atelier-")
    assert target.read_text(encoding="utf-8") == "deux\n"
    assert sorted(p.name for p in target.parent.iterdir()) == ["atelier.json"]


def test_ecriture_atomique_en_echec_garde_l_ancien_fichier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "atelier.json"
    target.write_text("ancien", encoding="utf-8")

    def refused(_source: object, _target: object) -> None:
        raise OSError("disque plein")

    monkeypatch.setattr("os.replace", refused)
    with pytest.raises(OSError, match="disque plein"):
        write_text_atomic(target, "nouveau")
    assert target.read_text(encoding="utf-8") == "ancien"
    assert [p.name for p in tmp_path.iterdir()] == ["atelier.json"]


# --- indépendance ---------------------------------------------------------------------------------


def test_kit_n_importe_ni_l_atelier_ni_freecad_ni_qt() -> None:
    """``kit/`` se copie dans un autre atelier : aucun import de Menuiserie hors de ``kit``,
    ni de FreeCAD, ni de Qt (ADR 0069)."""
    forbidden = ("FreeCAD", "FreeCADGui", "Part", "PySide", "PySide2", "PySide6", "pivy")
    files = sorted(KIT.rglob("*.py"))
    assert files
    for path in files:
        modules = imported_modules(path)
        assert not [m for m in modules if m.split(".")[0] in forbidden], path.name
        own = [m for m in modules if m.startswith("freecad.menuiserie")]
        assert all(m.startswith("freecad.menuiserie.kit") for m in own), (path.name, own)


# --- cas limites complémentaires (revue testeur CA-a) -----------------------------------------


def test_entier_trop_grand_pour_un_reel_est_refuse_proprement() -> None:
    """Un entier hors de portée d'un ``float`` doit être un refus codé, pas ``OverflowError``
    (sinon ``coerce`` et ``record_used`` laissent passer l'exception)."""
    setting = _length()
    with pytest.raises(SettingError) as refus:
        setting.check(10**400)
    assert refus.value.reason is Reason.ABOVE_MAXIMUM
    with pytest.raises(SettingError):
        setting.check(-(10**400))
    assert coerce(setting, 10**400) == setting.default


def test_dernier_utilise_dans_les_parametres_freecad() -> None:
    group = FakeParamGroup()
    settings = Settings(_catalog(), FreeCADStore(lambda _path: group, "p"))
    assert group.GetContents() is None  # FreeCAD rend ``None`` pour un groupe vide
    assert settings.value("Jeu") == 2.0
    settings.set_remember_last("Jeu", True)
    assert group.values == {("Boolean", "JeuRememberLast"): True}
    assert settings.record_used("Jeu", 7.0)
    assert group.values[("Float", "Jeu")] == 7.0
    settings.reset("Jeu")
    assert group.GetContents() is None


def test_valeur_refusee_ne_modifie_pas_le_stockage_ni_la_valeur_precedente() -> None:
    settings = Settings(_catalog(), MemoryStore())
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
    settings = Settings(_catalog(), store)
    for raw in (20.001, math.nan, math.inf, -0.5):
        store.write("Jeu", Kind.FLOAT, raw)
        assert settings.value("Jeu") == 2.0


def test_dossier_relatif_ou_invalide_ignore(tmp_path: Path) -> None:
    """Un chemin relatif ou avec un octet nul ne dépend pas du dossier courant : il est ignoré."""
    fallback = tmp_path / "repli"
    legacy = tmp_path / "ancien" / "materiaux.json"
    assert workshop_folder("atelier", str(legacy), fallback) == legacy.parent
    assert workshop_folder("a\0b", "", fallback) == fallback
    assert workshop_folder("", "materiaux.json", fallback) == fallback
    assert workshop_folder("", "x\0y.json", fallback) == fallback


def test_cle_reservee_au_dernier_utilise_refusee() -> None:
    """Une clé ``…RememberLast`` entrerait en collision avec la case « Dernier utilisé »."""
    with pytest.raises(ValueError, match="réservée"):
        Catalog([_length(key=f"Cote{REMEMBER_SUFFIX}")])


def test_ecriture_atomique_ferme_le_descripteur_si_ouverture_echoue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si ``os.fdopen`` échoue, le descripteur est fermé et aucun fichier temporaire ne reste."""
    closed: list[int] = []
    real_close = os.close

    def fail(*_args: object, **_kwargs: object) -> object:
        raise OSError("ouverture impossible")

    def close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(os, "fdopen", fail)
    monkeypatch.setattr(os, "close", close)
    with pytest.raises(OSError, match="ouverture impossible"):
        write_text_atomic(tmp_path / "f.json", "{}")
    assert len(closed) == 1
    assert list(tmp_path.iterdir()) == []
