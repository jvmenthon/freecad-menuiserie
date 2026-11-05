# Quincaillerie : références fournisseurs, modèles 3D et pose simple

- Issue : #159
- Statut : **étude fonctionnelle, à valider par jv** (aucun code, aucun ADR accepté).
- Demande de jv (2026-11-05) : « la feature doit être facile à utiliser » ; proposer les **vraies
  références** des fournisseurs ; savoir qui sont les principaux fournisseurs, comment récupérer leurs
  caractéristiques, s'ils fournissent des modèles 3D, sinon utiliser des modèles 3D génériques ;
  couvrir charnières, coulisses, pieds de caisson, vis, biscuits, et au minimum tourillons et faux
  tenons.
- Contraintes du projet : compatibilité avec les autres addons (ADR 0007), bibliothèque personnelle
  partagée entre projets (ADR 0028, 0031), document autonome (ADR 0002), cœur `core/` sans FreeCAD.

> **Fiabilité de l'étude.** Les points ci-dessous viennent de recherches web ; les pages des
> fabricants (conditions d'utilisation des données CAO) n'ont pas pu être lues en entier. Tout ce qui
> touche aux **licences** est marqué « à vérifier » et doit l'être auprès de chaque fabricant avant
> d'embarquer la moindre donnée. Les références chiffrées sont des exemples à confirmer sur catalogue.

## 1. Constat sur l'existant

L'atelier sait déjà usiner le bois pour des tourillons (J3c : diamètre, longueur, nombre, entraxe
automatiques) et des tenons-mortaises *taillés dans la pièce*. Il ne sait pas :

