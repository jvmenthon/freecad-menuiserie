# Pièce en bois depuis une source paramétrique à plusieurs solides

- Issue : #257 (priorité moyenne)
- Statut : **proposée**, en attente du « go » de jv (questions au § 8)
- Demande de jv (2026-11-13) : « prépare cette issue […] corrige tout ce qui est impacté par les
  changements ».
- ADR : **[0057 — Retrouver le solide d'une pièce en bois par ses faces](../adr/0057-solide-retrouve-par-ses-faces.md)** (proposé),
  qui remplace la décision 2 de l'[ADR 0020](../adr/0020-piece-en-bois-enveloppe-d-un-corps.md) ;
  suite de l'ADR 0056 (nommage topologique de FreeCAD 1.1, PR #255) ;
  [0050 — Répétition des pièces en bois](../adr/0050-repetition-des-pieces-en-bois.md) (complété).
- Spécification d'origine : [piece-en-bois.md](piece-en-bois.md) (B2, B11, Q3).

## 1. Besoin

« Convertir en pièce en bois » refuse aujourd'hui une source **qui se recalcule** (corps
PartDesign, booléenne ou composé Part) dès qu'elle contient plusieurs solides : « séparez-les en
plusieurs corps ». Or FreeCAD 1.1 autorise un corps à plusieurs solides (`AllowCompound`, vrai par
défaut) : dessiner les deux montants d'un cadre dans une seule esquisse, ou scier une planche en
deux par une coupe Part, est devenu un geste ordinaire.

La raison du refus était la désignation du solide par son **rang** (`SolidIndex`) : un corps qui
change peut renuméroter ses solides, et une pièce prendrait la forme d'une autre sans prévenir.

## 2. Ce que fait FreeCAD 1.1 (vérifié en CI, FreeCAD 1.1.3)

Mesuré par une sonde d'intégration provisoire sur la PR #258 (retirée de la branche, ses
rapports sont dans les journaux de CI des commits c28be85 à 5de56f4) ; ces faits seront figés par
des tests au lot S-a (§ 6).

