# [J2] Liste de débit

- Jalon : J2 (issue #13), après J4 et J6, à la demande de jv
- Statut : **acceptée** (réponses de jv au § 10, qui priment sur les recommandations ★)
- Branche : `jalon/J2`, partie de `jalon/J6` (PR #38 et #48 pas encore fusionnées dans `main`)
- ADR liés : [0002 — Bibliothèque de matériaux](../adr/0002-bibliotheque-de-materiaux.md),
  [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](../adr/0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](../adr/0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](../adr/0008-ensemble-objet-de-cotes.md),
  [0012](../adr/0012-liste-de-debit-a-la-demande.md) (remplacé), **[0013 — Liste de débit vivante](../adr/0013-liste-de-debit-vivante.md)** (accepté)
- Découpage : quatre PR, **J2a ∥ J2b → J2c → J2d** (§ 5)

## 1. Contexte

Le plan (§ 2) promet « le tableau des pièces (repère, quantité, L × l × e, essence, volume,
masse), affiché dans un Spreadsheet FreeCAD et exportable en CSV, qui regroupe les pièces
identiques ». Tout est prêt pour le calculer : chaque pièce brute porte son repère (`Mark`), ses
cotes finies, son matériau figé (`MaterialId`, `Material`, `Category`, `Density`), son fil et ses
surcotes de débit ; `record_of(obj)` en fait un `PartRecord` pur (J1b) qui calcule déjà cotes de
débit, volume et masse. Les assemblages de J3/J4 **ajoutent** de la matière à l'invitée (tenons,
languettes, queues d'aronde) : la pièce usinée dépasse alors de la brute et la longueur à débiter
est plus grande que la brute (Q1 de J3, § 4.8.6 de J4). Les tourillons sont des pièces rapportées.
Les pièces d'un ensemble (J4) portent `Furniture`, celles posées par J6 portent un repère qui est
aussi leur nom. Aujourd'hui, le menuisier doit recopier tout cela à la main.

L'issue #13 réunit aussi deux défauts de robustesse relevés en J1b, à trancher avec J2 parce que
la liste de débit est le premier code qui lit **toutes** les pièces d'un document : une pièce d'un
document plus récent (`record_of` lève `KeyError`) et la réparation d'un `MaterialId` d'un type
inattendu (matériau par défaut alors que `Category` et `Density` sont gardées).

## 2. Objectif

Le menuisier peut :

1. lancer **Liste de débit** (barre d'outils et menu Menuiserie) : l'atelier crée ou met à jour
   une feuille de calcul « Liste de débit » dans le document, une ligne par groupe de pièces
   identiques, avec repère, quantité, cotes finies et de débit, matériau, fil, volume et masse,
   puis les totaux par matériau ;
2. limiter la liste à ce qu'il a **sélectionné** (des pièces, un ensemble, un Std Part) ; sans
   sélection, la liste couvre tout le document ;
3. **exporter** la liste en CSV pour un tableur ou une scierie ;
4. compter juste : les tenons et queues sont **inclus** dans la longueur de débit ; une pièce vue
   à travers un `App::Link` compte autant de fois qu'elle apparaît ; les tourillons sont listés à
   part, en fournitures.

**Livrable visible** : dans le caisson de référence de J4d avec une tablette posée par J6 et une
traverse à tenons, « Liste de débit » affiche une feuille lisible (les deux côtés regroupés sur
une ligne de quantité 2), la traverse débitée tenons compris, et un CSV qui s'ouvre tel quel dans
LibreOffice Calc et Excel en français.

## 3. Critères d'acceptation

Légende : **U** = unitaire sans FreeCAD, **I** = intégration dans `freecadcmd` (1.0 et 1.1),
**G** = interface hors écran, **manuel** = recette `docs/recette/J2-scenarios-manuels.md`.

### 3.1 Calcul pur (`core/cutlist/`)

| N° | Critère | Test |
|---|---|---|
| C1 | `build_cut_list(entries)` regroupe les entrées de même **clé** (§ 4.2) en une ligne ; quantité = somme des quantités ; l'ordre des lignes est stable : repère (ordre naturel, « M2 » avant « M10 »), puis matériau, puis cotes décroissantes ; les pièces sans repère viennent en dernier. | U |
| C2 | Deux pièces de même repère mais de cotes, matériau, fil ou surcotes différents restent sur **deux lignes** et la liste porte un avertissement « Repère M1 utilisé pour des pièces différentes ». | U |
| C3 | Les cotes de débit = cotes finies + ajouts des assemblages (C4) + surcotes ; volume et masse par ligne (unitaires × quantité), en cotes **finies** et en cotes **de débit**. | U |
| C4 | `CutEntry.additions` (ajouts en mm le long de la longueur, de la largeur, de l'épaisseur) entre dans les cotes de débit, pas dans les cotes finies. | U |
| C5 | Totaux par matériau **et par épaisseur de débit** (demande de jv, 2026-10-22) : quantité, volume de débit (m³), masse (kg) ; **surface** de débit (m², L × l de débit), massif compris (demande de jv : on achète par épaisseur). Total général de masse. | U |
| C6 | Fournitures : `build_cut_list` regroupe les tourillons par (diamètre, longueur) et donne leur nombre. | U |
| C7 | `to_csv(cut_list, dialect)` produit un texte CSV : en-tête traduit, une ligne par groupe, puis les totaux et les fournitures séparés par une ligne vide ; dialecte par défaut (§ 4.5) : séparateur `;`, virgule décimale, UTF-8 avec BOM, fins de ligne CRLF ; les cellules qui commencent par `=`, `+`, `-`, `@`, tabulation ou retour chariot sont préfixées d'une apostrophe (injection de formule). | U |
| C8 | Nombres affichés : cotes en mm arrondies au dixième (« 800 », « 22,5 »), volume en m³ à 4 décimales, surface en m² à 3, masse en kg à 2. Une entrée invalide (cote non finie, quantité ≤ 0) lève `InvalidCutEntryError`, message traduit. | U |

### 3.2 Lecture du document (`features/cutlist_*.py`)

| N° | Critère | Test |
|---|---|---|
| D1 | `collect(doc)` renvoie une entrée par pièce de bois brute ; une pièce usinée est comptée par sa brute, une seule fois ; les objets d'autres ateliers sont ignorés. | I |
| D2 | `collect(objects)` sur une sélection : une pièce, sa pièce usinée, un ensemble (toutes ses pièces membres), un Std Part ou un groupe (toutes les pièces qu'il contient, récursivement) ; une pièce atteinte deux fois n'est comptée qu'une fois. | I |
| D3 | `App::Link` vers une pièce, une pièce usinée, un Std Part ou un ensemble : chaque lien ajoute **une** occurrence de ce qu'il vise (× `ElementCount` pour un tableau de liens) ; un lien vers un lien est suivi ; l'original visible dans le document compte aussi. | I |
| D4 | Ajouts : pour une invitée de tenon-mortaise, rainure-languette ou queue d'aronde, `CutEntry.additions` vaut l'étendue de la pièce usinée au-delà de la brute selon chaque axe local (boîte englobante de la forme usinée dans le repère de la brute) ; onglet, mi-bois et feuillure ne changent rien (retraits). | I |
| D5 | Tourillons : un assemblage `Dowels` ajoute `count` tourillons de `diameter` × `dowel_length` effectifs (valeurs automatiques résolues). | I |
| D6 | Colonne « Ensemble » : libellé de l'ensemble d'une pièce membre, vide sinon ; la clé de regroupement l'ignore (★ Q2). | I |
| D7 | Une pièce en erreur n'interrompt pas la liste et un avertissement la nomme : une pièce usinée à la forme absente, invalide ou non recalculée est listée d'après les propriétés de sa brute, sans ajouts (`NoMachinedShape`) ; une pièce à cote invalide (nulle, négative, non finie) n'a pas de débit calculable et est **ignorée** (`IgnoredPart`, avec la raison). | I |
| D8 | Robustesse (issue #13) : une pièce dont `Version` > `MODEL_VERSION` ou dont la catégorie est inconnue est listée avec la catégorie « ? » et un avertissement ; `record_of` lève `UnsupportedPartError` (traduite) au lieu de `KeyError`. | I |

### 3.3 Feuille de calcul et export

| N° | Critère | Test |
|---|---|---|
| S1 | `make_cut_list(doc, objects=None)` crée une feuille `Spreadsheet::Sheet` de libellé « Liste de débit » (nom interne `MenuiserieCutList`) ou **met à jour** celle qui existe (marquée par la propriété `MenuiserieCutList` = vrai) ; une feuille que l'utilisateur a renommée est retrouvée par la marque. Une seule transaction « Liste de débit ». | I |
| S2 | Mise à jour : la feuille est vidée puis réécrite ; les cellules que l'utilisateur a ajoutées à droite de la dernière colonne de l'atelier (colonne `P` et au-delà) sont **conservées** (★ Q3). | I |
| S3 | Mise en page : titre, date, portée (« Tout le document » ou « Sélection : 3 objets »), en-tête en gras, colonnes de nombres alignées à droite avec unités dans l'en-tête, largeurs de colonnes réglées, totaux et fournitures sous le tableau, avertissements en bas. | I + manuel |
| S4 | La feuille n'est **pas** recalculée automatiquement : elle porte la date de sa mise à jour, et l'infobulle de la commande le dit (★ Q3, ADR 0012). | I |
| S5 | `export_cut_list_csv(doc, path, objects=None)` écrit le CSV de C7 ; chemin refusé (message) s'il n'a pas l'extension `.csv`, s'il désigne un dossier ou un fichier non accessible en écriture ; écriture atomique (fichier temporaire du même dossier puis remplacement). | I |
| S6 | Annuler après « Liste de débit » : la feuille revient à son état précédent (absente si elle vient d'être créée). | I |
| S7 | Document ouvert sans l'atelier : la feuille reste une feuille FreeCAD ordinaire, lisible. | I |

### 3.4 Interface

| N° | Critère | Test |
|---|---|---|
| G1 | Commande `Menuiserie_CutList` « Liste de débit » (icône générée par `tools/generer_icones.py`) : active dès qu'un document est ouvert ; crée ou met à jour la feuille, l'ouvre dans un onglet, affiche les avertissements dans la vue rapport. | G |
| G2 | Commande `Menuiserie_CutListExport` « Exporter la liste de débit (CSV)… » : boîte d'enregistrement, nom proposé `<document> - liste de débit.csv` à côté du document ; message de confirmation dans la barre d'état ; refus affiché dans une boîte d'avertissement (comme J4). | G |
| G3 | Aucune des deux commandes ne modifie la sélection ni une pièce ; l'export ne modifie pas le document. | G |
| G4 | Recette : caisson J4d + tablette J6 + traverse à tenons + un lien vers un tiroir ; feuille et CSV ouverts dans le tableur de jv. | manuel |

### 3.5 Issue #13, retouches

| N° | Critère | Test |
|---|---|---|
| R1 | Pièce d'un document plus récent (`Version` > `MODEL_VERSION`) : `Material` en lecture seule et `onChanged` inactif sur le matériau ; le panneau l'ouvre en lecture seule avec un message (★ Q6). | I |
| R2 | Réparation d'un `MaterialId` d'un type inattendu : le matériau est retrouvé d'après le libellé `Material` (`find_by_name`) avant de prendre le matériau par défaut ; `MaterialId` et `Material` ajoutés aux cas `RETYPED` de `tests/integration/test_suites_revue_j1b.py`. | I |
| R3 | Docstrings de `features/wood_part_restore.py` (contrôle du type de chaque propriété) et de `apply_editor_modes` ; paragraphe ajouté à l'ADR 0003 (§ « Limite » : une propriété d'un type inattendu est supprimée même sur un document plus récent). | revue |

## 4. Conception

### 4.1 Vue d'ensemble

```
core/cutlist/          Python pur : CutEntry, CutLine, CutList, build_cut_list, to_csv, formats
features/cutlist_collect.py   document → CutEntry (pièces, usinées, liens, ensembles, tourillons)
features/cutlist_sheet.py     CutList → Spreadsheet::Sheet (création, mise à jour, mise en page)
features/cutlist_export.py    CutList → fichier CSV (chemin validé, écriture atomique)
api.py                        make_cut_list, export_cut_list_csv, cut_list_of
gui/commands/cutlist.py       deux commandes, boîte d'enregistrement
```

Patterns (CONTRIBUTING, « Conception ») : **pipeline** collecte → calcul pur → rendu ; le calcul
ne connaît ni FreeCAD ni le format de sortie ; deux **rendus** (feuille, CSV) consomment la même
`CutList` ; la collecte est un **visiteur** du document qui délègue à une petite table de lecteurs
par type d'objet (pièce, usinée, lien, conteneur, ensemble, tourillons), comme le registre des
assemblages de J3.

### 4.2 Modèle pur (`core/cutlist/`)

```python
@dataclass(frozen=True)
class CutEntry:  # une pièce brute vue une fois (quantity occurrences)
    record: PartRecord  # J1b : repère, matériau, cotes finies, surcotes, fil, densité
    quantity: int = 1
    additions: Dimensions3 = ZERO  # ajouts des assemblages (mm), le long de L, l, e
    furniture: str = ""  # libellé de l'ensemble, affichage seulement
    source: str = ""  # nom interne de l'objet, pour les avertissements


@dataclass(frozen=True)
class Hardware:  # fourniture (tourillon)
    kind: HardwareKind  # DOWEL (seul en J2)
    diameter: float
    length: float
    quantity: int


@dataclass(frozen=True)
class CutLine:  # un groupe de pièces identiques
    mark: str
    quantity: int
    material_id: str
    material_name: str
    kind: MaterialKind
    finished: Dimensions
    rough: Dimensions
    grain: GrainDirection
    furniture: tuple[str, ...]  # ensembles concernés, triés, sans doublon

    def volume_m3(self, rough: bool) -> float: ...
    def mass_kg(self, rough: bool) -> float: ...
    def area_m2(self) -> float: ...  # L × l de débit × quantité (panneaux)


@dataclass(frozen=True)
class CutList:
    lines: tuple[CutLine, ...]
    totals: tuple[MaterialTotal, ...]
    hardware: tuple[Hardware, ...]
    warnings: tuple[Notice, ...]  # Notice de J4 (gabarit traduit + paramètres)


def build_cut_list(entries: Iterable[CutEntry], hardware: Iterable[Hardware] = ()) -> CutList: ...
def to_csv(cut_list: CutList, dialect: CsvDialect = FRENCH_CSV) -> str: ...
```

**Clé de regroupement** (★ Q1) : `(mark, material_id, finished, additions, allowances, grain)`,
cotes comparées au centième de mm. Le repère fait partie de la clé : deux pièces de même cotes et
de repères différents restent sur deux lignes (le repère est l'identité choisie par le menuisier,
J6 L5). L'ensemble n'en fait pas partie (★ Q2). Le fil est relatif à la pièce (ADR 0003) : une
pièce tournée dans le meuble reste identique.

### 4.3 Collecte (`features/cutlist_collect.py`)

- Point d'entrée : `collect(doc_or_objects) -> tuple[list[CutEntry], list[Hardware], list[Notice]]`.
- **Pièce brute** (`is_wood_part`) : une entrée, `record_of`. **Pièce usinée** : ramenée à sa brute
  (`blank_of`) ; ajouts = `max(0, étendue de Shape.BoundBox de l'usinée dans le repère local de la
  brute − cote finie)` par axe, en partant du côté positif et du côté négatif séparément. Calcul
  générique : il couvre tenons, languettes, queues et tout futur ajout sans connaître les
  assemblages, et ignore les retraits (ADR 0006 : un retrait ne raccourcit jamais la brute).
- **Doublons** : chaque brute est comptée une fois par chemin d'accès ; l'ensemble des brutes
  vues directement est un `set` de noms internes ; les occurrences par lien s'ajoutent (D3).
- **Liens** : `App::Link` (et `LinkElement`, tableau de liens) : on suit `LinkedObject` jusqu'à
  une cible qui n'est pas un lien, on lit la cible récursivement avec un **multiplicateur**
  (`ElementCount` ou 1). Profondeur bornée (32) contre les cycles, avertissement au-delà.
- **Conteneurs** : `App::Part`, `App::DocumentObjectGroup` : `Group` récursif ; **Ensemble** :
  ses membres (`members_of` de J4).
- **Tourillons** : pour chaque `DowelJoint` dont les deux pièces sont dans la portée, valeurs
  effectives (`DowelValues`, déjà calculées pour le panneau) → `Hardware`.
- Lecture seule : aucune écriture dans le document, aucun `recompute`.

### 4.4 Feuille de calcul (`features/cutlist_sheet.py`)

Colonnes A–O : Repère, Qté, Longueur finie, Largeur finie, Épaisseur finie, Longueur de débit,
Largeur de débit, Épaisseur de débit, Matériau, Fil, Ensemble, Volume de débit (m³), Masse (kg),
Surface (m²), Remarque (ex. « tenons compris : +60 mm »). Écriture par `sheet.set(cell, text)` de
**valeurs littérales** (un texte qui commence par `=` est préfixé d'une apostrophe : jamais de
formule construite à partir d'un repère ou d'un libellé), `setStyle`, `setAlignment`,
`setColumnWidth`, `setDisplayUnit` non utilisé (nombres déjà convertis). La feuille porte une
propriété `MenuiserieCutList` (bool, masquée) pour être retrouvée ; aucune autre propriété,
aucun proxy (ADR 0012, point conservé par l'ADR 0013) : un document sans l'atelier l'ouvre sans
message (seul l'objet `CutList` de la liste vivante y est signalé sans proxy, § 10.1 V3).

### 4.5 Export CSV

Module `csv` de la bibliothèque standard, écrit dans une chaîne (`io.StringIO`) par `core`, puis
fichier écrit par `features/cutlist_export.py` : `pathlib.Path`, extension `.csv` imposée,
dossier parent existant, `tempfile.NamedTemporaryFile(dir=parent, delete=False)` puis
`os.replace`. Dialecte `FRENCH_CSV` (★ Q4) : `;`, virgule décimale, `utf-8-sig`, `\r\n` ; le
dialecte est un paramètre de `core` ; **remplacé par § 10 (Q4 b)** : `INTERNATIONAL_CSV` (`,` et
point) par défaut, `FRENCH_CSV` en paramètre de l'API.

### 4.6 Traductions, unités, sécurité

- Toutes les chaînes par `QT_TRANSLATE_NOOP` / `translate` (contexte « Menuiserie »).
- Aucun accès réseau, aucun `eval`, aucune formule de tableur écrite ; chemin d'export choisi par
  l'utilisateur et validé ; injection CSV neutralisée (C7).
- Les cellules ne contiennent que des nombres convertis et des textes de l'utilisateur échappés.

### 4.7 Compatibilité avec les autres ateliers (ADR 0007)

La feuille est un `Spreadsheet::Sheet` standard (aucun proxy) ; nom interne et propriété dans
notre espace (`MenuiserieCutList`) ; les objets d'autres ateliers sont ignorés sans erreur ; aucun
observateur global ; aucune dépendance ajoutée (`csv`, `tempfile`, `os` de la bibliothèque
standard ; module Spreadsheet de FreeCAD, présent en 1.0 et 1.1).

## 5. Découpage en PR

| Lot | Branche | Contenu | Diff estimé hors tests | Critères |
|---|---|---|---|---|
| **J2a** | `fix/robustesse-piece` | issue #13 : `UnsupportedPartError`, lecture seule d'une pièce plus récente, réparation par `find_by_name`, docstrings, ADR 0003 | ≈ 150 | D8, R1–R3 |
| **J2b** | `feat/debit-core` | `core/cutlist/` : modèle, regroupement, totaux, fournitures, formats, CSV | ≈ 350 | C1–C8 |
| **J2c** | `feat/debit-document` | collecte, feuille, export, API, CHANGELOG ; livrable par la console | ≈ 380 | D1–D7, S1–S7 |
| **J2d** | `feat/debit-interface` | deux commandes, icônes (script), recette, README « Liste de débit », scène des captures | ≈ 200 | G1–G4 |

J2a et J2b sont indépendants et peuvent partir ensemble ; J2c suit J2b (et J2a pour D8) ; J2d
suit J2c. Chaque sous-lot entre dans `jalon/J2` sur CI verte (squash) ; relecture complète sur la
PR `jalon/J2` → `main`.

## 6. Compatibilité

- **Documents existants** : aucune migration ; aucune propriété ajoutée aux pièces. Les
  documents J1–J6 donnent une liste de débit dès leur ouverture.
- **Nouvel objet** : la feuille, objet standard sans proxy ; elle n'entre pas dans le contrat de
  persistance de l'ADR 0003 (seule sa marque `MenuiserieCutList` est figée).
- **Document J2 ouvert par un atelier plus ancien ou sans atelier** : feuille ordinaire.
- **FreeCAD 1.0 et 1.1** : `Spreadsheet::Sheet.set`, `setStyle`, `setAlignment`,
  `setColumnWidth`, `clearAll`, `getUsedCells` (à vérifier en début de J2c pour S2),
  `App::Link.ElementCount`, `LinkedObject`.

## 7. Risques

| N° | Risque | Parade |
|---|---|---|
| K1 | Liste périmée après une modification (pas de recalcul automatique). | Levé par § 10 (Q3 b) : liste vivante, ADR 0013 (V1). |
| K2 | Boîte englobante faussée par une forme usinée invalide ou non recalculée. | Forme absente ou invalide → ajouts nuls et avertissement (D7). |
| K3 | Liens imbriqués, tableaux de liens, liens vers des Std Part contenant d'autres liens. | Lecture récursive avec multiplicateur, profondeur bornée, tests D3 sur 1.0 et 1.1. |
| K4 | Tableur qui lit mal le CSV (séparateur, accents). | BOM UTF-8, `;`, virgule décimale ; recette dans le tableur de jv (G4) ; Q4. |
| K5 | Cellules ajoutées par l'utilisateur effacées à la mise à jour. | Colonnes `P` et au-delà conservées (S2) ; Q3. |

## 8. Hors périmètre

- Optimisation de débit des panneaux (calepinage), chiffrage, prix (plan § 2, « Ensuite »).
- ~~Numérotation automatique des repères~~ : entrée dans J2 (§ 10, Q5 b, N1).
- Bandes de chant et alaises dans la liste (J4b, issue #5) : la structure `Hardware` / lignes les
  accueillera.
- Plans TechDraw par pièce (J5).
- Vis, lamelles, dominos, quincaillerie autre que les tourillons.
- ~~Liste vivante recalculée à chaque modification~~ : entrée dans J2 (§ 10, Q3 b, ADR 0013).

## 9. Questions à jv

**Q1 — Regrouper les pièces identiques : par repère ou par cotes ?**
★ (a) *Repère + cotes + matériau* : deux pièces regroupées seulement si elles ont le même repère
et les mêmes cotes et matériau ; un repère réutilisé pour des pièces différentes est signalé.
(b) *Cotes + matériau seulement* : deux pièces identiques de repères différents (« M1 » et
« M3 ») sont fusionnées sur une ligne « M1, M3 ».

**Q2 — Les pièces de deux ensembles différents (deux caissons) : une liste commune ou une liste
par ensemble ?**
★ (a) *Commune* : on regroupe toutes les pièces identiques, la colonne « Ensemble » cite les
ensembles concernés ; pour une liste d'un seul meuble, on sélectionne l'ensemble avant la
commande. (b) *Par ensemble* : un bloc par ensemble, sans regroupement entre eux.

**Q3 — La feuille se met-elle à jour toute seule ?**
★ (a) *À la demande* : on relance « Liste de débit », la feuille est réécrite (les colonnes que
vous ajoutez à droite sont gardées) et datée. (b) *Automatique* à chaque recalcul : toujours à
jour, mais plus lent sur un gros meuble et la feuille ne peut plus être retouchée (ADR 0012).

**Q4 — Format du CSV.**
★ (a) *Français* : séparateur point-virgule, virgule décimale (s'ouvre directement dans Excel et
LibreOffice en français). (b) *International* : virgule et point décimal. (c) Les deux, au choix
dans la boîte d'export.

**Q5 — Pièces sans repère.**
★ (a) Listées sans repère (« — »), regroupées par cotes, avec un avertissement ; une commande
« Numéroter les repères » viendra plus tard. (b) Ajouter dès J2 la numérotation automatique
(M1, M2… pour les pièces sans repère, à la demande).

**Q6 — Pièce d'un document créé par une version plus récente de l'atelier (issue #13).**
★ (a) *Lecture seule* : la pièce s'affiche et entre dans la liste, mais son matériau ne se modifie
pas (message dans le panneau). (b) *Erreur explicite* à chaque modification du matériau.

## 10. Réponses de jv (2026-10-22) et compléments

Ces réponses priment sur les recommandations ★ du § 9 et sur les critères qu'elles contredisent
(C1, C2, C7, S4, § 4.4, § 4.5 et § 8 : voir les renvois).
Exigence ajoutée, mot pour mot : « La liste de débit doit être exportable en pdf ».

| Question | Réponse | Effet |
|---|---|---|
| Q1 | **b** | Regroupement par cotes, matériau, fil, surcotes et ajouts, **sans le repère** ; une ligne cite tous ses repères triés (« M1, M3 »). |
| Q2 | a | Inchangé : liste commune, colonne « Ensemble ». |
| Q3 | **b** | La liste se met à jour **toute seule** à chaque recalcul : ADR 0012 remplacé par l'ADR 0013. |
| Q4 | **b** | CSV international par défaut : séparateur `,`, point décimal, UTF-8 avec BOM, CRLF. |
| Q5 | **b** | Numérotation automatique des repères dès J2 (commande). |
| Q6 | a | Reformulée puis choisie : matériau verrouillé (déjà livré en J2a). |

### 10.1 Critères modifiés ou ajoutés

| N° | Critère | Test |
|---|---|---|
| C1′ | Clé de regroupement : `(material_id, finished, additions, allowances, grain)` ; `CutLine.marks` = repères distincts non vides, ordre naturel ; colonne « Repère » = `", ".join(marks)` ou « — ». Tri des lignes : premier repère (ordre naturel), lignes sans repère en dernier. | U |
| C2′ | Un même repère porté par des pièces **différentes** (deux groupes) reste signalé (`REPEATED_MARK`). | U |
| C7′ | `to_csv` utilise `INTERNATIONAL_CSV` par défaut ; `FRENCH_CSV` reste disponible (paramètre de l'API `export_cut_list_csv(..., dialect=…)`). | U + I |
| P1 | `to_html(cut_list, translate, title, scope, date) -> str` (pur) : document HTML autonome (titre, date, portée, tableau, totaux, fournitures, avertissements) ; **tout texte échappé** (`html.escape`), aucun script, aucune ressource externe. | U |
| P2 | `export_cut_list_pdf(doc, path, objects=None)` (Gui seulement : `QTextDocument` + `QPdfWriter`, A4 paysage, marges 10 mm) ; mêmes règles de chemin que le CSV (`.pdf` imposé, écriture atomique). Commande `Menuiserie_CutListPdf` « Exporter la liste de débit (PDF)… ». | G + manuel |
| N1 | `number_marks(doc, objects=None, prefix="M")` : chaque **groupe** de pièces sans repère (Q1′) reçoit le premier numéro libre `M<n>` (les repères existants de la forme `M<n>` sont sautés) ; les pièces d'un même groupe partagent le repère ; ordre : ensemble, puis cotes décroissantes ; une transaction « Numéroter les repères » ; les pièces qui ont déjà un repère ne changent pas. Commande `Menuiserie_NumberMarks`. Le libellé suit le repère (J6, doublons « M1 (2) »). | U + I + G |
| V1 | Liste vivante (ADR 0013) : après `make_cut_list`, modifier une cote puis recalculer met la feuille à jour **sans relancer la commande** ; ajouter ou supprimer une pièce aussi (au plus tard au recalcul suivant l'ajout, cf. ADR 0013 § risques) ; Annuler restaure la feuille avec le reste. | I |
| V2 | La liste vivante ne crée aucun cycle : un ensemble, une pièce pilotée par expression ou un assemblage recalculent comme avant (tests J4 inchangés) ; `doc.recompute()` ne laisse rien « Touched ». | I |
| V3 | Document ouvert sans l'atelier : la feuille reste lisible (valeurs enregistrées) ; l'objet `CutList` est signalé sans proxy, sans erreur bloquante. | I |
| V4 | Supprimer l'objet `CutList` (ou la feuille) arrête la mise à jour sans erreur ; relancer « Liste de débit » le recrée. Colonnes `P` et au-delà toujours conservées. | I |

S4 (« pas de recalcul automatique ») est **retiré**.

### 10.3 Demande de jv (recette, 2026-10-22) : aperçu et miniatures

Demande, mot pour mot : « Je veux un affichage visuel avant l'export (html ?). Il doit y avoir
une miniature de la pièce. »

Choix de l'architecte du lot (sans ADR : aucune décision structurante, tout reste dans les
couches existantes) :

- **Miniature** : projection isométrique **maison** des faces de la forme usinée de la première
  pièce du groupe (`features/cutlist_thumbnail.py` : `Face.tessellate` et `Edge.discretize` de
  `Part`, sans rendu 3D ni écran, donc en CI et en ligne de commande) ; le calcul de la
  projection, le tri des faces (algorithme du peintre, faces arrière écartées), l'ombrage par la
  normale et le SVG sont **purs** (`core/cutlist/_thumbnail.py`). `TechDraw.projectEx` n'est pas
  utilisé : il suppose un document et l'atelier TechDraw. Couleur du matériau de la bibliothèque,
  trois tons comme les icônes ; arêtes visibles en trait. Repli : boîte de débit L × l × e quand
  la pièce usinée est absente, invalide, à recalculer ou trop fine (plus de 20 000 triangles).
- **HTML** : le SVG est inclus en URI `data:` (jamais de fichier ni d'URL) ; `QTextDocument`
  l'affiche tel quel, dans la fenêtre comme dans le PDF (image rastérisée à 4 fois sa taille
  d'affichage : 480 × 320 pour 120 × 80). Pas de `addResource`.
- **Fenêtre** : `QDialog` non modale (fille de la fenêtre principale, détruite à sa fermeture)
  avec un `QTextBrowser` (liens désactivés) et les boutons « Actualiser », « Exporter en PDF… »,
  « Exporter en CSV… », « Fermer ». Elle affiche le HTML du PDF ; les exports appellent les
  mêmes fonctions que les commandes d'export (document recalculé avant, refus visibles en boîte).

| N° | Critère | Test |
|---|---|---|
| A1 | `core.cutlist.thumbnail_svg(faces, color)` (pur) : isométrie (`isometric`), faces tournées vers l'arrière écartées, ordre du peintre, trois tons du matériau, arêtes visibles, dessin centré dans 120 × 80 unités, SVG autonome (ni `<text>`, ni script, ni lien) ; `box_faces(L, l, e)` : repli. `features.cutlist_thumbnail.thumbnails_of(doc, cut_list)` : **une miniature par groupe** (clé `CutLine.source`, première pièce du groupe), forme **usinée** (une pièce à tenon ou à queues d'aronde ne donne pas le dessin de la boîte), repli sur la boîte de débit si la forme est absente, invalide ou à recalculer ; 200 pièces en moins de 2 s ; lecture seule. | U + I |
| A2 | `to_html(…, thumbnails=)` : colonne « Miniature » en tête de chaque ligne de la liste (image `data:image/svg+xml;base64`, 120 × 80) ; sans miniatures, le HTML est inchangé ; aucune URL externe ni `file://` ; une miniature qui n'est pas un SVG est refusée. `api.cut_list_html(doc, objects=None)` donne ce HTML (sans interface). | U + I |
| A3 | Commande `Menuiserie_CutListPreview` « Aperçu de la liste de débit » (icône générée par `tools/generer_icones.py`, barre d'outils et menu) : fenêtre non modale, `QTextBrowser` avec une image par ligne, quatre boutons ; portée = sélection, sinon document ; document, sélection et historique d'annulation inchangés ; aucune boîte modale bloquante. | G |
| A4 | Le PDF contient les miniatures ; « Exporter en PDF… » et « Exporter en CSV… » de la fenêtre écrivent les mêmes fichiers que les commandes d'export (annuler la boîte ne fait rien) ; « Actualiser » relit le document. | G + manuel |

### 10.2 Découpage complété

| Lot | Branche | Contenu | Critères |
|---|---|---|---|
| **J2e** | `feat/debit-reponses-core` | C1′, C2′, C7′, `to_html` (P1), logique pure de numérotation (N1) | C1′, C2′, C7′, P1, N1 (U) |
| **J2f** | `feat/debit-vivante` | objet `CutList` (ADR 0013), `make_cut_list` le crée, `number_marks` (document), API | V1–V4, N1 (I) |
| **J2g** | `feat/debit-pdf-numerotation` | commandes PDF et numérotation, icônes, recette et README mis à jour | P2, N1 (G), G4 |
