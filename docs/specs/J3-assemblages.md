# [J3] Assemblages 1 : tenon-mortaise, rainure-languette, feuillure, tourillons

- Jalon : J3 (version cible 0.2.0, à confirmer par jv)
- Statut : **validée** par jv le 2026-10-20 (Q1 à Q6 : recommandations retenues, § 9) ; position des
  pièces intérieures de l'Ensemble (J4) tranchée par jv le 2026-10-20 (§ 8)
- Exigences de jv intégrées le 2026-10-20 : compatibilité avec les autres addons (§ 4.9,
  ADR 0007) ; modification facile d'un ensemble de pièces, préparée ici et réalisée en J4 (§ 8)
- ADR liés : [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](../adr/0006-piece-brute-et-piece-usinee.md) (accepté),
  [0007 — Compatibilité avec les autres ateliers](../adr/0007-compatibilite-avec-les-autres-ateliers.md) (accepté)
- Découpage : cinq PR **J3a → J3b → (J3c ∥ J3d) → J3e** (§ 5)

## 1. Contexte

Avec J1, le menuisier dessine des pièces de bois (planches, tasseaux, panneaux) mais elles se
traversent ou se touchent sans être assemblées : pour montrer un tenon et sa mortaise, il
faudrait des booléennes `Part` faites à la main, qui ne suivent pas quand une cote change. Le plan
(§ 2) demande qu'un assemblage soit un objet qui relie deux pièces, modifie leur forme et suive
les pièces quand elles changent. Mi-bois et queue d'aronde viennent en J4 ; la liste de débit (J2,
après J4) reprendra les assemblages.

## 2. Objectif

Le menuisier peut :

1. relier deux pièces par un **tenon-mortaise**, une **rainure-languette**, une **feuillure**
   (ou logement) ou des **tourillons**, en sélectionnant les deux pièces puis une commande ;
2. régler l'assemblage (épaisseur du tenon, jeu, diamètre des tourillons…) dans l'éditeur de
   propriétés ou un panneau de tâche, avec des proportions **automatiques** de menuisier ;
3. modifier ensuite les cotes ou la position des pièces (à la main ou par des expressions) :
   tenons, mortaises, rainures et tourillons **suivent** en un seul recalcul, nombre de tourillons
   compris ;
4. utiliser les pièces assemblées dans les autres ateliers (TechDraw, `Part`, export STEP) et
   ouvrir le document sans l'atelier (ADR 0007).

**Livrable visible** : un cadre de deux montants et deux traverses assemblés par quatre
tenons-mortaises, qui se met à jour quand on change la largeur des montants ou des traverses
(J3b : par la console ; J3d–J3e : par les commandes et le panneau).

## 3. Critères d'acceptation

Légende : **U** = unitaire sans FreeCAD, **I** = intégration dans `freecadcmd` (1.0 et 1.1),
**G** = interface hors écran, **manuel** = recette décrite dans `docs/recette/J3e-scenarios-manuels.md`.
Les lettres des critères sont propres à cette spécification.

**Cadre de référence** (utilisé par plusieurs critères ; cotes en mm, cadre à plat dans le plan XY) :

| Pièce | Cotes L × l × e | `Placement` (base ; rotation) |
|---|---|---|
| Montant M1 | 600 × 60 × 22 | (0, 0, 0) ; aucune |
| Montant M2 | 600 × 60 × 22 | (0, 340, 0) ; aucune |
| Traverse T1 | 280 × 60 × 22 | (60, 60, 0) ; 90° autour de Z |
| Traverse T2 | 280 × 60 × 22 | (600, 60, 0) ; 90° autour de Z |

T1 occupe x ∈ [0, 60], y ∈ [60, 340] (affleurante au bout des montants), T2 x ∈ [540, 600]. Les
bouts des traverses touchent les chants intérieurs des montants (y = 60 et y = 340). Chêne partout.
Variante « pilotée » : `M2.Placement.Base.y = 400 mm - Width`, `M2.Width = M1.Width`,
`T1.Placement.Base.y = T2.Placement.Base.y = M1.Width`, `T1.Length = T2.Length = 400 mm - 2 * M1.Width`,
`T1.Placement.Base.x = Width`, `T2.Width = T1.Width` (expressions natives posées par le test).

### J3a — Géométrie et stratégies d'assemblage (`core/`)

| N° | Critère | Test |
|---|---|---|
| M1 | `RigidTransform` : construction depuis une matrice 4 × 4 (lignes), `inverse`, `compose`, `apply` ; `relative_axes(host, guest)` renvoie la permutation signée des axes du repère local de l'invitée dans celui de l'hôte pour des rotations multiples de 90° (bruit ≤ 1e-6 toléré : rotation de 90° + 1e-9 acceptée) ; une rotation de 45° ou de 90,01° lève `JointError` (gabarit « Les deux pièces doivent être d'équerre (angles multiples de 90°). »). | U |
| M2 | `classify(host, guest)` : écart > 0,01 mm sur un axe → `Separated` ; chevauchement ≤ 0,01 mm sur exactement un axe et > 0,01 mm sur les deux autres → `Contact` avec la face de l'invitée (`+X`, `-X`, `+Y`, `-Y`, `+Z`, `-Z` dans son repère local) et le rectangle de contact (repère de l'invitée) ; chevauchement > 0,01 mm sur les trois axes → `Overlap` avec la boîte commune (repère de l'hôte). Contact par une arête ou un coin seuls → `Separated`. Cas : cadre de référence (M1/T1 : contact, face `-X` de T1, rectangle 60 × 22) ; T1 reculée de 0,005 mm → contact ; de 0,02 mm → séparées ; avancée de 5 mm → chevauchement. | U |
| M3 | **Tenon-mortaise, valeurs automatiques** (M1 hôte, T1 invitée, tous paramètres à 0 = auto) : épaisseur du tenon = arrondi(22 / 3) = **7**, centré dans l'épaisseur (z ∈ [7,5 ; 14,5]) ; largeur = 60 − 2 × arrondi(60 / 6) = **40**, centrée ; longueur = arrondi(2/3 × 60) = **40** (60 = profondeur de M1 dans l'axe du tenon) ; mortaise = section du tenon, profondeur 40 + **2** (jeu de fond) = 42. Plan : ajout dans T1 = boîte x ∈ [−40, 0], y ∈ [10, 50], z ∈ [7,5 ; 14,5] (repère de T1) ; enlèvement dans M1 = boîte de 40 × 42 × 7 contre le chant y = 60 (repère de M1 : x ∈ [10, 50], y ∈ [18, 60]). Arrondi au mm « demi vers le haut » (`floor(x + 0,5)`), minimum 1 mm. | U |
| M4 | Tenon-mortaise, paramètres saisis : épaisseur 8, largeur 30, décalage en largeur +5, décalage en épaisseur −2 → ajout et enlèvement déplacés d'autant ; `through=True` → tenon de 60 (profondeur de l'hôte) et mortaise débouchante de 60 sans jeu de fond. Refus (`JointError`, gabarit traduit cité dans le message) : longueur + jeu > profondeur sans `through` ; section hors du rectangle de contact ; mortaise qui ne laisse pas au moins une paroi de matière sur chaque face de l'hôte ; contact par la face (`±Z`) ou par le chant (`±Y`) de l'invitée ; pièces séparées ou qui se chevauchent. | U |
| M5 | **Les proportions suivent les pièces** : largeur de T1 = 80 → épaulements arrondi(80 / 6) = 13, tenon de 54 ; M1 large de 80 → tenon de arrondi(53,33) = 53, mortaise de 55 ; épaisseur de T1 = 27 → tenon de 9. Une valeur saisie (≠ 0) ne suit pas. | U |
| M6 | **Rainure-languette** (deux lames 1000 × 100 × 22 chant contre chant, invitée = celle dont le chant `±Y` touche) : languette auto épaisseur 7, longueur **10**, toute la longueur du contact ; rainure profonde de 10 + **1** = 11. Rainure filante par défaut : invitée de 600 sur un hôte de 1000 → rainure sur les 1000 mm de l'hôte ; `through_groove=False` → 600 mm. Contact par un bout (`±X`) accepté (emboîture) ; languette de l'épaisseur entière de l'invitée acceptée (panneau en rainure) si l'hôte garde ses parois (sinon refus comme M4). | U |
| M7 | **Feuillure / logement** : les pièces doivent se chevaucher (sinon refus) ; enlèvement dans l'hôte = boîte commune ; feuillure filante par défaut : la boîte est prolongée sur toute la longueur (X local) de l'hôte ; invitée inchangée. Exemple : côté 600 × 300 × 18, fond de 6 mm logé sur 10 mm de large au bord → enlèvement 600 × 10 × 6. | U |
| M8 | Paramètres = objets valeur immuables (`MortiseTenonParams`, `TongueGrooveParams`, `RabbetParams`, `DowelParams`) validés à la construction : longueurs finies, non booléennes, 0 ≤ x ≤ 20 000 ; décalages finis, \|x\| ≤ 20 000 ; nombre de tourillons entier 0 à 50. `ValueError` citant le champ ; un cas refusé et un cas limite accepté par règle. | U |
| M9 | Registre : à chaque `JointKind` correspond exactement une stratégie (`strategy_for(kind)`), toutes conformes au protocole `JointStrategy` ; aucune branche sur le type dans le code appelant (revue). `resolve(...)` de chaque stratégie renvoie les valeurs effectives (auto résolues) utilisées par le plan et affichées par le panneau. | U + revue |
| M10 | `guess_roles(a, b)` : l'invitée est la pièce dont la face de contact est entièrement couverte (bout de traverse contre chant de montant) ; pour un chevauchement, la pièce la plus mince ; cas symétrique (deux lames identiques bout à bout) → ordre donné conservé. | U |
| M11 | `core/` n'importe ni FreeCAD ni Qt ; couverture de `core/` ≥ 90 % ; aucun module > 400 lignes. | U |