| # | Fait | Conséquence |
|---|---|---|
| F1 | Un corps PartDesign dont l'esquisse a deux contours séparés donne un composé de 2 solides ; un composé Part et une coupe Part aussi. Chaque face a un nom cartographié. | la source est lisible telle quelle |
| F2 | Changer une cote (longueur de protrusion, position de la scie, longueur de la planche) ou l'ordre des entrées d'un composé **garde** les noms de chaque solide, même quand le rang des solides s'inverse. | le nom suit le solide, pas le rang |
| F3 | **Ajouter une fonction** au corps (une poche dans un seul solide) **change le nom de toutes les faces**, y compris celles de l'autre solide : comparer des noms mémorisés ne suffit pas. | il faut le mécanisme de suivi de FreeCAD |
| F4 | Un **lien natif vers des faces** (`App::PropertyLinkSub`) suit ces changements : après la poche, les 6 faces de chaque solide sont retrouvées ; après une rainure en travers d'une face, 3 faces sur 6 (les autres sont notées manquantes, `?Face1`). | le lien natif est le bon outil ; il faut plusieurs faces |
| F5 | **Scission** (trait de scie à travers un solide) : les faces encore suivies se répartissent dans les deux moitiés. **Fusion** (pont entre deux solides, scie retirée) : le solide unique porte des faces des deux anciens. | scission et fusion se détectent |
| F6 | **Supprimer une fonction** du corps fait perdre **tous** les liens, même ceux des solides que la fonction ne touchait pas. Une face notée manquante ne revient pas d'elle-même. | il faut un second moyen de retrouver le solide |
| F7 | Un objet scripté (`Part::FeaturePython` d'un autre atelier) qui construit un composé de 2 solides a des noms tirés du **rang** (`Face1;:C1…`) : si son script inverse ses solides, les noms restent attachés au rang. | une telle source reste refusée |
| F8 | Le sous-solide lu par `Shape.Solids[i]` garde sa carte des éléments. | la pièce en bois garde une carte (ADR 0056) |
| F9 | Un objet dont `execute()` réécrit son propre lien de faces et un texte, en statut `Output`, reste « à jour » : pas de recalcul en boucle, un recalcul à vide ne l'exécute pas. | le rafraîchissement du § 4.1 est possible |

## 3. Comportement attendu

**Vocabulaire.** « Source vivante » : source qui se recalcule (tout sauf la forme importée, type
exactement `Part::Feature` sans dépendance, qui garde le régime actuel B11).

| # | Critère |
|---|---|
| S1 | Convertir une source vivante à N solides crée **N pièces en bois** dans la même transaction (une annulation les retire toutes), chacune à la place de son solide, comme pour une forme importée. Sources acceptées : corps PartDesign, objets natifs de Part (booléennes, composé, extrusion d'une esquisse à plusieurs contours…). |
| S2 | Modifier la source (cote, ajout d'une fonction, ordre des solides, ajout d'un solide) laisse chaque pièce sur **son** solide : matériau, repère, assemblages, place dans un ensemble et dans la liste de débit inchangés. |
| S3 | Supprimer une fonction de la source laisse aussi chaque pièce sur son solide tant que ce solide est reconnaissable (§ 4.3). |
| S4 | **Jamais d'échange silencieux.** Si le solide d'une pièce n'est plus identifiable, la pièce passe en erreur avec un message traduit qui dit quoi faire ; les autres pièces de la même source ne sont pas touchées. Cas : solide supprimé, solide scindé en plusieurs, solide fusionné avec celui d'une autre pièce. |
| S5 | Une source convertie qui **gagne un solide** : un avertissement traduit le signale (« “Corps” contient un solide sans pièce en bois ») ; relancer « Convertir en pièce en bois » sur la source crée seulement les pièces manquantes. La commande n'est donc plus grisée sur une source convertie dont un solide est libre. Aucun nouveau panneau ni icône. |
| S6 | Une source vivante à **un seul** solide est suivie de la même façon : si elle gagne un second solide, la pièce garde le sien (aujourd'hui : erreur). |
| S7 | Source scriptée (objet Python d'un autre atelier) à plusieurs solides, ou source qui dépend d'un tel objet : **refus** traduit à la conversion, comme aujourd'hui (F7). |
| S8 | Forme importée à plusieurs solides : inchangé (`SolidIndex` + empreinte, B11). |
| S9 | Répétition (ADR 0050) : la copie d'une pièce en bois désigne le même solide que son origine et le suit de la même façon ; une pièce et ses copies sur le même solide ne sont pas une fusion. |
| S10 | Réouverture, annulation / rétablissement, copier-coller, liste de débit (deux solides identiques regroupés « 2 × »), pièce usinée : inchangés. |
| S11 | Document enregistré avant cette version : s'ouvre sans avertissement ; ses pièces en bois (toutes à un seul solide ou importées) gagnent le suivi au premier recalcul réussi. Un document de la nouvelle version ouvert dans une ancienne : la pièce d'une source à plusieurs solides passe en erreur (« contient N solides »), sans échange. |

## 4. Conception

### 4.1 Deux moyens de reconnaître un solide (ADR 0057)

La pièce mémorise, pour une source vivante :

- `SolidFaces` (`App::PropertyLinkSub` vers la source, masquée) : jusqu'à **8 faces** du solide,
  les plus grandes d'abord. FreeCAD met ce lien à jour à chaque recalcul de la source (F4).
- `SolidSignature` (existante) : l'empreinte **du dernier recalcul réussi** (volume, aire,
  inertie, centre de masse). Elle sert de secours quand tous les liens sont perdus (F6).

`SolidIndex` reste réservé aux formes importées (`-1` pour une source vivante).

Après chaque recalcul réussi, la pièce **réécrit** ces deux propriétés d'après le solide retrouvé
(faces actuelles, empreinte actuelle) : le suivi ne s'use pas au fil des modifications. Elles ont
le statut `Output`, comme les cotes d'encombrement : c'est l'extension de l'exception déjà
documentée de l'ADR 0020 (décision 5) ; la pièce n'écrit que dans elle-même et seulement quand la
valeur change.

### 4.2 Retrouver le solide (à chaque recalcul)

1. **Par les faces.** Les faces encore suivies de `SolidFaces` désignent chacune un solide de la
   source. Toutes dans le même solide : c'est lui. Dans plusieurs solides : **scission**, erreur.
2. **Par l'empreinte**, si aucune face n'est suivie : un seul solide de la source a l'empreinte
   mémorisée : c'est lui. (Une fonction supprimée ailleurs dans le corps ne change pas ce solide.)
3. **Par élimination** (question Q4), si l'empreinte ne correspond à aucun solide : il reste
   exactement une pièce sans solide et exactement un solide sans pièce : la pièce le prend, avec
   un avertissement traduit dans la vue rapport.
4. Sinon : erreur « le solide de cette pièce n'est plus reconnaissable ».

**Fusion.** Le solide retrouvé porte aussi des faces suivies (ou l'empreinte) d'une autre pièce de
la même source qui n'est ni sa copie ni son origine : erreur sur les deux pièces. Défaire la
fusion dans le dessin les rétablit.

Une pièce en erreur ne réécrit rien : elle garde ses dernières faces et sa dernière empreinte.

### 4.3 Messages (traduits, citent la pièce et la source)

| Cas | Message |
|---|---|
| Solide supprimé ou méconnaissable | « Pièce en bois “P” : son solide n'existe plus dans “Corps” ou a trop changé. Supprimez la pièce, ou annulez la modification du dessin. » |
| Scission | « Pièce en bois “P” : son solide a été coupé en plusieurs dans “Corps”. Supprimez la pièce puis convertissez de nouveau “Corps” pour obtenir une pièce par morceau. » |
| Fusion | « Pièces en bois “P” et “Q” : leurs solides ont été réunis dans “Corps”. Supprimez l'une des deux, ou séparez-les dans le dessin. » |
| Élimination (avertissement) | « Pièce en bois “P” : elle a repris le seul solide libre de “Corps”. » |
| Solide sans pièce (avertissement) | « “Corps” contient un solide sans pièce en bois : relancez “Convertir en pièce en bois”. » |
| Source scriptée (refus) | « “X” est construit par un script et contient N solides : ses solides ne peuvent pas être suivis. Séparez-les en plusieurs objets. » |

### 4.4 Modules touchés (« tout ce qui est impacté »)

| Module | Changement |
|---|---|
| `core/shaped/` (Python pur) | nouvelle fonction de décision `resolve(votes, signatures, …)` : à partir des solides désignés par les faces, des empreintes et des pièces sœurs, rend le rang retenu ou un motif d'échec (énumération) ; testée sans FreeCAD |
| `features/shaped_sources.py` | `_single` remplacé par la règle S1/S7 (source vivante acceptée, scriptée refusée, y compris par ses dépendances) ; `picked_solid` devient le régime « importé » ; nouveau `tracked_solid` (faces, empreinte, élimination) ; plafond `MAX_SOLIDS` inchangé |
| `features/shaped_part_schema.py` | propriété `SolidFaces` ; `SolidSignature` et `SolidFaces` en `Output` ; `MODEL_VERSION` = 2 ; description de `SolidIndex` et `SolidSignature` mise à jour |
| `features/shaped_part.py` | `source_solid` choisit le régime ; `execute()` réécrit faces et empreinte ; migration 1 → 2 (propriété ajoutée, rien d'autre) |
| `features/shaped_create.py` | `_plans` pour une source vivante ; `converted_part_of` et `_checked_reading` : conversion des seuls solides libres (S5) |
| `features/repeat_new.py` | `SolidFaces` recopiée par valeur dans une copie (ADR 0050, décision 3) |
| `_api/wood.py` | docstrings de `make_shaped_parts` ; même signature |
| `gui/commands/shaped_part.py` | commande active sur une source convertie qui a un solide libre (S5) ; pas de nouvelle interface |
| Avertissement S5 | émis par la pièce au recalcul (une fois par changement du nombre de solides libres), pas d'observateur nouveau |
| Traductions | nouveaux messages (fr source, en) |
| Documentation | `piece-en-bois.md` (B2, B11, Q3, risques), ADR 0020 (décision 2 marquée remplacée), ADR 0050, ADR 0056 (ligne « choix maintenu » de l'inventaire, après fusion de la PR #255), `CONTRIBUTING.md` (exception `Output`), `CHANGELOG.md` |

Non touchés : liste de débit (elle lit la forme de chaque pièce), assemblages et pièce usinée,
ensembles, accrochage, profils d'arête et bande de chant (leur code de position ne dépend d'aucun
numéro, ADR 0056 décision 2).

### 4.5 Sécurité et coût

- Le travail reste borné : `MAX_SOLIDS` (256) par source, 8 faces par pièce ; la recherche du
  solide d'une face compare des faces de la source (`isSame`), au plus faces × 8 par pièce.
- Aucune lecture du texte interne des noms cartographiés : seul FreeCAD les interprète.
- Les empreintes et les noms de faces viennent du document : une valeur illisible est traitée
  comme absente (erreur traduite), jamais évaluée.

## 5. Compatibilité des documents

- `Version` de la pièce en bois : 1 → 2. Migration : ajout de `SolidFaces` (vide). Aucune autre
  propriété ne change de nom, de type ni de sens ; `SolidIndex` et `SolidSignature` des formes
  importées sont lus comme avant.
- Ouverture d'un document récent par un atelier plus ancien : voir S11 ; le mécanisme existant
  « document d'une version plus récente » s'applique (matériau en lecture seule).
- Compatibilité avec les autres ateliers (ADR 0007) : la source n'est jamais modifiée ;
  `SolidFaces` est un lien natif, lisible par tout outil FreeCAD.

## 6. Découpage

Une branche de jalon, trois lots, revue complète (testeur, sécurité, reviewer) avant d'annoncer
la PR prête.

| Lot | Contenu | Tests |
|---|---|---|
| **S-a** Suivi | `core/shaped` (décision), schéma v2, `tracked_solid`, `execute()`, migration ; la sonde devient `test_solides_suivis_freecad.py` (faits F1 à F9) | unitaires de la décision (tous les cas du § 4.2) ; intégration : cote, poche, rainure, ordre inversé, fonction supprimée, scission, fusion, solide supprimé, réouverture, annulation |
| **S-b** Conversion | sources acceptées et refusées (S1, S7), conversion des solides libres (S5), avertissement, commande | intégration : corps à 2 solides, coupe Part, composé, extrusion d'esquisse, source scriptée refusée, 3e solide ajouté puis converti |
| **S-c** Autour | répétition (S9), liste de débit (S10), traductions, documentation et ADR | intégration : répétition d'une pièce d'un corps à 2 solides, débit « 2 × », document de la version 1 rouvert |

## 7. Risques

| Risque | Parade |
|---|---|
| Réécrire un lien dans `execute()` relance le recalcul ou perturbe le graphe | statut `Output`, écriture seulement si la valeur change, même cible que `Source` (pas de nouvelle dépendance) ; vérifié par la sonde (F9) et figé par un test |
| Deux solides identiques (même empreinte) après perte de tous les liens | l'empreinte contient le centre de masse : deux solides au même endroit n'existent pas ; si elle désigne plusieurs solides, on passe à l'étape suivante, puis à l'erreur |
| Élimination qui attribue un solide neuf à une pièce dont le solide a été supprimé | n'a lieu que s'il reste une seule pièce et un seul solide, et avertit ; désactivable (Q4) |
| Objet scripté à un seul solide dont les faces changent de numéro, scié ensuite en deux par une coupe Part | limite connue : les faces suivies peuvent se répartir autrement ; la scission est alors signalée en erreur, pas d'échange silencieux tant que les deux moitiés portent des faces suivies |
| FreeCAD change son suivi des faces dans une version future | les tests F1 à F9 échouent en CI et désignent le fait qui a changé |

## 8. Questions pour jv (★ = recommandé)

- **Q1 — Une face ou plusieurs ?** ★ Plusieurs (8, les plus grandes), suivies par un lien natif de
  FreeCAD. Une seule face se perd à la première rainure qui la traverse (F4) et ne permet pas de
  voir une scission (F5).
- **Q2 — Fusion ou scission ?** ★ Erreur explicite sur les seules pièces concernées, avec la
  marche à suivre (§ 4.3). Variante écartée : la pièce garde d'office le plus gros morceau ; c'est
  un choix que l'atelier ferait à ta place.
- **Q3 — Sources scriptées d'autres ateliers à plusieurs solides ?** ★ Refus gardé : leurs noms de
  faces suivent le rang, pas le solide (F7).
- **Q4 — Reprise par élimination ?** Quand on supprime une fonction qui modifiait un solide, ses
  liens et son empreinte sont perdus tous les deux. ★ S'il ne reste qu'une pièce sans solide et
  qu'un solide sans pièce, la pièce le reprend avec un avertissement. Sinon : erreur, et il faut
  supprimer puis reconvertir la pièce (matériau, repère et assemblages à refaire).
- **Q5 — Solide ajouté à une source déjà convertie ?** ★ Avertissement, et « Convertir en pièce en
  bois » relancée sur la source crée les pièces manquantes (S5).
