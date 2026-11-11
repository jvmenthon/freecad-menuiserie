# ADR 0048 — Sélection par ensemble dans la vue 3D

- Statut : **accepté** (jv, 2026-11-10 : clic simple = ensemble, double-clic = descendre, double-clic dans le vide = remonter, Ctrl+clic natif)
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

1. **Remplacer la sélection native après coup** : après un clic 3D simple, on sélectionne à la
   place de la pièce l'élément voulu de la chaîne. Retenue : ne consomme aucun
   évènement, la navigation, le Ctrl+clic et les autres ateliers restent intacts.
2. **Consommer le clic dans le filtre d'application** (comme le double-clic, ADR 0018) et écrire la
   sélection nous-mêmes : risque de casser la navigation (rotation au bouton gauche selon le style)
   et la sélection des autres ateliers. Rejetée.
3. **Imposer la sélection par l'arbre** : refus de jv. Rejetée.

## Décision

1. Règles de clic, de descente et de remontée : voir la spécification (fonctions pures dans
   `core/`). Le double-clic sur une pièce déjà sélectionnée ouvre son panneau (ADR 0018).
2. La chaîne d'un objet vient de ses liens `Furniture` (ADR 0008/0037), pas de la hiérarchie des
   Std Part (ADR 0038) : un ensemble est sélectionné, pas son Std Part.
3. Seuls les clics et double-clics gauches sans modificateur dans la vue 3D sont concernés. Un
   filtre d'application (posé et retiré avec l'atelier, comme celui du double-clic) note le clic
   puis remplace la sélection native une fois FreeCAD passé ; le double-clic reste dans le filtre
   de l'ADR 0018. Le double-clic dans le vide se souvient de la sélection d'avant le premier clic
   (FreeCAD la vide).
4. Un observateur de sélection (posé avec le filtre) applique la même règle à une sélection native
   faite dans la vue 3D (point cliqué non nul, sans Ctrl ni Maj) : il rattrape les clics que le
   filtre ne voit pas, comme le premier clic après la création d'un ensemble (constaté par jv le
   2026-11-11). Les sélections par l'arbre ou par script n'ont pas de point et sont ignorées.
5. Rien n'est écrit dans le document.

## Coordination avec le panneau « Structure » (ADR 0046)

Le panneau lit la sélection de FreeCAD (`Gui.Selection`) et suit donc le changement sans code
commun. Aucun fichier du panneau n'est modifié ; les fichiers touchés ici sont `gui/double_click.py`,
`init_gui.py` et des modules neufs. Risque de conflit faible avec la PR #191.

## Conséquences

- La sélection faite par un clic 3D n'est plus toujours la pièce touchée : les commandes qui
  attendent des pièces (Assemblage…) se font au Ctrl+clic ou par l'arbre.
- Une pièce libre (sans ensemble) se sélectionne comme avant.
- Le clic simple sur une pièce d'un ensemble ne garde pas la face ou l'arête touchée : les
  commandes qui en ont besoin (mesure, congé, accrochage sur une face) se font au Ctrl+clic, qui
  reste natif.
- Le relâchement du bouton qui suit un double-clic consommé est consommé aussi : sinon FreeCAD le
  traite comme un clic sur la pièce déjà sélectionnée et sélectionne son Std Part (constaté par jv
  le 2026-11-11, vérification GUI de non-régression).