- poser un **objet du commerce** (charnière, coulisse, pied…) avec sa référence ;
- usiner les **perçages et logements propres à une référence** (cuvette de charnière Ø35, trous de
  vis de la platine, mortaise d'un faux tenon) ;
- **compter** la quincaillerie dans la liste de débit.

## 2. Fournisseurs

Deux familles à distinguer : les **fabricants** (qui publient les références et les données techniques)
et les **distributeurs** (qui vendent, avec leurs propres références).

| Fabricant | Spécialité | Données CAO publiques (d'après les sites) |
|---|---|---|
| **Blum** (AT) | charnières Clip top, coulisses Tandem / Movento, tiroirs Legrabox | service « CAD/CAM Data Service » : 3D par produit ou paquets complets, 2D de pose, **macros CNC** ; inscription gratuite |
| **Hettich** (DE) | coulisses, tiroirs ArciTech / InnoTech, charnières Sensys, ferrures coulissantes | « Hettich CAD » : plus de 15 000 articles, plus de 80 formats (DWG / DXF, parfois STEP / SAT / IGES) ; **perçages DXF** pour la CNC |
| **Häfele** (DE) | catalogue général (plus de 40 000 articles CAD annoncés), pieds, assemblages Minifix / Rafix, tourillons | téléchargement CAO sans inscription d'après un forum, prix masqués sans compte (à vérifier) |
| **Grass** (AT) | charnières, coulisses, tiroirs Nova Pro | à explorer |
| **Salice** (IT) | charnières, vérins | à explorer |
| **Lamello** (CH) | biscuits, Clamex, Tenso, Zeta | à explorer (le biscuit est un standard de fait : P-system) |
| **Festool** (DE) | faux tenons **Domino** (4×20 à 14×140) | tableau des tailles public ; pas de modèle 3D confirmé |
| Titus (Häfele), Würth, Mepla, Richelieu… | gammes complémentaires, distributeurs | à explorer |

Côté France, les distributeurs professionnels (Formusson / groupe Mirwault, Richelieu, Häfele
France…) revendent ces marques avec leurs propres codes. **Recommandation** : indexer par la
**référence du fabricant** (stable, mondiale) et garder la référence distributeur comme champ libre
facultatif.

## 3. Comment récupérer les caractéristiques

| Voie | Contenu | Avantages | Limites |
|---|---|---|---|
| **A. Téléchargement manuel** sur le portail du fabricant (3D, DXF de perçage) | forme réelle, cotes exactes | fiable, officiel | inscription, conditions d'utilisation, **pas de redistribution probable** |
| **B. Catalogues électroniques** BMEcat / ETIM, DATANORM (surtout DE / AT / CH) | nom, référence, caractéristiques, prix | structuré, automatisable | souvent réservé aux revendeurs ; peu de géométrie ; licence |
| **C. Saisie des cotes par nous** (fiche technique publique → fichier JSON de l'atelier) | cotes fonctionnelles (entraxes, diamètres, profondeurs) | libre de droits si ce sont des **faits techniques** saisis à la main, redistribuable | travail de saisie ; risque d'erreur ; à relire ; les marques et photos restent protégées |
| **D. Scraping du site / de l'eShop** | tout | — | **à écarter** : conditions d'utilisation, fragilité, risque juridique |
| **E. Import par l'utilisateur** de ses propres fichiers STEP / DXF | modèle réel de la référence | licence respectée (l'utilisateur les a téléchargés lui-même) | demande un effort à l'utilisateur |

**Constat important** : aucune source consultée ne permet de **redistribuer** les modèles 3D des
fabricants avec l'addon ; ils sont conçus pour être téléchargés par l'utilisateur final. Conséquence
directe : **l'addon ne doit pas embarquer les STEP des fabricants** sans accord écrit.

## 4. Modèles 3D : fabricants ou génériques ?

Les fabricants fournissent des modèles (Blum, Hettich, Häfele au moins), mais :

1. ils sont lourds (détail complet de mécanisme) et ralentissent un document de meuble ;
2. leur licence n'autorise pas, à notre connaissance, la redistribution ;
3. ils ne sont pas paramétriques (une longueur de coulisse = un fichier).

**Recommandation (à valider, Q2) — deux niveaux, le premier suffisant :**

- **Niveau 1, génériques paramétriques (intégrés).** Pour chaque *famille* (charnière à cuvette Ø35,
  coulisse à billes, pied de caisson réglable, vis à bois, biscuit, tourillon, faux tenon), un modèle
  simplifié construit en Python pur à partir de **cotes fonctionnelles** : enveloppe, point de pose,
  perçages et logements à usiner. Le catalogue (références réelles) ne fournit que des **nombres** (§5).
  Licence : nôtre. Poids : très léger.
- **Niveau 2, modèle du fabricant (facultatif, importé par l'utilisateur).** Une référence peut
  pointer vers un fichier STEP que l'utilisateur a téléchargé ; il remplace l'affichage générique,
  jamais les cotes d'usinage. Le dossier est celui de l'atelier (ADR 0031).

Les pièces de visserie standard (ISO / DIN) peuvent aussi venir de l'addon **Fasteners** s'il est
installé ; il est tiers et sa licence est indiquée de façon contradictoire selon les sources
(LGPL ou GPL2, à vérifier). Ne pas en dépendre : détecter sa présence, rien de plus (ADR 0007).

## 5. Format du catalogue

Fichier JSON, strict comme `dimensions.json` (ADR 0028) :

```
{"format": 1, "items": [{
  "id": "blum-71b3550",            // fabricant + référence, unique
  "manufacturer": "Blum", "reference": "71B3550",
  "family": "hinge-cup-35",        // famille générique (niveau 1)
  "label": "Charnière CLIP top 110° à recouvrement",
  "params": {"cup_diameter": 35, "cup_depth": 13, "edge_distance": 5, "screw_pitch": 45, ...},
  "source": "fiche technique publique, 2026-11"
}]}
```

- **Catalogue intégré** (livré avec l'addon) : quelques dizaines de références parmi les plus
  courantes, **saisies à la main** (voie C), chaque entrée avec sa source.
- **Catalogue personnel** (dossier de l'atelier) : l'utilisateur ajoute ses références ; une entrée du
  même `id` remplace l'intégrée (comme les matériaux).
- Pas de prix ni de marque figurative dans le catalogue intégré (simple nomenclature factuelle).

### 5 bis. Décision de jv (2026-11-05) : catalogue local d'abord, téléchargement plus tard

- **Ce jalon** : seulement un **petit catalogue local** livré avec l'addon, de quelques références de
  base (voie C). Aucune connexion réseau, aucun compte, l'addon reste utilisable hors ligne.
- **Plus tard, dans le cadre du SaaS** : télécharger d'autres références depuis un service. Cela
  relève d'issues séparées portant le label **Saas-feature** (issue #161), hors de ce jalon.
- Pour que ce second temps ne change rien au format, le catalogue est conçu comme un **jeu de
  sources** : `items` du catalogue intégré, du catalogue personnel, et plus tard des « paquets »
  téléchargés dans le dossier de l'atelier, tous au même format `{"format": 1, "items": […]}` et
  fusionnés par `id` (la source la plus proche de l'utilisateur l'emporte : personnel, paquet,
  intégré). Un paquet est un simple fichier JSON déposé dans le dossier : le téléchargement viendra
  l'y mettre, sans que l'addon ait à changer.
- **Contenu minimal du catalogue local** (valeurs à confirmer sur fiches techniques) :
  tourillons Ø6×30, Ø8×35, Ø10×40 ; faux tenons Domino 5×30, 6×40, 8×40, 8×50, 10×50 ; biscuits
  Lamello n° 0, 10, 20 ; vis à bois / aggloméré Ø3,5, 4, 5 à longueurs courantes ; une charnière
  à cuvette Ø35 générique et une coulisse à billes générique, sans fabricant, pour tester le parcours.
  Les références Blum, Hettich, etc. viendront avec le lot Q-e.
- Famille inconnue d'une version plus ancienne : la référence reste dans la liste de débit, sans forme.

## 6. Types de quincaillerie : priorités

| Priorité | Type | Ce que l'atelier fait | Difficulté |
|---|---|---|---|
| **1** | **Tourillon** | déjà posé par J3c ; ajouter la **référence** (Ø × L du commerce) et le compte | faible |
| **1** | **Faux tenon (Domino)** | mortaises *aux deux pièces* (profil plat arrondi), tenon séparé en bois, tailles 4×20 … 10×50 (valeurs à confirmer) | moyenne : nouveau gabarit de mortaise |
| **1** | **Biscuit (lamelle)** | fente en arc dans chaque pièce, tailles 0, 10, 20 | moyenne |
| 2 | **Vis** (bois, aggloméré, tête fraisée, ISO / DIN) | trou de passage + avant-trou, fraisage ; choix du diamètre et de la longueur selon l'épaisseur | faible à moyenne |
| 2 | **Pied de caisson réglable** | pose sur la face du dessous, 4 points ou plus, trou ou embase | faible |
| 3 | **Charnière à cuvette** (Blum, Salice, Grass, Hettich) | cuvette Ø35 sur la porte (profondeur, distance au bord), platine sur le côté (entraxe 32 mm) | moyenne : dépend de la référence et du recouvrement |
| 3 | **Coulisse de tiroir** | pose sur côté de caisson et de tiroir à hauteur réglée, longueur selon profondeur ; trous système 32 | forte : cotes liées à la longueur, au poids, au type |

Les types 3 sont ceux qui bénéficient le plus de **références réelles** ; les types 1 sont déjà des
assemblages (le « bon » exemple pour commencer).

## 7. Parcours utilisateur simple

L'objectif de jv est la facilité ; quatre gestes au plus :

1. **Choisir** : commande « Quincaillerie » → un seul panneau : filtre par type, fabricant, mot-clé
   (« Clip top 110° »), vignette générique, cotes lisibles. Les références récentes ou favorites en
   tête (stockage dans le dossier de l'atelier, ADR 0031).
2. **Poser** : sélectionner dans la vue 3D **une face ou deux pièces** ; l'atelier propose
   automatiquement l'emplacement (charnière : à 100 mm des angles et entraxe 32 mm ; coulisse : à
   hauteur du milieu ; pied : aux quatre coins ; faux tenon : régulièrement le long du joint).
3. **Régler** : un petit éditeur (décalage, nombre, côté) avec **aperçu en direct** dans la vue 3D
   (règle générale de jv, 2026-10-22) ; changer de référence sans repartir de zéro.
4. **Suivre** : la quincaillerie **suit les pièces** (expressions natives, ADR 0009) comme les
   assemblages, y compris dans un ensemble qu'on étire.

Les logements usinés viennent d'un **plan d'usinage** de la quincaillerie, comme pour un assemblage
(ADR 0006) : la pièce usinée se perce, la brute n'est pas touchée.

## 8. Liste de débit et nomenclature

- Nouvelle section « Quincaillerie » : référence fabricant, libellé, **quantité**, pièces concernées,
  regroupée par référence.
- Export CSV avec les colonnes `fabricant`, `référence`, `quantité`, pour qu'un devis ou une commande
  puisse suivre (cf. idée « SaaS menuisiers », hors périmètre de ce jalon).

## 9. Compatibilité avec les autres addons

- La quincaillerie est un objet Python standard avec une forme `Part` ; aucun format propriétaire.
- Le modèle importé en niveau 2 est un STEP ordinaire, utilisable ailleurs.
- Aucune modification globale de FreeCAD, noms dans notre espace (ADR 0007).
- Fasteners : ne jamais remplacer ni dépendre ; éventuelle passerelle ultérieure.

## 10. Découpage proposé (si jv valide)

| Lot | Contenu |
|---|---|
| Q-a | `core/hardware/` : schéma du catalogue, lecture stricte, familles et leurs cotes d'usinage (pur Python, tests) |
| Q-b | Catalogue local intégré minimal (§ 5 bis) : tourillons, faux tenons Domino, biscuits, quelques vis |
| Q-c | Fonctionnalité : pose sur face / assemblage, plan d'usinage, aperçu en direct, panneau de choix |
| Q-d | Liste de débit : section quincaillerie, export CSV |
| Q-e | Pieds de caisson et charnières à cuvette (références réelles Blum, Salice, Grass, Hettich) |
| Q-f | Coulisses de tiroir |
| Q-g | Import facultatif d'un STEP du fabricant (niveau 2) |
| (SaaS) | Téléchargement de paquets de références : issues **Saas-feature**, hors jalon |

ADR à écrire avant Q-a : « Quincaillerie : catalogue de références, modèles génériques » (décisions
de §4 et §5).

## 11. Questions pour jv

- **Q1.** Données : valider la voie C (cotes saisies à la main depuis les fiches publiques, aucun
  fichier de fabricant embarqué) ? ★ oui.
- **Q2.** Modèles 3D : génériques paramétriques d'abord, STEP du fabricant en option importée par
  l'utilisateur plus tard ? ★ oui.
- **Q3.** Périmètre du premier jalon : tourillons, faux tenons, biscuits et vis (lots Q-a à Q-d) ?
  Charnières, pieds et coulisses ensuite ? ★ oui.
- **Q4.** Marques d'abord : Blum et Hettich (et Festool / Lamello pour tenons et biscuits) puis
  Häfele, Grass, Salice ? ★ oui.
- **Q5.** Contacter les fabricants pour un accord de redistribution (utile seulement si on veut
  embarquer leurs STEP) : à lancer par vous ?
- **Q6.** Votre atelier utilise-t-il quelle gamme de quincaillerie ? Les références réellement
  employées priment sur la liste du § 2.
