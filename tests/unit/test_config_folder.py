# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dossier de l'atelier et écriture atomique ``kit/config.folder`` (ADR 0069)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from freecad.menuiserie.kit.config.folder import workshop_folder, write_text_atomic

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


def test_dossier_relatif_ou_invalide_ignore(tmp_path: Path) -> None:
    """Un chemin relatif ou avec un octet nul ne dépend pas du dossier courant : il est ignoré."""
    fallback = tmp_path / "repli"
    legacy = tmp_path / "ancien" / "materiaux.json"
    assert workshop_folder("atelier", str(legacy), fallback) == legacy.parent
    assert workshop_folder("a\0b", "", fallback) == fallback
    assert workshop_folder("", "materiaux.json", fallback) == fallback
    assert workshop_folder("", "x\0y.json", fallback) == fallback


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


@pytest.mark.skipif(os.name == "nt", reason="droits POSIX")
def test_ecriture_garde_les_droits_du_fichier_existant(tmp_path: Path) -> None:
    target = tmp_path / "atelier.json"
    target.write_text("ancien", encoding="utf-8")
    target.chmod(0o640)
    write_text_atomic(target, "neuf")
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


@pytest.mark.skipif(os.name == "nt", reason="droits POSIX")
def test_fichier_neuf_suit_le_masque_de_l_utilisateur(tmp_path: Path) -> None:
    previous = os.umask(0o027)
    try:
        target = tmp_path / "neuf.json"
        write_text_atomic(target, "x")
    finally:
        os.umask(previous)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


@pytest.mark.skipif(os.name == "nt", reason="liens symboliques")
def test_un_lien_symbolique_est_remplace_par_un_fichier(tmp_path: Path) -> None:
    real = tmp_path / "reel.json"
    real.write_text("cible", encoding="utf-8")
    link = tmp_path / "atelier.json"
    link.symlink_to(real)
    write_text_atomic(link, "neuf")
    assert not link.is_symlink()
    assert real.read_text(encoding="utf-8") == "cible"
