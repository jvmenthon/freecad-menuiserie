# [J4] Ensembles, gabarits et assemblages 2 : bureau à cotes globales, caisson en quelques clics

- Jalon : J4 (version cible 0.3.0, à confirmer par jv)
- Statut : **proposée** (2026-10-21), en attente des réponses de jv aux questions du § 9
- Exigences de jv intégrées : modifier facilement un ensemble de pièces (spécification J3, § 8,
  2026-10-20) ; position des pièces intérieures, deux modes, « par défaut elle ne bouge pas »,
  formule respectée avec avertissement (décision de jv du 2026-10-20) ; les assemblages de J3
  suivent ; compatibilité avec les autres addons (ADR 0007), y compris Std Part et `App::Link`
- ADR liés : [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](../adr/0006-piece-brute-et-piece-usinee.md) (accepté),
  [0007 — Compatibilité avec les autres ateliers](../adr/0007-compatibilite-avec-les-autres-ateliers.md) (accepté),
  [0008 — L'Ensemble, objet de cotes hors conteneur](../adr/0008-ensemble-objet-de-cotes.md) (proposé),
  [0009 — Suivi des pièces par expressions natives](../adr/0009-suivi-par-expressions-natives.md) (proposé),
  [0010 — Gabarits générateurs](../adr/0010-gabarits-generateurs.md) (proposé)
- Découpage : cinq PR **J4a → J4b′ → (J4c ∥ J4d)**, et **J4e** indépendant (§ 5). Le prime de
  J4b′ évite la confusion avec **J4b**, la finition des chants (issue #5), qui reste un jalon à part.

## 1. Contexte

Avec J3, le menuisier dessine des pièces et les assemble ; les assemblages suivent les cotes et
les positions des pièces en un recalcul (ADR 0006). Mais pour rendre un bureau plus profond, il
doit changer à la main le plateau, les deux joues, déplacer le voile de fond, ou écrire lui-même
une dizaine d'expressions. Exigence de jv, mot pour mot : « je veux pouvoir modifier facilement un
ensemble de piece; par exemple si j'ai concu un bureau, je veux pouvoir modifier la profondeur de
celui-ci et des toutes les pieces impactés (plateau; caisson) ». Le plan (§ 7) attend aussi en J4
un caisson paramétrique (« un caisson complet en quelques clics »), le mi-bois et la queue
d'aronde. La liste de débit (J2) vient après J4 et lira les ensembles et les gabarits.

## 2. Objectif

Le menuisier peut :

1. regrouper des pièces dans un **Ensemble** (« Bureau ») qui porte trois cotes globales
   (`Width`, `Depth`, `Height`) ; changer une cote étire, déplace ou laisse en place chaque pièce
   selon des règles de menuisier, **par des expressions FreeCAD natives** visibles dans les pièces ;
2. choisir, pour une pièce intérieure (étagère, voile de fond), entre **position fixe** (elle
   garde sa distance au bord de départ : par défaut, **elle ne bouge pas**) et **proportion** ;
3. garder ses propres formules : une cote ou une position déjà pilotée par une expression ou une
   contrainte n'est jamais remplacée ; la formule s'applique et un **avertissement** le signale ;
4. voir les assemblages de J3 (pièces usinées, tenons, tourillons…) **suivre** en un recalcul ;
5. créer un **caisson** complet (côtés, dessus, dessous, fond en feuillure, étagères, tourillons)
   par un gabarit, puis le redimensionner comme tout Ensemble ;
6. relier deux pièces par un **mi-bois** (sous réserve de Q6) ;
7. ranger l'ensemble dans un **Std Part**, le dupliquer par **`App::Link`**, le dessiner dans
   TechDraw et l'exporter en STEP, sans que l'atelier gêne les autres outils (ADR 0007).

**Livrable visible** : le bureau de référence (§ 3) passe de 600 à 800 mm de profondeur par une
seule saisie ; le caisson de référence est créé en une commande puis rendu plus haut.

## 3. Critères d'acceptation

Légende : **U** = unitaire sans FreeCAD, **I** = intégration dans `freecadcmd` (1.0 et 1.1),
**G** = interface hors écran, **manuel** = recette décrite dans `docs/recette/J4-scenarios-manuels.md`.
Les lettres des critères sont propres à cette spécification.

**Bureau de référence** (cotes en mm, ensemble « Bureau » dans le document, sans conteneur ;
`EdgeMargin` = 50 mm, sous réserve de Q3). Étendues dans le repère de l'ensemble (X = largeur,
Y = profondeur, Z = hauteur) :

| Pièce | Cotes L × l × e | `Placement` (base ; rotation) | X | Y | Z |
|---|---|---|---|---|---|
| Plateau P | 1200 × 600 × 30 | (0, 0, 720) ; aucune | [0, 1200] | [0, 600] | [720, 750] |
| Joue gauche JG | 720 × 560 × 22 | (22, 0, 0) ; −90° autour de Y (L selon Z, e selon −X) | [0, 22] | [0, 560] | [0, 720] |
| Joue droite JD | 720 × 560 × 22 | (1200, 0, 0) ; idem | [1178, 1200] | [0, 560] | [0, 720] |
| Voile V | 1156 × 400 × 18 | (22, 459, 320) ; +90° autour de X (l selon Z, e selon −Y) | [22, 1178] | [441, 459] | [320, 720] |

Assemblages : tourillons JG–V et JD–V (hôte = joue, invitée = voile), valeurs automatiques de
J3 : contact 400 × 18 → 4 tourillons Ø 8 × 35. Les joues sont en retrait de 40 mm à l'arrière
(≤ `EdgeMargin`) ; le voile est intérieur en profondeur (141 mm du fond, 441 mm de l'avant).
Cotes de l'ensemble à la création : 1200 × 600 × 750, `Origin` = (0, 0, 0).

### J4a — Règles de suivi et liaisons (`core/furniture/`)

| N° | Critère | Test |
|---|---|---|
| F1 | Objets valeur validés à la construction : `FurnitureBox` (trois cotes finies, non booléennes, de `MIN_DIMENSION_MM` à `MAX_DIMENSION_MM`), `Member`, `FollowRule` ; `InteriorMode` a les valeurs stables `Fixed`, `Proportional` (ordre figé). `ValueError` citant le champ ; un cas refusé et un cas limite accepté par règle. | U |
| F2 | `member_spans(member, box)` : étendue de chaque membre sur X, Y, Z du repère de l'ensemble et axe local aligné (`Length`, `Width`, `Thickness`) par `relative_axes` (J3) ; bureau de référence : valeurs du tableau. Un membre tourné de 45° par rapport à l'ensemble est exclu des liaisons avec la notice `NotSquare` (« « Voile » n'est pas d'équerre avec l'ensemble : il ne suit pas ses cotes. »). | U |
| F3 | **Accroche aux bords** : une face à ≤ 0,01 mm du bord de départ d'un axe est `Start`, du bord de fin `End`. Bureau : P `Start`/`End` sur X et Y, `End` sur Z (pièce non étirable en Z : ses deux faces suivent la face accrochée) ; JG `Start` sur X ; JD `End` sur X. | U |
| F4 | **Propagation par contact** (`core/contact.classify`, faces normales à l'axe) jusqu'à point fixe, résultat indépendant de l'ordre des membres : V `Start` en X (contre JG) et `End` en X (contre JD) ; V et JG/JD `End` en haut de Z (contre le dessous de P). | U |
| F5 | **Retrait** : une face encore libre à ≤ `EdgeMargin` d'un bord le suit : JG/JD `End` à l'arrière (40 mm). `EdgeMargin` = 0 → leur arrière suit le mode intérieur (`Fixed` : ne bouge pas). Face à ≤ `EdgeMargin` des deux bords : le plus proche ; égalité → `Start`. Le retrait ne remplace jamais une accroche par bord ou par contact. | U |
| F6 | **Pièce intérieure** (face ni accrochée, ni en contact, ni en retrait) : mode `Fixed` (défaut) → `Start`, la pièce **ne bouge pas** ; mode `Proportional` → la coordonnée garde sa proportion de la cote ; sur un axe non étirable, c'est le **milieu** de la pièce qui la garde. Bureau, V en `Proportional` : milieu à 450 / 600 = 0,75 de la profondeur. | U |
| F7 | **Épaisseur jamais étirée** : sur l'axe de `Thickness`, une seule règle par pièce (priorité bord > contact > retrait > mode) ; conflit de même priorité (pièce aussi épaisse que l'ensemble) → `Start` et notice `ThicknessKept`. Une cote d'ensemble ne change jamais une pièce qu'elle ne traverse pas. | U |
| F8 | **Liaisons** (`bindings_for`) : expressions exactes pour le bureau — P : `Length` = `<<Bureau>>.Width`, `Width` = `<<Bureau>>.Depth`, `Placement.Base.z` = `<<Bureau>>.Height - 30 mm` ; JG et JD : `Length` = `<<Bureau>>.Height - 30 mm`, `Width` = `<<Bureau>>.Depth - 40 mm` ; JD : `Placement.Base.x` = `<<Bureau>>.Width` ; V : `Length` = `<<Bureau>>.Width - 44 mm`, `Width` = `<<Bureau>>.Height - 350 mm`, aucune sur Y en `Fixed`, `Placement.Base.y` = `<<Bureau>>.Depth * 0.75 + 9 mm` en `Proportional`. La coordonnée de `Placement.Base` liée est celle de l'origine locale (début ou fin de l'étendue selon le signe de l'axe). Nombres : au plus 9 décimales, sans zéros inutiles, constante nulle omise. Aucune liaison qui ne changerait rien (`Start` des deux côtés). | U |
| F9 | **Formules de l'utilisateur** : une propriété listée dans `Member.driven` (expression ou contrainte) ne reçoit aucune liaison ; notice `UserFormula` (avertissement) citant pièce et propriété. Une liaison dont le texte enregistré diffère de l'expression actuelle est traitée comme une formule de l'utilisateur. | U |
| F10 | **Aperçu et refus** (`predict`, `check_resize`) : Depth → 800 donne P 1200 × 800, JG/JD l = 760, V inchangé (`Fixed`) ou Y ∈ [591, 609] (`Proportional`) ; Height → 800 : P en z = 770, V l = 450. Refus (`FurnitureError`, gabarit traduit) : Depth → 30 (« « Joue gauche » deviendrait trop petite : Width = −10 mm ») ; Height → 350,05 (V l = 0,05 < 0,1) ; une paire d'assemblage donnée qui changerait de classe (`Contact` → `Separated`). | U |
| F11 | **Sous-ensemble membre** (sous réserve de Q2) : un `FurnitureBox` membre est une boîte dont les trois cotes sont étirables ; ses liaisons portent sur `Origin.x/y/z`, `Width`, `Depth`, `Height`. Un ensemble ne peut pas être membre de lui-même ni d'un de ses membres (`FurnitureError`). | U |
| F12 | `core/` n'importe ni FreeCAD ni Qt ; couverture de `core/` ≥ 90 % ; aucun module > 400 lignes. | U |

### J4b′ — L'objet Ensemble dans le document (`features/`, `api.py`)

| N° | Critère | Test |
|---|---|---|
| N1 | `make_furniture([P, JG, JD, V], label="Bureau")` (pièces brutes ou usinées) : un objet `Furniture`, cotes 1200 × 600 × 750, `Origin` (0, 0, 0) ; chaque brute reçoit `Furniture`, `PositionMode` = `Fixed` et `FurnitureBindings` ; expressions de F8 dans les `ExpressionEngine` ; après `recompute()` les formes et volumes sont inchangés et aucun objet n'est « Touched ». | I |
| N2 | Chaque propriété des tableaux du § 4.4 existe avec type, groupe, infobulle, défaut et mode d'édition indiqués ; `WoodPart` garde `Version` = 2 ; une pièce hors ensemble n'a aucune propriété ajoutée. | I |
| N3 | **Le bureau suit** : `Depth` = 800 → un recompute → P 1200 × 800 × 30, JG/JD 720 × 760 × 22, V à Y ∈ [441, 459] ; `Height` = 800 → P en z = 770, joues de 770, V de 1156 × 450 et **5** tourillons de chaque côté ; `Width` = 1400 → P de 1400, JD en x ∈ [1378, 1400], V de 1356. Tout valide, aucun « Touched ». | I |
| N4 | `set_position_mode(V, "Proportional")` réécrit les seules liaisons de V (une transaction) ; `Depth` = 800 → V à Y ∈ [591, 609]. Retour à `Fixed` → liaison Y supprimée, V reste où il est. | I |
| N5 | **Formule de l'utilisateur** (décision de jv) : V porte `Placement.Base.y` = `<<Bureau>>.Depth - 141 mm` avant `make_furniture` → l'expression est gardée, la liste renvoyée et la vue rapport contiennent l'avertissement `UserFormula` ; `Depth` = 800 → `Placement.Base.y` de V = 659 (la formule s'applique) et un avertissement cite V ; changer son mode ne touche pas cette propriété (avertissement). Même règle pour une pièce placée par une contrainte de l'atelier Assembly (§ 4.4.3). | I |
| N6 | **Assemblages J3** : les pièces usinées et leurs assemblages restent valides après chaque changement de N3, valeurs automatiques recalculées (nombre de tourillons de N3), en un seul recompute ; les liaisons sont posées sur la **brute** ; déplacer la pièce usinée d'une brute dont `Placement` est lié est refusé avec un message (aucune écriture perdue en silence). | I |
| N7 | `resize_furniture(bureau, depth=30)` → `ValueError` traduite citant JG, rien n'est modifié (cotes, expressions, aucune transaction ouverte). Cote saisie dans l'éditeur de propriétés qui casse une pièce : comportement de Q4 (recommandé : appliquée, pièces ou assemblages en erreur sans forme partielle, avertissement, `undo()` rétablit tout). | I |
| N8 | `add_to_furniture(bureau, objets)` et `remove_from_furniture(objets)` : ajout = liaisons calculées sur la géométrie actuelle ; retrait = suppression des **seules** liaisons de l'atelier (texte identique à `FurnitureBindings`) et des trois propriétés ajoutées, géométrie inchangée. Refus avant modification (`TypeError`/`ValueError` traduites) : objet qui n'est ni pièce ni ensemble, membre d'un autre ensemble, conteneur (`getParentGeoFeatureGroup`) différent de celui de l'ensemble, autre document. `rebind_furniture(bureau)` recalcule toutes les liaisons de l'atelier d'après la géométrie actuelle. | I |
| N9 | **Std Part** : bureau et pièces dans un `App::Part` tourné de 30° autour de Z et déplacé → N3 donne les mêmes cotes (repère du conteneur) ; déplacer le Std Part déplace le bureau sans toucher aux liaisons. | I |
| N10 | **`App::Link`** : un lien vers ce Std Part suit le redimensionnement de l'original (`Part.getShape(lien)` : même volume que l'original, à 1e-6 près relatif) ; « Édition › Dupliquer la sélection » du Std Part donne un second bureau indépendant dont les liaisons visent la copie de l'ensemble (sinon : avertissement `UserFormula` et `rebind_furniture` les rétablit). | I |
| N11 | **Sous-ensemble** (sous réserve de Q2) : un ensemble « Caisson » membre du bureau suit `Depth` (`<<Bureau>>.Depth - 40 mm`) et ses propres pièces suivent le caisson, en un recompute ; un cycle d'ensembles est refusé. | I |
| N12 | Enregistrer, fermer, rouvrir : propriétés, expressions et `FurnitureBindings` identiques, aucun « Touched » ; proxy `freecad.menuiserie.features.furniture.Furniture`, `dumps()` = `None`, `Version` = 1. Réouverture contrôlée (ADR 0003, aides de `schema.py`) : `Version` absente, plus récente ou mal typée ; propriété de membre mal typée (`PositionMode` en `App::PropertyString`) supprimée avec avertissement et recréée à `Fixed`. | I |
| N13 | Annuler / rétablir : création, ajout, retrait, changement de mode, redimensionnement = **une** entrée chacun ; `undo()` restaure cotes, expressions et propriétés de membre. | I |
| N14 | **Compatibilité (ADR 0007)** : le bureau dans un Std Part sert de source à une vue TechDraw qui se recalcule sans erreur ; le Std Part s'exporte en STEP et se réimporte avec le même volume ; document ouvert dans un `freecadcmd` sans l'atelier : il s'ouvre, formes valides de même volume. Inventaire : type `Menuiserie::Furniture`, commandes `Menuiserie_…`, aucune dépendance d'exécution, aucun observateur global. | I (TechDraw : ignoré si non importable, alors G) |
| N15 | Les documents J1 et J3 s'ouvrent sans changement (aucune propriété ajoutée, rien de « Touched ») ; `record_of(brute)` inchangé pour un membre. | I |

### J4c — Affichage, commandes et panneau de l'Ensemble (`gui/`)

| N° | Critère | Test |
|---|---|---|
| P1 | Commandes `Menuiserie_Furniture` (« Ensemble », active si au moins une pièce est sélectionnée et aucun panneau ouvert) et `Menuiserie_FurnitureAdd` (« Ajouter à l'ensemble », pièces + un ensemble sélectionnés) dans la barre d'outils et le menu ; icône `Menuiserie_Furniture.svg` générée par `tools/generer_icones.py` ; une entrée d'annulation par commande. | G |
| P2 | `ViewProviderFurniture` : l'ensemble apparaît dans l'arbre avec ses membres en enfants (pièce usinée à la place de sa brute, sous-ensembles, assemblages dont les deux pièces sont membres) ; double-clic → panneau. Supprimer l'ensemble dans l'interface retire d'abord les liaisons de l'atelier et les propriétés de membre (`onDelete`, même transaction) : aucune expression orpheline. | G |
| P3 | Panneau : trois champs de cotes et `EdgeMargin` ; liste des membres avec une colonne « Position » (`Fixed` / `Proportional`, traduits « Ne bouge pas » / « Proportion ») et une colonne « Suit » (« étirée », « déplacée », « fixe », « proportion », « formule », « pas d'équerre ») ; bouton « Relier les pièces ». Chaque saisie est prévisualisée ; « OK » = une entrée « Modifier l'ensemble » ; « Annuler » rétablit tout. | G |
| P4 | Un refus de `check_resize` s'affiche sous les champs (message traduit) et désactive « OK » ; les avertissements `UserFormula`, `NotSquare`, `ThicknessKept` s'affichent dans le panneau et la vue rapport. | G |
| P5 | Cote d'ensemble pilotée par une expression (sous-ensemble) : champ inactif, jamais écrit (règle C6 de J1). | G |
| P6 | Aucun observateur global laissé en place ; aucune préférence hors de `Mod/Menuiserie` ; chaînes traduisibles ; `from PySide import …` seulement. | G + revue |
| P7 | Scénario du livrable (bureau dessiné à la main, Ensemble, profondeur 600 → 800, voile en proportion, formule de l'utilisateur, annuler, rétablir, enregistrer, rouvrir, Std Part + `App::Link`, vue TechDraw) sur FreeCAD 1.0 et 1.1 ; coexistence avec l'atelier Assembly intégré (le Std Part sert de composant) ; captures dans la PR. | manuel |

### J4d — Gabarit « Caisson » (`core/templates/`, `features/templates.py`, `gui/`)

**Caisson de référence** : 600 × 400 × 720 (L × P × H), panneaux de 18 en `cp-bouleau`, fond de 8
logé en feuillure de 10, une étagère.

| N° | Critère | Test |
|---|---|---|
| K1 | `carcass_layout(CarcassParams)` (pur) renvoie pièces et assemblages : côtés 720 × 400 × 18 (x ∈ [0, 18] et [582, 600]) ; dessus et dessous 564 × 400 × 18 entre les côtés ; fond 704 × 584 × 8 à y ∈ [392, 400], x ∈ [8, 592], z ∈ [8, 712] ; étagère 562 × 391 × 18 à x ∈ [19, 581], y ∈ [0, 391], z ∈ [351, 369] ; 4 tourillons (côté hôte, dessus/dessous invité, Ø 8, longueur 30, profondeur dans l'hôte 12) ; 4 feuillures (hôte = côté, dessus, dessous ; invité = fond) ; étagère sans assemblage, mode `Fixed`. | U |
| K2 | `CarcassParams` validé : cotes de F1 ; épaisseur > 0 et < moitié de la plus petite cote ; fond plus mince que les panneaux ; feuillure ≤ épaisseur ; 0 à 10 étagères réparties à intervalles égaux ; identifiants de matériaux connus. `ValueError` citant le champ. | U |
| K3 | `make_carcass(doc, params)` : en un recompute, 6 pièces, 4 assemblages tourillons, 4 feuillures, 5 pièces usinées (l'étagère reste une brute), un Ensemble 600 × 400 × 720 (`Template` = `Carcass`) et ses liaisons ; tout valide ; 4 tourillons par jonction. | I |
| K4 | Le caisson suit : `Depth` = 500 → côtés, dessus, dessous de 500, fond à y ∈ [492, 500], étagère de 491, **5** tourillons par jonction ; `Height` = 800 → côtés de 800, dessus en z ∈ [782, 800], étagère **immobile** en z ∈ [351, 369] (`Fixed`) ou en z ∈ [391, 409] (`Proportional`). | I |
| K5 | `make_carcass(doc, params, furniture=bureau)` : le caisson devient membre du bureau (sous-ensemble si Q2 = Oui, sinon ses pièces rejoignent directement le bureau). | I |
| K6 | Commande `Menuiserie_Carcass` (« Caisson », icône existante) : panneau de paramètres, aperçu, « OK » = une entrée « Créer un caisson » ; « Annuler » ne laisse aucun objet. | G |
| K7 | Recette du livrable du plan : « un caisson complet en quelques clics », redimensionné, vue TechDraw. | manuel |

### J4e — Mi-bois (`core/joints/half_lap.py`, `features/joints/half_lap.py`) — sous réserve de Q6

| N° | Critère | Test |
|---|---|---|
| B1 | `HalfLapStrategy` (registre J3) : deux pièces qui se croisent (chevauchement sur toute l'épaisseur commune) ; chaque pièce perd la moitié de la boîte commune, l'hôte la moitié haute (+Z local), l'invitée la moitié basse ; `Depth` = 0 → automatique, moitié de l'épaisseur commune arrondie au mm ; `FlipSide` inverse. Croix de deux traverses 600 × 60 × 22 → entailles 60 × 60 × 11. Refus : chevauchement partiel, pièces pas d'équerre (M1). | U |
| B2 | `make_half_lap`, proxy `…features.joints.half_lap.HalfLapJoint`, type `Menuiserie::HalfLap`, réouverture et annulation comme O8 et O10 de J3. | I |
| B3 | Commande `Menuiserie_HalfLap` (icône existante) dans la famille de J3d ; panneau J3e générique. | G |
| B4 | Membres d'un Ensemble : l'entaille suit le redimensionnement (N3). | I |

## 4. Conception

### 4.1 Principe (ADR 0008, 0009, 0010)

- **Ensemble** = un objet de **cotes** (`App::FeaturePython`, nom interne `Furniture`), sans
  forme et **sans lien vers ses membres** : il porte `Width`, `Depth`, `Height`, un coin de
  départ `Origin` et `EdgeMargin`. Son repère est celui du conteneur commun de ses membres
  (document ou Std Part) : X = largeur, Y = profondeur, Z = hauteur.
- **Membre** = pièce brute (ou sous-ensemble) qui porte un lien `Furniture` vers son ensemble.
  Les dépendances vont des membres vers l'ensemble, jamais l'inverse : aucun cycle possible.
- **Liaison** = expression FreeCAD native posée par l'atelier dans l'`ExpressionEngine` d'un membre
  (`Width = <<Bureau>>.Depth - 40 mm`). Elle est calculée **une fois** (création, ajout, changement
  de mode, « Relier ») par les règles pures de `core/furniture` ; ensuite, changer une cote ne fait
  appel à aucun code de l'atelier : FreeCAD évalue les expressions, puis les assemblages et les
  pièces usinées suivent (ADR 0006).
- **Gabarit** = générateur ponctuel : il crée des pièces, des assemblages et un Ensemble ordinaires,
  puis disparaît (ADR 0010).

```
freecad/menuiserie/
├── core/
│   ├── furniture/
│   │   ├── __init__.py          J4a  façade : FurnitureBox, Member, InteriorMode, FollowRule, Binding, Notice, FurnitureError
│   │   ├── _model.py            J4a  objets valeur, validation
│   │   ├── _follow.py           J4a  member_spans, accroche, contact, retrait, mode → follow_rules
│   │   ├── _bindings.py         J4a  bindings_for, format des expressions et des nombres
│   │   └── _check.py            J4a  predict, check_resize
│   ├── templates/
│   │   ├── __init__.py          J4d  PieceSpec, JointSpec, Layout
│   │   └── carcass.py           J4d  CarcassParams, carcass_layout
│   └── joints/half_lap.py       J4e  HalfLapParams, HalfLapStrategy
├── features/
│   ├── furniture.py             J4b′ proxy Furniture, création, membres, réouverture
│   ├── furniture_bindings.py    J4b′ lecture des membres (blocs, formules), écriture et retrait des liaisons
│   ├── templates.py             J4d  instanciation d'un Layout (pièces, assemblages, ensemble)
│   └── joints/half_lap.py       J4e  HalfLapJoint
├── api.py                       J4b′ make_furniture, add_to_furniture, remove_from_furniture, set_position_mode,
│                                     rebind_furniture, resize_furniture ; J4d make_carcass ; J4e make_half_lap
└── gui/
    ├── view_providers/furniture.py  J4c
    ├── commands/furniture.py        J4c  Menuiserie_Furniture, Menuiserie_FurnitureAdd ; J4d Menuiserie_Carcass
    └── task_panels/
        ├── furniture.py             J4c  FurnitureTaskPanel (ObjectTaskPanel de J3e)
        └── carcass.py               J4d  CarcassTaskPanel
```

### 4.2 Design patterns retenus

| Besoin | Pattern | Justification |
|---|---|---|
| Règles de suivi (bord, contact, retrait, mode) | **Chaîne de règles** ordonnée par priorité, fonctions pures | quatre sources d'accroche ; ordre de priorité explicite et testable, pas de `if` imbriqués |
| Données de l'ensemble | **objets valeur** immuables (`FurnitureBox`, `Member`, `FollowRule`, `Binding`, `Notice`, `CarcassParams`, `Layout`) | testables sans FreeCAD |
| Création | **Fabrique** (`create_furniture`, `make_furniture`, `make_carcass`) | commandes, scripts et tests |
| Gabarits | **Builder** : `carcass_layout` décrit, `features/templates.py` construit | un seul constructeur pour tous les gabarits futurs (étagère, cadre, tiroir) |
| Mi-bois | **Strategy + registre** de J3 | point d'extension prévu |
| Objets du document | **Proxy** FeaturePython + ViewProvider séparé | règle du projet |
| Avertissements au changement de cote | **Observer** (`onChanged` du proxy, hors restauration et annulation) | pas d'appel croisé, pas d'observateur global |

### 4.3 `core/furniture/` (J4a)

```python
class InteriorMode(str, Enum):  # enregistré (PositionMode) : valeurs stables, ajout en fin seulement
    FIXED = "Fixed"
    PROPORTIONAL = "Proportional"


class Anchor(Enum):  # non enregistré
    START = "Start"  # garde sa distance au bord de départ
    END = "End"  # garde sa distance au bord de fin
    RATIO = "Ratio"  # garde sa proportion de la cote


class FurnitureAxis(Enum):  # X = Width, Y = Depth, Z = Height
    WIDTH = "Width"
    DEPTH = "Depth"
    HEIGHT = "Height"


@dataclass(frozen=True)
class FurnitureBox:
    width: float
    depth: float
    height: float


@dataclass(frozen=True)
class Member:
    key: str  # nom interne de l'objet (Name)
    block: PlacedBlock | None  # pièce : cotes + placement dans le repère de l'ensemble (origine déduite)
    box: FurnitureBox | None  # sous-ensemble : ses cotes (et `origin`)
    origin: Vec3 | None
    mode: InteriorMode
    driven: frozenset[str]  # propriétés pilotées par une formule ou une contrainte de l'utilisateur


@dataclass(frozen=True)
class FollowRule:  # règle d'un membre sur un axe
    axis: FurnitureAxis
    start: Anchor
    end: Anchor
    local: str | None  # "Length" ou "Width" si étirable, None si Thickness (une seule règle)


@dataclass(frozen=True)
class Binding:
    key: str
    prop: str  # "Length", "Width", "Placement.Base.y", "Origin.x", "Depth"…
    expression: str  # texte FreeCAD, « <<Bureau>>.Depth - 40 mm »


@dataclass(frozen=True)
class Notice:  # avertissement traduisible, jamais bloquant
    template: str
    params: Mapping[str, str]


class FurnitureError(TemplatedError): ...  # refus (redimensionnement, cycle d'ensembles)


def member_spans(member: Member, box: FurnitureBox) -> Mapping[FurnitureAxis, tuple[float, float, str]]: ...
def follow_rules(box: FurnitureBox, members: Sequence[Member], edge_margin: float) -> tuple[Mapping[str, tuple[FollowRule, ...]], tuple[Notice, ...]]: ...
def bindings_for(label: str, box: FurnitureBox, members: Sequence[Member], rules: Mapping[str, tuple[FollowRule, ...]]) -> tuple[tuple[Binding, ...], tuple[Notice, ...]]: ...
def predict(old: FurnitureBox, new: FurnitureBox, members: Sequence[Member], rules: Mapping[str, tuple[FollowRule, ...]]) -> Mapping[str, PlacedBlock | FurnitureBox]: ...
def check_resize(old: FurnitureBox, new: FurnitureBox, members: Sequence[Member], rules: Mapping[str, tuple[FollowRule, ...]], joined: Sequence[tuple[str, str]]) -> None: ...  # FurnitureError
```

**Règle de suivi d'une coordonnée** (début ou fin de l'étendue d'un membre sur un axe), première
qui s'applique :

1. **bord** : à ≤ 0,01 mm (`CONTACT_TOLERANCE_MM`) du bord de départ → `START`, du bord de fin → `END` ;
2. **contact** : face en contact (`classify` → `Contact`, normale selon l'axe) avec une face déjà
   accrochée → même ancre ; itéré jusqu'à point fixe, dans un ordre canonique (tri par `key`) ;
3. **retrait** : à ≤ `EdgeMargin` d'un bord → ce bord (le plus proche ; égalité → `START`) ;
4. **mode** : `FIXED` → `START` (ne bouge pas) ; `PROPORTIONAL` → `RATIO`.

Sur l'axe aligné sur `Thickness`, les deux faces partagent une seule ancre (la plus prioritaire ;
conflit → `START` + `ThicknessKept`) et `RATIO` s'applique au milieu de la pièce. Sur un axe
aligné sur `Length` ou `Width`, deux ancres différentes donnent une cote liée :
`cote = f(fin) − f(début)` avec `f(START) = c`, `f(END) = C − (C₀ − c)`, `f(RATIO) = C × c / C₀`
(`C` = cote de l'ensemble, `C₀` à la liaison, `c` = coordonnée à la liaison, relative à `Origin`).
Les constantes sont figées à la liaison ; « Relier les pièces » les recalcule après une
modification à la main.

**Format des expressions** : `<<Label>>.Cote`, puis `* ratio` (9 décimales au plus), puis
`+ k mm` ou `- k mm` (6 décimales au plus, zéros inutiles retirés, constante nulle omise). Les
expressions visent le **libellé** de l'ensemble (FreeCAD les réécrit au renommage). Le texte
retenu est celui que relit l'`ExpressionEngine` après `setExpression` (normalisation de FreeCAD).

### 4.4 `features/` (J4b′)

#### 4.4.1 Ensemble `Furniture` (`App::FeaturePython`, nom interne `Furniture`, libellé « Ensemble »)

| Propriété | Type | Groupe | Défaut | Édition | Infobulle |
|---|---|---|---|---|---|
| `Width` | `App::PropertyLength` | Ensemble | boîte des membres | modifiable | Largeur de l'ensemble (axe X de son repère). Les pièces liées suivent par leurs expressions. |
| `Depth` | `App::PropertyLength` | Ensemble | idem | modifiable | Profondeur de l'ensemble (axe Y). |
| `Height` | `App::PropertyLength` | Ensemble | idem | modifiable | Hauteur de l'ensemble (axe Z). |
| `Origin` | `App::PropertyVectorDistance` | Ensemble | coin min. de la boîte | lecture seule | Coin de départ de l'ensemble (avant, gauche, bas) dans le repère de son conteneur. |
| `EdgeMargin` | `App::PropertyLength` | Ensemble | 50 mm (Q3) | modifiable | Retrait maximal pour qu'une pièce suive le bord le plus proche. Pris en compte à la prochaine liaison. |
| `Template` | `App::PropertyString` | Ensemble | `""` | lecture seule | Gabarit qui a créé l'ensemble (information seulement). |
| `Version` | `App::PropertyInteger` | Base | 1 | masquée | Version du modèle de données de l'ensemble, utilisée pour migrer les anciens fichiers. |

`execute()` ne construit rien (pas de forme) ; il valide les cotes (`FurnitureBox`) et passe
l'objet en erreur avec un message traduit sinon. `onChanged(Width|Depth|Height)` hors
restauration, annulation et recalcul : avertissement dans la vue rapport pour chaque membre dont
une propriété concernée suit une formule de l'utilisateur (N5), et, si `check_resize` refuse, un
avertissement citant la pièce (Q4). Le proxy n'écrit jamais dans un autre objet.

#### 4.4.2 Propriétés ajoutées aux membres (dynamiques, groupe « Ensemble »)

| Propriété | Type | Défaut | Édition | Infobulle |
|---|---|---|---|---|
| `Furniture` | `App::PropertyLink` | l'ensemble | lecture seule | Ensemble dont la pièce suit les cotes. |
| `PositionMode` | `App::PropertyEnumeration` (`Fixed`, `Proportional`) | `Fixed` | lecture seule (panneau de l'ensemble, `set_position_mode`) | Pièce intérieure quand une cote de l'ensemble change : Fixed, elle ne bouge pas ; Proportional, elle garde sa proportion. Sans effet sur une position pilotée par une formule. |
| `FurnitureBindings` | `App::PropertyMap` | `{}` | masquée | Expressions posées par l'atelier (propriété → texte), pour les distinguer des formules de l'utilisateur. |

Ajoutées à l'entrée dans l'ensemble, retirées à la sortie ; posées sur la **brute** (une pièce
usinée passée à l'API est remplacée par sa `Base`) ou sur le sous-ensemble. `WoodPart` et
`MachinedPart` ne changent pas (aucune `Version` modifiée) : le proxy `Furniture` contrôle ces
propriétés sur ses membres (`InList` filtrée par `Furniture`) à sa réouverture.
`PositionMode` est en lecture seule dans l'éditeur de propriétés : `WoodPart` n'écoute pas ce
changement, qui passe donc par `set_position_mode` (API, panneau) ; celui-ci réécrit les liaisons
de la pièce dans la même transaction. Un script qui écrit la propriété directement ne change rien
avant le prochain « Relier les pièces ».

#### 4.4.3 Lecture des membres et formules de l'utilisateur (`furniture_bindings.py`)

- Bloc d'un membre = `PlacedBlock` de J3 exprimé dans le repère du conteneur commun.
- `driven` = propriétés concernées (`Length`, `Width`, `Placement` et ses sous-chemins) dont
  l'expression actuelle n'est pas celle de `FurnitureBindings`, plus `Placement` si un objet de
  l'atelier Assembly intégré (`Assembly::JointGroup` et ses joints, détectés par `TypeId` et
  `InList`, sans import du module) référence la pièce : c'est la « contrainte » de jv. Détection
  au mieux : un autre mécanisme qui réécrit `Placement` sans expression n'est pas vu (risque R6).
- Écriture : `setExpression(prop, texte)` puis relecture, mise à jour de `FurnitureBindings` ;
  retrait : `setExpression(prop, None)` seulement si le texte actuel est celui enregistré.

#### 4.4.4 API

```python
def make_furniture(objects: Sequence[DocumentObject], label: str = "") -> tuple[DocumentObject, tuple[str, ...]]: ...  # (ensemble, avertissements traduits)
def add_to_furniture(furniture: DocumentObject, objects: Sequence[DocumentObject]) -> tuple[str, ...]: ...
def remove_from_furniture(objects: Sequence[DocumentObject]) -> None: ...
def set_position_mode(obj: DocumentObject, mode: str) -> tuple[str, ...]: ...
def rebind_furniture(furniture: DocumentObject) -> tuple[str, ...]: ...
def resize_furniture(furniture: DocumentObject, *, width: float | None = None, depth: float | None = None, height: float | None = None) -> None: ...  # check_resize puis écriture et recalcul
def furniture_of(obj: DocumentObject) -> DocumentObject | None: ...
```

Sans transaction (les commandes l'ouvrent, comme J3) ; ViewProvider ajouté si `App.GuiUp`.

### 4.5 Recalcul, réouverture, annuler / rétablir

- **Graphe** : ensemble (cotes) → membres (expressions, `Furniture`) → assemblages → pièces
  usinées ; un sous-ensemble se place entre son ensemble et ses membres. Un seul `recompute()`.
- **Aucune écriture pendant le recalcul** : les liaisons sont écrites par l'API, jamais par
  `execute()` ; changer une cote n'écrit rien d'autre que la cote.
- **Réouverture** : proxy sans état, `onDocumentRestored` (aides de `schema.py`), contrôle des
  propriétés de membre ; aucun objet « Touched ».
- **Annuler / rétablir** : les expressions, `FurnitureBindings` et les propriétés de membre sont des
  propriétés ordinaires, restaurées par FreeCAD ; une commande = une transaction.

### 4.6 Affichage, commandes, panneau (J4c)

`ViewProviderFurniture` (chemin figé `freecad.menuiserie.gui.view_providers.furniture`) :
`claimChildren` = membres (pièce usinée à la place de sa brute), sous-ensembles et assemblages
internes, calculés d'après `InList` (affichage seulement, aucun lien du document) ;
`setEdit` → `FurnitureTaskPanel`. Le panneau réutilise `ObjectTaskPanel` (J3e) : transactions,
fermeture forcée, `DeletionWatcher` le temps du panneau seulement.

### 4.7 Gabarit « Caisson » (J4d, ADR 0010)

`carcass_layout(params) -> Layout` (pur) décrit pièces (`PieceSpec` : clé, libellé traduisible,
cotes, `PlacedBlock`, matériau, mode) et assemblages (`JointSpec` : type, hôte, invitée,
paramètres validés de J3). Construction : côtés pleine hauteur et pleine profondeur ; dessus et
dessous entre les côtés, tourillons Ø 8 × 30 enfoncés de 12 dans les côtés (les valeurs
automatiques de J3, 35 mm dont 17,5 dans l'hôte, perceraient un côté de 18) ; fond de 8 logé de
10 dans une feuillure des côtés, du dessus et du dessous ; étagères posées (jeu de 1 mm aux côtés,
1 mm devant le fond), réparties à intervalles égaux, mode `Fixed`. `features/templates.py`
instancie un `Layout` : pièces (`create_wood_part`), assemblages (fabriques J3), ensemble et
liaisons (`create_furniture`) ; aucun objet « gabarit » n'est gardé.

### 4.8 Sécurité

Aucune lecture de fichier ni entrée externe nouvelle. Les expressions sont construites par
l'atelier à partir de nombres validés et du libellé de l'ensemble passé par
`<<…>>` : un libellé contenant `>>` est refusé à la liaison (message) pour ne jamais produire une
expression qui viserait un autre objet. Les valeurs relues (`PositionMode`, `FurnitureBindings`,
cotes) sont contrôlées à la réouverture ; aucun `eval`.

### 4.9 Compatibilité avec les autres ateliers (ADR 0007), Std Part et `App::Link`

- L'Ensemble n'a pas de forme et n'est pas un conteneur : il ne change ni la portée des liens ni
  le placement des pièces. Le meuble se déplace, se tourne, se duplique par **Std Part** et
  **`App::Link`**, outils natifs (N9, N10) ; l'atelier Assembly prend le Std Part comme composant.
- Les pièces restent des `Part::FeaturePython` à forme standard (O13, O14 de J3 inchangés).
- Les liaisons sont des expressions natives, visibles et modifiables par l'utilisateur et lisibles
  par tout outil ; sans l'atelier, le document s'ouvre avec ses formes enregistrées (N14).
- Espace de noms : `Menuiserie::Furniture`, `Menuiserie::HalfLap`, commandes `Menuiserie_Furniture`,
  `Menuiserie_FurnitureAdd`, `Menuiserie_Carcass`, `Menuiserie_HalfLap` ; aucun objet nommé
  « Assembly » ni « Part » ; aucune dépendance ajoutée ; aucun observateur global.

## 5. Découpage en PR

| Lot | Branche | Contenu | Diff estimé hors tests | Critères |
|---|---|---|---|---|
| **J4a** | `feat/ensembles-core` | `core/furniture/` (modèle, règles, liaisons, aperçu), ADR 0008 à 0010 acceptés | ≈ 400 | F1–F12 |
| **J4b′** | `feat/ensembles-document` | `features/furniture.py`, `furniture_bindings.py`, API, CHANGELOG ; livrable par la console | ≈ 380 | N1–N15 |
| **J4c** | `feat/ensembles-panneau` | ViewProvider, deux commandes, panneau, icône, recette manuelle, README « Modifier un meuble » | ≈ 350 | P1–P7 |
| **J4d** | `feat/gabarit-caisson` | `core/templates/`, `features/templates.py`, `make_carcass`, commande et panneau | ≈ 380 | K1–K7 |
| **J4e** | `feat/assemblage-mi-bois` | stratégie, objet, commande du mi-bois (Q6) | ≈ 200 | B1–B4 |

Chaque lot est livrable seul : J4a est une bibliothèque testée sans FreeCAD ; J4b′ atteint le
livrable par la console ; J4c ajoute l'interface ; J4d (après J4b′, indépendant de J4c : sa
commande est dans son propre module) livre le caisson ; J4e ne dépend que de J3 et peut partir
tout de suite (B4 est vérifié dès que J4b′ est fusionné).

## 6. Compatibilité

- **Documents J1 et J3** : aucune migration ; `WoodPart` (`Version` 2), `MachinedPart` et les
  assemblages (`Version` 1) inchangés (N15).
- **Nouveaux objets** : `Furniture` et `HalfLapJoint` naissent en `Version` 1 (contrat de
  l'ADR 0003) ; les propriétés de membre et la valeur d'énumération `PositionMode` entrent dans le
  contrat de persistance (ADR 0009).
- **Document J4 ouvert par un atelier J3** : proxy `Furniture` introuvable signalé par FreeCAD ;
  les expressions restent dans les pièces et s'évaluent (l'objet garde ses propriétés) ; les
  propriétés de membre sont ignorées.
- **J2 (liste de débit)** : lira les brutes comme avant ; regroupement par ensemble possible
  grâce à `Furniture` (prévu en J2).
- **FreeCAD 1.0 et 1.1** : `setExpression` sur `Placement.Base.x`, `App::PropertyMap`,
  `App::PropertyVectorDistance` et ses sous-chemins existent dans les deux ; à vérifier en début
  de J4b′ : normalisation du texte des expressions et réécriture au renommage (R2).

## 7. Risques

| N° | Risque | Effet | Parade |
|---|---|---|---|
| R1 | Les règles automatiques classent mal une pièce (retrait proche d'un bord, pièce posée sans contact). | Pièce qui ne suit pas ou suit le mauvais bord. | Aperçu et colonne « Suit » dans le panneau avant « OK » ; mode par pièce ; formule de l'utilisateur toujours respectée ; « Relier ». |
| R2 | Texte des expressions normalisé ou réécrit par FreeCAD (renommage, copie) différemment selon 1.0 / 1.1. | Liaison de l'atelier prise pour une formule de l'utilisateur. | Texte relu après écriture (§ 4.3) ; le cas défavorable est sûr : la formule est gardée, un avertissement propose « Relier ». Test en début de J4b′ sur les deux versions. |
| R3 | Constantes figées à la liaison : une pièce modifiée à la main ensuite (plateau de 30 → 40) n'est plus cohérente. | Pièces qui se chevauchent après une cote. | `check_resize` le détecte s'il touche un assemblage ; « Relier les pièces » ; documenté dans le README. |
| R4 | Pièce usinée déplacée à la main alors que la brute a un `Placement` lié (report de Q4 de J3). | Déplacement annulé au recalcul suivant. | Refus explicite avec message (N6). |
| R5 | Cote saisie hors panneau qui casse une pièce ou un assemblage. | Objets en erreur. | Q4 ; jamais de forme partielle (J3) ; avertissement ; annulation. |
| R6 | « Contrainte » au sens large : seuls les expressions et les joints de l'atelier Assembly intégré sont détectés. | Une pièce pilotée par un autre addon peut recevoir une liaison. | Documenté ; la liaison reste une expression visible que l'utilisateur peut effacer. |
| R7 | Arbre : un membre réclamé à la fois par l'ensemble et par un Std Part ou une pièce usinée. | Doublons ou ordre étrange dans l'arbre. | `claimChildren` réclame la pièce usinée (qui réclame sa brute) ; vérifié en G et en recette sur 1.0 et 1.1. |
| R8 | Volume de travail : quatre sources d'accroche, sous-ensembles, gabarit. | Lots qui dépassent 400 lignes. | Sous-ensembles et gabarits réduits selon Q2 et Q5 ; J4e détachable (Q6). |

## 8. Hors périmètre

- Usinages croisés et nœuds à trois pièces (**issue #19**) ; un assemblage ne voit toujours que
  les brutes (ADR 0006).
- **J4b** — finition des chants (issue #5) et finitions en relief (issue #7).
- **J2** — liste de débit (**issue #13**), qui reprendra ensembles et gabarits.
- **J5** — publication (TechDraw coté, traductions, Addon Manager).
- Queue d'aronde (Q6), gabarits étagère, cadre, tiroir (Q5), quincaillerie, taquets.
- Pièces non d'équerre avec l'ensemble, cotes d'ensemble autres que les trois axes, ensembles
  répartis entre plusieurs conteneurs, pièces d'un autre atelier membres d'un ensemble,
  `App::Link` **de pièces** à l'intérieur d'un ensemble (le lien d'un Std Part entier est couvert).
- Intégration spécifique à l'atelier Assembly ou à d'autres addons (coexistence seulement).

## 9. Questions pour jv

Une réponse d'un mot suffit ; la recommandation est marquée ★.

**Q1 — Nature de l'Ensemble.** **Cotes** ★ (objet de cotes sans conteneur ; on déplace et duplique
le meuble avec un Std Part et `App::Link`, natifs) / **Conteneur** (groupe à repère propre, comme
un Std Part de l'atelier). ★ parce qu'un conteneur dont les pièces lisent les cotes crée un cycle
de dépendances et refait ce que Std Part fait déjà (ADR 0008).

**Q2 — Ensemble dans un ensemble (caisson dans le bureau) ?** **Oui** ★ (le caisson suit le bureau
et garde ses propres cotes) / **Non** (le gabarit ajoute ses pièces directement au bureau).

**Q3 — Retrait jusqu'auquel une pièce suit le bord le plus proche (joue à 40 mm du fond du
plateau) ?** **0** (contact seulement) / **20** mm / **50** mm ★. Au-delà, la pièce est intérieure
et suit votre règle (par défaut, elle ne bouge pas).

**Q4 — Cote changée dans l'éditeur de propriétés qui casserait une pièce ou un assemblage ?**
**Appliquer** ★ (pièces en erreur, avertissement, annulable ; le panneau, lui, refuse avant) /
**Rétablir** (l'atelier remet l'ancienne valeur, au prix d'une écriture hors recalcul).

**Q5 — Gabarits livrés en J4 ?** **Caisson** ★ / **Caisson+étagère** / **Quatre** (caisson,
étagère, cadre, tiroir).

**Q6 — Assemblages 2 dans J4 ?** **Deux** (mi-bois et queue d'aronde) / **Mi-bois** ★ (queue
d'aronde plus tard : elle demande des solides non parallélépipédiques) / **Aucun**.
