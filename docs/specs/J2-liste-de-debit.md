# [J2] Liste de débit

- Jalon : J2 (issue #13), après J4 et J6, à la demande de jv
- Statut : **proposée** (questions du § 9 posées à jv ; les recommandations ★ s'appliquent tant
  qu'il n'a pas répondu)
- Branche : `jalon/J2`, partie de `jalon/J6` (PR #38 et #48 pas encore fusionnées dans `main`)
- ADR liés : [0002 — Bibliothèque de matériaux](../adr/0002-bibliotheque-de-materiaux.md),
  [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md),
  [0006 — Pièce brute et pièce usinée](../adr/0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](../adr/0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](../adr/0008-ensemble-objet-de-cotes.md),
  **[0012 — Liste de débit calculée à la demande](../adr/0012-liste-de-debit-a-la-demande.md)** (proposé)
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
| C5 | Totaux par matériau : quantité, volume de débit (m³), masse (kg) ; pour un panneau (contreplaqué, MDF, mélaminé) aussi la **surface** (m², L × l de débit). Total général de masse. | U |
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
| D7 | Une pièce en erreur (forme non recalculée, cote invalide) n'interrompt pas la liste : elle est listée d'après ses propriétés et un avertissement la nomme. | I |
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
class CutEntry:            # une pièce brute vue une fois (quantity occurrences)
    record: PartRecord     # J1b : repère, matériau, cotes finies, surcotes, fil, densité
    quantity: int = 1
    additions: Dimensions3 = ZERO   # ajouts des assemblages (mm), le long de L, l, e
    furniture: str = ""             # libellé de l'ensemble, affichage seulement
    source: str = ""                # nom interne de l'objet, pour les avertissements

@dataclass(frozen=True)
class Hardware:            # fourniture (tourillon)
    kind: HardwareKind     # DOWEL (seul en J2)
    diameter: float
    length: float
    quantity: int

@dataclass(frozen=True)
class CutLine:             # un groupe de pièces identiques
    mark: str; quantity: int; material_id: str; material_name: str; kind: MaterialKind
    finished: Dimensions; rough: Dimensions; grain: GrainDirection
    furniture: tuple[str, ...]          # ensembles concernés, triés, sans doublon
    def volume_m3(self, rough: bool) -> float: ...
    def mass_kg(self, rough: bool) -> float: ...
    def area_m2(self) -> float: ...     # L × l de débit × quantité (panneaux)

@dataclass(frozen=True)
class CutList:
    lines: tuple[CutLine, ...]
    totals: tuple[MaterialTotal, ...]
    hardware: tuple[Hardware, ...]
    warnings: tuple[Notice, ...]        # Notice de J4 (gabarit traduit + paramètres)

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
aucun proxy (ADR 0012) : un document sans l'atelier l'ouvre sans message.

### 4.5 Export CSV

Module `csv` de la bibliothèque standard, écrit dans une chaîne (`io.StringIO`) par `core`, puis
fichier écrit par `features/cutlist_export.py` : `pathlib.Path`, extension `.csv` imposée,
dossier parent existant, `tempfile.NamedTemporaryFile(dir=parent, delete=False)` puis
`os.replace`. Dialecte `FRENCH_CSV` (★ Q4) : `;`, virgule décimale, `utf-8-sig`, `\r\n` ; le
dialecte est un paramètre de `core` pour un futur choix « international » (`,` et point).

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
| K1 | Liste périmée après une modification (pas de recalcul automatique). | Date et portée en tête ; infobulle ; mise à jour en un clic (ADR 0012) ; Q3. |
| K2 | Boîte englobante faussée par une forme usinée invalide ou non recalculée. | Forme absente ou invalide → ajouts nuls et avertissement (D7). |
| K3 | Liens imbriqués, tableaux de liens, liens vers des Std Part contenant d'autres liens. | Lecture récursive avec multiplicateur, profondeur bornée, tests D3 sur 1.0 et 1.1. |
| K4 | Tableur qui lit mal le CSV (séparateur, accents). | BOM UTF-8, `;`, virgule décimale ; recette dans le tableur de jv (G4) ; Q4. |
| K5 | Cellules ajoutées par l'utilisateur effacées à la mise à jour. | Colonnes `P` et au-delà conservées (S2) ; Q3. |

## 8. Hors périmètre

- Optimisation de débit des panneaux (calepinage), chiffrage, prix (plan § 2, « Ensuite »).
- Numérotation automatique des repères (★ Q5 : commande séparée plus tard).
- Bandes de chant et alaises dans la liste (J4b, issue #5) : la structure `Hardware` / lignes les
  accueillera.
- Plans TechDraw par pièce (J5).
- Vis, lamelles, dominos, quincaillerie autre que les tourillons.
- Liste vivante recalculée à chaque modification (ADR 0012, option écartée).

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
