# Sélection par ensemble dans la vue 3D (descente niveau par niveau)

- Statut : **validée par jv** (2026-11-10) ; reste à écrire
- ADR : [0048](../adr/0048-selection-par-ensemble-dans-la-vue-3d.md)
- Demande de jv (2026-11-10) : « lors d'un clic dans la vue 3D, c'est l'ensemble qui se
  sélectionne ; je peux alors descendre (drill down) jusqu'à la pièce. »

## Comportement voulu (réponses de jv du 2026-11-10)

- **Clic simple** sur une pièce membre d'un ensemble : sélectionne l'**ensemble de plus haut
  niveau** (poignées, flèches et anneaux de l'ADR 0038). Si l'élément déjà sélectionné contient la
  pièce cliquée (ensemble, sous-ensemble ou la pièce elle-même), la sélection ne change pas : on
  peut donc cliquer dans un tiroir sélectionné sans remonter.
- **Double-clic** sur une pièce : **descend d'un niveau** vers elle (ensemble > sous-ensemble >
  pièce). Une fois la pièce sélectionnée, le double-clic ouvre son panneau, comme aujourd'hui
  (ADR 0018). Une pièce libre (sans ensemble) garde le double-clic actuel.
- **Double-clic dans le vide** : **remonte d'un niveau** (de la pièce à son ensemble, d'un
  sous-ensemble à son parent). Au plus haut niveau, rien ne change.
- **Ctrl+clic** (et Maj+clic) : comportement natif de FreeCAD, pièces seules (jv : « ok »). Les
  commandes à plusieurs pièces (assemblage, ensemble) restent utilisables.
- Une pièce déjà sélectionnée reste sélectionnée par un clic de plus (jv : Q3 « ok »).

Exemple : meuble > caisson > tiroir > façade. Clic sur la façade : meuble. Double-clic : caisson.
Double-clic : tiroir. Double-clic : façade. Double-clic : panneau de la façade. Double-clic dans le
vide : retour au tiroir.

## Hors périmètre / inchangé

- Pas de descente tant qu'un panneau de tâche est ouvert : la sélection reste native.
- Les clics dans l'arbre natif et dans le panneau « Structure » (PR #191) ne sont pas touchés ; le
  panneau suit la sélection de FreeCAD comme aujourd'hui.
- Un clic sur une flèche, poignée ou anneau (ADR 0021/0038) reste prioritaire.
- Objets d'autres ateliers : sélection native.
- Aucun objet, propriété ni observateur permanent dans le document (ADR 0007).

## Découpage

1 lot, trois couches :
1. `core/selection_chain.py` : fonctions pures (clic, double-clic, remontée) + tests unitaires.
2. `features/` : `selection_chain(obj)` : ensembles de plus haut à plus bas niveau qui contiennent
   un objet (liens `Furniture`, sous-ensembles comme membres, ADR 0037/0038).
3. `gui/click_select.py` : un filtre d'application note le clic gauche simple (sans mouvement ni
   modificateur) et remplace ensuite la sélection native ; le filtre du double-clic (ADR 0018)
   appelle la descente ou la remontée avant d'ouvrir le panneau. Vérification GUI hors écran.
