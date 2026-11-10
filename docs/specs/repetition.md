# Répétition de pièces

- Issue [#180](https://github.com/jvmenthon/freecad-menuiserie/issues/180), demande de jv (2026-11-07).
- Décision : [ADR 0043](../adr/0043-repetition-objet-de-cotes-et-copies-liees.md) (accepté) ;
  grille X × Y × Z : [ADR 0045](../adr/0045-repetition-en-grille.md) (proposé) ;
  jusqu'à une butée : [ADR 0047](../adr/0047-repetition-jusqu-a-une-butee.md) (accepté).
- Statut : **validée par jv** (2026-11-08) : Q4 et Q5 modifiées (cases à cocher), toutes les
  autres questions selon les choix ★.
- Révision 2 (même jour) : intègre les demandes de jv — copies modifiables après coup, liées à
  l'original, dissociables, copie par Ctrl + déplacement, cercle et trajet ensuite, réemploi de
  FreeCAD.

## 1. Besoin

Répéter une ou plusieurs pièces (avec leurs assemblages) N fois : tasseaux, lames, barreaux,
étagères, pieds, tiroirs en série. Exigences de jv :

1. la répétition se **modifie facilement après coup** (nombre, pas) ;
2. les copies gardent les **dimensions de l'original** : si l'original change, les copies
   changent ;
3. on peut **dissocier** une copie de son original ;
4. un **déplacement avec Ctrl** enfoncée crée automatiquement une copie ;
5. d'abord **linéaire**, puis **circulaire** et **le long d'un trait** (le modèle doit les
   prévoir) ;
6. réemployer ce que FreeCAD fournit quand c'est pertinent (§ 5).

## 2. Modèle : un objet « Répétition » + des pièces ordinaires

- **Objet `Repeat`** (« Répétition ») : objet de données sans forme, dans le même esprit que
  l'Ensemble (ADR 0008). Propriétés : `Source` (la ou les pièces répétées), `Mode`
  (`Linear` ; `Circular` et `Path` réservés), `Count` (copies en plus de la source), `Step`,
  `Axis`, `Reverse`, plus, pour le mode longueur, `Span`.
- **Copies** : de **vraies pièces** (brute + usinée, ADR 0006), car il faut des assemblages, de
  l'usinage et une ligne par copie dans la liste de débit. Chacune porte `Repeat` (lien vers
  la répétition) et `RepeatIndex` (lecture seule).
- **Liaison par expressions natives** (comme l'ADR 0009) : les cotes de la copie
  (`Length`, `Width`, `Thickness`, matériau, finitions) et son `Placement` sont des expressions
  sur la source et sur la répétition : `Placement = Source.Placement + k × Step × axe`. Changer
  `Step` dans l'éditeur de propriétés déplace donc toutes les copies ; déplacer ou redimensionner
  la source les suit.
- **Changer le nombre** : commande « Modifier la répétition » (double-clic sur la répétition ou
  sur une copie) qui rouvre le panneau ; elle ajoute ou retire des copies **hors recalcul**,
  dans une transaction. Les copies retirées sont les dernières. Un assemblage de la source est
  recréé pour chaque copie qui n'en a pas encore (aussi un assemblage ajouté à la source après
  coup), et un membre ajouté à un ensemble source est copié dans chaque ensemble copie.
- **Conteneur** : la répétition est créée dans le conteneur `App::Part` de ses sources (qui doivent
  être dans le même), comme leurs copies. L'axe X, Y ou Z est celui du **repère du conteneur**, pas
  celui du document ; la copie par glissement lit l'axe de la flèche dans ce même repère.
- **Dissocier** : commande « Dissocier la copie » : supprime les expressions de la copie (elle
  garde ses valeurs actuelles) et la sort de la répétition ; elle devient une pièce libre. La
  répétition garde son décompte (les index suivants ne bougent pas).
- **Supprimer la répétition** (jv, 2026-11-10) : ses copies sont supprimées avec elle (assemblages
  et Std Part compris), dans la même annulation ; une copie dissociée reste.
