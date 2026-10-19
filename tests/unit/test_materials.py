# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bibliothèque de matériaux : lecture, validation et fusion (critères A1 à A4)."""

from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path

import pytest

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.i18n import CONTEXT, QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import (
    BUILTIN_SOURCE,
    MAX_FILE_BYTES,
    MAX_MATERIALS,
    LibraryIssue,
    Material,
    MaterialKind,
    MaterialLibrary,
    Severity,
    UnknownMaterialError,
    load_library,
    merge_materials,
    parse_materials,
    read_materials_file,
    to_finite_float,
)

BUILTIN_PATH = DATA_DIR / "materiaux.json"
SOURCE = "/chemin/utilisateur/materiaux.json"

REFERENCE: dict[str, object] = {
    "id": "chene",
    "kind": "solid",
    "name": {"fr": "Chêne", "en": "Oak"},
    "density": 710,
    "thicknesses": [18, 22],
    "color": "#B8875A",
}


def entry(**changes: object) -> dict[str, object]:
    """Entrée valide « erable », modifiée par ``changes``."""
    data: dict[str, object] = {
        "id": "erable",
        "kind": "solid",
        "name": {"fr": "Érable", "en": "Maple"},
        "density": 650,
        "thicknesses": [22, 27],
        "color": "#E8D2A8",
    }
    data.update(changes)
    return data


def entry_without(key: str) -> dict[str, object]:
    data = entry()
    del data[key]
    return data


def document(*entries: object, **root: object) -> dict[str, object]:
    return {"format": 1, "materials": list(entries), **root}


def write(tmp_path: Path, content: str | bytes, name: str = "materiaux.json") -> Path:
    path = tmp_path / name
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


def make_material(
    material_id: str, label: str, kind: MaterialKind = MaterialKind.SOLID
) -> Material:
    return Material(
        id=material_id,
        kind=kind,
        names={"fr": label},
        density=600.0,
        thicknesses=(18.0, 22.0),
        color=(10, 20, 30),
        has_grain=not kind.is_panel,
    )


def errors(issues: list[LibraryIssue]) -> list[LibraryIssue]:
    return [issue for issue in issues if issue.severity is Severity.ERROR]


# --- A1 : bibliothèque intégrée -------------------------------------------------------

BUILTIN_TABLE = [
    ("chene", "solid", "Chêne", "Oak", 710, (18, 22, 27, 34, 41, 54), "#B8875A", True),
    ("hetre", "solid", "Hêtre", "Beech", 720, (18, 22, 27, 34, 41, 54), "#D9B48A", True),
    ("frene", "solid", "Frêne", "Ash", 690, (18, 22, 27, 34, 41, 54), "#E3CFA5", True),
    ("noyer", "solid", "Noyer", "Walnut", 650, (18, 22, 27, 34, 41), "#6B4A33", True),
    ("merisier", "solid", "Merisier", "Cherry", 620, (18, 22, 27, 34, 41), "#B5654A", True),
    (
        "pin-sylvestre",
        "solid",
        "Pin sylvestre",
        "Scots pine",
        520,
        (18, 22, 27, 34, 45),
        "#E8C68E",
        True,
    ),
    (
        "sapin-epicea",
        "solid",
        "Sapin \u2013 épicéa",
        "Fir \u2013 spruce",
        450,
        (18, 22, 27, 34, 45),
        "#EEDDB8",
        True,
    ),
    ("douglas", "solid", "Douglas", "Douglas fir", 530, (22, 27, 34, 45), "#D49A6A", True),
    (
        "cp-bouleau",
        "plywood",
        "Contreplaqué bouleau",
        "Birch plywood",
        680,
        (4, 6.5, 9, 12, 15, 18, 21, 24),
        "#E6D3B0",
        True,
    ),
    (
        "cp-peuplier",
        "plywood",
        "Contreplaqué peuplier",
        "Poplar plywood",
        450,
        (5, 10, 15, 18, 22),
        "#EADFC4",
        True,
    ),
    ("mdf", "mdf", "MDF", "MDF", 750, (3, 6, 10, 12, 16, 19, 22, 25), "#A98B6D", False),
    (
        "melamine-blanc",
        "melamine",
        "Mélaminé blanc",
        "White melamine",
        650,
        (8, 16, 19, 22),
        "#F2F2F0",
        False,
    ),
]


