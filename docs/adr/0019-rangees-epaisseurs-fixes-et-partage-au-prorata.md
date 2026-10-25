# ADR 0019 — Rangées de pièces : épaisseurs fixes, partage au prorata, pièces verrouillées

- Statut : **proposé** (règle de jv du 2026-10-23, à la recette J4/J6)
- Date : 2026-10-23
- Spécification : [docs/specs/ensembles-epaisseurs-fixes.md](../specs/ensembles-epaisseurs-fixes.md)
- ADR liés : [0009 — Suivi par expressions natives](0009-suivi-par-expressions-natives.md)
  (complété), [0010 — Gabarits générateurs](0010-gabarits-generateurs.md),
  [0016 — Pièces qui se chevauchent](0016-assemblages-au-contact-entre-pieces-qui-se-chevauchent.md)

## Contexte

Règle de jv, mot pour mot : « Les épaisseurs des matériaux sont fixes, ainsi si on modifie la
largeur du bureau seul le voile est modifié. Si je modifie l'épaisseur des joues, la largeur du
bureau ne bouge pas. C'est le voile qui est modifié. S'il y a plusieurs pièces elles sont toutes
modifiées proportionnellement sauf si elles sont configurées comme fixes. Si tu as un cas
impossible (par exemple les 2 joues + 1 voile fixes) tu dois afficher un message d'erreur qui
propose de déverrouiller les pièces verrouillées sous forme de cases à cocher. »

Avec l'ADR 0009, chaque face suit un bord de l'ensemble avec une constante figée à la liaison :
`Length` du voile = `<<Bureau>>.Width - 44 mm`, 44 étant les deux épaisseurs de joue du moment.
Trois défauts en découlent :

1. une joue plus épaisse grandit vers l'extérieur ou chevauche le voile, qui ne bouge pas ;
2. deux pièces libres côte à côte (deux étagères de part et d'autre d'un montant) suivent
   chacune les deux bords : chacune prend toute la différence, elles se chevauchent ;
3. aucune pièce ne peut être déclarée « à cotes fixes » ; une rangée sans pièce libre n'est pas
   détectée.

## Options

1. **Garder les constantes figées**, relier de nouveau après un changement d'épaisseur. Ne
   répond pas à la règle (le voile ne suit pas tout seul) ni au partage au prorata. Rejetée.
2. **Grille globale par axe** : toutes les faces de l'ensemble découpent l'axe en cellules, les
   cellules libres se partagent la différence. Simple, mais fausse : le voile, isolé en
   profondeur, se déplacerait au prorata au lieu de suivre le fond (spécification J4, F10), et
   l'écart de 40 mm derrière les joues grandirait. Rejetée.
3. **Rangées par membre** : sur chaque axe, un membre ne se règle que sur les pièces **en
   vis-à-vis** (qui se recouvrent sur les deux autres axes). La rangée est découpée en cellules ;
   les épaisseurs sont des cellules rigides qui citent la propriété `Thickness` de la pièce dans
   l'expression ; les pièces étirables non verrouillées se partagent la différence au prorata.
   Les options « fixe / non fixe » de l'ADR 0009 décident des écarts aux bords. Retenue.

## Décision

1. **Rangée** (option 3) : pour un membre M et un axe A, la rangée est M et les membres d'équerre
   dont l'étendue recouvre celle de M de plus de 0,01 mm sur chacun des deux autres axes. Une
   pièce sans vis-à-vis se comporte comme avec l'ADR 0009 (bords, mode `Stay` ou
   `Proportional`).
2. **Épaisseurs vivantes** : une cellule qui est exactement l'épaisseur d'une pièce vaut
   `<<Pièce>>.Thickness` dans l'expression. Changer l'épaisseur d'une joue ne change ni
   l'ensemble ni la joue d'en face : la joue grandit vers l'intérieur et les pièces libres de la
   rangée absorbent. Une épaisseur coupée par une autre face (feuillure, pièce dessinée hors
   tout) reste une constante figée.
