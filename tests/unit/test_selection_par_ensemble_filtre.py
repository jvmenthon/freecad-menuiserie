# SPDX-License-Identifier: LGPL-2.1-or-later
"""Filtre de clic de la sélection par ensemble (ADR 0048), FreeCAD et Qt simulés : cas limites de
non-régression (pièce libre, Ctrl+clic, panneau ouvert, double-clic dans le vide, trois niveaux,
objet supprimé, relâchement consommé une seule fois)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests.unit.aides_click_select import (
    CONTROL,
    DOUBLE,
    PRESS,
    RELEASE,
    RIGHT,
    Event,
    World,
    simulated_click_select,
)

NIVEAUX = ("meuble", "caisson", "tiroir", "facade")


@pytest.fixture(name="world")
def fixture_world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_click_select(monkeypatch) as world:
        yield world


def clic(world: World, filtre: Any, nom: str | None, **kwargs: Any) -> None:
    """Appui puis relâchement au même point sur ``nom``, sélection native de FreeCAD simulée
    entre les deux (la pièce cliquée), puis minuteries à zéro exécutées."""
    world.pick = nom
    filtre.eventFilter(None, Event(PRESS, **kwargs))
    world.selection[:] = [world.doc.objects[nom]] if nom else []
    filtre.eventFilter(None, Event(RELEASE, **kwargs))
    world.flush()


def hierarchie(world: World) -> None:
    world.link(*NIVEAUX)
    world.chains["meuble"] = []


# --- Clic simple -----------------------------------------------------------------------------


def test_clic_sur_une_piece_libre_reste_natif(world: World) -> None:
    world.obj("libre")
    filtre = world.filter()
    clic(world, filtre, "libre")
    assert world.selected() == ["libre"]
    assert world.errors == []


def test_clic_simple_selectionne_le_plus_haut_niveau(world: World) -> None:
    hierarchie(world)
    clic(world, world.filter(), "facade")
    assert world.selected() == ["meuble"]


def test_clic_dans_un_sous_ensemble_selectionne_ne_remonte_pas(world: World) -> None:
    hierarchie(world)
    world.selection[:] = [world.doc.objects["tiroir"]]
    clic(world, world.filter(), "facade")
    assert world.selected() == ["tiroir"]


def test_clic_sur_une_piece_deja_selectionnee_la_garde(world: World) -> None:
    hierarchie(world)
    world.selection[:] = [world.doc.objects["facade"]]
    clic(world, world.filter(), "facade")
    assert world.selected() == ["facade"]


def test_clic_hors_ensemble_selectionne_autre_apres_ensemble(world: World) -> None:
    hierarchie(world)
    world.obj("libre")
    world.selection[:] = [world.doc.objects["tiroir"]]
    clic(world, world.filter(), "libre")
    assert world.selected() == ["libre"]


def test_clic_dans_le_vide_ne_change_rien(world: World) -> None:
    hierarchie(world)
    clic(world, world.filter(), None)
    assert world.selected() == []


def test_clic_avec_deplacement_est_une_rotation_de_vue(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick = "facade"
    filtre.eventFilter(None, Event(PRESS, x=10, y=10))
    world.selection[:] = [world.doc.objects["facade"]]
    filtre.eventFilter(None, Event(RELEASE, x=30, y=10))
    assert world.timers == []
    world.flush()
    assert world.selected() == ["facade"]


def test_clic_n_est_jamais_consomme(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick = "facade"
    assert filtre.eventFilter(None, Event(PRESS)) is False
    assert filtre.eventFilter(None, Event(RELEASE)) is False


def test_clic_droit_et_autres_evenements_ignores(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick = "facade"
    assert filtre.eventFilter(None, Event(PRESS, button=RIGHT)) is False
    assert filtre.eventFilter(None, Event(DOUBLE, button=RIGHT)) is False
    assert filtre.eventFilter(None, Event(99)) is False
    assert world.timers == []


def test_clic_sur_une_poignee_a_la_priorite(world: World) -> None:
    hierarchie(world)

    class Session:
        active = True

        @staticmethod
        def target_at(_point: tuple[int, int]) -> str:
            return "arrow0"

    world.session = Session()
    clic(world, world.filter(), "facade")
    assert world.selected() == ["facade"]  # sélection native, pas remplacée


# --- Modificateurs ---------------------------------------------------------------------------


def test_ctrl_clic_est_ignore(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    clic(world, filtre, "facade", modifiers=CONTROL)
    assert world.selected() == ["facade"]
    assert world.timers == []


def test_ctrl_double_clic_est_ignore(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick = "facade"
    assert filtre.eventFilter(None, Event(DOUBLE, modifiers=CONTROL)) is False
    assert filtre.swallow_release is False
    assert world.selected() == []


def test_ctrl_clic_apres_clic_simple_n_utilise_pas_l_ancien_appui(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick = "facade"
    filtre.eventFilter(None, Event(PRESS))
    filtre.eventFilter(None, Event(PRESS, modifiers=CONTROL))  # second appui avec Ctrl
    filtre.eventFilter(None, Event(RELEASE))
    assert world.timers == []


# --- Panneau de tâche ------------------------------------------------------------------------


def test_panneau_ouvert_selection_native(world: World) -> None:
    hierarchie(world)
    world.dialog = True
    filtre = world.filter()
    clic(world, filtre, "facade")
    assert world.selected() == ["facade"]
    world.pick = "facade"
    assert filtre.eventFilter(None, Event(DOUBLE)) is False
    assert filtre.swallow_release is False


def test_panneau_ouvert_entre_le_clic_et_la_minuterie(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick = "facade"
    filtre.eventFilter(None, Event(PRESS))
    world.selection[:] = [world.doc.objects["facade"]]
    filtre.eventFilter(None, Event(RELEASE))
    world.dialog = True  # un panneau s'ouvre avant la minuterie
    world.flush()
    assert world.selected() == ["facade"]
    assert world.errors == []


# --- Double-clic : descente à trois niveaux, remontée ---------------------------------------


def double_clic(world: World, filtre: Any, nom: str | None) -> bool:
    world.pick = nom
    return bool(filtre.eventFilter(None, Event(DOUBLE)))


def test_parcours_a_trois_niveaux(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    clic(world, filtre, "facade")
    assert world.selected() == ["meuble"]
    for attendu in ("caisson", "tiroir", "facade"):
        assert double_clic(world, filtre, "facade") is True
        assert world.selected() == [attendu]
        filtre.eventFilter(None, Event(RELEASE))  # relâchement consommé
    assert double_clic(world, filtre, "facade") is False  # panneau de la pièce
    assert world.selected() == ["facade"]
    for attendu in ("tiroir", "caisson", "meuble"):
        assert double_clic(world, filtre, None) is True
        assert world.selected() == [attendu]
        filtre.eventFilter(None, Event(RELEASE))
    assert double_clic(world, filtre, None) is False  # plus haut niveau
    assert world.selected() == ["meuble"]


def test_double_clic_sur_une_piece_libre_n_est_pas_consomme(world: World) -> None:
    world.obj("libre")
    filtre = world.filter()
    assert double_clic(world, filtre, "libre") is False
    assert filtre.swallow_release is False


def test_double_clic_dans_le_vide_sans_selection_ni_avant_ne_fait_rien(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    assert double_clic(world, filtre, None) is False
    assert world.selected() == []


def test_double_clic_dans_le_vide_repli_avant(world: World) -> None:
    """FreeCAD vide la sélection au premier clic dans le vide : l'élément d'avant le clic sert."""
    hierarchie(world)
    filtre = world.filter()
    world.selection[:] = [world.doc.objects["facade"]]
    world.pick = None
    filtre.eventFilter(None, Event(PRESS))  # note « avant » = façade
    world.selection.clear()  # sélection native vidée par le clic dans le vide
    filtre.eventFilter(None, Event(RELEASE))
    world.flush()
    assert double_clic(world, filtre, None) is True
    assert world.selected() == ["tiroir"]


def test_double_clic_dans_le_vide_repli_trop_ancien(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.selection[:] = [world.doc.objects["facade"]]
    filtre.eventFilter(None, Event(PRESS))
    world.selection.clear()
    world.now += 5000  # bien au-delà de deux intervalles de double-clic
    assert double_clic(world, filtre, None) is False
    assert world.selected() == []


def test_double_clic_vide_prefere_la_selection_courante_a_l_avant(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.selection[:] = [world.doc.objects["tiroir"]]
    filtre.eventFilter(None, Event(PRESS))  # avant = tiroir
    world.selection[:] = [world.doc.objects["caisson"]]
    assert double_clic(world, filtre, None) is True
    assert world.selected() == ["meuble"]


def test_double_clic_avec_plusieurs_objets_selectionnes_repart_du_haut(world: World) -> None:
    hierarchie(world)
    world.obj("autre")
    world.selection[:] = [world.doc.objects["autre"], world.doc.objects["tiroir"]]
    assert double_clic(world, world.filter(), "facade") is True
    assert world.selected() == ["meuble"]


def test_double_clic_vide_avec_plusieurs_objets_selectionnes_ne_fait_rien(world: World) -> None:
    hierarchie(world)
    world.selection[:] = [world.doc.objects["tiroir"], world.doc.objects["facade"]]
    assert double_clic(world, world.filter(), None) is False


# --- Relâchement consommé une seule fois -----------------------------------------------------


def test_relachement_consomme_une_seule_fois(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    assert double_clic(world, filtre, "facade") is True
    assert filtre.swallow_release is True
    assert filtre.eventFilter(None, Event(RELEASE)) is True
    assert filtre.swallow_release is False
    assert filtre.eventFilter(None, Event(RELEASE)) is False
    assert world.timers == []  # le relâchement consommé ne déclenche pas de clic simple


def test_nouvel_appui_annule_un_relachement_en_attente(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    double_clic(world, filtre, "facade")
    world.pick = "facade"
    filtre.eventFilter(None, Event(PRESS))
    assert filtre.swallow_release is False
    assert filtre.eventFilter(None, Event(RELEASE)) is False


def test_double_clic_non_consomme_ne_consomme_pas_le_relachement(world: World) -> None:
    world.obj("libre")
    filtre = world.filter()
    double_clic(world, filtre, "libre")
    assert filtre.eventFilter(None, Event(RELEASE)) is False


def test_relachement_du_bouton_droit_ne_touche_pas_au_drapeau(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    double_clic(world, filtre, "facade")
    assert filtre.eventFilter(None, Event(RELEASE, button=RIGHT)) is False
    assert filtre.swallow_release is True


# --- Objet supprimé --------------------------------------------------------------------------


def test_objet_supprime_avant_la_minuterie(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick = "facade"
    filtre.eventFilter(None, Event(PRESS))
    filtre.eventFilter(None, Event(RELEASE))
    world.doc.objects["facade"].delete()
    world.selection.clear()
    world.flush()
    assert world.selected() == []
    assert world.errors == []


def test_objet_sous_le_curseur_inconnu_du_document_est_le_vide(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick = "fantome"  # getObjectInfo nomme un objet absent du document
    assert filtre.eventFilter(None, Event(DOUBLE)) is False
    assert world.errors == []


def test_widget_detruit_pendant_le_clic_est_ignore(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick_error = RuntimeError("Internal C++ object already deleted")
    assert filtre.eventFilter(None, Event(PRESS)) is False
    assert filtre.eventFilter(None, Event(DOUBLE)) is False
    assert world.errors == []


def test_erreur_inattendue_est_journalisee_sans_consommer(world: World) -> None:
    hierarchie(world)
    filtre = world.filter()
    world.pick_error = ValueError("boum")
    assert filtre.eventFilter(None, Event(DOUBLE)) is False
    assert len(world.errors) == 1


def test_avant_supprime_avant_la_minuterie_sans_erreur(world: World) -> None:
    """Défaut : l'élément sélectionné avant le clic est supprimé entre l'appui et la minuterie ;
    FreeCAD lève alors ``ReferenceError`` à l'accès à ``Name`` et le journal reçoit une trace
    d'erreur à chaque clic de ce genre."""
    hierarchie(world)
    filtre = world.filter()
    world.selection[:] = [world.doc.objects["tiroir"]]
    world.pick = "facade"
    filtre.eventFilter(None, Event(PRESS))
    filtre.eventFilter(None, Event(RELEASE))
    tiroir = world.doc.objects["tiroir"]
    tiroir.delete()
    tiroir.invalidate()
    world.flush()
    assert world.errors == []