def test_bibliotheque_integree_sans_anomalie() -> None:
    materials, issues = read_materials_file(BUILTIN_PATH, BUILTIN_SOURCE)
    assert issues == []
    ids = [m.id for m in materials]
    labels = [m.name("fr") for m in materials]
    assert len(set(ids)) == len(ids)
    assert len(set(labels)) == len(labels)
    assert {row[0] for row in BUILTIN_TABLE} <= set(ids)
    assert len(MaterialLibrary(materials)) >= 12


@pytest.mark.parametrize("row", BUILTIN_TABLE, ids=[row[0] for row in BUILTIN_TABLE])
def test_bibliotheque_integree_conforme_a_la_specification(
    row: tuple[str, str, str, str, float, tuple[float, ...], str, bool],
) -> None:
    material_id, kind, fr, en, density, thicknesses, color, has_grain = row
    library, _ = load_library(BUILTIN_PATH, None)
    material = library.get(material_id)
    assert material.kind is MaterialKind(kind)
    assert material.name("fr") == fr
    assert material.name("en") == en
    assert material.density == density
    assert material.thicknesses == thicknesses
    assert material.color == tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
    assert material.has_grain is has_grain


def test_chargement_de_la_bibliotheque_integree_seule() -> None:
    library, issues = load_library(BUILTIN_PATH, None)
    assert issues == []
    assert library.default_material().id == "chene"


# --- A2 : une règle de validation par cas ----------------------------------------------

LONG_LIST = list(range(1, 52))

ENTRY_RULES = [
    pytest.param(entry_without("id"), "id", None, id="id-absent"),
    pytest.param(entry(id=42), "id", None, id="id-non-chaine"),
    pytest.param(entry(id="Érable"), "id", None, id="id-motif"),
    pytest.param(entry(id="erable-"), "id", None, id="id-tiret-final"),
    pytest.param(entry(id=""), "id", None, id="id-vide"),
    pytest.param(entry(id="a" * 65), "id", None, id="id-trop-long"),
    pytest.param(entry_without("kind"), "kind", "erable", id="kind-absent"),
    pytest.param(entry(kind="bois"), "kind", "erable", id="kind-inconnu"),
    pytest.param(entry(kind=["solid"]), "kind", "erable", id="kind-non-chaine"),
    pytest.param(entry_without("name"), "name", "erable", id="name-absent"),
    pytest.param(entry(name=42), "name", "erable", id="name-type"),
    pytest.param(entry(name={}), "name", "erable", id="name-objet-vide"),
    pytest.param(entry(name={"FR": "Érable"}), "name", "erable", id="name-langue"),
    pytest.param(entry(name={"fra": "Érable"}), "name", "erable", id="name-langue-longue"),
    pytest.param(entry(name="   "), "name", "erable", id="name-vide"),
    pytest.param(entry(name="x" * 81), "name", "erable", id="name-trop-long"),
    pytest.param(entry(name="Éra\u0007ble"), "name", "erable", id="name-controle"),
    pytest.param(entry(name={"fr": 3}), "name", "erable", id="name-libelle-non-chaine"),
    pytest.param(entry_without("density"), "density", "erable", id="density-absente"),
    pytest.param(entry(density="650"), "density", "erable", id="density-chaine"),
    pytest.param(entry(density=True), "density", "erable", id="density-booleen"),
    pytest.param(entry(density=49.9), "density", "erable", id="density-trop-faible"),
    pytest.param(entry(density=2000.1), "density", "erable", id="density-trop-forte"),
    pytest.param(entry(density=float("inf")), "density", "erable", id="density-infinie"),
    pytest.param(entry_without("thicknesses"), "thicknesses", "erable", id="ep-absentes"),
    pytest.param(entry(thicknesses=18), "thicknesses", "erable", id="ep-non-liste"),
    pytest.param(entry(thicknesses=[]), "thicknesses", "erable", id="ep-liste-vide"),
    pytest.param(entry(thicknesses=LONG_LIST), "thicknesses", "erable", id="ep-trop-nombreuses"),
    pytest.param(entry(thicknesses=[18, 0]), "thicknesses", "erable", id="ep-nulle"),
    pytest.param(entry(thicknesses=[-18]), "thicknesses", "erable", id="ep-negative"),
    pytest.param(entry(thicknesses=[300.5]), "thicknesses", "erable", id="ep-trop-grande"),
    pytest.param(entry(thicknesses=["18"]), "thicknesses", "erable", id="ep-chaine"),
    pytest.param(entry(thicknesses=[True]), "thicknesses", "erable", id="ep-booleen"),
    pytest.param(entry(thicknesses=[float("nan")]), "thicknesses", "erable", id="ep-nan"),
    pytest.param(entry_without("color"), "color", "erable", id="color-absente"),
    pytest.param(entry(color="E8D2A8"), "color", "erable", id="color-sans-diese"),
    pytest.param(entry(color="#E8D2A"), "color", "erable", id="color-courte"),
    pytest.param(entry(color="#GGGGGG"), "color", "erable", id="color-non-hexa"),
    pytest.param(entry(color="#E8D2A8\n"), "color", "erable", id="color-saut-de-ligne"),
    pytest.param(entry(color=0xE8D2A8), "color", "erable", id="color-entier"),
    pytest.param(entry(has_grain="oui"), "has_grain", "erable", id="has-grain-chaine"),
    pytest.param(entry(has_grain=1), "has_grain", "erable", id="has-grain-entier"),
]


