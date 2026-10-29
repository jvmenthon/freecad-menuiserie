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
| m2 | mineur | `freecad/menuiserie/core/geometry.py` (`Vec3`) | `Vec3` n'a ni addition, ni soustraction, ni produit par un réel : six réécritures composante par composante dans `core/magnet`, `features/part_drag.py` et `gui/drag/`. | Ajouter `__add__`, `__sub__` et `scaled()` à `Vec3` et supprimer les six réécritures. |
| m5 | mineur | `freecad/menuiserie/gui/drag/events.py` (`_Installation.uninstall`) | Quatre `try/finally` imbriqués pour que chaque retrait soit tenté même si un autre échoue. | Utiliser `contextlib.ExitStack` (un `callback` par retrait). |
| m8 | mineur | `.github/workflows/ci.yml` (étape « Chargement dans l'interface de FreeCAD ») | Le commentaire sur la zone de notifications coupée ne cite pas le ticket FreeCAD de l'interblocage des notifications hors écran. | Citer le ticket FreeCAD dans le commentaire. |

## Relecture de fin de jalon « Pièce en bois » (issue #73, ADR 0020), 2026-10-26

| N° | Niveau | Où | Problème | Correction proposée |
|----|--------|----|----------|---------------------|
| p1 | mineur | `freecad/menuiserie/features/shaped_create.py` (`reframe`), `api.reset_shaped_axes` | La garde « Placement piloté par une expression » n'existe que dans le panneau : par l'API, un membre d'ensemble change de repère puis l'expression remet son `Placement`, et la forme bouge. | Déplacer la garde dans `reframe` (`ValueError` traduite), le panneau la réutilise. |
| p2 | mineur | `freecad/menuiserie/core/shaped/_vec.py` | Reprend `core/snap/_vec.py` (dot, cross, norm, scale, unit, is_finite). | Un seul module de vecteurs partagé dans `core/` (avec m2). |
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
| r1 | mineur (question de conception pour jv) | `freecad/menuiserie/gui/drag/session.py` (`Rotating._follow`, `snapped_angle(self.total, …)`) | L'aimant de l'anneau porte sur l'angle **parcouru** et non sur l'angle **obtenu** : une pièce à 7,3° ne revient jamais d'équerre en la tirant par l'anneau (7,3° + multiples de 15°). | À poser à jv : aimanter l'angle obtenu (orientation du début + angle parcouru, ramenée au multiple de 15° le plus proche) ou garder l'angle parcouru ? |
| r2 | mineur | `tests/gui/` | Test manquant, non ajouté : Ctrl+Z dans le panneau ouvert après un geste d'anneau (la transaction du panneau est celle qui annule). | Ajouter une vérification hors écran : panneau ouvert, anneau tiré, Ctrl+Z, angle d'avant. |
| r3 | mineur | `tests/gui/verifications_souris_rotation.py` | Test manquant, non ajouté : anneaux d'une pièce rangée dans un conteneur `App::Part` ou `PartDesign::Body` (B5 : les anneaux suivent les axes du conteneur ; seul le calcul pur est testé). | Ajouter une vérification hors écran avec un conteneur tourné. |