- **Butée sur une pièce usinée** : la butée vise sa pièce brute (la pièce usinée dépend des
  assemblages recopiés : cycle, « The graph must be a DAG »). Un document plus ancien est corrigé
  à l'ouverture.

À vérifier dans FreeCAD au premier lot (R-a, essai jetable) : expressions sur `Placement`
composée, indexation d'une liste (`Rep.Offsets[2]`) pour les modes cercle et trajet, coût de
recalcul à 100 copies.

## 2 bis. Répéter un ensemble (demande de jv)

La source peut être une pièce, plusieurs pièces ou un **ensemble** (tiroir, caisson, module).
Copier un ensemble crée un **ensemble copie**, sous-ensemble du même parent s'il y en a un :

- l'ensemble copie reçoit une copie de **chaque membre** (pièces et sous-ensembles, récursivement),
  avec leurs assemblages internes, leurs options et leurs distances ;
- ses cotes globales (`Width`, `Depth`, `Height`) et son `Origin` (sa position, pour un ensemble
  sans Std Part) sont des expressions sur l'ensemble source et sur la répétition : redimensionner l'ensemble source redimensionne toutes
  les copies, qui recalculent leurs membres avec les mêmes règles (rangées, parts, ADR 0019) ;
- **Std Part** (ADR 0038, ADR 0044 « Std Part de l'ensemble ») : l'ensemble source est rangé dans
  son Std Part ; l'ensemble copie a **le sien**, créé comme celui d'un ensemble neuf et rangé dans
  le même conteneur, où entrent les copies de ses membres. Le `Placement` du Std Part de la copie
  est celui du Std Part de la source plus le pas (et la même rotation), son `Origin` est celui de
  la source : déplacer ou tourner la source à la souris entraîne les copies. Un sous-ensemble
  copié avec son parent a son Std Part dans celui de la copie du parent (position portée par ce
  Std Part, règle `carried`) ; dissocier une copie lui laisse son Std Part ; supprimer une copie
  (nombre réduit, ou dans l'interface) supprime son Std Part vide, sans en laisser d'orphelin ;
- les assemblages entre un membre de l'ensemble et une pièce extérieure (cas B du § 3) sont
  recréés pour chaque copie, comme pour une pièce ;
- « Dissocier » une copie d'ensemble coupe les expressions de l'ensemble et de tous ses membres ;
  elle devient un ensemble libre ;
- sélection mixte (pièces et ensembles) : acceptée, chaque élément est répété avec le même pas ;
  une pièce membre d'un ensemble ne peut pas être répétée seule en même temps que son ensemble.

Piège connu : un membre qui lit une cote par expression vers son ensemble donne une « cyclic
reference » si l'ensemble était un conteneur ; l'Ensemble étant un objet de cotes (ADR 0008), les
liaisons source → copie ne forment pas de cycle. Vérifié au lot R-a.

## 3. Ce que « copier » veut dire

1. Copie d'une pièce : mêmes cotes, matériau, sens du fil, finitions ; nom « {nom} {k+1} ».
2. **Assemblages** (Q4 détaillée) : voir ci-dessous.
3. Quincaillerie : reprise avec l'assemblage.
4. Si la source est membre d'un ensemble, les copies le sont aussi (options reprises). **Réponse
   de jv (2026-11-08)** : une case **« Suivre le redimensionnement »** dans le panneau
   (`FollowResize` dans `Repeat`, décochée par défaut = pas fixe) :
   - décochée : le pas reste fixe ; agrandir l'ensemble ne déplace pas les copies ;
   - cochée : la répétition passe en « nombre sur une longueur » et sa longueur est une
     expression sur la cote de l'ensemble le long de l'axe (moins les retraits actuels aux deux
     bords) ; agrandir l'ensemble recalcule le pas et redistribue les copies, le nombre ne change
     pas. Si l'axe de la répétition n'est pas un axe de l'ensemble (pièce hors ensemble), la case
     est grisée.
5. Compatibilité (ADR 0007) : `Part::FeaturePython` ordinaires, forme `Part` standard,
   propriétés dans notre espace de noms.

### Q4 en détail : les assemblages

Exemple : un barreau tenonné dans une traverse haute et une traverse basse, répété 5 fois.

| Cas | Comportement ★ |
|---|---|
| A. Assemblage entre deux pièces **toutes deux sélectionnées** (ex. barreau + pied) | recréé pour chaque copie, entre les copies homologues, mêmes paramètres, **liés** à ceux de l'assemblage d'origine |
| B. Assemblage entre une pièce sélectionnée et une **non sélectionnée** (barreau ↔ traverse) | recréé pour chaque copie, la pièce non sélectionnée gardant son rôle (hôte ou invitée) : la traverse reçoit 5 tenons |
| C. Assemblage entre deux pièces non sélectionnées | ignoré |
| D. Une copie sort de l'hôte (pas trop grand), ou l'assemblage est impossible pour une autre raison | **assemblage non recopié** (décision de jv, 2026-11-10, qui remplace « créé quand même ») : sa faisabilité est vérifiée avant création avec les calculs du recalcul ; la copie reste une pièce simple et le nombre d'assemblages non recopiés est signalé (« 3 assemblages n'ont pas été recopiés : les pièces ne se touchent pas. »), dans la vue rapport et dans le panneau |
| E. Changer un paramètre de l'assemblage d'origine (diamètre de tourillon) | suit sur les copies tant qu'elles sont liées ; dissocier la copie dissocie aussi ses assemblages |
| F. Ajouter une copie après coup | ses assemblages sont créés comme pour A et B |
| G. Supprimer une copie | ses assemblages sont supprimés avec elle (comportement J3 existant) |

**Réponse de jv (2026-11-08)** : le panneau a une case **« Recopier les assemblages »**
(cochée par défaut). Décochée : seules les pièces sont copiées (cas A, B et F ne créent rien).
Cochée : les assemblages répétés **partagent la configuration** de l'assemblage d'origine ; un
changement sur le premier assemblage modifie tous les assemblages enfants (cas E). La case est
mémorisée dans `Repeat` (`CopyJoints`) et reprise par « Modifier la répétition ».

**Assemblage impossible (jv, 2026-11-10).** « Si l'assemblage est impossible, il n'est pas
recopié. » À chaque création et à chaque édition (`make_repeat`, `edit_repeat`, panneau), après
placement des copies, chaque assemblage enfant est réévalué : un enfant devenu impossible est
supprimé, un enfant manquant devenu possible est créé, un enfant dissocié par l'utilisateur ne
revient pas. Les grilles (une évaluation par cellule) et les ensembles suivent la même règle.
**Limite** : un simple recalcul (source déplacée après coup) ne crée ni ne supprime rien, car un
recalcul n'écrit pas la structure du document ; un enfant devenu impossible est alors signalé par
sa vérification habituelle jusqu'à la prochaine édition de la répétition.

## 4. Geste : Ctrl + déplacement (lot R-d, réponses de jv Q9 et Q10)

Dans le déplacement à la souris (J6, `gui/drag/`), **Ctrl** + clic sur une flèche de la pièce
sélectionnée crée une copie au lieu de déplacer l'original : l'original reste en place, un
fantôme (boîte translucide) suit la souris avec l'aimantation habituelle (Maj la coupe toujours,
Ctrl + Maj = copie sans aimantation). Le lâcher crée une répétition de 1 copie liée (`CountAndStep`,
axe global du déplacement, pas = distance, `Reverse` si le sens est négatif), en une transaction
« Répéter », puis le panneau « Modifier la répétition » s'ouvre aussitôt (nombre, pas,
dissociation). Échap, un simple clic ou un déplacement inférieur à 0,01 mm ne créent rien.

