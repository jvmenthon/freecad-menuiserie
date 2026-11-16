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
| Cocher une case, cliquer un bouton | `cliquer(widget)` (sur la case elle-même pour une case à cocher) |
| Choisir une ligne d'une liste déroulante | `choisir(liste, rang)` (flèches Haut et Bas) |
| Valider le panneau | `cliquer(bouton_ok())` |
| Annuler, rétablir | `lancer("Std_Undo")`, `lancer("Std_Redo")` |
| Cliquer des pièces dans la vue 3D | `selectionner(a, b)` (`Gui.Selection`) |
| Cliquer des faces dans la vue 3D | `selectionner_des_faces((a, "Face6"), (b, "Face5"))` ; `pieces.face_vers(a, (0, 0, 1))` donne le nom de la face |
| Passer à un autre document ouvert | `passer_a(doc)` (onglet de sa vue 3D) |
| Annuler le panneau | `cliquer(bouton_annuler())`, `appuyer_sur_echap(champ)` |
| Répondre à une boîte de message | `with ReponseAuxBoites(OUI) as boites:` autour du geste qui l'ouvre (bouton standard `OUI`, `NON` pour une boîte de FreeCAD, début du texte du bouton pour une boîte de l'atelier) |
| Lire et refermer le refus d'une commande | `refus_signale()` (texte de la boîte d'avertissement de l'atelier, « » s'il n'y en a pas) |
| Enregistrer un fichier | `with ReponseAEnregistrer(chemin):` autour du geste qui ouvre la boîte d'enregistrement |
| Choisir dans un menu contextuel | `with ReponseAuMenu("Renommer"):` autour de `clic_droit(zone, point)` (un texte par niveau de sous-menu) |
| Répondre à une boîte de saisie de texte | `with ReponseALaSaisie("Tasseau"):` autour du geste qui l'ouvre |
| Glisser-déposer une ligne d'un arbre | `glisser(zone, depart, arrivee)` (deux fonctions qui donnent les points au moment du geste) |
| Lire les erreurs affichées | `vue_rapport()` après `vider_la_vue_rapport()` ; `pieces.erreurs_python(texte)` en tire les erreurs Python |

`taper`, `cliquer` et `choisir` refusent un widget masqué, grisé ou en lecture seule : le geste
passerait sans rien faire et le scénario ne vérifierait plus rien. Pour vérifier qu'un bouton
grisé ne fait rien, `cliquer(bouton, meme_grise=True)`.

