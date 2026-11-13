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

- `gui/task_panels/align.py` importe `report_refusal` de `gui/commands/base.py`, comme le panneau
  de distance : déplacer cette fonction dans un module neutre de `gui/` (revue de la PR #254).
