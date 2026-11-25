# Corrections mineures à faire

Liste tenue à jour selon la règle de jv (2026-10-23) : chaque relecture classe ses points par
niveau ; les points bloquants et majeurs sont corrigés pendant la relecture, les **mineurs** sont
notés ici et traités lors d'une relecture suivante. Ajouter les nouveaux mineurs, retirer ceux
qui sont corrigés (en citant la PR qui les corrige dans son message de commit).

Niveaux : **bloquant** (faux, plantage, perte de données), **majeur** (comportement gênant,
contournable), **mineur** (confort, docs, dette de test).

## Relecture « épaisseurs fixes » (PR #86, ADR 0019), 2026-10-25

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| M1 | mineur | `freecad/menuiserie/gui/task_panels/furniture.py` (`_locked_toggled`) | Une cote refusée reste affichée en rouge, avec ses cases, après qu'on a décoché « Cotes fixes » de la pièce en cause : le refus ne se réévalue qu'à la saisie suivante. | Après un changement de verrou, recontrôler la cote refusée (`check_resize`) et effacer le refus s'il ne tient plus. |
| M2 | mineur | `freecad/menuiserie/features/furniture_locks.py` (`_locked_keys`) | `unlock_and_resize` et `unlock_and_set_thickness` acceptent des pièces d'un **autre** ensemble : elles sont déverrouillées sans que cela serve. | Refuser (`ValueError` traduite, avant toute écriture) une pièce dont l'ensemble n'est pas celui visé. |
| M3 | mineur | `CHANGELOG.md:13`, `tests/integration/bureau.py:28`, ADR 0009, `docs/specs/J4-ensembles.md` | Docs périmées : le CHANGELOG cite `<<Joue gauche>>.Thickness` et `bureau.py` parle de « libellé » alors que les pièces sont citées par leur `Name` ; l'ADR 0009 et la spécification J4 ne renvoient pas à l'ADR 0019 qui les complète. | Écrire `WoodPart001.Thickness` / « Name » ; ajouter un lien « complété par l'ADR 0019 ». |
| M4 | mineur | `tests/integration/bureau.py`, `test_ensemble_membres.py`, `test_ensemble_epaisseurs.py` | Les attentes codent en dur les `Name` générés (`WoodPart001`…) : un ordre de création différent casse les tests sans régression réelle. | Construire les expressions attendues à partir des objets (`f"{joue.Name}.Thickness"`). |
| M5 | mineur | `freecad/menuiserie/core/furniture/_bindings.py` (`same_binding`) | La normalisation des `Name.Thickness` rend une formule de l'utilisateur `Autre.Thickness` égale à une liaison de l'atelier qui citait une autre pièce : « Relier les pièces » peut la prendre pour la sienne et la remplacer. | Ne normaliser que les `Name` des membres de l'ensemble (ou de sa copie), pas tout identifiant suivi de `.Thickness`. |

