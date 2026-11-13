# Finition des chants : profils d'arête et bande de chant

- Issue : #5
- Statut : **acceptée** (Q2 tranchée par jv le 2026-11-01 ; Q1, Q3 à Q7 : « go » de jv le 2026-11-01 sur les choix ★ ; Q8 : voir § 9).
- Demande de jv : « pouvoir donner une finition aux chants et aux arêtes des pièces de bois »
  (quart de rond, chanfrein, arête cassée, bec-de-corbin, doucine, gorge, demi-rond ; bande de
  chant collée ; alaise).
- ADR : **[0029 — Profils d'arête usinés par balayage](../adr/0029-profils-d-arete-par-balayage.md)**
  et **[0030 — Bande de chant : solide séparé, cotes finies](../adr/0030-bande-de-chant.md)**
  (acceptés). ADR liés : 0002 (matériaux), 0003, 0006 (brute et usinée), 0007 (compatibilité),
  0008/0019 (ensembles), 0020 (pièce en bois).
- Découpage : deux jalons, **profils (CH-a à CH-c)** puis **bande de chant (CH-d à CH-f)** (§ 5).

**Vocabulaire.**

- *Arête* : ligne où se rencontrent deux faces d'une pièce. Une pièce de bois en a 12.
- *Chant* : petite face d'un panneau (celles que l'on plaque). Une pièce en a 4 utiles (±X, ±Y).
- *Profil* : forme enlevée le long d'une arête (chanfrein, quart de rond…).
- *Repère local* : X = longueur, Y = largeur, Z = épaisseur (ADR 0003). Les faces sont nommées
  d'après lui : **dessus** (Z+), **dessous** (Z−), **avant** (Y−), **arrière** (Y+), **gauche**
  (X−), **droite** (X+). Une arête s'appelle par ses deux faces : « dessus-avant ».

## 1. Contexte

Aujourd'hui toutes les pièces sont des parallélépipèdes à arêtes vives (hors assemblages). Un
meuble réel a presque toujours une arête adoucie, des chants plaqués ou un profil de défonceuse.
L'atelier dispose du bon mécanisme pour y arriver : la **pièce usinée** (ADR 0006) assemble sa
forme à partir de la brute et de plans d'usinage calculés en Python pur dans `core/` ; les
assemblages y ajoutent des enlèvements. Une finition d'arête est un enlèvement de plus, lié à une
seule pièce.

## 2. Objectif

1. **Profils** : donner à une ou plusieurs arêtes d'une pièce un profil paramétrique : chanfrein
   (une ou deux distances), quart de rond, arête cassée (réglage rapide : 1 mm), gorge, demi-rond,
   bec-de-corbin, doucine. Les cotes finies et le débit ne changent pas.
2. **Bande de chant** : plaquer sur un ou plusieurs chants d'un panneau une bande (ABS, mélaminé,
   placage) d'épaisseur réglable, dessinée comme un solide à part, avec reprise dans la liste de
   débit (longueur de chant par matériau, cote de coupe du panneau).
3. Tout reste **paramétrique** : changer une cote, déplacer, étirer par l'ensemble : les
   finitions suivent. Un assemblage ne casse pas une finition, et inversement.

## 3. Critères d'acceptation

### CH-a — Règles pures (`core/edges/`, aucun import de FreeCAD)

- A1 `EdgeId` désigne une des 12 arêtes par deux faces (axe, signe) ; `parse_edge("dessus-avant")`
  et `edge_code` font l'aller-retour ; toute autre chaîne est refusée (`ValueError`).
- A2 `face_edges(face)` donne les 4 arêtes d'une face ; `all_edges()` les 12 ; `loop_edges("Z+")`
  les 4 arêtes du dessus ; les raccourcis sont des fonctions pures, testées.