@pytest.mark.parametrize(("bad_entry", "field", "material_id"), ENTRY_RULES)
def test_entree_invalide_rejetee_seule(
    bad_entry: dict[str, object], field: str, material_id: str | None
) -> None:
    materials, issues = parse_materials(document(REFERENCE, bad_entry), SOURCE)
    assert [m.id for m in materials] == ["chene"]
    [issue] = errors(issues)
    assert issue.source == SOURCE
    assert issue.material_id == material_id
    assert issue.params["field"] == field
    message = issue.format()
    assert SOURCE in message
    assert f"« {field} »" in message
    assert f"« {material_id or '#2'} »" in message


def test_identifiant_en_double_rejette_la_seconde_entree() -> None:
    duplicate = entry(id="chene", name="Chêne bis")
    materials, issues = parse_materials(document(REFERENCE, duplicate), SOURCE)
    assert [m.name() for m in materials] == ["Chêne"]
    [issue] = errors(issues)
    assert issue.material_id == "chene"
    assert issue.params["field"] == "id"


def test_densite_hors_flottants_rejetee_depuis_un_fichier(tmp_path: Path) -> None:
    text = json.dumps(document(REFERENCE)).replace("710", "1e400")
    materials, issues = read_materials_file(write(tmp_path, text))
    assert materials == []
    assert errors(issues)[0].params["field"] == "density"


def test_cle_inconnue_dans_une_entree_signalee_sans_rejet() -> None:
    materials, issues = parse_materials(document(entry(densty=650)), SOURCE)
    assert [m.id for m in materials] == ["erable"]
    [issue] = issues
    assert issue.severity is Severity.WARNING
    assert issue.params["field"] == "densty"
    assert issue.material_id == "erable"


def test_cle_inconnue_signalee_meme_si_l_entree_est_rejetee() -> None:
    bad = entry_without("density")
    bad["densty"] = 650
    _, issues = parse_materials(document(bad), SOURCE)
    assert [i.severity for i in issues] == [Severity.WARNING, Severity.ERROR]


def test_cle_inconnue_a_la_racine_signalee() -> None:
    materials, issues = parse_materials(document(REFERENCE, comment="x"), SOURCE)
    assert len(materials) == 1
    [issue] = issues
    assert issue.severity is Severity.WARNING
    assert issue.params["field"] == "comment"


def test_entrees_en_trop_ignorees_avec_une_erreur() -> None:
    entries = [entry(id=f"m{i}", name=f"Matériau {i}") for i in range(MAX_MATERIALS + 3)]
    materials, issues = parse_materials(document(*entries), SOURCE)
    assert len(materials) == MAX_MATERIALS
    [issue] = issues
    assert issue.severity is Severity.ERROR
    assert issue.params["count"] == str(MAX_MATERIALS + 3)


def test_entrees_non_objets_ignorees_avec_une_erreur() -> None:
    materials, issues = parse_materials(document(REFERENCE, 3, "x", entry()), SOURCE)
    assert [m.id for m in materials] == ["chene", "erable"]
    [issue] = issues
    assert issue.severity is Severity.ERROR
    assert issue.params["positions"] == "2, 3"


