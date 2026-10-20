# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites et invalides de J1a (critères A2 à A8), en complément des tests du dev.

Un défaut connu est marqué ``xfail(strict=True)`` : le test échoue tant que le code de
production n'est pas corrigé, puis doit être « dé-marqué » par le dev qui corrige.
"""

from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path

import pytest

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.materials import (
    BUILTIN_SOURCE,
    MAX_ID_LENGTH,
    MAX_MATERIALS,
    MAX_NAME_LENGTH,
    MAX_THICKNESS_MM,
    MAX_THICKNESSES,
    LibraryIssue,
    Material,
    MaterialKind,
    Severity,
    load_library,
    merge_materials,
    parse_materials,
    read_materials_file,
)
from freecad.menuiserie.core.part_model import (
    DEFAULT_PANEL_ALLOWANCES,
    DEFAULT_SOLID_ALLOWANCES,
    MAX_DIMENSION_MM,
    MIN_DIMENSION_MM,
    Allowances,
    Dimensions,
    GrainDirection,
    InvalidDimensionsError,
    allowances_after_material_change,
    grain_after_material_change,
    is_standard_thickness,
    mass_kg,
    rough_dimensions,
    volume_m3,
)
from tests.unit.aides import OAK, SOURCE, document, errors, make_material, requires_symlinks, write

BUILTIN_PATH = DATA_DIR / "materiaux.json"


def entry(**changes: object) -> dict[str, object]:
    """Entrée valide « erable », modifiée par ``changes``."""
    data: dict[str, object] = {
        "id": "erable",
        "kind": "solid",
        "name": "Érable",
        "density": 650,
        "thicknesses": [22, 27],
        "color": "#E8D2A8",
    }
    data.update(changes)
    return data


def parse_one(raw: dict[str, object]) -> tuple[list[Material], list[LibraryIssue]]:
    """Analyse ``OAK`` suivi de ``raw`` ; ``OAK`` doit toujours rester chargé."""
    materials, issues = parse_materials(document(OAK, raw), SOURCE)
    assert materials[0].id == "chene"
    return materials[1:], issues


def builtin() -> list[Material]:
    materials, issues = read_materials_file(BUILTIN_PATH, BUILTIN_SOURCE)
    assert issues == []
    return materials


# --- A2 : valeurs limites acceptées -----------------------------------------------------

ACCEPTED_ENTRIES = [
    pytest.param(entry(id="a" * MAX_ID_LENGTH), id="id-64-caracteres"),
    pytest.param(entry(id="1"), id="id-un-chiffre"),
    pytest.param(entry(id="a-1-b"), id="id-tirets-internes"),
    pytest.param(entry(name="x" * MAX_NAME_LENGTH), id="name-80-caracteres"),
    pytest.param(entry(name="\U0001f333" * MAX_NAME_LENGTH), id="name-80-emojis"),
    pytest.param(entry(name="  " + "x" * MAX_NAME_LENGTH + "\t\n"), id="name-80-apres-strip"),
    pytest.param(entry(name={"en": "Maple"}), id="name-anglais-seul"),
    pytest.param(entry(density=50), id="density-minimum"),
    pytest.param(entry(density=2000), id="density-maximum"),
    pytest.param(entry(density=1e3), id="density-notation-exposant"),
    pytest.param(entry(thicknesses=[MAX_THICKNESS_MM]), id="ep-maximum"),
    pytest.param(entry(thicknesses=[1e-3]), id="ep-tres-fine"),
    pytest.param(entry(thicknesses=list(range(1, MAX_THICKNESSES + 1))), id="ep-50-valeurs"),
    pytest.param(entry(color="#abcdef"), id="color-minuscules"),
    pytest.param(entry(has_grain=False), id="has-grain-faux-sur-massif"),
]


@pytest.mark.parametrize("raw", ACCEPTED_ENTRIES)
def test_valeur_limite_acceptee(raw: dict[str, object]) -> None:
    materials, issues = parse_one(raw)
    assert issues == []
    assert [m.id for m in materials] == [raw["id"]]


def test_libelle_nettoye_des_espaces_insecables() -> None:
    [material], issues = parse_one(entry(name="\u00a0Érable\u2003"))
    assert issues == []
    assert material.name() == "Érable"


# --- A2 : valeurs invalides supplémentaires ---------------------------------------------

REJECTED_ENTRIES = [
    pytest.param(entry(id="erable\n"), "id", id="id-saut-de-ligne-final"),
    pytest.param(entry(id="a--b"), "id", id="id-double-tiret"),
    pytest.param(entry(id="-erable"), "id", id="id-tiret-initial"),
    pytest.param(entry(id="\uff45rable"), "id", id="id-pleine-chasse"),
    pytest.param(entry(id="e\u0301rable"), "id", id="id-accent-combinant"),
    pytest.param(entry(id=None), "id", id="id-null"),
    pytest.param(entry(id=True), "id", id="id-booleen"),
    pytest.param(entry(kind="Solid"), "kind", id="kind-majuscule"),
    pytest.param(entry(kind=" solid"), "kind", id="kind-espace"),
    pytest.param(entry(kind=None), "kind", id="kind-null"),
    pytest.param(entry(name=None), "name", id="name-null"),
    pytest.param(entry(name=["Érable"]), "name", id="name-liste"),
    pytest.param(entry(name="Éra\tble"), "name", id="name-tabulation-interne"),
    pytest.param(entry(name="Éra\x7fble"), "name", id="name-del"),
    pytest.param(entry(name="Éra\x85ble"), "name", id="name-controle-c1"),
    pytest.param(entry(name="x" * (MAX_NAME_LENGTH + 1)), "name", id="name-81-caracteres"),
    pytest.param(entry(name={"fr": "Érable", "EN": "Maple"}), "name", id="name-2e-langue"),
    pytest.param(entry(name={"fr": "Érable", "en": ""}), "name", id="name-2e-libelle-vide"),
    pytest.param(entry(name={"": "Érable"}), "name", id="name-langue-vide"),
    pytest.param(entry(name={"én": "Maple"}), "name", id="name-langue-accentuee"),
    pytest.param(entry(density=None), "density", id="density-null"),
    pytest.param(entry(density=False), "density", id="density-faux"),
    pytest.param(entry(density=[650]), "density", id="density-liste"),
    pytest.param(entry(density=49.999), "density", id="density-juste-sous-minimum"),
    pytest.param(entry(density=0), "density", id="density-nulle"),
    pytest.param(entry(density=-650), "density", id="density-negative"),
    pytest.param(entry(density=10**400), "density", id="density-entier-geant"),
    pytest.param(entry(density=float("nan")), "density", id="density-nan"),
    pytest.param(entry(thicknesses=[18, None]), "thicknesses", id="ep-null"),
    pytest.param(entry(thicknesses=[[18]]), "thicknesses", id="ep-imbriquee"),
    pytest.param(entry(thicknesses=[False]), "thicknesses", id="ep-faux"),
    pytest.param(entry(thicknesses=[1e-400]), "thicknesses", id="ep-zero-par-arrondi"),
    pytest.param(entry(thicknesses=[300.0001]), "thicknesses", id="ep-juste-au-dessus"),
    pytest.param(entry(thicknesses=[10**400]), "thicknesses", id="ep-entier-geant"),
    pytest.param(entry(thicknesses={"a": 18}), "thicknesses", id="ep-objet"),
    pytest.param(entry(color="#E8D2A8 "), "color", id="color-espace-final"),
    pytest.param(entry(color="#\uff11\uff12\uff13\uff14\uff15\uff16"), "color", id="color-pleine"),
    pytest.param(entry(color="#E8D2A8FF"), "color", id="color-avec-alpha"),
    pytest.param(entry(color=None), "color", id="color-null"),
    pytest.param(entry(has_grain=None), "has_grain", id="has-grain-null"),
    pytest.param(entry(has_grain=0), "has_grain", id="has-grain-zero"),
    pytest.param(entry(has_grain="true"), "has_grain", id="has-grain-texte"),
]


@pytest.mark.parametrize(("raw", "field"), REJECTED_ENTRIES)
def test_valeur_invalide_rejetee(raw: dict[str, object], field: str) -> None:
    materials, issues = parse_one(raw)
    assert materials == []
    [issue] = errors(issues)
    assert issue.params["field"] == field
    assert issue.source == SOURCE
    assert SOURCE in issue.format()


def test_doublon_apres_entree_rejetee_conserve_la_premiere_valide() -> None:
    first = entry(density="x")
    second = entry()
    materials, issues = parse_materials(document(first, second), SOURCE)
    assert [m.id for m in materials] == ["erable"]
    [issue] = errors(issues)
    assert issue.params["field"] == "density"


def test_trois_doublons_deux_erreurs() -> None:
    materials, issues = parse_materials(document(entry(), entry(), entry()), SOURCE)
    assert len(materials) == 1
    assert [i.params["field"] for i in errors(issues)] == ["id", "id"]


def with_duplicate_density(value: str) -> str:
    """Document dont l'entrée « erable » répète la clé ``density`` avec ``value``."""
    raw = json.dumps(entry())[:-1] + f', "density": {value}}}'
    return f'{{"format": 1, "materials": [{raw}]}}'


