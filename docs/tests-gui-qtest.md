# Tests d'interface avec QTest

Des scénarios complets joués dans le vrai FreeCAD, avec les gestes de l'utilisateur : touches du
clavier et clics de souris envoyés par `QTest` aux widgets des panneaux de tâche. Ils complètent
les tests unitaires (`tests/unit`, logique pure), les tests d'intégration (`tests/integration`,
API sans interface) et les vérifications d'interface (`tests/gui`, qui écrivent les propriétés
des widgets sans passer par le clavier ni la souris).

## Lancer

L'atelier doit être dans le dossier `Mod` de FreeCAD (ou de `FREECAD_USER_HOME`).

```sh
# À la main, Linux : serveur X virtuel
xvfb-run -a freecad -t tests.qtest.scenario_queue_aronde
# À la main, Windows (non vérifié en CI) : FreeCAD s'ouvre, joue le scénario et se ferme
FreeCAD.exe -t tests.qtest.scenario_queue_aronde
# CI : par le lanceur, depuis la racine du dépôt
SCENARIO=tests.qtest.scenario_queue_aronde RAPPORT_QTEST=rapport.txt \
    xvfb-run -a freecad tests/qtest/lanceur.py
```

`-t` est le mode test de FreeCAD : il charge le module avec `unittest`, affiche le rapport et
sort avec le code 0 (succès) ou 1 (échec). Il suffit à la main. La CI passe par
`tests/qtest/lanceur.py`, qui joue le module `SCENARIO`, écrit le rapport `unittest` dans le
fichier `RAPPORT_QTEST` au fil de l'eau et quitte par `os._exit` : l'arrêt normal de FreeCAD
plante parfois après un scénario réussi (voir « Limites connues ») et sa sortie standard,
tamponnée, est alors perdue. La CI joue tous les modules `tests/qtest/scenario_*.py`, un
FreeCAD par module. Variables facultatives :

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
| Annuler le panneau | `cliquer(bouton_annuler())`, `appuyer_sur_echap(champ)` |
| Répondre à une boîte de message | `with ReponseAuxBoites(OUI) as boites:` autour du geste qui l'ouvre (bouton standard `OUI`, `NON` pour une boîte de FreeCAD, début du texte du bouton pour une boîte de l'atelier) |
| Lire les erreurs affichées | `vue_rapport()` après `vider_la_vue_rapport()` |

Les gestes du couple de pièces assemblé par une queue d'aronde (créer une pièce, la poser, régler
un champ, double-cliquer un objet) et les contrôles communs (`controler_le_document`) sont dans
`tests/qtest/angle_a_queues.py`, partagés par les scénarios.

Puis on vérifie le document : cotes, `Placement`, état des objets (`"Invalid" in obj.State`),
formes (`Shape.isValid()`, volumes), noms des entrées d'annulation.

Les widgets sont trouvés par leur `objectName` (`WoodPartTaskPanel`, `lengthEdit`, `TailCount`,
`TailCountAuto`…) : ces noms sont un contrat entre les panneaux et les scénarios. Un nom changé
fait échouer le scénario avec un message explicite (« 0 widgets … dans le panneau … au lieu
d'un »).

Les libellés comparés (entrées d'annulation) sont les chaînes sources de l'atelier, en français :
FreeCAD doit tourner sans traduction de l'atelier vers une autre langue, ce qui est le cas en CI.

## Scénarios

| Module | Ce qui est joué |
|---|---|
| `scenario_queue_aronde` | Deux pièces de 20 cm, la seconde tournée de 90°, queue d'aronde à 10° avec 4 griffes de 30 mm ; capture de la vue 3D. |
| `scenario_annuler_retablir` | Le même, puis Ctrl+Z jusqu'au document vide et Ctrl+Y jusqu'à la fin. |
| `scenario_reouverture` | Enregistrer, fermer, rouvrir (par l'API `saveAs`, `closeDocument`, `openDocument` : les boîtes de fichier ne sont pas jouées), puis modifier l'assemblage par double-clic. |
| `scenario_annulation_panneau` | Chaque panneau ouvert, rempli, puis annulé (bouton Annuler et touche Échap), en création et en modification. |
| `scenario_modifier_piece_assemblee` | Largeur et épaisseur d'une pièce déjà assemblée changées au clavier. |
| `scenario_saisies_hostiles` | 0, négatif, valeur transitoire, texte, 99999 dans les champs du panneau d'assemblage. |
| `scenario_document_ferme` | Document fermé ou changé avec un panneau ouvert (création et modification), panneau annulé pendant une saisie en cours. |
| `scenario_suppression` | Suppression d'un assemblage, d'une pièce assemblée, d'un ensemble avec son contenu (boîte de confirmation). |

Chaque scénario finit par les contrôles communs : aucun objet « Invalid » ni « Touched », formes
valides, aucune transaction ouverte, panneau fermé, vue rapport sans erreur quand le scénario la
surveille. À chaque bug d'enchaînement corrigé, son geste exact s'ajoute à un scénario.

Les scénarios dont les tests sont des étapes numérotées sur un même document héritent de
`aides.Etapes` : après une étape en échec, les suivantes sont sautées.

## Limites connues

- Seuls les panneaux « Pièce en bois » et « Queue d'aronde » sont joués pour l'instant
  (annulation, saisies hostiles) ; les autres panneaux viennent avec les scénarios de priorité 2
  (un par famille de fonctions).
- `scenario_modifier_piece_assemblee` ne joue pas encore une épaisseur qui rompt l'assemblage :
  le comportement attendu est à trancher (message dans le panneau ou non).
- Les boîtes de message de FreeCAD sont répondues par leur bouton standard et comptées, pas
  reconnues à leur titre (il dépend de la langue).

- L'image capturée n'est pas contrôlée (elle sert à la relecture) ; seul `scenario_queue_aronde`
  en prend une, car le rendu `softpipe` qu'elle demande est dix fois plus lent.
- À l'arrêt normal de FreeCAD (`-t`), les enveloppes PySide des widgets sont parfois détruites
  après leurs objets C++ : SIGSEGV dans `Shiboken::BindingManager` après un scénario réussi.
  Le lanceur l'évite (`os._exit`) ; à la main, relancer.
- Une boîte de message modale bloque la boucle d'événements : y répondre par `ReponseAuxBoites`,
  armée avant le geste.
- La vue 3D n'est pas cliquée au pixel près : un clic sur une pièce passe par `Gui.Selection`, un
  glissement à la souris est remplacé par l'écriture du `Placement` dans une transaction.
- Entrée dans un champ valide le panneau (bouton OK par défaut) : `taper` finit par Tab.
- FreeCAD ne rafraîchit l'état de ses boutons que périodiquement : `lancer` attend.
- Avec `-t`, une erreur d'import du module ouvre une boîte de dialogue qui bloque (le lanceur
  en fait un rapport et le code 1) : toujours lancer sous `timeout` en CI.
- `QtTest` vient de `PySide6` (absent de la couche `PySide` de FreeCAD) : réservé aux tests.