## Relecture « souris et distances » (issue #65, ADR 0021 et 0022), 2026-10-25

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| m1 | mineur | `freecad/menuiserie/gui/drag/geometry.py` | `mouse_ray`, le placement des poignées et `MAGNET_PX` sont dans `gui/` alors que l'ADR 0021 (point 2) les met dans `core/magnet` ; le nom `geometry.py` est trompeur (le module dessine). | Déplacer ces trois éléments vers `core/magnet` et renommer `geometry.py` en `drawing.py`. |
| m8 | mineur | `.github/workflows/ci.yml` (étape « Chargement dans l'interface de FreeCAD ») | Le commentaire sur la zone de notifications coupée ne cite pas le ticket FreeCAD de l'interblocage des notifications hors écran. | Citer le ticket FreeCAD dans le commentaire. |

## Relecture de fin de jalon « Pièce en bois » (issue #73, ADR 0020), 2026-10-26

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| p1 | mineur | `freecad/menuiserie/features/shaped_create.py` (`reframe`), `api.reset_shaped_axes` | La garde « Placement piloté par une expression » n'existe que dans le panneau : par l'API, un membre d'ensemble change de repère puis l'expression remet son `Placement`, et la forme bouge. | Déplacer la garde dans `reframe` (`ValueError` traduite), le panneau la réutilise. |
| p3 | mineur | `features/wood_material_proxy.py`, `features/shaped_part.py` | La base commune `MaterialProxy` importe ses aides de `wood_part_restore` ; `shaped_part` ré-exporte `dimensions_of` / `record_of` de `wood_part_record`. | Déplacer les aides de matériau dans `wood_material_restore.py`. |
| p4 | mineur | `features/picked.py` (`furniture_candidate`) | Imports différés pour casser le cycle `picked → machined_part → … → shaped_frame → placement`. | Sortir `to_placement` vers un module de bas niveau (à côté de `rigid_transform`). |
| p5 | mineur | `features/shaped_create.py` (`create_shaped_part`) | La source est lue deux fois (booléennes, `isValid`). | Passer la lecture déjà faite à une fonction interne commune. |
| p6 | mineur | `features/shaped_sources.py` | Une esquisse dans un corps encore sans solide est ramenée au corps et refusée (« corps sans protrusion ») ; cas non testé. | Retomber sur la lecture de profil si le corps n'a pas de solide, ou au moins tester et documenter. |
| p7 | mineur | `features/joints/base.py` | L'avertissement de matière manquante (E3) est réémis à chaque recalcul de l'assemblage. | N'avertir que si le ratio change, ou exposer l'état dans une propriété masquée. |
| p8 | mineur | `docs/specs/piece-en-bois.md` (F2) | Seule la case « Cotes fixes » est grisée ; les options « fixe » des bords restent actives (elles choisissent le côté suivi). | Aligner la formulation de F2 sur ce comportement. |
| p9 | mineur | recette D4, D6 | Texture et accrochage à la conversion ne sont vérifiés que par la recette manuelle. | Ajouter une vérification hors écran. |

## Relecture de fin de jalon « Rotation » (issue #117, ADR 0025 et 0026), 2026-10-29

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| r2 | mineur | `tests/gui/` | Test manquant, non ajouté : Ctrl+Z dans le panneau ouvert après un geste d'anneau (la transaction du panneau est celle qui annule). | Ajouter une vérification hors écran : panneau ouvert, anneau tiré, Ctrl+Z, angle d'avant. |
| r3 | mineur | `tests/gui/verifications_souris_rotation.py` | Test manquant, non ajouté : anneaux d'une pièce rangée dans un conteneur `App::Part` ou `PartDesign::Body` (B5 : les anneaux suivent les axes du conteneur ; seul le calcul pur est testé). | Ajouter une vérification hors écran avec un conteneur tourné. |

## Relecture de fin de jalon « Assemblages en biais » (issue #114, ADR 0024), 2026-11-01

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| b1 | mineur | spec § 7, `features/joints/base.py` | L'avertissement « épaulement très aigu » au-delà de 45° n'est pas implémenté ; B8 prévoit « Biais : 10° », le code affiche une phrase plus longue. | Ajouter l'avertissement dans la vue rapport ; aligner le texte ou la spec. |
| b2 | mineur | `core/furniture/_model.py`, `_edit.py` | `NoticeKind.NOT_SQUARE` et `Follow.NOT_SQUARE` ne sont plus produits depuis AB-d (toute pièce non d'équerre suit par translation). | Retirer les deux valeurs et leurs gabarits à la prochaine évolution du modèle d'ensemble. |
| b3 | mineur | `tests/unit/test_assemblage_biais.py` | Chemins refusés sans test : `NO_WALL` en biais, invitée qui entre par un chant (`OVERLAPPING`), `TOO_SMALL` (polyèdre vide), rainure-languette en biais composé. | Ajouter les cas. |

## Relecture de fin de jalon « Profils d'arête » (issue #5, ADR 0029), 2026-11-01

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| c1 | mineur | `tests/integration/test_profils_piece.py` | L'avertissement d'un profil qui touche un assemblage (B3) n'a pas de test d'intégration. | Ajouter le cas (profil sur l'arête d'un tenon ou d'une rainure, avertissement cité). |
| c2 | mineur | `gui/task_panels/edge_finish.py` | Le panneau ne se ferme pas si la pièce ou le profil est supprimé pendant l'édition (pas de surveillance de suppression). | Fermer le panneau à la suppression de l'objet, comme les autres panneaux. |
| c3 | mineur | `features/edge_profile.py` | Une famille inconnue relue d'un fichier devient silencieusement un chanfrein. | Avertir dans le rapport de l'objet. |
| c4 | mineur | `core/edges/_families.py` | « Demi-rond » donne la même section que « Congé » (b = a) ; seule la cote B ignorée les distingue. | Documenter, ou ajouter automatiquement l'arête opposée. |
| c5 | mineur | `core/edges/_ids.py`, messages | Noms et codes d'arêtes cités dans les messages non traduisibles. | Passer les noms par `QT_TRANSLATE_NOOP`. |
| c6 | mineur | `gui/task_panels/edge_finish.py` | Aperçu lourd : recalcul complet du document et rapport bavard à chaque saisie. | Utiliser `recompute_preview`, regrouper les rapports. |
| c7 | mineur | `docs/specs/finition-des-chants.md`, `CONTRIBUTING.md` | Écarts spec/docs : A3 `profile_section` n'existe pas, « carré a×b » faux pour le bec, liste d'objets de CONTRIBUTING.md non mise à jour, `getattr(..., "Finishes", ())` à harmoniser. | Aligner la spec et la liste. |
## Relecture de fin de jalon « Ensemble à la souris » (ADR 0038), 2026-11-07

Les points majeurs et les mineurs 8, 9 et 13 de cette relecture sont corrigés dans la branche
`fix/ensemble-souris-revue` ; restent les points suivants (e13 corrigé : spec § 2.2 et § 4.2, note
« amendé par l'ADR 0038 » dans l'ADR 0008).

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| e10 | mineur | `gui/drag/furniture_target.py:117-127` | Ensemble ancien sans Std Part : les poignées avant, gauche et basse sont affichées mais toujours refusées. | Les masquer, ou retomber sur `Origin` pour ces trois faces. |
| e11 | mineur | `features/furniture_container.py:135` (`guide_container`) | Un ancien ensemble rangé dans un `App::Part` de l'utilisateur rend ce conteneur transparent pour l'aimant. | Limiter la transparence aux Std Parts propres (`carried_furniture`). |
| e12 | mineur | `features/states.py` (`_finish`), `features/furniture_drag.py:297` | `LockedPiecesError` au relâchement n'est traitée que dans la vue rapport : pas de « Déverrouiller et appliquer » dans la vue 3D, contrairement à ce que dit la docstring. | Corriger la docstring, ou ajouter la proposition dans la vue 3D. |
| e14 | mineur | `tests/` | Tests manquants : Ctrl+Z / Ctrl+Y de `make_furniture` (Std Part), Ctrl+Y d'un geste, « Annuler » du panneau après un geste et une saisie d'angle, réouverture d'un document au sous-ensemble déplacé ou tourné, taille et rotation d'un sous-sous-ensemble. | Ajouter les vérifications (intégration et GUI hors écran). |
| e15 | mineur | `gui/drag/furniture_target.py:137`, `core/geometry.py` (`_box_drawing`), `features/furniture_drag.py:131` et `:216` | Code dupliqué : les huit coins d'une boîte ; le décalage tourné suivi de `write_std_placement`. | Factoriser en `box_corners` et en `_shifted_placement`. |
| e16 | mineur | `tests/gui/verifications_souris_ensemble.py` | Le fichier fait 661 lignes. | Le découper par thème (taille, déplacement, rotation, sous-ensemble, panneau). |

## Relecture « assemblages en biais, suite » (issue #78, ADR 0034), 2026-11-07

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| s1 | mineur | `features/joints/base.py` (résumé du panneau) | T3 : la ligne « Biais » du panneau n'existe pas pour feuillure, mi-bois, onglet, tourillons, queue d'aronde. | Ajouter les champs `oblique`/`cut_angle` aux valeurs effectives de ces types. |
| s3 | mineur | feuillure, mi-bois, onglet | Pièces au contact en biais refusées (`OBLIQUE_OVERLAP_ONLY`). | Prolonger l'invitée par le coin ajouté (ADR 0014 en biais). |

## Jalon « Quincaillerie » (issue #159, ADR 0033), 2026-11-06

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| Q1 | mineur | `freecad/menuiserie/data/quincaillerie.json` | Cotes des biscuits Lamello saisies de mémoire d'après les tableaux publics, non relues sur fiche (marquées « à confirmer »). Les Domino ont été relus sur les fiches Festool le 2026-11-06. | Comparer avec la fiche Lamello, puis retirer la mention. |
| Q2 | mineur | `features/joints/slots.py` | Le choix entre liste de tailles et taille personnalisée est fixé (liste par défaut pour les faux tenons). jv veut pouvoir régler ce comportement par défaut dans la configuration de l'atelier (issue #148). | Lire le réglage de l'atelier à la création de l'assemblage. |
| Q3 | mineur | `features/joints/slots.py`, `core/cutlist` | La référence choisie (`reference=`) fixe les cotes mais n'est pas mémorisée sur l'assemblage : la liste de débit n'a ni fabricant ni référence, seulement taille et quantité. | Propriété `Reference` sur l'assemblage et colonnes fabricant / référence du CSV (spec § 8). |
| Q4 | mineur | `gui/task_panels/joint.py` | Pas de panneau de choix de référence (filtre par type et mot-clé, spec § 7) : la référence ne se choisit que par l'API. | Liste filtrable de `core.hardware.Catalog.search` dans le panneau de l'assemblage. |
| Q5 | mineur | `core/hardware/_families.py` | Familles vis, charnière et coulisse : cotes validées, mais aucune forme ni pose (lots Q-e à Q-g). | Lots ultérieurs de la spec § 10. |
| Q6 | mineur | `core/hardware/_parser.py` (`parse_item`) | Une clé en double dans `params` (objet imbriqué) n'est pas signalée : la dernière valeur gagne en silence ; seule une clé en double au niveau de l'entrée est refusée. | Refuser aussi un `JsonObject` en `params`. |
| Q7 | mineur | `core/joints/slots.py` | Une mortaise peut toucher le bord du contact (marge de tolérance seulement) et ouvrir le chant de la pièce. | Exiger une paroi minimale (`MIN_WALL_MM`) entre la mortaise et le bord du contact. |
| Q8 | mineur | `core/joints/slides.py` | La coulisse est une boîte simple et ses avant-trous du côté du tiroir reprennent les positions du côté du caisson ; la coulisse réelle (rail, billes, verrou) et sa fixation propre ne sont pas modélisées. | Famille de coulisses avec cotes de fixation propres à chaque côté. |
| Q9 | mineur | `core/joints/feet.py` | Les pieds ne se posent que sous un panneau couché dans le repère du document ; pas de pied sur un panneau en biais ni de position libre (grille régulière seulement). | Positions saisies ou pose depuis une face choisie. |

## Relecture « factorisation » du jalon quincaillerie (PR #164), 2026-11-07

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| Q10 | mineur | `features/joints/{feet,slides,shelf_pins,slots}.py` | Les `PropertySpec` « diamètre/profondeur des trous », « distance au bord », « nombre » se répètent (environ 10 lignes chacune). Une fabrique ne gagnerait presque rien : l'extraction des traductions exige `QT_TRANSLATE_NOOP("…", "texte")` littéral à l'endroit de la propriété, donc infobulle et libellé restent écrits à chaque appel. | Abandonné tant que l'extraction des traductions ne lit pas les paramètres de fabrique. |
| Q11 | mineur | `core/joints/slides.py` | 316 lignes : à passer en paquet comme `shelf_pins` et `slots` (ADR 0040) avant d'approcher 400. | Même découpage `_params` / `_strategy`. |

## Panneau « Structure » (ADR 0046) : points restants, 2026-11-11

Tous les autres mineurs des relectures du panneau (lots 1 à 4, reprise sur `main`, revue finale, lecteur
de répétitions m5) sont corrigés.

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| S7 | mineur | `features/structure_source.py` (`DocumentStructure`) | Le lecteur est reconstruit à chaque rafraîchissement : `foreign_objects` lit `InList` et `OutList` de tous les objets, ce qui devient mesurable sur un très gros document (non mesuré). Impossible à trancher sans FreeCAD : il faut une mesure réelle. | Mesurer sur un document de 1 000 objets avant d'optimiser ; sinon, rien à faire. |

## Relecture finale du jalon « Répétition » (issue #180, ADR 0043 et 0044), 2026-11-08

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| rp1 | mineur | `features/repeat.py` | `Step` et `Reverse` de la répétition sont modifiables dans l'éditeur de propriétés sans que l'ensemble soit relié (les copies de membres suivent, pas les liaisons de l'ensemble). | Les passer en lecture seule, ou relier l'ensemble à chaque changement. |
| rp2 | mineur | `gui/task_panels/repeat.py` (docstring l. 13 et 362) | L'aperçu ne garde pas le dernier réglage accepté si `bind_furniture` lève après la création des copies. | Défaire les copies créées avant de rendre le refus, ou valider les liaisons avant de créer. |
| rp3 | mineur | `features/repeat_copies.py`, `repeat_furniture_links.py`, `repeat_follow.py`, `repeat_joints.py`, `repeat_links.py`, `core/repeat/`, `gui/drag/copy_rules.py` | Duplications : `_SIZES` et la table axe → cote ; `_AXES`, `COMPONENTS` et `copy_rules._AXES` ; `_during_deletion` ≡ `restoring_or_undoing` ; calcul de la longueur répété dans `repeat_follow` ; `resolve_for` et `source_extent` recalculés trois fois par saisie ; littéral `"joint_derived"` répété. | Une table d'axes dans `core/repeat`, réemployer `restoring_or_undoing`, une fonction de longueur, un résultat mis en cache par saisie, une constante pour `joint_derived`. |
| rp4 | mineur | `features/repeat.py` (`copies_of`) | `copies_of(repeat)` renvoie aussi les copies de membres d'un ensemble copie, ce que ne dit pas la docstring. | Préciser la docstring ou séparer `copies_of` et `inner_copies_of`. |
| rp5 | mineur | `features/` (préexistant) | Supprimer directement un membre d'un ensemble copie par `doc.removeObject` laisse des assemblages invalides. | Retirer les assemblages du membre dans `unsetupObject`. |
| rp6 | mineur | `tests/gui/` | Pas d'essai en interface réelle d'un Ctrl + glisser sur une pièce tournée hors multiple de 90° (refus), ni sur une pièce d'un conteneur tourné. | Ajouter une vérification hors écran avec un conteneur tourné. |


## Répétition en grille (ADR 0045), 2026-11-08

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| rg1 | mineur | `core/repeat/_model.py` (`RepeatParams._set_grid`) | Pour une grille, `axis`, `count`, `step`, `span` et `reverse` reflètent la première ligne (compatibilité avec le code à un axe) : `replace(params, axis=...)` est sans effet sur une grille, qui l'emporte. | Retirer les champs reflets quand plus aucun appelant ne lit `params.axis` / `params.count`, et ne garder que `lines`. |
| rg2 | mineur | `features/repeat_props.py` | Les propriétés `Step2`/`Reverse2`/`Step3`/`Reverse3` restent visibles et modifiables dans l'éditeur quand la ligne est inutilisée (`Axis2` = `None`) ; même réserve que rp1 (ensemble non relié). | Les masquer (mode d'édition) tant que la ligne n'est pas utilisée ; voir rp1. |
| rg3 | mineur | `core/repeat/_grid.py` (`grid_overlaps`, `rank_of`) | Comparaison deux à deux de toutes les boîtes (101 au plus, environ 5 000 paires) à chaque saisie du panneau, et recherche linéaire du rang. Sans effet mesurable à 100 copies, mais inutilement quadratique ; `grid_overlaps` vaut d'ailleurs « un axe au moins se chevauche » (vérifié par tests). | Sortie anticipée ou test par axe seulement ; table cellule → rang calculée une fois par grille. |
| rg4 | mineur | `features/repeat_copies.py` (`_renumber`) | Le rang et les libellés automatiques suivent la grille, mais un libellé de copie que l'utilisateur a tapé à la main et qui ressemble au libellé automatique d'un autre rang est pris pour automatique. | Mémoriser le libellé attribué (propriété cachée) plutôt que le déduire. |
| rg5 | mineur | `gui/task_panels/repeat.py` | En « pas sur une longueur », le nombre calculé d'un axe est écrit dans son champ masqué : si l'on revient en « nombre et pas », le nombre repart de cette valeur et pas de celle que l'on avait saisie. Même comportement qu'avant la grille. | Garder la saisie et la valeur calculée dans deux champs distincts. |


## Pièce créée contre une face (PR #252), 2026-11-16

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| pf2 | mineur | `core/snap/_perpendicular.py` (`footprint`, `face_section`) | Les colonnes largeur / épaisseur de l'orientation sont lues de la même façon dans les deux fonctions (motif proche). | Un petit helper commun « axe de la pièce selon l'axe d'appui ». |
| pf3 | mineur | `features/snap_local_face.py` (`fit_to_footprint`) | Jusqu'à 18 appels `common` OCC à chaque départ perpendiculaire (3 reprises × 2 axes × 3 sondes). | Mesurer ; sortir tôt quand l'étendue ne change pas à la première reprise. |
| pf4 | mineur | `tests/integration/test_accrochage_perpendiculaire.py` | Seuil de volume résiduel `1e-2` littéral ; pas de test isolé de `fit_to_footprint` (cas « rien ne change »). | Nommer la constante ; test avec fausse face. |
| pf5 | mineur | `features/perpendicular.py` (`_nearest_edge_row`) | Seuls les deux côtés du repère d'appui (parallèles aux axes de la pièce porteuse) sont regardés : près d'une arête oblique, la pièce suit l'axe le plus proche sans tourner vers l'oblique (elle ne déborde pas). | Si jv le demande : orienter la pièce selon une arête oblique (rotation hors des 24 orientations). |
| pf6 | mineur | `features/perpendicular.py` (`perpendicular_start`) | Second test `edge_row is None` sans effet en pratique (le repère local n'existe qu'avec un clic) ; fonction longue, six sorties (limite). | `along_edge(orientation, row: int \| None)` ; extraire `_edge_aware_orientation`. |
| pf7 | mineur | `core/snap/_perpendicular.py` (`face_section`, `along_edge`) | Condition dense dans `face_section` ; `abs(x.component(row)) == 1.0` répété ; entiers nus `(0, 1)` pour les axes du plan. | Helper `_follows(vector, row)`, booléen nommé, constante `_FACE_AXES`. |
| pf8 | mineur | `features/perpendicular.py` (`_nearest_edge_row`) | Commentaires « côté qui suit y » peu intuitifs (distance = produit scalaire avec l'autre axe). | Une phrase d'explication. |

- `gui/task_panels/align.py` importe `report_refusal` de `gui/commands/base.py`, comme le panneau
  de distance : déplacer cette fonction dans un module neutre de `gui/` (revue de la PR #254).
- `gui/task_panels/align.py` : aucun test GUI ne couvre l'envoi forcé de la position automatique
  sur un axe ; `_combo_row` pourrait recevoir ses éléments en paramètre (revue de l'alignement
  sur un axe, PR #254).
- `core/align/_align.py` (`_squared`, revue de la mise en parallèle, PR #254) : à 45° ± bruit
  numérique, le choix du quart de tour peut basculer d'un sens à l'autre (inhérent à l'arrondi) ;
  `Alignment.angle` ne compte pas ce tour en plus (non affiché aujourd'hui) ; `_product` irait
  mieux dans `core/geometry.py` avec `Matrix3`.

## Relecture « nommage topologique » (PR #255, ADR 0056), 2026-11-13

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| nt1 | mineur | `features/solids.py` (`machined_shape`), ADR 0056 | La carte des éléments de la pièce usinée est enregistrée dans le `.FCStd` et tenue à chaque booléenne : taille du fichier et temps de recalcul non mesurés sur un meuble réel (plusieurs dizaines d'assemblages). | Mesurer taille et temps avant/après sur un meuble de référence ; documenter le résultat dans l'ADR 0056. |

## Relecture « scénarios QTest de priorité 1 » (PR #263, ADR 0059), 2026-11-15

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| qt1 | mineur | `features/structure_source.py` (`renamed_object`), `features/machined_part.py` (`blank_of`) | La condition « pièce usinée dont la brute existe » est écrite deux fois. | Une fonction partagée (`has_blank`) utilisée par les deux. |
| qt2 | mineur | `gui/double_click.py`, `gui/part_appearance.py`, `gui/structure_sync.py`, `gui/commands/cutlist.py`, `gui/view_providers/repeat.py` | Lectures `getattr(x, "ViewObject", None)` qui ne passent pas par `display_io.view_object_of` (non exposées à la fermeture d'un document à ce jour). | Les remplacer au fil de l'eau. |
| qt3 | mineur | `tests/qtest/scenario_annulation_panneau.py`, `scenario_annuler_retablir.py`, `scenario_reouverture.py` | Deux fonctions `etat` proches ; `fermer_le_document_actif` refait `aides.fermer` ; `setUpModule` recopié dans chaque module. | Regrouper dans `aides.py` quand les scénarios de priorité 2 arrivent. |

## Audit FreeCAD 1.0 / 1.1, 2026-11-14

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| fc1 | mineur | `gui/task_panels/furniture_widgets.py`, `joint.py`, `carcass.py`, `repeat.py` (`_ERROR_STYLE`, `_HINT_STYLE`, `_WARNING_STYLE`) | Couleurs de texte fixes (`#c0392b`, `#6b6b6b`, `#b35c00`) : le thème sombre livré avec FreeCAD 1.0 les rend peu contrastées (environ 3 : 1). | Prendre la couleur dans la palette Qt (`palette(placeholder-text)` pour l'aide) et éclaircir le rouge et l'orange ; à valider par jv sur les deux thèmes. |
| fc2 | mineur | `gui/cutlist_preview.py` (`setStyleSheet("... #ffffff")`) | Fond blanc forcé sans couleur de texte : en thème sombre, le texte hérité peut être clair sur blanc. | Fixer aussi `color` (noir) dans la même feuille de style. |

## Coplanarité (PR #262, ADR 0058), 2026-11-15

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| cp1 | mineur | `features/repeat_coplanar.py` (`RepeatPlanes`) | Seul le conteneur de la première source est lu : des sources de conteneurs différents ne voient pas les voisines des autres. | Lire les voisines de chaque conteneur distinct (même repère de répétition). |
| cp2 | mineur | `features/magnet_guides.py` (`neighbor_planes`) | Voisines lues dans l'ordre du document (pas les plus proches d'abord) : au-delà de `MAX_GUIDES`, des voisines utiles peuvent manquer. | Passer l'enveloppe des sources en `reference`. |
| cp4 | mineur | `gui/task_panels/repeat_coplanar.py` (`CoplanarCues.show`) | `except Exception` avale l'erreur sans trace (voulu : le repère ne doit pas casser l'aperçu). | Journaliser en debug (`App.Console.PrintLog`). |
| cp5 | mineur | `gui/drag/states.py` (`Dragging.lit`), `core/magnet/_coplanar.py` (`PlaneIndex.coplanar`) | Même recherche « voisines d'une face » avec deux règles d'affichage. | Regrouper au 3e usage. |
| cp6 | mineur | `gui/task_panels/repeat.py` (`_field_changed`), `repeat_field_snap.py` (`with_field`) | `kind` est une chaîne « step » / « span » ; tout autre texte est pris pour `span`. | `Literal["step", "span"]` ou petit `Enum`, `ValueError` sinon. |
| cp7 | mineur | `gui/task_panels/repeat.py` (`__init__`) | Le panneau note lui-même chaque champ dans `FieldSnap` après `_fill`. | Méthode `FieldSnap.sync()` qui lit `rawValue` de chaque champ. |
| cp8 | mineur | `gui/task_panels/repeat_coplanar.py` (`_never`, `_snapped`) | Deux petits helpers de module là où une `partial` suffirait. | Simplifier au prochain passage. |
| cp9 | mineur | `core/magnet/_coplanar.py` (`snap_field`) | `slopes or ()` répété alors que `slopes` peut valoir `None`. | `slopes = _slopes(...) or []` dès le départ. |

## Grille « Parallèle et aligner sur » (PR #269, ADR 0066), 2026-11-17

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| al1 | mineur | `core/align/_align.py` (`face_center`) | Plus utilisée en production (seulement par les tests), mais toujours exportée par la façade ; `_layout._corners` fait presque le même calcul. | La déplacer dans les tests ou la calculer depuis `_corners`. |
| al2 | mineur | `gui/task_panels/align_layout.py` (`_ANCHORS`, `"parallel"`) | Les chaînes `start` / `center` / `end` / `parallel` sont répétées dans la GUI et dans `features/part_align.py` sans test qui fixe le contrat. | Importer des constantes publiques (`Anchor.value`, une clé `PARALLEL_KEY`) ou ajouter un test de cohérence. |
| al3 | mineur | `gui/task_panels/align_layout.py` (`_COLORS`) | Couleurs des axes répétées en littéraux (aussi dans les outils d'icônes). | Une constante partagée si un 3e usage apparaît. |
| al4 | mineur | `features/part_align.py` (`_shown`), `align_layout.py` (`_refresh`), `align.py` | `_shown` après la classe avec une fonction imbriquée ; `axis not in self._across` sur une chaîne ; `with self._guard` redondant autour des réglages de la grille. | Remonter `_shown`, utiliser un `frozenset`, retirer la garde redondante. |

## Dissocier la répétition (PR #260, ADR 0067), 2026-11-24

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| dr1 | mineur | `core/repeat/_model.py` (`copy_name`) | Une source déjà nommée « Montant (2) » donne des copies « Montant (2) (2) ». | Retirer le suffixe « (n) » de la source avant de numéroter, si jv le souhaite. |
| dr2 | mineur | `core/repeat/_model.py` (`is_copy_name`) | Un nom « Barreau 3 » saisi à la main sur la copie de rang 2 est pris pour l'ancien nom automatique et renommé « Barreau (n) » quand le rang change. | Accepté (ancien format) ; à revoir si un document le montre. |
| dr3 | mineur | `gui/commands/repeat.py`, `gui/structure_actions.py` | Après Ctrl+Z, les copies restent « Touched » jusqu'au recalcul suivant (comportement de FreeCAD). | Recalculer après l'annulation si cela gêne. |
| dr4 | mineur | `features/repeat_copies.py` (`_bind_furnitures`), `features/furniture_variants.py` | Le choix des notices montrées selon l'opération (copie : sans DRAWN_SIZE ; redimensionnement) est écrit à deux endroits. | Un prédicat ou une constante nommée dans `core/furniture`, partagé par les deux appelants. |