def test_cle_en_double_rejette_l_entree_meme_si_les_valeurs_sont_valides(tmp_path: Path) -> None:
    # json.loads garderait la dernière occurrence : l'ambiguïté est signalée, l'entrée rejetée.
    materials, issues = read_materials_file(write(tmp_path, with_duplicate_density("700")))
    assert materials == []
    [issue] = errors(issues)
    assert issue.material_id == "erable"
    assert issue.params["field"] == "density"


def test_cle_en_double_invalide_rejette_l_entree(tmp_path: Path) -> None:
    materials, issues = read_materials_file(write(tmp_path, with_duplicate_density('"lourd"')))
    assert materials == []
    assert errors(issues)[0].params["field"] == "density"


def test_exactement_500_materiaux_sans_anomalie() -> None:
    entries = [entry(id=f"m{i}", name=f"Matériau {i}") for i in range(MAX_MATERIALS)]
    materials, issues = parse_materials(document(*entries), SOURCE)
    assert issues == []
    assert len(materials) == MAX_MATERIALS


def test_chaine_nan_n_est_pas_une_constante_json(tmp_path: Path) -> None:
    text = json.dumps(document(OAK, entry(density="NaN")))
    materials, issues = read_materials_file(write(tmp_path, text))
    assert [m.id for m in materials] == ["chene"]
    assert errors(issues)[0].params["field"] == "density"


