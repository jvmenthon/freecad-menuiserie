# Menuiserie — atelier FreeCAD

Atelier (workbench) FreeCAD pour concevoir des meubles et ouvrages de menuiserie de façon
paramétrique : pièces de bois réelles, assemblages classiques et liste de débit automatique.

> **Statut : en développement (jalon J4 – ensembles et gabarit Caisson).** La pièce de bois
> paramétrique se crée depuis la barre d'outils ou la console Python, et se modifie dans son panneau de tâche
> ou dans l'éditeur de propriétés ; elle s'affiche avec la texture de son matériau quand la
> bibliothèque en fournit une.

## Fonctionnalités prévues

| Jalon | Contenu |
|---|---|
| J0 | Fondations : atelier chargeable, CI, outillage qualité |
| J1 | Pièce de bois paramétrique, bibliothèque d'essences et de panneaux |
| J2 | Liste de débit (tableau FreeCAD + export CSV) |
| J3 | Assemblages : tenon-mortaise, rainure-languette, tourillons |
| J4 | Ensembles (cotes et onglet **Ensemble**), mi-bois, queue d'aronde, onglet, gabarit de caisson |
| J5 | Plans TechDraw, traductions, publication dans l'Addon Manager |

## Prérequis

- FreeCAD **1.0** ou plus récent.

## Installation (développement)

Clonez le dépôt dans le dossier `Mod` de votre profil FreeCAD, puis redémarrez FreeCAD :

| Système | Dossier `Mod` |
|---|---|
| Linux | `~/.local/share/FreeCAD/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/Mod/` |
| Windows | `%APPDATA%\FreeCAD\Mod\` |

```sh
git clone https://github.com/jvmenthon/freecad-menuiserie.git <dossier Mod>/Menuiserie
```

L'atelier **Menuiserie** apparaît alors dans la liste des ateliers.

## Pièce de bois (barre d'outils)

Dans l'atelier **Menuiserie**, la commande **Pièce de bois** (barre d'outils ou menu
*Menuiserie*) crée une planche de chêne de 800 × 200 × 22 mm et ouvre son panneau de tâche :
repère, type et matériau, sens du fil, cotes finies (avec unités : `80 cm`, `2'`), épaisseurs
standard du matériau en un clic et surcotes de débit. Chaque modification est visible
aussitôt ; **OK** crée une seule entrée d'annulation, **Annuler** ne laisse rien. Un
double-clic sur une pièce rouvre le panneau ; une cote pilotée par une expression y reste
pilotée.

## Poser une pièce contre une autre

Avant de lancer **Pièce de bois**, sélectionnez dans la vue 3D une à trois **faces, arêtes ou
sommets** (pièces de bois, pièces d'un ensemble ou d'un Std Part, objets d'un autre atelier :
Part, PartDesign, esquisse…). La nouvelle pièce apparaît en aperçu semi-transparent **contre** ces
éléments, du côté extérieur de la matière, et le groupe *Rotation* du panneau les cite
(« Contre : Face3 de « Côté gauche » »). Rien de ce que vous avez sélectionné n'est modifié ni
désélectionné.

- **Une face** : la pièce est posée à plat sur la face, par le coin le plus proche du point où vous
  avez cliqué, vers l'intérieur de la face.
- **Une arête** : la pièce s'appuie sur la face voisine la plus tournée vers vous, une de ses
  arêtes confondue avec l'arête choisie.