# --- Observateur de sélection (clic que le filtre ne voit pas, jv 2026-11-11) ------------------


def selection_3d(world: World, nom: str, point: tuple[float, float, float]) -> None:
    """Sélection native de FreeCAD sur ``nom`` avec le point cliqué ``point``, sans appui vu par
    le filtre, puis minuteries exécutées."""
    world.selection[:] = [world.doc.objects[nom]]
    watch = world.module._SelectionWatch()  # pylint: disable=protected-access
    watch.addSelection(world.doc.Name, nom, "", point)
    world.flush()


def test_observateur_rattrape_le_premier_clic(world: World) -> None:
    hierarchie(world)
    world.filter()
    selection_3d(world, "facade", (10.0, 20.0, 30.0))
    assert world.selected() == ["meuble"]
    assert world.errors == []


def test_observateur_ignore_l_arbre_et_les_scripts(world: World) -> None:
    hierarchie(world)
    world.filter()
    selection_3d(world, "facade", (0.0, 0.0, 0.0))
    assert world.selected() == ["facade"]


def test_observateur_ignore_ctrl_clic(world: World) -> None:
    hierarchie(world)
    world.filter()
    world.modifiers = CONTROL
    selection_3d(world, "facade", (10.0, 20.0, 30.0))
    assert world.selected() == ["facade"]


def test_observateur_garde_le_niveau_de_l_appui(world: World) -> None:
    """Appui vu par le filtre (tiroir sélectionné) : l'observateur garde le tiroir."""
    hierarchie(world)
    filtre = world.filter()
    world.selection[:] = [world.doc.objects["tiroir"]]
    world.pick = "facade"
    filtre.eventFilter(None, Event(PRESS))
    selection_3d(world, "facade", (10.0, 20.0, 30.0))
    assert world.selected() == ["tiroir"]


def test_observateur_rien_atelier_quitte(world: World) -> None:
    hierarchie(world)
    world.module.uninstall()
    selection_3d(world, "facade", (10.0, 20.0, 30.0))
    assert world.selected() == ["facade"]


def test_observateur_pose_et_retire_avec_l_atelier(world: World) -> None:
    world.module.install()
    assert len(world.observers) == 1
    world.module.uninstall()
    assert world.observers == []