def test_libelle_avec_demi_substitut_isole_rejete(tmp_path: Path) -> None:
    text = json.dumps(document(OAK, entry())).replace("\\u00c9rable", "\\ud800rable")
    assert "\\ud800" in text
    materials, issues = read_materials_file(write(tmp_path, text))
    for material in materials:
        for label in material.names.values():
            label.encode("utf-8")
    assert [m.id for m in materials] == ["chene"]
    assert errors(issues)[0].params["field"] == "name"


def test_libelle_avec_paire_de_substituts_valide_accepte(tmp_path: Path) -> None:
    text = json.dumps(document(entry(name="Arbre \U0001f333")))
    assert "\\ud83c\\udf33" in text
    [material], issues = read_materials_file(write(tmp_path, text))
    assert issues == []
    assert material.name() == "Arbre \U0001f333"


# --- A3 : fichiers limites -----------------------------------------------------------------

FILE_RULES = [
    pytest.param(b"   \n\t ", id="espaces-seuls"),
    pytest.param(b"null", id="racine-null"),
    pytest.param(b"true", id="racine-booleen"),
    pytest.param(b"1", id="racine-nombre"),
    pytest.param(b"{}", id="objet-vide"),
    pytest.param(b'{"format": null, "materials": []}', id="format-null"),
    pytest.param(b'{"format": 1e0, "materials": []}', id="format-exposant"),
    pytest.param(b'{"format": -1, "materials": []}', id="format-negatif"),
    pytest.param(b'{"format": 1, "materials": null}', id="materials-null"),
    pytest.param(b'{"format": 1, "materials": "[]"}', id="materials-chaine"),
    pytest.param(b'{"format": 1, "materials": []} x', id="donnees-en-trop"),
    pytest.param(b'{"format": 1, "materials": [],}', id="virgule-finale"),
    pytest.param(b"{'format': 1, 'materials': []}", id="apostrophes"),
    pytest.param(b'{"format": 1, "materials": []}\x00', id="octet-nul"),
    pytest.param("\ufeff".encode("utf-16"), id="utf16"),
    pytest.param(b'{"format": 1, "materials": ["\xc3"]}', id="utf8-tronque"),
]


