# ADR 0066 — Aligner deux faces : rendre parallèle et aligner au début, au centre ou à la fin

- Statut : **proposé** (jv a choisi la grille « // , début, centre, fin » le 2026-11-16 et le
  logo F des boutons « // » le 2026-11-17)
- Date : 2026-11-17
- ADR liés : [0054](0054-aligner-deux-faces.md) (remplace la partie « Centrer sur X, Y, Z » de
  son point 5)

## Contexte

Le panneau « Aligner deux faces » avait trois boutons « Centrer sur X, Y, Z ». Cocher l'un d'eux
faisait deux choses à la fois : la pièce tournait dans le plan pour que son grand côté suive
celui de la référence, puis son centre venait sur celui de l'autre face. Les essais de jv
(2026-11-16, doute D9 des scénarios QTest) ont montré trois défauts :

- « Centrer » n'est pas le bon mot : le geste visible est surtout de **rendre les faces
  parallèles** ;
- on ne choisit pas l'axe auquel la pièce devient parallèle ;
- il manque un vrai alignement bord à bord (une traverse au ras du bout d'un montant) ;
- « Centrer Z » restait cliquable sans rien faire quand Z est la normale des faces.

## Décision

1. Une **disposition** (`core/align/_layout.py`, `Layout`) suit le mouvement de l'ADR 0054
   (tourner puis plaquer, décalages) :
   - `parallel` : axe auquel le **grand côté** de la face déplacée devient parallèle (rotation
     dans le plan de la référence, autour de sa normale, par le plus petit angle ; quart de tour
     au plus si la face déplacée est carrée ; d'équerre, c'est sa normale qui suit l'axe). Les
     côtés de la face de référence ne comptent plus : l'utilisateur choisit l'axe.
   - `anchors` : pour chaque axe, **début**, **centre** ou **fin** : le rectangle englobant de la
     face déplacée vient au même bord « moins », au même centre, ou au même bord « plus » que
     celui de la face de référence le long de cet axe. Comme le centrage d'avant, la translation
     reste dans le plan de la référence ; centres sur les deux axes du plan : centres confondus.
2. **Plus de rotation implicite** : aligner sans « // » ne fait pas tourner la pièce.
3. Un axe qui **suit la normale** des faces (sa part dans le plan est plus courte que 0,05, la
   pente minimale de l'ADR 0054) est refusé avec un message ; la distance entre les faces se
   règle avec « Position » et le 3e décalage. « // » est refusé quand le déplacement se fait sur
   un axe (la pièce ne tourne pas). Axes d'ancrage non perpendiculaires entre eux : refusés.
4. **Panneau** (maquette 2) : une grille « Parallèle et aligner sur », une ligne par axe X, Y, Z
   du conteneur de la pièce déplacée : un bouton « // » (logo F : la pièce penchée se couche sur
   la planche du dessous, flèche arrondie dans la couleur de l'axe ; un seul axe à la fois) puis
   trois boutons début, centre, fin (un seul par ligne). Recliquer un bouton l'éteint. La ligne
   de l'axe qui suit la normale est grisée et décochée, avec une infobulle (réponse au doute D9) ;
   la colonne « // » est grisée sur un axe de déplacement.
5. **API** : `api.align_faces(..., layout={"parallel": "X", "X": "start", "Y": "center"})`
   remplace `centered="XYZ"` (clés : `"parallel"` et les axes `"X"`, `"Y"`, `"Z"` ; valeurs
   d'ancrage : `"start"`, `"center"`, `"end"`). Toute autre clé ou valeur est refusée avant de
   toucher à la pièce.

## Conséquences

- Les icônes `Menuiserie_CenterX/Y/Z.svg` sont remplacées par `Menuiserie_ParallelX/Y/Z.svg` et
  `Menuiserie_AlignStart/Center/End.svg` (générées par `tools/generer_icones.py`).
- Un script qui appelait `align_faces(..., centered=...)` doit passer à `layout=` : l'ancien
  centrage sur les trois axes s'écrit `layout={"parallel": "X", "X": "center", "Y": "center"}`
  pour des faces horizontales (Z suit leur normale et n'est plus accepté).
- Rien n'est gardé dans le document : l'alignement reste ponctuel (ADR 0054).
