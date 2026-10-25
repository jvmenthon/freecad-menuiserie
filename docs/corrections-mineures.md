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
| M3 | mineur | `CHANGELOG.md:13`, `tests/integration/bureau.py:28`, ADR 0009, `docs/specs/J4-*.md` | Docs périmées : le CHANGELOG cite `<<Joue gauche>>.Thickness` et `bureau.py` parle de « libellé » alors que les pièces sont citées par leur `Name` ; l'ADR 0009 et la spécification J4 ne renvoient pas à l'ADR 0019 qui les complète. | Écrire `WoodPart001.Thickness` / « Name » ; ajouter un lien « complété par l'ADR 0019 ». |
| M4 | mineur | `tests/integration/bureau.py`, `test_ensemble_membres.py`, `test_ensemble_epaisseurs.py` | Les attentes codent en dur les `Name` générés (`WoodPart001`…) : un ordre de création différent casse les tests sans régression réelle. | Construire les expressions attendues à partir des objets (`f"{joue.Name}.Thickness"`). |
| M5 | mineur | `freecad/menuiserie/core/furniture/_bindings.py` (`same_binding`) | La normalisation des `Name.Thickness` rend une formule de l'utilisateur `Autre.Thickness` égale à une liaison de l'atelier qui citait une autre pièce : « Relier les pièces » peut la prendre pour la sienne et la remplacer. | Ne normaliser que les `Name` des membres de l'ensemble (ou de sa copie), pas tout identifiant suivi de `.Thickness`. |