@pytest.mark.parametrize("content", FILE_RULES)
def test_fichier_limite_ignore_avec_une_seule_erreur(tmp_path: Path, content: bytes) -> None:
    path = write(tmp_path, content)
    materials, issues = read_materials_file(path, "utilisateur")
    assert materials == []
    [issue] = issues
    assert issue.severity is Severity.ERROR
    assert issue.source == "utilisateur"


def test_bom_utf8_accepte(tmp_path: Path) -> None:
    # PowerShell 5 (Windows) écrit un BOM en tête des fichiers UTF-8.
    path = write(tmp_path, b"\xef\xbb\xbf" + json.dumps(document(OAK)).encode())
    materials, issues = read_materials_file(path, "utilisateur")
    assert issues == []
    assert [m.id for m in materials] == ["chene"]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="tubes nommés indisponibles")
def test_tube_nomme_refuse_sans_blocage(tmp_path: Path) -> None:
    fifo = tmp_path / "materiaux.json"
    os.mkfifo(fifo)
    materials, [issue] = read_materials_file(fifo)
    assert materials == []
    assert issue.severity is Severity.ERROR


@requires_symlinks
def test_lien_symbolique_vers_un_fichier_accepte(tmp_path: Path) -> None:
    target = write(tmp_path, json.dumps(document(OAK)), "cible.json")
    link = tmp_path / "materiaux.json"
    link.symlink_to(target)
    materials, issues = read_materials_file(link)
    assert issues == []
    assert [m.id for m in materials] == ["chene"]


def test_format_entier_geant_deja_decode_sans_exception() -> None:
    materials, [issue] = parse_materials({"format": 10**5000, "materials": []}, SOURCE)
    assert materials == []
    assert issue.severity is Severity.ERROR


# --- A4 : fusion ---------------------------------------------------------------------------


def test_remplacement_vers_le_libelle_d_un_autre_integre_rejete() -> None:
    library, [issue] = merge_materials(builtin(), [make_material("chene", "Hêtre")], SOURCE)
    assert library.get("chene").name() == "Chêne"
    assert library.get("hetre").name() == "Hêtre"
    assert issue.severity is Severity.ERROR
    assert issue.params["other"] == "hetre"


def test_libelle_en_double_dans_le_fichier_utilisateur(tmp_path: Path) -> None:
    text = json.dumps(document(entry(), entry(id="erable-sycomore")))
    path = write(tmp_path, text)
    library, [issue] = load_library(BUILTIN_PATH, path)
    assert "erable" in library
    assert "erable-sycomore" not in library
    assert issue.material_id == "erable-sycomore"
    assert issue.source == str(path)