3. **Partage au prorata** entre les cellules libres de la rangée : pièces étirables non
   verrouillées (règle de jv : « seules les pièces sont modifiées »), et, **seulement s'il n'y a
   aucune pièce libre dans la rangée**, écarts entre deux pièces et écarts aux bords dont la
   distance n'est pas fixe en mode `Proportional`. S'il y a une pièce libre, les écarts entre
   pièces restent rigides (constantes) : un caisson entre deux joues absorbe seul la
   différence (`<<Bureau>>.Width - <<Joue droite>>.Thickness - <<Joue gauche>>.Thickness - 756 mm`),
   alors qu'une étagère seule entre deux panneaux (rangée verticale sans pièce libre) partage
   ses deux jeux au prorata. En mode `Stay`, un écart au bord non fixe prend toute la
   différence (la pièce ne bouge pas, ou suit l'autre bord). Les expressions restent natives
   (ADR 0009).
4. **Pièce verrouillée** : nouvelle propriété de membre `Locked` (« Cotes fixes »,
   `App::PropertyBool`, faux par défaut, groupe « Ensemble »). Ses cotes ne changent jamais ;
   elle compte comme une cellule rigide de sa rangée.
5. **Cas impossible** : une rangée sans cellule libre ni écart au bord est **bloquée**. Changer la
   cote de l'ensemble sur cet axe, ou une épaisseur de cette rangée, est refusé avant toute
   écriture par une erreur qui nomme les pièces verrouillées de la rangée. Le panneau qui refuse
   (Ensemble ou Pièce de bois) affiche une case à cocher par pièce verrouillée et un bouton
   « Déverrouiller et appliquer ». Dans l'éditeur de propriétés, la valeur est appliquée avec un
   avertissement (règle Q4 de J4).
6. **Écriture** : l'option d'un membre peut changer la rangée d'autres membres. L'API et les
   panneaux relient alors tout l'ensemble ; dans l'éditeur de propriétés, le `onChanged` du membre
   ne relie que lui (ADR 0009, point 2) et avertit si d'autres liaisons sont à refaire
   (« Relier les pièces »).

## Conséquences

- Les expressions des membres citent l'épaisseur des pièces voisines ; renommer une pièce est
  suivi par FreeCAD (réécriture de `<<…>>`), et `same_binding` ignore déjà les libellés visés.
- **Auto-référence** : une pièce qui cite sa propre épaisseur l'écrit `Thickness` (sans
  `<<Libellé>>.`), comme FreeCAD réécrit une telle référence à la pose : le texte enregistré
  (`FurnitureBindings`) est ainsi celui qu'on relit. Une pièce peut se citer elle-même.
- **Pas de cycle entre objets** : le graphe de dépendances de FreeCAD est par objet, et refuse
  que deux pièces se citent l'une l'autre (`RuntimeError: cyclic reference`) — deux étagères dans
  une même rangée, chacune citant l'épaisseur de l'autre. Les liaisons voulues de tous les
  membres sont parcourues dans l'ordre des clés (cote avant position, axes X, Y, Z) ; le terme
  d'épaisseur qui fermerait un cycle est **figé en constante** (coefficient x épaisseur
  actuelle). Le calcul porte sur tous les membres puis se filtre par clés : relier un seul membre
  donne le même texte. Limite connue : l'épaisseur ainsi figée ne suit plus un changement
  d'épaisseur de cette pièce avant « Relier les pièces ».
- Les liaisons de la spécification J4 (F8) changent de texte : `- 44 mm` devient deux
  `Thickness`, `- 30 mm` devient `<<Plateau>>.Thickness` ; une joue reçoit une liaison
  `Placement.Base.x` = son épaisseur. Les valeurs numériques sont inchangées, sauf le voile en
  mode `Proportional` (les deux écarts gardent leur proportion au lieu de son milieu).
- Limite connue : deux rangées qui partagent une pièce mais pas la même composition (étagère
  posée sur un tasseau d'un côté seulement) peuvent donner deux positions différentes à cette
  pièce ; le contrôle des paires d'assemblage (`JOINT_LOST`) le signale quand elles sont
  assemblées.
- Aucune migration (règle Q5 de J6 : « c'est une v0 ») : un document existant garde ses
  liaisons figées jusqu'à « Relier les pièces » ; `Locked` absent vaut faux.