### J3b — Objets du document : pièce usinée et tenon-mortaise (`features/`, `api.py`)

**Premier commit** : refactorisation pure (aucun changement de comportement) des aides de
`wood_part_schema.py` / `wood_part_restore.py` en aides génériques décrites par des données
(`features/schema.py`, § 4.4.4) ; tous les tests J1 passent sans modification.

| N° | Critère | Test |
|---|---|---|
| O1 | Cadre de référence + `make_mortise_tenon` pour (M1, T1), (M2, T1), (M1, T2), (M2, T2) : 4 assemblages, 4 pièces usinées, un seul `doc.recompute()`. Chaque pièce usinée est un solide unique valide ; volume de T1/T2 usinée = 280 × 60 × 22 + 2 × 40 × 40 × 7 = **392 000** mm³, de M1/M2 usinée = 600 × 60 × 22 − 2 × 42 × 40 × 7 = **768 480** mm³ ; `Placement` des pièces usinées = celui de leur brute ; brutes `Visibility` = faux ; forme des assemblages vide. | I |
| O2 | Chaque propriété des tableaux du § 4.4 existe avec type, groupe, infobulle, défaut et mode d'édition indiqués ; `WoodPart` est inchangée (`Version` = 2, mêmes propriétés). | I |
| O3 | Graphe : `OutList` d'un assemblage = ses deux brutes ; `OutList` d'une pièce usinée = sa brute + ses assemblages ; aucun cycle ; après un `recompute()`, aucun objet « Touched ». Créer les quatre assemblages dans l'ordre inverse donne les mêmes volumes. | I |
| O4 | **Le cadre suit** (variante pilotée) : `M1.Width` = 80 → un recompute → tous valides, traverses de 240, volume T usinée = 240 × 60 × 22 + 2 × 53 × 40 × 7 = **346 480**, M usinée = 600 × 80 × 22 − 2 × 55 × 40 × 7 = **1 025 200** ; puis `T1.Width` = 80 → tenons de 54, volume T1 usinée = 240 × 80 × 22 + 2 × 53 × 54 × 7 = **462 468**. | I |
| O5 | Paramètres de l'assemblage : `TenonThickness` = 8 → volumes recalculés (tenon et mortaise de 8) ; `Through` = vrai → mortaise débouchante ; retour à 0 → valeurs automatiques. Une expression sur `TenonThickness` (`<<T1>>.Thickness / 2`) est respectée. | I |
| O6 | Erreurs : T1 écartée de 5 mm → l'assemblage n'est pas valide, `getStatusString()` contient le message traduit « Les pièces ne se touchent pas » ; la pièce usinée est en erreur ou reste « Touched » (jamais de forme partielle) ; aucune exception non rattrapée ; T1 remise en place → tout valide, volumes de O1. Refus avant création dans `make_*` (`TypeError`/`ValueError` traduits, aucun objet créé) : objet qui n'est pas une pièce de bois ni une pièce usinée, même pièce deux fois, pièces de documents ou de conteneurs (`App::Part`, `getParentGeoFeatureGroup`) différents. | I |
| O7 | `make_mortise_tenon` accepte une pièce usinée à la place de sa brute ; un second assemblage sur une pièce déjà usinée réutilise sa pièce usinée (une seule par brute). `machined_part_of(brute)` et `blank_of(objet)` renvoient l'objet attendu. | I |
| O8 | Enregistrer, fermer, rouvrir : propriétés identiques, objets valides, volumes inchangés, aucun objet « Touched ». Proxies `freecad.menuiserie.features.machined_part.MachinedPart` et `freecad.menuiserie.features.joints.mortise_tenon.MortiseTenonJoint`, `dumps()` = `None`, `Version` = 1. | I |
| O9 | Réouverture contrôlée (règles de l'ADR 0003, aides génériques partagées) : `Version` absente → propriétés manquantes recréées, `Version` = 1 ; `Version` = 2 → avertissement « version plus récente », rien de migré ; propriété d'un type inattendu → recréée avec avertissement. | I |
| O10 | Annuler / rétablir : création d'un assemblage dans une transaction → `undo()` supprime l'assemblage **et** la pièce usinée créée avec lui, la brute est de nouveau visible ; `redo()` les restaure, volumes de O1. Modification de `TenonThickness` annulable. *(À vérifier en début de lot : `Visibility` est-elle enregistrée dans la transaction en 1.0 et 1.1 ? Sinon, le signaler à l'architecte avant de contourner.)* | I |
| O11 | Suppression : supprimer un assemblage (`doc.removeObject`) → la pièce usinée est recalculée sans lui ; `remove_machined_part(p)` (API) supprime une pièce usinée **sans assemblage** et réaffiche sa brute ; supprimer une brute → ses assemblages passent en erreur et sa pièce usinée est en erreur ou reste « Touched » (comme O6), sans exception. | I |
| O12 | Les documents J1 s'ouvrent sans changement (pièces, `Version` = 2, rien de « Touched ») ; `record_of(brute)` est inchangé pour une pièce assemblée (J2 lit la brute). | I |
| O13 | **Compatibilité (ADR 0007)** : la forme d'une pièce usinée sert d'outil et de base d'un `Part::Cut` ordinaire (volume attendu) et de source d'une vue TechDraw (`TechDraw::DrawViewPart` sur une page avec `Template` vide) qui se recalcule sans erreur ; elle s'exporte en STEP et se réimporte avec le même volume (à 1e-6 près relatif). | I (TechDraw : ignoré si non importable dans `freecadcmd`, alors G) |
| O14 | **Compatibilité (ADR 0007)** : le cadre de O1 enregistré puis ouvert dans un `freecadcmd` **sans l'atelier** (sous-processus, `sys.path` sans `freecad.menuiserie`) : le document s'ouvre, chaque pièce usinée a une forme valide de même volume. Test d'inventaire : toute commande enregistrée par l'atelier commence par `Menuiserie_`, tout `TYPE` de proxy par `Menuiserie::`, aucun module hors de `freecad.menuiserie` ; `pyproject.toml` ne déclare aucune dépendance d'exécution. | I + U |

### J3c — Rainure-languette, feuillure, tourillons (`core/joints/dowels.py`, `features/joints/`)

| N° | Critère | Test |
|---|---|---|
| R1 | `make_tongue_groove` et `make_rabbet` : objets aux propriétés du § 4.4.3, volumes conformes à M6 et M7 dans le document, réouverture et annulation comme O8 et O10, proxies `…features.joints.tongue_groove.TongueGrooveJoint` et `…features.joints.rabbet.RabbetJoint`. | I |
| R2 | Cadre et panneau : panneau de 10 mm logé en rainure-languette (languette de 10 mm d'épaisseur) dans un montant de 22 → rainure de 10 × 11 filante ; changer la largeur du panneau par expression → la rainure suit. | I |
| T1 | **Tourillons, valeurs automatiques** : diamètre = plus grand de 6, 8, 10, 12 ne dépassant pas la moitié de l'épaisseur au contact et dont le perçage, décalage dans l'épaisseur compris, reste dans cette épaisseur (rayon + \|décalage\| < demi-épaisseur − 0,01) (22 → **10**, 18 → **8**, 16 → 8, 12 → **6** ; 22 décalé de 6 → 8 ; 10 → refus « pièces trop minces pour des tourillons », 12 mm au moins sans décalage) ; longueur selon le diamètre : 6 → 30, 8 → **35**, 10 → 40, 12 → 50 (diamètre saisi hors de ces valeurs : longueur du plus grand diamètre du commerce qui ne le dépasse pas, 30 en dessous de 6) ; profondeur dans l'hôte = moitié de la longueur ; perçages = profondeur + **1** de jeu de fond de chaque côté ; distance au bord = 2 × diamètre ; nombre = 1 (au milieu) si contact − 2 × distance ≤ diamètre + 0,01, sinon min(50, max(2, ⌈(contact − 2 × distance) / 128⌉ + 1)) (plafonné à `MAX_DOWEL_COUNT` = 50 : contact de 20 m → 50 tourillons, entraxe alors supérieur à 128 mm), réduit tant que l'entraxe serait ≤ diamètre + 0,01 : le nombre automatique n'est jamais refusé pour l'entraxe (traverse de 45 × 22 → 1 tourillon) ; répartis régulièrement ; centrés dans l'épaisseur. Exemples : contact 60 × 22 → 2 tourillons Ø 10 × 40 à 20 et 40 mm ; contact 300 × 18 → 4 tourillons Ø 8 × 35 à 16, 105,33, 194,67 et 284 mm. | U |
| T2 | Tourillons, paramètres saisis (diamètre, longueur, profondeur dans l'hôte, nombre, distance au bord, décalage) respectés ; refus : perçage qui traverse ou laisse moins de 3 mm de fond, diamètre ≥ épaisseur au contact, profondeur ≥ longueur, nombre qui ne tient pas. | U |
| T3 | `make_dowels` dans le document : la forme de l'assemblage est l'ensemble des tourillons (cylindres), les deux pièces usinées sont percées ; volume = brute − perçages. | I |
| T4 | **Le nombre suit** (exigence de jv) : contact passé de 60 à 300 mm par une expression sur la largeur de la pièce → un recompute → 4 tourillons, perçages recalculés ; `Count` saisi à 3 → toujours 3. | I |
| T5 | Proxy `…features.joints.dowels.DowelJoint`, réouverture et annulation comme O8 et O10 ; O13 et O14 vérifiés aussi sur un document avec rainure-languette, feuillure et tourillons. | I |

### J3d — Affichage et commandes (`gui/`)

| N° | Critère | Test |
|---|---|---|
| C1 | Commandes `Menuiserie_MortiseTenon` (« Tenon-mortaise »), `Menuiserie_TongueGroove` (« Rainure-languette »), `Menuiserie_Rabbet` (« Feuillure »), `Menuiserie_Dowels` (« Tourillons ») dans la barre d'outils et le menu Menuiserie, avec les icônes existantes ; actives seulement si exactement deux pièces (brutes ou usinées) distinctes sont sélectionnées et qu'aucun panneau n'est ouvert. | G |
| C2 | Lancer une commande sur M1 puis T1 (dans un ordre ou l'autre : rôles par `guess_roles`) crée l'assemblage et ouvre son panneau (J3e ; avant J3e : recalcul seul) ; **une** entrée d'annulation « Créer un assemblage tenon-mortaise » (idem par type). | G |
| C3 | Pièce usinée : icône de la pièce de bois, couleur et texture de la brute (mêmes nœuds que J1d), mises à jour quand le matériau ou le fil de la brute change ; la brute apparaît sous elle dans l'arbre. | G |
| C4 | Double-clic sur une pièce usinée : ouvre le panneau J1c de sa **brute** (titre « Modifier « <Label de la brute> » ») ; la vue 3D montre la pièce usinée mise à jour en direct. | G |
| C5 | Déplacer une pièce usinée (modification de `Placement` par l'éditeur de propriétés ou l'outil Transformer) déplace sa brute, en une entrée d'annulation (sous réserve de Q4). | G + I |
| C6 | Assemblages dans l'arbre avec l'icône de leur type ; tourillons affichés couleur hêtre (`#D9B48A`, ou couleur de `hetre` de la bibliothèque). | G |
| C7 | Aucun observateur global laissé en place après une commande ou un panneau ; aucune préférence écrite hors de `Mod/Menuiserie` (ADR 0007). | G + revue |

### J3e — Panneau de tâche d'un assemblage (`gui/task_panels/`)

| N° | Critère | Test |
|---|---|---|
| E1 | Panneau commun aux quatre types, construit d'après la description des paramètres (pas un `.ui` par type) : pièces reliées (libellés), bouton « Inverser », et pour chaque paramètre une case « Auto » et un champ d'unité ; en mode auto, le champ est inactif et montre la valeur effective (`resolve`). | G |
| E2 | Chaque modification est visible immédiatement ; « OK » crée une entrée d'annulation (« Créer… » en création, « Modifier un assemblage » sinon) ; « Annuler » en création ne laisse ni assemblage ni pièce usinée créée ni entrée d'annulation, et la brute est de nouveau visible ; en modification, rétablit les valeurs. | G |
| E3 | Une erreur d'assemblage (ex. tenon trop long) s'affiche dans le panneau (message traduit), « OK » reste possible et laisse l'assemblage en erreur. | G |
| E4 | Paramètre piloté par une expression : champ inactif, jamais écrit (règle C6 de J1). | G |
| E5 | Double-clic sur un assemblage : ouvre son panneau. | G |
| E6 | Scénario du livrable sur FreeCAD 1.0 et 1.1 : cadre de référence dessiné à la main, quatre tenons-mortaises par la commande, changement de largeur des montants et traverses, annuler, rétablir, enregistrer, rouvrir ; vue TechDraw d'un montant (mortaises visibles en traits cachés) ; captures dans la PR. | manuel |
| E7 | Chaînes traduisibles, `from PySide import …` seulement. | revue + test d'imports |

## 4. Conception

### 4.1 Principe (ADR 0006)

- **Pièce brute** = `WoodPart` de J1, inchangée : cotes, matériau, fil, débit.
- **Assemblage** = objet par assemblage, qui lie deux pièces brutes et calcule un **plan
  d'usinage** (ajouts et enlèvements dans le repère local de chaque pièce) à partir des seules
  pièces brutes et de ses paramètres.
- **Pièce usinée** = objet par pièce assemblée, qui lie sa brute et ses assemblages ; forme =
  (boîte de la brute ∪ ajouts) − enlèvements, placée au `Placement` de la brute. Elle est
  affichée ; la brute est masquée et apparaît sous elle dans l'arbre.

Le tenon et la languette sont **ajoutés** à la pièce brute : on dessine les pièces à leurs cotes
visibles (traverse entre les montants, de chant à chant) et l'assemblage ajoute le tenon (Q1).
Mortaises, rainures, feuillures et perçages sont enlevés. La feuillure (ou logement) suppose que
l'invitée occupe déjà la place logée (chevauchement) ; les autres types supposent un **contact**.

```
freecad/menuiserie/
├── core/
│   ├── i18n.py                  J3a  + TemplatedError (base de InvalidDimensionsError et JointError)
│   ├── geometry.py              J3a  Vec3, Box, Cylinder, RigidTransform, axes, JointError
│   ├── contact.py               J3c  Contact, Overlap, Separated, classify (extrait de geometry.py, M11)
│   └── joints/
│       ├── __init__.py          J3a  façade : JointKind, JointPlan, JointError, JointStrategy, strategy_for, guess_roles, mm_round
│       ├── _base.py             J3a  protocole JointStrategy, paramètres validés, arrondis et règles communes
│       ├── _registry.py         J3a  registre figé des stratégies, strategy_for
│       ├── _roles.py            J3a  guess_roles
│       ├── _profile.py          J3a  profil commun tenon / languette (section, longueur, logement)
│       ├── mortise_tenon.py     J3a  MortiseTenonParams, MortiseTenonStrategy
│       ├── tongue_groove.py     J3a  TongueGrooveParams, TongueGrooveStrategy
│       ├── rabbet.py            J3a  RabbetParams, RabbetStrategy
│       └── dowels.py            J3a  DowelParams ; J3c  DowelStrategy, JointKind.DOWELS
├── features/
│   ├── schema.py                J3b  PropertySpec générique, ajout / contrôle / migration (extrait de wood_part_*)
│   ├── solids.py                J3b  conversion Box / Cylinder (core) → formes Part
│   ├── machined_part.py         J3b  proxy MachinedPart, create / find / remove
│   └── joints/
│       ├── __init__.py          J3b  vide (évite le cycle machined_part → joints.base → fabriques)
│       ├── factories.py         J3b  fabriques create_*, JOINT_CLASSES
│       ├── base.py              J3b  JointFeature (Template Method), placed_blank, plan_for
│       ├── mortise_tenon.py     J3b  MortiseTenonJoint
│       ├── tongue_groove.py     J3c  TongueGrooveJoint
│       ├── rabbet.py            J3c  RabbetJoint
│       └── dowels.py            J3c  DowelJoint
├── api.py                       J3b  make_mortise_tenon ; J3c : make_tongue_groove, make_rabbet, make_dowels
└── gui/
    ├── part_appearance.py       J3d  couleur / texture d'une pièce (extrait du ViewProvider J1)
    ├── view_providers/machined_part.py  J3d
    ├── view_providers/joint.py  J3d
    ├── commands/joints.py       J3d  JointCommand (base) + 4 commandes
    └── task_panels/
        ├── base.py              J3e  ObjectTaskPanel : transactions, fermeture forcée, surveillance (ADR 0005), partagé avec J1c
        ├── joint_fields.py      J3e  ParamField : un champ par PropertySpec (cote, nombre, booléen, case « Auto »)
        └── joint.py             J3e  JointTaskPanel
```

### 4.2 Design patterns retenus

| Besoin | Pattern | Justification |
|---|---|---|
| Quatre types d'assemblage en J3, deux de plus en J4 | **Strategy + registre** (`core/joints`) | point d'extension prévu par la feuille de route ; aucune chaîne de `if kind == …` |
| Squelette commun des objets assemblage | **Template Method** (`JointFeature`) | quatre variantes : propriétés communes, lecture des brutes, `execute`, réouverture fixés par la base ; chaque sous-classe fournit `KIND`, `PROPERTIES` et `params(obj)` |
| Données d'assemblage | **objets valeur** immuables (`…Params`, `JointPlan`, `Box`, `Cylinder`) | testables, validés à la construction |
| Création | **Fabrique** par type (`create_mortise_tenon`…, `make_…`) | utilisée par commandes, scripts et tests |
| Objets du document | **Proxy** FeaturePython + ViewProvider séparé | règle du projet |
| Quatre commandes | **Command** + base `JointCommand` | une classe par commande, sans duplication |
| Apparence partagée pièce / pièce usinée | **composition** (`PartAppearance`) | évite d'hériter du ViewProvider J1 |

### 4.3 `core/` (J3a ; tourillons en J3c)

#### 4.3.1 `core/geometry.py` et `core/contact.py`

```python
CONTACT_TOLERANCE_MM: Final = 0.01
ANGLE_TOLERANCE: Final = 1e-6  # écart toléré des coefficients de la matrice à {-1, 0, 1}


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float


class Axis(Enum):  # face ou direction dans un repère local
    X_POS = "+X"
    X_NEG = "-X"
    Y_POS = "+Y"
    Y_NEG = "-Y"
    Z_POS = "+Z"
    Z_NEG = "-Z"


@dataclass(frozen=True)
class Box:  # boîte alignée sur les axes d'un repère, min <= max sur chaque axe (aplatie permise : rectangle de contact)
    min: Vec3
    max: Vec3


@dataclass(frozen=True)
class Cylinder:  # base au centre d'une face, axe signé, rayon et hauteur > 0
    base: Vec3
    axis: Axis
    radius: float
    height: float


Solid = Box | Cylinder


@dataclass(frozen=True)
class RigidTransform:
    rotation: tuple[
        tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]
    ]
    translation: Vec3

    @classmethod
    def from_matrix(
        cls, rows: Sequence[Sequence[float]]
    ) -> RigidTransform: ...  # 4 × 4, Placement.toMatrix()
    def inverse(self) -> RigidTransform: ...
    def compose(self, other: RigidTransform) -> RigidTransform: ...
    def apply(self, point: Vec3) -> Vec3: ...


@dataclass(frozen=True)
class PlacedBlock:  # pièce brute vue par core : cotes finies (Dimensions) + Placement
    dimensions: Dimensions
    placement: RigidTransform

    def local_box(self) -> Box: ...  # [0, L] × [0, l] × [0, e]


def relative_axes(
    host: PlacedBlock, guest: PlacedBlock
) -> tuple[Axis, Axis, Axis]: ...  # JointError si pas d'équerre
def to_host(host, guest, solid: Solid) -> Solid: ...  # repère invitée → repère hôte (et to_guest)


# core/contact.py (sorti de geometry.py en J3c pour rester sous 400 lignes, M11)
@dataclass(frozen=True)
class Contact:
    guest_face: Axis
    host_face: Axis
    rectangle: Box  # aplati, repère de l'invitée
    host_depth: float  # étendue de l'hôte dans l'axe normal au contact


@dataclass(frozen=True)
class Overlap:
    common: Box  # repère de l'hôte


class Separated: ...


def classify(host: PlacedBlock, guest: PlacedBlock) -> Contact | Overlap | Separated: ...
```

Tous les calculs se font dans le repère local de l'hôte, après avoir exprimé l'invitée dans ce
repère : seule la rotation **relative** doit être d'équerre ; le cadre peut être tourné
n'importe comment dans l'espace. `features/` convertit `Placement` en `RigidTransform` par
`Placement.toMatrix()` ; `core/` ne connaît pas FreeCAD.

#### 4.3.2 `core/joints/` : protocole, plan, registre

```python
class JointKind(str, Enum):  # non enregistré dans les documents (le chemin du proxy l'est)
    MORTISE_TENON = "MortiseTenon"
    TONGUE_GROOVE = "TongueGroove"
    RABBET = "Rabbet"
    DOWELS = "Dowels"  # ajouté en J3c avec DowelStrategy (M9 : une stratégie par type)


class JointError(TemplatedError):  # défini dans geometry.py (levé par relative_axes), ré-exporté
    template: str  # gabarit QT_TRANSLATE_NOOP
    params: Mapping[str, str]


@dataclass(frozen=True)
class JointPlan:
    host_cuts: tuple[Solid, ...]  # repère local de l'hôte
    host_additions: tuple[Solid, ...]
    guest_cuts: tuple[Solid, ...]  # repère local de l'invitée
    guest_additions: tuple[Solid, ...]
    inserts: tuple[Solid, ...]  # pièces rapportées (tourillons), repère de l'hôte


class JointStrategy(Protocol[P, R]):
    kind: ClassVar[JointKind]

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: P
    ) -> R: ...  # valeurs effectives
    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: P) -> JointPlan: ...


def strategy_for(kind: JointKind) -> JointStrategy[Any, Any]: ...  # registre figé (Mapping)
def guess_roles(a: PlacedBlock, b: PlacedBlock) -> tuple[int, int]: ...  # indices (hôte, invitée)
def mm_round(value: float) -> float: ...  # floor(x + 0,5), au moins 1
```

`_profile.py` porte le calcul partagé tenon / languette (section dans le rectangle de contact,
décalages, longueur, logement avec jeu de fond, débouchant ou non, filant ou non, contrôle des
parois) : tenon-mortaise et rainure-languette n'en diffèrent que par leurs valeurs automatiques
(épaulements, longueur) et le prolongement filant ; c'est ce qui garde `pylint duplicate-code` vert.

#### 4.3.3 Paramètres et valeurs par défaut de menuisier

Convention : **0 = automatique** pour toute cote qui dépend des pièces (Q2) ; la valeur
automatique est recalculée à chaque recalcul, donc suit les pièces ; une valeur saisie est fixe.
Ajustement serré : aucun jeu latéral (Q3).

| Type | Paramètre (`core` / propriété) | Défaut | Règle automatique |
|---|---|---|---|
| Tenon-mortaise | `tenon_thickness` / `TenonThickness` | 0 | ⅓ de l'épaisseur au contact, arrondi au mm (22 → 7, 27 → 9) |
| | `tenon_width` / `TenonWidth` | 0 | largeur au contact − 2 épaulements de ⅙ de cette largeur arrondis au mm (60 → 40) |
| | `tenon_length` / `TenonLength` | 0 | ⅔ de la profondeur de la pièce mortaisée, arrondi au mm (60 → 40) |
| | `width_offset` / `WidthOffset`, `thickness_offset` / `ThicknessOffset` | 0 | centré |
| | `through` / `Through` | faux | traversant : tenon = profondeur de l'hôte, mortaise débouchante sans jeu |
| | `mortise_clearance` / `MortiseClearance` | 2 mm | jeu de fond de la mortaise |
| Rainure-languette | `tongue_thickness` / `TongueThickness` | 0 | ⅓ de l'épaisseur au contact, arrondi |
| | `tongue_length` / `TongueLength` | 10 mm | — |
| | `thickness_offset` / `ThicknessOffset` | 0 | centrée |
| | `groove_clearance` / `GrooveClearance` | 1 mm | jeu de fond de la rainure |
| | `through_groove` / `ThroughGroove` | vrai | rainure filante sur toute l'étendue de l'hôte le long du contact |
| Feuillure / logement | `through` / `Through` | vrai | prolongée sur toute la longueur (X) de l'hôte |
| Tourillons | `diameter` / `Diameter` | 0 | plus grand de 6, 8, 10, 12 ≤ ½ épaisseur au contact, perçage dans l'épaisseur décalage compris |
| | `dowel_length` / `DowelLength` | 0 | 6 → 30, 8 → 35, 10 → 40, 12 → 50 ; autre diamètre : celle du plus grand diamètre du commerce qui ne le dépasse pas (30 en dessous de 6) |
| | `host_depth` / `HostDepth` | 0 | moitié de la longueur |
| | `count` / `Count` | 0 | voir T1 (entraxe au plus 128 mm, 50 au plus, au moins 2 si la place le permet, jamais refusé pour l'entraxe) |
| | `edge_distance` / `EdgeDistance` | 0 | 2 × diamètre |
| | `thickness_offset` / `ThicknessOffset` | 0 | centrés |
| | `hole_clearance` / `HoleClearance` | 1 mm | jeu de fond de chaque perçage |

Contraintes de forme : contact par le bout (`±X`) pour le tenon ; bout ou chant (`±X`, `±Y`) pour
la languette et les tourillons ; jamais par la face (`±Z`). Épaisseur du tenon et de la languette
mesurée selon l'axe Z local de l'invitée.

### 4.4 `features/` (J3b ; J3c pour les trois autres types)

#### 4.4.1 Pièce usinée `MachinedPart` (`Part::FeaturePython`, nom interne `MachinedPart`)

| Propriété | Type | Groupe | Défaut | Édition | Infobulle |
|---|---|---|---|---|---|
| `Base` | `App::PropertyLink` | Pièce | brute | lecture seule | Pièce de bois brute (cotes, matériau, fil) dont cette pièce est usinée. |
| `Joints` | `App::PropertyLinkList` | Pièce | `[]` | lecture seule | Assemblages qui usinent cette pièce (tenons, mortaises, rainures, perçages). |
| `Version` | `App::PropertyInteger` | Base | 1 | masquée | Version du modèle de données de la pièce usinée, utilisée pour migrer les anciens fichiers. |

`Label` = « {label} (usinée) » (gabarit traduisible, `{label}` = libellé de la brute) à la
création ; la brute garde le sien ; jamais de modification de `DuplicateLabels` (ADR 0007). `execute()` : lit `Base` (doit être une `WoodPart`,
sinon erreur traduite) et, pour chaque assemblage, `plan_for(joint)` puis le côté (hôte ou
invitée) qui correspond à `Base` ; forme = `makeBox` ∪ ajouts − enlèvements, `removeSplitter()`,
puis `Shape.Placement = Base.Placement` (reconstruction de la forme seulement). Un plan en erreur
lève le même message que l'assemblage. `onChanged("Placement")` hors recalcul, restauration et
annulation : reporte la valeur sur `Base.Placement` (Q4).

```python
def create_machined_part(blank: DocumentObject) -> DocumentObject: ...  # masque la brute
def machined_part_of(blank: DocumentObject) -> DocumentObject | None: ...  # d'après blank.InList
def ensure_machined_part(blank: DocumentObject) -> DocumentObject: ...
def blank_of(
    obj: DocumentObject,
) -> DocumentObject: ...  # WoodPart → elle-même, MachinedPart → Base ; TypeError sinon
def remove_machined_part(
    machined: DocumentObject,
) -> None: ...  # refus s'il reste des assemblages ; réaffiche la brute
def removal_refusal(
    machined: DocumentObject,
) -> str | None: ...  # message traduit du refus (ViewProvider, onDelete), None si permis
def is_machined_part(obj: object) -> bool: ...
```

#### 4.4.2 Base des assemblages `JointFeature` (Template Method)

Propriétés communes (groupe « Assemblage ») :

| Propriété | Type | Défaut | Édition | Infobulle |
|---|---|---|---|---|
| `HostPart` | `App::PropertyLink` | — | lecture seule | Pièce qui reçoit l'assemblage : mortaise, rainure, feuillure, ou premier côté percé. |
| `GuestPart` | `App::PropertyLink` | — | lecture seule | Pièce qui porte le tenon ou la languette, se loge dans la feuillure, ou second côté percé. |
| `Version` | `App::PropertyInteger` (groupe Base) | 1 | masquée | Version du modèle de données de l'assemblage, utilisée pour migrer les anciens fichiers. |

```python
class JointFeature:
    KIND: ClassVar[JointKind]; TYPE: ClassVar[str]; VERSION: ClassVar[int] = 1
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]]           # propres au type
    def __init__(self, obj: DocumentObject) -> None: ...      # communes + PROPERTIES
    def execute(self, obj: DocumentObject) -> None: ...       # plan_for → forme = inserts (vide sinon), Placement de l'hôte
    def onDocumentRestored(self, obj: DocumentObject) -> None: ...  # aides génériques (schema.py)
    def dumps(self) -> None: ...; def loads(self, state: object) -> None: ...
    def params(self, obj: DocumentObject) -> Any: ...         # étape fournie par la sous-classe

def plan_for(joint: DocumentObject) -> JointPlan: ...   # ValueError traduit (JointError, brutes invalides)
def resolved_for(joint: DocumentObject) -> object: ...  # valeurs effectives pour le panneau
def create_mortise_tenon(doc, host, guest, **params) -> DocumentObject: ...  # sans transaction ni recalcul
```

`HostPart` et `GuestPart` sont en lecture seule dans l'éditeur de propriétés (défaut D1) :
changer une pièce d'un assemblage demanderait de mettre à jour les `Joints` des pièces usinées.
L'inversion hôte / invitée reste possible par le bouton « Inverser » du panneau (les deux pièces
restent les mêmes). Si un script modifie quand même l'une d'elles, `execute` de l'assemblage
lève une `ValueError` traduite (« Les pièces de l'assemblage « … » ne correspondent plus à ses
pièces usinées : supprimez l'assemblage puis recréez-le. ») lorsque les brutes des pièces
usinées qui le listent ne sont pas exactement `HostPart` et `GuestPart` ; la pièce usinée qui
liste un assemblage qui ne la relie plus lève la même erreur. Aucune forme partielle : les
pièces usinées gardent leur forme précédente.

Les fabriques valident (deux pièces distinctes, `WoodPart` ou `MachinedPart`, même document,
même conteneur), résolvent les brutes, créent l'assemblage, puis `ensure_machined_part` pour
chaque brute et ajoutent l'assemblage à leurs `Joints`. `api.make_…` ajoutent les ViewProviders
si `App.GuiUp` (à partir de J3d) et recalculent, comme `make_wood_part`.

#### 4.4.3 Propriétés par type

Groupes « Tenon » / « Mortaise », « Languette » / « Rainure », « Feuillure », « Tourillons ».
Longueurs : `App::PropertyLength` ; décalages : `App::PropertyDistance` ; booléens :
`App::PropertyBool` ; `Count` : `App::PropertyIntegerConstraint` (0 à 50). Noms et défauts : § 4.3.3.
Infobulles (extrait ; les autres sur le même modèle, toutes en `QT_TRANSLATE_NOOP("App::Property", …)`) :

- `TenonThickness` : « Épaisseur du tenon. 0 : automatique, un tiers de l'épaisseur de la pièce à
  tenon arrondi au mm. »
- `TenonWidth` : « Largeur du tenon. 0 : automatique, largeur de la pièce moins deux épaulements
  d'un sixième. »
- `TenonLength` : « Longueur du tenon, ajoutée au bout de la pièce. 0 : automatique, deux tiers de
  la profondeur de la pièce mortaisée. »
- `Through` : « Tenon traversant : la mortaise débouche de l'autre côté de la pièce. »
- `MortiseClearance` : « Jeu de fond : profondeur de la mortaise au-delà du bout du tenon. »
- `Count` : « Nombre de tourillons. 0 : automatique, selon la longueur du contact (entraxe de
  128 mm au plus). »

#### 4.4.4 `features/schema.py` (refactorisation, premier commit de J3b)

`PropertySpec(name, type_id, group, tooltip, default=None, mode=EDITABLE, label="", resolved="")`
(`label` : libellé du champ du panneau J3e, gabarit traduisible ; `resolved` : nom de la valeur
effective dans le résultat de `resolve` pour un paramètre « 0 = automatique », qui reçoit une case
« Auto »), `version_spec(tooltip,
version)` et les fonctions `add_missing_properties(obj, specs, defaults=None, choices=None)`
(`choices` : listes des énumérations), `remove_mistyped_properties(obj, specs, noun)`,
`restored_version(obj, current, noun)`, `apply_editor_modes(obj, specs)` et
`restore_schema(obj, specs, current, noun)` (réouverture des objets sans énumération) sortent de
`wood_part_schema.py` / `wood_part_restore.py` sous forme générique ; la pièce de bois les
appelle avec sa description (comportement, messages et tests J1 inchangés). Les messages de
réouverture citent « Pièce », « Pièce usinée » ou « Assemblage » selon l'objet (`noun`, gabarit
traduisible).

### 4.5 Ordre de recalcul, dépendances, réouverture, annuler / rétablir

- **Graphe** : brutes (et leurs expressions) → assemblages (`HostPart`, `GuestPart`, expressions
  des paramètres) → pièces usinées (`Base`, `Joints`). Un seul `recompute()` suffit, y compris
  quand une cote de brute est pilotée par une expression (évaluée au recalcul de la brute, avant
  l'assemblage). Aucun objet n'écrit dans un autre pendant `execute()`.
- **Suivi** : changer une cote ou le `Placement` d'une brute marque la brute, donc ses assemblages
  et les pièces usinées concernées ; les valeurs automatiques (y compris le nombre de tourillons)
  sont recalculées. Un assemblage ne déplace ni ne redimensionne jamais une pièce.
- **Réouverture** : proxies sans état ; `onDocumentRestored` contrôle `Version` et types (ADR 0003)
  sans recalcul ; aucun objet « Touched » ; formes relues du fichier.
- **Annuler / rétablir** : chaque commande = une transaction (création de l'assemblage, de la ou
  des pièces usinées, liens et masquage des brutes) ; les proxies n'ont pas d'état, FreeCAD
  restaure les propriétés. Les reports de `Placement` (Q4) et les mises à jour de `Joints` se
  font dans la transaction de l'appelant et jamais pendant `Transacting`.
- **Suppression** : FreeCAD retire un assemblage supprimé des `Joints` qui le citent ; le
  ViewProvider de la pièce usinée réaffiche la brute quand on supprime la pièce usinée
  (`onDelete`), refusé s'il reste des assemblages (message).

### 4.6 Affichage (J3d)

- `ViewProviderMachinedPart` (chemin figé `freecad.menuiserie.gui.view_providers.machined_part`) :
  icône `Menuiserie_WoodPart.svg`, `claimChildren` = [brute], apparence par `PartAppearance`
  (extrait de `ViewProviderWoodPart` : couleur `MaterialColor`, texture J1d), lue sur la brute ;
  `setEdit` ouvre le panneau J1c de la brute ; `onDelete` comme § 4.5.
- `ViewProviderJoint` (`…gui.view_providers.joint`) : icône selon le type
  (`Menuiserie_MortiseTenon.svg`, `Menuiserie_TongueGroove.svg`, `Menuiserie_Rabbet.svg`,
  `Menuiserie_Dowels.svg`, déjà générées) ; couleur hêtre ; double-clic → panneau (J3e).
- Les ViewProviders sans `Version` suivent la règle de l'ADR 0003 (`finishRestoring`).

### 4.7 Commandes et panneau (J3d, J3e)

`JointCommand` (base) : `NAME`, `FACTORY` (référence directe à la fabrique `api.make_…`), textes,
icône ; `IsActive` (deux pièces sélectionnées, pas de panneau ouvert) ; `Activated` :
`guess_roles`, transaction « Créer un assemblage … », fabrique (ViewProviders posés par l'api),
panneau en création. Un refus de la fabrique (`TypeError`, `ValueError`) abandonne la transaction
et s'affiche dans la barre d'état et la vue rapport. Quatre sous-classes.

`JointTaskPanel` (`task_panels/joint.py`) : formulaire construit en code d'après les `PropertySpec`
du type (`label`, case « Auto » si `resolved`) ; libellés des deux pièces, « Inverser » échange
`HostPart` et `GuestPart` ; chaque saisie est écrite puis l'assemblage et ce qui en dépend sont
recalculés (aperçu, sans les pages TechDraw ni les autres documents) ; une erreur de `plan_for`
s'affiche sous les champs. Cycle de vie commun avec le panneau J1c dans `task_panels/base.py`
(`ObjectTaskPanel`, `show_panel`, `start_editing`, `close_transaction`, `DeletionWatcher`) ; l'objet
mis en mode édition (la pièce usinée pour sa brute) est mémorisé à l'ouverture pour quitter
l'édition après une fermeture forcée même si son lien vers la brute a disparu.

### 4.8 Sécurité

Aucune lecture de fichier ni entrée externe nouvelle hors du document ; les valeurs relues d'un
document sont contrôlées (types, bornes de M8 appliquées par `params(obj)`, messages avec
`quoted_value`) ; un plan géométrique absurde lève `JointError`, jamais d'exception OCC non
rattrapée dans `execute()` (les erreurs de booléenne sont converties en message traduit).

### 4.9 Compatibilité avec les autres ateliers (exigence de jv, ADR 0007)

- Pièces usinées et assemblages sont des `Part::FeaturePython` dont la `Shape` est un solide
  ordinaire, enregistré dans le `.FCStd` : TechDraw, `Part::Cut`, Assembly intégré (FreeCAD 1.x),
  BIM, CAM et l'export STEP les utilisent sans connaître l'atelier (O13). La brute reste aussi un
  `Part::Feature` valide (parallélépipède).
- Document lisible sans l'atelier, formes valides (O14).
- Aucune modification globale : pas d'observateur permanent (le `DeletionWatcher` vit le temps du
  panneau), pas de préférence hors de `Mod/Menuiserie`, aucune modification d'objets d'autres
  ateliers ; seule la brute est masquée sous sa pièce usinée.
- Espace de noms : commandes `Menuiserie_…`, types `Menuiserie::MachinedPart`,
  `Menuiserie::MortiseTenon`, `Menuiserie::TongueGroove`, `Menuiserie::Rabbet`,
  `Menuiserie::Dowels` ; aucun objet nommé « Assembly » ni « Joint » nu (noms internes
  `MachinedPart`, `MortiseTenon`, `TongueGroove`, `Rabbet`, `Dowels`) ; coexistence avec l'addon
  Woodworking sans conflit (préfixes distincts ; à vérifier à la main en E6 si installé).
- Aucune dépendance Python ajoutée.

## 5. Découpage en PR

| Lot | Branche | Contenu | Diff estimé hors tests | Critères |
|---|---|---|---|---|
| **J3a** | `feat/assemblages-core` | `core/geometry.py` (dont `classify`, sorti en J3c dans `core/contact.py`), `core/joints/` (base, profil, tenon-mortaise, rainure-languette, feuillure), ADR déjà acceptés (PR #18) | ≈ 400 | M1–M11 |
| **J3b** | `feat/assemblages-document` | refactorisation `features/schema.py` (commit séparé, ≈ 60 lignes nettes), `solids.py`, `machined_part.py`, `joints/base.py`, `joints/mortise_tenon.py`, `api.make_mortise_tenon`, CHANGELOG | ≈ 380 | O1–O14 |
| **J3c** | `feat/assemblages-types` | `core/joints/dowels.py`, `features/joints/tongue_groove.py`, `rabbet.py`, `dowels.py`, fabriques et `api` | ≈ 350 | R1–R2, T1–T5 |
| **J3d** | `feat/assemblages-affichage` | `gui/part_appearance.py` (extraction), deux ViewProviders, `commands/joints.py`, `init_gui.py`, ajout des ViewProviders dans `api` | ≈ 300 | C1–C7 |
| **J3e** | `feat/assemblages-panneau` | `task_panels/joint.py`, module partagé de transaction, recette manuelle, README « Assembler deux pièces » | ≈ 300 | E1–E7 |

J3c et J3d partent de `main` après J3b et sont indépendants ; les commandes des types de J3c sont
ajoutées par celui des deux lots fusionné en second (une ligne par type). J3b atteint déjà le
livrable par la console (pièces usinées affichées avec le ViewProvider Part par défaut) ; J3d
ajoute couleur, texture et commandes ; J3e le réglage graphique.

## 6. Compatibilité

- **Documents J1** : `WoodPart` inchangée (`Version` 2, mêmes propriétés) : aucune migration (O12).
- **Nouveaux objets** : `MachinedPart` et les quatre assemblages naissent en `Version` 1 avec le
  contrat de l'ADR 0003 (chemins figés, proxies sans état, migration à la réouverture, ajout en fin
  d'énumération seulement, aucune énumération en J3).
- **Document J3 ouvert par un atelier J1** : proxies introuvables signalés par FreeCAD ; formes
  enregistrées affichées, non recalculables ; les brutes restent des pièces J1 complètes.
- **Document ouvert sans l'atelier** : formes valides (O14, ADR 0007).
- **J2 (liste de débit)** : lit les brutes (`record_of`) ; la longueur de débit d'une traverse
  devra ajouter ses tenons (`JointPlan.guest_additions`) : prévu en J2, pas en J3.
- **FreeCAD 1.0 et 1.1** : `Part.makeBox`, `makeCylinder`, `fuse`, `cut`, `removeSplitter`,
  `Placement.toMatrix`, `App::PropertyIntegerConstraint`, `getParentGeoFeatureGroup` existent dans
  les deux ; point à vérifier en J3b : `Visibility` dans les transactions (O10).

## 7. Hors périmètre

- Mi-bois, queue d'aronde, gabarits, caisson, objet « Ensemble » (J4, § 8) ; liste de débit (J2).
- Tenon à enfourchement, à renfort (haunch), chevillé, multiple, oblique ou d'about ; mortaise aux
  bouts arrondis (mèche) ; languette rapportée, fausse languette, lamelles, vis, quincaillerie.
- Pièces non d'équerre entre elles, assemblages entre plus de deux pièces, pièces dans des
  conteneurs différents, `App::Link` de pièces, pièces d'un autre atelier.
- Contrôle du sens du fil (tenon en bois de bout), jeu latéral et dilatation des panneaux
  (seul le jeu de fond est modélisé), tourillons dans la liste de débit (J2).
- Interaction entre usinages d'une même pièce (un assemblage ne voit que les brutes).
- Intégration spécifique à l'atelier Assembly, à Woodworking ou à CAM (coexistence seulement).

## 8. Préparation de J4 : objet « Ensemble » (exigence de jv)

Exigence de jv, mot pour mot : « je veux pouvoir modifier facilement un ensemble de piece; par
exemple si j'ai concu un bureau, je veux pouvoir modifier la profondeur de celui-ci et des toutes
les pieces impactés (plateau; caisson) ». Réalisée en J4 ; **J3 ne crée pas l'Ensemble** : le
cadre de J3 se pilote déjà avec quelques expressions natives (variante pilotée du § 3) et
l'Ensemble ne le simplifierait qu'au prix d'un lot de plus dans J3.

Ce que J3 garantit pour J4 : les assemblages suivent les cotes et positions des pièces en un
recalcul, valeurs automatiques et nombre de tourillons compris (M5, O4, T4), sans jamais écrire
dans les pièces ; la géométrie relative (`core/geometry.py` : repères, axes, boîtes ; `core/contact.py` : contact, chevauchement) est
réutilisable pour classer les pièces d'un ensemble.

Esquisse pour la spécification J4 (non contractuelle ici) :

- Objet `Furniture` (« Ensemble » ; pas « Assembly », réservé à l'atelier intégré : ADR 0007),
  `App::FeaturePython` groupe (`Group`) avec un repère (`Placement`) et trois cotes globales
  `Width`, `Depth`, `Height` (`App::PropertyLength`).
- Les pièces suivent par des **expressions FreeCAD natives** posées dans leur `ExpressionEngine`
  (ex. `Width = <<Bureau>>.Depth - 40 mm`, `Placement.Base.y = <<Bureau>>.Depth - 18 mm`),
  visibles et modifiables par l'utilisateur et lisibles par les autres outils.
- Règle (calcul pur dans `core/`) : une cote d'ensemble **étire** les pièces qui la traversent
  (leur cote locale `Length` ou `Width` alignée sur l'axe de la cote), **déplace** celles qui sont
  au-delà du plan de référence, ne change **jamais** une épaisseur (`Thickness`), ni une pièce
  qu'elle ne traverse pas.
- Une modification d'une cote d'ensemble = **une** transaction ; refus (rien n'est modifié, message)
  si une pièce passerait sous sa cote minimale (`MIN_DIMENSION_MM`, ou une limite d'assemblage).
- Les expressions posées par l'utilisateur sont respectées : une propriété déjà pilotée n'est
  jamais remplacée ; elle est signalée dans le compte rendu de la commande.
- **Position d'une pièce intérieure (étagère) quand la cote change — décision de jv du
  2026-10-20**, mot pour mot : « je veux les deux cas; par défaut elle ne bouge pas sauf si la
  position est calculer avec une contrainte ou formule (afficher un warning dans ce cas) ». Donc :
  - deux modes au choix **par pièce** : « position fixe » (la pièce garde sa distance au bord de
    référence de l'ensemble) et « proportionnelle » (elle reste à la même proportion de la cote) ;
  - **par défaut, la pièce ne bouge pas** (position fixe) ;
  - si sa position est pilotée par une expression (ou une contrainte), c'est la formule qui
    s'applique, quel que soit le mode, et un **avertissement** est affiché (vue rapport et compte
    rendu de la commande) pour signaler que la pièce a suivi sa formule.

## 9. Questions ouvertes pour jv

**Décisions de jv (2026-10-20)** : recommandations retenues pour Q1 à Q6 — Q1 (a) ajoutés, Q2 (a) 0 = automatique, Q3 valeurs proposées (22 mm → tourillon Ø 10), Q4 (a), Q5 ADR 0006 accepté, Q6 détection automatique + « Inverser ». ADR 0007 accepté. Usinages croisés et nœuds à trois pièces : issue #19, après J3.

**Q1 — Tenon et languette : ajoutés à la pièce ou taillés dedans ?** (change le dessin et le débit)
(a) *Ajoutés* : on dessine la traverse entre les montants (cotes visibles) ; l'assemblage ajoute le
tenon, la pièce usinée dépasse de la brute ; J2 ajoutera les tenons à la longueur de débit.
(b) *Taillés* : la traverse est dessinée avec ses tenons (longueur de débit), elle chevauche les
montants, l'assemblage enlève les épaulements ; il faut recalculer longueur et position de la
traverse à chaque changement de tenon.
*Recommandation : (a).* Le dessin reste celui du meuble vu de l'extérieur, la longueur du tenon
peut être automatique et suivre le montant sans toucher à la traverse, et l'Ensemble de J4 n'a
qu'une cote visible à piloter. L'architecture (ADR 0006) supporte les deux.

**Q2 — Proportions automatiques ou figées à la création ?**
(a) 0 = automatique, recalculé à chaque changement des pièces ; une valeur saisie est fixe (le
bédane de 8 mm) ; (b) valeurs calculées une fois à la création puis figées.
*Recommandation : (a)*, seule à faire « suivre » l'assemblage ; le panneau montre la valeur
effective à côté de la case « Auto ». Inconvénient : l'éditeur de propriétés affiche « 0 mm ».

**Q3 — Valeurs par défaut de menuisier** (§ 4.3.3) : tenon au tiers de l'épaisseur, épaulements
d'un sixième de la largeur, longueur aux deux tiers du montant, jeu de fond de mortaise 2 mm ;
languette de 10 mm, jeu de fond 1 mm, rainure filante ; tourillons Ø ≤ ½ épaisseur (6/8/10/12),
longueurs 30/35/40/50, distance au bord 2 Ø, entraxe ≤ 128 mm, jeu de fond 1 mm ; aucun jeu
latéral. *Recommandation : ces valeurs ;* corrigez celles qui diffèrent de votre pratique
(notamment 22 mm → tourillon de 10, ou 8 ?).

**Q4 — Déplacer une pièce assemblée.** La pièce visible est la pièce usinée ; sa position est
celle de la brute. (a) déplacer la pièce usinée déplace la brute (transparent) ; (b) position en
lecture seule, on déplace la brute dans l'arbre.
*Recommandation : (a).*

**Q5 — Deux objets par pièce assemblée (ADR 0006).** Une pièce assemblée apparaît comme la pièce
usinée, avec sa brute masquée dessous dans l'arbre. C'est imposé par le recalcul de FreeCAD
(sinon cycle). Le libellé de la pièce usinée est « <libellé de la brute> (usinée) » à la création
(décision de revue J3b : FreeCAD rend les libellés uniques) ; renommer l'une
ne renomme pas l'autre. *Recommandation : valider l'ADR 0006 ;* un renommage synchronisé pourra
venir plus tard si la gêne est réelle.

**Q6 — Rôle des pièces à la création.** *Recommandation :* détection automatique (la traverse
dont le bout touche le montant porte le tenon), ordre de sélection si c'est ambigu, bouton
« Inverser » dans le panneau.