def test_valeurs_normalisees_au_chargement() -> None:
    raw = entry(name="  Érable  ", thicknesses=[27, 18, 18.0, 6.5], color="#e8d2a8")
    [material], issues = parse_materials(document(raw), SOURCE)
    assert issues == []
    assert dict(material.names) == {"fr": "Érable"}
    assert material.thicknesses == (6.5, 18.0, 27.0)
    assert material.color == (0xE8, 0xD2, 0xA8)
    assert material.density == 650.0


@pytest.mark.parametrize(
    ("kind", "has_grain"),
    [("solid", True), ("plywood", True), ("mdf", False), ("melamine", False)],
)
def test_fil_par_defaut_selon_le_type(kind: str, has_grain: bool) -> None:
    [material], _ = parse_materials(document(entry(kind=kind)), SOURCE)
    assert material.has_grain is has_grain


def test_fil_explicite_prioritaire() -> None:
    [material], _ = parse_materials(document(entry(kind="mdf", has_grain=True)), SOURCE)
    assert material.has_grain is True


def test_langue_non_chaine_rejetee() -> None:
    _, issues = parse_materials(document(entry(name={1: "Érable"})), SOURCE)
    assert errors(issues)[0].params["field"] == "name"


@pytest.mark.parametrize(
    "char",
    [
        pytest.param("\u200b", id="Cf-espace-sans-chasse"),
        pytest.param("\u202e", id="Cf-inversion-bidi"),
        pytest.param("\ud800", id="Cs-demi-substitut"),
        pytest.param("\ue000", id="Co-usage-prive"),
        pytest.param("\u0378", id="Cn-non-attribue"),
        pytest.param("\u2028", id="Zl-separateur-de-ligne"),
        pytest.param("\u2029", id="Zp-separateur-de-paragraphe"),
    ],
)
def test_libelle_avec_caractere_interdit_rejete(char: str) -> None:
    materials, issues = parse_materials(document(entry(name=f"Éra{char}ble")), SOURCE)
    assert materials == []
    assert errors(issues)[0].params["field"] == "name"


def test_libelle_normalise_en_nfc_au_chargement() -> None:
    decomposed = unicodedata.normalize("NFD", "Érable")
    [material], issues = parse_materials(document(entry(name=decomposed)), SOURCE)
    assert issues == []
    assert material.name() == "Érable"
    assert unicodedata.is_normalized("NFC", material.name())


def test_materiau_construit_directement_normalise_en_nfc() -> None:
    material = make_material("chene", unicodedata.normalize("NFD", "Chêne"))
    assert material.name() == "Chêne"
    library = MaterialLibrary([material])
    assert library.find_by_name(unicodedata.normalize("NFD", "Chêne")) is material


def test_code_de_langue_entier_geant_cite_sans_exception() -> None:
    _, issues = parse_materials(document(entry(name={10**5000: "Érable"})), SOURCE)
    assert errors(issues)[0].params["language"] == "?"


# --- A3 : fichier ignoré en entier --------------------------------------------------------

FILE_RULES = [
    pytest.param(b"\xff\xfe{}", id="non-utf8"),
    pytest.param("{", id="json-invalide"),
    pytest.param("", id="fichier-vide"),
    pytest.param("[]", id="racine-liste"),
    pytest.param('"texte"', id="racine-chaine"),
    pytest.param('{"materials": []}', id="format-absent"),
    pytest.param('{"format": "1", "materials": []}', id="format-chaine"),
    pytest.param('{"format": true, "materials": []}', id="format-booleen"),
    pytest.param('{"format": 1.0, "materials": []}', id="format-flottant"),
    pytest.param('{"format": 0, "materials": []}', id="format-zero"),
    pytest.param('{"format": 2, "materials": []}', id="format-plus-recent"),
    pytest.param('{"format": 1}', id="materials-absent"),
    pytest.param('{"format": 1, "materials": {}}', id="materials-objet"),
    pytest.param('{"format": 1, "materials": [], "x": NaN}', id="nan"),
    pytest.param('{"format": 1, "materials": [Infinity]}', id="infinity"),
    pytest.param('{"format": 1, "materials": [-Infinity]}', id="moins-infinity"),
    pytest.param("[" * 200_000 + "]" * 200_000, id="imbrication-profonde"),
    pytest.param('{"format": ' + "9" * 5000 + "}", id="entier-geant"),
]


