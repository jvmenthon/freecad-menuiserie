# Gabarits : socle commun et gabarits personnels

- Issue : #152 (gabarits de meubles) ; suite du gabarit « Caisson » (J4d).
- Statut : **à valider par jv** (décisions de jv du 2026-11-05 au 2026-11-11 intégrées, § 1).
- ADR : [0050 — Registre de gabarits et panneau généré](../adr/0050-registre-de-gabarits-et-panneau-genere.md)
  et [0051 — Gabarit personnel : description JSON d'un ensemble](../adr/0051-gabarit-personnel-description-json.md)
  (proposés). ADR liés : 0007 (compatibilité), 0008, 0009, 0019 (ensembles), 0010 (gabarits
  générateurs, inchangé), 0031 (configuration de l'atelier), 0043 à 0047 (répétition), 0046
  (arbre simplifié).
- Réflexion préalable : [gabarits-problematiques.md](gabarits-problematiques.md) (P1 à P31).
- Suite : [gabarits-meubles.md](gabarits-meubles.md) (Bibliothèque, Table, Cadre-porte, Tiroir),
  **après** cette spécification.

## 1. Décisions de jv

| # | Décision | Date |
|---|---|---|
| D1 | Ordre : **socle d'abord** (registre, panneau généré, galerie, caisson migré), puis gabarit personnel « tel quel », puis éditeur de règles, puis les meubles. | 2026-11-11 |
| D2 | Gabarits personnels rangés dans un **dossier global** : `<données utilisateur FreeCAD>/Menuiserie/gabarits/`, repris plus tard par le réglage « Dossier de l'atelier » (#148, ADR 0031). Utilisables dans tous les projets. | 2026-11-06, 2026-11-11 |
| D3 | **Portée globale seule** dans un premier temps ; la portée « projet » (gabarit rangé dans le `.FCStd`) viendra plus tard, sans migration. | 2026-11-06 |
| D4 | Panneau d'un gabarit : l'**essentiel** visible (taille usuelle, L × P × H, matériau), le reste dans « Options avancées », **repli mémorisé**. | 2026-11-11 |
| D5 | Gabarit personnel enregistré en **fichier de description JSON** (aucun code exécuté). | 2026-11-11 |
| D6 | Éditeur de règles : **quatre verbes** (suivre, répéter, exposer, optionnel) ; une **couleur par rôle** de pièce **plus un marqueur** pour un rôle cumulé ; palette **esthétique** par défaut ; mode daltonien et couleurs personnalisées dans les préférences (#148). | 2026-11-06, 2026-11-11 |
| D7 | Gabarit personnel : on sélectionne un ensemble ; **tel quel** = enregistré directement ; **modulaire** = règles posées dans l'éditeur. L'IA du SaaS (proposer des règles) viendra plus tard et produira la **même description**. | 2026-11-05 |
| D8 | Questions Q1 à Q10 des meubles : tranchées **au début du lot des meubles**. | 2026-11-11 |

## 2. Ce qui existe déjà et qu'on réutilise

- **Gabarit générateur** (ADR 0010) : fonction pure `…_layout(params) → Layout`, construite par
  `features/templates.py` en pièces, assemblages et Ensemble ordinaires. Inchangé.
- **Ensemble** (ADR 0008, 0009, 0019) : cotes globales, distances « fixe / non fixe », modes
  `Stay` / `Proportional`, `predict` et `check_resize` (refus et avertissements). C'est le verbe
  **Suivre**.
- **Répétition** (ADR 0043 à 0047) : objet `Repeat` persistant, nombre et pas modifiables après coup,
  grille, butée, copies liées. C'est le verbe **Répéter** : on ne crée pas un second mécanisme.
- **Matériau d'ensemble** (#77), **sous-ensembles** (ADR 0037), **panneau « Structure »** (ADR 0046).

## 3. Socle (lots GS-a à GS-d)

### 3.1 Registre et description des paramètres (ADR 0050)

`core/templates/_registry.py` : chaque gabarit intégré se déclare une fois par un
`TemplateEntry` (objet valeur, figé) :

| Champ | Contenu |
|---|---|
| `id` | identifiant stable, écrit dans `Template` de l'ensemble (`Carcass`…) |
| `label`, `category`, `thumbnail` | libellé traduisible, catégorie de la galerie, nom de l'icône (générée par `tools/generer_icones.py`) |
| `fields` | tuple de `FieldSpec` : `name`, `kind` (`length`, `count`, `choice`, `material`, `flag`), `label`, `tooltip`, bornes, défaut, `advanced` (vrai = replié), `group` (titre de groupe) |
| `presets` | tailles usuelles : `(label, {name: valeur})` |
| `build_params` | `dict → …Params` (valide ; refus = `TemplatedError` qui cite le champ) |
| `layout` | `…Params → Layout` (pur) |

Les règles qui portent sur plusieurs champs restent dans `…Params` (P2) : le panneau affiche leur
refus sous le champ cité. Les dépendances d'affichage (P3) se limitent à `hidden_if`
(`{"back_style": "None"}`), comme les champs d'assemblage de la quincaillerie.

### 3.2 Panneau généré

`gui/task_panels/template.py` : `TemplateTaskPanel(entry)` construit ses champs depuis `fields` :

1. en haut, la liste « Taille usuelle » (`presets`, plus « Personnalisée ») ;
2. groupe **Essentiel** : champs non `advanced` (L × P × H, matériau) ;
3. groupe repliable **Options avancées** : les autres, par `group` ;
4. aperçu en direct à chaque changement (`valueChanged`, règle de jv du 2026-10-22), une seule
   transaction « Créer un {label} », refus affiché sous le champ, OK grisé tant qu'il y a un refus ;
5. l'état replié ou déplié est mémorisé par gabarit
   (`Mod/Menuiserie/Templates/<id>/AdvancedOpen`, D4) ;
6. placement : contre la sélection comme une pièce neuve (J6), sinon à l'origine.

Champs à saisie clavier : `setKeyboardTracking(False)` (norme « Entrées utilisateur » de
`CONTRIBUTING.md`).

### 3.3 Galerie

Commande `Menuiserie_Template` (« Gabarit… ») : une boîte de dialogue à vignettes, classées par
catégorie (« Caissons et rangements », « Tables et bureaux », « Portes et façades »,
« Tiroirs », « Mes gabarits »), avec une recherche par nom. Un clic choisit, « Créer » (ou
double-clic) ouvre le panneau généré. « Mes gabarits » liste les fichiers du dossier global (§ 4)
avec leur vignette ; un fichier refusé y apparaît grisé, avec la raison en infobulle.
La commande `Menuiserie_Carcass` reste, comme raccourci vers le panneau du caisson.

### 3.4 Caisson migré

`carcass.py` gagne sa déclaration (`TemplateEntry`), le panneau `gui/task_panels/carcass.py`
disparaît au profit du panneau généré. Comportement inchangé : les tests K1 à K7 de J4 et ceux du
lot #214 (poignées de l'ensemble après création) passent sans modification de leurs attentes.

## 4. Gabarit personnel (lots GP-a à GP-c, ADR 0051)

### 4.1 Le fichier

`<dossier des gabarits>/<nom>.gabarit.json` + `<nom>.png` (vignette). Dossier par défaut :
`<données utilisateur FreeCAD>/Menuiserie/gabarits/` (D2) ; quand #148 livrera « Dossier de
l'atelier », ce sera `<dossier de l'atelier>/gabarits/`, même chemin par défaut, rien à migrer.

Contenu (format 1) :

```json
{
  "format": 1,
  "template": {"name": "Caisson cuisine 60", "category": "Mes gabarits", "created": "2026-11-12"},
  "furniture": {"label": "Caisson cuisine", "size": [600, 560, 720], "material": "cp-bouleau"},
  "pieces": [{"key": "p1", "label": "Côté gauche", "dims": [720, 560, 18],
              "placement": [[...matrice 3×4 relative à l'Origin...]],
              "material": "cp-bouleau", "grain": "Length",
              "mode": "Stay", "fixed": ["left", "right", "front", "back", "bottom", "top"]}],
  "joints": [{"kind": "Dowels", "host": "p1", "guest": "p3", "params": {"diameter": 8}}],
  "repeats": [{"sources": ["p5"], "mode": "Linear", "lines": [...], "stops": [...]}],
  "children": [ ...sous-ensembles, même forme... ],
  "parameters": [ ...§ 4.3, vide pour un gabarit « tel quel »... ],
  "options": [ ...§ 4.3... ]
}
```

- **Lecture stricte** (comme `materiaux.json` et `dimensions.json`) : 256 Kio au plus, JSON strict,
  `format` connu, au plus 300 pièces, clés inconnues ignorées avec avertissement, nombres finis
  et bornés, matériaux contrôlés par la bibliothèque, paramètres d'assemblage revalidés par le
  registre des assemblages ; un fichier invalide est refusé **entier** avec un message qui cite
  la clé. Aucun code exécuté, aucun chemin suivi hors du dossier.
- **Écriture** atomique (fichier temporaire puis renommage), nom de fichier tiré du nom du gabarit
  et nettoyé (lettres, chiffres, tirets) ; un nom existant demande « remplacer / renommer ».
- Le fichier est un `Layout` sérialisé, étendu des répétitions et sous-ensembles : la construction
  passe par le même `features/templates.py`.

### 4.2 Enregistrer « tel quel » (GP-a)

Clic droit sur un ensemble (vue 3D, arbre ou panneau « Structure ») → **« Enregistrer comme
gabarit… »** : nom, catégorie (« Mes gabarits » par défaut), case « Modulaire » (décochée).

- Ce qui est enregistré : pièces de bois de l'ensemble et de ses sous-ensembles (cotes,
  placement relatif à l'`Origin`, matériau, sens du fil, mode et options « fixe »), assemblages
  entre ces pièces, répétitions dont les sources sont dans l'ensemble, matériau d'ensemble.
- **Refus** avec la liste des objets en cause : pièce hors atelier ou pièce en bois enveloppe d'un
  corps (ADR 0020) ; assemblage vers une pièce extérieure à l'ensemble ; butée de répétition hors
  de l'ensemble. Le message propose de les retirer de l'ensemble ou de dissocier.
- Vignette : capture de la vue 3D, ensemble seul, vue isométrique, 256 × 256.
- À l'usage, le gabarit se crée **à sa taille d'origine**, puis l'ensemble prend les cotes saisies
  (L × P × H, essentiel) par le mécanisme de l'Ensemble : les pièces suivent selon les options
  « fixe » enregistrées, refus de `check_resize` affichés sous les cotes.

### 4.3 Éditeur de règles (GP-b, puis GP-c)

« Enregistrer comme gabarit… » avec **Modulaire** coché ouvre un panneau en trois étapes ; l'ensemble
reste visible, chaque pièce colorée selon son rôle (§ 4.4).

1. **Suivre** (cotes) : la pièce choisie montre ses six distances « fixe / non fixe » et son mode,
   comme le panneau d'ensemble ; c'est le même réglage, appliqué au document (annulable). Un bouton
   « Proposer » pré-remplit d'après la géométrie : une pièce qui touche deux bords opposés de
   l'ensemble s'étire sur cet axe, une pièce intérieure reste (`Stay`).
2. **Répéter et options** :
   - **Répéter** : crée ou modifie une répétition (panneau de la répétition existant) ;
   - **Optionnel** : choisir des pièces → un groupe nommé (« Socle »), coché par défaut ou non. Au
     plus 5 groupes ; à l'enregistrement, chacune des combinaisons (32 au plus) est construite en
     `core` et vérifiée : un assemblage ou une répétition qui perd une pièce est retiré, une butée
     ou une liaison qui perd sa pièce est **refusée** (message nommant le groupe).
3. **Paramètres et essai** :
   - **Exposer** : rendre réglable L, P, H de l'ensemble (toujours exposés), le nombre ou le pas
     d'une répétition, l'épaisseur d'un groupe de pièces, le matériau d'un groupe de pièces ; chaque
     paramètre a un nom, des bornes, un défaut, « essentiel » ou « avancé » ;
   - **Essai** : des curseurs sur les paramètres exposés, appliqués à l'aperçu (transaction
     abandonnée à la sortie), avec les refus et avertissements de l'ensemble et de la répétition.
     Bouton « Enregistrer » grisé tant qu'un essai aux bornes échoue (bornes min et max de chaque
     paramètre, testées en `core` par `predict`).

**GP-c (plus tard)** : champ « formule » replié d'un paramètre dérivé (paramètres nommés, `+ − × ÷`,
parenthèses, nombres), analysé et évalué par `core` (analyseur dédié, jamais `eval`).

### 4.4 Couleurs par rôle (D6)

Pendant l'éditeur seulement, chaque pièce prend la couleur de son **rôle principal** ; un rôle
cumulé est montré par un **contour** de la couleur du second rôle (lignes plus épaisses). Les
couleurs du matériau sont rétablies à la fermeture ; elles sont posées **hors transaction** (pas
d'entrée d'annulation, comme la transparence en édition, PR #132). Une légende est dans le panneau.

| Rôle (ordre de priorité) | Calcul | Couleur par défaut |
|---|---|---|
| Optionnelle | membre d'un groupe optionnel | prune `#9B6B9E` |
| Se répète | source ou copie d'une répétition | ocre `#D08C4A` |
| S'étire | une cote change quand L, P ou H passe de +100 mm (`predict`) | bleu canard `#2A7F9E` |
| Se déplace | seule la position change dans ce même essai | vert sauge `#7FA36B` |
| Fixe | rien ne change | ardoise `#6B7A8F` |

Rôle principal = le premier de la liste ; le contour = le suivant. La légende indique aussi, pour
la pièce choisie, l'axe concerné (« s'étire en largeur »). Préférences (#148, plus tard) : mode
daltonien (palette Okabe-Ito) ou couleurs personnalisées ; en attendant, la palette est une
constante de `gui/`.

## 5. Critères d'acceptation

U = unitaire (`core`, sans FreeCAD), I = intégration FreeCAD (CI), G = interface, manuel.

### GS-a — Registre et description des paramètres

| N° | Critère | Test |
|---|---|---|
| S1 | `TemplateEntry` et `FieldSpec` refusent une déclaration incohérente (nom en double, défaut hors bornes, `hidden_if` vers un champ inconnu, preset avec un champ inconnu). | U |
| S2 | `registry()` contient `Carcass` ; `entry("Carcass").build_params(defaults)` donne le caisson de référence (600 × 400 × 720, 1 étagère) et `layout` le même `Layout` que `carcass_layout` aujourd'hui. | U |
| S3 | `build_params` avec une valeur refusée lève `TemplatedError` dont `params["field"]` est le libellé du champ. | U |

### GS-b — Panneau généré

| N° | Critère | Test |
|---|---|---|
| S4 | Le panneau du caisson montre « Taille usuelle », L, P, H, matériau ; « Options avancées » replié au premier usage ; déplié puis refermé, il se rouvre déplié (paramètre mémorisé). | G |
| S5 | Changer une cote recrée l'aperçu dans une seule transaction ; « Annuler » ne laisse aucun objet ; « OK » laisse une entrée d'annulation « Créer un caisson ». | I |
| S6 | Valeur refusée : message sous le champ, OK grisé ; corrigée : message retiré, OK actif. | G |

### GS-c — Galerie

| N° | Critère | Test |
|---|---|---|
| S7 | `Menuiserie_Template` ouvre la galerie : catégories, vignette du caisson, recherche « cai » → caisson seul. | G |
| S8 | « Mes gabarits » liste les fichiers valides du dossier ; un fichier invalide est grisé avec sa raison en infobulle ; le dossier absent est créé à la première écriture, pas à la lecture. | I |

### GS-d — Caisson migré

| N° | Critère | Test |
|---|---|---|
| S9 | Tests K1 à K7 (J4) et ceux de #214 inchangés et verts ; `Menuiserie_Carcass` ouvre le panneau généré. | U, I |

### GP-a — Gabarit personnel « tel quel »

| N° | Critère | Test |
|---|---|---|
| P1 | `to_description(layout)` puis `from_description(…)` redonnent le même `Layout` (pièces, assemblages, répétitions, sous-ensembles) ; le JSON est stable (clés triées, nombres à 6 décimales). | U |
| P2 | Lecture stricte : fichier > 256 Kio, JSON invalide, `format` inconnu, nombre non fini, matériau inconnu, paramètres d'assemblage refusés, clé de pièce inconnue dans un assemblage : refus **entier** citant la clé. Clé inconnue ailleurs : avertissement. | U |
| P3 | « Enregistrer comme gabarit… » sur un caisson créé par le gabarit Caisson : fichier et vignette écrits ; recréé depuis la galerie à 800 × 500 × 900, il donne les mêmes pièces que le caisson redimensionné à la main. | I |
| P4 | Refus : ensemble contenant une pièce en bois enveloppe d'un corps, ou un assemblage vers une pièce extérieure : message listant les objets ; rien n'est écrit. | I |
| P5 | Nom déjà pris : « remplacer / renommer » ; écriture atomique (un échec d'écriture laisse l'ancien fichier intact). | U, I |
| P6 | Un ensemble avec une répétition (étagères ×3) et un sous-ensemble (tiroir) s'enregistre et se recrée, répétition modifiable après coup. | I |

### GP-b — Éditeur de règles et couleurs

| N° | Critère | Test |
|---|---|---|
| P7 | `piece_roles(layout)` (pur, via `predict`) : caisson de référence → côtés, dessus, dessous « s'étire » ; étagère « s'étire » (largeur) ; fond « s'étire » ; une étagère répétée « se répète » avec contour « s'étire ». | U |
| P8 | Couleurs posées à l'ouverture, rétablies à la fermeture (OK comme Annuler), aucune entrée d'annulation créée par elles. | I |
| P9 | « Proposer » règle les distances « fixe » d'après la géométrie ; le résultat est annulable d'un coup. | I |
| P10 | Groupe optionnel « Socle » : les 2 combinaisons sont vérifiées à l'enregistrement ; décoché à l'usage, la plinthe et ses assemblages ne sont pas créés. Groupe qui casserait une butée : refus nommant le groupe. | U, I |
| P11 | Paramètres exposés (nombre d'étagères 1 à 6, épaisseur 15 à 22) : le panneau généré du gabarit personnel les montre, selon « essentiel / avancé » ; l'essai aux bornes échoue → « Enregistrer » grisé avec la raison. | U, G |
| P12 | Recette (`docs/recette/gabarits-scenarios-manuels.md`) : un menuisier enregistre son caisson cuisine, le rend modulaire (n étagères, socle optionnel) et le réutilise dans un autre projet. | manuel |

## 6. Découpage

| Lot | Contenu | Dépend de |
|---|---|---|
| GS-a | registre, `FieldSpec`, `TemplateEntry`, déclaration du caisson | — |
| GS-b | panneau généré, repli mémorisé | GS-a |
| GS-c | galerie, commande `Menuiserie_Template`, icône | GS-b |
| GS-d | caisson migré, ancien panneau retiré | GS-b |
| GP-a | description JSON, lecture stricte, « Enregistrer comme gabarit… » tel quel, « Mes gabarits » | GS-c |
| GP-b | éditeur de règles (suivre, répéter, optionnel, exposer, essai), couleurs par rôle | GP-a |
| GP-c | formules (plus tard) | GP-b |

Un fil et une branche de jalon `jalon/gabarits` depuis `main`, sous-branches squashées, une PR de
jalon vers `main`, fusionnée par jv seul. Règles de `CONTRIBUTING.md` : modules ≤ 400 lignes,
`core/` sans FreeCAD, libellés traduisibles.

**Plus tard** (hors de ce jalon) : meubles intégrés ([gabarits-meubles.md](gabarits-meubles.md),
Q1 à Q10) ; portée « projet » (P28 à P31) ; préférences de couleurs et dossier de l'atelier (#148) ;
IA du SaaS qui pré-remplit les règles (P17 à P22) ; cadenas sur les faces dans la vue 3D.

## 7. Compatibilité et sécurité

- Aucun nouvel objet persistant : un gabarit crée des objets ordinaires (ADR 0010) ; un document se
  lit sans l'atelier.
- Fichiers lus et écrits seulement dans le dossier des gabarits ; nom de fichier nettoyé ; lecture
  bornée ; aucun code exécuté ; la vignette PNG est vérifiée comme les textures (taille, format).
- Paramètres FreeCAD sous `Mod/Menuiserie` seulement.

## 8. Questions restantes pour jv

**R1 — Catégories de la galerie** : « Caissons et rangements, Tables et bureaux, Portes et façades,
Tiroirs, Mes gabarits » ★ / autre liste.

**R2 — Paramètres qu'on peut exposer en GP-b** : cotes, nombre et pas de répétition, épaisseur et
matériau d'un groupe de pièces ★ / ajouter les jeux d'assemblage.

**R3 — Une pièce en bois enveloppe d'un corps (ADR 0020) dans l'ensemble** : refus avec message ★ /
enregistrée comme simple pièce rectangulaire (perte de sa forme).
