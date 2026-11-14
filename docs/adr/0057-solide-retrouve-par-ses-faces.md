# ADR 0057 — Retrouver le solide d'une pièce en bois par ses faces

- Statut : **proposé** (issue #257 ; en attente du « go » de jv sur les questions de la
  spécification, § 8)
- Date : 2026-11-14
- Spécification : [docs/specs/piece-en-bois-plusieurs-solides.md](../specs/piece-en-bois-plusieurs-solides.md)
- ADR liés : [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0020 — La pièce en bois, enveloppe d'un corps FreeCAD](0020-piece-en-bois-enveloppe-d-un-corps.md)
  (décision 2 remplacée pour les sources qui se recalculent),
  [0050 — Répétition des pièces en bois](0050-repetition-des-pieces-en-bois.md) (complété),
  0056 — Nommage topologique de FreeCAD 1.1 (PR #255)

## Contexte

L'ADR 0020 (décision 2) refuse une source paramétrique à plusieurs solides, parce que la pièce
désigne son solide par un rang (`SolidIndex`) qu'une modification du dessin peut changer. L'ADR
0056 a établi que FreeCAD 1.1 ne nomme pas les solides mais nomme leurs **faces**. jv demande
(issue #257) d'en tirer parti : FreeCAD 1.1 crée par défaut des corps à plusieurs solides.

Une sonde d'intégration sur FreeCAD 1.1.3 (spécification, § 2, faits F1 à F9) a montré que :

- les noms cartographiés suivent le solide quand une cote ou l'ordre des solides change ;
- mais le **texte** du nom de toutes les faces d'un corps change dès qu'on lui ajoute une
  fonction : mémoriser des noms et les comparer ne marche pas ;
- un lien natif `App::PropertyLinkSub` vers des faces, lui, est mis à jour par FreeCAD à travers
  ces changements ; il perd les faces qu'une opération découpe, et il perd **tout** quand une
  fonction du corps est supprimée ;
- scission et fusion de solides se lisent dans la répartition des faces encore suivies ;
- un objet scripté à plusieurs solides a des noms tirés du rang, donc sans valeur d'identité.
- un objet peut réécrire son propre lien de faces dans `execute()` (statut `Output`) sans
  relancer de recalcul.

## Options

1. **Garder le refus.** Sûr, mais oblige à un corps par pièce alors que FreeCAD 1.1 pousse à
   l'inverse. Rejetée (demande de jv).
2. **Mémoriser le texte des noms cartographiés** (piste de l'issue) et chercher « le solide qui
   contient la face de nom X ». Échoue à la première fonction ajoutée au corps (F3). Rejetée.
3. **Lire la racine de l'historique dans le texte du nom** (fonction d'origine et nom dans cette
   fonction, avant le premier suffixe `;:H`). Résisterait à l'ajout et à la suppression de
   fonctions, mais dépend du format interne des noms, que FreeCAD ne garantit pas. Rejetée.
4. **Empreinte géométrique seule** (chercher le solide de même volume, aire, inertie, centre).
   Échoue dès qu'une cote change : c'est tout l'intérêt d'une source paramétrique. Rejetée seule.
5. **Lien natif vers plusieurs faces, empreinte du dernier recalcul en secours.** Retenue.

## Décision

1. **Deux régimes.** Une forme **importée** (type exactement `Part::Feature`, sans dépendance)
   garde `SolidIndex` et l'empreinte figée (ADR 0020, inchangé). Toute autre source acceptée, dite
   **vivante**, est suivie par ses faces, qu'elle ait un ou plusieurs solides.
2. **`SolidFaces`** (`App::PropertyLinkSub` vers la source) : jusqu'à 8 faces du solide, les plus
   grandes d'abord. L'atelier ne lit jamais le texte des noms cartographiés : FreeCAD tient le
   lien à jour, l'atelier lit le résultat (`FaceN`, ou `?FaceN` pour une face perdue).
3. **`SolidSignature`**, pour une source vivante, est l'empreinte du **dernier recalcul réussi**.
4. **Résolution à chaque recalcul**, dans l'ordre : faces suivies (toutes dans un même solide) ;
   à défaut d'aucune face suivie, solide unique de même empreinte ; à défaut, élimination (une
   seule pièce sans solide, un seul solide sans pièce, avec avertissement) ; sinon erreur
   traduite. La règle est une fonction pure de `core/shaped`, testée sans FreeCAD.
5. **Jamais d'échange silencieux.** Faces suivies dans plusieurs solides : scission, erreur. Solide
   retrouvé qui porte aussi les faces ou l'empreinte d'une autre pièce de la même source (hors
   copies de répétition) : fusion, erreur sur les deux. Une pièce en erreur garde ses dernières
   valeurs.
6. **Rafraîchissement.** Après un recalcul réussi, `execute()` réécrit `SolidFaces` et
   `SolidSignature` d'après le solide retrouvé, en statut `Output` et seulement si la valeur
   change. C'est l'extension de l'exception de l'ADR 0020 (décision 5) : la pièce n'écrit que dans
   elle-même. Sans cela, le suivi s'userait à chaque face découpée.
7. **Sources refusées** : objet scripté (`Part::FeaturePython` hors atelier, ou tout objet à
   proxy) qui contient plusieurs solides, et source qui dépend d'un tel objet.
8. **Solide libre.** Une source convertie peut gagner un solide : avertissement, et la conversion
   relancée ne crée que les pièces des solides sans pièce. `converted_part_of` ne suffit plus à
   dire qu'une source est « déjà convertie ».
9. **Répétition (complète l'ADR 0050, décision 3)** : `SolidFaces` fait partie des valeurs
   recopiées dans une copie ; une pièce et ses copies désignent le même solide.
10. **Persistance** : `Version` de la pièce en bois = 2 ; migration par ajout de `SolidFaces`
    vide ; une pièce de version 1 à source vivante (un seul solide) gagne ses faces au premier
    recalcul réussi.

## Conséquences

- Un corps à plusieurs solides, une planche sciée par une coupe Part ou un composé donnent une
  pièce en bois par solide, qui suit son solide à travers les modifications courantes : cote,
  fonction ajoutée, fonction supprimée ailleurs, solide ajouté, ordre changé.
- Limites assumées, toutes signalées par une erreur ou un avertissement : solide scindé, solides
  fusionnés, fonction supprimée sur le solide même quand plusieurs pièces sont touchées à la fois.
- `execute()` écrit deux propriétés de sortie de plus ; `CONTRIBUTING.md` étend l'exception.
- La pièce lit, pour détecter une fusion, les propriétés mémorisées des autres pièces de la même
  source : une lecture, jamais une écriture, et pas de dépendance de recalcul entre pièces.
- Le comportement de FreeCAD sur lequel repose la décision est figé par des tests d'intégration
  (faits F1 à F9) : un changement dans une version future se voit en CI.
- L'ADR 0020 (décision 2) et l'inventaire de l'ADR 0056 (« pièce en bois paramétrique à plusieurs
  solides refusée : choix maintenu ») sont à annoter à la réalisation.