- A3 `profile_section(family, a, b)` donne la section enlevée, en polyligne et arcs exacts, dans le
  repère de l'arête (origine sur l'arête, axes le long des deux faces). Pour chaque famille :
  aire enlevée attendue (chanfrein a·b/2 ; quart de rond (1 − π/4)·a² ; etc.), section fermée,
  sans auto-intersection, contenue dans le carré a × b.
- A4 `edge_cut(dimensions, edge, family, a, b)` renvoie un `Extrusion` (section balayée sur toute la
  longueur de l'arête, dans le repère local de la pièce) ; il dépasse l'arête de 0,01 mm aux deux
  bouts pour une coupe franche.
- A5 Bornes : 0,1 mm ≤ a, b ≤ 0,5 × la plus petite dimension des deux faces voisines ; deux
  arêtes opposées d'une même face dont les profils se rejoignent sont refusées avec un message
  qui nomme la pièce, les arêtes et la cote maximale.
- A6 Les familles sont enregistrées dans un registre (Strategy, comme `core/joints/_registry`) :
  ajouter une famille ne modifie aucune autre.
- A7 Test d'import existant étendu : `core/edges` n'importe ni FreeCAD, ni Qt, ni pivy.

### CH-b — Objet et usinage (`features/edge_profile.py`, `features/machined_part.py`)

- B1 `EdgeProfile` : `Part::FeaturePython` (ADR 0029), qui lie une pièce **brute** (`WoodPart`) ;
  sa forme est vide ; son `execute()` ne calcule que son plan et signale ses erreurs (cote trop
  grande, pièce en bois non prise en charge).
- B2 `MachinedPart` reçoit `Finishes` (lecture seule) ; sa forme = (brute − profils − coeur de la
  bande) + ajouts des assemblages − enlèvements des assemblages. Un profil ne retire jamais un
  tenon ni une languette (ajoutés après), et ne rebouche jamais une mortaise (retirée après).
- B3 Un profil dont la zone coupe un enlèvement ou un ajout d'assemblage donne un **avertissement**
  (« Le profil touche l'assemblage X »), jamais un refus.
- B4 Créer un profil crée la pièce usinée si besoin (`ensure_machined_part`) ; supprimer le
  dernier profil et le dernier assemblage supprime la pièce usinée (comportement existant).
- B5 Pièce en bois (`ShapedPart`) : acceptée quand sa forme est une boîte (solide égal à son
  encombrement, 2026-11-13, `features/box_parts.py`), refusée sinon avec un message clair (§ 8).
  Pièce sans arête : refus.
- B6 Pièce en biais ou pièce d'assemblage d'onglet : le profil suit les arêtes de la **boîte
  brute** ; à l'onglet, il s'arrête net (pas de retour d'onglet, § 8) ; un test le fixe.
- B7 Les arêtes sont enregistrées par leur **code local** (`"Z+Y-"`), jamais par un numéro
  d'arête de la forme (nommage topologique) : une cote modifiée, une rotation, un assemblage
  ajouté ne changent pas le choix.
- B8 `Version` de `MachinedPart` : 1 → 2 (propriété ajoutée, migration sans perte) ;
  `EdgeProfile` : `Version` = 1. Un ancien document s'ouvre sans changement.
- B9 API publique (`_api/`) : `add_edge_profile(part, edges, family, a, b)`,
  `remove_edge_profile(profile)`, `edge_profiles_of(part)`, avec avertissements renvoyés
  (ADR 0017).

### CH-c — Interface (`gui/`)

- C1 Commande « Finition des chants » (icône `Menuiserie_FinitionChants.svg`, générée par
  `tools/generer_icones.py`), active quand une pièce de l'atelier (brute ou usinée) est
  sélectionnée.
- C2 Panneau de tâche (simplifié le 2026-11-05 à la demande de jv) : famille (liste, « Quart de
  rond » 1 mm par défaut : c'est l'arête cassée, sans bouton dédié), cote A
  (`Gui::QuantitySpinBox`), cote B **visible seulement si la famille la demande** (bec-de-corbin,
  doucine ; ou profil relu asymétrique), et la liste **« Pièces concernées »** (2026-11-13) : une
  carte par pièce (pastille et liseré de couleur, nom de la pièce, nombre d'arêtes, « Toutes »,
  « Aucune », croix pour retirer la pièce) avec le **dessin cliquable** de ses arêtes. Deux
  dessins, au choix de l'utilisateur (bascule mémorisée dans les préférences de l'atelier) :
  **patron déplié** (les six faces à plat en croix, chaque côté de case est une arête) ou **boîte
  en perspective** (vue de l'avant, de la droite et du dessus ; arêtes cachées en pointillés ;
  faces cachées hachurées en gris, écartées de la boîte avec la mention « cachée »). Un clic sur
  une arête la choisit ou la retire, un clic dans une face choisit ses quatre arêtes (ou les
  retire si elles le sont toutes). Arêtes choisies et faces dont les quatre arêtes le sont
  prennent la couleur de la pièce.
- C2b Plusieurs pièces dans un même panneau (2026-11-13) : chaque pièce reçoit **son propre
  profil** (même famille, mêmes cotes), tous créés dans la transaction de la commande (une seule
  entrée d'annulation). Retirer une carte retire le profil que le panneau avait créé pour elle.
  En modification (double-clic sur un profil), la pièce du profil ne peut pas quitter la liste
  (« Supprimer ce profil » le fait) ; d'autres pièces peuvent s'y ajouter.
- C2c Mise en valeur dans la vue 3D (2026-11-13) : pendant la tâche, les arêtes choisies de
  chaque pièce sont tracées en trait épais de la couleur de sa carte, et les faces dont les
  quatre arêtes sont choisies teintées. C'est une incrustation de la vue (comme les flèches de
  déplacement) : rien n'est écrit dans le document ni dans l'historique d'annulation, les
  couleurs des pièces ne changent jamais ; elle est retirée à toute fermeture.
- C3 Cibles désignées par la **sélection** (2026-11-11) : la commande est active même sans
  sélection ; le panneau demande alors de désigner dans la vue 3D une pièce, une face ou une
  arête. Avant la commande ou panneau ouvert : une face coche ses 4 arêtes, une arête cette
  arête, un sommet les 3 arêtes du coin, une pièce seule n'en coche aucune (la pièce n'est
  jamais profilée en entier). Plusieurs pièces sélectionnées donnent une carte chacune ; une
  pièce cliquée panneau ouvert s'ajoute à la liste. Une pièce qui n'est pas une boîte est
  refusée avec un message (dans le panneau s'il y a d'autres pièces).
- C4 Règle de jv du 2026-10-22 : toute modification du panneau s'affiche en direct (aperçu
  recalculé, `valueChanged`), Annuler remet l'état d'avant, un Ctrl+Z défait l'ensemble.