def test_libelles_identiques_apres_nettoyage_en_double(tmp_path: Path) -> None:
    path = write(tmp_path, json.dumps(document(entry(id="chene-x", name="  Chêne "))))
    library, [issue] = load_library(BUILTIN_PATH, path)
    assert "chene-x" not in library
    assert issue.params["other"] == "chene"


def test_fichier_utilisateur_dossier_n_empeche_pas_la_bibliotheque(tmp_path: Path) -> None:
    library, [issue] = load_library(BUILTIN_PATH, tmp_path)
    assert len(library) == len(builtin())
    assert issue.source == str(tmp_path)


def test_fusion_ne_modifie_pas_les_listes_fournies() -> None:
    integrated = builtin()
    snapshot = list(integrated)
    user = [make_material("chene", "Chêne rouvre"), make_material("erable", "Érable")]
    merge_materials(integrated, user, SOURCE)
    assert integrated == snapshot
    assert [m.id for m in user] == ["chene", "erable"]


def test_remplacement_change_la_famille() -> None:
    replacement = make_material("hetre", "Hêtre lamellé", MaterialKind.PLYWOOD)
    library, _ = merge_materials(builtin(), [replacement], SOURCE)
    assert library.get("hetre").kind is MaterialKind.PLYWOOD
    assert library.find_by_name("Hêtre lamellé") is replacement


def test_echange_de_libelles_entre_remplacements_independant_de_l_ordre() -> None:
    first = make_material("chene", "Chêne rouvre")
    second = make_material("hetre", "Chêne")
    in_order, issues_in_order = merge_materials(builtin(), [first, second], SOURCE)
    reversed_order, issues_reversed = merge_materials(builtin(), [second, first], SOURCE)
    assert errors(issues_in_order) == []
    assert errors(issues_reversed) == []
    assert list(in_order) == list(reversed_order)


def test_libelle_unicode_decompose_considere_comme_doublon() -> None:
    decomposed = unicodedata.normalize("NFD", "Chêne")
    assert decomposed != "Chêne"
    library, issues = merge_materials(builtin(), [make_material("chene-x", decomposed)], SOURCE)
    assert "chene-x" not in library
    assert errors(issues)[0].params["other"] == "chene"


# --- A5 : calculs ----------------------------------------------------------------------------


def test_debit_exactement_a_la_borne_maximale() -> None:
    finished = Dimensions(MAX_DIMENSION_MM - 20, 200, 22)
    assert rough_dimensions(finished, DEFAULT_SOLID_ALLOWANCES).length == MAX_DIMENSION_MM


def test_volume_et_masse_aux_bornes() -> None:
    largest = Dimensions(MAX_DIMENSION_MM, MAX_DIMENSION_MM, MAX_DIMENSION_MM)
    assert volume_m3(largest) == pytest.approx(8000.0)
    assert mass_kg(largest, 2000) == pytest.approx(16_000_000.0)
    smallest = Dimensions(MIN_DIMENSION_MM, MIN_DIMENSION_MM, MIN_DIMENSION_MM)
    assert volume_m3(smallest) == pytest.approx(1e-12, rel=1e-12)


def test_arrondis_des_cotes_decimales() -> None:
    rough = rough_dimensions(Dimensions(0.1, 0.2, 0.3), Allowances(0.2, 0.1, 0.0))
    assert rough.length == pytest.approx(0.3, abs=1e-12)
    assert rough.width == pytest.approx(0.3, abs=1e-12)
    assert volume_m3(Dimensions(799.9, 199.9, 21.9)) == pytest.approx(
        799.9 * 199.9 * 21.9 / 1e9, rel=1e-12
    )


def test_masse_proportionnelle_a_la_densite_de_la_bibliotheque() -> None:
    library, _ = load_library(BUILTIN_PATH, None)
    board = Dimensions(800, 200, 22)
    for material in library:
        assert mass_kg(board, material.density) == pytest.approx(
            0.00352 * material.density, abs=1e-9
        )


