# ADR 0046 — Arbre de construction simplifié (mode simple / expert)

- Statut : **proposé** (demande de jv, 2026-11-08 ; option 3 retenue par jv)
- Date : 2026-11-09
- ADR liés : [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0038 — Ensemble à la souris](0038-ensemble-a-la-souris.md) (Std Part par ensemble),
  [0043 — Répétition](0043-repetition-objet-de-cotes-et-copies-liees.md),
  [0031 — Configuration de l'atelier](0031-configuration-de-l-atelier.md)

## Contexte

L'arbre est trop chargé pour un débutant. Sur deux caissons répétés ×3, jv voit plus de
100 lignes une fois tout déplié : Ensemble > Std Part > pièces usinées (brute en enfant), huit
assemblages à plat par caisson, une Origine par ensemble, des copies de répétition qui sont des
Std Part complets, un objet « Répétition » à la racine, un tableur par liste de débit. Les noms
(« (usinée) », « (Std Part) », « Caisson001 ») sont techniques.

## Décision

1. **Deux modes d'affichage**, réglés dans la configuration de l'atelier (ADR 0031) :
   **simple** (par défaut) et **expert** (arbre actuel, inchangé). Le mode ne change *jamais* le
   contenu du document, seulement l'affichage : un même fichier s'ouvre identique dans les deux.
2. **Ensemble et Std Part sur un seul niveau.** L'Ensemble réclame directement les pièces du Std
   Part (`claimChildren`) et le Std Part de l'atelier ainsi que son Origine sont `ShowInTree =
   False`. Les deux réglages sont indissociables : seul, le premier montre les pièces deux fois,
   le second fait disparaître l'ensemble (prototype FreeCAD 1.1.4). Le Std Part reste dans le
   document (ADR 0038). Seuls les Std Part créés par l'atelier sont masqués.
3. **Dossier « Assemblages (N) »** par ensemble, replié, réclamé par l'Ensemble ; il contient les
   assemblages, la quincaillerie et les distances de l'ensemble. C'est un objet-dossier réel du
   document (FreeCAD n'accepte que des objets du document dans `claimChildren`), sans forme ni
   dépendance, nom suivi de son effectif.
4. **Objets techniques masqués** en mode simple : brutes, Origines, sources de pièces en forme
   (Body, esquisses), tableur de la liste de débit (rangé sous l'objet CutList).
5. **Répétition** : « Répétition » et ses copies sont repliées sous une seule ligne
   « <nom> ×N » ; les copies ne s'affichent pas à plat à la racine.
6. **Glisser-déposer** (voulu par jv) : FreeCAD refuse le geste dans un groupe réclamé
   (`cannot be dragged out of`). Le ViewProvider de l'Ensemble implémente `canDragObject`,
   `dragObject`, `canDropObject` et `dropObject` : déposer une pièce sur un ensemble l'y range (même
   chemin que la commande « ajouter au sous-ensemble », ADR 0037), la sortir d'un ensemble la
   retire. Refus expliqué si la pièce porte un assemblage vers l'extérieur (ADR 0026).
7. **Noms** : le vocabulaire (« usinée », « Std Part », numéros) sera revu dans un lot suivant,
   hors de cet ADR.

## Conditions imposées par le test (FreeCAD 1.1.4)

- **Supprimer l'Ensemble** supprime aussi son Std Part, ses pièces et son dossier
  « Assemblages » (transaction unique, annulable) ; rien ne retombe à la racine.
- Le **masquage est réappliqué** à l'ouverture, après une copie et après une édition par
  double-clic : le Std Part masqué est réapparu à la racine dans ces cas.
- Le masquage s'applique aussi aux copies de la répétition (copie d'un Ensemble ou d'un Std Part).
- Enregistrement, réouverture avec l'atelier chargé, double-clic (panneau de tâche), sélection
  en 3D et Supprimer d'une pièce marchent déjà ; ils entrent dans la recette.

## Compatibilité avec les autres addons

Aucune propriété ni type d'objet de FreeCAD n'est modifié : `ShowInTree` et `claimChildren` sont les
mécanismes natifs. Un document ouvert sans l'atelier garde son arbre FreeCAD normal (Std Part
visibles). Les Std Part qui ne viennent pas de l'atelier ne sont jamais masqués.

## Conséquences

- Un objet de plus par ensemble (dossier) ; le mode expert reste le recours pour tout voir.
- Le dossier « Assemblages » doit rester synchronisé avec les assemblages de l'ensemble
  (création, suppression, changement d'ensemble).
- Cohérent avec l'ADR 0038 : l'Ensemble n'est toujours pas un conteneur.

## Lots proposés

1. Mode simple/expert + Ensemble/Std Part sur un niveau + masquage (avec suppression et
   réapplication du masquage).
2. Dossier « Assemblages (N) » (assemblages, quincaillerie, distances).
3. Glisser-déposer dans l'arbre.
4. Répétition repliée, liste de débit regroupée, objets de formes masqués.
5. Noms d'affichage.