- Une flèche se tire sur un seul axe de la pièce : la copie exige que cet axe soit X, Y ou Z du
  document (pièce non tournée ou tournée d'un multiple de 90°) ; sinon refus expliqué.
- Une copie liée n'a pas de flèche (son placement est piloté) : on ne copie pas une copie ; le
  garde-fou `check_copyable` la refuse avec un message au cas où.
- Ctrl + clic ailleurs que sur une flèche reste à FreeCAD (sélection multiple) ; aucun
  raccourci clavier n'est consommé. Poignées et anneaux ne copient pas.

## 5. Réemploi de FreeCAD

| Fonction FreeCAD | Pertinent ? |
|---|---|
| Expressions natives | **Oui**, base du modèle (déjà utilisées, ADR 0009) |
| Draft `OrthoArray`, `PolarArray`, `PathArray` (`Draft.make_*_array`) | **Non comme objet** : un tableau est un seul objet à éléments virtuels, donc pas d'usinage ni d'assemblage par copie ni de ligne de débit par copie. **Oui comme source de calcul** pour le mode trajet : les placements le long d'une arête (`draftobjects/patharray.py`, répartition et orientation avec `Align`, `Tangent`) évitent de réécrire la géométrie des courbes. Draft est livré avec FreeCAD ; import tardif dans `features/` seulement, repli propre s'il manque. |
| `App::Link` / `LinkArray` | **Non** : les éléments partagent la forme de la source, on ne peut pas usiner chaque copie ; en revanche, utile plus tard pour une répétition de pièces **sans** assemblage (grandes quantités de lames) si la lenteur à 100 copies pose problème. |
| `Part::Compound` | Non (idem tableau) |
| Rotation/axe de `Base.Placement` | Oui pour le mode cercle : une rotation autour d'un axe et d'un centre |

Le calcul des décalages (linéaire, cercle) reste dans `core/repeat/`, Python pur, testé sans
FreeCAD ; seul le trajet appelle Draft, dans `features/`.

## 6. Découpage et critères

| Lot | Contenu | Tests |
|---|---|---|
| R-a | essai jetable des expressions (§ 2) puis `core/repeat/` : décalages linéaires, bornes, chevauchement, modes de longueur ; mode `Circular`/`Path` réservés dans le modèle | R1 N+pas, R2 N sur une longueur, R3 pas sur une longueur, R4 bornes, R5 chevauchement signalé, R6 inversion |
| R-b | `features/repeat.py` : objet `Repeat`, copies liées de pièces **et d'ensembles**, assemblages A à G, ensemble, une transaction, `_api/repeat.py` | R7 5 barreaux entre 2 traverses = 10 assemblages, R8 annulation en un bloc, R9 source modifiée → copies suivent, R10 `Step` modifié → copies déplacées, R11 dissocier, R12 ensemble, R13 liste de débit N+1 lignes, R19 répéter un caisson : membres copiés, redimensionner le caisson source redimensionne la copie, R20 dissocier un ensemble copie |
| R-c | commande « Répéter », panneau avec aperçu en direct, « Modifier la répétition », « Dissocier », icônes, traductions | GUI hors écran : R14 aperçu = copies créées, R15 refus affiché, R16 changer le nombre |
| R-d | Ctrl + déplacement | R17 copie par glissement, R18 annulation |
| R-e | recette manuelle, captures | — |
| plus tard | cercle, trajet (jalons séparés, même objet `Repeat`) | — |

## 7. Questions à jv (★ = recommandé)

- **Q1 — Nature.** ★ Objet `Repeat` + copies réelles liées par expressions (§ 2). Rejeté :
  tableau Draft (copies virtuelles).
- **Q2 — Modes de saisie.** ★ Nombre+pas, nombre sur une longueur, pas sur une longueur.
- **Q3 — Direction.** ★ Axe X/Y/Z global + « Inverser » ; ensuite axes de la pièce.
- **Q4 — Assemblages.** ✅ jv (2026-11-08) : case « Recopier les assemblages » ; assemblages
  enfants liés au premier (§ 3).
- **Q5 — Ensemble.** ✅ jv (2026-11-08) : case « Suivre le redimensionnement » (fixe ou suit), § 3.4.
- **Q6 — Ce qui est lié.** ★ Cotes, matériau, finitions et placement ; la **position** d'une copie
  déplacée à la main reste libre (la copie se dissocie de la position seulement ?). Alternative :
  toute modification manuelle d'une copie la dissocie entièrement.
- **Q11 — Ensembles.** ★ Copie d'ensemble = sous-ensemble copie complet, lié aux cotes de l'ensemble
  source (§ 2 bis). Alternative : copier seulement les pièces, sans ensemble.
- **Q7 — Maximum.** ★ 100 copies.
- **Q8 — Nom.** ★ « Barreau 2 », « Barreau 3 »…
- **Q9 — Maj.** Maj coupe déjà l'aimantation. ★ **Ctrl** pour copier (convention FreeCAD et
  la plupart des logiciels), Maj reste « sans aimantation » ; ou Maj = copier et **Alt** =
  « sans aimantation ».