@pytest.mark.parametrize("content", FILE_RULES)
def test_fichier_invalide_ignore_en_entier(tmp_path: Path, content: str | bytes) -> None:
    path = write(tmp_path, content)
    materials, issues = read_materials_file(path)
    assert materials == []
    [issue] = issues
    assert issue.severity is Severity.ERROR
    assert issue.source == str(path)
    assert str(path) in issue.format()


def test_format_plus_recent_explique(tmp_path: Path) -> None:
    _, [issue] = read_materials_file(write(tmp_path, '{"format": 2, "materials": []}'))
    assert "version plus récente" in issue.format()


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_constantes_non_finies_refusees(tmp_path: Path, constant: str) -> None:
    text = json.dumps(document(entry())).replace("650", constant)
    _, [issue] = read_materials_file(write(tmp_path, text))
    assert issue.params["value"] == constant


def test_fichier_trop_volumineux_ignore_avant_lecture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write(tmp_path, b" " * (MAX_FILE_BYTES + 1))

    def refuse_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("le fichier ne doit pas être ouvert")

    monkeypatch.setattr(Path, "open", refuse_open)
    materials, [issue] = read_materials_file(path)
    assert materials == []
    assert issue.params["size"] == str(MAX_FILE_BYTES + 1)


def test_fichier_qui_grossit_pendant_la_lecture_borne(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write(tmp_path, b" " * (MAX_FILE_BYTES + 10))
    real_stat = Path.stat

    def small_stat(self: Path, **kwargs: bool) -> os.stat_result:
        values = list(real_stat(self, **kwargs))
        values[6] = 10  # st_size
        return os.stat_result(values)

    monkeypatch.setattr(Path, "stat", small_stat)
    materials, [issue] = read_materials_file(path)
    assert materials == []
    assert issue.params["size"] == f"> {MAX_FILE_BYTES}"


def test_fichier_de_taille_maximale_accepte(tmp_path: Path) -> None:
    text = json.dumps(document(REFERENCE))
    path = write(tmp_path, text + " " * (MAX_FILE_BYTES - len(text.encode("utf-8"))))
    materials, issues = read_materials_file(path)
    assert issues == []
    assert len(materials) == 1


def test_dossier_ignore(tmp_path: Path) -> None:
    materials, [issue] = read_materials_file(tmp_path)
    assert materials == []
    assert issue.severity is Severity.ERROR


def test_fichier_illisible_ignore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write(tmp_path, json.dumps(document(REFERENCE)))

    def deny(*args: object, **kwargs: object) -> None:
        raise PermissionError(13, "Permission non accordée")

    monkeypatch.setattr(Path, "open", deny)
    materials, [issue] = read_materials_file(path, "utilisateur")
    assert materials == []
    assert issue.source == "utilisateur"
    assert issue.params["error"] == "Permission non accordée"


def test_fichier_absent_sans_anomalie(tmp_path: Path) -> None:
    assert read_materials_file(tmp_path / "absent.json") == ([], [])


# --- A4 : fusion -------------------------------------------------------------------------


def builtin_library() -> list[Material]:
    materials, issues = read_materials_file(BUILTIN_PATH, BUILTIN_SOURCE)
    assert issues == []
    return materials


def test_nouvel_identifiant_ajoute_apres_les_integres() -> None:
    builtin = builtin_library()
    library, issues = merge_materials(builtin, [make_material("erable", "Érable")], SOURCE)
    assert issues == []
    assert [m.id for m in library] == [*(m.id for m in builtin), "erable"]


def test_identifiant_existant_remplace_entierement_a_sa_place() -> None:
    builtin = builtin_library()
    replacement = make_material("hetre", "Hêtre étuvé")
    library, [issue] = merge_materials(builtin, [replacement], SOURCE)
    assert [m.id for m in library] == [m.id for m in builtin]
    assert library.get("hetre") is replacement
    assert library.find_by_name("Hêtre") is None
    assert issue.severity is Severity.INFO
    assert issue.source == SOURCE
    assert issue.material_id == "hetre"


def test_libelle_deja_porte_par_un_autre_identifiant_rejete() -> None:
    builtin = builtin_library()
    user = [make_material("chene-europe", "Chêne"), make_material("erable", "Érable")]
    library, [issue] = merge_materials(builtin, user, SOURCE)
    assert "chene-europe" not in library
    assert "erable" in library
    assert issue.severity is Severity.ERROR
    assert issue.material_id == "chene-europe"
    assert issue.params["field"] == "name"
    assert issue.params["other"] == "chene"


def test_libelle_libere_par_un_remplacement_reutilisable() -> None:
    user = [make_material("chene-europe", "Chêne"), make_material("chene", "Chêne rouvre")]
    library, issues = merge_materials(builtin_library(), user, SOURCE)
    assert errors(issues) == []
    assert library.find_by_name("Chêne") == user[0]


def test_echange_de_libelles_entre_trois_remplacements() -> None:
    user = [
        make_material("frene", "Chêne"),
        make_material("chene", "Hêtre"),
        make_material("hetre", "Frêne"),
    ]
    for ordered in (user, user[::-1], [user[1], user[0], user[2]]):
        library, issues = merge_materials(builtin_library(), ordered, SOURCE)
        assert errors(issues) == []
        assert [i.severity for i in issues] == [Severity.INFO] * 3
        assert library.find_by_name("Chêne") == user[0]


def test_conflit_entre_deux_entrees_utilisateur_la_premiere_l_emporte() -> None:
    user = [make_material("erable", "Érable"), make_material("erable-plane", "Érable")]
    library, [issue] = merge_materials(builtin_library(), user, SOURCE)
    assert "erable" in library
    assert "erable-plane" not in library
    assert issue.material_id == "erable-plane"
    assert issue.params["other"] == "erable"


def test_remplacement_rejete_rend_sa_place_et_son_libelle_a_l_integre() -> None:
    # « chene » veut le libellé du hêtre intégré : rejeté, le chêne intégré revient avec
    # « Chêne », ce qui rejette à son tour l'ajout « chene-europe ».
    user = [make_material("chene-europe", "Chêne"), make_material("chene", "Hêtre")]
    for ordered in (user, user[::-1]):
        library, issues = merge_materials(builtin_library(), ordered, SOURCE)
        assert library.get("chene").name() == "Chêne"
        assert "chene-europe" not in library
        others = {i.material_id: i.params["other"] for i in errors(issues)}
        assert others == {"chene": "hetre", "chene-europe": "chene"}
        assert [i.severity for i in issues] == [Severity.ERROR, Severity.ERROR]


def test_libelle_cite_le_detenteur_final() -> None:
    user = [
        make_material("chene", "Hêtre"),
        make_material("erable", "Chêne"),
        make_material("erable-plane", "Chêne"),
    ]
    library, issues = merge_materials(builtin_library(), user, SOURCE)
    assert library.find_by_name("Chêne") == library.get("chene")
    others = {i.material_id: i.params["other"] for i in errors(issues)}
    assert others == {"chene": "hetre", "erable": "chene", "erable-plane": "chene"}


def test_doublons_fournis_directement_a_la_fusion_rejetes() -> None:
    builtin = [make_material("a", "A"), make_material("a", "A2"), make_material("b", "A")]
    user = [make_material("c", "C"), make_material("c", "C2")]
    library, issues = merge_materials(builtin, user, SOURCE)
    assert [m.id for m in library] == ["a", "c"]
    assert [(i.source, i.params["field"]) for i in issues] == [
        (BUILTIN_SOURCE, "id"),
        (BUILTIN_SOURCE, "name"),
        (SOURCE, "id"),
    ]


def test_fichier_utilisateur_absent_sans_anomalie(tmp_path: Path) -> None:
    library, issues = load_library(BUILTIN_PATH, tmp_path / "absent.json")
    assert issues == []
    assert len(library) == len(BUILTIN_TABLE)


def test_chargement_avec_fichier_utilisateur(tmp_path: Path) -> None:
    user = document(entry(), entry(id="chene", name="Chêne massif", density=700))
    path = write(tmp_path, json.dumps(user))
    library, issues = load_library(BUILTIN_PATH, path)
    assert [(i.severity, i.source) for i in issues] == [(Severity.INFO, str(path))]
    assert [m.id for m in library][-1] == "erable"
    assert library.get("chene").density == 700


def test_fichier_utilisateur_invalide_n_empeche_pas_la_bibliotheque(tmp_path: Path) -> None:
    library, [issue] = load_library(BUILTIN_PATH, write(tmp_path, "{"))
    assert len(library) == len(BUILTIN_TABLE)
    assert issue.severity is Severity.ERROR


def test_bibliotheque_integree_absente_signalee(tmp_path: Path) -> None:
    library, [issue] = load_library(tmp_path / "absent.json", None)
    assert len(library) == 0
    assert issue.severity is Severity.ERROR
    assert issue.source == BUILTIN_SOURCE


# --- Modèle de données -----------------------------------------------------------------


def test_bibliotheque_acces() -> None:
    oak = make_material("chene", "Chêne")
    mdf = make_material("mdf", "MDF", MaterialKind.MDF)
    library = MaterialLibrary([mdf, oak])
    assert "chene" in library
    assert "erable" not in library
    assert list(library) == [mdf, oak]
    assert len(library) == 2
    assert library.get("mdf") is mdf
    assert library.find("erable") is None
    assert library.find_by_name("Chêne") is oak
    assert library.find_by_name("Inconnu") is None
    assert library.by_kind(MaterialKind.MDF, MaterialKind.MELAMINE) == [mdf]
    assert library.by_kind() == [mdf, oak]
    assert library.default_material() is oak
    with pytest.raises(UnknownMaterialError):
        library.get("erable")


def test_materiau_par_defaut_sans_massif_ni_materiau() -> None:
    mdf = make_material("mdf", "MDF", MaterialKind.MDF)
    assert MaterialLibrary([mdf]).default_material() is mdf
    with pytest.raises(UnknownMaterialError):
        MaterialLibrary([]).default_material()


@pytest.mark.parametrize(
    "materials",
    [
        [make_material("a", "A"), make_material("a", "B")],
        [make_material("a", "A"), make_material("b", "A")],
    ],
    ids=["identifiant", "libelle"],
)
def test_bibliotheque_refuse_les_doublons(materials: list[Material]) -> None:
    with pytest.raises(ValueError, match="double"):
        MaterialLibrary(materials)


def test_libelle_selon_la_langue() -> None:
    material = Material(
        "x", MaterialKind.SOLID, {"en": "Oak", "fr": "Chêne"}, 1, (1,), (0, 0, 0), True
    )
    assert material.name() == "Chêne"
    assert material.name("en") == "Oak"
    assert material.name("de") == "Chêne"
    english_only = Material("y", MaterialKind.SOLID, {"en": "Oak"}, 1, (1,), (0, 0, 0), True)
    assert english_only.name() == "Oak"
    with pytest.raises(ValueError, match="libellé"):
        Material("z", MaterialKind.SOLID, {}, 1, (1,), (0, 0, 0), True)


def test_libelles_immuables() -> None:
    names = {"fr": "Chêne"}
    material = Material("x", MaterialKind.SOLID, names, 1, (1,), (0, 0, 0), True)
    names["fr"] = "Modifié"
    assert material.name() == "Chêne"
    with pytest.raises(TypeError):
        material.names["fr"] = "Modifié"  # type: ignore[index]


def test_anomalie_formatee_avec_sa_source() -> None:
    issue = LibraryIssue(Severity.WARNING, "src", "{source} : {x}", {"x": "y"})
    assert issue.format() == "src : y"
    assert dict(issue.params) == {"source": "src", "x": "y"}


@pytest.mark.parametrize(
    ("kind", "is_panel"),
    [
        (MaterialKind.SOLID, False),
        (MaterialKind.PLYWOOD, True),
        (MaterialKind.MDF, True),
        (MaterialKind.MELAMINE, True),
    ],
)
def test_familles_de_panneaux(kind: MaterialKind, is_panel: bool) -> None:
    assert kind.is_panel is is_panel


@pytest.mark.parametrize(
    ("value", "expected"),
    [(12, 12.0), (6.5, 6.5), (True, None), ("12", None), (None, None), (10**400, None)],
)
def test_conversion_en_nombre_fini(value: object, expected: float | None) -> None:
    assert to_finite_float(value) == expected


def test_marqueur_de_traduction_neutre() -> None:
    assert CONTEXT == "Menuiserie"
    assert QT_TRANSLATE_NOOP(CONTEXT, "Pièce de bois") == "Pièce de bois"
