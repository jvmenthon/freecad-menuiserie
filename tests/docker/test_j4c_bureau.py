# SPDX-License-Identifier: LGPL-2.1-or-later
"""Test spécifique pour le scénario J4c : Bureau de référence.

Ce test vérifie la préparation du bureau de référence manuellement :
- Plateau (P)
- Deux joues (JG, JD)
- Voile (V)
- Deux jeux de tourillons (JG-V et JD-V)

Ce test ne crée PAS encore l'ensemble, conformément à la spécification.
"""

from __future__ import annotations

import pytest

from tests.integration.bureau import build_parts, LAYOUT, EXPRESSIONS

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")


class TestJ4cBureauReference:
    """Tests pour le scénario J4c : Bureau de référence (sans ensemble)."""

    def test_creation_pieces_brutes(self, document):
        """J4c : Créer les 4 pièces brutes (plateau, 2 joues, voile)."""
        bureau = build_parts(document)

        # Vérifier que les 4 pièces existent
        assert len(bureau.parts) == 4
        assert "P" in bureau.parts  # Plateau
        assert "JG" in bureau.parts  # Joue gauche
        assert "JD" in bureau.parts  # Joue droite
        assert "V" in bureau.parts  # Voile

        # Vérifier les dimensions du plateau
        plateau = bureau.parts["P"]
        assert plateau.Length.Value == pytest.approx(1200, abs=0.1)
        assert plateau.Width.Value == pytest.approx(600, abs=0.1)
        assert plateau.Thickness.Value == pytest.approx(30, abs=0.1)

        # Vérifier les dimensions des joues
        for mark in ("JG", "JD"):
            joue = bureau.parts[mark]
            assert joue.Length.Value == pytest.approx(720, abs=0.1)
            assert joue.Width.Value == pytest.approx(560, abs=0.1)
            assert joue.Thickness.Value == pytest.approx(22, abs=0.1)

        # Vérifier les dimensions du voile
        voile = bureau.parts["V"]
        assert voile.Length.Value == pytest.approx(1156, abs=0.1)
        assert voile.Width.Value == pytest.approx(400, abs=0.1)
        assert voile.Thickness.Value == pytest.approx(18, abs=0.1)

    def test_positionnement_pieces(self, document):
        """J4c : Vérifier le positionnement des pièces."""
        bureau = build_parts(document)

        # Vérifier le positionnement du plateau (z = 720)
        plateau = bureau.parts["P"]
        assert plateau.Placement.Base.z == pytest.approx(720, abs=0.1)

        # Vérifier le positionnement des joues (x = 22 et x = 1200)
        jg = bureau.parts["JG"]
        jd = bureau.parts["JD"]
        assert jg.Placement.Base.x == pytest.approx(22, abs=0.1)
        assert jd.Placement.Base.x == pytest.approx(1200, abs=0.1)

        # Vérifier le positionnement du voile (x = 22, y = 459, z = 320)
        voile = bureau.parts["V"]
        assert voile.Placement.Base.x == pytest.approx(22, abs=0.1)
        assert voile.Placement.Base.y == pytest.approx(459, abs=0.1)
        assert voile.Placement.Base.z == pytest.approx(320, abs=0.1)

    def test_tourillons_jg_v(self, document):
        """J4c : Créer les tourillons entre JG et V."""
        bureau = build_parts(document)

        # Créer l'assemblage par tourillons entre JG et V
        joint_jg_v = api.make_dowels(bureau.parts["JG"], bureau.parts["V"])

        # Vérifier que l'assemblage a été créé
        assert joint_jg_v is not None

        # Vérifier que des tourillons ont été générés
        assert len(joint_jg_v.Shape.Solids) > 0

        bureau.joints.append(joint_jg_v)

    def test_tourillons_jd_v(self, document):
        """J4c : Créer les tourillons entre JD et V."""
        bureau = build_parts(document)

        # Créer l'assemblage par tourillons entre JD et V
        joint_jd_v = api.make_dowels(bureau.parts["JD"], bureau.parts["V"])

        # Vérifier que l'assemblage a été créé
        assert joint_jd_v is not None

        # Vérifier que des tourillons ont été générés
        assert len(joint_jd_v.Shape.Solids) > 0

        bureau.joints.append(joint_jd_v)

    def test_bureau_sans_ensemble(self, document):
        """J4c : Vérifier que l'ensemble n'est PAS créé (conformément à la spécification)."""
        bureau = build_parts(document)

        # Créer les deux jeux de tourillons
        bureau.joints.append(api.make_dowels(bureau.parts["JG"], bureau.parts["V"]))
        bureau.joints.append(api.make_dowels(bureau.parts["JD"], bureau.parts["V"]))

        # Vérifier que l'ensemble n'est pas créé
        assert bureau.furniture is None

        # Vérifier que nous avons bien 2 assemblages (tourillons)
        assert len(bureau.joints) == 2

        # Vérifier que chaque assemblage a des tourillons
        for joint in bureau.joints:
            assert len(joint.Shape.Solids) > 0

    def test_nombre_tourillons(self, document):
        """J4c : Vérifier le nombre de tourillons pour chaque assemblage."""
        bureau = build_parts(document)

        # Créer les assemblages
        joint_jg_v = api.make_dowels(bureau.parts["JG"], bureau.parts["V"])
        joint_jd_v = api.make_dowels(bureau.parts["JD"], bureau.parts["V"])

        # Vérifier le nombre de tourillons (doit être > 0)
        # Le nombre exact dépend de la largeur de contact
        jg_v_count = len(joint_jg_v.Shape.Solids)
        jd_v_count = len(joint_jd_v.Shape.Solids)

        assert jg_v_count > 0
        assert jd_v_count > 0

        # Les deux assemblages devraient avoir le même nombre de tourillons
        assert jg_v_count == jd_v_count