- **Q10 — Après la copie par glissement.** ★ Le panneau « Modifier la répétition » s'ouvre
  aussitôt (nombre, pas) ; ou pas de panneau, un simple clic droit « Modifier ».

## 8. Notes de réalisation du lot R-b3 (ensembles)

Décisions détaillées : [ADR 0044](../adr/0044-repetition-d-ensembles-et-liaisons-des-copies.md).

- Une copie liée d'une pièce membre entre dans l'ensemble avec les mêmes options, **sans liaison
  d'ensemble** (elle suit sa source) mais comptée dans les rangées de ses voisines ; dissociée,
  elle est reliée normalement. Les options de la source changées après la copie ne se propagent
  pas aux copies.
- « Suivre le redimensionnement » : `Span` et `Step` deviennent des expressions (retraits actuels
  figés) ; refus traduit si une source n'est dans aucun ensemble ou si les sources sont dans des
  ensembles différents. Avec des copies liées, la source et ses copies se partagent un
  redimensionnement au prorata : à pas fixe, des copies serrées peuvent se chevaucher.
- Copie d'ensemble : ensemble neuf (sous-ensemble du même parent) dont les cotes et l'`Origin`
  suivent la source, avec une copie de chaque membre ; limites : pièce en bois à forme libre
  refusée, Distances gardées non copiées, cote des sources figée dans `Step`.

