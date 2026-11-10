# ADR 0047 — Sélection par ensemble dans la vue 3D

- Statut : **proposé** (en attente de jv)
- Date : 2026-11-10
- Spécification : [docs/specs/selection-par-ensemble.md](../specs/selection-par-ensemble.md)
- ADR liés : [0007](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008](0008-ensemble-objet-de-cotes.md), [0018](0018-double-clic-dans-la-vue-3d.md),
  [0037](0037-sous-ensemble-depuis-des-membres.md), [0038](0038-ensemble-a-la-souris.md),
  [0046](0046-arbre-simplifie-mode-simple.md) (panneau « Structure », PR #191)

## Contexte

Un clic dans la vue 3D sélectionne la pièce touchée, même quand elle appartient à un ensemble. jv
veut sélectionner d'abord l'ensemble (pour le tailler, le déplacer, le tourner, ADR 0038), puis
descendre niveau par niveau jusqu'à la pièce.

## Options

1. **Remplacer la sélection native après coup** : un observateur de sélection (déjà posé par
   l'atelier, `gui/drag/events.py`) constate qu'un clic 3D vient de sélectionner une pièce
   membre, et sélectionne à sa place l'élément voulu de la chaîne. Retenue : ne consomme aucun
   évènement, la navigation, le Ctrl+clic et les autres ateliers restent intacts.
2. **Consommer le clic dans le filtre d'application** (comme le double-clic, ADR 0018) et écrire la
   sélection nous-mêmes : risque de casser la navigation (rotation au bouton gauche selon le style)
   et la sélection des autres ateliers. Rejetée.
3. **Imposer la sélection par l'arbre** : refus de jv. Rejetée.

## Décision

1. Règle de descente : voir la table de la spécification (fonction pure dans `core/`).
2. La chaîne d'un objet vient de ses liens `Furniture` (ADR 0008/0037), pas de la hiérarchie des
   Std Part (ADR 0038) : un ensemble est sélectionné, pas son Std Part.
3. Seuls les clics gauche simples sans modificateur dans la vue 3D déclenchent la descente. Le
   filtre existant note l'instant et le point du clic, l'observateur applique la règle et rend la
   main au rafraîchissement des flèches.
4. Rien n'est écrit dans le document ; aucun nouvel observateur : on réutilise le filtre et
   l'observateur posés pendant que l'atelier est actif.

## Coordination avec le panneau « Structure » (ADR 0046)

Le panneau lit la sélection de FreeCAD (`Gui.Selection`) et suit donc le changement sans code
commun. Aucun fichier du panneau n'est modifié ; les fichiers touchés ici sont `gui/drag/events.py`
et un module de sélection neuf. Risque de conflit faible avec la PR #191.

## Conséquences

- La sélection faite par un clic 3D n'est plus toujours la pièce touchée : les commandes qui
  attendent des pièces (Assemblage…) se font au Ctrl+clic ou par l'arbre.
- Une pièce libre (sans ensemble) se sélectionne comme avant.