- C5 Éditer un profil existant : double-clic sur la pièce usinée → le panneau de la pièce propose
  un groupe « Finitions » (liste des profils, bouton Modifier / Supprimer).
- C6 Plusieurs profils par pièce, sans arête en commun (une arête, un profil) ; reprendre une
  arête déjà profilée remplace son profil après confirmation.
- C7 Tout texte visible traduisible (`QT_TRANSLATE_NOOP`), en français.

### CH-d — Bande de chant (`core/banding/`, `features/edge_banding.py`)

- D1 `core/banding/` (pur) : `band_strips(dimensions, sides, thickness)` donne une `Box` par chant ;
  la bande qui court selon la plus grande dimension prend le coin, l'autre s'arrête contre elle ;
  recouvrement nul, volume exact. Chants autorisés : ±X et ±Y ; ±Z refusé.
- D2 `core_box(dimensions, sides, thickness)` : boîte du coeur du panneau, une fois les bandes
  retirées (cotes finies − épaisseur des bandes sur les chants plaqués).
- D3 `EdgeBanding` : `Part::FeaturePython` (ADR 0030) lié à une brute ; propriétés `Sides`
  (liste de codes), `Thickness` (0,2 à 5 mm), `BandMaterial` (identifiant de matériau de kind
  `banding`). Sa **forme** = les bandes ; elle reçoit les profils d'arête de la pièce (l'arête
  reste continue, bande comprise) ; aspect lu sur le matériau de bande (couleur, texture).