## 9. Grille X × Y × Z (demande de jv, 2026-11-08 ; ADR 0045, proposé)

Demande de jv : « la répétition peut se faire sur tous les axes en même temps mais avec le même mode
de saisie ». Lecture retenue : une **grille**. La répétition à un axe (§ 2 à 8) en est le cas
particulier d'une seule ligne.

### 9.1 Saisie

- **Un seul mode de saisie** pour toute la répétition : nombre et pas, nombre sur une longueur, ou
  pas sur une longueur.
- **Une ligne par axe** (X, Y, Z), chacune avec sa valeur selon le mode (nombre et pas, nombre et
  longueur, ou pas et longueur) et son sens (« Inverser »).
- Le **nombre** d'un axe est celui des éléments de l'axe, **original compris** ; un axe de nombre 1
  est inactif. Dans le panneau, la case d'activation de la ligne est équivalente (nombre ≥ 2).
- Exemple : 4 × 3 sur X et Y, pas de 100 mm sur X et de 150 mm sur Y = **11 copies** en plus de
  l'original ; avec un troisième axe de 2, 4 × 3 × 2 = 23 copies.
- Total des copies = (nx · ny · nz) − 1, au plus **100** ; au-delà, refus avec un message
  (« 11 × 10 donneraient 109 copies en plus de l'original ; le maximum est 100 »), dans le panneau
  comme par l'API. Un axe seul reste borné à 100 copies.

### 9.2 Copies et cellules

- La copie de cellule `(i, j, k)` est à `source + Σ (rang × pas × sens)` sur chaque axe du repère
  du conteneur (§ 2) ; l'original est `(0, 0, 0)`.
- Chaque copie porte sa **cellule** (`RepeatCell`) en plus du rang linéaire `RepeatIndex` (X, puis
  Y, puis Z) : changer le nombre d'un axe **ne renumérote pas** les copies, seul l'ordre
  d'affichage et les libellés automatiques suivent.
- Réglages de la répétition : première ligne = `Axis`, `Count`, `Step`, `Span`, `Reverse` (comme
  avant) ; lignes suivantes = mêmes noms suffixés `2` et `3`. `Count*` : copies en plus de
  l'original le long de l'axe.

### 9.3 Modifier la grille

« Modifier la répétition » (`edit_repeat`) :

| Changement | Effet |
|---|---|
| nombre d'un axe en plus | cellules manquantes créées (copies, assemblages, ensembles) ; les autres intactes |
| nombre d'un axe en moins, axe désactivé | copies des cellules qui sortent supprimées, avec assemblages et Std Part |
| pas ou sens | copies conservées déplacées (expressions) |
| un seul axe remplacé par un seul autre axe | les copies suivent sur le nouvel axe |
| copie dissociée ou supprimée à la main | elle ne revient pas |

### 9.4 Assemblages, ensembles, suivi

- **Assemblages** : l'assemblage entre copies homologues vise la **même cellule** ; une pièce fixe
  reçoit un assemblage par copie ; « Recopier les assemblages » est inchangé (§ 3, Q4).
- **Ensembles** : même position relative dans chaque cellule, un Std Part par copie (§ 2 bis,
  ADR 0044).
- **Suivre le redimensionnement** : axe par axe. Chaque axe actif suit la cote de l'ensemble sur son
  axe (`Width` pour X, `Depth` pour Y, `Height` pour Z) ; refus traduit hors ensemble (§ 3.4).
- **Chevauchement** : signalé par axe (pas inférieur à la cote des sources sur l'axe), puis pour la
  grille complète ; avertissement non bloquant.

### 9.5 Panneau

Un sélecteur de mode ; trois lignes X, Y, Z (case d'activation, nombre, pas ou longueur selon le
mode, « Inverser ») ; aperçu en direct de **toutes** les copies ; total affiché (« Grille 4 × 3 :
11 copies en plus de l'original ») ; refus clair au-delà de 100 copies. Ctrl + glisser (§ 4) garde
son comportement : une copie sur un axe.

### 9.6 Critères

| Réf. | Critère | Tests |
|---|---|---|
| G1 | 4 × 3, pas 100 et 150 mm : 11 copies aux bonnes cellules | `test_repetition_grille.py` (unitaire et intégration) |
| G2 | les trois modes de saisie, par axe ; sens par axe | idem |
| G3 | total > 100 refusé (message), 100 accepté, rien n'est créé en cas de refus | idem |
| G4 | changer le nombre ou le pas d'un axe garde les copies des cellules conservées | idem |
| G5 | dissocier une copie de la grille : elle ne revient pas | idem |
| G6 | annuler et rétablir, enregistrer et rouvrir ; document d'avant la grille | idem |
| G7 | assemblages par cellule, pièce fixe, copie d'ensemble en grille | `test_repetition_grille_assemblages.py`, `test_repetition_grille_ensembles.py` |
| G8 | suivre le redimensionnement sur deux axes | `test_repetition_grille_ensembles.py` |
| G9 | panneau hors écran : aperçu, total, refus, modes, chevauchement, modification | `tests/gui/verifications_repetition_grille.py` |

## 10. Jusqu'à une butée (demande de jv, 2026-11-10 ; ADR 0047, accepté)

Dans les modes « nombre sur une longueur » et « pas sur une longueur », la longueur de chaque axe
peut être **calculée jusqu'à une butée** au lieu d'être saisie.

- **Butée** : une face, une arête (jv, 2026-11-10), un sommet ou une pièce entière, choisis dans la vue 3D (bouton « Butée… »
  de la ligne de l'axe, puis clic dans la vue). Pour une pièce, on retient sa face la plus proche
  dans le sens de la répétition. Chaque axe d'une grille a sa butée.
- **Sens** (jv, 2026-11-10) : déduit de la butée, la répétition va toujours vers elle ; la case
  « Inverser » est grisée tant qu'une butée est choisie. Une butée qui chevauche l'original est
  refusée.
- **Ouverture de « Répéter »** (jv, 2026-11-10/11) : « nombre sur une longueur », 2 éléments, aucune
  copie et aucune butée avant le premier choix (« OK » grisé jusque-là), mais le choix de la butée
  est déjà en cours : le premier clic dans la vue 3D donne la butée et l'axe (celui où elle est le
  plus loin de l'original), seul actif. « Butée… » sur une ligne ou un second clic sur ce bouton
  reprend la main.
- **Case « Intervalle avant la fin »** (jv, 2026-11-10 ; propriété `EndGap`) : `n` éléments
  partagent la longueur en `n` intervalles égaux au lieu de `n - 1` ; la dernière pièce s'arrête
  un intervalle avant la fin (ou la butée). « Déduire l'épaisseur » est alors grisée. Avec « Suivre
  le redimensionnement », le pas suit `longueur / n`.
- **Face de la pièce répétée** (jv, 2026-11-10) : cliquée comme butée, c'est le point de départ :
  son axe devient le seul actif et la butée reste à choisir.
- **Essai de « Déduire l'épaisseur »** (jv, 2026-11-10) : après le choix d'une butée, si la saisie
  est refusée ou si des copies se chevauchent, la case passe dans l'autre état ; si ce n'est pas
  mieux, elle revient à son état initial et le refus ou l'avertissement restent affichés.
- **Longueur** = distance, sur l'axe et dans le sens de la répétition, de la face de départ de
  l'original à la butée ; affichée en lecture seule. On garde le choix de ce qui est fixé : le
  nombre (`CountOnSpan`, le pas se calcule) ou le pas (`StepOnSpan`, le nombre se calcule).
- **Case « Déduire l'épaisseur de la pièce »** (modes sur une longueur, saisie ou butée ; cochée par
  défaut, comme les documents existants) : cochée, longueur utile = longueur − épaisseur, la
  dernière copie arrive **à fleur** de la butée ; décochée, elle **commence** à la butée et la
  collision est signalée dans le panneau, sans bloquer.
- **La longueur suit la butée** : déplacer ou redimensionner la butée recalcule `Span` et `Step`,
  les copies suivent. Limite : un recalcul ne crée ni ne supprime de copie ; en « pas sur une
  longueur » le nombre ne change qu'en rouvrant « Modifier la répétition » (avertissement).
- **Butée supprimée** : la répétition garde la dernière longueur, repasse en saisie et le dit par un
  avertissement ; aucune erreur.
- **Refus traduits** : butée derrière l'original, plus proche que l'épaisseur (case cochée), butée
  = original, une de ses copies ou un membre de l'ensemble répété, sous-élément ni face ni sommet,
  butée avec « Nombre et pas » ou avec « Suivre le redimensionnement ».
- **Persistance** : `Stop`, `Stop2`, `Stop3` (lien global + sous-élément), `StopLabel*`,
  `StopHolders`, `DeductThickness`.

### Critères

| Réf. | Critère | Tests |
|---|---|---|
| B1 | longueur = distance à la butée, avec et sans déduction ; refus (derrière, trop proche, sous-élément) | `tests/unit/test_repetition_butee.py` |
| B2 | butée = pièce, face, sommet ; dernière copie à fleur / en collision | `tests/integration/test_repetition_butee.py` |
| B3 | butée déplacée : les copies suivent ; « pas sur une longueur » : nombre à l'édition | idem |
| B4 | butée supprimée : longueur gardée, avertissement, aucune erreur | idem |
| B5 | grille à deux butées, sens inverse, butée hors du conteneur | idem |
| B6 | enregistrer / rouvrir, annuler / rétablir, document d'avant les butées (case cochée) | idem |
| B7 | panneau hors écran : bouton Butée, sélection simulée, case d'épaisseur, retrait, prérempli | `tests/gui/verifications_repetition_butee.py` |