- **Un sommet** : un coin de la pièce sur le sommet, dans le quart d'espace libre.
- **Deux ou trois éléments** : la pièce touche tous les éléments. Deux faces en vis-à-vis
  (l'intérieur de deux joues) étirent la longueur de la pièce à l'écart entre elles, sans jamais
  changer l'épaisseur ; vous pouvez ensuite saisir la cote que vous voulez, votre saisie
  l'emporte. Un élément qui n'est pas d'équerre avec le premier est ignoré, avec un message.
- Les boutons **X**, **Y**, **Z** font tourner la pièce d'un quart de tour autour de l'axe du
  document sans la détacher de ce qu'elle touche. Contre une face inclinée, ils tournent autour des
  axes de cette face (sa normale et ses arêtes) : limite connue, utilisez Std Transform pour un
  autre axe.
- Si le premier élément est dans un Std Part, la pièce y est créée (même s'il est tourné ou
  déplacé) ; vu à travers un lien, la pièce reste à côté de la copie. Si c'est un membre d'un
  ensemble, la case **Ajouter à l'ensemble « … »** est cochée : la pièce suit ensuite les cotes
  de l'ensemble ; décochez-la pour la laisser à part.

La pièce ne garde aucun lien avec ce qu'elle touche : si l'élément bouge ensuite, elle ne le suit
pas (passez par l'ensemble pour un meuble paramétrique). La sélection se fait **avant** de lancer
la commande. Les éléments d'un même objet sont pris dans l'ordre de FreeCAD, qui regroupe les
sélections par objet.

## Assembler deux pièces

Sélectionnez deux pièces (dans l'arbre ou la vue 3D), puis **Tenon-mortaise**,
**Rainure-languette**, **Feuillure**, **Tourillons**, **Mi-bois**, **Queue d'aronde** ou
**Onglet** (barre d'outils ou menu *Menuiserie*).
L'atelier devine quelle pièce reçoit la mortaise (la traverse dont le bout touche le montant
porte le tenon) et ouvre le panneau de l'assemblage : pièces reliées, bouton **Inverser** pour
échanger leurs rôles, et un champ par paramètre. Une cote cochée **Auto** suit les pièces
(proportions de menuisier, valeur effective affichée) ; décochez-la pour saisir une valeur fixe.
Chaque pièce assemblée devient une « pièce usinée » (tenons ajoutés, mortaises creusées), sa
pièce brute rangée dessous dans l'arbre. Un double-clic sur un assemblage rouvre son panneau,
un double-clic sur une pièce usinée ouvre celui de sa brute.
Pour un **Onglet**, dessinez les deux pièces à leur longueur hors tout (de pointe longue à pointe
longue), qui se chevauchent au coin : la coupe passe par le coin extérieur et le coin intérieur
(45° pour deux largeurs égales) et le panneau affiche les angles de coupe.

## Modifier un meuble (ensemble)

Sélectionnez les pièces d'un meuble, puis **Ensemble** : l'atelier crée un ensemble (largeur,
profondeur, hauteur de la boîte qui contient les pièces) et relie chaque pièce à ses cotes par
des expressions FreeCAD ordinaires, visibles dans l'éditeur de propriétés. Par défaut, toute
distance entre une face et le bord de l'ensemble de son côté est **fixe** : la pièce suit ce
bord quand la cote change. Un double-clic sur l'ensemble ouvre son panneau : les trois cotes,
la liste des pièces (colonne **Suit** : étirée, déplacée, proportion, fixe, formule) et, pour
la pièce choisie, son mode (**Reste en place** ou **Proportion**) et ses six distances aux
bords avec une case **fixe** à décocher là où elle doit rester en place. Une cote qui
casserait une pièce ou un assemblage est refusée dans le panneau (dans l'éditeur de
propriétés, elle est appliquée avec un avertissement et reste annulable). Vos propres formules
sont toujours gardées. **Ajouter à l'ensemble** et **Retirer de l'ensemble** changent ses
pièces ; après une retouche à la main (plateau passé de 30 à 40 mm), **Relier les pièces**
recalcule les expressions. Pour déplacer, tourner ou dupliquer le meuble, rangez l'ensemble et
ses pièces dans un **Std Part**, puis utilisez **App::Link**.

Depuis la console Python, `api.set_edge_distance(piece, "Left", 10)` règle la distance entre
une face de la pièce et ce bord de l'ensemble, comme le champ du panneau.

## Gabarit Caisson

Le bouton **Caisson** ouvre un panneau de paramètres (dimensions, épaisseurs, feuillure du fond,
étagères, assemblage des côtés) avec aperçu dans la vue 3D, puis crée côtés, dessus, dessous,
fond, étagères et assemblages. Le résultat est un **ensemble ordinaire** : il se modifie par le
même panneau (double-clic) et ne se régénère jamais depuis le gabarit, qui ne sert qu'à le
construire (voir l'ADR 0010).

## Liste de débit

**Liste de débit** écrit dans le document une feuille de calcul « Liste de débit » et l'ouvre
dans un onglet : une ligne par groupe de pièces identiques (repère, quantité, cotes finies et
de débit, matériau, fil, volume, masse), puis les totaux par matériau et les tourillons en
fournitures. Les tenons et queues d'aronde sont **compris** dans la longueur de débit ; une
pièce vue par un `App::Link` compte une fois de plus. La liste couvre les objets
**sélectionnés** (pièces, ensemble, Std Part), sinon tout le document. La liste est
**vivante** : la commande crée aussi un objet « Mise à jour de la liste de débit » qui réécrit
la feuille à chaque recalcul du document (cote modifiée, pièce ajoutée ou supprimée, tenon
changé) ; Annuler restaure feuille et pièces ensemble. Supprimer cet objet arrête la mise à
jour, relancer la commande la rétablit. Les colonnes que vous ajoutez à droite de la colonne O
sont gardées, et la feuille reste une feuille FreeCAD ordinaire, lisible sans l'atelier. **Exporter la liste de débit (CSV)…**
enregistre la même liste dans un fichier CSV au format international (séparateur virgule,
point décimal, UTF-8) ; le format français reste disponible depuis la console :
`api.export_cut_list_csv(doc, "debit.csv", dialect=api.FRENCH_CSV)`. Depuis la console :
`api.make_cut_list(doc)`, `api.export_cut_list_csv(doc, "debit.csv")` et
`api.number_marks(doc)`, qui donne un repère `M<n>` à chaque groupe de pièces sans repère
(commande à venir).

## Pièce de bois (console Python)

```python
from freecad.menuiserie.api import make_wood_part

planche = make_wood_part(800, 200, 22, "chene")  # longueur, largeur, épaisseur finies en mm
planche.Length = 1000  # ou depuis l'éditeur de propriétés
planche.Material = "Hêtre"  # masse volumique, catégorie, fil et surcotes suivent
```

La pièce est un parallélépipède : longueur selon X, largeur selon Y, épaisseur selon Z, dans
son repère local ; on l'oriente avec `Placement`. Elle garde l'identifiant, la catégorie et la
masse volumique de son matériau : un plan ouvert sur une autre machine reste exact. Pour pouvoir
annuler une création depuis un script, encadrez-la par `doc.openTransaction(…)` et
`doc.commitTransaction()`.

## Ajouter une essence

L'atelier lit, en plus de sa bibliothèque intégrée (`freecad/menuiserie/data/materiaux.json`), un
fichier personnel qu'il ne crée ni ne modifie jamais :

| Système | Fichier (dossier de données utilisateur de FreeCAD) |
|---|---|
| Linux | `~/.local/share/FreeCAD/Menuiserie/materiaux.json` |
| macOS | `~/Library/Application Support/FreeCAD/Menuiserie/materiaux.json` |
| Windows | `%APPDATA%\FreeCAD\Menuiserie\materiaux.json` |

Selon la version de FreeCAD, ce dossier peut être versionné (par exemple `…/FreeCAD/v1-1/`) :
`FreeCAD.getUserAppDataDir()` dans la console Python donne le bon. Pour utiliser un autre
fichier (bibliothèque partagée), renseignez le paramètre `UserLibraryPath` de
`BaseApp/Preferences/Mod/Menuiserie` :

```python
FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Menuiserie").SetString(
    "UserLibraryPath", "/chemin/vers/materiaux.json"
)
```

Exemple complet (format 1, encodage UTF-8) :

```json
{
  "format": 1,
  "materials": [
    {
      "id": "erable",
      "kind": "solid",
      "name": {"fr": "Érable", "en": "Maple"},
      "density": 650,
      "thicknesses": [22, 27, 34],
      "color": "#E8D2A8"
    },
    {
      "id": "cp-chene",
      "kind": "plywood",
      "name": "Contreplaqué plaqué chêne",
      "density": 680,
      "thicknesses": [10, 15, 19],
      "color": "#C49A6C",
      "has_grain": true
    }
  ]
}
```

- `id` : identifiant stable (minuscules sans accent, chiffres, tirets), enregistré dans les plans ;
  un `id` de la bibliothèque intégrée **remplace** entièrement ce matériau.
- `kind` : `solid` (massif), `plywood` (contreplaqué), `mdf` ou `melamine`.
- `name` : libellé français, ou libellés par langue ; il doit être unique.
- `density` : masse volumique en kg/m³ (50 à 2000) ; `thicknesses` : épaisseurs standard en mm
  (0,1 à 300) ; `color` : couleur d'affichage `#RRGGBB` ; `has_grain` (facultatif) : fil du bois.

Le fichier est lu une fois par session ; après l'avoir modifié, relancez FreeCAD ou exécutez
`from freecad.menuiserie.features.library import reload_library; reload_library()`. Une entrée
invalide est ignorée seule et signalée dans la vue rapport ; les pièces déjà créées gardent
leurs valeurs.

## Ajouter une texture

Un matériau peut afficher une image (veinage, décor) à la place de sa couleur. Ajoutez à son
entrée une clé `texture` :

```json
{
  "id": "noyer-noir",
  "kind": "solid",
  "name": "Noyer noir",
  "density": 610,
  "thicknesses": [22, 27],
  "color": "#4A3326",
  "texture": {"image": "textures/noyer-noir.jpg", "size": [600, 200]}
}
```

- `image` : chemin **relatif** au dossier du fichier `materiaux.json` (séparateur `/`, sans
  `..`), qui doit y rester (un lien symbolique qui en sort est refusé) ; image **PNG** ou
  **JPEG** (`.png`, `.jpg`, `.jpeg`), de **16 Mio** et **4 096 pixels** de côté au plus (un
  JPEG progressif compte au plus 100 balayages).
- `size` : largeur et hauteur **réelles**, en mm (10 à 10 000), couvertes par l'image : une
  image de 600 × 200 mm couvre 600 mm de pièce, quelle que soit sa taille, et se répète au-delà.
- **Sens du fil = largeur de l'image** : orientez la photo pour que le veinage soit horizontal.
  Sur la pièce, il suit la propriété `GrainDirection` (longueur, largeur ; « sans fil » comme
  longueur).

L'image n'est jamais enregistrée dans le plan (`.FCStd`) : elle est relue dans la bibliothèque
à l'ouverture. Sur une machine qui ne l'a pas, ou si elle est absente, illisible ou trop grande,
la pièce garde la couleur `color` du matériau (un avertissement par image dans la vue rapport).
Les textures affichées en même temps occupent au plus 256 Mio d'images décodées (environ cinq
images de 4 096 × 4 096 pixels) ; au-delà, les pièces suivantes gardent leur couleur.
Les faces en bois de bout montrent une bande étirée de l'image ; une pièce sélectionnée ou
survolée s'affiche unie, sans sa texture, le temps de la sélection. Après avoir modifié la
bibliothèque, `reload_library()` puis un nouveau choix de matériau, ou la réouverture du plan,
mettent l'affichage à jour.

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md). Les décisions d'architecture sont consignées dans
[docs/adr](docs/adr).

## Licence

[LGPL-2.1-or-later](LICENSE), comme FreeCAD.