- D4 La pièce usinée perd le volume des bandes (pas de recouvrement, pas de scintillement) :
  `Finishes` contient aussi les `EdgeBanding`.
- D5 Une même face ne peut être plaquée que par un objet ; refus sinon, message à la création.
- D6 Un assemblage dont l'usinage touche un chant plaqué donne un avertissement (B3). Les
  bandes ne sont pas percées par un assemblage (§ 8).
- D7 Bibliothèque : `MaterialKind.BANDING = "banding"` ajouté au format JSON ; 8 bandes
  intégrées (ABS blanc, noir, gris ; mélaminé blanc ; placage chêne, hêtre, noyer, merisier),
  épaisseurs usuelles 0,4 / 0,8 / 1 / 2 mm. Les menus de matériaux de **pièce** ne proposent pas
  ce kind ; le format reste `format: 1`. Une version plus ancienne de l'atelier ignore ces entrées
  (entrée invalide ignorée seule, ADR 0002).

### CH-e — Liste de débit (`core/cutlist/`, `features/cutlist_*.py`)

- E1 Une pièce bandée porte sa **cote de coupe** (finie moins les bandes) en plus de ses cotes
  finies, dans l'aperçu, le CSV et le PDF.
- E2 Deux pièces de mêmes cotes mais de bandes différentes ne sont pas regroupées (clé de
  regroupement, comme `BevelCut`).
- E3 Section « Chants » : une ligne par matériau de bande et épaisseur, longueur totale nette
  (somme des longueurs de chant × quantité), arrondie au 0,1 m supérieur ; décision de la marge
  de commande : Q6.
