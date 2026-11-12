# Plans cotés imprimables (atelier et client)

- Statut : **proposée** (2026-11-12), en attente des réponses de jv (§ 6)
- Issue : #153 (étude de marché du 2026-11-04, sous-issue de la revue UX #217)
- ADR : [0053](../adr/0053-plans-cotes-avec-techdraw.md) (proposé)
- Demande : plan de l'ouvrage coté (vues, cotes principales) en PDF pour l'atelier ; vue 3D soignée
  pour le client et le devis ; plan par pièce avec ses usinages. Piste : TechDraw, sans modifier
  FreeCAD globalement (ADR 0007). Besoin à valider en entretiens : on vise donc un premier lot
  petit et utile seul.

## 1. Trois livrables

| Livrable | Public | Contenu |
|---|---|---|
| **Plan de l'ouvrage** | atelier | une page : face, dessus, côté, vue 3D filaire, cotes hors tout (L × l × H), cartouche (nom, matériau, échelle, date) |
| **Vue client** | client, devis | une page : vue 3D ombrée avec textures, fond blanc, cotes hors tout, sans traits cachés |
| **Plan de pièce** | atelier | une page par pièce : vues utiles, cotes de la pièce, cotes des usinages (tenons, mortaises, rainures, perçages), repère, matériau, quantité |

Les trois s'obtiennent depuis la sélection (un ensemble, ou des pièces) ; sans sélection, tout le
document.

## 2. Principe (ADR 0053)

- **Pages TechDraw standard** (`TechDraw::DrawPage`, `DrawViewPart`, `DrawViewDimension`),
  construites par une commande, à la demande, à partir des formes de l'atelier (ADR 0007 : ce sont
  des `Part::Feature` ordinaires, TechDraw les lit sans l'atelier). Aucun nouveau type d'objet.
- **Gabarit de page** : les gabarits ISO fournis par TechDraw (A4/A3, paysage), choisis dans le
  dossier de l'installation de FreeCAD ; aucun gabarit n'est installé ni modifié.
- **Régénération** : les pages produites portent une propriété masquée `MenuiserieDrawing` ; la
  commande les retrouve et les reconstruit (comme la liste de débit, ADR 0013). Une page modifiée à
  la main par jv n'est jamais écrasée sans le dire : la commande propose une nouvelle page.
- **PDF** : export par TechDraw (`TechDrawGui.exportPageAsPdf`), bouton « Exporter en PDF » dans le
  panneau de la commande ; le PDF multi-pages des plans de pièce réutilise le mécanisme du PDF de la
  liste de débit.
- **Vue client** : TechDraw n'ombre pas ni ne texture les faces. La vue client est donc une capture
  de la vue 3D de FreeCAD (arrière-plan blanc, vue isométrique, textures de l'atelier), insérée dans
  une page par `TechDraw::DrawViewImage`, avec cotes hors tout en vue filaire superposée (Q3).

## 3. Cotes

- **Hors tout** : trois cotes (longueur, largeur, hauteur) lues sur l'enveloppe exacte de
  l'ensemble (ADR 0049), jamais sur la boîte englobante d'un déplacement en cours.
- **Pièce** : longueur, largeur, épaisseur, plus les usinages lus dans les enregistrements des
  assemblages (ADR 0003, 0006) : position de la mortaise depuis le chant, section et longueur du
  tenon, profondeur, diamètre des perçages. Le calcul est pur (`core/drawing/`), la création des
  cotes TechDraw est dans `features/drawing_*.py` (même découpage que la liste de débit).
- Les cotes sont des **cotes TechDraw rattachées à la géométrie de la vue** : elles suivent un
  changement de forme à la régénération. Le risque (références d'arêtes qui se renumérotent) est
  levé par un lot de preuve de faisabilité (§ 5, lot P-a) avant tout le reste.

## 4. Hors périmètre

- Nomenclature, étiquettes de pièces, plan de coupe des panneaux : voir la liste de débit.
- Export DXF/DWG, mise en plan automatique d'ouvrages à biais complexes (une vue de face
  supplémentaire sur l'axe de la pièce, plus tard).
- Aucune préférence ni gabarit global de TechDraw modifiés.

## 5. Découpage

| Lot | Contenu | CI |
|---|---|---|
| P-a | preuve de faisabilité : page + 3 vues + cotes hors tout sur un meuble de test, régénération, export PDF (tests d'intégration FreeCAD) | oui |
| P-b | plan de l'ouvrage : commande, panneau (format, échelle, orientation des vues), cartouche | oui |
| P-c | plan de pièce avec usinages ; PDF multi-pages | oui |
| P-d | vue client (capture ombrée + page) | oui |
| P-e | icônes, infobulle avec prérequis (ADR 0052), traductions, documentation | oui |

Un seul jalon, une PR vers `master` à la fin, revue complète (testeur, sécurité, reviewer) sur
cette PR.

## 6. Questions à jv (★ = recommandé)

1. **Premier lot** : démarrer par le plan de l'ouvrage (atelier) ★, ou par la vue client ?
2. **Gabarit** : A3 paysage par défaut ★ (A4 et portrait au choix dans le panneau).
3. **Vue client** : capture ombrée de la vue 3D insérée comme image ★ (beau, mais non vectoriel),
   ou vue TechDraw filaire seulement (vectoriel, moins « client »).
4. **Plans de pièce** : une page par pièce ★, ou une page par groupe de pièces identiques (les
   copies d'une répétition, ADR 0043) avec la quantité ★ — ces deux choix se combinent : une page
   par pièce *distincte*, la quantité écrite au cartouche.
5. **Page modifiée à la main** : ne jamais l'écraser, proposer une nouvelle page ★.
6. **Cartouche** : champs fixes (ouvrage, matériau, échelle, date, auteur lu dans les préférences
   de l'atelier). Autres champs à prévoir (client, numéro d'affaire) ?
7. **Entretiens** : l'issue parle d'une hypothèse à valider. Faut-il attendre un entretien avant le
   lot P-c (usinages), le plus coûteux ?
