# ADR 0062 — Épaisseurs qui suivent la cote de l'ensemble qu'elles remplissent

- Statut : **proposé**, accepté à la fusion de la PR #265 par jv (jv, 2026-11-16 : « D11 on doit
  pouvoir modifier l'épaisseur », puis option « Empilées : au prorata »)
- Date : 2026-11-16
- ADR liés : [0009](0009-suivi-par-expressions-natives.md) (un objet n'écrit que dans lui-même),
  [0019](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md) (rangées, épaisseurs fixes),
  [0020](0020-piece-en-bois-enveloppe-d-un-corps.md) (cotes dessinées),
  [0038](0038-ensemble-a-la-souris.md) (poignées),
  [0043](0043-repetition-objet-de-cotes-et-copies-liees.md) (copies liées)

## Contexte

L'ADR 0019 tient les épaisseurs pour fixes : un changement de cote de l'ensemble est absorbé par
les pièces qui s'étirent ou par les écarts. Quand des pièces à plat remplissent seules une cote
(un cadre à plat de 22 mm rangé dans un ensemble de 22 mm de haut, ou un fond de 22 mm et un
dessus de 18 mm empilés dans 40 mm), aucune cellule de la rangée ne peut absorber : la cote était
refusée avec « aucune pièce de la rangée ne peut s'adapter (les épaisseurs la remplissent) ».
Le scénario QTest S11 l'a montré (doute D11). jv veut pouvoir changer l'épaisseur ainsi, pièces
empilées comprises.

## Décision

1. **Rangée de couches** : sur un axe, une rangée bloquée dont chaque cellule intérieure est
   exactement l'épaisseur d'une pièce à plat, et dont chaque pièce est à plat sur une seule de ces
   cellules, est une rangée de couches (`Row.layer`, clés de ces pièces). Une couche peut porter
   plusieurs pièces côte à côte.
2. **Partage au prorata** : quand la cote de l'ensemble sur cet axe passe de `a` à `b`, chaque
   pièce de la rangée prend l'épaisseur `e x b / a` (`followed_thicknesses`). Les pièces restent
   empilées dans le même ordre ; leurs positions suivent par les épaisseurs vivantes de l'ADR 0019.
   22 + 18 mm dans 40 mm deviennent 27,5 + 22,5 mm dans 50 mm.
3. **Exceptions, la rangée reste bloquée** (refus inchangé, avec son explication) : une pièce
   verrouillée (« Cotes fixes », proposée à « Déverrouiller et appliquer »), une pièce en bois à
   cotes dessinées, une copie liée de répétition, une Distance gardée sur l'axe, et un
   sous-ensemble qui suit son parent par expression (rien n'y écrirait les épaisseurs). Une épaisseur qui sortirait de 0,1 à 300 mm refuse la cote (« deviendrait trop
   grande / petite »). Des pièces qui ne remplissent pas la cote (un écart au-dessus ou entre
   elles) ne changent pas : l'écart absorbe, comme avant (ADR 0019).
4. **Écriture** : les cotes de l'ensemble sont écrites d'abord, puis les épaisseurs, après une
   liaison de tout l'ensemble sur la géométrie d'avant avec les nouvelles épaisseurs (même chemin qu'une
   épaisseur saisie, ADR 0019, point 6), dans la même transaction : un seul Ctrl+Z. Chemins
   couverts : panneau de l'ensemble, `api.resize_furniture`, « Déverrouiller et appliquer »,
   éditeur de propriétés, poignées de la vue 3D. Une écriture qui échoue en route rend ce
   qu'elle avait écrit (cotes, épaisseurs). Dans l'éditeur de propriétés, où une cote saisie est
   d'habitude appliquée même refusée (Q4), une cote que les épaisseurs ne peuvent pas suivre,
   pour quelque raison que ce soit (nulle, épaisseur hors bornes, autre membre trop petit),
   revient à sa valeur d'avant : sinon les pièces ne la
   rempliraient plus et la saisie suivante serait refusée. L'ensemble écrit alors dans ses
   pièces depuis son `onChanged` : même écart à « un objet n'écrit que dans lui-même »
   (ADR 0009, point 2) que pour une épaisseur saisie (ADR 0019, point 6).
5. **Poignées de la vue 3D** : pendant le geste, seule la boîte change ; les épaisseurs suivent
   au relâchement (le relâchement repasse par le chemin du panneau). Échap n'a donc rien à rendre
   aux pièces.

## Conséquences

- Le refus « les épaisseurs la remplissent » ne paraît plus que pour les exceptions du point 3.
- Une épaisseur au prorata peut ne pas exister en matériau (27,5 mm) : c'est voulu par jv ; la
  liste de débit montre l'épaisseur obtenue.
- Le contrôle (`check_resize`) annonce les épaisseurs qui suivront ; `predict` les reçoit.
- Limite : l'aperçu des poignées ne montre pas les épaisseurs pendant le geste (point 5).
