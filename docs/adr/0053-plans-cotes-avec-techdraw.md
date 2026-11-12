# ADR 0053 — Plans cotés produits avec TechDraw

- Statut : **proposé** (2026-11-12), en attente de la décision de jv
- Date : 2026-11-12
- Issue : #153
- Spécification : [docs/specs/plans-cotes.md](../specs/plans-cotes.md)
- ADR liés : [0006](0006-piece-brute-et-piece-usinee.md),
  [0007](0007-compatibilite-avec-les-autres-ateliers.md),
  [0013](0013-liste-de-debit-vivante.md),
  [0049](0049-cotes-du-parent-a-l-enveloppe.md)

## Contexte

L'atelier doit produire un plan coté imprimable pour l'atelier, une vue soignée pour le client et un
plan par pièce avec ses usinages. FreeCAD fournit TechDraw. Les formes de l'atelier sont des
`Part::Feature` standard (ADR 0007), que TechDraw sait projeter.

## Options

1. **TechDraw, pages construites à la demande.** Retenue. Format standard, modifiable à la main par
   l'utilisateur, lisible sans l'atelier, PDF fourni par TechDraw.
2. **Objet « Plan » à proxy** qui se recalcule seul. Rejetée : insère un objet dans le graphe de
   dépendances de tout le meuble (même raisonnement que l'ADR 0012) et ne se lit pas sans l'atelier.
3. **Dessin maison** (SVG/PDF écrit par l'atelier, comme la liste de débit). Rejetée : refait
   projection, cotation et cartouche que TechDraw fait déjà, et ne s'ouvre pas dans TechDraw.
4. **Vue client en vectoriel TechDraw seulement.** TechDraw n'ombre ni ne texture ; rendu peu
   « client ». Gardée comme repli (Q3 de la spécification).

## Décision

1. Les plans sont des **objets TechDraw standard** (`DrawPage`, `DrawViewPart`,
   `DrawViewDimension`, `DrawViewImage`). Aucun type d'objet ni proxy nouveau.
2. Une commande les crée **à la demande**, marque ses pages d'une propriété booléenne masquée
   `MenuiserieDrawing`, et les reconstruit à la régénération ; une page modifiée à la main n'est
   jamais écrasée.
3. Le **gabarit** est un gabarit ISO déjà fourni par TechDraw ; l'atelier n'en installe ni n'en
   modifie, et ne touche à aucune préférence de TechDraw (ADR 0007).
4. Le calcul des cotes (hors tout à l'enveloppe, ADR 0049 ; usinages lus dans les enregistrements
   des assemblages) est **pur**, dans `core/drawing/` ; la création des objets TechDraw est dans
   `features/drawing_*.py`. L'import de `TechDraw` est paresseux : l'atelier se charge et reste
   utilisable si TechDraw est absent (la commande est alors grisée avec son prérequis, ADR 0052).
5. La **vue client** est une capture de la vue 3D insérée comme image dans une page ; la vue filaire
   TechDraw reste le repli vectoriel.
6. Un **lot de preuve** (P-a) précède le reste : cotes TechDraw rattachées à la géométrie des vues
   et régénération stable. Si les références d'arêtes ne tiennent pas, les cotes seront posées sur
   des sommets de l'enveloppe et l'ADR sera amendé avant le code des lots suivants.

## Conséquences

- Les plans s'ouvrent, s'impriment et s'exportent sans l'atelier.
- Les pages ne se mettent pas à jour toutes seules : il faut relancer la commande (comme le fait la
  liste de débit avant l'ADR 0013) ; à revoir si jv le demande.
- La vue client n'est pas vectorielle.
- Les tests d'intégration exigent FreeCAD avec TechDraw (déjà présent dans l'image de CI).
