# ADR 0013 — Liste de débit vivante : objet `CutList` qui réécrit sa feuille au recalcul

- Statut : **accepté** (jv, 2026-10-22, réponse Q3 b de la spécification J2) ; remplace l'ADR 0012 ;
  point 1 corrigé et point 5 tranché par l'addendum J2f (en fin de document)
- Date : 2026-10-22
- Spécification : [docs/specs/J2-liste-de-debit.md](../specs/J2-liste-de-debit.md), § 10
- ADR liés : [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0012 — Liste de débit calculée à la demande](0012-liste-de-debit-a-la-demande.md) (remplacé)

## Contexte

jv veut que la liste se mette à jour toute seule (Q3 b). FreeCAD ne recalcule un objet que s'il
est marqué ou si l'un des objets qu'il **lie** a changé ; un `Spreadsheet::Sheet` ordinaire ne
dépend pas des pièces. Un observateur de document (`slotRecomputedDocument`) réécrirait la feuille
hors du recalcul, donc hors de l'ordre des dépendances et dans des transactions d'annulation
inattendues.

## Décision

1. Un objet `Menuiserie::CutList` (`App::FeaturePython`, sans forme, `Version` 1, proxy sans
   état) porte : `Sheet` (`App::PropertyLink` vers la feuille, qu'il réécrit), `Scope`
   (`App::PropertyLinkListHidden` : objets choisis, vide = tout le document), `Sources`
   (`App::PropertyLinkListHidden`, **`App::PropertyLinkList` d'après l'addendum** : brutes, pièces usinées, liens et assemblages lus au dernier
   calcul, pour que FreeCAD le recalcule **après** eux et dès que l'un change).
2. `execute` : collecte (lecture seule, J2c), calcule, réécrit les colonnes A–O de la feuille,
   puis met `Sources` à jour si l'ensemble des objets lus a changé. `mustExecute` renvoie vrai
   quand un objet de l'atelier a été ajouté ou supprimé depuis le dernier calcul (comparaison
   des noms), pour que la création ou la suppression d'une pièce soit vue.
3. La feuille reste un `Spreadsheet::Sheet` standard, sans proxy, marquée `MenuiserieCutList`
   (ADR 0012, point 2 conservé) ; les colonnes `P` et au-delà restent à l'utilisateur.
4. Nul ne dépend de `CutList` (feuille de l'arbre des dépendances) : aucun cycle possible avec les
   ensembles et leurs expressions. `CutList` n'écrit que dans lui-même et dans sa feuille.
5. **À vérifier dès le début de J2f sur FreeCAD 1.0 et 1.1** : modifier `Sources` dans `execute`
   sans boucle ni avertissement ; `mustExecute` d'un proxy Python appelé à chaque recalcul. Repli
   si l'un échoue : `Sources` mis à jour par un observateur limité aux documents qui contiennent un
   `CutList` (`slotCreatedObject` / `slotDeletedObject` → `touch()` du `CutList`), sans écrire
   dans la feuille hors du recalcul. (Vérifié en J2f : repli inutile, voir l'addendum.)

## Conséquences

- Toujours à jour après un recalcul ; Annuler restaure feuille et pièces ensemble.
- Un objet de plus dans l'arbre (« Liste de débit ») ; ouvert sans l'atelier, il est signalé
  sans proxy mais la feuille garde ses valeurs (ADR 0007).
- Coût : une collecte par recalcul qui touche une pièce (lecture des propriétés et d'une boîte
  englobante par pièce usinée) ; négligeable pour un meuble, à mesurer sur 500 pièces (test).
- La collecte, le calcul pur et le rendu de J2b/J2c restent valables ; seul le déclencheur change.

## Addendum J2f — vérification du point 5 (FreeCAD 1.0, CI sur 1.0 et 1.1)

- Modifier `Sources` dans `execute` : sans boucle ni avertissement ; `mustExecute` d'un proxy
  Python est appelé à chaque recalcul. Le repli par observateur n'est **pas** nécessaire.
- **Correction du point 1** : un lien `App::PropertyLinkListHidden` n'entre pas dans le graphe de
  dépendances (`OutList` et `InList` vides, aucune propagation du « Touched » : une cote modifiée
  ne recalculait pas la liste). `Sources` est donc un `App::PropertyLinkList` ordinaire ;
  `Scope` reste un `PropertyLinkListHidden` (les objets choisis sont aussi dans `Sources`). Les
  pièces ont ainsi `CutList` dans leur `InList` : les recherches de l'atelier par `InList`
  filtrent par type et ne sont pas touchées. Pour que la suppression d'une pièce ne montre pas
  l'avertissement « objets référencés » de FreeCAD (exigence de jv, J6), `CutList` a un
  ViewProvider Python minimal (`gui/view_providers/cutlist.py`, sans état, icône de la commande)
  dont `canDelete(obj)` est vrai pour tout objet de `Sources` ou de `Scope`, sur le modèle de la
  pièce usinée ; vérifié en interface hors écran par `Std_Delete` (sans lui, une boîte bloque).
  Posé par `make_cut_list` quand l'interface est chargée ; sans l'atelier, l'objet est affiché
  comme un objet ordinaire, sans conséquence.
- `Sources` contient les objets que la collecte lit (pièces, pièces usinées, ensembles, liens,
  conteneurs, assemblages par tourillons dont les deux pièces sont dans la portée) ; `mustExecute`
  ne compare que les quatre premières familles (ajouter un assemblage modifie ses pièces usinées).
  Quand une portée est choisie, `mustExecute` reste faux : ses objets sont dans `Sources`.
- La feuille est recalculée (`sheet.recompute()` puis `purgeTouched()`) dans `execute` : rien ne
  reste « Touched » après `doc.recompute()`. 500 pièces : la liste coûte quelques centièmes de
  seconde par recalcul.
- Un document plus récent que l'atelier (`Version` > 1) n'est pas réécrit.