- E4 Les profils ne changent ni les cotes, ni le volume, ni la masse affichés (écart documenté :
  volume surestimé de l'ordre de 0,1 % pour une arête cassée).

### CH-f — Finitions (icônes, captures, recette)

- F1 Icônes de la commande (profil, bande) par le script générateur ; captures CI : une pièce
  aux arêtes cassées et un panneau bandé dans la scène de `tools/captures_interface.py`.
- F2 Recette `docs/recette/finition-des-chants-scenarios-manuels.md` : trois styles de
  navigation, pièce de bois, panneau mélaminé, pièce assemblée, ensemble étiré, Ctrl+Z, ouverture
  du fichier **sans** l'atelier (formes ordinaires visibles).

## 4. Conception

### 4.1 Principe (ADR 0029)

Un profil est une **section 2D** enlevée, balayée le long d'une arête. Le calcul est en `core/` ;
`features/` le convertit en solide `Part` (face dessinée de segments et d'arcs puis extrusion) et
le soustrait. On n'utilise ni `makeFillet` ni `makeChamfer` : ils agissent sur la forme finale,
retrouvent les arêtes par numéro (nommage topologique instable après un assemblage) et ne se
testent pas sans FreeCAD. Contrepartie : au croisement de deux arêtes profilées la forme est la
**coupe commune** des deux balayages (angle vif propre pour un chanfrein, pas de coin sphérique
pour un quart de rond) ; un raffinement de coin est reporté (§ 8).

### 4.2 Modules

```
core/edges/        __init__.py (façade) _ids.py (EdgeId, raccourcis) _sections.py (sections)
                   _families.py (registre, une classe par famille) _cut.py (edge_cut, bornes)
core/banding/      _strips.py (bandes, coeur, longueurs)
core/_polyhedron.py  + Extrusion (section balayée), ajoutée à PlanSolid
features/edge_profile.py   EdgeProfile + création
features/edge_banding.py   EdgeBanding + création
features/solids.py         + conversion d'Extrusion (solid_shape)
features/machined_part.py  + Finishes, ordre des opérations
core/edges/_diagram.py     patron déplié, boîte en perspective, ce qu'un clic y désigne
gui/task_panels/edge_finish.py, edge_targets.py (cartes), edge_diagram.py (dessin cliquable) ;
gui/commands/edge_finish.py ; gui/pick_edge.py ; gui/edge_highlight.py (mise en valeur 3D)
```

Familles (paramètres A, B en mm ; la section est contenue dans le carré A × B de l'angle) :

| Famille | Section enlevée | A | B |
|---------|-----------------|---|---|
| Chanfrein | triangle | distance sur la 1re face | distance sur la 2e (0 = A, soit 45°) |
| Quart de rond | carré moins quart de disque (rayon A) | rayon | 0 = A (ellipse si B ≠ A) |
| Arête cassée | quart de rond, préréglé | 1 mm | — |
| Gorge | quart de disque concave | rayon | B = A |
| Demi-rond | deux quarts de rond sur les deux arêtes d'un chant | rayon max = épaisseur / 2 | — |
| Bec-de-corbin | quart de rond puis épaulement droit | rayon | largeur de l'épaulement |
| Doucine | deux arcs tangents en S (cavet puis quart de rond) | largeur | hauteur |

« Arête cassée » est un préréglage de la famille Quart de rond (rayon 1 mm), pas une famille
distincte : un seul code de calcul, un libellé familier pour le menuisier.

### 4.3 Propriétés FreeCAD

`EdgeProfile` (groupe « Profil ») :

| Propriété | Type | Remarque |
|-----------|------|----------|
| `Part` | `App::PropertyLink` | brute, lecture seule |
| `Edges` | `App::PropertyStringList` | codes `"Z+Y-"`, validés contre l'énumération des 12 |
| `Family` | `App::PropertyEnumeration` | `Chamfer, Round, Cove, Bullnose, Beak, Ogee` (ajouts en fin seulement) |
| `SizeA`, `SizeB` | `App::PropertyLength` | bornes de A5 ; infobulles traduites |
| `Version` | `App::PropertyInteger` | 1 |

`EdgeBanding` (groupe « Bande de chant ») : `Part`, `Sides` (`PropertyStringList` : `"X-"`, `"X+"`,
`"Y-"`, `"Y+"`), `Thickness` (`PropertyLength`), `BandMaterial` (`PropertyString`, identifiant),
`Version`. `MachinedPart.Finishes` : `App::PropertyLinkList`, lecture seule, groupe « Pièce ».

Chemins de persistance figés (ADR 0003) :
`freecad.menuiserie.features.edge_profile.EdgeProfile`,
`freecad.menuiserie.features.edge_banding.EdgeBanding`, view providers sous
`freecad.menuiserie.gui.view_providers.`.

### 4.4 Ordre des opérations de la pièce usinée

```
forme = brute
        − coeur de bande (D4)       −  profils (B2)
        − trims des assemblages (ADR 0016)
        + ajouts des assemblages    − enlèvements des assemblages
```

Les profils passent donc **avant** les ajouts (un tenon garde ses arêtes vives, comme sur l'établi
où l'on arrondit avant d'araser) et **avant** les enlèvements (une mortaise reste d'équerre). Le
graphe de recalcul reste sans cycle : brute → (assemblage, profil, bande) → pièce usinée ; un
profil ne lit que sa brute, la bande lit sa brute et les profils de celle-ci.

### 4.5 Sélection des arêtes (C3)

Le clic en 3D fournit un sous-élément `EdgeN` et son point. On calcule le milieu de l'arête cliquée
dans le repère local et on le rapproche des 12 arêtes de la boîte brute (distance minimale,
tolérance = 5 % de la plus petite cote). Une arête qui n'est plus sur la boîte (déjà profilée,
coupée par un assemblage) se rapproche de la plus proche et le panneau l'affiche coché. Seul le
code est conservé (B7).

### 4.6 Bande et cote de coupe (ADR 0030)

Les cotes `Length`/`Width` de la pièce restent les cotes **finies, bandes comprises** : contacts,
assemblages, accrochage et ensembles continuent de raisonner sur la boîte. La bande est un solide
de l'épaisseur choisie, posé *dans* la boîte finie ; le coeur est plus petit d'autant. La liste de
débit calcule la cote de coupe du panneau (`core_box`).

### 4.7 Design patterns

- Strategy + registre : familles de profils (A6).
- Template Method : squelette commun de `EdgeProfile` / `EdgeBanding` (proxy, schéma, modes
  d'édition) repris de `features/joints/base.py` autant que possible.
- Façade : `core.edges`, `core.banding`.
- State : sélection en 3D (idle / picking) dans le panneau, sans toucher `gui/drag`.

### 4.8 Sécurité

Codes d'arête et de chant validés contre une énumération fermée (jamais interprétés) ; réels finis
et bornés (A5, D3) ; au plus 12 profils et 4 chants par pièce ; identifiant de matériau de bande
soumis à la même règle que les autres identifiants ; bibliothèque lue comme aujourd'hui (JSON
strict, 1 Mio, ADR 0002). Aucune évaluation de texte, aucun fichier nouveau.

### 4.9 Compatibilité avec les autres ateliers (ADR 0007)

Objets `Part::FeaturePython` ordinaires ; la pièce usinée et les bandes sont des solides `Part`
valides, exportables (STEP), utilisables par TechDraw et visibles sans l'atelier. Aucun objet d'un
autre atelier n'est modifié, aucune propriété ajoutée à un objet étranger. Les arêtes sont lues
dans le repère de la pièce : un déplacement par un autre outil n'invalide rien.

## 5. Découpage en PR et impact

Deux jalons, chacun avec sa branche et sa PR de fin de jalon vers `main`.

| Lot | Contenu | Dépend de |
|-----|---------|-----------|
| CH-a | `core/edges/`, `Extrusion`, tests unitaires | — |
| CH-b | `EdgeProfile`, `MachinedPart.Finishes`, API, solide `Part` | CH-a |
| CH-c | commande, panneau, choix en 3D, icônes | CH-b |
| — | **PR jalon « Profils d'arête »** (revue complète) | CH-c |
| CH-d | `core/banding/`, `EdgeBanding`, kind `banding`, matériaux | CH-b |
| CH-e | liste de débit | CH-d |
| CH-f | panneau de bande, captures, recette | CH-d, CH-e |
| — | **PR jalon « Bande de chant »** (revue complète) | CH-f |

Fichiers existants touchés : `core/_polyhedron.py`, `features/solids.py`,
`features/machined_part.py`, `core/materials/_model.py`,
`data/materiaux.json`, `core/cutlist/_model.py` et `features/cutlist_*.py`, `gui/commands/`,
`_api/`, `tools/generer_icones.py`, `tools/captures_interface.py`, `CHANGELOG.md`,
`CONTRIBUTING.md` (liste des types d'objets).

## 6. Compatibilité des documents

`WoodPart` et les assemblages ne changent pas. `MachinedPart` passe en `Version` 2 (propriété
`Finishes` vide) ; migration dans `onDocumentRestored`. Un document enregistré avec les finitions
s'ouvre dans une version plus ancienne de l'atelier en **refusant** la pièce usinée (version
inconnue, message clair) : c'est le comportement habituel (ADR 0003). Aucun ancien document n'est
touché. Pas de migration utilisateur (« c'est une v0 », jv).

## 7. Risques

- Coins d'arêtes profilées : angle vif au croisement ; vérifié visuellement (captures) et par
  test de volume (A3, B2). Raffinement par arrondi de coin reporté (§ 8).
- Cotes de pièce réduites par un ensemble (étirement) : un profil devenu trop grand donne une
  erreur de recalcul traduite, pas un plantage ; le suivi proportionnel n'est pas proposé.
- Booléennes OCC sur sections à arcs : calcul de volume en test d'intégration, erreurs OCC
  converties en `ValueError` (`translated_errors`).
- Piège FreeCAD connu (mémoire du projet) : objets ajoutés en transaction depuis le panneau →
  tout passe par l'API de `features/`, jamais par des écritures directes de `gui/`.

## 8. Hors périmètre (issues à ouvrir si jv le souhaite)

- Profils sur une **pièce en bois** (`ShapedPart`) : formes libres, pas de boîte d'arêtes (Q4).
- **Alaise massive** : c'est une pièce de bois collée sur le chant ; faisable aujourd'hui avec
  une pièce et une rainure-languette. Une commande « Ajouter une alaise » (gabarit) peut suivre.
- **Retour d'onglet** d'un profil entre deux pièces coupées en biais.
- Arrondi des **coins** (sphérique) à la rencontre de trois arêtes ; profils partiels (arrêtés).
- **Bibliothèque de profils personnels** (JSON de sections libres) : la structure en registre la
  rend possible ; reportée (Q5).
- **Perçage des bandes** par un assemblage (tourillons au chant) : visuel seulement, les
  bandes restent pleines.
- **Configuration de l'atelier** (préférences, dont l'arête cassée par défaut) : issue #148.
- Profils différents par moitié d'arête, bande de chant sur chant courbe, bande à épaisseurs
  différentes par chant dans un même objet (deux objets suffisent).

## 9. Questions pour jv

Réponses de jv du 2026-11-01 : Q2 tranchée sur sa carte ; « go pour le reste » valide les choix ★ de Q1 et de Q3 à Q7 ; Q8 ci-dessous. ★ = choix retenu.

- Q1 **Périmètre et ordre.** ★ Deux jalons : profils d'abord, bande de chant ensuite ; l'alaise
  reste une pièce ordinaire. Sinon : bande d'abord (panneaux mélaminés tôt, comme le suggère
  l'issue), ou tout dans un seul jalon.
- Q2 **Cotes d'un panneau bandé.** **Tranché par jv le 2026-11-01 : cotes finies, bande comprise.** Les cotes de la pièce restent les cotes **finies, bande
  comprise** ; la liste de débit donne la cote de coupe. Sinon : la bande s'ajoute à l'extérieur
  des cotes (les cotes de la pièce sont celles du panneau nu).
- Q3 **Choix des arêtes.** ★ Cases à cocher + raccourcis **et** clic dans la vue 3D. Sinon : cases
  seulement (plus simple).
- Q4 **Pièce en bois (forme libre).** ★ Profils refusés pour l'instant. Sinon : profils sur la
  boîte d'encombrement seulement (peut surprendre sur une forme courbe).
- Q5 **Profils personnels** (JSON, comme les matériaux). ★ Reportés : sept familles intégrées
  d'abord. Sinon : inclus dans le premier jalon.
- Q6 **Longueur de chant commandée.** ★ Longueur nette arrondie au 0,1 m, sans marge. Sinon :
  marge de perte réglable (ex. +10 %), ou +50 mm par pièce pour le rognage.
- Q7 **Matériaux de bande.** ★ Dans la même bibliothèque (`materiaux.json`, kind `banding`),
  donc extensibles par l'utilisateur et texturables. Sinon : fichier séparé `bandes.json`.
- Q8 **Arête cassée par défaut.** Réponse de jv : pas d'application automatique ; ajouter une
  fonction de **configuration de l'atelier** (page de préférences), traitée plus tard : issue #148.
  Hors périmètre de ce chantier.