# --- A6 : messages et types ----------------------------------------------------------------


def test_cotes_immuables() -> None:
    board = Dimensions(800, 200, 22)
    with pytest.raises(AttributeError):
        board.length = 1000  # type: ignore[misc]


def test_surcote_moins_zero_equivaut_a_zero() -> None:
    assert Allowances(-0.0, 0, 0) == DEFAULT_PANEL_ALLOWANCES


@pytest.mark.parametrize("value", [10**3, 20_000.0])
def test_cotes_entieres_et_borne_acceptees(value: float) -> None:
    assert Dimensions(value, value, value).thickness == float(value)


def test_message_ne_montre_pas_une_valeur_arrondie_a_la_borne() -> None:
    with pytest.raises(InvalidDimensionsError) as error:
        Dimensions(MAX_DIMENSION_MM + 0.01, 200, 22)
    assert error.value.params["value"] != error.value.params["max"]


# --- A7 : changement de matériau -----------------------------------------------------------


@pytest.mark.parametrize(
    ("material", "current", "expected"),
    [
        (
            make_material("mdf-veine", "MDF veiné", MaterialKind.MDF, has_grain=True),
            GrainDirection.NONE,
            GrainDirection.LENGTH,
        ),
        (
            make_material("mdf-veine", "MDF veiné", MaterialKind.MDF, has_grain=True),
            GrainDirection.WIDTH,
            GrainDirection.WIDTH,
        ),
        (
            make_material("loupe", "Loupe", MaterialKind.SOLID, has_grain=False),
            GrainDirection.WIDTH,
            GrainDirection.NONE,
        ),
    ],
    ids=["panneau-avec-fil-depuis-none", "panneau-avec-fil-conserve", "massif-sans-fil"],
)
def test_fil_suit_has_grain_et_non_la_famille(
    material: Material, current: GrainDirection, expected: GrainDirection
) -> None:
    assert grain_after_material_change(material, current) is expected


def test_surcotes_aller_retour_massif_panneau_massif() -> None:
    step = allowances_after_material_change(
        MaterialKind.SOLID, MaterialKind.MELAMINE, Allowances(20, 5, 0)
    )
    assert step == DEFAULT_PANEL_ALLOWANCES
    back = allowances_after_material_change(MaterialKind.MELAMINE, MaterialKind.SOLID, step)
    assert back == DEFAULT_SOLID_ALLOWANCES


def test_surcotes_moins_zero_considerees_par_defaut() -> None:
    current = Allowances(-0.0, -0.0, -0.0)
    result = allowances_after_material_change(MaterialKind.MDF, MaterialKind.SOLID, current)
    assert result == DEFAULT_SOLID_ALLOWANCES


def test_surcote_presque_par_defaut_conservee() -> None:
    current = Allowances(20.000000001, 5, 0)
    result = allowances_after_material_change(MaterialKind.SOLID, MaterialKind.MDF, current)
    assert result is current


# --- A8 : épaisseurs standard -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("material_id", "thickness", "expected"),
    [
        ("chene", 54.05, True),
        ("chene", 53.95, True),
        ("chene", 54.06, False),
        ("cp-bouleau", 6.45, True),
        ("cp-bouleau", 6.55, True),
        ("cp-bouleau", 6.44, False),
        ("cp-bouleau", 0, False),
        ("cp-bouleau", -18, False),
        ("cp-bouleau", float("nan"), False),
        ("cp-bouleau", float("inf"), False),
    ],
)
def test_epaisseur_standard_aux_bornes(material_id: str, thickness: float, expected: bool) -> None:
    library, _ = load_library(BUILTIN_PATH, None)
    assert is_standard_thickness(library.get(material_id), thickness) is expected


def test_tolerance_negative_ne_reconnait_rien() -> None:
    library, _ = load_library(BUILTIN_PATH, None)
    assert not is_standard_thickness(library.get("cp-bouleau"), 18, tolerance=-1)
