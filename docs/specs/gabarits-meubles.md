# Gabarits de meubles : bibliothèque, table, cadre et porte, tiroir

- Issue : #152 (gabarits de meubles courants) ; suite du gabarit « Caisson » de J4d.
- Statut : **proposée** (en attente des réponses de jv aux questions Q1 à Q10 du § 9 ; les choix ★ s'appliquent en attendant).
- Demande de jv (2026-11-05) : « avancer sur les specs des gabarits de meubles ».
- ADR : [0032 — Gabarits composés dans une ouverture](../adr/0032-gabarits-composes-dans-une-ouverture.md) (proposé). ADR liés : 0006 (brute et usinée), 0007 (compatibilité), 0008 et 0019 (ensembles), 0010 (gabarits générateurs, inchangé), 0024 (assemblages en biais).
- Hors périmètre : quincaillerie (poignées, charnières, coulisses : issue #159), finition des chants (issue #5), plans TechDraw (issue #153), liste de débit (déjà livrée : les gabarits ne font que créer des pièces ordinaires).

## 1. Contexte

L'ADR 0010 a fixé le principe : un gabarit est une **fonction pure** `…_layout(params) → Layout`
(`core/templates/`) ; `features/templates.py` la construit en pièces de bois, assemblages J3 et
Ensemble ordinaires ; aucun objet « gabarit » n'est gardé. Le Caisson (J4d) est livré et prouve
le mécanisme. L'étude de marché (#152) montre que le menuisier veut **adapter un modèle plutôt
que tout redessiner**. Cette spécification ajoute les gabarits suivants, sans changer ce principe.

## 2. Objectifs

1. Livrer, dans cet ordre, **Bibliothèque**, **Table**, **Cadre et panneau (porte)**, **Tiroir**
   (Q1). Chacun : « un meuble complet en quelques clics », cotes globales modifiables ensuite
   comme tout Ensemble, assemblages par défaut raisonnables, matériaux au choix.
2. Pouvoir **poser un gabarit dans une ouverture** d'un meuble existant (porte ou tiroir dans un
   caisson) avec les jeux qui conviennent (§ 4, ADR 0032).
3. Factoriser ce que les gabarits partagent (matériaux, origine, validation, répartition à
   intervalles égaux) pour qu'un nouveau gabarit tienne en une fonction `…_layout`, un panneau et
   une commande, comme le promet l'ADR 0010.
4. Rester compatible avec les autres ateliers (ADR 0007) : formes `Part` standard, noms dans
   notre espace, aucune modification globale de FreeCAD.

## 3. Gabarits, un par un

Repère de l'ensemble pour tous : X = largeur, Y = profondeur (avant en 0), Z = hauteur. Les cotes
sont celles du **hors tout**, comme pour le caisson. Les valeurs par défaut sont des propositions.

### 3.1 Bibliothèque (étagère haute, meuble ouvert)

Le caisson est déjà un meuble à étagères ; la bibliothèque en est la forme **ouverte et
cloisonnée**. Elle réutilise les fonctions du caisson (côtés, dessus, dessous, étagères, fond).

| Paramètre | Défaut | Remarque |
|---|---|---|
| L × P × H | 800 × 300 × 1800 | |
| Épaisseur des panneaux | 18 | comme le caisson |
| Fond | **Aucun** ★ / feuillure (comme le caisson) / panneau plaqué à l'arrière | `back_style` |
| Travées | 1 | 1 à 6 ; montants intermédiaires pleine hauteur entre dessous et dessus |
| Étagères par travée | 4 | 0 à 10, réparties à intervalles égaux, chaque travée indépendante |
| Socle | non | si oui : hauteur 60, retrait 20 à l'avant (pièce « Plinthe ») |
| Assemblage | tourillons | comme le caisson |

Les étagères restent **posées** (mode `Stay`, jeux de 1 mm), comme au caisson. Le nombre de
travées et d'étagères se fixe à la création (ADR 0010, point 4).

### 3.2 Table

Plateau posé sur un piètement de quatre pieds et de quatre traverses (tablier).

| Paramètre | Défaut (table à manger) | Remarque |
|---|---|---|
| L × P × H | 1600 × 800 × 750 | H = hauteur du dessus du plateau |
| Plateau : épaisseur | 30 | matériau massif par défaut `chene` |
| Plateau : débord | 40 tout autour | 0 pour un plateau à fleur |
| Pieds : section | 60 × 60 | carrés ★ (Q4), droits, sans conicité |
| Tablier : hauteur, épaisseur | 80 × 25 | traverses de long et de court |
| Tablier : retrait par rapport au pied | 10 | arase reculée, élégance du pied |
| Entretoise basse | non | si oui : barre en H à 150 mm du sol |
| Fixation du plateau | **posé, non assemblé** ★ (Q3) | les taquets viennent avec la quincaillerie (#159) |

Assemblages : traverses aux pieds par **tenon-mortaise** (J3) ; entretoise par tenon-mortaise.
Presets proposés (Q9) : « Table à manger » (ci-dessus), « Table basse » (1000 × 500 × 450,
pieds 50), « Bureau » (1400 × 700 × 740, mêmes règles ; le bureau de J4 reste un ensemble libre).

### 3.3 Cadre et panneau, porte

Un cadre rectangulaire : deux montants pleine hauteur, deux traverses (haute et basse), et un
remplissage. Sert de porte, de façade, de panneau de lit, de cadre de miroir.

| Paramètre | Défaut | Remarque |
|---|---|---|
| L × H × épaisseur | 400 × 700 × 22 | l'épaisseur est celle des bois du cadre |
| Largeur des montants / traverses | 60 / 60 | traverse basse réglable séparément (défaut 60) |
| Traverse intermédiaire | non | 0 à 3, répartie à intervalles égaux |
| Remplissage | **Panneau plein en rainure** ★ / vitrage (verre, hors catalogue, jeu seulement) / aucun | `fill` |
| Panneau : épaisseur | 10 | ; jeu au fond de la rainure : 2 mm par côté (le bois travaille) |
| Rainure | profondeur 10, largeur = épaisseur du panneau | sur la face intérieure de chaque bois |

Assemblages : traverses aux montants par **tenon-mortaise**, panneau par **rainure-languette**
(J3). Cas classique de l'**usinage croisé** (issue #19) : la rainure traverse le tenon. Le tenon
prend la largeur de la rainure et remplit la rainure ; le tenon à renfort reste le sujet de #19,
non bloquant (Q5).

**Porte de caisson.** Même gabarit, avec la source « ouverture » (§ 4) : le cadre est calculé
depuis l'ouverture choisie, avec le jeu (2 mm) et le recouvrement ou l'affleurement (Q7). Sans
quincaillerie, aucune charnière n'est posée.

**Fenêtre simple** (issue #152) : un dormant et un ouvrant sont deux cadres, plus un vitrage. Elle
reste **après** ce jalon (Q1) : elle demande le catalogue du verre et la feuillure vitrée.

### 3.4 Tiroir

Un tiroir pour un caisson, calculé depuis l'ouverture (§ 4) ou depuis ses propres cotes.

| Paramètre | Défaut | Remarque |
|---|---|---|
| Ouverture L × H × P | prise sur le caisson ou 560 × 150 × 380 | |
| Jeu latéral (par côté) | 13 | place d'une coulisse du commerce, 12,5 ; 2 sans coulisse |
| Jeu haut et bas | 3 | |
| Façade | **posée devant** (recouvre l'ouverture de 5 mm tout autour) ★ / affleurante | `front_style` |
| Corps : épaisseur des côtés, devant, derrière | 15 | `pin-sylvestre` par défaut |
| Fond | 6, en rainure dans les quatre parois, `cp-bouleau` | |
| Assemblage | **queue d'aronde devant, tenon-mortaise derrière** ★ (Q6) / tourillons | |

Pas de coulisse ni de poignée en livrable (Q10) : les jeux sont réservés, la quincaillerie
viendra par l'issue #159 (le tiroir lira ensuite son catalogue).

### 3.5 Escalier droit

**Reporté.** Il demande des pièces obliques (limons) et des assemblages à angle différent de 90°
(#78, ouverte pour la feuillure, les tourillons et la mi-bois). Une courte étude (règle de
Blondel `2h + g ≈ 63 cm`, nombre de marches calculé) suivra quand #78 sera tranchée.

## 4. Ouverture et gabarits composés (ADR 0032)

Une **ouverture** est un vide rectangulaire entre des pièces d'un ensemble : le vide d'un caisson
entre ses côtés, son dessus, son dessous (et la plus haute étagère). Elle est calculée par une
fonction pure de `core/templates/` à partir du `Layout` du caisson ou des pièces choisies, sans
géométrie FreeCAD.

- Porte et tiroir se **construisent dans** l'ouverture : l'utilisateur choisit un caisson (ou
  sélectionne le vide) ; le gabarit prend ses cotes, son origine et son jeu.
- Le résultat est un **sous-ensemble** du caisson (comme pour K5), avec ses propres cotes ; il
  suit le caisson aux options par défaut. Si l'ouverture change, le tiroir ou la porte la suit.
- Sans ouverture choisie, la porte et le tiroir ont leurs cotes libres et se placent à la
  souris ou par saisie, comme toute pièce.

## 5. Critères d'acceptation

Tests : U = unitaire (Python pur, `core/templates/`), I = intégration FreeCAD, G = GUI, manuel.

### GM-a — Socle commun (`core/templates/`)

| N° | Critère | Test |
|---|---|---|
| A1 | `_common.py` regroupe ce que partagent les gabarits : matériaux, `origin`, répartition à intervalles égaux, rotations de pièces. `carcass.py` est modifié sans changer de comportement : ses tests K1 à K4 passent inchangés. | U |
| A2 | `Opening` (objet valeur) : x, y, z, largeur, hauteur, profondeur libres ; `carcass_opening(layout, index)` en donne les vides (haut du caisson, entre étagères). Refus : ouverture plus petite que 1 mm. | U |
| A3 | `build_layout(… , parent=ensemble)` place le gabarit dans un ensemble existant sans casser le caisson (K5 étendu). | I |

### GM-b — Bibliothèque

| N° | Critère | Test |
|---|---|---|
| B1 | `bookcase_layout(BookcaseParams)` : par défaut 800 × 300 × 1800, 1 travée, 4 étagères, sans fond ; 2 côtés, dessus, dessous, 4 étagères ; position des étagères à intervalles égaux dans le vide. | U |
| B2 | Avec 3 travées : 2 montants intermédiaires pleine hauteur, largeur de travée égale, 4 étagères par travée soit 12, jeux de 1 mm. | U |
| B3 | `back_style` : « aucun » (aucune pièce de fond), « feuillure » (fond du caisson), « plaqué » (panneau sur l'arrière). `socle` : une plinthe, retrait 20. | U |
| B4 | `Depth` → 350 : montants, côtés, étagères suivent en un recompute ; les étagères restent à leur hauteur. | I |
| B5 | Refus (`BookcaseError`, gabarit traduit) : nombre de travées hors 1 à 6, étagère qui ne tient pas, épaisseur ≥ moitié de la plus petite cote. | U |
| B6 | Commande `Menuiserie_Bookcase`, panneau avec aperçu, une entrée « Créer une bibliothèque ». | G |

### GM-c — Table

| N° | Critère | Test |
|---|---|---|
| T1 | `table_layout(TableParams)` : plateau 1600 × 800 × 30, 4 pieds 60 × 60 × 720, 4 traverses 80 × 25, débord 40 ; le dessus est à z = 750. Traverses reculées de 10. | U |
| T2 | Entretoise : 1 barre en H (2 longues + 1 transverse) à 150 mm du sol, tenons aux pieds. | U |
| T3 | Assemblages : 8 tenon-mortaise (traverses), plateau non assemblé. | U |
| T4 | `Width` → 1800 : plateau, traverses longues, entretoise suivent ; les pieds gardent leur section et leur hauteur. `Height` → 740 : pieds raccourcis, plateau descendu. | I |
| T5 | Refus : plateau plus court que les pieds, tablier plus haut que la moitié de la hauteur, section de pied ≥ moitié du plus petit côté du piètement. | U |
| T6 | Presets « Table basse » et « Bureau ». Commande `Menuiserie_Table`. | U, G |

### GM-d — Cadre et panneau, porte

| N° | Critère | Test |
|---|---|---|
| C1 | `frame_layout(FrameParams)` : 2 montants 700 × 60 × 22, 2 traverses entre montants (400 − 120 = 280 de long), 1 panneau de remplissage 10 d'épaisseur avec 2 mm de jeu au fond de rainure. | U |
| C2 | Assemblages : 4 tenon-mortaise, 4 rainure-languette ; le tenon a la largeur de la rainure. | U |
| C3 | Traverse intermédiaire : 1 à 3, répartie à intervalles égaux, panneaux multiples (un par vide). `fill` = vitrage : pas de panneau, rainure maintenue. | U |
| C4 | `Width` → 500 : traverses et panneau suivent, les montants restent. | I |
| C5 | Porte de caisson : `door_from_opening(opening, gap=2, overlay)` donne le cadre ; affleurant : L = ouverture − 2 × jeu ; recouvrant : L = ouverture + 2 × recouvrement. | U |
| C6 | Refus : montant ≥ la moitié de la largeur, rainure ≥ épaisseur, jeu < 0. Commande `Menuiserie_Frame`. | U, G |

### GM-e — Tiroir

| N° | Critère | Test |
|---|---|---|
| D1 | `drawer_layout(DrawerParams)` : ouverture 560 × 150 × 380, jeu 13 par côté → corps 534 de large, profondeur ≤ 380, hauteur = 150 − 2 × 3. Façade recouvrant de 5 mm. | U |
| D2 | Parois 15, fond 6 dans une rainure de 6 × 8 de profondeur dans les quatre parois. | U |
| D3 | Assemblages : 2 queues d'aronde devant, 2 tenon-mortaise derrière (ou 4 tourillons, selon `joinery`). | U |
| D4 | `drawer_in_opening(carcass, opening)` : le tiroir devient sous-ensemble du caisson ; `Depth` du caisson → 500 : tiroir plus long. | I |
| D5 | Refus : ouverture trop basse pour des parois de 15 + fond, jeu latéral négatif, profondeur < 100. Commande `Menuiserie_Drawer`. | U, G |

### GM-f — Recette

| N° | Critère | Test |
|---|---|---|
| R1 | Scénarios manuels (`docs/recette/gabarits-meubles-scenarios-manuels.md`) : une bibliothèque de 3 travées, une table redimensionnée, une porte et un tiroir dans un caisson ; liste de débit exacte pour chacun. | manuel |
| R2 | Captures publiées dans la PR du jalon : un meuble par gabarit. | CI |

## 6. Conception

- `core/templates/` gagne `_common.py`, `bookcase.py`, `table.py`, `frame.py`, `drawer.py`,
  `opening.py` ; chaque module a son `…Params` (validé, `…Error` traduisible) et son `…_layout`
  pur. Aucun import de FreeCAD (règle de `core/`).
- `features/templates.py` ne change pas de principe : il instancie un `Layout` (pièces, assemblages,
  Ensemble). Il gagne l'option `parent`, déjà prévue pour K5.
- `gui/commands/` : une commande et un panneau par gabarit ; les panneaux partagent un
  `TemplatePanel` (aperçu, une transaction, refus affichés sous les champs), tiré de celui du
  caisson. Icônes : `tools/generer_icones.py` (jamais à la main).
- Aucun nouveau type d'objet persistant : pas de migration (ADR 0010).

## 7. Découpage

| Lot | Contenu | Dépend de |
|---|---|---|
| GM-a | socle commun, `Opening`, `parent` | J4d |
| GM-b | Bibliothèque | GM-a |
| GM-c | Table (peut avancer en parallèle de GM-b) | GM-a |
| GM-d | Cadre et panneau, porte de caisson | GM-a |
| GM-e | Tiroir dans une ouverture | GM-a, GM-d (jeux) |
| GM-f | Recette et captures | tous |

Un fil, une branche de jalon `jalon/gabarits`, sous-branches squashées, une PR de jalon vers
`main` (règles du projet). Fenêtre et escalier : jalons à part.

## 8. Risques

- **Usinage croisé du cadre** (#19) : tenon et rainure se rencontrent ; couvert par le tenon qui
  remplit la rainure, avertissement si le résultat est douteux.
- **Ouvertures** : un vide mal calculé produit un tiroir qui frotte. Les jeux sont des paramètres
  visibles et le calcul est testé sans FreeCAD.
- **Quincaillerie** (#159) : les gabarits ne devancent pas la décision de jv ; les jeux des
  coulisses sont réservés par un paramètre.
- **Régénération** : on ne modifie pas le nombre de travées après coup (ADR 0010). Si jv le
  demande, un lot « régénérer » aura son ADR.

## 9. Questions pour jv (★ = appliqué en attendant votre réponse)

**Q1 — Ordre et périmètre ?** **Bibliothèque, Table, Cadre-porte, Tiroir** ★ / ajouter la fenêtre /
ajouter l'escalier (dépend de #78).

**Q2 — Bibliothèque : nouveau gabarit ou options du caisson ?** **Nouveau gabarit « Bibliothèque »
qui réutilise le code du caisson** ★ / ajouter travées, socle et fond optionnel au Caisson.

**Q3 — Table : fixation du plateau ?** **Posé, non assemblé** ★ / tourillons dans les traverses /
taquets (après la quincaillerie).

**Q4 — Pieds de table ?** **Carrés de section réglable** ★ / section L × l / conique (plus tard).

**Q5 — Cadre : le tenon à renfort (#19) est-il nécessaire dès ce jalon ?** **Non, tenon qui
remplit la rainure** ★ / oui, faire #19 avant.

**Q6 — Tiroir : assemblage du corps ?** **Queue d'aronde devant, tenon-mortaise derrière** ★ /
tourillons seuls / mi-bois.

**Q7 — Porte : posée en applique (recouvrante) ou affleurante ?** **Recouvrante de 5 mm** ★ /
affleurante avec 2 mm de jeu / au choix à la création.

**Q8 — Poser un gabarit dans un caisson existant (ADR 0032) ?** **Oui, par choix de l'ouverture** ★ /
non, gabarits indépendants à placer à la main.

**Q9 — Tailles usuelles (table à manger, table basse, bureau) ?** **Oui, en présélections codées
dans le gabarit** ★ / non / présélections modifiables par l'utilisateur (bibliothèque, plus tard).

**Q10 — Quincaillerie dans les gabarits ?** **Aucune en livrable, jeux réservés** ★ / poignées
et charnières génériques dès ce jalon.
