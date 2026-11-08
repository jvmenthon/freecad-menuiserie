# Répétition de pièces

- Issue [#180](https://github.com/jvmenthon/freecad-menuiserie/issues/180), demande de jv (2026-11-07).
- Décision : [ADR 0043](../adr/0043-repetition-objet-de-cotes-et-copies-liees.md) (proposé).
- Statut : **validée par jv** (2026-11-08) : Q4 et Q5 modifiées (cases à cocher), toutes les
  autres questions selon les choix ★.
- Révision 2 (même jour) : intègre les demandes de jv — copies modifiables après coup, liées à
  l'original, dissociables, copie par Maj + déplacement, cercle et trajet ensuite, réemploi de
  FreeCAD.

## 1. Besoin

Répéter une ou plusieurs pièces (avec leurs assemblages) N fois : tasseaux, lames, barreaux,
étagères, pieds, tiroirs en série. Exigences de jv :

1. la répétition se **modifie facilement après coup** (nombre, pas) ;
2. les copies gardent les **dimensions de l'original** : si l'original change, les copies
   changent ;
3. on peut **dissocier** une copie de son original ;
4. un **déplacement avec Maj** enfoncée crée automatiquement une copie ;
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
  recréé pour chaque nouvelle copie.
- **Dissocier** : commande « Dissocier la copie » : supprime les expressions de la copie (elle
  garde ses valeurs actuelles) et la sort de la répétition ; elle devient une pièce libre. La
  répétition garde son décompte (les index suivants ne bougent pas).

À vérifier dans FreeCAD au premier lot (R-a, essai jetable) : expressions sur `Placement`
composée, indexation d'une liste (`Rep.Offsets[2]`) pour les modes cercle et trajet, coût de
recalcul à 100 copies.

## 2 bis. Répéter un ensemble (demande de jv)

La source peut être une pièce, plusieurs pièces ou un **ensemble** (tiroir, caisson, module).
Copier un ensemble crée un **ensemble copie**, sous-ensemble du même parent s'il y en a un :

- l'ensemble copie reçoit une copie de **chaque membre** (pièces et sous-ensembles, récursivement),
  avec leurs assemblages internes, leurs options et leurs distances ;
- ses cotes globales (`Width`, `Depth`, `Height`) et son `Origin` sont des expressions sur
  l'ensemble source et sur la répétition : redimensionner l'ensemble source redimensionne toutes
  les copies, qui recalculent leurs membres avec les mêmes règles (rangées, parts, ADR 0019) ;
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
| D. Une copie sort de l'hôte (pas trop grand) | assemblage créé quand même ; la vérification J3 le signale sur la copie, la copie reste modifiable |
| E. Changer un paramètre de l'assemblage d'origine (diamètre de tourillon) | suit sur les copies tant qu'elles sont liées ; dissocier la copie dissocie aussi ses assemblages |
| F. Ajouter une copie après coup | ses assemblages sont créés comme pour A et B |
| G. Supprimer une copie | ses assemblages sont supprimés avec elle (comportement J3 existant) |

**Réponse de jv (2026-11-08)** : le panneau a une case **« Recopier les assemblages »**
(cochée par défaut). Décochée : seules les pièces sont copiées (cas A, B et F ne créent rien).
Cochée : les assemblages répétés **partagent la configuration** de l'assemblage d'origine ; un
changement sur le premier assemblage modifie tous les assemblages enfants (cas E). La case est
mémorisée dans `Repeat` (`CopyJoints`) et reprise par « Modifier la répétition ».

## 4. Geste : Maj + déplacement

Dans le déplacement à la souris (J6, `gui/drag/`), l'appui sur **Maj** au début du glissement
crée une copie au lieu de déplacer l'original : l'original reste en place, la copie suit la
souris, avec l'aimantation habituelle. Le lâcher crée une répétition de 1 copie liée (donc
modifiable ensuite : nombre, pas, dissociation). **Conflit** : Maj coupe déjà l'aimantation
pendant le glissement (spec souris, C5). Voir Q9.

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
| R-d | Maj + déplacement | R17 copie par glissement, R18 annulation |
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
