# Tests d'interface avec QTest (preuve de concept)

Des scénarios complets joués dans le vrai FreeCAD, avec les gestes de l'utilisateur : touches du
clavier et clics de souris envoyés par `QTest` aux widgets des panneaux de tâche. Ils complètent
les tests unitaires (`tests/unit`, logique pure), les tests d'intégration (`tests/integration`,
API sans interface) et les vérifications d'interface (`tests/gui`, qui écrivent les propriétés
des widgets sans passer par le clavier ni la souris).

## Lancer

L'atelier doit être dans le dossier `Mod` de FreeCAD (ou de `FREECAD_USER_HOME`).

```sh
# Linux (CI) : serveur X virtuel
xvfb-run -a freecad -t tests.qtest.scenario_queue_aronde
# Windows (non vérifié en CI) : FreeCAD s'ouvre, joue le scénario et se ferme
FreeCAD.exe -t tests.qtest.scenario_queue_aronde
```

`-t` est le mode test de FreeCAD : il charge le module avec `unittest`, affiche le rapport et
sort avec le code 0 (succès) ou 1 (échec). Variables facultatives :

- `CAPTURES_QTEST` : dossier où le scénario enregistre une image de la vue 3D ;
- `PILE_EN_CAS_DE_PLANTAGE` : fichier où `faulthandler` écrit la pile Python de tous les fils si
  FreeCAD plante dans du code C++ (sinon : sortie d'erreur du processus).

Ces deux variables sont réservées aux tests : les chemins sont utilisés tels quels (le fichier de
pile est écrasé).

## Écrire un scénario

Un module `tests/qtest/scenario_<sujet>.py` (pas `test_*.py` : pytest ne doit pas le ramasser)
avec une classe `unittest.TestCase`, et les aides de `tests/qtest/aides.py` :

| Geste de l'utilisateur | Aide |
|---|---|
| Cliquer un bouton de la barre d'outils | `lancer("Menuiserie_…")` (action Qt, attend qu'elle soit active) |
| Taper une valeur dans un champ | `taper(champ, "20 cm")` (Ctrl+A, touches, Tab) |
| Cocher une case, cliquer un bouton | `cliquer(widget)` |
| Valider le panneau | `cliquer(bouton_ok())` |
| Annuler, rétablir | `lancer("Std_Undo")`, `lancer("Std_Redo")` |
| Cliquer des pièces dans la vue 3D | `selectionner(a, b)` (`Gui.Selection`) |

Puis on vérifie le document : cotes, `Placement`, état des objets (`"Invalid" in obj.State`),
formes (`Shape.isValid()`, volumes), noms des entrées d'annulation.

Les widgets sont trouvés par leur `objectName` (`WoodPartTaskPanel`, `lengthEdit`, `TailCount`,
`TailCountAuto`…) : ces noms sont un contrat entre les panneaux et les scénarios. Un nom changé
fait échouer le scénario avec un message explicite (« widget … absent du panneau … »).

Les libellés comparés (entrées d'annulation) sont les chaînes sources de l'atelier, en français :
FreeCAD doit tourner sans traduction de l'atelier vers une autre langue, ce qui est le cas en CI.

## Limites connues

- Preuve de concept (ADR 0059) : un seul scénario, avec annuler puis rétablir. Les saisies
  invalides, l'enregistrement puis la réouverture et les autres commandes ne sont pas encore
  joués ; l'image capturée n'est pas contrôlée (elle sert à la relecture).

- La vue 3D n'est pas cliquée au pixel près : un clic sur une pièce passe par `Gui.Selection`, un
  glissement à la souris est remplacé par l'écriture du `Placement` dans une transaction.
- Entrée dans un champ valide le panneau (bouton OK par défaut) : `taper` finit par Tab.
- FreeCAD ne rafraîchit l'état de ses boutons que périodiquement : `lancer` attend.
- Une erreur d'import du module ouvre une boîte de dialogue qui bloque : toujours lancer sous
  `timeout` en CI.
- `QtTest` vient de `PySide6` (absent de la couche `PySide` de FreeCAD) : réservé aux tests.
