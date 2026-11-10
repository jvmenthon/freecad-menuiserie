# Sélection par ensemble dans la vue 3D (descente niveau par niveau)

- Statut : **proposée**, à valider par jv (questions Q1 à Q5 ci-dessous)
- ADR : [0047](../adr/0047-selection-par-ensemble-dans-la-vue-3d.md)
- Demande de jv (2026-11-10) : « lors d'un clic dans la vue 3D, c'est l'ensemble qui se
  sélectionne ; je peux alors descendre (drill down) jusqu'à la pièce. »

## Comportement voulu

Un clic gauche sur une pièce membre d'un ensemble sélectionne l'**ensemble de plus haut niveau**
(les poignées, flèches et anneaux de l'ADR 0038 s'affichent). Les clics suivants **descendent d'un
niveau** vers la pièce cliquée : ensemble > sous-ensemble > pièce.

Soit `chaîne` la liste (de haut en bas) des ensembles qui contiennent la pièce cliquée, terminée par
la pièce. Soit `S` la sélection actuelle (un seul objet).

| Situation avant le clic                             | Sélection après le clic             |
|-----------------------------------------------------|-------------------------------------|
| `S` absent de la chaîne (rien, autre ensemble…)     | le premier élément (ensemble haut)  |
| `S` est l'élément *i* de la chaîne                  | l'élément *i+1*                     |
| `S` est la pièce elle-même                          | la pièce (reste)                    |
| pièce sans ensemble                                 | la pièce (comportement actuel)      |
| clic dans le vide                                   | rien (comportement actuel)          |

Exemple : deux caissons dans un meuble, un tiroir (sous-ensemble) dans le caisson de gauche.
Clic sur la façade du tiroir : meuble → clic : caisson → clic : tiroir → clic : façade.
Cliquer ensuite sur une autre pièce du même tiroir passe directement à cette pièce (`S` = tiroir
est dans sa chaîne, au rang juste avant elle).

## Hors périmètre / inchangé

- **Ctrl+clic et Maj+clic** gardent le comportement natif de FreeCAD (ajout à la sélection, pièces
  seules) : les commandes à plusieurs pièces (assemblage, ensemble) restent utilisables.
- Le **double-clic** (ADR 0018) ouvre toujours le panneau de la pièce sous le curseur.
- Les clics dans l'arbre natif et dans le panneau « Structure » (PR #191) ne sont pas touchés : la
  descente ne concerne que les clics dans la vue 3D. Le panneau suit la sélection comme aujourd'hui.
- Un clic sur une flèche, poignée ou anneau (glissement, ADR 0021/0038) reste prioritaire.
- Aucun objet, propriété ni observateur permanent dans le document (ADR 0007).

## Questions pour jv (recommandation ★)

- **Q1 — Remonter d'un niveau.** ★ Pas de geste dédié : cliquer dans le vide puis re-cliquer
  repart du haut. Variante : **Alt+clic = remonter d'un niveau**.
- **Q2 — Accès direct à la pièce.** ★ Ctrl+clic (natif). Variante : un réglage « sélectionner
  directement la pièce » dans les préférences de l'atelier (désactive toute la fonction).
- **Q3 — Après la pièce.** ★ Un clic de plus sur la même pièce la laisse sélectionnée. Variante :
  il revient à l'ensemble de plus haut niveau (cycle).
- **Q4 — Pièces d'un ensemble en cours de modification (panneau de pièce ouvert).** ★ La descente
  est suspendue : un clic sélectionne directement la pièce, comme aujourd'hui.
- **Q5 — Objets d'autres ateliers** dans la vue : ★ sélection native, inchangée.

## Découpage

1 lot, trois couches :
1. `core/` : fonction pure `next_in_chain(chain, current)` (table ci-dessus) + tests unitaires.
2. `features/` : `selection_chain(obj)` : ensembles de plus haut à plus bas niveau qui contiennent
   un objet (liens `Furniture`, sous-ensembles comme membres, ADR 0037/0038).
3. `gui/` : le filtre d'application de la vue 3D note qu'un clic gauche (sans mouvement, sans
   modificateur) vient d'avoir lieu ; l'observateur de sélection existant (`gui/drag/events.py`)
   remplace alors la sélection native par l'élément choisi. Vérification GUI hors écran + capture.
