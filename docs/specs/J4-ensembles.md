# [J4] Ensembles, gabarits et assemblages 2 : bureau à cotes globales, caisson en quelques clics

- Jalon : J4 (version cible 0.3.0, à confirmer par jv)
- Statut : **validée** par jv le 2026-10-21 (§ 9 : Q1, Q2, Q4, Q5 recommandations retenues ;
  Q3, Q6 et Q7 réponses de jv intégrées). Reste ouverte **Q8** : la spécification applique sa
  recommandation ★ en attendant.
- Exigences de jv intégrées : modifier facilement un ensemble de pièces (spécification J3, § 8,
  2026-10-20) ; position des pièces intérieures, deux modes, « par défaut elle ne bouge pas »,
  formule respectée avec avertissement (décision de jv du 2026-10-20) ; **chaque distance à un
  bord est fixe ou non, au choix** (Q3, 2026-10-21) ; **la pièce bouge par défaut** (Q7,
  2026-10-21 : toute distance est fixe par défaut, la case « fixe » se décoche) ; **mi-bois, queue d'aronde et onglet à 45°**
  (Q6, 2026-10-21) ; les assemblages de J3 suivent ; compatibilité avec les autres addons
  (ADR 0007), y compris Std Part et `App::Link`
- ADR liés : [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](../adr/0006-piece-brute-et-piece-usinee.md) (accepté),
  [0007 — Compatibilité avec les autres ateliers](../adr/0007-compatibilite-avec-les-autres-ateliers.md) (accepté),
  [0008 — L'Ensemble, objet de cotes hors conteneur](../adr/0008-ensemble-objet-de-cotes.md) (accepté),
  [0009 — Suivi des pièces par expressions natives](../adr/0009-suivi-par-expressions-natives.md) (accepté),
  [0010 — Gabarits générateurs](../adr/0010-gabarits-generateurs.md) (accepté)
- Découpage : sept PR, **J4a → J4b′ → (J4c ∥ J4d)** pour les ensembles, et **J4e ∥ (J4f → J4g)**
  pour les assemblages, qui ne dépendent que de J3 (§ 5). Le prime de J4b′ évite la confusion avec
  **J4b**, la finition des chants (issue #5), qui reste un jalon à part.

## 1. Contexte

Avec J3, le menuisier dessine des pièces et les assemble ; les assemblages suivent les cotes et
les positions des pièces en un recalcul (ADR 0006). Mais pour rendre un bureau plus profond, il
doit changer à la main le plateau, les deux joues, déplacer le voile de fond, ou écrire lui-même
une dizaine d'expressions. Exigence de jv, mot pour mot : « je veux pouvoir modifier facilement un
ensemble de piece; par exemple si j'ai concu un bureau, je veux pouvoir modifier la profondeur de
celui-ci et des toutes les pieces impactés (plateau; caisson) ». Et, sur les distances aux bords
(Q3) : « lorsque je défini une distance, je veux pouvoir indiqué si elle est fix ou non ». Le plan
(§ 7) attend aussi en J4 un caisson paramétrique (« un caisson complet en quelques clics ») et les
assemblages 2 ; jv a choisi (Q6) : « mi bois, queu arronde et 45 ». La liste de débit (J2) vient
après J4 et lira les ensembles, les gabarits et les assemblages.

## 2. Objectif

Le menuisier peut :

1. regrouper des pièces dans un **Ensemble** (« Bureau ») qui porte trois cotes globales
   (`Width`, `Depth`, `Height`) ; changer une cote étire, déplace ou laisse en place chaque pièce,
   **par des expressions FreeCAD natives** visibles dans les pièces ;
2. indiquer, pour **chaque distance** entre une face de pièce et le bord de l'ensemble de son côté
   (gauche, droite, avant, arrière, bas, haut), si elle est **fixe** (la pièce suit ce bord quand la
   cote change) ou **non fixe** (la pièce reste où elle est, ou garde sa proportion si son mode est
   « Proportion »), dans le panneau de l'ensemble comme dans l'éditeur de propriétés. Par défaut,
   toute distance est fixe : **la pièce bouge par défaut** et suit le bord de son côté (Q7) ; le
   menuisier décoche « fixe » là où elle doit rester en place ;
3. garder ses propres formules : une cote ou une position déjà pilotée par une expression ou une
   contrainte n'est jamais remplacée ; la formule s'applique et un **avertissement** le signale ;
4. voir les assemblages de J3 et de J4 (pièces usinées, tenons, tourillons, queues…) **suivre** en
   un recalcul ;
5. créer un **caisson** complet (côtés, dessus, dessous, fond en feuillure, étagères, tourillons)
   par un gabarit, puis le redimensionner comme tout Ensemble, y compris dans un autre ensemble ;
6. relier deux pièces par un **mi-bois**, une **queue d'aronde** traversante ou un **onglet** ;
7. ranger l'ensemble dans un **Std Part**, le dupliquer par **`App::Link`**, le dessiner dans
   TechDraw et l'exporter en STEP, sans que l'atelier gêne les autres outils (ADR 0007).

**Livrable visible** : le bureau de référence (§ 3) passe de 600 à 800 mm de profondeur par une
seule saisie, les joues et le voile suivant le fond par défaut (Q7) ; le caisson de référence est
créé en une commande puis rendu plus haut ; un tiroir simple est assemblé à queues d'aronde, un
cadre à onglets, une croix à mi-bois.

## 3. Critères d'acceptation

Légende : **U** = unitaire sans FreeCAD, **I** = intégration dans `freecadcmd` (1.0 et 1.1),
**G** = interface hors écran, **manuel** = recette décrite dans `docs/recette/J4-scenarios-manuels.md`.
Les lettres des critères sont propres à cette spécification.

**Bureau de référence** (cotes en mm, ensemble « Bureau » dans le document, sans conteneur).
Étendues dans le repère de l'ensemble (X = largeur, Y = profondeur, Z = hauteur) et distances
**fixes par défaut** (F3 ; Q7 : toute distance, sauf sur l'épaisseur où seule la face la plus
proche de son bord l'est) :

| Pièce | Cotes L × l × e | `Placement` (base ; rotation) | X | Y | Z | Fixes par défaut |
|---|---|---|---|---|---|---|
| Plateau P | 1200 × 600 × 30 | (0, 0, 720) ; aucune | [0, 1200] | [0, 600] | [720, 750] | gauche, droite, avant, arrière, haut |
| Joue gauche JG | 720 × 560 × 22 | (22, 0, 0) ; −90° autour de Y (L selon Z, e selon −X) | [0, 22] | [0, 560] | [0, 720] | gauche, avant, arrière, bas, haut |
| Joue droite JD | 720 × 560 × 22 | (1200, 0, 0) ; idem | [1178, 1200] | [0, 560] | [0, 720] | droite, avant, arrière, bas, haut |
| Voile V | 1156 × 400 × 18 | (22, 459, 320) ; +90° autour de X (l selon Z, e selon −Y) | [22, 1178] | [441, 459] | [320, 720] | gauche, droite, arrière, bas, haut |

Assemblages : tourillons JG–V et JD–V (hôte = joue, invitée = voile), valeurs automatiques de
J3 : contact 400 × 18 → 4 tourillons Ø 8 × 35. Les joues sont en retrait de 40 mm à l'arrière :
cette distance est **fixe par défaut** (Q7) : les joues suivent la profondeur sans rien cocher.
Le scénario « reste en place » la **décoche** (`FixedBack` = faux sur JG et JD). Le voile est
intérieur en profondeur (141 mm du fond, 441 mm de l'avant) : sur l'axe de son épaisseur, seule
la face arrière, la plus proche de son bord, est fixe par défaut ; il suit le fond. Cotes de l'ensemble à la création :
1200 × 600 × 750, `Origin` = (0, 0, 0). Tous les membres en mode `Stay` (« Reste en place »).

### J4a — Règles de suivi et liaisons (`core/furniture/`)

| N° | Critère | Test |
|---|---|---|
| F1 | Objets valeur validés à la construction : `FurnitureBox` (trois cotes finies, non booléennes, de `MIN_DIMENSION_MM` à `MAX_DIMENSION_MM`), `Member`, `FollowRule` ; `InteriorMode` a les valeurs stables `Stay`, `Proportional` et `Edge` les valeurs stables `Left`, `Right`, `Front`, `Back`, `Bottom`, `Top` (ordre figé) ; `Member.fixed` est un ensemble d'`Edge` ou `None` (options à calculer). `ValueError` citant le champ ; un cas refusé et un cas limite accepté par règle. | U |
| F2 | `member_spans(member)` : étendue de chaque membre sur X, Y, Z du repère de l'ensemble et axe local aligné (`Length`, `Width`, `Thickness`) par `relative_axes` (J3) ; `edge_distances(member, box)` : distance de chaque face au bord de son côté (gauche = début de X… haut = fin de Z). Bureau : valeurs du tableau ; JG : arrière 40, droite 1178. Un membre tourné de 45° par rapport à l'ensemble est exclu des liaisons avec la notice `NotSquare` (« « Voile » n'est pas d'équerre avec l'ensemble : il ne suit pas ses cotes. »). | U |
| F3 | **Options par défaut** (`default_fixed`, seulement pour un membre dont `fixed` est `None` ; Q7, réponse de jv : « La pièce bouge par défaut ») : **toute distance est fixe**, nulle ou non (1 mm, 40 mm), règle isolée dans `fixed_by_default` ; sur l'axe de `Thickness`, seule la face la plus proche de son bord est fixe (égalité → début), sans notice. Bureau : P fixe à gauche, droite, avant, arrière, haut ; JG à gauche, avant, arrière, bas, haut ; JD à droite, avant, arrière, bas, haut ; V à gauche, droite, arrière, bas, haut. Un membre dont `fixed` est donné garde ses options telles quelles. | U |
| F4 | **Options par défaut, contact** : *sans objet depuis la réponse de jv à Q7* (toute distance est déjà fixe par défaut ; la règle de contact, de proche en proche, est retirée). Résultat indépendant de l'ordre des membres. L'option « non fixe » reste disponible : le menuisier la choisit pièce par pièce. | U |
| F5 | **Distance fixe** (`follow_rules`) : face dont la distance est fixe → elle suit le bord de son côté (`START` pour gauche, avant, bas ; `END` pour droite, arrière, haut). Bureau (options par défaut) : l'arrière de JG suit `END`, sa largeur suit la profondeur. `FixedBack` décoché : son arrière ne bouge pas. | U |
| F6 | **Distance non fixe** : mode `Stay` (défaut) → `START`, la face **ne bouge pas** (dans le repère de l'ensemble) ; mode `Proportional` → la coordonnée garde sa proportion de la cote ; sur un axe non étirable, c'est le **milieu** de la pièce qui la garde. Bureau, V en `Proportional` avec `FixedBack` décoché : milieu à 450 / 600 = 0,75 de la profondeur. Une face fixe garde son bord dans les deux modes. | U |
| F7 | **Épaisseur jamais étirée** : sur l'axe de `Thickness`, une seule règle par pièce : une seule face fixe → elle décide ; deux faces fixes (pièce aussi épaisse que l'ensemble, ou deux cases cochées) → la plus proche de son bord, égalité → `START`, et notice `ThicknessKept` ; aucune → le mode. Une cote d'ensemble ne change jamais une pièce qu'elle ne traverse pas. | U |
| F8 | **Liaisons** (`bindings_for`) : expressions exactes pour le bureau, options par défaut — P : `Length` = `<<Bureau>>.Width`, `Width` = `<<Bureau>>.Depth`, `Placement.Base.z` = `<<Bureau>>.Origin.z + <<Bureau>>.Height - 30 mm` ; JG et JD : `Length` = `<<Bureau>>.Height - 30 mm`, `Width` = `<<Bureau>>.Depth - 40 mm` ; JD : `Placement.Base.x` = `<<Bureau>>.Origin.x + <<Bureau>>.Width` ; V : `Length` = `<<Bureau>>.Width - 44 mm`, `Width` = `<<Bureau>>.Height - 350 mm`, `Placement.Base.y` = `<<Bureau>>.Origin.y + <<Bureau>>.Depth - 141 mm` ; V avec `FixedBack` décoché : aucune sur Y en `Stay`, `Placement.Base.y` = `<<Bureau>>.Origin.y + <<Bureau>>.Depth * 0.75 + 9 mm` en `Proportional`. `FixedBack` décoché sur JG et JD : mêmes liaisons, sauf `Width` de JG et JD, absente. Les positions (`Placement.Base`, `Origin` d'un sous-ensemble) sont écrites **relativement à `<<Ensemble>>.Origin`** ; la coordonnée liée est celle de l'origine locale (début ou fin de l'étendue selon le signe de l'axe). Nombres : ratio à 9 décimales, constante à 6, sans zéros inutiles, constante nulle omise. Aucune liaison qui ne changerait rien (`START` des deux côtés), sauf pour un ensemble lui-même membre d'un autre (`nested`) : toutes ses positions suivent son `Origin`. | U |
| F9 | **Formules de l'utilisateur** : une propriété listée dans `Member.driven` (expression ou contrainte) ne reçoit aucune liaison, quelle que soit l'option fixe ; notice `UserFormula` (avertissement) citant pièce et propriété, seulement pour une propriété que l'atelier lie (`Length`, `Width`, `Placement` d'une pièce ; `Width`, `Depth`, `Height`, `Origin` d'un sous-ensemble : pas `Thickness` pilotée par une feuille de calcul). Une liaison dont le texte enregistré diffère de l'expression actuelle est traitée comme une formule de l'utilisateur ; une liaison **effacée** par l'utilisateur ne l'est pas : « Relier les pièces » la remet. | U |
| F10 | **Aperçu et refus** (`predict`, `check_resize`), bureau aux options par défaut : Depth → 800 donne P 1200 × 800, JG/JD l = 760, V à Y ∈ [641, 659] (il suit le fond) ; V `FixedBack` décoché : inchangé (`Stay`) ou Y ∈ [591, 609] (`Proportional`) ; JG/JD `FixedBack` décoché : inchangées (l = 560). Height → 800 : P en z = 770, V l = 450. Refus (`FurnitureError`, gabarit traduit) : Depth → 30 (« « Joue gauche » deviendrait trop petite : Width = −10 mm ») ; Height → 350,05 (V l = 0,05 < 0,1) ; une paire d'assemblage donnée qui changerait de classe (`Contact` → `Separated`, `Overlap` → autre). Notice `OutsideBox` (avertissement, pas un refus) pour une pièce non fixe qui dépasserait de l'ensemble (`FixedBack` décoché sur JG et JD, Depth → 500 : JG et JD). | U |
| F11 | **Sous-ensemble membre** (Q2 : Oui) : un `FurnitureBox` membre est une boîte dont les trois cotes sont étirables et qui porte les mêmes six options ; ses liaisons portent sur `Origin.x/y/z`, `Width`, `Depth`, `Height`. Un ensemble ne peut pas être membre de lui-même ni d'un de ses membres (`FurnitureError`). | U |
| F12 | `core/` n'importe ni FreeCAD ni Qt ; couverture de `core/` ≥ 90 % ; aucun module > 400 lignes. | U |

**Notes de réalisation de J4a** (dev, 2026-10-21 ; décisions les plus simples cohérentes avec les
ADR, à confirmer par l'architecte) :

1. **Q7** (réponse de jv : « La pièce bouge par défaut ») dans une seule fonction,
   `fixed_by_default(distance)` de `core/furniture/_defaults.py`, vraie pour toute distance. Sur
   l'axe de l'épaisseur, seule la face la plus proche de son bord est fixe par défaut : la pièce
   n'y est jamais étirée, et deux cases cochées d'office donneraient `ThicknessKept` pour chaque
   pièce. La règle de contact (F4) est retirée.
2. **Repère** : `Member.block` et `Member.origin` sont relatifs à l'`Origin` de l'ensemble ; les
   positions liées s'écrivent `<<Ensemble>>.Origin.x + …` (relecture de la PR #29, vérifié sur
   FreeCAD 1.0 et 1.1). `bindings_for(…, nested=True)` lie aussi les positions qui ne bougent pas
   avec la cote (`<<Caisson>>.Origin.x + 22 mm`) : à passer en J4b′ pour un ensemble lui-même
   membre d'un autre, dont l'`Origin` peut bouger ; ses membres sont alors reliés à son entrée et
   à sa sortie du parent.
3. **J4b′** : `check_resize` devra descendre dans les sous-ensembles (il ne contrôle aujourd'hui
   que les membres directs) ; le test de relecture R2 devra couvrir les libellés contenant `'` et
   `"`, que FreeCAD réécrit en `\'` et `\"`.
4. **Signatures** (§ 4.3 mis à jour) : `member_spans(member)` sans la boîte, qui ne sert pas,
   renvoie des `Span` (`lo`, `hi`, `local`, `reversed`) ; `Member` reçoit `label` (nom cité dans
   les messages) et des valeurs par défaut ; `Notice` = (`kind` : `NoticeKind`, `params`), avec
   `template` et `message` en propriétés ; `predict` renvoie des `Member` (l'`Origin` d'un
   sous-ensemble y figure). Aides ajoutées : `with_default_options`, `driven_properties` (F9 :
   texte enregistré ≠ expression actuelle), `is_driven` (`Placement` couvre ses sous-chemins),
   `check_membership` (F11 : cycle d'ensembles), `label_reference`, `expression_text`,
   `bound_by_workshop` (F9 : `UserFormula` seulement pour une propriété que l'atelier lie).
5. **Nombres** : ratio à 9 décimales, constante à 6 (§ 4.3, plus précis que F8).
6. **Libellé** : refusé s'il contient `>` (pas seulement `>>` : « Bureau <2> » donnerait
   `<<Bureau <2>>>`, lu `<<Bureau <2>>`), `\` (échappement de FreeCAD dans `<<…>>` : `Bur\'eau`
   vise `Bur'eau`, `a\` est illisible) ou un caractère invisible (§ 4.9).
7. **`check_resize`** renvoie aussi `UserFormula` pour une propriété pilotée sur un axe qui change
   (N5 n'a plus qu'à traduire) et refuse une cote qui dépasserait 20 000 mm (« trop grande »).

### J4b′ — L'objet Ensemble dans le document (`features/`, `api.py`)

| N° | Critère | Test |
|---|---|---|
| N1 | `make_furniture([P, JG, JD, V], label="Bureau")` (pièces brutes ou usinées) : un objet `Furniture`, cotes 1200 × 600 × 750, `Origin` (0, 0, 0) ; chaque brute reçoit `Furniture`, `PositionMode` = `Stay`, les six options `Fixed…` aux valeurs par défaut du tableau de référence et `FurnitureBindings` ; expressions de F8 (options par défaut) dans les `ExpressionEngine` ; après `recompute()` les formes et volumes sont inchangés et aucun objet n'est « Touched ». | I |
| N2 | Chaque propriété des tableaux du § 4.4 existe avec type, groupe, infobulle, défaut et mode d'édition indiqués ; `WoodPart` garde `Version` = 2 ; une pièce hors ensemble n'a aucune propriété ajoutée. | I |
| N3 | **Le bureau suit** (options par défaut, Q7) : `Depth` = 800 → un recompute → P 1200 × 800 × 30, JG/JD 720 × 760 × 22, V à Y ∈ [641, 659] ; `Height` = 800 → P en z = 770, joues de 770, V de 1156 × 450 et **5** tourillons de chaque côté ; `Width` = 1400 → P de 1400, JD en x ∈ [1378, 1400], V de 1356. Avec `set_member_options(JG, fixed={"Back": False})`, idem JD, `Depth` = 800 → P de 800, joues inchangées (560). Tout valide, aucun « Touched ». | I |
| N4 | **Option dans l'éditeur de propriétés** : dans une transaction, `JG.FixedBack = False` → la liaison `Width` = `<<Bureau>>.Depth - 40 mm` de JG est retirée (seulement JG), `FurnitureBindings` mis à jour, JG reste où elle est ; `undo()` rétablit option et liaison ensemble ; `JG.FixedBack = True` la repose. Même chose pour `PositionMode` = `Proportional` sur V, `FixedBack` décoché : `Depth` = 800 → V à Y ∈ [591, 609] ; retour à `Stay` → liaison Y supprimée, V reste où il est. Rien n'est réécrit à la réouverture ni pendant `undo()` / `redo()`. | I |
| N5 | **Formule de l'utilisateur** (décision de jv) : V porte `Placement.Base.y` = `<<Bureau>>.Depth - 141 mm` avant `make_furniture` → l'expression est gardée, la liste renvoyée et la vue rapport contiennent l'avertissement `UserFormula` ; `Depth` = 800 → `Placement.Base.y` de V = 659 (la formule s'applique) et un avertissement cite V ; changer son mode ou cocher `FixedBack` ne touche pas cette propriété (avertissement). Même règle pour une pièce placée par une contrainte de l'atelier Assembly (§ 4.4.3). | I |
| N6 | **Assemblages J3** : les pièces usinées et leurs assemblages restent valides après chaque changement de N3, valeurs automatiques recalculées (nombre de tourillons de N3), en un seul recompute ; les liaisons sont posées sur la **brute** ; déplacer la pièce usinée d'une brute dont `Placement` est lié est refusé avec un message (aucune écriture perdue en silence). | I |
| N7 | `resize_furniture(bureau, depth=30)` (options par défaut) → `ValueError` traduite citant JG, rien n'est modifié (cotes, expressions, aucune transaction ouverte). Cote saisie dans l'éditeur de propriétés qui casse une pièce (Q4 : appliquer) : la cote est appliquée, pièces ou assemblages en erreur sans forme partielle, avertissement dans la vue rapport, `undo()` rétablit tout. | I |
| N8 | `add_to_furniture(bureau, objets)` et `remove_from_furniture(objets)` : ajout = options par défaut (F3, F4) et liaisons calculées sur la géométrie actuelle, sans toucher aux options des membres déjà présents ; retrait = suppression des **seules** liaisons de l'atelier (texte identique à `FurnitureBindings`) et des propriétés ajoutées, géométrie inchangée. Refus avant modification (`TypeError`/`ValueError` traduites) : objet qui n'est ni pièce ni ensemble, membre d'un autre ensemble, conteneur (`getParentGeoFeatureGroup`) différent de celui de l'ensemble, autre document. `rebind_furniture(bureau)` recalcule toutes les liaisons de l'atelier d'après la géométrie actuelle **et les options enregistrées** (il ne les remet pas aux valeurs par défaut). | I |
| N9 | **Std Part** : bureau et pièces dans un `App::Part` tourné de 30° autour de Z et déplacé → N3 donne les mêmes cotes (repère du conteneur) ; déplacer le Std Part déplace le bureau sans toucher aux liaisons. | I |
| N10 | **`App::Link`** : un lien vers ce Std Part suit le redimensionnement de l'original (`Part.getShape(lien)` : même volume que l'original, à 1e-6 près relatif) ; « Édition › Dupliquer la sélection » du Std Part donne un second bureau indépendant dont les liaisons visent la copie de l'ensemble (sinon : avertissement `UserFormula` et `rebind_furniture` les rétablit). | I |
| N11 | **Sous-ensemble** (Q2 : Oui) : un ensemble « Caisson » membre du bureau, en retrait de 40 mm à l'arrière (`FixedBack` fixe par défaut), suit `Depth` (`<<Bureau>>.Depth - 40 mm`) et ses propres pièces suivent le caisson, en un recompute ; un cycle d'ensembles est refusé. | I |
| N12 | Enregistrer, fermer, rouvrir : propriétés, options, expressions et `FurnitureBindings` identiques, aucun « Touched » ; proxy `freecad.menuiserie.features.furniture.Furniture`, `dumps()` = `None`, `Version` = 1. Réouverture contrôlée (ADR 0003, aides de `schema.py`) : `Version` absente, plus récente ou mal typée ; propriété de membre mal typée (`PositionMode` en `App::PropertyString`, `FixedTop` en `App::PropertyInteger`) supprimée avec avertissement et recréée (`Stay` ; option à sa valeur par défaut F3–F4), sans réécrire les liaisons. | I |
| N13 | Annuler / rétablir : création, ajout, retrait, changement de mode ou d'option, redimensionnement = **une** entrée chacun ; `undo()` restaure cotes, options, expressions et propriétés de membre. | I |
| N14 | **Compatibilité (ADR 0007)** : le bureau dans un Std Part sert de source à une vue TechDraw qui se recalcule sans erreur ; le Std Part s'exporte en STEP et se réimporte avec le même volume ; document ouvert dans un `freecadcmd` sans l'atelier : il s'ouvre, formes valides de même volume. Inventaire : type `Menuiserie::Furniture`, commandes `Menuiserie_…`, aucune dépendance d'exécution, aucun observateur global. | I (TechDraw : ignoré si non importable, alors G) |
| N15 | Les documents J1 et J3 s'ouvrent sans changement (aucune propriété ajoutée, rien de « Touched ») ; `record_of(brute)` inchangé pour un membre. | I |

**Notes de réalisation de J4b′** (dev, 2026-10-21 ; décisions les plus simples cohérentes avec
les ADR, à confirmer par l'architecte) :

1. **Modules** : `features/furniture.py` (proxy, propriétés de l'ensemble et des membres,
   `create_furniture`), `furniture_bindings.py` (lecture des membres, liaisons,
   `member_option_changed`, contrôle descendant), `furniture_members.py` (fabrique et gestion
   des membres, refus avant modification) et `furniture_restore.py` (réouverture des propriétés
   de membre) ; l'API est un bloc séparé de `api.py`.
2. **Liaison reconnue au libellé près** (R2, N10) : `same_binding` (ajouté à la façade de
   `core.furniture`) compare l'expression actuelle au texte de `FurnitureBindings` en ignorant
   le libellé visé dans `<<…>>`. Renommer l'ensemble (FreeCAD réécrit `<<Bureau>>`, `'` et `"`
   devenant `\'` et `\"`) ou le copier ne transforme donc pas ses liaisons en formules de
   l'utilisateur, et « Relier » rétablit une liaison qui vise encore l'original. F9 est précisé
   en ce sens.
3. **Réouverture** (N12) : les propriétés de membre sont contrôlées par le
   `onDocumentRestored` **du membre** (`WoodPart`, ou `Furniture` pour un sous-ensemble), pas
   par celui de l'ensemble : FreeCAD 1.0 et 1.1 quittent (code 1, sans message) quand on
   supprime une propriété d'un autre objet pendant la restauration. `WoodPart` garde
   `Version` = 2. Après une réparation, les objets sont à recalculer, comme en J1 et J3.
4. **Cote saisie dans l'éditeur** (Q4, N7) : `onBeforeChange` lit les cotes d'avant (attribut
   transitoire `previous_box`), `onChanged` les contrôle (`check_resize`, sous-ensembles
   compris) et avertit ; rien pendant une restauration, une annulation, un recalcul, une
   écriture de l'atelier (drapeau transitoire du proxy) ni pour une cote pilotée par une
   expression.
5. **Contrôle descendant** : chaque niveau contrôle ses membres et ses propres paires
   d'assemblage ; une paire entre une pièce de l'ensemble et une pièce d'un sous-ensemble n'est
   pas contrôlée.
6. **N3, joues qui restent en place** : décocher `FixedBack` des seules joues fait perdre ses
   tourillons au voile, qui suit le fond (refus de `resize_furniture`, avertissement dans
   l'éditeur) ; « tout valide » demande de décocher aussi `FixedBack` du voile.
7. **N5** : la formule de l'utilisateur posée avant `make_furniture` vise le plateau
   (`<<Plateau>>.Width - 141 mm`), l'ensemble n'existant pas encore. Contrainte de l'atelier
   Assembly : joint d'un `Assembly::JointGroup` qui cite la brute **ou sa pièce usinée**.
8. **N6** : déplacer une pièce usinée dont la brute a une expression sur son `Placement`
   (liaison ou formule) est refusé avec un avertissement dans la vue rapport ; la brute ne
   bouge pas.
9. **API** : les avertissements sont renvoyés **et** écrits dans la vue rapport ;
   `resize_furniture` renvoie `None` (avertissements dans la vue rapport) et refuse une cote
   pilotée par une expression (sous-ensemble). `remove_from_furniture` refuse, avant toute
   modification, un objet qui n'est membre d'aucun ensemble. `add_to_furniture` ne change pas
   les cotes de l'ensemble. Le libellé par défaut est « Ensemble » ; FreeCAD peut le rendre
   unique, les liaisons visent le libellé obtenu. Un ensemble qui entre dans un autre est relié
   à nouveau (`nested`).
10. **N10** : « Dupliquer la sélection » est reproduit dans `freecadcmd` par
    `doc.copyObject([std_part], True)`, qui fait viser la copie par les expressions copiées.
    **N14** : l'export STEP d'un Std Part contient aussi les brutes masquées ; le volume
    réimporté est comparé à la somme des formes du Std Part.
11. **B5** (J4e) est couvert ici : croix à mi-bois en ensemble, traverse invitée en
    `Proportional` sans distance fixe à gauche ni à droite ; `Width` 600 → 800 élargit
    l'invitée à 80 mm et recalcule les deux entailles en un recompute.
12. **D7** (J4f) est couvert ici aussi : tiroir à queues d'aronde (façade à plat, côté
    debout) en ensemble ; la hauteur du tiroir (cote `Depth` de l'ensemble) passe de 150 à
    200 mm par `resize_furniture` → 4 queues automatiques, un recompute, tout valide.
13. **Suppression de l'ensemble** (relecture de la PR #32) : `Furniture.unsetupObject`,
    appelé par `removeObject` dans FreeCAD 1.0 et 1.1 (interface comprise) et annulable,
    retire les liaisons de l'atelier de ses membres : aucune expression ne reste en erreur.
    Les membres gardent leurs propriétés de membre (**orphelins**, `Furniture` vide) ;
    `make_furniture` et `add_to_furniture` les acceptent et réécrivent `Furniture`, le mode, les
    options et `FurnitureBindings` ; `remove_from_furniture` les accepte aussi. À la réouverture,
    toute propriété de membre manquante est recréée (options selon F3 pour le membre).

### J4c — Affichage, commandes et panneau de l'Ensemble (`gui/`)

| N° | Critère | Test |
|---|---|---|
| P1 | Commandes `Menuiserie_Furniture` (« Ensemble », active si au moins une pièce est sélectionnée et aucun panneau ouvert) et `Menuiserie_FurnitureAdd` (« Ajouter à l'ensemble », pièces + un ensemble sélectionnés) dans la barre d'outils et le menu ; icône `Menuiserie_Furniture.svg` générée par `tools/generer_icones.py` ; une entrée d'annulation par commande. | G |
| P2 | `ViewProviderFurniture` : l'ensemble apparaît dans l'arbre avec ses membres en enfants (pièce usinée à la place de sa brute, sous-ensembles, assemblages dont les deux pièces sont membres) ; double-clic → panneau. Supprimer l'ensemble dans l'interface retire d'abord les liaisons de l'atelier et les propriétés de membre (`onDelete`, même transaction) : aucune expression orpheline. | G |
| P3 | Panneau : trois champs de cotes ; liste des membres avec une colonne « Position » (`Stay` / `Proportional`, traduits « Reste en place » / « Proportion ») et une colonne « Suit » (« étirée », « déplacée », « fixe », « proportion », « formule », « pas d'équerre ») ; pour le membre choisi, **six lignes « distance au bord »** (gauche, droite, avant, arrière, bas, haut) : la distance en mm, modifiable (déplace la pièce, ou change sa cote si la face opposée est conservée), et une case **« fixe »** ; bouton « Relier les pièces ». Saisir une distance ne change pas la case « fixe ». Chaque saisie est prévisualisée ; « OK » = une entrée « Modifier l'ensemble » ; « Annuler » rétablit tout. | G |
| P4 | Un refus de `check_resize` s'affiche sous les champs (message traduit) et désactive « OK » ; les avertissements `UserFormula`, `NotSquare`, `ThicknessKept`, `OutsideBox` s'affichent dans le panneau et la vue rapport. | G |
| P5 | Cote d'ensemble pilotée par une expression (sous-ensemble) : champ inactif, jamais écrit (règle C6 de J1). Distance d'une face pilotée par une formule de l'utilisateur : champ et case inactifs, infobulle « formule ». | G |
| P6 | Aucun observateur global laissé en place ; aucune préférence hors de `Mod/Menuiserie` ; chaînes traduisibles ; `from PySide import …` seulement. | G + revue |
| P7 | Scénario du livrable (bureau dessiné à la main, Ensemble, profondeur 600 → 800 (les joues suivent par défaut), « fixe » décoché puis recoché à l'arrière des joues, voile en proportion, formule de l'utilisateur, annuler, rétablir, enregistrer, rouvrir, Std Part + `App::Link`, vue TechDraw) sur FreeCAD 1.0 et 1.1 ; coexistence avec l'atelier Assembly intégré (le Std Part sert de composant) ; captures dans la PR. | manuel |

### J4d — Gabarit « Caisson » (`core/templates/`, `features/templates.py`, `gui/`)

Q5 : seul le caisson est livré en J4. **Caisson de référence** : 600 × 400 × 720 (L × P × H),
panneaux de 18 en `cp-bouleau`, fond de 8 logé en feuillure de 10, une étagère.

| N° | Critère | Test |
|---|---|---|
| K1 | `carcass_layout(CarcassParams)` (pur) renvoie pièces et assemblages : côtés 720 × 400 × 18 (x ∈ [0, 18] et [582, 600]) ; dessus et dessous 564 × 400 × 18 entre les côtés ; fond 704 × 584 × 8 à y ∈ [392, 400], x ∈ [8, 592], z ∈ [8, 712] ; étagère 562 × 391 × 18 à x ∈ [19, 581], y ∈ [0, 391], z ∈ [351, 369] ; 4 tourillons (côté hôte, dessus/dessous invité, Ø 8, longueur 30, profondeur dans l'hôte 12) ; 4 feuillures (hôte = côté, dessus, dessous ; invité = fond) ; étagère sans assemblage, mode `Stay`. **Options explicites** (`PieceSpec.fixed`, jamais celles par défaut) : côtés, dessus et dessous fixes sur les bords qu'ils touchent et du côté des pièces qu'ils touchent ; fond fixe sur ses six bords (retraits de 8 mm conservés) ; étagère fixe à gauche, à droite, à l'avant et à l'arrière (jeux de 1 mm conservés), non fixe en bas et en haut. | U |
| K2 | `CarcassParams` validé : cotes de F1 ; épaisseur > 0 et < moitié de la plus petite cote ; fond plus mince que les panneaux ; feuillure ≤ épaisseur ; 0 à 10 étagères réparties à intervalles égaux ; identifiants de matériaux connus. `ValueError` citant le champ. | U |
| K3 | `make_carcass(doc, params)` : en un recompute, 6 pièces, 4 assemblages tourillons, 4 feuillures, 5 pièces usinées (l'étagère reste une brute), un Ensemble 600 × 400 × 720 (`Template` = `Carcass`), les options de K1 et leurs liaisons ; tout valide ; 4 tourillons par jonction. | I |
| K4 | Le caisson suit : `Depth` = 500 → côtés, dessus, dessous de 500, fond à y ∈ [492, 500], étagère de 491, **5** tourillons par jonction ; `Height` = 800 → côtés de 800, dessus en z ∈ [782, 800], étagère **immobile** en z ∈ [351, 369] (`Stay`) ou en z ∈ [391, 409] (`Proportional`). | I |
| K5 | `make_carcass(doc, params, furniture=bureau)` : le caisson devient un **sous-ensemble** du bureau (Q2), avec les options par défaut F3–F4 vis-à-vis du bureau. | I |
| K6 | Commande `Menuiserie_Carcass` (« Caisson », icône existante) : panneau de paramètres, aperçu, « OK » = une entrée « Créer un caisson » ; « Annuler » ne laisse aucun objet. | G |
| K7 | Recette du livrable du plan : « un caisson complet en quelques clics », redimensionné, vue TechDraw. | manuel |

**Notes de réalisation de J4d** (dev, 2026-10-21 ; décisions les plus simples cohérentes avec
les ADR, à confirmer par l'architecte) :

1. **Fond (K1)** : fixe sur **cinq** bords, gauche, droite, bas, haut et arrière, pas à
   l'avant. Les retraits de 8 mm sur ses quatre chants sont conservés. Sur l'axe de son
   épaisseur, une seule face est fixe (F7) : deux faces fixes donneraient l'avertissement
   `ThicknessKept` à chaque création. Côtés, dessus et dessous sont fixes sur toutes leurs
   distances, sauf la face intérieure de leur épaisseur. Étagère : fixe à gauche, à droite, à
   l'avant et à l'arrière, mode `Stay`. `Proportional` se règle ensuite avec `set_member_options`.
2. **`CarcassParams`** (`core/templates/carcass.py`) : `width`, `depth`, `height`,
   `thickness`, `back_thickness`, `rabbet_depth`, `shelf_count`, `material_id` et
   `back_material_id` (les deux en `cp-bouleau` par défaut), `joinery` et `origin` (coin
   avant gauche bas, `Vec3`, pour placer un caisson dans un bureau, K5). Chaque refus cite le
   champ (`CarcassError`, gabarit traduisible). Les identifiants de matériaux sont contrôlés
   par `check_materials(params, ids)`, une fonction pure à qui `features` passe les
   identifiants de la bibliothèque, avant toute création. Les étagères (0 à 10) sont refusées
   si elles ne tiennent pas (intervalle nul ou étagère de moins de 1 mm). Les intervalles sont
   égaux entre le dessous, les étagères et le dessus.
3. **Type d'assemblage** (`CarcassJoinery`) : `Dowels` (par défaut, K1) ou `None` (pièces
   aboutées, à visser ou à coller). Le fond est toujours en feuillure filante. La
   rainure-languette a été écartée : la languette du dessus traverserait la feuillure du fond.
   Règle des tourillons pour toute épaisseur `e` : diamètre du commerce d'au plus `e/2`,
   profondeur dans le côté `round(2e/3)`, longueur = cette profondeur + `e`. Pour 18 mm, cela
   donne Ø 8 × 30, enfoncés de 12 dans le côté. Le nombre reste automatique : 4 pour 400 mm,
   5 pour 500 mm. Avec des tourillons, il faut des panneaux d'au moins 12 mm.
4. **Modules** : la commande est dans `gui/commands/carcass.py` et le panneau dans
   `gui/task_panels/carcass.py`, et non dans `gui/commands/furniture.py`, pour ne pas toucher
   aux fichiers de J4c, développé en parallèle. `features/templates.py` contient `build_layout`
   (le constructeur unique) et `build_carcass`. L'entrée des pièces avec des options données
   passe par `furniture_members.join_with_options`, avec les mêmes refus que
   `add_to_furniture`.
5. **API** : `make_carcass(doc=None, params=None, *, furniture=None, **champs)` renvoie
   `(ensemble, avertissements)`, comme `make_furniture`. Elle n'ouvre aucune transaction et ne
   lance qu'un seul recalcul. Avec `furniture`, le caisson est créé dans le conteneur de
   l'ensemble parent, puis il y entre avec les options par défaut (F3).
6. **Panneau (K6)** : chaque saisie abandonne la transaction « Créer un caisson », ce qui
   retire l'aperçu précédent, puis la rouvre et recrée le caisson. Il n'y a donc jamais qu'un
   caisson et qu'une transaction. Des paramètres refusés s'affichent sous les champs, rien n'est
   créé et « OK » laisse le panneau ouvert. La commande ne prend pas d'ensemble parent dans la
   sélection : le cas du sous-ensemble (K5) passe par l'API.
7. **À reprendre lors de la fusion de J4c** : `make_carcass` pose les ViewProviders des
   pièces, des pièces usinées et des assemblages, mais pas celui de l'ensemble
   (`ViewProviderFurniture`, livré par J4c). Il faudra l'ajouter au même endroit que pour
   `make_furniture`.
8. Toutes les étagères ont le libellé « Étagère », que FreeCAD rend unique (« Étagère001 »).
   L'icône `Menuiserie_Carcass.svg`, déjà produite par `tools/generer_icones.py`, ne change pas.

### Assemblages 2 : règles communes à J4e, J4f, J4g

Chaque assemblage est une stratégie du registre de J3 (`JointKind`, `strategy_for`) et un proxy
`JointFeature` (Template Method de `features/joints/base.py`), avec ses paramètres en objet valeur
`PARAMS` de `core` (0 = automatique, comme en J3, valeur effective affichée par le panneau
générique de J3e via `resolve`). Création par une fabrique de `features/joints/factories.py`
(`create_joint`), refus avant toute création ; pièce usinée de chaque brute créée si besoin ;
réouverture, annulation et compatibilité comme O8, O10, O13 et O14 de J3 ; bouton « Inverser »
du panneau J3e pour échanger les rôles. Les critères ci-dessous ne répètent pas ces points ; chaque
lot a un test d'intégration qui les couvre pour son type.

### J4e — Mi-bois (`core/joints/half_lap.py`, `features/joints/half_lap.py`)

| N° | Critère | Test |
|---|---|---|
| B1 | `HalfLapParams(depth=0.0, flip_side=False)` validé (J3 : longueur ≥ 0, booléen). `HalfLapStrategy` : les pièces se **chevauchent** (`Overlap`) ; leurs axes d'épaisseur sont parallèles ; épaisseurs égales et faces à fleur (± 0,01 mm) ; la boîte commune couvre toute l'épaisseur. L'hôte perd la partie haute (+Z local) de la boîte commune sur `depth`, l'invitée la partie basse sur `e − depth` ; `depth` = 0 → automatique, `mm_round(e / 2)` ; `flip_side` inverse haut et bas. Croix de deux traverses 600 × 60 × 22 → entailles 60 × 60 × 11 ; angle de deux traverses 400 × 50 × 19 qui se chevauchent de 50 × 50 au bout → hôte 50 × 50 × 10, invitée 50 × 50 × 9. | U |
| B2 | Refus (`JointError`, gabarit traduit) : pièces en contact ou écartées (« Mi-bois : dessinez les deux pièces qui se croisent ; elles doivent se chevaucher. ») ; épaisseurs différentes ou pas à fleur (« Mi-bois : les deux pièces doivent avoir la même épaisseur et être à fleur. ») ; `depth` ≥ e ; pièces pas d'équerre (M1 de J3). | U |
| B3 | Proxy `freecad.menuiserie.features.joints.half_lap.HalfLapJoint`, type `Menuiserie::HalfLap`, nom interne `HalfLap`, libellé « Mi-bois » ; propriétés `Depth` (`App::PropertyLength`, groupe « Mi-bois », « Profondeur de l'entaille de la pièce hôte ; 0 = moitié de l'épaisseur. ») et `FlipSide` (`App::PropertyBool`, « Entaille de l'hôte par-dessous. ») ; `Version` = 1. Croix de B1 : pièces usinées valides, un solide chacune, volume = brute − 39 600 mm³. | I |
| B4 | Commande `Menuiserie_HalfLap` (« Mi-bois », icône existante) dans la famille de J3d ; panneau J3e générique (profondeur effective affichée). | G |
| B5 | Membres d'un Ensemble : la croix d'un cadre suit `Width` (entailles recalculées, un recompute). | I |

Précisions du dev (J4e, 2026-10-21), décisions les plus simples là où la spécification se tait :

- Axes d'épaisseur non parallèles (une pièce sur chant) : même refus que des épaisseurs
  différentes (« Mi-bois : les deux pièces doivent avoir la même épaisseur et être à fleur. »).
- `depth` ≥ e (saisie ou automatique) : « Mi-bois : entaille de {depth} mm pour des pièces de
  {thickness} mm ; elle doit être moins profonde que l'épaisseur. » ; `e` est l'épaisseur de
  l'hôte.
- Faces à fleur à 0,01 mm près : l'entaille de l'invitée va jusqu'à sa propre face, jamais de
  peau résiduelle ; les deux entailles se rejoignent au même niveau.
- `HalfLapValues(depth, guest_depth, host_cut, guest_cut)` : le panneau affiche `depth` ; les
  enlèvements sont exacts (pas de `CUT_OVERRUN_MM`, réservé aux prismes de J4f), comme la
  feuillure de J3.
- Rôles : à épaisseur égale, `guess_roles` garde l'ordre de sélection ; la première pièce
  sélectionnée est l'hôte, entaillée par-dessus (infobulle de la commande).
- Libellés du panneau : « Profondeur de l'entaille » (case « Auto ») et « Entaille de l'hôte
  par-dessous ». Icône existante inchangée (`tools/generer_icones.py` relancé, aucun écart).
- B5 attend J4b′ (Ensemble) : non couvert par ce lot.

### J4f — Queue d'aronde traversante (`core/geometry.py` `Prism`, `core/joints/dovetail.py`, `features/joints/dovetail.py`)

Pièce **à queues** = invitée (côté de tiroir), pièce **à griffes** = hôte (façade, ici traversante).
Notations : `W` = largeur du contact (selon la largeur de l'invitée), `e` = épaisseur de l'invitée,
`L` = profondeur de l'hôte (son épaisseur, axe normal au contact), pente « 1 : n ».

| N° | Critère | Test |
|---|---|---|
| D1 | `Prism` (core/geometry) : polygone plan d'au moins 3 sommets distincts, non alignés, sans auto-intersection, extrudé d'un vecteur non nul hors de son plan ; `moved(prism, transform)` le transporte ; `Solid` = `Box \| Cylinder \| Prism`. `ValueError` sinon. | U |
| D2 | `DovetailParams(tail_count=0, pin_width=0.0, slope=0.0)` validé : `count_param`, `length_param`, et `ratio_param` nouveau (`ParamKind.RATIO` : 0 ou 2 ≤ n ≤ 20). Automatiques : `tail_count` = max(1, ⌊W / (3 e) + 0,5⌋) ; `pin_width` (largeur des griffes au plus étroit, sur la face extérieure de l'hôte) = `mm_round(L / 3)` ; `slope` = 6 (pente 1:6). | U |
| D3 | `DovetailStrategy` : contact par le **bout** de l'invitée (`contact_frame(…, end_only=True)` de J3) ; le bout de l'hôte arrive à fleur de la face extérieure de l'invitée (± 0,01 mm). Largeur des queues côté pointe `t = (W − (n + 1) p) / n`, côté épaulement `b = t − 2 L / slope` ; queue i : pointe de `p + i (t + p)` à `+ t`, rétrécie de `L / slope` de chaque côté à l'épaulement ; trapèze dans le plan (largeur, normale), extrudé sur `e`. Ajouts de l'invitée = les queues (longueur `L`) ; enlèvements de l'hôte = les mêmes prismes dans son repère, prolongés de `CUT_OVERRUN_MM` (0,1 mm) hors de la matière là où ils débouchent. Deux planches 400 × 150 × 18 en angle → n = 3, p = 6, t = 42, b = 36, queues à [6, 48], [54, 96], [102, 144] côté pointe ; `resolve` renvoie ces valeurs. | U |
| D4 | Refus (`JointError`, gabarit traduit) : contact par une face ou par le chant (messages de J3) ; hôte qui dépasse ou n'arrive pas à la face extérieure de l'invitée (« Queue d'aronde : la pièce à griffes doit arriver à fleur de la face extérieure de la pièce à queues. ») ; `b` < 1 mm ou `t` ≤ 0 (« Queues trop étroites : {count} queues dans {width} mm avec des griffes de {pin} mm et une pente 1:{slope}. »). | U |
| D5 | `features/solids.solid_shape` convertit un `Prism` (`Part.makePolygon` → `Part.Face` → `extrude`). Proxy `…features.joints.dovetail.DovetailJoint`, type `Menuiserie::Dovetail`, nom interne `Dovetail`, libellé « Queue d'aronde » ; propriétés `TailCount` (`App::PropertyIntegerConstraint`, 0 à 50), `PinWidth` (`App::PropertyLength`), `Slope` (`App::PropertyFloat`, « Pente 1:n des queues ; 0 = automatique (1:6). »), groupe « Queue d'aronde » ; `Version` = 1. Planches de D3 : pièces usinées valides, un solide chacune ; invitée = brute + 37 908 mm³, hôte = brute − 37 908 mm³ ; export STEP réimporté au même volume. | I |
| D6 | Commande `Menuiserie_Dovetail` (« Queue d'aronde », icône existante) ; panneau J3e générique (nombre, griffes, pente effectifs). | G |
| D7 | Membres d'un Ensemble : un tiroir dont la hauteur passe de 150 à 200 mm → 4 queues automatiques, un recompute, tout valide. | I |

Précisions du dev (J4f, 2026-10-21), décisions les plus simples là où la spécification se tait :

- Face extérieure de l'invitée : celle de ses deux faces (selon son épaisseur) où le bout de
  l'hôte arrive à fleur (± 0,01 mm) ; l'hôte doit en outre dépasser l'autre face de plus de
  0,01 mm (il couvre toute l'épaisseur). Sinon, y compris pour un hôte juste aussi large que
  l'épaisseur (ses griffes seraient détachées) : « Queue d'aronde : la pièce à griffes doit
  arriver à fleur de la face extérieure de la pièce à queues. »
- `W` = largeur du contact (selon la largeur de l'invitée), positions des queues comptées depuis
  son bord ; `e` = épaisseur du contact ; `L` = profondeur de l'hôte (`host_depth` de J3).
- Logements : prolongés de `CUT_OVERRUN_MM` au-delà des deux faces de l'hôte (flancs prolongés
  à la même pente, le volume enlevé dans la matière ne change pas) et au-delà de la face
  extérieure de l'invitée ; pas du côté de sa face intérieure, où l'hôte garde sa matière.
- `b` = 1 mm tout juste est accepté (refus si `b` < 1 mm). Contact par le chant : message de
  J3 tel quel (« Le tenon se fait au bout de la pièce, pas sur son chant. »).
- `ratio_param` : nombre fini, non booléen, 0 ou 2 ≤ n ≤ 20, décimal permis ; refus « Paramètre
  d'assemblage invalide : {field} = {value} (0 pour automatique, ou rapport fini entre {min}
  et {max} attendu). ». `MAX_RATIO` est exporté par la façade `core.joints` pour le panneau.
- Panneau J3e : nouveau genre de champ « rapport » pour `App::PropertyFloat` (champ décimal
  sans unité, 2 décimales, borné de 2 à 20 comme `core` : 0 passe par la case « Auto »).
  Libellés « Nombre de queues », « Largeur des griffes », « Pente 1:n », chacun avec sa case
  « Auto ». Transaction « Créer un assemblage à queue
  d'aronde ».
- `DovetailValues(tail_count, pin_width, slope, tail_width, tail_base, tails)` : `t`, `b` et
  les intervalles des queues côté pointe.
- Les contrôles du `Prism` (polygone simple, plan, extrusion hors du plan) sont dans le module
  privé `core/_polygon.py`, pour garder `core/geometry.py` sous 400 lignes.
- Rôles : `guess_roles` de J3 suffit (la pièce dont le bout est entièrement couvert porte les
  queues). Icône existante inchangée (`tools/generer_icones.py` relancé, aucun écart).
- D7 attend J4b′ (Ensemble) : non couvert par ce lot ; le test d'intégration vérifie déjà que
  des planches de 200 mm passent à 4 queues automatiques en un recalcul.

### J4g — Onglet (`core/joints/miter.py`, `features/joints/miter.py`)

| N° | Critère | Test |
|---|---|---|
| A1 | `MiterStrategy` : les deux pièces se **chevauchent** au coin, dessinées à leur longueur **hors tout** (pointe longue). Boîte commune `C` ; axe commun `s` = axe selon lequel les deux pièces couvrent exactement `C` (à fleur, ± 0,01 mm) ; dans le plan des deux autres axes (u, v), chaque pièce s'arrête sur une face de `C` et l'autre la traverse. Plan de coupe = plan qui contient `s`, le **coin extérieur** (où les deux bouts se rejoignent) et le **coin intérieur** de `C`. Chaque pièce perd le prisme triangulaire de `C` situé du côté de l'autre pièce. Angles de coupe = atan(w_invitée / w_hôte) et son complément : **45°** pour deux largeurs égales, sinon les deux faces coupées coïncident quand même. `MiterParams` est un objet valeur sans champ en J4 (`PARAMS` exigé par `JointFeature`). | U |
| A2 | Cadre : deux traverses 500 × 60 × 20 qui se chevauchent de 60 × 60 au coin → chacune perd 36 000 mm³, angles 45° ; coin de caisson : deux panneaux 720 × 400 × 18 et 600 × 400 × 18 qui se chevauchent sur 18 × 18 × 400 (axe commun = profondeur) → chacun perd 18 × 18 / 2 × 400 = 64 800 mm³ ; largeurs 60 et 40 → angles 33,69° et 56,31°. `resolve` renvoie les deux angles (degrés, 2 décimales). | U |
| A3 | Refus (`JointError`, gabarit traduit) : contact ou écart (« Onglet : dessinez les deux pièces à leur longueur hors tout ; elles doivent se chevaucher au coin. ») ; une pièce qui dépasse le coin (croix, T : « Onglet : les deux pièces doivent s'arrêter au même coin. ») ; pièces pas à fleur sur l'axe commun ; pas d'équerre (M1 de J3). | U |
| A4 | Proxy `…features.joints.miter.MiterJoint`, type `Menuiserie::Miter`, nom interne `Miter`, libellé « Onglet » ; aucune propriété propre (`PROPERTIES` = ()), `Version` = 1. Pièces de A2 : usinées valides, un solide chacune ; leur intersection a un volume nul, leur réunion vaut celle des deux brutes et la somme de leurs volumes celle des deux brutes moins `C` (± 1e-6 relatif). | I |
| A5 | Commande `Menuiserie_Miter` (« Onglet ») ; icône `Menuiserie_Miter.svg` ajoutée à `tools/generer_icones.py` (test des icônes à jour) ; panneau J3e générique (angles affichés, aucun champ). | G |
| A6 | Membres d'un Ensemble : un cadre à onglets suit `Width` et `Height` (traverses fixes aux bords qu'elles touchent), un recompute, tout valide. | I |

Précisions du dev (J4g, 2026-10-21), décisions les plus simples là où la spécification se tait :

- A4 (ligne du tableau corrigée) : chaque pièce garde la moitié de `C` que l'autre perd ; le
  test vérifie aussi que les faces coupées sont coplanaires et confondues.
- Axes, dans le repère de l'hôte : `s` = l'axe où aucune pièce ne dépasse `C` (± 0,01 mm) ;
  `u` = l'axe où seul l'hôte dépasse, d'un seul côté ; `v` = l'axe où seule l'invitée dépasse,
  d'un seul côté. Refus, dans cet ordre : pas de chevauchement (contact ou écart) ; aucun axe à
  fleur (épaisseurs différentes, même centrées, pièces décalées) → « Onglet : les deux pièces
  doivent avoir la même étendue le long de l'arête du coin et y être à fleur. » ; une pièce qui
  dépasse `C` des deux côtés d'un axe (T, croix) → « même coin » ; toute autre disposition
  (pièces alignées bout à bout, pièce incluse dans l'autre) → « même coin ».
- Angles : mesurés depuis une coupe d'équerre de chaque pièce (lecture de la scie) ; `w_hôte` =
  étendue de `C` selon `v` (largeur de l'hôte dans le plan du coin), `w_invitée` = selon `u` ;
  angle de l'hôte = atan(w_invitée / w_hôte), de l'invitée = son complément.
  `MiterValues(host_angle, guest_angle, host_cut, guest_cut)`, angles arrondis au centième ;
  « Inverser » les échange.
- Enlèvements : chaque triangle est agrandi d'au moins `CUT_OVERRUN_MM` hors de la matière
  (sommets prolongés le long de l'hypoténuse, qui reste sur le plan de coupe) et prolongé de
  `CUT_OVERRUN_MM` de chaque côté selon `s` : le volume enlevé dans la pièce ne change pas et
  les deux faces coupées restent dans le même plan.
- Panneau J3e : aucun champ ; les angles s'affichent dans un libellé (`summaryLabel`) rempli
  par le gabarit `JointFeature.SUMMARY` du type (vide pour les autres assemblages) : « Angles de
  coupe : {host_angle}° pour la pièce hôte, {guest_angle}° pour la pièce invitée (depuis une
  coupe d'équerre). ». Transaction « Créer un assemblage d'onglet ». `mm_text` est exporté par la
  façade `core.joints` pour écrire les angles à la française.
- `make_miter(host, guest, **params)` garde la signature des autres fabriques : aucun paramètre
  accepté en J4, un nom inconnu lève `TypeError` avant toute création.
- Rôles : `guess_roles` de J3 (la plus mince est l'invitée ; à épaisseur égale, la première
  pièce sélectionnée est l'hôte). Icône `Menuiserie_Miter.svg` (angle de cadre) ajoutée à
  `tools/generer_icones.py`.
- Renfort (lamelle, fausse languette) hors périmètre, décision de jv (issue #30). A6 attend
  J4b′ (Ensemble) : non couvert par ce lot ; le test d'intégration vérifie déjà que la coupe suit
  la largeur d'une traverse en un recalcul.

## 4. Conception

### 4.1 Principe (ADR 0008, 0009, 0010)

- **Ensemble** = un objet de **cotes** (`App::FeaturePython`, nom interne `Furniture`), sans
  forme et **sans lien vers ses membres** : il porte `Width`, `Depth`, `Height` et un coin de
  départ `Origin`. Son repère est celui du conteneur commun de ses membres (document ou Std Part) :
  X = largeur, Y = profondeur, Z = hauteur.
- **Membre** = pièce brute (ou sous-ensemble) qui porte un lien `Furniture` vers son ensemble, son
  mode et ses six **options de distance** (`FixedLeft` … `FixedTop`). Les dépendances vont des
  membres vers l'ensemble, jamais l'inverse : aucun cycle possible.
- **Liaison** = expression FreeCAD native posée par l'atelier dans l'`ExpressionEngine` d'un membre
  (`Width = <<Bureau>>.Depth - 40 mm`). Elle est calculée (création, ajout, changement de mode ou
  d'option, « Relier ») par les règles pures de `core/furniture` ; ensuite, changer une cote ne
  fait appel à aucun code de l'atelier : FreeCAD évalue les expressions, puis les assemblages et
  les pièces usinées suivent (ADR 0006).
- **Gabarit** = générateur ponctuel : il crée des pièces (avec leurs options), des assemblages et
  un Ensemble ordinaires, puis disparaît (ADR 0010).
- **Assemblages 2** = trois stratégies et trois proxies de plus dans le cadre de J3 ; la queue
  d'aronde et l'onglet introduisent un solide non parallélépipédique, le `Prism` (§ 4.8).

```
freecad/menuiserie/
├── core/
│   ├── geometry.py              J4f  + Prism (polygone plan extrudé), moved() étendu
│   ├── furniture/
│   │   ├── __init__.py          J4a  façade : FurnitureBox, Member, Edge, InteriorMode, FollowRule, Binding, Notice, FurnitureError
│   │   ├── _model.py            J4a  objets valeur, validation
│   │   ├── _messages.py         J4a  gabarits des refus et des avertissements
│   │   ├── _spans.py            J4a  member_spans, edge_distances
│   │   ├── _defaults.py         J4a  default_fixed, fixed_by_default (Q7)
│   │   ├── _follow.py           J4a  follow_rules, mouvement d'une face (Linear)
│   │   ├── _bindings.py         J4a  bindings_for, format des expressions et des nombres
│   │   └── _check.py            J4a  predict, check_resize, check_membership
│   ├── templates/
│   │   ├── __init__.py          J4d  PieceSpec, JointSpec, Layout
│   │   └── carcass.py           J4d  CarcassParams, carcass_layout
│   └── joints/
│       ├── _base.py             J4e–g JointKind + HALF_LAP, DOVETAIL, MITER ; J4f ratio_param
│       ├── half_lap.py          J4e  HalfLapParams, HalfLapStrategy
│       ├── dovetail.py          J4f  DovetailParams, DovetailValues, DovetailStrategy
│       └── miter.py             J4g  MiterParams, MiterValues, MiterStrategy
├── features/
│   ├── solids.py                J4f  Prism → Part
│   ├── furniture.py             J4b′ proxy Furniture, création, membres, réouverture
│   ├── furniture_bindings.py    J4b′ lecture des membres (blocs, options, formules), écriture et retrait des liaisons, member_option_changed
│   ├── templates.py             J4d  instanciation d'un Layout (pièces, options, assemblages, ensemble)
│   └── joints/
│       ├── half_lap.py          J4e  HalfLapJoint
│       ├── dovetail.py          J4f  DovetailJoint
│       └── miter.py             J4g  MiterJoint
├── api.py                       J4b′ make_furniture, add_to_furniture, remove_from_furniture, set_member_options,
│                                     rebind_furniture, resize_furniture ; J4d make_carcass ; J4e–g make_half_lap, make_dovetail, make_miter
└── gui/
    ├── view_providers/furniture.py  J4c
    ├── commands/furniture.py        J4c  Menuiserie_Furniture, Menuiserie_FurnitureAdd ; J4d Menuiserie_Carcass
    ├── commands/joints.py           J4e–g Menuiserie_HalfLap, Menuiserie_Dovetail, Menuiserie_Miter (famille J3d)
    └── task_panels/
        ├── furniture.py             J4c  FurnitureTaskPanel (ObjectTaskPanel de J3e)
        └── carcass.py               J4d  CarcassTaskPanel
```

### 4.2 Design patterns retenus

| Besoin | Pattern | Justification |
|---|---|---|
| Règles de suivi (option fixe, mode) et options par défaut (bord, contact) | **Chaîne de règles** ordonnée par priorité, fonctions pures | priorité explicite et testable, pas de `if` imbriqués |
| Données de l'ensemble | **objets valeur** immuables (`FurnitureBox`, `Member`, `FollowRule`, `Binding`, `Notice`, `CarcassParams`, `Layout`) | testables sans FreeCAD |
| Création | **Fabrique** (`create_furniture`, `make_furniture`, `make_carcass`, `create_joint`) | commandes, scripts et tests |
| Gabarits | **Builder** : `carcass_layout` décrit, `features/templates.py` construit | un seul constructeur pour tous les gabarits futurs (étagère, cadre, tiroir) |
| Mi-bois, queue d'aronde, onglet | **Strategy + registre** de J3 ; **Template Method** `JointFeature` | point d'extension prévu, aucun changement du squelette |
| Objets du document | **Proxy** FeaturePython + ViewProvider séparé | règle du projet |
| Avertissements au changement de cote ; option changée dans l'éditeur de propriétés | **Observer** (`onChanged` du proxy de l'objet modifié, hors restauration, annulation et recalcul) | pas d'appel croisé, pas d'observateur global ; l'objet n'écrit que dans lui-même |

### 4.3 `core/furniture/` (J4a)

```python
class InteriorMode(
    str, Enum
):  # enregistré (PositionMode) : valeurs stables, ajout en fin seulement
    STAY = "Stay"  # distance non fixe : la face ne bouge pas
    PROPORTIONAL = "Proportional"  # distance non fixe : la face garde sa proportion


class Edge(str, Enum):  # enregistré (propriétés Fixed<Edge>) : valeurs stables
    LEFT = "Left"  # début de X
    RIGHT = "Right"  # fin de X
    FRONT = "Front"  # début de Y
    BACK = "Back"  # fin de Y
    BOTTOM = "Bottom"  # début de Z
    TOP = "Top"  # fin de Z
    # propriétés : axis (FurnitureAxis), at_end (bool), anchor (Anchor.START ou Anchor.END)


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
    block: (
        PlacedBlock | None
    )  # pièce : cotes + placement dans le repère de l'ensemble (origine déduite)
    box: FurnitureBox | None  # sous-ensemble : ses cotes (et `origin`)
    origin: Vec3 | None
    mode: InteriorMode
    fixed: (
        frozenset[Edge] | None
    )  # distances fixes ; None = nouveau membre, options par défaut à calculer
    driven: frozenset[str]  # propriétés pilotées par une formule ou une contrainte de l'utilisateur
    label: str  # nom cité dans les messages (J4a)


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
class Notice:  # avertissement traduisible, jamais bloquant ; template et message en propriétés
    kind: NoticeKind  # UserFormula, NotSquare, ThicknessKept, OutsideBox
    params: Mapping[str, str]


class FurnitureError(TemplatedError): ...  # refus (redimensionnement, cycle d'ensembles)


def member_spans(
    member: Member,
) -> Mapping[FurnitureAxis, Span]: ...  # Span(lo, hi, local, reversed)
def edge_distances(member: Member, box: FurnitureBox) -> Mapping[Edge, float]: ...
def default_fixed(
    box: FurnitureBox, members: Sequence[Member]
) -> Mapping[str, frozenset[Edge]]: ...  # membres dont fixed est None
def follow_rules(
    box: FurnitureBox, members: Sequence[Member]
) -> tuple[Mapping[str, tuple[FollowRule, ...]], tuple[Notice, ...]]: ...  # fixed renseigné
def bindings_for(
    label: str,
    box: FurnitureBox,
    members: Sequence[Member],
    rules: Mapping[str, tuple[FollowRule, ...]],
    *,
    nested: bool = False,
) -> tuple[tuple[Binding, ...], tuple[Notice, ...]]: ...
def predict(
    old: FurnitureBox,
    new: FurnitureBox,
    members: Sequence[Member],
    rules: Mapping[str, tuple[FollowRule, ...]],
) -> Mapping[str, Member]: ...
def check_resize(
    old: FurnitureBox,
    new: FurnitureBox,
    members: Sequence[Member],
    rules: Mapping[str, tuple[FollowRule, ...]],
    joined: Sequence[tuple[str, str]],
) -> tuple[Notice, ...]: ...  # FurnitureError si refus
```

**Distance à un bord** : chaque face d'un membre a une distance au bord de l'ensemble **de son
côté** (face de début de X → bord gauche, face de fin de X → bord droit, etc.). Chaque distance
porte une option **fixe / non fixe** (Q3).

**Options par défaut** (`default_fixed`, appliquées une fois, à l'entrée du membre dans
l'ensemble ; ensuite seul le menuisier les change) :

1. **toute distance est fixe**, nulle ou non (Q7, réponse de jv : « La pièce bouge par défaut » ;
   seul endroit : `fixed_by_default`) ;
2. sur l'axe de `Thickness`, seule la face la plus proche de son bord est fixe (égalité → début) ;
3. le menuisier décoche ensuite « fixe » là où la pièce doit rester en place.

**Règle de suivi d'une face** (`follow_rules`), première qui s'applique :

1. **formule de l'utilisateur** : la propriété n'est pas liée (F9) ;
2. **distance fixe** → ancre du bord de son côté (`START` pour gauche, avant, bas ; `END` pour
   droite, arrière, haut) ;
3. **distance non fixe** → le mode : `STAY` → `START` (ne bouge pas) ; `PROPORTIONAL` → `RATIO`.

Sur l'axe aligné sur `Thickness`, les deux faces partagent une seule ancre (une seule face fixe :
la sienne ; deux : la plus proche de son bord, égalité → `START`, et `ThicknessKept` ; aucune :
le mode, `RATIO` s'appliquant au milieu de la pièce). Sur un axe aligné sur `Length` ou `Width`,
deux ancres différentes donnent une cote liée :
`cote = f(fin) − f(début)` avec `f(START) = c`, `f(END) = C − (C₀ − c)`, `f(RATIO) = C × c / C₀`
(`C` = cote de l'ensemble, `C₀` à la liaison, `c` = coordonnée à la liaison, relative à `Origin`).
Les constantes sont figées à la liaison ; « Relier les pièces » les recalcule après une
modification à la main, **sans toucher aux options**.

**Format des expressions** : pour une position, `<<Label>>.Origin.x + ` d'abord ; puis
`<<Label>>.Cote`, puis `* ratio` (9 décimales au plus), puis `+ k mm` ou `- k mm` (6 décimales au
plus, zéros inutiles retirés, constante nulle omise). Une liaison effacée par l'utilisateur n'est
pas une formule : « Relier les pièces » la remet. Les
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
| `Template` | `App::PropertyString` | Ensemble | `""` | lecture seule | Gabarit qui a créé l'ensemble (information seulement). |
| `Version` | `App::PropertyInteger` | Base | 1 | masquée | Version du modèle de données de l'ensemble, utilisée pour migrer les anciens fichiers. |

`EdgeMargin`, proposé avant la réponse de jv à Q3, **n'existe pas** : aucun document ne l'a jamais
porté (rien à migrer). `execute()` ne construit rien (pas de forme) ; il valide les cotes
(`FurnitureBox`) et passe l'objet en erreur avec un message traduit sinon.
`onChanged(Width|Depth|Height)` hors restauration, annulation et recalcul : avertissement dans la
vue rapport pour chaque membre dont une propriété concernée suit une formule de l'utilisateur (N5),
et, si `check_resize` refuse, un avertissement citant la pièce (Q4 : la cote est appliquée). Le
proxy n'écrit jamais dans un autre objet.

#### 4.4.2 Propriétés ajoutées aux membres (dynamiques, groupe « Ensemble »)

| Propriété | Type | Défaut | Édition | Infobulle |
|---|---|---|---|---|
| `Furniture` | `App::PropertyLink` | l'ensemble | lecture seule | Ensemble dont la pièce suit les cotes. |
| `PositionMode` | `App::PropertyEnumeration` (`Stay`, `Proportional`) | `Stay` | modifiable | Faces dont la distance au bord n'est pas fixe : Stay, elles ne bougent pas ; Proportional, elles gardent leur proportion de la cote. Sans effet sur une position pilotée par une formule. |
| `FixedLeft` | `App::PropertyBool` | F3–F4 | modifiable | Distance fixe au bord gauche de l'ensemble : la pièce garde cette distance quand la largeur change. |
| `FixedRight` | `App::PropertyBool` | F3–F4 | modifiable | Distance fixe au bord droit : la pièce suit ce bord quand la largeur change. |
| `FixedFront` | `App::PropertyBool` | F3–F4 | modifiable | Distance fixe au bord avant. |
| `FixedBack` | `App::PropertyBool` | F3–F4 | modifiable | Distance fixe au bord arrière : la pièce suit ce bord quand la profondeur change. |
| `FixedBottom` | `App::PropertyBool` | F3–F4 | modifiable | Distance fixe au bas de l'ensemble. |
| `FixedTop` | `App::PropertyBool` | F3–F4 | modifiable | Distance fixe au haut de l'ensemble : la pièce suit ce bord quand la hauteur change. |
| `FurnitureBindings` | `App::PropertyMap` | `{}` | masquée | Expressions posées par l'atelier (propriété → texte), pour les distinguer des formules de l'utilisateur. |

Ajoutées à l'entrée dans l'ensemble, retirées à la sortie ; posées sur la **brute** (une pièce
usinée passée à l'API est remplacée par sa `Base`) ou sur le sous-ensemble. Les noms
`Fixed` + valeur d'`Edge` sont figés (contrat de persistance, ADR 0009).

**Option changée dans l'éditeur de propriétés** (Q3 : « réglable dans les propriétés ») :
`WoodPart.onChanged` (et `Furniture.onChanged` pour un sous-ensemble) appelle, par import différé,
`furniture_bindings.member_option_changed(obj, prop)` pour `PositionMode` et `Fixed…`, hors
restauration (`"Restore" in obj.State`), hors annulation (`Document.Transacting`) et hors écriture
de l'atelier lui-même (drapeau, comme `MachinedPart` en J3). Cette fonction recalcule les seules
liaisons de **ce membre** (règles F5–F7 sur sa géométrie actuelle et les cotes actuelles de
l'ensemble) et ne les écrit que dans **son** `ExpressionEngine` et **son** `FurnitureBindings`,
dans la transaction ouverte par l'éditeur. Aucun objet n'écrit dans un autre. `WoodPart` garde
`Version` = 2 (aucune propriété ajoutée à son schéma) ; son `onChanged` ne fait rien pour une
pièce hors ensemble.

#### 4.4.3 Lecture des membres et formules de l'utilisateur (`furniture_bindings.py`)

- Bloc d'un membre = `PlacedBlock` de J3 exprimé dans le repère du conteneur commun ; options lues
  dans les six `Fixed…` (`Member.fixed`), `None` pour un objet qui entre dans l'ensemble.
- `driven` = propriétés concernées (`Length`, `Width`, `Placement` et ses sous-chemins) dont
  l'expression actuelle n'est pas celle de `FurnitureBindings`, plus `Placement` si un objet de
  l'atelier Assembly intégré (`Assembly::JointGroup` et ses joints, détectés par `TypeId` et
  `InList`, sans import du module) référence la pièce : c'est la « contrainte » de jv. Détection
  au mieux : un autre mécanisme qui réécrit `Placement` sans expression n'est pas vu (risque R6).
- Écriture : `setExpression(prop, texte)` puis relecture, mise à jour de `FurnitureBindings` ;
  retrait : `setExpression(prop, None)` seulement si le texte actuel est celui enregistré.

#### 4.4.4 API

```python
def make_furniture(
    objects: Sequence[DocumentObject], label: str = ""
) -> tuple[DocumentObject, tuple[str, ...]]: ...  # (ensemble, avertissements traduits)
def add_to_furniture(
    furniture: DocumentObject, objects: Sequence[DocumentObject]
) -> tuple[str, ...]: ...
def remove_from_furniture(objects: Sequence[DocumentObject]) -> None: ...
def set_member_options(
    obj: DocumentObject, *, mode: str | None = None, fixed: Mapping[str, bool] | None = None
) -> tuple[str, ...]: ...  # fixed : {"Back": True, …}
def rebind_furniture(furniture: DocumentObject) -> tuple[str, ...]: ...
def resize_furniture(
    furniture: DocumentObject,
    *,
    width: float | None = None,
    depth: float | None = None,
    height: float | None = None,
) -> None: ...  # check_resize puis écriture et recalcul
def furniture_of(obj: DocumentObject) -> DocumentObject | None: ...
```

Sans transaction (les commandes l'ouvrent, comme J3) ; ViewProvider ajouté si `App.GuiUp`.

### 4.5 Recalcul, réouverture, annuler / rétablir

- **Graphe** : ensemble (cotes) → membres (expressions, `Furniture`) → assemblages → pièces
  usinées ; un sous-ensemble se place entre son ensemble et ses membres. Un seul `recompute()`.
- **Aucune écriture pendant le recalcul** : les liaisons sont écrites par l'API ou par
  `member_option_changed` (hors recalcul), jamais par `execute()` ; changer une cote n'écrit rien
  d'autre que la cote.
- **Réouverture** : proxy sans état, `onDocumentRestored` (aides de `schema.py`), contrôle des
  propriétés de membre ; aucun objet « Touched ».
- **Annuler / rétablir** : les expressions, les options, `FurnitureBindings` et les propriétés de
  membre sont des propriétés ordinaires, restaurées par FreeCAD ; une commande = une transaction.

### 4.6 Affichage, commandes, panneau (J4c)

`ViewProviderFurniture` (chemin figé `freecad.menuiserie.gui.view_providers.furniture`) :
`claimChildren` = membres (pièce usinée à la place de sa brute), sous-ensembles et assemblages
internes, calculés d'après `InList` (affichage seulement, aucun lien du document) ;
`setEdit` → `FurnitureTaskPanel`. Le panneau réutilise `ObjectTaskPanel` (J3e) : transactions,
fermeture forcée, `DeletionWatcher` le temps du panneau seulement. Les six lignes « distance au
bord » (P3) lisent `edge_distances` ; une distance saisie déplace la pièce (ou change sa cote sur
un axe étirable dont la face opposée est conservée) puis relie ce membre, dans la transaction du
panneau.

### 4.7 Gabarit « Caisson » (J4d, ADR 0010)

`carcass_layout(params) -> Layout` (pur) décrit pièces (`PieceSpec` : clé, libellé traduisible,
cotes, `PlacedBlock`, matériau, mode, **options `fixed` explicites**) et assemblages (`JointSpec` :
type, hôte, invitée, paramètres validés de J3). Construction : côtés pleine hauteur et pleine
profondeur ; dessus et dessous entre les côtés, tourillons Ø 8 × 30 enfoncés de 12 dans les côtés
(les valeurs automatiques de J3, 35 mm dont 17,5 dans l'hôte, perceraient un côté de 18) ; fond de
8 logé de 10 dans une feuillure des côtés, du dessus et du dessous ; étagères posées (jeu de 1 mm
aux côtés, 1 mm devant le fond), réparties à intervalles égaux, mode `Stay`. Le gabarit fixe
lui-même les distances que le menuisier attend d'un caisson (jeux de l'étagère, retraits du fond)
au lieu de compter sur les options par défaut, qui laisseraient ces faces non fixes.
`features/templates.py` instancie un `Layout` : pièces (`create_wood_part`), assemblages (fabriques
J3), ensemble, options et liaisons (`create_furniture`) ; aucun objet « gabarit » n'est gardé.

### 4.8 Assemblages 2 (J4e, J4f, J4g)

#### 4.8.1 Insertion dans le cadre de J3

- `core/joints/_base.py` : `JointKind` reçoit `HALF_LAP = "HalfLap"`, `DOVETAIL = "Dovetail"`,
  `MITER = "Miter"` (non enregistrés) ; `_registry.py` les ajoute au registre figé ; J4f ajoute
  `ParamKind.RATIO` et `ratio_param(default)` (0 = automatique, sinon 2 ≤ n ≤ 20) aux contrôles
  communs (`validate_params`), sans dupliquer les autres.
- Chaque stratégie a `resolve` (valeurs effectives : `HalfLapValues`, `DovetailValues`,
  `MiterValues`, affichées par le panneau J3e) et `plan` (`JointPlan`).
- `features/joints/<type>.py` : une sous-classe de `JointFeature` qui fixe `KIND`, `TYPE`,
  `OBJECT_NAME`, `LABEL`, `PARAMS` et `PROPERTIES` ; les noms des propriétés suivent
  `property_name` (`tail_count` → `TailCount`), lus par `params_from` et écrits par `write_params`.
  `MiterParams` est une `dataclass(frozen=True)` **sans champ** : `__init_subclass__` exige un
  type, `params_from` construit `MiterParams()`, `write_params` n'écrit rien. Un renfort futur
  (Q8) ajoutera un champ, une propriété et `Version` = 2 avec migration « aucun renfort ».
- Fabriques `create_half_lap`, `create_dovetail`, `create_miter` par `create_joint` ;
  `make_…` dans `api.py`. Commandes dans la famille de J3d, panneau générique de J3e (bouton
  « Inverser » compris).

#### 4.8.2 Le solide `Prism` (J4f)

```python
@dataclass(frozen=True)
class Prism:
    """Polygone plan extrudé : sommets dans un plan, vecteur d'extrusion hors de ce plan."""

    points: tuple[Vec3, ...]  # ≥ 3 sommets distincts, non alignés, coplanaires, polygone simple
    extrusion: Vec3  # non nul, non parallèle au plan


Solid = Box | Cylinder | Prism
```

`moved(prism, transform)` transforme sommets et vecteur. `features/solids.solid_shape` :
`Part.Face(Part.makePolygon([*points, points[0]])).extrude(extrusion)`. Les enlèvements qui
débouchent sur une face sont prolongés de `CUT_OVERRUN_MM` = 0,1 mm hors de la matière (le volume
enlevé dans la pièce ne change pas ; les booléennes d'OCC évitent les faces confondues). Les ajouts
sont exacts et fusionnés par `removeSplitter` comme le tenon de J3.

#### 4.8.3 Mi-bois (J4e)

Deux pièces de même épaisseur, à fleur, qui se croisent (croix), se rejoignent en T ou en angle :
elles sont dessinées à leur place et **se chevauchent** dans la boîte commune `C`. L'hôte perd
`C` sur `depth` depuis sa face +Z locale, l'invitée le reste de `C` depuis sa face −Z (inversé par
`flip_side`). Uniquement des `Box` : aucun nouveau solide.

| Paramètre | Propriété | Défaut | 0 = automatique |
|---|---|---|---|
| `depth` | `Depth` (`App::PropertyLength`) | 0 | `mm_round(e / 2)` |
| `flip_side` | `FlipSide` (`App::PropertyBool`) | faux | — |

#### 4.8.4 Queue d'aronde traversante (J4f)

Invitée = pièce à queues (côté de tiroir), hôte = pièce à griffes ; l'invitée touche l'hôte par son
**bout**, dessinée à sa longueur visible (épaulement contre la face intérieure de l'hôte), le bout
de l'hôte à fleur de la face extérieure de l'invitée. Dans le repère de l'invitée (calculs de
`contact_frame` de J3) : plan (largeur `W`, normale), épaisseur `e` ; `L` = profondeur de l'hôte.
Griffes de bord en demi-griffes (un côté droit) de largeur `p` côté pointe, griffes intérieures de
largeur `p` côté pointe ; queues de largeur `t` côté pointe, `b = t − 2 L / slope` côté épaulement.

| Paramètre | Propriété | Défaut | 0 = automatique |
|---|---|---|---|
| `tail_count` | `TailCount` (`App::PropertyIntegerConstraint`, 0–50) | 0 | max(1, ⌊W / (3 e) + 0,5⌋) |
| `pin_width` | `PinWidth` (`App::PropertyLength`) | 0 | `mm_round(L / 3)` |
| `slope` | `Slope` (`App::PropertyFloat`) | 0 | 6 (pente 1:6, compromis feuillus / résineux) |

Queue i (i = 0 … n − 1), côté pointe de `x₀ = p + i (t + p)` à `x₁ = x₀ + t` ; trapèze
`(x₀ + L/slope, 0)`, `(x₁ − L/slope, 0)`, `(x₁, L)`, `(x₀, L)` dans le plan (largeur, normale vers
l'hôte), extrudé sur `e`. Pas de jeu (J3 : aucun jeu latéral).

#### 4.8.5 Onglet (J4g)

Deux pièces d'angle dessinées à leur longueur **hors tout** (de pointe longue à pointe longue), qui
se chevauchent au coin dans la boîte commune `C`. Le plan de coupe contient l'axe commun `s`, le
coin extérieur et le coin intérieur de `C` : 45° pour des largeurs égales, sinon atan(w_invitée /
w_hôte) et son complément, les deux faces coupées coïncidant toujours. Cadre (axe commun =
épaisseur) et coin de caisson (axe commun = profondeur) sont le même calcul. Chaque pièce perd un
`Prism` triangulaire (triangle dans le plan (u, v), extrudé sur `s`). Aucun paramètre en J4 ;
**renfort** (lamelle, fausse languette) : Q8.

#### 4.8.6 Application de l'ADR 0006 (brute → usinée)

| Assemblage | Dessin de la brute | Plan | Longueur de débit (J2) |
|---|---|---|---|
| Mi-bois | à sa place, les deux pièces se croisent | **retrait** seulement (deux entailles) | la brute, inchangée |
| Queue d'aronde | invitée à sa longueur visible, en contact par le bout ; hôte hors tout | **ajout** des queues à l'invitée (+ `L`), **retrait** des logements dans l'hôte | invitée : brute + `L`, comme un tenon de J3 (Q1 de J3) ; hôte : la brute |
| Onglet | les deux à leur longueur hors tout, chevauchement au coin | **retrait** seulement (un prisme triangulaire chacune) | la brute (longueur à la pointe longue, celle que le menuisier débite) |

L'onglet raccourcit bien la pièce le long de son arête intérieure (pointe courte), mais **par
retrait** : la brute garde la longueur hors tout, sa forme reste le parallélépipède (ADR 0003), la
pièce usinée porte la coupe. L'autre dessin (une pièce butée contre l'autre) aurait demandé
d'ajouter un triangle à l'une et d'en retirer un à l'autre, et ne montrerait plus la cote hors tout
du cadre : écarté. Dans un Ensemble, les pièces d'onglet et de mi-bois se chevauchent :
`check_resize` vérifie que la paire reste en `Overlap`.

### 4.9 Sécurité

Aucune lecture de fichier ni entrée externe nouvelle. Les expressions sont construites par
l'atelier à partir de nombres validés et du libellé de l'ensemble passé par
`<<…>>` : un libellé contenant `>>` est refusé à la liaison (message) pour ne jamais produire une
expression qui viserait un autre objet. Les valeurs relues (`PositionMode`, `Fixed…`,
`FurnitureBindings`, cotes, paramètres d'assemblage) sont contrôlées à la réouverture ; aucun
`eval`.

### 4.10 Compatibilité avec les autres ateliers (ADR 0007), Std Part et `App::Link`

- L'Ensemble n'a pas de forme et n'est pas un conteneur : il ne change ni la portée des liens ni
  le placement des pièces. Le meuble se déplace, se tourne, se duplique par **Std Part** et
  **`App::Link`**, outils natifs (N9, N10) ; l'atelier Assembly prend le Std Part comme composant.
- Les pièces restent des `Part::FeaturePython` à forme standard (O13, O14 de J3 inchangés) ; les
  pièces usinées à queues ou à onglet sont des solides Part ordinaires (export STEP, D5).
- Les liaisons sont des expressions natives, visibles et modifiables par l'utilisateur et lisibles
  par tout outil ; sans l'atelier, le document s'ouvre avec ses formes enregistrées (N14).
- Espace de noms : `Menuiserie::Furniture`, `Menuiserie::HalfLap`, `Menuiserie::Dovetail`,
  `Menuiserie::Miter`, commandes `Menuiserie_Furniture`, `Menuiserie_FurnitureAdd`,
  `Menuiserie_Carcass`, `Menuiserie_HalfLap`, `Menuiserie_Dovetail`, `Menuiserie_Miter` ; aucun
  objet nommé « Assembly » ni « Part » ; aucune dépendance ajoutée ; aucun observateur global.

## 5. Découpage en PR

| Lot | Branche | Contenu | Diff estimé hors tests | Critères |
|---|---|---|---|---|
| **J4a** | `feat/ensembles-core` | `core/furniture/` (modèle, options par défaut, règles, liaisons, aperçu) | ≈ 400 | F1–F12 |
| **J4b′** | `feat/ensembles-document` | `features/furniture.py`, `furniture_bindings.py` (dont `member_option_changed`), crochet dans `WoodPart.onChanged`, API, CHANGELOG ; livrable par la console | ≈ 400 | N1–N15 |
| **J4c** | `feat/ensembles-panneau` | ViewProvider, deux commandes, panneau (distances et cases « fixe »), icône, recette manuelle, README « Modifier un meuble » | ≈ 400 | P1–P7 |
| **J4d** | `feat/gabarit-caisson` | `core/templates/`, `features/templates.py`, `make_carcass`, commande et panneau | ≈ 380 | K1–K7 |
| **J4e** | `feat/assemblage-mi-bois` | stratégie, objet, fabrique, commande du mi-bois | ≈ 200 | B1–B5 |
| **J4f** | `feat/assemblage-queue-aronde` | `Prism` (core et solids), `ratio_param`, stratégie, objet, fabrique, commande | ≈ 350 | D1–D7 |
| **J4g** | `feat/assemblage-onglet` | stratégie, objet, fabrique, commande, icône | ≈ 220 | A1–A6 |

Chaque lot est livrable seul : J4a est une bibliothèque testée sans FreeCAD ; J4b′ atteint le
livrable par la console ; J4c ajoute l'interface ; J4d (après J4b′, indépendant de J4c : sa
commande est dans son propre module) livre le caisson. J4e et J4f ne dépendent que de J3 et peuvent
partir tout de suite ; J4g suit J4f (il utilise `Prism`). Les critères « dans un Ensemble » (B5,
D7, A6) sont vérifiés dès que J4b′ est fusionné.

## 6. Compatibilité

- **Documents J1 et J3** : aucune migration ; `WoodPart` (`Version` 2), `MachinedPart` et les
  assemblages de J3 (`Version` 1) inchangés (N15). Le crochet de `WoodPart.onChanged` n'agit que
  sur une pièce membre d'un ensemble.
- **Nouveaux objets** : `Furniture`, `HalfLapJoint`, `DovetailJoint` et `MiterJoint` naissent en
  `Version` 1 (contrat de l'ADR 0003) ; les propriétés de membre (`Furniture`, `PositionMode`, les
  six `Fixed…`, `FurnitureBindings`) et les valeurs `Stay`, `Proportional` entrent dans le contrat
  de persistance (ADR 0009).
- **Réponse de jv à Q3** : aucun document J4 n'existe encore ; `EdgeMargin` et la valeur
  `Fixed` de `PositionMode` (proposés avant la réponse) disparaissent sans migration. La valeur
  `Fixed` est renommée `Stay` pour ne pas confondre « distance fixe » (option) et « reste en
  place » (mode).
- **Document J4 ouvert par un atelier J3** : proxys `Furniture` et assemblages 2 introuvables,
  signalés par FreeCAD ; les expressions restent dans les pièces et s'évaluent ; les formes
  enregistrées des pièces usinées restent affichées ; les propriétés de membre sont ignorées.
- **J2 (liste de débit)** : lira les brutes comme avant, plus la longueur des queues d'aronde
  (ajouts, § 4.8.6) ; regroupement par ensemble grâce à `Furniture`.
- **FreeCAD 1.0 et 1.1** : `setExpression` sur `Placement.Base.x`, `App::PropertyMap`,
  `App::PropertyVectorDistance` et ses sous-chemins, `Part.Face(...).extrude` existent dans les
  deux ; à vérifier en début de J4b′ : normalisation du texte des expressions, réécriture au
  renommage (R2), et `onChanged` d'une propriété dynamique modifiée dans l'éditeur de propriétés,
  dans sa transaction (R9).

## 7. Risques

| N° | Risque | Effet | Parade |
|---|---|---|---|
| R1 | Options par défaut inattendues (Q7 : toute distance fixe ; pièce intérieure qui suit le bord le plus proche alors que le menuisier la voulait immobile). | Pièce qui bouge alors que le menuisier la croyait en place. | Aperçu, colonne « Suit » et cases « fixe » visibles dans le panneau avant « OK » ; `OutsideBox` ; Q7 ; formule de l'utilisateur toujours respectée ; « Relier ». |
| R2 | Texte des expressions normalisé ou réécrit par FreeCAD (renommage, copie) différemment selon 1.0 / 1.1. | Liaison de l'atelier prise pour une formule de l'utilisateur. | Texte relu après écriture (§ 4.3) ; le cas défavorable est sûr : la formule est gardée, un avertissement propose « Relier ». Test en début de J4b′ sur les deux versions. |
| R3 | Constantes figées à la liaison : une pièce modifiée à la main ensuite (plateau de 30 → 40) n'est plus cohérente. | Pièces qui se chevauchent après une cote. | `check_resize` le détecte s'il touche un assemblage ; « Relier les pièces » ; documenté dans le README. |
| R4 | Pièce usinée déplacée à la main alors que la brute a un `Placement` lié (report de Q4 de J3). | Déplacement annulé au recalcul suivant. | Refus explicite avec message (N6). |
| R5 | Cote saisie hors panneau qui casse une pièce ou un assemblage (Q4 : appliquée). | Objets en erreur. | Jamais de forme partielle (J3) ; avertissement ; annulation. |
| R6 | « Contrainte » au sens large : seuls les expressions et les joints de l'atelier Assembly intégré sont détectés. | Une pièce pilotée par un autre addon peut recevoir une liaison. | Documenté ; la liaison reste une expression visible que l'utilisateur peut effacer. |
| R7 | Arbre : un membre réclamé à la fois par l'ensemble et par un Std Part ou une pièce usinée. | Doublons ou ordre étrange dans l'arbre. | `claimChildren` réclame la pièce usinée (qui réclame sa brute) ; vérifié en G et en recette sur 1.0 et 1.1. |
| R8 | Volume de travail : sept lots, panneau plus riche (six distances par pièce). | Lots qui dépassent 400 lignes. | Assemblages détachés en trois lots indépendants des ensembles ; si J4c déborde, la saisie des distances (pas les cases) passe dans un lot J4c₂. |
| R9 | `onChanged` d'une option écrit des expressions hors des commandes de l'atelier (éditeur de propriétés, script). | Écriture pendant une restauration, une annulation ou en boucle. | Gardes `Restore`, `Transacting` et drapeau d'écriture propre ; l'objet n'écrit que dans lui-même ; N4 et N13 le vérifient. |
| R10 | Booléennes d'OCC sur prismes (faces confondues, arêtes vives des queues et des onglets). | Forme invalide ou partielle. | `CUT_OVERRUN_MM` ; `removeSplitter` ; contrôle `isValid()` de J3 (jamais de forme partielle) ; tests d'intégration sur 1.0 et 1.1 avec volumes. |
| R11 | Queue d'aronde automatique dans un ensemble : le nombre de queues saute quand la largeur change. | Dessin qui change d'aspect. | Voulu (comme les tourillons de J3) ; un nombre saisi est fixe. |

## 8. Hors périmètre

- Usinages croisés et nœuds à trois pièces (**issue #19**) ; un assemblage ne voit toujours que
  les brutes (ADR 0006).
- **J4b** — finition des chants (issue #5) et finitions en relief (issue #7).
- **J2** — liste de débit (**issue #13**), qui reprendra ensembles, gabarits et ajouts des queues.
- **J5** — publication (TechDraw coté, traductions, Addon Manager).
- Queue d'aronde à recouvrement (demi-cachée), à coulisse ou à griffes non traversantes ; mi-bois
  à épaisseurs différentes ou en biais ; onglet de pièces qui ne sont pas d'équerre entre elles ;
  renforts d'onglet (Q8).
- Gabarits étagère, cadre, tiroir (Q5 : caisson seul en J4), quincaillerie, taquets.
- Pièces non d'équerre avec l'ensemble, cotes d'ensemble autres que les trois axes, ensembles
  répartis entre plusieurs conteneurs, pièces d'un autre atelier membres d'un ensemble,
  `App::Link` **de pièces** à l'intérieur d'un ensemble (le lien d'un Std Part entier est couvert).
- Remise des options aux valeurs par défaut en un clic (« Relier » garde les options).
- Intégration spécifique à l'atelier Assembly ou à d'autres addons (coexistence seulement).

## 9. Questions pour jv

Une réponse d'un mot suffit ; la recommandation est marquée ★.

**Q1 — Nature de l'Ensemble.** **Cotes** ★ (objet de cotes sans conteneur ; on déplace et duplique
le meuble avec un Std Part et `App::Link`, natifs) / **Conteneur** (groupe à repère propre, comme
un Std Part de l'atelier). ★ parce qu'un conteneur dont les pièces lisent les cotes crée un cycle
de dépendances et refait ce que Std Part fait déjà (ADR 0008).
*Réponse de jv (2026-10-21) : ★ retenue.*

**Q2 — Ensemble dans un ensemble (caisson dans le bureau) ?** **Oui** ★ (le caisson suit le bureau
et garde ses propres cotes) / **Non** (le gabarit ajoute ses pièces directement au bureau).
*Réponse de jv (2026-10-21) : ★ retenue.*

**Q3 — Retrait jusqu'auquel une pièce suit le bord le plus proche.**
*Réponse de jv (2026-10-21) : « lorsque je défini une distance, je veux pouvoir indiqué si elle
est fix ou non ».* Plus de seuil automatique (`EdgeMargin` supprimé) : chaque distance d'une face
au bord de son côté porte une option fixe / non fixe (six propriétés `Fixed…`, panneau et éditeur
de propriétés) ; fixe = la pièce garde cette distance et suit le bord ; non fixe = elle reste en
place (`Stay`) ou garde sa proportion (`Proportional`). Défaut : fixe (§ 4.3, Q7).

**Q4 — Cote changée dans l'éditeur de propriétés qui casserait une pièce ou un assemblage ?**
**Appliquer** ★ (pièces en erreur, avertissement, annulable ; le panneau, lui, refuse avant) /
**Rétablir** (l'atelier remet l'ancienne valeur, au prix d'une écriture hors recalcul).
*Réponse de jv (2026-10-21) : ★ retenue.*

**Q5 — Gabarits livrés en J4 ?** **Caisson** ★ / **Caisson+étagère** / **Quatre** (caisson,
étagère, cadre, tiroir).
*Réponse de jv (2026-10-21) : ★ retenue.*

**Q6 — Assemblages 2 dans J4 ?**
*Réponse de jv (2026-10-21) : « mi bois, queu arronde et 45 ».* J4 livre le mi-bois (J4e), la
queue d'aronde traversante (J4f) et l'onglet (J4g), § 3 et § 4.8.

**Q7 — Distance non nulle au bord (joue à 40 mm du fond, étagère à 1 mm du côté) : fixe par
défaut ?** **Non** ★ (la pièce reste en place tant que vous ne cochez pas « fixe » ; seules les
pièces contre le bord, ou contre une pièce qui le suit, le suivent) / **Oui** (toute distance est
fixe à la création : tout suit le bord le plus proche, l'étagère comprise).
*Réponse de jv (2026-10-21) : « La pièce bouge par défaut ».* **Oui**, contre la recommandation :
toute distance est fixe par défaut, nulle ou non ; la pièce suit le bord de son côté (sur l'axe
de son épaisseur, celui dont elle est le plus proche). L'option « non fixe » reste disponible
pour le menuisier (F3, § 4.3).

**Q8 — Renfort d'onglet en J4 ?** **Aucun** ★ (onglet collé seul ; renfort dans un lot suivant) /
**Lamelle** (biscuit) / **Fausse languette**. ★ parce que chacun demande un nouvel usinage dans
les deux pièces, et la fausse languette une pièce rapportée : un lot de plus. *Question ouverte*
(la spécification applique ★ en attendant).
