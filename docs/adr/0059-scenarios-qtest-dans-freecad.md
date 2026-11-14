# ADR 0059 — Scénarios d'interface joués avec QTest dans FreeCAD (preuve de concept)

- Statut : **proposé**, accepté à la fusion de la PR #263 par jv (jv, 2026-11-14 : « go pour un
  poc qtest »)
- Date : 2026-11-14
- ADR liés : [0001](0001-structure-de-l-atelier.md) (Qt par la couche `PySide`),
  [0007](0007-compatibilite-avec-les-autres-ateliers.md), [0023](0023-freecad-1-1-minimum.md)

## Contexte

Trois niveaux de tests existent : unitaires (`tests/unit`, logique pure), intégration
(`tests/integration`, API dans FreeCAD sans interface) et vérifications d'interface (`tests/gui`,
lancées par `verifier_atelier.py` hors écran). Ces dernières écrivent les propriétés des widgets
et appellent `accept()` : aucun test ne passe par le clavier ni la souris, ni n'enchaîne plusieurs
commandes comme un utilisateur. Plusieurs régressions récentes venaient justement de
l'enchaînement des gestes (focus, fin de saisie, bouton par défaut, état des boutons).

## Décision

1. Un quatrième niveau, `tests/qtest` : des **scénarios** (`scenario_<sujet>.py`, classes
   `unittest.TestCase`) joués dans le vrai FreeCAD par son mode test, `freecad -t <module>`,
   sur un serveur X virtuel (`xvfb-run`) dans le job d'intégration de la CI.
2. Les gestes passent par `QTest` (`keyClicks`, `mouseClick`) sur les widgets réels des panneaux ;
   les commandes par leur action Qt. La vue 3D n'est pas cliquée au pixel : sélection par
   `Gui.Selection`, glissement remplacé par l'écriture du `Placement`.
3. **Exception à la règle « Qt par `PySide` »** : la couche de compatibilité de FreeCAD n'expose
   pas `QtTest`. Il est importé de `PySide6` (à défaut `PySide2`) dans un seul fichier,
   `tests/qtest/qttest.py`. Le test `test_qt_par_la_couche_de_freecad` n'admet que ce fichier et
   que ce module ; le code de l'atelier (`freecad/`) reste sans import direct.
4. `faulthandler` est activé pendant les scénarios : pile Python en cas de plantage C++.
5. Preuve de concept : un seul scénario (queue d'aronde). Elle est **promue** si le scénario
   reste stable en CI (pas d'échec intermittent sur les PR suivantes) et que jv valide la liste
   des scénarios suivants ; sinon l'étape de CI et `tests/qtest` sont retirés, sans effet sur
   l'atelier.

## Alternatives écartées

- **Étendre `tests/gui`** : son lanceur maison ne donne ni rapport `unittest` ni code de retour
  par test, et il tourne en `offscreen`, où un clic traité par FreeCAD plante (NaviCube sans
  contexte OpenGL).
- **pytest-qt** : dépendance supplémentaire à installer dans l'environnement de FreeCAD, et pytest
  ne démarre pas l'interface de FreeCAD ; `freecad -t` le fait sans rien ajouter.
- **Automatisation par pixels** (clics à l'écran) : fragile, dépend du rendu et de la taille de
  la fenêtre.

## Conséquences

- Coût de CI : installation de `xvfb` et environ deux minutes pour le scénario avec capture (rendu
  logiciel `softpipe`), quelques secondes sans.
- Les `objectName` des widgets des panneaux deviennent un contrat avec les scénarios.
- Une erreur d'import d'un scénario ouvre une boîte de dialogue bloquante : lancement toujours
  sous `timeout`.
- Windows (là où jv travaille) n'est pas couvert : étape suivante possible.