Les gestes du couple de pièces assemblé par une queue d'aronde (créer une pièce, la poser, régler
un champ, double-cliquer un objet) et les contrôles communs (`controler_le_document`) sont dans
`tests/qtest/angle_a_queues.py`, partagés par les scénarios. Les scénarios dont le sujet n'est pas
la création d'une pièce partent des dispositions de `tests/qtest/pieces.py` (montant et traverse,
angle de caisse, cadre de quatre pièces), posées par l'API publique.

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
| `scenario_cadre_et_debit` | Cadre de quatre pièces, quatre tenons-mortaises, aperçu de la liste de débit, export CSV par la boîte d'enregistrement, pièce sans repère numérotée, feuille « Liste de débit ». |
| `scenario_types_d_assemblage` | Chacun des neuf types d'assemblage : création en automatique, chaque case « Auto » décochée et sa valeur retapée, « Inverser » deux fois, deux Ctrl+Z. |
| `scenario_biais` | Tenon-mortaise à 15° puis 45°, chaque référence du biais, traverse élargie ; mi-bois refusé sans chevauchement, accepté à cheval. |
| `scenario_ensemble` | Ensemble créé, pièce ajoutée, pièce ajoutée hors de la boîte (elle grandit), largeur retapée, hauteur refusée (les épaisseurs ne suivent pas), « cotes fixes » puis « Déverrouiller et appliquer », rotation de 90°, assemblage entre deux ensembles refusé (issue #209, à retourner quand elle sera corrigée). |
| `scenario_repetition` | Traverse assemblée répétée 4 fois, nombre puis pas changés, copie dissociée, assemblage posé à la main sur une copie. |
| `scenario_rotation` | Quarts de tour et champs d'angle du panneau, sur une pièce libre, une pièce assemblée (fenêtre « Assemblage défait », les deux réponses) et une pièce d'un ensemble. |
| `scenario_aligner_et_distance` | « Aligner deux faces » (chaque mode, centrer X, Y et Z, décalage, inverser), puis une distance gardée : définie, tenue quand la pièce de référence est déplacée puis l'ensemble relié, tenue quand l'ensemble s'élargit, réglée, abandonnée. |
| `scenario_quincaillerie` | Caisson, pieds, perçage au pas de 32 mm (rangs retapés jusqu'au refus et jusqu'au plafond du champ), hauteur du caisson changée, côté devenu trop petit (refus dans le panneau, « OK » grisé). |
| `scenario_piece_depuis_un_corps` | Corps PartDesign converti en pièce en bois, tenon-mortaise dessus, corps allongé. |
| `scenario_panneau_structure` | Panneau « Structure » : clic sur une ligne, menu contextuel (renommer, sortir de l'ensemble, supprimer), pièce glissée dans un ensemble. |
| `scenario_autres_ateliers` | Passage par l'atelier Part avec un panneau ouvert, commandes de Part, vue TechDraw de la pièce usinée, retour dans l'atelier. |
| `scenario_activation_des_commandes` | Boutons actifs pour 0, 1, 2 et 3 pièces sélectionnées, avec un panneau ouvert, et pour des faces, un ensemble, un membre ; ligne « Prérequis » des infobulles. |
| `scenario_deux_documents` | L'angle à queue d'aronde construit dans deux documents en alternance, puis comparés. |

Chaque scénario finit par les contrôles communs : aucun objet « Invalid » ni « Touched », formes
valides, aucune transaction ouverte, panneau fermé, vue rapport sans erreur quand le scénario la
surveille. Un scénario qui annule finit par rétablir (`pieces.retablir_tout`) et recontrôle le
document. À chaque bug d'enchaînement corrigé, son geste exact s'ajoute à un scénario.

Les scénarios dont les tests sont des étapes numérotées sur un même document héritent de
`aides.Etapes` : après une étape en échec, les suivantes sont sautées.

## Limites connues

- Pas encore de scénario pour les profils d'arête ni pour les plans cotés : leurs commandes ne
  sont pas dans `main` ; ils viendront avec elles. Le corps à plusieurs solides (issue #257)
  aussi.
- `scenario_modifier_piece_assemblee` ne joue pas encore une épaisseur qui rompt l'assemblage :
  une boîte de choix est prévue (épaissir vers l'intérieur, vers l'extérieur, agrandir l'autre
  pièce, annuler), le scénario viendra avec elle.
- Le panneau « Structure » ne renomme que par son menu contextuel : la touche F2 n'y est pas
  branchée, le scénario ne la joue pas.
- Le déplacement d'une pièce à la souris dans la vue 3D n'est pas joué (ADR 0059) : les scénarios
  écrivent le placement dans une transaction (`pieces.deplacer`), ce qui ne passe pas par la
  séance de glissement de l'atelier.
- Une réponse de minuterie abandonne après `ESSAIS_MAX` essais et referme la fenêtre : le
  scénario échoue au lieu de bloquer FreeCAD jusqu'au délai de la CI.
- `ReponseAEnregistrer` pilote la boîte d'enregistrement de Qt (celle de FreeCAD sous Xvfb) :
  la boîte native de Windows ou d'un bureau Linux n'est pas un widget Qt.
- Les lignes d'un arbre (`QTreeWidgetItem`) sont recréées à chaque rafraîchissement : un scénario
  qui en garde une fait planter FreeCAD à la fermeture du document ; la retrouver par son texte
  à chaque geste (`scenario_panneau_structure`).
- Un menu contextuel, une boîte de saisie et un glisser-déposer bloquent la boucle d'événements
  comme une boîte modale : la réponse part d'une minuterie armée avant le geste.
- Non simulés : le dessin d'un corps PartDesign, la création d'une page TechDraw, le choix de
  l'atelier dans la liste de FreeCAD (faits par le script).
- Les boîtes de message de FreeCAD sont répondues par leur bouton standard et comptées, pas
  reconnues à leur titre (il dépend de la langue).

- L'image capturée n'est pas contrôlée (elle sert à la relecture) ; seul `scenario_queue_aronde`
  en prend une, car le rendu `softpipe` qu'elle demande est dix fois plus lent.
- À l'arrêt normal de FreeCAD (`-t`), les enveloppes PySide des widgets sont parfois détruites
  après leurs objets C++ : SIGSEGV dans `Shiboken::BindingManager` après un scénario réussi.
  Le lanceur l'évite (`os._exit`) ; à la main, relancer.
- Une boîte de message modale bloque la boucle d'événements : y répondre par `ReponseAuxBoites`,
  armée avant le geste.
- La vue 3D n'est pas cliquée au pixel près : un clic sur une pièce ou une face passe par
  `Gui.Selection`, un
  glissement à la souris est remplacé par l'écriture du `Placement` dans une transaction.
- Entrée dans un champ valide le panneau (bouton OK par défaut) : `taper` finit par Tab.
- FreeCAD ne rafraîchit l'état de ses boutons que périodiquement : `lancer` attend.
- Avec `-t`, une erreur d'import du module ouvre une boîte de dialogue qui bloque (le lanceur
  en fait un rapport et le code 1) : toujours lancer sous `timeout` en CI.
- `QtTest` vient de `PySide6` (absent de la couche `PySide` de FreeCAD) : réservé aux tests.
