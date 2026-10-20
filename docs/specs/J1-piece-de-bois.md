# [J1] Pièce de bois paramétrique et bibliothèque de matériaux

- Jalon : J1 (version cible 0.1.0)
- Statut : **validée par jv le 2026-10-19** (questions Q1 à Q3 : recommandations retenues) ;
  complétée le 2026-10-20 avant J1b (reprise de la revue finale de J1a, textures : lot J1d), puis
  pendant J1c (écarts relevés sur la PR #15 : § 4.2.3, § 4.5, critères C2 à C6 ; Q4 tranchée
  par jv le 2026-10-20 : option (a)) ; complétée le 2026-10-20 par deux exigences de jv
  (mémoire du sens du fil, fil masqué pour un matériau sans fil : critères C10 à C12, ADR 0005 ;
  questions Q5 et Q6 ouvertes)
- ADR liés : [0002 — Bibliothèque de matériaux](../adr/0002-bibliotheque-de-materiaux.md),
  [0003 — Modèle de la pièce de bois](../adr/0003-modele-de-la-piece-de-bois.md),
  [0004 — Rendu des textures des matériaux](../adr/0004-rendu-des-textures.md),
  [0005 — Mémoire du sens du fil](../adr/0005-memoire-du-sens-du-fil.md)
- Découpage : quatre PR **J1a → J1b → (J1c ∥ J1d)** (voir § 5) ; J1a fusionnée (345ff4d)

## 1. Contexte

Le menuisier dessine avec des pièces de bois réelles : une planche a une longueur, une largeur et une
épaisseur finies, une essence (ou un type de panneau), un sens du fil et un repère qui la désigne sur
le plan et dans la liste de débit. Pour débiter, il ajoute une surcote à ses cotes finies. Aujourd'hui
(J0) l'atelier se charge mais ne propose aucun outil : il faudrait passer par `Part::Box`, qui ne sait
rien de l'essence, du fil ni du débit.

La liste de débit (J2) et les assemblages (J3) s'appuieront entièrement sur cet objet : ses
propriétés, son repère local et son format de fichier deviennent un contrat qu'il faudra respecter
dans tous les documents enregistrés.

## 2. Objectif

Le menuisier peut :

1. créer une **pièce de bois** paramétrique (planche, tasseau, panneau) en choisissant ses cotes
   finies et son matériau dans une **bibliothèque d'essences et de panneaux** ;
2. la modifier à tout moment dans l'éditeur de propriétés ou dans un panneau de tâche, avec
   annulation possible ;
3. compléter la bibliothèque avec ses propres essences et panneaux, sans toucher à l'atelier.

**Livrable visible** : créer une planche de chêne 800 × 200 × 22 et la modifier
(J1b : depuis la console Python et l'éditeur de propriétés ; J1c : depuis la barre d'outils), et
la voir avec la texture de son essence, à l'échelle réelle et dans le sens du fil, quand la
bibliothèque en fournit une (J1d) — sinon avec sa couleur.

## 3. Critères d'acceptation

Légende du type de test : **U** = unitaire sans FreeCAD (`tests/unit`), **I** = intégration dans
`freecadcmd` (`tests/integration`, FreeCAD 1.0 et 1.1), **G** = interface hors écran
(`tests/gui/verifier_atelier.py`).

### J1a — Bibliothèque et calculs (`core/`, `data/`)

| N° | Critère | Test |
|---|---|---|
| A1 | `data/materiaux.json` se charge **sans aucune anomalie** et contient au moins les 12 matériaux du § 4.3.4, avec des identifiants uniques et des libellés français uniques. | U |
| A2 | Chaque règle de validation du § 4.3.2 est vérifiée : une entrée qui la viole est rejetée avec une anomalie qui cite la source, l'identifiant (s'il est lisible) et le champ fautif ; les autres entrées du fichier restent chargées. | U (un cas par règle) |
| A3 | Un fichier illisible, qui n'est pas du JSON valide, qui dépasse 1 Mio, dont la racine n'est pas un objet ou dont `format` n'est pas `1` est **ignoré en entier** avec une seule anomalie de niveau erreur ; `NaN`/`Infinity` sont refusés. | U |
| A4 | Fusion : une entrée utilisateur d'identifiant nouveau est ajoutée après les matériaux intégrés ; une entrée utilisateur d'identifiant existant **remplace entièrement** le matériau intégré (anomalie de niveau info) ; une entrée utilisateur dont le libellé français est déjà porté par un autre identifiant est rejetée. Un fichier utilisateur absent ne produit aucune anomalie. | U |
| A5 | Calculs : pour 800 × 200 × 22 mm, `volume_m3` = 0,00352 m³ et `mass_kg` à 710 kg/m³ = 2,4992 kg (à 1e-9 près) ; `rough_dimensions` avec des surcotes 20 / 5 / 0 donne 820 × 205 × 22. | U |
| A6 | `Dimensions` refuse toute cote inférieure à 0,1 mm (donc toute cote ≤ 0), non finie ou > 20 000 mm ; `Allowances` refuse toute surcote < 0, non finie ou > 20 000 mm (exception `InvalidDimensionsError`). | U |
| A7 | Règles de changement de matériau : vers un matériau sans fil → `GrainDirection.NONE` ; vers un matériau avec fil alors que le fil valait `NONE` → `LENGTH` (J1c, critère C10 : le sens mémorisé, `LENGTH` par défaut) ; sinon le fil est conservé. Les surcotes ne sont remplacées par celles de la nouvelle famille (massif / panneau) **que si** elles valent encore exactement celles de l'ancienne famille. | U |
| A8 | `is_standard_thickness` reconnaît 18 mm pour le contreplaqué bouleau (tolérance 0,05 mm) et refuse 17 mm. | U |
| A9 | `core/` n'importe ni FreeCAD ni Qt (test existant `test_separation_app_gui` toujours vert) ; couverture de `core/` ≥ 90 %. | U |
| A10 | Texture facultative : une entrée munie d'une `texture` valide expose `Material.texture` (chemin absolu de l'image, résolu dans le dossier du fichier qui la déclare, et taille en mm) ; sans `texture`, `Material.texture` vaut `None`. Chaque règle de `texture` du § 4.3.2 est vérifiée comme au critère A2 (entrée rejetée, champ `texture`, `texture.image` ou `texture.size` cité). L'existence du fichier image n'est **pas** vérifiée par `core/` (J1d, la couleur restant le secours). | U |

### J1b — Objet du document (`features/`, `api.py`, ViewProvider)

**Premiers commits de J1b, avant tout code de `features/` : reprise de la revue finale de J1a**
(`refactor(core)` de pur déplacement, puis `fix(core)` pour R1 et R2 ; aucun autre changement de
comportement ; conception au § 4.2).

| N° | Critère | Test |
|---|---|---|
| R1 | `Material(...)` construit directement valide **tous** ses champs dans `__post_init__` avec les mêmes bornes que la lecture JSON (§ 4.3.2) et lève `ValueError` en citant le champ : `id` (motif, 1 à 64 caractères), `kind` (instance de `MaterialKind`), `names` (au moins une langue, code `^[a-z]{2}$`, libellé normalisé NFC et sans espaces de bord, 1 à 80 caractères, sans caractère interdit), `density` (nombre fini non booléen, 50 à 2000), `thicknesses` (1 à 50 nombres finis non booléens entre 0,1 et 300 mm, **normalisées** : triées, dédoublonnées, en `float`), `color` (exactement 3 entiers non booléens de 0 à 255), `has_grain` (booléen), `texture` (`Texture` ou `None`). `Texture(...)` refuse un `image` non absolu, une `size` hors de 2 nombres finis entre 10 et 10 000 mm et un `folder` qui n'est pas un dossier absolu contenant strictement l'image (par défaut : le dossier de l'image). Un cas refusé et un cas limite accepté par règle. | U |
| R2 | Bornes alignées : une épaisseur standard < 0,1 mm (ex. 0,05) rejette l'entrée de bibliothèque (champ `thicknesses`, message citant « 0,1 » et « 300 ») ; 0,1 est acceptée. Pour chaque matériau de `data/materiaux.json` et chacune de ses épaisseurs standard `e`, `Dimensions(800, 200, e)` est valide. | U |
| R3 | `to_finite_float` vit dans le module privé `core/_validation.py`, avec les autres aides partagées (§ 4.2.1), et `quoted_value` dans le module public `core/text.py` ; ni `core.materials` ni `core.part_model` ne les exposent plus. Test d'imports (AST, comme `test_separation_app_gui`) sur `freecad/menuiserie/` et `tests/` : aucun module n'importe un **nom** commençant par `_` ; hors de `core/` et de `tests/unit/` (qui teste ces aides directement), aucun module n'importe `core._validation` ni un sous-module privé `core.materials._…`. | U |
| R4 | `core/materials.py` est remplacé par le paquet `core/materials/` du § 4.2.2 : `from freecad.menuiserie.core.materials import X` fonctionne pour chaque nom de `__all__` (liste figée par un test), aucun module du paquet ne dépasse 400 lignes, tous les tests J1a passent avec, pour seule modification, leurs imports (et les cas R2). | U |
| R5 | ADR 0003 au statut « accepté » (fait avec ce complément de spécification) ; § 4.2 et § 4.3.2 conformes au code livré ; CHANGELOG complété (découpage interne, validation de `Material`, épaisseur minimale 0,1 mm). | revue |

Puis l'objet du document :

| N° | Critère | Test |
|---|---|---|
| B1 | Dans `freecadcmd`, `create_wood_part(doc, length=800, width=200, thickness=22, material_id="chene")` puis `doc.recompute()` donne un objet valide : `Shape.Volume` = 3 520 000 mm³, boîte englobante de 800 (X) × 200 (Y) × 22 (Z) avec un coin à l'origine du repère local, `MaterialId` = `"chene"`, `Category` = `"Solid"`, `Density` = 710 kg/m³, `GrainDirection` = `"Length"`, `PreferredGrainDirection` = `"Length"`, `Version` = `MODEL_VERSION` (2 depuis le critère C10 ; 1 en J1b). | I |
| B2 | Chaque propriété du tableau du § 4.4.2 existe avec le type, le groupe, l'infobulle et le mode d'édition indiqués. | I |
| B3 | Modifier `Length` à 1000 mm puis recalculer donne un volume de 4 400 000 mm³ ; le `Placement` (préalablement déplacé et tourné) est **inchangé**. Idem pour `Width` et `Thickness`. | I |
| B4 | Une expression sur une cote fonctionne : `Length` = `Width * 4` donne 800 mm, puis 1000 mm après `Width` = 250. | I |
| B5 | Choisir `Material` = « Hêtre » met à jour `MaterialId`, `Category`, `Density` sans changer les cotes ; choisir « MDF » passe `GrainDirection` à `"None"` et les surcotes 20 / 5 / 0 à 0 / 0 / 0 (critère A7). | I |
| B6 | Une cote à 0 met l'objet en erreur au recalcul (`isValid()` faux, message traduit « cote invalide » dans `getStatusString()`), sans exception non rattrapée ni blocage du document ; remettre une cote valide rend l'objet valide. Une valeur négative saisie directement n'est jamais retenue (la propriété reste ≥ 0) ; une expression qui donne une cote ≤ 0 met l'objet en erreur sans exception (le moteur d'expressions de FreeCAD peut écrire une valeur négative dans la propriété : on ne lutte pas contre lui). | I |
| B7 | Enregistrer, fermer, rouvrir : toutes les propriétés sont identiques, l'objet est valide et le volume inchangé. Si la bibliothèque est inchangée, aucun objet n'est marqué « Touched » après réouverture. | I |
| B8 | Réouverture avec une bibliothèque où le matériau n'existe plus (fichier utilisateur retiré) : `MaterialId`, le libellé de `Material` et `Density` sont conservés, l'objet reste valide, un seul avertissement est écrit dans la vue rapport. | I |
| B9 | Migration : un objet enregistré sans `Version` ni `ThicknessAllowance` (propriétés supprimées avant enregistrement pour simuler un ancien fichier) est rouvert avec les propriétés manquantes recréées à leur valeur par défaut et `Version` = `MODEL_VERSION` (2 depuis C10 ; migration 1 → 2 : critère C10). | I |
| B10 | Annuler / rétablir : création encadrée par `openTransaction` / `commitTransaction`, puis `undo()` supprime la pièce et `redo()` la restaure avec ses propriétés (`UndoMode` = 1). Idem pour une modification de `Length`. | I |
| B11 | Le proxy enregistré dans le document est `freecad.menuiserie.features.wood_part.WoodPart` et `dumps()` renvoie `None` (test « contrat de persistance », cf. ADR 0003). | I |
| B12 | `record_of(obj)` renvoie un `PartRecord` cohérent avec les propriétés (prépare J2) ; `is_wood_part` vaut vrai pour une pièce et faux pour un `Part::Box`. | I |
| B13 | Dans l'interface, `api.make_wood_part(800, 200, 22, "chene")` crée une pièce avec l'icône `Menuiserie_WoodPart.svg` dans l'arbre ; la propriété de vue `MaterialColor` vaut la couleur du chêne et la couleur diffuse de `ShapeAppearance` aussi (J1b n'affiche aucune texture) ; changer de matériau change les deux. Dans `freecadcmd`, la même fonction fonctionne sans importer `FreeCADGui`. Les SVG de `resources/icons/` ne sont pas modifiés (`test_icones` vert). | G + I |
| B14 | Une anomalie de la bibliothèque utilisateur est signalée **une seule fois** par session dans la vue rapport, traduite, sans empêcher la création de pièces avec les matériaux valides. | I |

### J1c — Commande et panneau de tâche (`gui/`)

| N° | Critère | Test |
|---|---|---|
| C1 | La commande `Menuiserie_WoodPart` (« Pièce de bois ») apparaît dans la barre d'outils et le menu Menuiserie, avec icône et infobulle ; elle est inactive sans document ou si un panneau de tâche est déjà ouvert. | G |
| C2 | Lancer la commande crée une pièce (chêne, 800 × 200 × 22 par défaut) et ouvre le panneau, titré « Nouvelle pièce de bois » ; « OK » laisse **une** pièce et **une** entrée d'annulation « Créer une pièce de bois ». | G |
| C3 | « Annuler » dans le panneau de création ne laisse ni pièce ni entrée d'annulation. | G |
| C4 | Double-clic sur une pièce : le panneau s'ouvre, titré « Modifier « <Label> » », avec ses valeurs actuelles ; chaque modification est visible immédiatement dans la vue 3D ; « OK » crée **une** entrée d'annulation « Modifier une pièce de bois » ; « Annuler » rétablit toutes les valeurs d'origine. | G (+ manuel) |
| C5 | Le filtre « Type » (Tous, Massif, Contreplaqué, MDF, Mélaminé) restreint la liste des matériaux ; la liste « Matériau » affiche toujours le libellé de `obj.Material` (un filtre qui exclut le matériau courant applique le premier matériau du type : Q4 tranchée, critère C12) ; les épaisseurs standard du matériau choisi sont proposées en un clic par le menu du bouton « Épaisseurs standard » (bouton inactif si `Thickness` est pilotée par une expression ou si le matériau est inconnu localement) ; une épaisseur hors standard pour un **panneau** affiche un avertissement visible mais **non bloquant**, jamais pour du massif. Règle dans `core` : `is_nonstandard_panel_thickness` (U : contreplaqué bouleau 17 mm → vrai, 18 et 18,04 mm → faux ; chêne 17 mm → faux). | U + G (+ manuel) |
| C6 | Si une cote (dimension ou surcote) est pilotée par une expression : la propriété `expression` du champ vaut le texte de l'expression ; aucune action du panneau n'écrit la propriété ; après une modification d'une autre cote puis « OK », l'expression est toujours dans `ExpressionEngine` et la valeur la suit. Si `Mark`, `Material` ou `GrainDirection` est pilotée par une expression, le champ correspondant est inactif et le panneau ne l'écrit pas. Icône d'expression et champ en lecture seule : vérifiés **à la main** sur 1.0 et 1.1 (hors écran, le volet des tâches peut être replié : pas de vérification G conditionnelle à l'affichage). | G (+ manuel) |
| C7 | Les champs de cote acceptent les unités (`80 cm`, `2'`) et refusent une valeur ≤ 0. | manuel |
| C8 | Toute chaîne visible (commande, panneau, `.ui`, messages) passe par `translate()`, `QT_TRANSLATE_NOOP` ou les chaînes traduisibles du `.ui` ; aucun import `PySide2`/`PySide6`. | revue + test d'imports |
| C9 | Scénario du livrable, déroulé à la main sur FreeCAD 1.0 et 1.1 et décrit dans la PR : créer une planche de chêne 800 × 200 × 22, la passer à 1000 × 250 × 27 en hêtre, annuler, rétablir, enregistrer, rouvrir. Puis : fil en Largeur, MDF (ligne « Sans fil » absente), enregistrer, rouvrir, chêne : le fil est en Largeur (C10, C11). | manuel |
| C10 | **Mémoire du sens du fil** (exigence de jv, § 4.4.6, ADR 0005) : chaque pièce mémorise son dernier sens du fil (`Length` ou `Width`) dans la propriété masquée `PreferredGrainDirection` et le retrouve en revenant à un matériau avec fil, quel que soit le chemin (panneau, éditeur de propriétés, `set_material`). **U** : `grain_after_material_change(chêne, NONE, preferred=WIDTH)` → `WIDTH` ; `(chêne, NONE)` → `LENGTH` (A7 inchangé) ; `(chêne, LENGTH, preferred=WIDTH)` → `LENGTH` (le fil courant prime) ; `(mdf, WIDTH, preferred=WIDTH)` → `NONE` ; `remembered_grain(WIDTH, LENGTH)` → `WIDTH`, `(NONE, WIDTH)` → `WIDTH`, `(NONE)` → `LENGTH`, `(LENGTH, WIDTH)` → `LENGTH` ; `preferred` ou `previous` = `NONE` → `ValueError`. **I** : (1) chêne, `GrainDirection = "Width"` → préférence `Width` ; `set_material(obj, "mdf")` → `None`, préférence `Width` ; `set_material(obj, "chene")` → `Width` ; idem par `obj.Material = "MDF"` puis `"Chêne"` (éditeur de propriétés) ; chêne `Width` → MDF → contreplaqué bouleau → `Width` ; pièce créée en MDF : `None`, préférence `Length`, puis chêne → `Length`. (2) Chêne `Width` → MDF, enregistrer, fermer, rouvrir : préférence `Width`, aucun objet « Touched » (B7) ; puis chêne → `Width`. (3) Annuler / rétablir, une transaction par étape : `Width` (T1), MDF (T2), chêne (T3) → `Width` ; `undo` → `None` / préférence `Width` ; `undo` → `Width` / `Width` ; `undo` → `Length` / `Length` (la préférence suit l'annulation) ; trois `redo` → `Width` / `Width`. (4) Document ancien : `PreferredGrainDirection` supprimée et `Version` remise à 1 avant enregistrement ; une pièce en chêne `Width` est rouverte avec la préférence `Width` et `Version` = 2, puis MDF → chêne donne `Width` ; une pièce en MDF (`None`) est rouverte avec la préférence `Length` ; un document de version 0 (B9) reçoit la préférence de même. (5) Contrôles de réouverture de l'ADR 0003 appliqués à la nouvelle propriété : valeur inconnue (`"Diagonal"`) dans un document de version 2 → remplacée par le sens mémorisable de `GrainDirection` (`Length` si `None`), un avertissement ; dans un document de version 3 → gardée, un avertissement ; type inattendu (`App::PropertyString`) → supprimée puis recréée d'après `GrainDirection`, un avertissement. | U + I |
| C11 | **Fil masqué pour un matériau sans fil** (exigence de jv, § 4.4.6 et § 4.5) : si le matériau de la pièce n'a pas de fil (`has_grain` faux ; matériau inconnu localement : défaut de sa catégorie), `GrainDirection` est masquée dans l'éditeur de propriétés (`obj.getEditorMode("GrainDirection")` = `["Hidden"]`) et la ligne « Sens du fil » du panneau aussi (`grainLabel` et `grainCombo` : `isHidden()` vrai) ; avec fil, la propriété est éditable (`[]`) et la ligne affichée avec le sens mémorisé. `PreferredGrainDirection` est masquée dans tous les cas. **U** : `material_has_grain(chêne, SOLID)` vrai, `(mdf, MDF)` faux, `(None, SOLID)` et `(None, PLYWOOD)` vrais, `(None, MDF)` et `(None, MELAMINE)` faux. **I** : création en chêne puis en MDF ; chêne → MDF → chêne ; après `undo()` puis `redo()` d'un changement de matériau, le mode suit la valeur rétablie ; après réouverture d'une pièce en MDF et d'une pièce en chêne ; pièce d'un matériau inconnu localement de catégorie `MDF` → masquée. **G** : panneau ouvert sur une pièce en chêne `Width` : choisir « MDF » dans la liste masque la ligne, choisir « Chêne » la réaffiche avec « Largeur » ; panneau ouvert sur une pièce en MDF : ligne masquée dès l'ouverture. | U + I + G |
| C12 | **Filtre « Type »** (Q4 tranchée par jv le 2026-10-20 : option (a)) : choisir un type qui **exclut** le matériau de la pièce applique aussitôt le premier matériau de ce type, dans l'ordre de la bibliothèque, par le même chemin qu'un choix dans la liste (`set_material` : fil d'après C10, surcotes d'après A7) ; un type qui l'inclut, et « Tous », ne modifient pas la pièce ; un type sans aucun matériau laisse la liste vide et la pièce inchangée. **G** (bibliothèque intégrée, sauf le dernier cas) : pièce en hêtre `Width` ; filtre « MDF » → `MaterialId` = `mdf`, `GrainDirection` = `None`, surcotes 0 / 0 / 0, ligne du fil masquée (C11) ; « Contreplaqué » → `cp-bouleau`, `Width`, ligne affichée ; « Massif » → `chene` (premier massif), `Width`, surcotes 20 / 5 / 0 ; « Tous » → pièce inchangée ; « Annuler » rétablit hêtre, `Width`, préférence `Width` et surcotes d'origine ; même parcours puis « OK » → **une** entrée d'annulation. Bibliothèque temporaire sans mélaminé : filtre « Mélaminé » → liste vide, pièce inchangée. | G |

### J1d — Textures des matériaux (`core/appearance.py`, `features/appearance.py`, `gui/`)

Conception au § 4.6 et dans l'ADR 0004. **Aucun test ne dépend des textures intégrées** (PR #8,
`data/textures/`) : chaque test crée sa propre bibliothèque dans un dossier temporaire (paramètre
`UserLibraryPath`, puis `reload_library()`) avec une image produite par le test. Tant que #8 n'est
pas fusionnée, la bibliothèque intégrée n'a aucune texture et les pièces s'affichent en couleur ;
la fusion de #8 ne demande aucune modification de code.

| N° | Critère | Test |
|---|---|---|
| D1 | Projection : pour une texture de 600 × 200 mm, `texture_mapping((600, 200), GrainDirection.LENGTH)` donne `direction_s` = (1/600, 0, 0) et `direction_t` = (0, 1/200, 1/200) (en mm⁻¹, repère local) ; `WIDTH` donne (0, 1/600, 0) et (1/200, 0, 1/200) ; `NONE` donne le même résultat que `LENGTH`. La projection ne dépend ni des cotes ni du `Placement` : une planche de 1 200 mm de long fil en long montre exactement deux répétitions de l'image le long du fil. | U |
| D2 | `part_appearance(material, grain, image_usable)` : matériau sans texture → `Appearance(color=<couleur du matériau>, texture=None, mapping=None)` sans appeler `image_usable` ; texture et `image_usable(texture)` vrai → `texture` = texture du matériau (`image` = son chemin) et `mapping` = D1 ; texture et `image_usable` faux → comme sans texture. | U |
| D3 | Dans `freecadcmd` : `usable_texture_file(texture)` est vrai pour un fichier ordinaire non vide de 16 Mio au plus, resté dans le dossier de la bibliothèque (lien interne compris), et faux **sans exception** pour un chemin absent, un dossier, un fichier vide, un fichier de plus de 16 Mio (fichier creux), un lien symbolique cassé, un tube nommé, un périphérique, un lien qui sort du dossier (même créé après le chargement de la bibliothèque). `appearance_of(obj)` sur une pièce d'un matériau texturé de la bibliothèque temporaire renvoie l'image et la projection de son `GrainDirection` (`Width` après `obj.GrainDirection = "Width"`), la couleur seule si l'image est absente, et `None` si `MaterialId` est inconnu localement ; l'appel ne marque pas l'objet « Touched ». | I |
| D4 | Rendu, dans l'interface hors écran : une pièce d'un matériau texturé (image PNG 64 × 32 produite par le test) a, dans `vobj.RootNode` et avant `vobj.SwitchNode`, un `SoSwitch` nommé `MenuiserieTexture` actif, qui contient un `SoTextureCoordinatePlane` aux directions de D1 et un `SoTexture2` (modèle `MODULATE`, répétition `REPEAT` en S et T) dont l'image fait 64 × 32 pixels ; la couleur diffuse de `ShapeAppearance` est le blanc de base et `MaterialColor` la couleur du matériau. Passer `GrainDirection` à `Width` change les directions ; changer `Length` ou le `Placement` ne les change pas. Deux pièces du même matériau partagent le **même** nœud `SoTexture2` (image décodée une fois). | G |
| D5 | Repli : image absente, contenu illisible (octets aléatoires nommés `.png`), contenu d'un autre format que celui de l'extension (JPEG nommé `.png`), image de plus de 4 096 pixels de côté → `SoSwitch` inactif (`SO_SWITCH_NONE`), couleur diffuse = `MaterialColor`, aucune exception (le script se termine), et **un seul** avertissement traduit par image et par session, même avec deux pièces (vérifié avec un cache d'images muni d'une fonction d'avertissement de test). | G |
| D6 | Enregistrer, fermer, rouvrir dans l'interface avec la même bibliothèque : la texture est réaffichée (D4) et le document de l'interface n'est pas marqué modifié ; l'archive `.FCStd` ne contient aucune image de texture. Rouvrir après suppression de l'image : couleur `MaterialColor` (D5). Les propriétés de l'objet (`Version` = `MODEL_VERSION`) sont inchangées : J1d n'ajoute aucune propriété à `WoodPart`. | G |
| D7 | Vérification visuelle sur FreeCAD 1.0 et 1.1, captures dans la PR : planche texturée avec une image de test quadrillée tous les 100 mm (carreaux mesurés à 100 mm avec l'outil de mesure), veinage dans le sens de la longueur puis de la largeur selon `GrainDirection`, arêtes visibles en mode « Flat Lines », présélection et sélection toujours visibles. README : section « Ajouter une texture » (format, sens du fil = largeur de l'image, taille réelle, PNG/JPEG, 16 Mio et 4 096 pixels au plus). | manuel + revue |

## 4. Conception

### 4.1 Vue d'ensemble

```
freecad/menuiserie/
├── api.py                         J1b  façade publique pour scripts et console
├── core/
│   ├── i18n.py                    J1a  marqueur QT_TRANSLATE_NOOP pur Python
│   ├── _validation.py             J1b  aides privées partagées (nombres, NFC, bornes de cotes)
│   ├── text.py                    J1b  citation sûre d'un texte lu dans un fichier (quoted_value)
│   ├── materials/                 J1a, découpé en J1b (§ 4.2.2) : façade + modules privés
│   ├── part_model.py              J1a  Dimensions, Allowances, GrainDirection, PartRecord, calculs, règles
│   └── appearance.py              J1d  couleur / texture d'une pièce, projection de la texture
├── data/
│   └── materiaux.json             J1a  bibliothèque intégrée (format 1) ; textures : PR #8
├── features/
│   ├── freecad_types.py           #11  alias DocumentObject / Document, modes d'édition partagés
│   ├── i18n.py                    #11  translated() : gabarits traduits (App.Qt.translate)
│   ├── library.py                 J1b  accès à la bibliothèque depuis FreeCAD (chemins, cache, journal)
│   ├── wood_part.py               J1b  proxy WoodPart (Part::FeaturePython) + fonctions utilitaires
│   ├── wood_part_schema.py        #11  propriétés, énumérations, valeurs par défaut, modes d'édition
│   ├── wood_part_restore.py       #11  contrôles de la réouverture, avertissements, matériau de migration
│   └── appearance.py              J1d  apparence d'une pièce d'après la bibliothèque locale
├── gui/
│   ├── view_providers/wood_part.py J1b icône, couleur ; J1c : édition (double-clic) ; J1d : texture
│   ├── textures.py                J1d  chargement Qt des images, cache de nœuds SoTexture2 partagés
│   ├── commands/wood_part.py      J1c  commande Menuiserie_WoodPart
│   └── task_panels/
│       ├── wood_part.py           J1c  WoodPartTaskPanel
│       └── wood_part.ui           J1c  formulaire Qt Designer
├── resources/icons/Menuiserie_WoodPart.svg  existante (tools/generer_icones.py), réutilisée telle quelle
└── init_gui.py                    J1c  enregistrement de la commande dans Initialize()
```

Principes (ADR 0002 et 0003) :

- `core/` porte toute la logique (validation, fusion, calculs, règles de changement de matériau) et
  ne travaille qu'en **mm** et **kg/m³**, en flottants. Les conversions d'unités FreeCAD se font
  uniquement dans `features/`.
- `execute()` ne lit **que** `Length`, `Width`, `Thickness` : il ne consulte jamais la bibliothèque,
  ce qui garantit un recalcul identique sur toutes les machines.
- Le document conserve un **instantané** du matériau (identifiant stable, catégorie, masse
  volumique) : un fichier envoyé à quelqu'un qui n'a pas la même bibliothèque reste exact.

### 4.2 `core/` (J1a)

#### `core/i18n.py`

```python
CONTEXT: Final = "Menuiserie"


def QT_TRANSLATE_NOOP(context: str, text: str) -> str:
    """Marque une chaîne pour lupdate sans la traduire (core/ ne peut pas importer Qt)."""
```

Les messages produits par `core/` sont des **gabarits** français marqués par ce marqueur, avec
paramètres nommés (`"{source} : matériau « {id} », champ « {field} » : {reason}"`). La couche
`features/` les traduit (`translate(CONTEXT, gabarit).format(**params)`).

#### 4.2.1 `core/_validation.py` (J1b, module privé)

Aides partagées par `core/materials/` et `core/part_model.py`, déplacées telles quelles depuis
`materials.py` (seul `MIN_DIMENSION_MM`/`MAX_DIMENSION_MM` change de module) :

```python
MIN_DIMENSION_MM: Final = 0.1  # ré-exportés par part_model (__all__) : API inchangée
MAX_DIMENSION_MM: Final = 20_000.0


def to_finite_float(value: object) -> float | None: ...  # nombre fini non booléen, sinon None
def bounded_float(value: object, minimum: float, maximum: float) -> float | None: ...
def decimal_text(number: float) -> str: ...  # « 0,1 », « 300 » : bornes citées dans les messages
def nfc(text: str) -> str: ...
def has_forbidden_character(text: str) -> bool: ...  # catégories Cc, Cf, Cs, Co, Cn, Zl, Zp


class FrozenMapping(Mapping[str, str]): ...  # ex-_FrozenMapping
```

`quoted_value(value: object) -> str` (citation tronquée à 32 caractères et échappée) vit dans
le module **public** `core/text.py` : `features/` s'en sert aussi pour citer dans la vue rapport
les textes lus dans un document (`Label`, `MaterialId`, valeurs d'énumération).

Une règle de champ = **une** fonction de normalisation qui renvoie la valeur normalisée ou `None`
(ex. `normalized_density(value) -> float | None`, `normalized_thicknesses(value) ->
tuple[float, ...] | None`, `normalized_color(value) -> tuple[int, int, int] | None`), définie à
côté du modèle (`core/materials/_model.py`). La lecture JSON la transforme en `LibraryIssue`
(champ cité), le constructeur de `Material` en `ValueError` (critère R1) : les bornes ne sont
écrites qu'une fois et `pylint duplicate-code` reste vert. La lecture JSON convertit d'abord
`"#RRGGBB"` en triplet, puis applique la même règle que le constructeur.

Livré en J1b : `normalized_id`, `normalized_label`, `normalized_names`, `normalized_density`,
`normalized_thicknesses`, `normalized_color`, `normalized_texture_size` et `is_language_code`.
Le constructeur de `Material` les applique dans l'ordre des champs ; `kind` doit être une
instance de `MaterialKind`, `has_grain` un booléen, `texture` une `Texture` ou `None`. Message :
`matériau « chene », champ « density » : nombre fini entre 50 et 2000 kg/m³ attendu, reçu « 0 »`
(non traduit : erreur de programmation, jamais montrée pour un fichier de bibliothèque).

#### 4.2.2 `core/materials/` (paquet ; découpage décidé en J1b)

`materials.py` (≈ 1 100 lignes) devient un paquet dont `__init__.py` est une **façade** : il
ré-exporte l'API publique ci-dessous (`__all__` explicite, exigé par `mypy --strict`) et ne contient
aucune logique. Le chemin d'import `freecad.menuiserie.core.materials` ne change pas ; les
sous-modules sont privés (préfixe `_`) et ne sont importés que par la façade et entre eux ; les
noms qu'ils partagent n'ont pas de préfixe `_` (critère R3 : aucun module n'importe un nom privé).

| Module | Contenu | Taille visée |
|---|---|---|
| `__init__.py` | façade, `__all__` | ≈ 50 |
| `_messages.py` | tous les gabarits `QT_TRANSLATE_NOOP` des anomalies et `BUILTIN_SOURCE` | ≈ 170 |
| `_model.py` | bornes (`MAX_THICKNESS_MM`…), `MaterialKind`, `Texture`, `Material` (validation R1), `MaterialLibrary`, `UnknownMaterialError`, fonctions `normalized_*` | ≈ 300 |
| `_issues.py` | `Severity`, `LibraryIssue`, `LibraryFormatError`, création et plafonnement des anomalies | ≈ 110 |
| `_entry.py` | entrée brute en cours de validation (`Entry`), objets JSON à clés en double (`JsonObject`, `json_object`, `duplicated_field`) | ≈ 125 |
| `_parser.py` | validation d'un document JSON décodé : racine, `_parse_*`, `parse_materials` | ≈ 350 |
| `_reader.py` | lecture sûre d'un fichier (descripteur unique, `fstat`, lecture bornée), décodage JSON, `read_materials_file` | ≈ 130 |
| `_merge.py` | `merge_materials`, `load_library` | ≈ 150 |

Dépendances sans cycle : `_model` n'importe que `core._validation` ; `_issues` importe
`_messages` ; `_entry` importe `_issues` et `_messages` ; `_parser` importe `_entry`, `_model`,
`_issues`, `_messages` ; `_reader` importe `_entry` (`object_pairs_hook`) et `_parser` ; `_merge`
importe `_reader` (pour `load_library`) et les précédents. `_entry` a été ajouté au découpage
initial à la livraison de J1b : sans lui, `_parser.py` dépassait 400 lignes (critère R4).
Commit de pur déplacement d'abord (relu avec `git diff --color-moved=dimmed-zebra`), puis
commits R1 et R2. Ce découpage est interne et réversible : pas d'ADR.

API publique (inchangée hormis R1 à R3) :

```python
FORMAT_VERSION: Final = 1
MAX_FILE_BYTES: Final = 1_048_576
MAX_MATERIALS: Final = 500
MAX_ISSUES: Final = 200                # anomalies renvoyées au plus, + 1 anomalie de synthèse

class MaterialKind(str, Enum):
    SOLID = "solid"
    PLYWOOD = "plywood"
    MDF = "mdf"
    MELAMINE = "melamine"

    @property
    def is_panel(self) -> bool: ...

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

@dataclass(frozen=True)
class LibraryIssue:
    severity: Severity
    source: str                       # chemin du fichier ou "intégrée"
    template: str                     # gabarit français marqué QT_TRANSLATE_NOOP
    params: Mapping[str, str]
    material_id: str | None = None

    def format(self) -> str:          # gabarit non traduit, rempli (tests, journaux)

@dataclass(frozen=True)
class Texture:                        # ValueError si image non absolue ou size hors bornes (R1)
    image: Path                       # chemin absolu résolu (existence non vérifiée)
    size: tuple[float, float]         # mm : largeur (sens du fil), hauteur couvertes par l'image
    folder: Path | None = None        # dossier résolu de la bibliothèque, contenant l'image ;
                                      # None : dossier de l'image (J1d, confinement à l'ouverture)

@dataclass(frozen=True)
class Material:                       # immuable, hachable ; tous les champs validés (R1, ValueError)
    id: str
    kind: MaterialKind
    names: Mapping[str, str]          # code langue ISO 639-1 -> libellé ; au moins une entrée
    density: float                    # kg/m³, 50 à 2000
    thicknesses: tuple[float, ...]    # mm, 0,1 à 300 ; normalisées : triées, sans doublon
    color: tuple[int, int, int]       # RVB 0–255
    has_grain: bool
    texture: Texture | None = None

    def name(self, lang: str = "fr") -> str:
        """Libellé dans la langue demandée, sinon français, sinon la première langue disponible."""

class UnknownMaterialError(KeyError): ...
class LibraryFormatError(ValueError): ...      # usage interne, converti en LibraryIssue

class MaterialLibrary:
    """Collection immuable et ordonnée ; identifiants et libellés français uniques (ValueError sinon)."""
    def __init__(self, materials: Iterable[Material]) -> None: ...
    def __contains__(self, material_id: object) -> bool: ...
    def __iter__(self) -> Iterator[Material]: ...       # intégrés puis ajouts utilisateur, ordre des fichiers
    def __len__(self) -> int: ...
    def get(self, material_id: str) -> Material: ...    # UnknownMaterialError
    def find(self, material_id: str) -> Material | None: ...
    def find_by_name(self, name: str, lang: str = "fr") -> Material | None: ...
    def by_kind(self, *kinds: MaterialKind) -> list[Material]: ...
    def default_material(self) -> Material: ...         # premier matériau massif, sinon le premier

def parse_materials(data: object, source: str, folder: Path | None = None
                    ) -> tuple[list[Material], list[LibraryIssue]]: ...  # folder : dossier du fichier
def read_materials_file(path: Path, source: str | None = None) -> tuple[list[Material], list[LibraryIssue]]: ...
def merge_materials(builtin: Sequence[Material], user: Sequence[Material], user_source: str
                    ) -> tuple[MaterialLibrary, list[LibraryIssue]]: ...
def load_library(builtin_path: Path, user_path: Path | None
                 ) -> tuple[MaterialLibrary, list[LibraryIssue]]: ...
```

`read_materials_file` : ouverture par `os.open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC)` (drapeaux
absents sous Windows ignorés), type (fichier ordinaire) et taille vérifiés par `os.fstat` sur ce
descripteur **avant** lecture, puis lecture bornée sur le même descripteur ; décodage UTF-8 strict
(BOM initial toléré : PowerShell 5 en écrit un), `json.loads(..., parse_constant=<refus>,
object_pairs_hook=<repérage des clés en double>)` ; aucune autre forme de désérialisation. Un
fichier utilisateur absent renvoie `([], [])`. `parse_materials`, `merge_materials` et
`load_library` renvoient au plus `MAX_ISSUES` anomalies, suivies d'une anomalie de synthèse.

#### 4.2.3 `core/part_model.py`

```python
MIN_DIMENSION_MM: Final = 0.1  # J1b : défini dans core/_validation.py, ré-exporté ici
MAX_DIMENSION_MM: Final = 20_000.0  # idem
STANDARD_THICKNESS_TOLERANCE_MM: Final = 0.05


class GrainDirection(str, Enum):  # valeurs stockées dans les documents : ne jamais les renommer
    LENGTH = "Length"
    WIDTH = "Width"
    NONE = "None"


class InvalidDimensionsError(ValueError):
    template: str
    params: Mapping[str, str]


@dataclass(frozen=True)
class Dimensions:  # cotes finies en mm ; MIN_DIMENSION_MM ≤ x ≤ MAX_DIMENSION_MM, finies
    length: float
    width: float
    thickness: float


@dataclass(frozen=True)
class Allowances:  # surcotes TOTALES (pas par face) en mm ; 0 ≤ x ≤ MAX
    length: float = 0.0
    width: float = 0.0
    thickness: float = 0.0


DEFAULT_SOLID_ALLOWANCES: Final = Allowances(20.0, 5.0, 0.0)  # cf. question ouverte Q2
DEFAULT_PANEL_ALLOWANCES: Final = Allowances()


@dataclass(frozen=True)
class PartRecord:  # entrée de la future liste de débit (J2)
    mark: str
    material_id: str
    material_name: str
    kind: MaterialKind
    finished: Dimensions
    allowances: Allowances
    grain: GrainDirection
    density: float  # kg/m³

    @property
    def rough(self) -> Dimensions: ...
    def volume_m3(self, rough: bool = False) -> float: ...
    def mass_kg(self, rough: bool = False) -> float: ...


def default_allowances(kind: MaterialKind) -> Allowances: ...
def rough_dimensions(finished: Dimensions, allowances: Allowances) -> Dimensions: ...
def volume_m3(dimensions: Dimensions) -> float: ...
def mass_kg(dimensions: Dimensions, density_kg_m3: float) -> float: ...
def is_standard_thickness(
    material: Material, thickness: float, tolerance: float = STANDARD_THICKNESS_TOLERANCE_MM
) -> bool: ...
def is_nonstandard_panel_thickness(material: Material, thickness: float) -> bool: ...  # J1c
def grain_after_material_change(
    new: Material,
    current: GrainDirection,
    preferred: GrainDirection = GrainDirection.LENGTH,  # J1c (C10)
) -> GrainDirection: ...
def remembered_grain(  # J1c (C10)
    grain: GrainDirection, previous: GrainDirection = GrainDirection.LENGTH
) -> GrainDirection: ...
def material_has_grain(material: Material | None, kind: MaterialKind) -> bool: ...  # J1c (C11)
def allowances_after_material_change(
    old_kind: MaterialKind | None, new_kind: MaterialKind, current: Allowances
) -> Allowances: ...
```

Règles du sens du fil (ajoutées en J1c, critères C10 et C11 ; § 4.4.6) :

- `grain_after_material_change(new, current, preferred)` : `NONE` si `new` n'a pas de fil ;
  sinon `current` s'il n'est pas `NONE`, sinon `preferred`. `preferred` = `NONE` est une erreur
  de programmation (`ValueError`). La valeur par défaut garde le comportement de A7.
- `remembered_grain(grain, previous)` : sens à mémoriser après que le fil a pris la valeur
  `grain` : `grain` s'il désigne un sens (`LENGTH`, `WIDTH`), sinon `previous` (`ValueError` si
  `previous` vaut `NONE`). Une seule règle pour trois usages : mise à jour de la mémoire à chaque
  choix du fil, valeur initiale à la migration (`previous` = `LENGTH`), valeur de remplacement
  d'une valeur inconnue à la réouverture.
- `material_has_grain(material, kind)` : `material.has_grain` si le matériau est connu
  localement, sinon le défaut de sa famille (`kind.has_grain_by_default`). Décide de la
  visibilité du fil (éditeur de propriétés et panneau).

Pas de pattern supplémentaire : trois fonctions pures, testées sans FreeCAD ; un objet valeur
« mémoire du fil » n'aurait qu'un champ et un usage.

`is_nonstandard_panel_thickness` (ajoutée en J1c, critère C5) : vrai si et seulement si le
matériau est un panneau (`kind.is_panel`) et que l'épaisseur n'est pas standard au sens de
`is_standard_thickness` (tolérance par défaut). Le massif se rabote : jamais signalé. La règle
métier de l'avertissement du panneau de tâche vit ainsi dans `core/`, testée sans FreeCAD.

### 4.3 Bibliothèque de matériaux (J1a)

#### 4.3.1 Format JSON (format 1)

```json
{
  "format": 1,
  "materials": [
    {
      "id": "chene",
      "kind": "solid",
      "name": {"fr": "Chêne", "en": "Oak"},
      "density": 710,
      "thicknesses": [18, 22, 27, 34, 41, 54],
      "color": "#B8875A",
      "has_grain": true
    },
    {
      "id": "noyer-noir",
      "kind": "solid",
      "name": "Noyer noir",
      "density": 610,
      "thicknesses": [22, 27],
      "color": "#4A3326",
      "texture": {"image": "textures/noyer-noir.jpg", "size": [600, 200]}
    }
  ]
}
```

Clés en anglais (identifiants), valeurs affichées en français. Les unités sont implicites et
documentées : `density` en kg/m³ (bois à environ 12 % d'humidité), `thicknesses` en mm.

`texture` (facultative) associe une image au matériau : `image` est relatif au dossier du fichier
de bibliothèque qui la déclare (bibliothèque intégrée : `freecad/menuiserie/data/`, images dans
`data/textures/`, PR #8) et `size` donne la largeur et la hauteur réelles, en mm, couvertes par
l'image, le fil du bois suivant la largeur de l'image. `core/` ne vérifie pas que l'image existe :
J1d s'en charge à l'affichage (§ 4.6) et utilise `color` si l'image manque ou est illisible.

#### 4.3.2 Règles de validation

| Élément | Règle | En cas de violation |
|---|---|---|
| Fichier | fichier ordinaire, ≤ 1 Mio, UTF-8 (BOM initial toléré), JSON valide, sans `NaN`/`Infinity` | fichier ignoré, 1 erreur |
| Racine | objet contenant `format` (entier, pas booléen) et `materials` (liste), sans clé en double | fichier ignoré, 1 erreur |
| `format` | égal à 1 ; supérieur → message « fichier créé par une version plus récente de l'atelier » | fichier ignoré, 1 erreur |
| `materials` | ≤ 500 entrées, chacune un objet | entrées en trop / non-objets ignorés, 1 erreur |
| `id` | obligatoire, chaîne, `^[a-z0-9]+(-[a-z0-9]+)*$`, 1 à 64 caractères ; unique dans le fichier | entrée rejetée (doublon : la 2ᵉ), 1 erreur |
| `kind` | obligatoire, l'une de `solid`, `plywood`, `mdf`, `melamine` | entrée rejetée |
| `name` | obligatoire ; chaîne (équivaut à `{"fr": …}`) ou objet `{langue: libellé}` non vide ; langue `^[a-z]{2}$` ; libellé normalisé en NFC, de 1 à 80 caractères après suppression des espaces de bord, sans caractère des catégories Unicode Cc, Cf, Cs, Co, Cn, Zl, Zp (contrôle, invisibles et bidi, demi-substituts, usage privé, non attribués, séparateurs de ligne et de paragraphe) | entrée rejetée |
| `density` | obligatoire, nombre fini (pas booléen), 50 ≤ d ≤ 2000 | entrée rejetée |
| `thicknesses` | obligatoire, liste non vide de 1 à 50 nombres finis, 0,1 ≤ e ≤ 300 (minimum aligné en J1b sur la plus petite cote d'une pièce, `MIN_DIMENSION_MM`) ; triée et dédoublonnée au chargement | entrée rejetée |
| `color` | obligatoire, chaîne `^#[0-9A-Fa-f]{6}$` | entrée rejetée |
| `has_grain` | facultatif, booléen ; défaut : vrai pour `solid` et `plywood`, faux pour `mdf` et `melamine` | entrée rejetée si non booléen |
| `texture` | facultatif ; objet contenant `image` et `size` | entrée rejetée (champ `texture`, ou `texture.image` / `texture.size` si absent) |
| `texture.image` | chaîne de 1 à 255 caractères, chemin **relatif** au dossier du fichier, séparateur `/`, sans composant `..`, sans `\` ni `:` (pas de chemin absolu ni de lecteur Windows), sans caractère des catégories interdites pour `name` ; extension `.png`, `.jpg` ou `.jpeg` (casse indifférente) ; le chemin résolu (liens symboliques compris) reste dans le dossier du fichier | entrée rejetée |
| `texture.size` | liste de 2 nombres finis (pas booléens), 10 ≤ v ≤ 10 000 mm : largeur et hauteur couvertes par l'image | entrée rejetée |
| Clé en double | dans une entrée ou dans un objet qu'elle contient (`name`, `texture`…) | entrée rejetée, 1 erreur citant la clé |
| Clé inconnue | (racine, entrée ou `texture`, citée `texture.<clé>`) | ignorée ; 1 seul avertissement par racine ou entrée, qui cite au plus 5 clés (tronquées à 32 caractères et échappées) puis « … et N autres » |
| Anomalies | au plus 200 par appel | les suivantes sont résumées par 1 anomalie de synthèse (gravité la plus haute parmi elles) |

Fusion (fichier utilisateur sur bibliothèque intégrée) : identifiant nouveau → ajouté à la fin ;
identifiant existant → **remplacement complet** de l'entrée intégrée, à sa place (anomalie info) ;
libellé français déjà utilisé par un autre identifiant → entrée utilisateur rejetée (les libellés
servent de valeurs à la liste déroulante `Material`, ils doivent être uniques). L'unicité des
libellés (comparés en forme NFC) est vérifiée **après** application de tous les remplacements :
le résultat ne dépend pas de l'ordre des remplacements (deux matériaux intégrés peuvent échanger
leurs libellés). En cas de conflit, un matériau intégré non remplacé garde son libellé ; entre
deux entrées utilisateur, la première du fichier le garde. Une entrée rejetée rend sa place au
matériau intégré qu'elle remplaçait.

#### 4.3.3 Extension par l'utilisateur

- Fichier unique : `<dossier de données utilisateur FreeCAD>/Menuiserie/materiaux.json`, soit
  `Path(App.getUserAppDataDir()) / "Menuiserie" / "materiaux.json"`. Selon la version de FreeCAD ce
  dossier peut être versionné (`…/FreeCAD/v1-1/`) ; il suit alors l'outil de migration de FreeCAD.
- Le paramètre `User parameter:BaseApp/Preferences/Mod/Menuiserie` → `UserLibraryPath` (chaîne,
  vide par défaut) permet de pointer un autre fichier (bibliothèque partagée). Pas de page de
  préférences en J1.
- L'atelier **ne crée ni n'écrit jamais** ce fichier ; il le lit une fois par session
  (`features.library.get_library()`), `reload_library()` permet de le relire depuis la console.
  La documentation utilisateur (README, section « Ajouter une essence ») donne un exemple complet.

#### 4.3.4 Contenu initial de `data/materiaux.json`

Valeurs moyennes indicatives, **à relire par jv lors de la revue de J1a** (cf. ADR 0002 : une
correction ultérieure n'affecte pas les pièces déjà créées).

| id | kind | fr / en | densité (kg/m³) | épaisseurs standard (mm) | couleur | fil |
|---|---|---|---|---|---|---|
| `chene` | solid | Chêne / Oak | 710 | 18, 22, 27, 34, 41, 54 | `#B8875A` | oui |
| `hetre` | solid | Hêtre / Beech | 720 | 18, 22, 27, 34, 41, 54 | `#D9B48A` | oui |
| `frene` | solid | Frêne / Ash | 690 | 18, 22, 27, 34, 41, 54 | `#E3CFA5` | oui |
| `noyer` | solid | Noyer / Walnut | 650 | 18, 22, 27, 34, 41 | `#6B4A33` | oui |
| `merisier` | solid | Merisier / Cherry | 620 | 18, 22, 27, 34, 41 | `#B5654A` | oui |
| `pin-sylvestre` | solid | Pin sylvestre / Scots pine | 520 | 18, 22, 27, 34, 45 | `#E8C68E` | oui |
| `sapin-epicea` | solid | Sapin – épicéa / Fir – spruce | 450 | 18, 22, 27, 34, 45 | `#EEDDB8` | oui |
| `douglas` | solid | Douglas / Douglas fir | 530 | 22, 27, 34, 45 | `#D49A6A` | oui |
| `cp-bouleau` | plywood | Contreplaqué bouleau / Birch plywood | 680 | 4, 6.5, 9, 12, 15, 18, 21, 24 | `#E6D3B0` | oui |
| `cp-peuplier` | plywood | Contreplaqué peuplier / Poplar plywood | 450 | 5, 10, 15, 18, 22 | `#EADFC4` | oui |
| `mdf` | mdf | MDF / MDF | 750 | 3, 6, 10, 12, 16, 19, 22, 25 | `#A98B6D` | non |
| `melamine-blanc` | melamine | Mélaminé blanc / White melamine | 650 | 8, 16, 19, 22 | `#F2F2F0` | non |

### 4.4 Objet du document (J1b)

#### 4.4.1 `features/library.py`

```python
PARAM_PATH: Final = "User parameter:BaseApp/Preferences/Mod/Menuiserie"
USER_LIBRARY_PARAM: Final = "UserLibraryPath"


def builtin_library_path() -> Path: ...  # DATA_DIR / "materiaux.json"
def user_library_path() -> Path: ...  # paramètre s'il est renseigné, sinon dossier utilisateur
def get_library() -> (
    MaterialLibrary
): ...  # chargée au premier appel, anomalies journalisées une fois
def reload_library() -> MaterialLibrary: ...
def display_language() -> str: ...  # "fr" en J1 (choix de la langue : J5)
def issue_message(issue: LibraryIssue) -> str: ...  # message traduit, source « intégrée » comprise
def report_issues(issues: Iterable[LibraryIssue]) -> None: ...  # vue rapport, selon la gravité
```

Journalisation (`report_issues`) : `ERROR` → `App.Console.PrintError`, `WARNING` →
`PrintWarning`, `INFO` → `PrintLog` ; messages traduits par `issue_message`, qui traduit le
gabarit puis le remplit avec `translated` (`features/i18n.py`, issue #11) :

```python
# App.Qt.translate("Menuiserie", template).format_map(params or {}) : disponible sans interface
def translated(template: str, params: Mapping[str, str] | None = None) -> str: ...
```

Le cache de session est explicite et réinitialisable (`reload_library()`), conformément à
CONTRIBUTING (pas d'autre état global). Tests d'intégration : une fixture `bibliotheque_temporaire`
écrit un `materiaux.json` dans `tmp_path`, renseigne `UserLibraryPath`, appelle `reload_library()`
et restaure le paramètre et la bibliothèque à la fin ; aucun test ne dépend du fichier
utilisateur de la machine.

#### 4.4.2 Propriétés de l'objet `WoodPart` (`Part::FeaturePython`)

Infobulles déclarées avec `QT_TRANSLATE_NOOP("App::Property", …)` pour être traduites par
l'éditeur de propriétés. « Lecture seule » = `setEditorMode(nom, 1)`, « masquée » = mode 2 (modes
réappliqués dans `onDocumentRestored`).

| Propriété | Type | Groupe | Défaut | Édition | Infobulle |
|---|---|---|---|---|---|
| `Length` | `App::PropertyLength` | Dimensions | 800 mm | oui | Longueur finie de la pièce, mesurée selon l'axe X local. |
| `Width` | `App::PropertyLength` | Dimensions | 200 mm | oui | Largeur finie de la pièce, mesurée selon l'axe Y local. |
| `Thickness` | `App::PropertyLength` | Dimensions | 22 mm | oui | Épaisseur finie de la pièce, mesurée selon l'axe Z local. |
| `Material` | `App::PropertyEnumeration` (libellés de la bibliothèque) | Matériau | matériau par défaut | oui | Essence ou panneau, choisi dans la bibliothèque de matériaux. |
| `MaterialId` | `App::PropertyString` | Matériau | `chene` | lecture seule | Identifiant stable du matériau dans la bibliothèque. C'est lui qui est enregistré et utilisé par les calculs. |
| `Category` | `App::PropertyEnumeration` (`Solid`, `Plywood`, `MDF`, `Melamine`) | Matériau | `Solid` | lecture seule | Type de matériau, déduit du matériau choisi : massif ou panneau (contreplaqué, MDF, mélaminé). |
| `Density` | `App::PropertyDensity` | Matériau | 710 kg/m³ | lecture seule | Masse volumique recopiée de la bibliothèque au choix du matériau ; sert au calcul de la masse. |
| `GrainDirection` | `App::PropertyEnumeration` (`Length`, `Width`, `None`) | Matériau | `Length` | oui ; **masquée** si le matériau n'a pas de fil (C11) | Sens du fil par rapport aux cotes de la pièce : le long de la longueur, de la largeur, ou sans fil (MDF, mélaminé uni). |
| `PreferredGrainDirection` (C10) | `App::PropertyEnumeration` (`Length`, `Width`) | Matériau | `Length` (migration : d'après `GrainDirection`) | masquée | Dernier sens du fil choisi pour la pièce, repris quand elle revient à un matériau avec fil. |
| `Mark` | `App::PropertyString` | Débit | `""` | oui | Repère de la pièce sur les plans et dans la liste de débit (ex. « M1 »). Des pièces identiques peuvent partager le même repère. |
| `LengthAllowance` | `App::PropertyLength` | Débit | 20 mm (massif) / 0 (panneau) | oui | Surcote totale ajoutée à la longueur finie pour obtenir la longueur de débit. |
| `WidthAllowance` | `App::PropertyLength` | Débit | 5 mm (massif) / 0 (panneau) | oui | Surcote totale ajoutée à la largeur finie pour obtenir la largeur de débit. |
| `ThicknessAllowance` | `App::PropertyLength` | Débit | 0 mm | oui | Surcote totale ajoutée à l'épaisseur finie pour obtenir l'épaisseur de débit. |
| `Version` | `App::PropertyInteger` | Base | `MODEL_VERSION` (2 depuis C10 ; 1 en J1b) | masquée | Version du modèle de données de la pièce, utilisée pour migrer les anciens fichiers. |

`Placement` et `Label` sont hérités. `Label` par défaut : `translate("Menuiserie", "Pièce de bois")`.
Nom interne : `WoodPart`.

Ordre des valeurs des énumérations figé ; on ne peut qu'**ajouter** des valeurs en fin de liste
(ADR 0003). `Density` est stockée en unités internes FreeCAD (kg/mm³) : conversion par
`Quantity(f"{d} kg/m^3")` et `getValueAs("kg/m^3")`, uniquement dans `features/`. Relue,
elle est arrondie à 6 décimales (`DENSITY_DECIMALS`) : l'aller-retour par les kg/mm³ donnerait
709,9999999999999 pour 710 (issue #11).

#### 4.4.3 `features/wood_part.py`

```python
class WoodPart:
    """Proxy du FeaturePython « pièce de bois ». Chemin de module figé (ADR 0003)."""

    TYPE: ClassVar[str] = "Menuiserie::WoodPart"
    VERSION: ClassVar[int] = MODEL_VERSION  # 2 depuis C10 (wood_part_schema.py)

    def __init__(self, obj: DocumentObject) -> None: ...  # obj.Proxy = self ; ajoute les propriétés
    def onDocumentRestored(self, obj: DocumentObject) -> None: ...
    def onChanged(self, obj: DocumentObject, prop: str) -> None: ...
    def execute(self, obj: DocumentObject) -> None: ...
    def dumps(self) -> None: ...
    def loads(self, state: object) -> None: ...
    def select_material(self, obj: DocumentObject, material: Material) -> None: ...


def create_wood_part(
    doc: Document,
    *,
    length: float = 800.0,
    width: float = 200.0,
    thickness: float = 22.0,
    material_id: str | None = None,
    mark: str = "",
) -> DocumentObject: ...  # App seulement, sans transaction
def validated_arguments(
    length: float, width: float, thickness: float, material_id: str | None
) -> tuple[Dimensions, Material]: ...  # validation seule, partagée avec api.py
def is_wood_part(obj: object) -> bool: ...  # faux aussi pour un objet supprimé
def set_material(obj: DocumentObject, material_id: str) -> None: ...  # UnknownMaterialError
def dimensions_of(obj: DocumentObject) -> Dimensions: ...
def allowances_of(obj: DocumentObject) -> Allowances: ...
def record_of(obj: DocumentObject) -> PartRecord: ...  # entrée de J2
def shows_grain(obj: DocumentObject) -> bool: ...  # J1c (C11) : fil visible pour ce matériau
```

Découpage (issue #11) : `wood_part.py` garde le proxy et ces fonctions publiques, et ré-exporte
`CATEGORIES`, `GRAIN_DIRECTIONS` et `CATEGORY_BY_KIND` ; `wood_part_schema.py` décrit les
propriétés (spécifications, énumérations, valeurs par défaut, ajout des propriétés manquantes,
modes d'édition) ; `wood_part_restore.py` porte les contrôles de la réouverture, leurs
avertissements et le matériau de la migration (`stored_material`, d'après `MaterialId`).

Comportement :

- **`execute`** : construit `Dimensions` depuis les trois cotes (en cas d'`InvalidDimensionsError`,
  lève `ValueError` avec le message traduit, ce qui met l'objet en erreur), puis
  `Part.makeBox(length, width, thickness)` ; **sauvegarde et réapplique `obj.Placement`** autour de
  l'affectation de `obj.Shape` (sinon FreeCAD remet le placement de la forme). Aucune lecture de la
  bibliothèque, aucune écriture d'autre propriété.
- **`onChanged("Material")`**, hors restauration (`"Restore" in obj.State`), hors annulation ou
  rétablissement (`obj.Document.Transacting` : les autres propriétés sont restaurées par la
  transaction elle-même) et hors resynchronisation interne (drapeau de réentrance, lu avec
  `getattr(self, "_syncing", False)` car `__init__` n'est pas rappelé à la réouverture) :
  retrouve le matériau par libellé et le passe à **`select_material`**, qui met à jour la liste
  et la valeur de `Material`, puis `MaterialId`, `Category`, `Density`, `GrainDirection` et les
  surcotes selon les règles `core` (critère A7). `create_wood_part` et `set_material` passent
  aussi par `select_material`. Les cotes ne sont **jamais** modifiées automatiquement.
- **`onDocumentRestored`** : d'abord la `Version` : d'un type autre que `App::PropertyInteger`,
  elle est supprimée et traitée comme 0 (avertissement) ; supérieure à `VERSION`, elle est gardée
  avec un avertissement « document créé par une version plus récente de l'atelier » (ADR 0003).
  Puis le **type** de chaque autre propriété (issue #11) : d'un type autre que celui du tableau
  du § 4.4.2, elle est supprimée avec un avertissement (type et valeur cités par
  `quoted_value`), puis recréée par la migration, quelle que soit la `Version`.
  Puis les listes **canoniques** de `Category` et `GrainDirection`
  (celles du fichier sont des données externes) ; une valeur hors liste devient la catégorie du
  matériau de la pièce (`Solid` s'il est inconnu localement) et le fil par défaut, avec un
  avertissement où la valeur est citée tronquée et échappée ; dans un document d'une `Version`
  plus récente, elle est au contraire gardée avec la liste du fichier (avertissement), pour ne
  pas être perdue à l'enregistrement (limites : ADR 0003). Ensuite migration
  (`_migrate(obj, library, from_version, *, repair)`, où une `Version` absente vaut
  0 : ajout des propriétés manquantes avec leurs défauts, puis `Version = VERSION` ; `repair`
  recrée de même les propriétés supprimées pour leur type, sans changer la `Version`). La
  bibliothèque est lue une fois par réouverture. Les défauts
  suivent le matériau de la pièce (`MaterialId`), ou le matériau par défaut s'il est inconnu
  localement ; catégorie, fil et surcotes suivent la catégorie de la pièce si elle existe. Avec
  une bibliothèque vide, la migration aboutit quand même : catégorie `Solid` si elle manque, fil
  et surcotes de cette famille, `Material`/`MaterialId`/`Density` absentes laissées vides, et un
  avertissement traduit dans la vue rapport. Puis réapplication
  des modes d'édition, puis reconstruction de la liste `Material` depuis la bibliothèque **seulement
  si elle diffère** ; si `MaterialId` est inconnu localement, le libellé enregistré est conservé
  comme valeur supplémentaire de la liste et `Density`/`Category` ne sont pas touchés.
  Migration 1 → 2 et visibilité du fil : § 4.4.6.
- **`dumps`/`loads`** : le proxy ne porte aucun état (tout est dans les propriétés).

#### 4.4.4 `api.py` (façade pour scripts et console)

```python
def make_wood_part(
    length: float = 800.0,
    width: float = 200.0,
    thickness: float = 22.0,
    material_id: str | None = None,
    *,
    mark: str = "",
    doc: Document | None = None,
) -> DocumentObject: ...
```

Valide les cotes et le matériau (`validated_arguments`), **puis** crée la pièce dans `doc`
(document actif par défaut, nouveau document s'il n'y en a pas : une erreur n'en crée aucun), attache
le ViewProvider **si `App.GuiUp`** (import de `gui` à l'intérieur de ce test uniquement), recalcule
et renvoie l'objet. N'ouvre pas de transaction : c'est l'appelant (commande, script) qui le fait.
`api.py` n'est importé ni par `__init__.py` ni par `features/`.

Usage console (livrable J1b) :

```python
from freecad.menuiserie.api import make_wood_part

planche = make_wood_part(800, 200, 22, "chene")
planche.Length = 1000  # ou depuis l'éditeur de propriétés
```

#### 4.4.5 `gui/view_providers/wood_part.py`

```python
class ViewProviderWoodPart:
    """Chemin de module figé (ADR 0003)."""

    def __init__(self, vobj: ViewObject) -> None: ...  # vobj.Proxy = self ; ajoute MaterialColor
    def attach(
        self, vobj: ViewObject
    ) -> None: ...  # garde vobj (non sérialisé) ; J1d : nœuds de texture
    def getIcon(self) -> str: ...  # icon_path("Menuiserie_WoodPart.svg"), icône existante
    def updateData(
        self, obj: DocumentObject, prop: str
    ) -> None: ...  # "MaterialId" → MaterialColor puis apparence, hors restauration ; J1d : "GrainDirection"
    def onChanged(self, vobj: ViewObject, prop: str) -> None: ...
    def finishRestoring(
        self,
    ) -> None: ...  # recrée MaterialColor si absente ; J1d : réaffiche la texture
    def dumps(self) -> None: ...
    def loads(self, state: object) -> None: ...
    # J1c :
    def setEdit(
        self, vobj: ViewObject, mode: int
    ) -> bool | None: ...  # mode 0 : panneau ; sinon None
    def unsetEdit(self, vobj: ViewObject, mode: int) -> bool | None: ...
    def doubleClicked(self, vobj: ViewObject) -> bool: ...
```

Propriété de vue (persistée dans `GuiDocument.xml`, contrat de l'ADR 0003) :

| Propriété | Type | Groupe | Défaut | Édition | Infobulle |
|---|---|---|---|---|---|
| `MaterialColor` | `App::PropertyColor` | Matériau | couleur du matériau | masquée | Couleur du matériau, enregistrée au choix du matériau ; affichée quand aucune texture ne peut l'être. |

Couleur : au changement de `MaterialId` (hors restauration), `MaterialColor` reçoit la couleur du
matériau de la bibliothèque ; si le matériau est inconnu localement, la valeur enregistrée est
conservée (instantané, comme la masse volumique). Le ViewProvider est le **seul** à écrire la
couleur diffuse de `ShapeAppearance` (présente en 1.0 et 1.1) : en J1b elle vaut toujours
`MaterialColor` ; en J1d, le blanc de base quand une texture est affichée (§ 4.6). Les autres
champs de `ShapeAppearance` (transparence, brillance…) restent à l'utilisateur ; la valeur n'est
écrite que si elle change, pour ne pas marquer le document modifié à la réouverture.
`finishRestoring` crée `MaterialColor` si elle manque (document enregistré avant son ajout) à
partir de la couleur diffuse enregistrée.

#### 4.4.6 Mémoire et visibilité du sens du fil (J1c, critères C10 et C11)

Exigences de jv du 2026-10-20, mot pour mot : « Le sens du fils doit être garder en mémoire ainsi
que on remet ensuite un matériau avec un fils il est repris » ; « Si le matériau n'a pas de fil ,
le fil de dois pas être visible ». Le menuisier qui a tourné le fil d'une planche en Largeur ne
doit pas perdre ce choix en essayant un panneau sans fil, et ne doit pas voir de réglage de fil
sur un MDF. Choix du format : ADR 0005.

**Mémoire** (`wood_part_schema.py`, `wood_part.py`, `wood_part_restore.py`) :

- Schéma : `PreferredGrainDirection` ajoutée à `_PROPERTIES` juste après `GrainDirection` (table
  du § 4.4.2) ; `PREFERRED_GRAIN_DIRECTIONS: Final = ("Length", "Width")` (valeurs stockées,
  mêmes chaînes que `GrainDirection`, ordre figé, ajouts en fin seulement) ; `MODEL_VERSION = 2`.
  Défaut (`_default_values`) : `remembered_grain(<fil de la pièce>, LENGTH)`, le fil de la pièce
  étant `obj.GrainDirection` s'il existe et fait partie de `GRAIN_DIRECTIONS`, sinon le fil par
  défaut calculé pour `GrainDirection` (`default_grain`).
- Mise à jour : `WoodPart.onChanged("GrainDirection")`, dans les mêmes conditions que
  `"Material"` (`_follows_user_changes` : ni resynchronisation interne, ni restauration, ni
  annulation ou rétablissement) et seulement si la propriété existe : `PreferredGrainDirection`
  ← `remembered_grain(GrainDirection, préférence actuelle)`, écrite seulement si elle change.
  Tout choix de `Length` ou `Width` la met donc à jour (panneau, éditeur de propriétés, console,
  expression), y compris sur un matériau sans fil où seule la console peut l'écrire (cette
  valeur serait de toute façon conservée par la règle A7 au retour vers un matériau avec fil) ;
  choisir « Sans fil » ne l'efface pas (Q6). L'écriture a lieu dans la transaction ouverte par
  l'appelant : annuler et rétablir restaurent les deux propriétés ensemble (C10 (3)).
- Usage : `_apply_material` passe `preferred=_preferred_grain(obj)` à
  `grain_after_material_change`. `_preferred_grain(obj)` (privée, `wood_part.py`) renvoie la
  valeur de la propriété, ou `LENGTH` si elle est absente ou inconnue (document plus récent qui
  garde une valeur inconnue, ADR 0003) : jamais d'exception. Le panneau, l'éditeur de propriétés
  et `set_material` passent tous par `select_material` : aucun code de mémoire dans `gui/`.
- Réouverture : `TYPE_BY_NAME`, donc `remove_mistyped_properties`, couvre la propriété sans code
  supplémentaire ; `restore_enumerations` canonise aussi `PreferredGrainDirection`, **après**
  `GrainDirection`, avec pour valeur de remplacement `remembered_grain(GrainDirection, LENGTH)`
  et la même règle `keep_unknown` ; `_migrate` 1 → 2 = `add_missing_properties` (défaut
  ci-dessus) puis `Version = 2`, sans autre transformation : la même fonction migre depuis 0 et
  depuis 1.
- Limite : le sens choisi avant la mise à jour de l'atelier n'a été enregistré nulle part ; une
  pièce déjà en MDF dans un document de version 1 reprend `Length` (C10 (4)).

**Visibilité** :

- Mode d'édition de `GrainDirection` : `EDITABLE` si `material_has_grain(matériau, famille)`,
  sinon `HIDDEN`, avec matériau = `get_library().find(obj.MaterialId)` et famille =
  `part_kind(obj, matériau)`. `shows_grain(obj)` (publique, `wood_part.py`) porte ce calcul pour
  `features/` et le panneau ; `apply_editor_modes(obj, *, show_grain: bool = True)` applique ce
  mode à `GrainDirection` à la place de celui de la table. `PreferredGrainDirection` reste
  toujours `HIDDEN`.
- Le mode est appliqué à la création (`select_material`), à la réouverture (`onDocumentRestored`,
  après la migration, comme aujourd'hui) et dans `onChanged("MaterialId" | "Category")` **à tout
  moment sauf pendant la restauration**, y compris pendant une resynchronisation, une annulation
  ou un rétablissement : le mode d'édition n'appartient ni au document ni à la transaction, il
  doit suivre la valeur rétablie (C11). `setEditorMode` n'est appelé que si le mode change.
- Masquer ne modifie jamais la valeur : une pièce en MDF garde `GrainDirection` = `None`, et la
  liste de débit (J2) lit toujours la propriété.

Patterns : rien de nouveau. La réaction aux changements reste l'**Observer** déjà en place
(`onChanged` du proxy) ; les règles sont des fonctions pures de `core/` (§ 4.2.3).

### 4.5 Commande et panneau de tâche (J1c)

#### `gui/commands/wood_part.py`

```python
COMMAND_NAME: Final = "Menuiserie_WoodPart"


class CreateWoodPartCommand:
    def GetResources(
        self,
    ) -> dict[
        str, str
    ]: ...  # Pixmap Menuiserie_WoodPart.svg (existante), MenuText « Pièce de bois », ToolTip
    def IsActive(self) -> bool: ...  # document actif et aucun panneau de tâche ouvert
    def Activated(self) -> None: ...


def register() -> None: ...  # Gui.addCommand(COMMAND_NAME, CreateWoodPartCommand())
```

`Activated` : `doc.openTransaction(translate("Menuiserie", "Créer une pièce de bois"))`,
`api.make_wood_part(doc=doc)`, puis `Gui.Control.showDialog(WoodPartTaskPanel(obj, creating=True))`.

`init_gui.py` : dans `Initialize()`, import différé de `gui.commands.wood_part`, appel de
`register()` ; `commands = ("Menuiserie_WoodPart",)`.

#### `gui/task_panels/wood_part.py` + `wood_part.ui`

```python
class WoodPartTaskPanel:
    def __init__(
        self, obj: DocumentObject, *, creating: bool
    ) -> None: ...  # form = Gui.PySideUic.loadUi(...)
    def accept(self) -> bool: ...
    def reject(self) -> bool: ...
    def getStandardButtons(self) -> int: ...  # Ok | Cancel


def start_editing(
    obj: DocumentObject,
) -> bool: ...  # setEdit(mode 0) : transaction + panneau ; faux si un panneau est ouvert
def finish_editing() -> None: ...  # unsetEdit(mode 0) : ferme le panneau
def has_expression(obj: DocumentObject, prop: str) -> bool: ...  # prop pilotée par ExpressionEngine
```

Titre du panneau (`form.windowTitle`, traduit) : « Nouvelle pièce de bois » en création,
« Modifier « {label} » » en modification (`Label` de la pièce à l'ouverture du panneau).

Formulaire (`.ui`, chaînes traduisibles, champs de cote en `Gui::QuantitySpinBox` unité mm,
bornes posées par le panneau : dimensions de `MIN_DIMENSION_MM` à `MAX_DIMENSION_MM`, surcotes de
0 à `MAX_DIMENSION_MM`) :

| Zone | Widgets |
|---|---|
| Identification | Repère (`QLineEdit`) |
| Matériau | Type (`QComboBox` filtre : Tous, Massif, Contreplaqué, MDF, Mélaminé), Matériau (`QComboBox`, libellés), Sens du fil (`QComboBox` : Longueur, Largeur, Sans fil) |
| Dimensions finies | Longueur, Largeur, Épaisseur (`Gui::QuantitySpinBox`), bouton « Épaisseurs standard » (`QPushButton` muni d'un `QMenu`, `autoDefault` faux ; une entrée par épaisseur standard, affichée dans le système d'unités de l'utilisateur), étiquette d'avertissement « épaisseur hors standard pour ce panneau » |
| Surcotes de débit (repliable) | Longueur, Largeur, Épaisseur (`Gui::QuantitySpinBox`) |

- Les libellés d'énumération affichés sont traduits ; la valeur écrite reste la valeur stable
  (`Length`, `Width`, `None`).
- Les **six champs de cote** (dimensions et surcotes) sont liés par
  `Gui.ExpressionBinding(widget).bind(obj, prop)` (application automatique) : ils affichent une
  expression existante et permettent d'en saisir une (touche « = »), annulée avec la transaction
  par « Annuler ». Une `QComboBox` ou un `QLineEdit` ne peut pas recevoir de liaison
  d'expression : si `Mark`, `Material` ou `GrainDirection` est pilotée par une expression
  (`has_expression`), le champ correspondant est inactif et le panneau ne l'écrit jamais.
- Chaque modification d'un champ non piloté par une expression est écrite immédiatement dans
  l'objet ; une modification de cote ou de matériau est suivie de `obj.recompute()` (aperçu en
  direct). Choisir une épaisseur dans le menu passe par le champ Épaisseur (même chemin qu'une
  saisie).
- Filtre « Type » (Q4 tranchée par jv le 2026-10-20 : « Prend le 1er matériau de la liste »,
  critère C12) : restreint la liste « Matériau », qui affiche toujours le libellé de
  `obj.Material`. Si le matériau de la pièce est exclu par le filtre, le premier matériau du type
  (ordre de la bibliothèque) est appliqué aussitôt par `set_material`, comme un choix dans la
  liste : le fil suit la mémoire (C10) et les surcotes la règle A7, ce qui rend le parcours des
  filtres sans perte. Un type qui inclut le matériau de la pièce, et « Tous », ne la modifient
  pas ; un type sans matériau laisse la liste vide et la pièce inchangée. Comportement déjà livré
  dans la PR #15 (`_fill_materials`).
- Ligne « Sens du fil » (`grainLabel` et `grainCombo`, critère C11) : affichée si
  `shows_grain(obj)`, masquée (`setVisible(False)`) sinon ; recalculée dans `_show_values`, donc à
  l'ouverture et après chaque changement de matériau (liste ou filtre). Revenue visible, elle
  affiche la valeur de `GrainDirection`, c'est-à-dire le sens mémorisé (C10). La liste garde ses
  trois entrées (Longueur, Largeur, Sans fil) : Q6.
- Avertissement d'épaisseur et menu des épaisseurs : recalculés après chaque recalcul, d'après
  `get_library().find(obj.MaterialId)` et `is_nonstandard_panel_thickness` ; bouton inactif si le
  matériau est inconnu localement ou si `Thickness` est pilotée par une expression.
- Transactions : la création ouvre « Créer une pièce de bois » (commande) ; l'édition ouvre
  « Modifier une pièce de bois » dans `setEdit` (par `start_editing`). `accept` →
  `commitTransaction`, `reject` → `abortTransaction` (supprime la pièce en création, rétablit les
  valeurs en édition), puis `doc.recompute()` et `resetEdit()` du document de l'interface de la
  pièce.

### 4.6 Textures des matériaux (J1d)

Choix de rendu et alternatives écartées : ADR 0004. Principes :

- La texture **n'est pas enregistrée** dans le document : elle suit la bibliothèque locale et est
  recalculée à l'ouverture et à chaque changement de `MaterialId` ou de `GrainDirection`. Seule
  `MaterialColor` (propriété de vue, J1b) est persistée. J1d ne change pas `WoodPart` : ni
  propriété, ni `Version` (`MODEL_VERSION`, porté à 2 par J1c pour C10), ni migration.
- Répartition : `core/` calcule la projection et choisit couleur ou texture (pur, testé U) ;
  `features/` interroge la bibliothèque et contrôle le fichier image en l'ouvrant **sans le
  lire** (testé I) ; `core/texture_file.py` ouvre le fichier une seule fois, confiné au dossier de
  la bibliothèque (testé U) ; `gui/` décode en mémoire les octets lus avec Qt et construit les
  nœuds Coin (testé G).
- Patterns : **cache poids-mouche** (un nœud `SoTexture2` partagé par fichier image : une seule
  copie en mémoire graphique, quel que soit le nombre de pièces), explicite et réinitialisable
  comme l'exige CONTRIBUTING, borné en mémoire par un budget global (`core/budget_cache.py`) ; **injection de dépendances** (`image_usable`, `warn`) pour tester sans
  système de fichiers ni console. Pas de Strategy : une seule projection existe (pas de pattern
  « pour le principe ») ; une famille de projections justifierait un registre plus tard.

#### 4.6.1 `core/appearance.py`

```python
TEXTURE_BASE_COLOR: Final = (255, 255, 255)  # couleur diffuse modulée par la texture
MAX_TEXTURE_FILE_BYTES: Final = 16 * 1024 * 1024
MAX_TEXTURE_PIXELS: Final = 4096  # par côté

Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class TextureMapping:
    """Projection plane, en mm⁻¹ dans le repère local : S = direction_s · p, T = direction_t · p."""

    direction_s: Vector3
    direction_t: Vector3


@dataclass(frozen=True)
class Appearance:
    color: tuple[int, int, int]  # couleur du matériau (secours)
    texture: Texture | None = None  # None : couleur seule
    mapping: TextureMapping | None = None  # présent si et seulement si texture (ValueError sinon)

    @property
    def image(self) -> Path | None: ...  # chemin de l'image de texture, ou None


def texture_mapping(size: tuple[float, float], grain: GrainDirection) -> TextureMapping: ...
def part_appearance(
    material: Material, grain: GrainDirection, image_usable: Callable[[Texture], bool]
) -> Appearance: ...
```

Projection (critère D1) : soit `a` l'axe du fil (X pour `Length` et `None`, Y pour `Width`) et
`(w, h)` = `texture.size` ; S = coordonnée selon `a` / `w`, T = somme des deux autres coordonnées
/ `h`. Le parement (faces ±Z) et les chants parallèles au fil montrent donc le veinage dans le sens
du fil, à l'échelle réelle, l'image se répétant tous les `w` mm le long du fil. Les faces
perpendiculaires au fil (bois de bout) montrent une bande étirée : limite acceptée (§ 7).
L'origine de l'image est le coin d'origine de chaque pièce.

#### 4.6.2 `core/texture_file.py` et `features/appearance.py`

```python
# core/texture_file.py (Python pur)
FileKey = tuple[int, int, int, int]  # st_dev, st_ino, st_size, st_mtime_ns


class TextureRefusedError(Exception):  # reason : gabarit traduisible ; params : valeurs
    reason: str
    params: dict[str, str]


def confined_image(texture: Texture) -> Path: ...  # image résolue, dans texture.folder


class TextureFile:  # gestionnaire de contexte ; TextureRefusedError dès la construction
    key: FileKey

    def __init__(self, texture: Texture) -> None: ...
    def read(self) -> bytes: ...  # au plus MAX_TEXTURE_FILE_BYTES + 1 octets lus, une fois
    def close(self) -> None: ...


# features/appearance.py
def usable_texture_file(texture: Texture) -> bool: ...  # TextureFile sans lecture


def appearance_of(
    obj: DocumentObject, image_usable: Callable[[Texture], bool] = usable_texture_file
) -> Appearance | None:
    ...
    # get_library().find(obj.MaterialId) ; None si inconnu ; sinon part_appearance(..., image_usable)
```

Ouverture (audit de sécurité, TOCTOU) : `texture.image` est résolu (`resolve(strict=True)`) à
**chaque** ouverture et doit rester strictement dans `texture.folder` (dossier résolu de la
bibliothèque au chargement), sinon refus « fichier sorti du dossier de la bibliothèque » ; la
cible est ouverte par `os.open(…, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC | O_NOCTTY)`
(drapeaux absents sous Windows : 0, plus `O_BINARY`), contrôlée par `fstat` (fichier ordinaire,
0 < taille ≤ 16 Mio) puis lue au plus une fois. Aucun accès ultérieur par le nom : `gui/` décode
ces octets en mémoire. Un lien interne au dossier est accepté, un dossier de bibliothèque qui
est lui-même un lien l'est aussi (résolu au chargement) ; `O_NOFOLLOW` fait échouer l'ouverture
si le dernier composant devient un lien entre la résolution et l'ouverture.

`image_usable` est injecté : `freecadcmd` utilise `usable_texture_file` (ouverture sans lecture),
l'interface `texture_cache().usable` (ouverture, lecture et décodage).

#### 4.6.3 `gui/textures.py`

```python
TextureNode = Decoded[SoTexture2]  # nœud partagé et octets de son image (core/budget_cache.py)


class TextureCache:
    def __init__(
        self,
        warn: Callable[[str], None] | None = None,
        max_entries: int = 32,
        max_bytes: int = DEFAULT_MAX_BYTES,  # 256 Mio
    ) -> None: ...  # warn par défaut : App.Console.PrintWarning
    def node(
        self, texture: Texture
    ) -> TextureNode | None: ...  # nœud partagé ; None si l'image est refusée
    def usable(self, texture: Texture) -> bool: ...  # node(texture) is not None
    def clear(self) -> None: ...


def texture_cache() -> TextureCache: ...  # cache de la session
def reset_texture_cache(
    warn: Callable[[str], None] | None = None,
    *,
    max_entries: int = 32,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TextureCache: ...  # tests


class TextureSwitch:  # nœuds propres à une pièce (§ 4.6.4)
    root: SoSwitch  # nommé « MenuiserieTexture »
    active: bool  # propriété

    def insert_before(self, parent: SoNode, sibling: SoNode) -> None: ...
    def show(self, mapping: TextureMapping, texture: TextureNode) -> None: ...  # garde le nœud
    def hide(self) -> None: ...  # switch inactif et nœud de texture retiré (libérable)
```

`node(texture)` : clé = identité du fichier ouvert, lue par `fstat` (`st_dev`, `st_ino`, taille,
date de modification) : deux liens physiques partagent un nœud, une image remplacée est relue ;
un fichier qui ne peut pas être ouvert est identifié par son chemin. Succès **et** refus sont
mémorisés (au plus `max_entries`, les plus anciens évincés), d'où un seul avertissement par
image et par session (D5).

Budget mémoire (audit de sécurité) : chaque `TextureSwitch` garde le nœud qu'il affiche, donc la
limite d'entrées ne borne pas la mémoire (≈ 48 Mio de pixels par image de 4 096 × 4 096). Le
cache compte les octets RVB de **toutes** les images décodées encore vivantes, retenues par lui
ou par une pièce affichée (références faibles sur les `Decoded`), et réserve
largeur × hauteur × 3 octets, lus dans l'en-tête, avant de décoder : il oublie au besoin ses
plus anciennes images, puis, si l'image ne tient toujours pas dans `max_bytes`, la refuse sans
mémoriser ce refus (elle s'affichera quand de la place se libère) ; couleur du matériau et un
seul avertissement par cache : « Textures non affichées au-delà de {max} Mio d'images décodées
(première : « {image} ») : couleur du matériau utilisée à la place. Cet avertissement n'est pas
répété. ». `hide()` retire le nœud de la pièce, qui libère sa place. Une image oubliée par le
cache mais encore affichée est retrouvée par sa clé (pas de seconde copie). Chargement :

1. `TextureFile(texture)` (§ 4.6.2) puis `read()` : les octets sont lus une fois ;
   `QImageReader(QBuffer(QByteArray(octets)), b"png" | b"jpeg")` selon l'extension et
   `setAutoDetectImageFormat(False)` : seuls les décodeurs PNG et JPEG de Qt sont sollicités, et
   jamais sur le fichier par son nom ;
2. `reader.size()` lu dans l'en-tête **avant** décodage : invalide ou côté > `MAX_TEXTURE_PIXELS` →
   refus ; réservation de largeur × hauteur × 3 octets dans le budget mémoire ;
3. contrôle des octets selon le format, avant décodage (`core/image_checks.py`,
   `check_image_bytes(data, "png" | "jpeg")`, Python pur, testé U) : JPEG de plus de
   `MAX_JPEG_SCANS` = 100 marqueurs de début de balayage (`FF DA`, comptés sur les octets : un
   `FF` des données compressées est toujours suivi de `00`) → refus « JPEG en {count}
   balayages, {max} au plus » (un JPEG progressif aux milliers de balayages vides figerait
   l'interface plusieurs minutes) ; PNG : blocs parcourus (signature, `IHDR` en premier, blocs
   non tronqués, sinon refus « blocs ou données PNG invalides »), blocs `IDAT` décompressés par
   `zlib.decompressobj` par morceaux d'au plus 1 Mio aussitôt oubliés, avec `max_length` borné à
   la taille brute **exacte** annoncée par `IHDR` (pour chaque passe, une seule ou les sept
   d'Adam7 : lignes × (1 octet de filtre + ⌈colonnes × bits par pixel / 8⌉)) plus un octet ;
   au-delà → refus « données PNG décompressées au-delà des {size} octets de l'image annoncée »
   (bombe de décompression : 2 Gio de zéros tiennent en 2 Mio) ; moins de données qu'annoncé est
   laissé au décodeur ;
4. `reader.read()` ; image nulle → refus (raison : `reader.errorString()`, tronquée) ;
5. conversion en `Format_RGB888` (opaque : pas de tri de transparence), retournement vertical
   (origine de Coin en bas à gauche), copie ligne par ligne sans le bourrage de `bytesPerLine` ;
6. `SoTexture2` : `image.setValue(SbVec2s(w, h), 3, pixels)`, `model = MODULATE`,
   `wrapS = wrapT = REPEAT`.

Refus : avertissement traduit, une fois : « Texture « {image} » non affichée ({reason}) : couleur du
matériau utilisée à la place. ». `{image}` est le chemin **entier**, caractères non imprimables
échappés par `core.text.escaped_text` (`repr` sans ses guillemets : `\n`, `\u202e`…), sans
troncature : le dossier de la bibliothèque est choisi librement et doit rester reconnaissable.
Motifs (`{reason}`) : fichier absent, vide, illisible ou de plus de 16 Mio ; fichier sorti du
dossier de la bibliothèque ; extension non prise en charge ; en-tête illisible ; dimensions
trop grandes ; JPEG de trop de balayages ; blocs ou données PNG invalides ; données PNG
décompressées au-delà de l'image annoncée ; image illisible (erreur de Qt, tronquée).

#### 4.6.4 ViewProvider (ajouts J1d)

- `attach` crée un `SoSwitch` nommé `MenuiserieTexture` (inactif), contenant un `SoGroup` avec un
  `SoTextureCoordinatePlane` propre à la pièce puis le `SoTexture2` partagé, et l'insère dans
  `vobj.RootNode` juste avant `vobj.SwitchNode` : la texture s'applique à tous les modes
  d'affichage ; les arêtes, de couleur sombre, restent lisibles (`MODULATE`).
- `_refresh(obj)`, appelée par `updateData("MaterialId" | "GrainDirection")` hors restauration et
  par `finishRestoring` : `appearance_of(obj)`, puis `texture_cache().node(image)` ; si les deux
  aboutissent → directions de la projection, nœud de texture, switch actif, couleur diffuse =
  `TEXTURE_BASE_COLOR` ; sinon → switch inactif, couleur diffuse = `MaterialColor`. Chaque valeur
  n'est écrite que si elle change. Aucune exception attendue ne sort de `_refresh` (les échecs
  sont des valeurs `None`) ; pas de `except Exception` global.
- Un changement de cote ou de `Placement` ne déclenche rien : la projection est en coordonnées
  locales et ne dépend pas des cotes.

Tests G : `tests/gui/verifier_atelier.py` devient une liste de vérifications (fonctions qui
renvoient chacune leurs problèmes, agrégés dans le rapport) ; J1d y ajoute D4 à D6, avec des
images PNG produites par `QImage` dans un dossier temporaire et `reset_texture_cache(warn=...)`
pour compter les avertissements. Pas de comparaison de pixels (rendu hors écran non garanti en
CI) : on vérifie le graphe de scène ; l'aspect visuel relève de D7.

Contrat pour la PR #8 (textures intégrées) : PNG ou JPEG de 16 Mio et 4 096 pixels de côté au
plus, fil le long de la largeur de l'image, `size` = dimensions réelles photographiées, sources et
tailles dans `data/textures/SOURCES.md` ; le critère A1 (bibliothèque intégrée sans anomalie)
s'applique. Un test unitaire de #8 vérifie que chaque image intégrée existe et respecte ces limites.

### 4.7 Sécurité

Lecture des fichiers de matériaux en JSON uniquement, par un seul descripteur (`os.open` non
bloquant, `fstat`, lecture bornée), taille bornée avant lecture, clés en double refusées, toutes
les valeurs typées et bornées (§ 4.3.2), valeurs citées dans les anomalies tronquées et échappées,
nombre d'anomalies plafonné ; chemins de texture relatifs, confinés au dossier du fichier de
bibliothèque après résolution des liens, jamais ouverts par `core/` ; aucune écriture de fichier ; aucun chemin construit à partir
du contenu d'un document ; `api.py` est le seul module hors `gui/` autorisé à importer `gui/`, et
seulement sous `if App.GuiUp`.

Images de texture (J1d) : chemin issu **uniquement** de la bibliothèque (le document ne fournit que
l'identifiant `MaterialId`, clé de recherche et jamais chemin) ; fichier ouvert **une seule fois**
(§ 4.6.2 : confinement au dossier de la bibliothèque revérifié à l'ouverture, `O_NOFOLLOW`,
`O_NONBLOCK`, contrôle par `fstat`, lecture bornée à 16 Mio) ; décodage seulement dans `gui/`,
en mémoire, par les décodeurs PNG ou JPEG de Qt imposés par l'extension, dimensions lues dans
l'en-tête et bornées à 4 096 pixels avant décodage, JPEG de plus de 100 balayages et PNG dont
les données décompressées dépassent la taille brute annoncée refusés avant décodage ; mémoire
des images décodées bornée à 256 Mio ; raison d'échec citée tronquée, chemin cité entier et
échappé ; l'image n'est jamais copiée dans le document.

## 5. Découpage en PR

| Lot | Branche | Contenu | Diff estimé hors tests | Critères |
|---|---|---|---|---|
| **J1a** (fusionnée, 345ff4d) | `feat/bibliotheque-materiaux` | `core/i18n.py`, `core/materials.py`, `core/part_model.py`, `data/materiaux.json`, ADR 0002 accepté | ≈ 320 lignes + 130 lignes de données | A1–A10 |
| **J1b** | `feat/piece-de-bois-document` | 1ᵉʳ commit (ou série) : reprise de la revue J1a (`core/_validation.py`, paquet `core/materials/`, validation de `Material`, épaisseur minimale, ADR 0003 accepté) ; puis `features/library.py`, `features/wood_part.py`, `api.py`, ViewProvider (icône existante, `MaterialColor`, couleur), README « Ajouter une essence » | ≈ 350 lignes + ≈ 80 lignes nettes pour la reprise (déplacements exclus, relus avec `--color-moved`) | R1–R5, B1–B14 |
| **J1c** (PR #15) | `feat/commande-piece-de-bois` | commande, panneau de tâche + `.ui`, édition au double-clic, `init_gui.py`, test G ; puis mémoire et visibilité du fil (`core/part_model.py`, `features/wood_part*.py`, ligne du fil du panneau, `MODEL_VERSION` = 2, ADR 0005) | ≈ 300 lignes + `.ui`, puis ≈ 100 lignes pour C10–C12 | C1–C12 |
| **J1d** | `feat/textures-piece-de-bois` | `core/appearance.py`, `features/appearance.py`, `gui/textures.py`, ajouts au ViewProvider, vérifications G, README « Ajouter une texture », ADR 0004 accepté | ≈ 220 lignes | D1–D7 |

J1c et J1d partent tous deux de `main` après la fusion de J1b et sont indépendants (seul point de
contact : le ViewProvider, où J1c ajoute l'édition et J1d la texture ; le second fusionné rebase).
J1d ne dépend pas de la PR #8 et réciproquement. Les textures font un lot séparé parce que J1b
avec la reprise de J1a et les textures dépasserait nettement les ≈ 400 lignes relisibles en une PR.

Chaque lot est livrable seul : J1a est invisible mais entièrement testé, J1b atteint déjà le
livrable du jalon par la console et l'éditeur de propriétés, J1c apporte l'outil graphique, J1d le
rendu réaliste.

## 6. Compatibilité

- **Fichiers `.FCStd` existants** : aucun objet de l'atelier n'existe encore ; aucune migration
  n'est nécessaire. J1b introduit le **premier format persistant** (`Version` = 1).
- **Mémoire du sens du fil (J1c, C10, ADR 0005)** : `Version` passe à 2 et
  `PreferredGrainDirection` est ajoutée. Un document de version 1 (enregistré avec `main` après
  J1b) est migré à la réouverture : la propriété est créée d'après `GrainDirection` (`Length` si
  `None`) et `Version` = 2 ; le document est alors à enregistrer de nouveau. Un document de
  version 2 ouvert avec un atelier antérieur (J1b) : avertissement « document créé par une
  version plus récente » (ADR 0003), la propriété inconnue de cet atelier est conservée telle
  quelle et réenregistrée, mais n'est ni lue ni mise à jour par lui. La visibilité du fil (C11)
  n'est pas enregistrée : elle est recalculée à chaque ouverture.
- **Contrat de persistance** (ADR 0003), vérifié par test : chemins
  `freecad.menuiserie.features.wood_part.WoodPart` et
  `freecad.menuiserie.gui.view_providers.wood_part.ViewProviderWoodPart`, noms des propriétés,
  valeurs des énumérations (ajout en fin seulement), unités. Toute évolution passe par
  `Version` + `_migrate` dans `onDocumentRestored`, avec un test de réouverture d'un fichier ancien.
  La propriété de vue `MaterialColor` en fait partie ; une propriété de vue absente à la
  réouverture est recréée dans `finishRestoring` (le ViewProvider n'a pas de `Version`).
- **Textures (J1d)** : aucune propriété ajoutée à `WoodPart`, `Version` inchangée par J1d, aucune migration.
  Rien de la texture n'est écrit dans le `.FCStd` : un plan ouvert sur une machine qui a la même
  bibliothèque affiche la texture, sinon la couleur `MaterialColor` enregistrée. Les documents
  enregistrés avec J1b s'ouvrent sans changement avec J1d. Si FreeCAD active un jour ses propres
  textures (`ShapeAppearance`, code désactivé en 1.0), la bascule ne touchera que le ViewProvider
  (ADR 0004).
- **Reprise de J1a** : `from freecad.menuiserie.core.materials import …` reste valable pour toute
  l'API publique ; seules disparaissent de ce module les aides `quoted_value` et `to_finite_float`
  (aucun utilisateur hors de l'atelier : J1a n'a pas été publiée). Une bibliothèque utilisateur
  déclarant une épaisseur standard < 0,1 mm voit désormais l'entrée rejetée avec une anomalie
  (aucune version publiée ne l'acceptait).
- **Fichiers de bibliothèque** : `format` = 1 ; une version future qui change le format devra
  continuer à lire le format 1.
- **FreeCAD 1.0 et 1.1** : `App::PropertyDensity`, `ShapeAppearance`, `obj.State`,
  `vobj.RootNode`/`vobj.SwitchNode`, `finishRestoring` côté ViewProvider Python et les nœuds Coin
  `SoTexture2`/`SoTextureCoordinatePlane` (pivy) existent dans les deux ; le dossier utilisateur peut être versionné selon la version (le fichier utilisateur
  suit la migration de FreeCAD, ou le paramètre `UserLibraryPath`).
- **Limite connue** : une pièce créée dans `freecadcmd` puis ouverte dans l'interface n'a pas de
  ViewProvider Python (icône et couleur génériques). Suivi par une issue dédiée (réparation à
  l'ouverture via un observateur de document côté interface).

## 7. Hors périmètre

- Liste de débit, regroupement, Spreadsheet, export CSV (J2) — seuls `PartRecord` et les calculs
  de volume / masse sont fournis.
- Commande « Mettre à jour depuis la bibliothèque » pour rafraîchir l'instantané d'un matériau.
- Page de préférences, éditeur graphique de la bibliothèque, plusieurs fichiers utilisateur.
- Choix de la langue des libellés de matériaux (toujours `fr` en J1) et fichiers `.ts`/`.qm` (J5) ;
  les chaînes sont seulement marquées.
- Intégration au système de matériaux natif de FreeCAD (`.FCMat`, `ShapeMaterial`).
- Sections non rectangulaires, chanfreins, profils ; orientation prédéfinie (debout, de chant) :
  on utilise `Placement`.
- Numérotation automatique des repères, quantités et Links (J2/J4), prix, humidité, choix de
  l'épaisseur brute de débit.
- Assemblages (J3).
- Textures (J1d) : rendu du bois de bout, orientation ou décalage propres à chaque pièce (toutes
  les pièces d'un matériau commencent l'image à leur coin d'origine), rotation ou échelle réglables
  par pièce, préférence pour désactiver les textures, rafraîchissement des pièces ouvertes après
  `reload_library()` (pris en compte au prochain changement de matériau ou à la réouverture),
  textures dans TechDraw et les exports, couleur choisie à la main sur une pièce (la couleur
  diffuse appartient au ViewProvider), textures natives de FreeCAD. Les textures intégrées
  elles-mêmes arrivent par la PR #8. Une pièce texturée garde le blanc de base dans
  `ShapeAppearance`, donc paraît blanche sans l'atelier ou dans un export : obtenir ce blanc dans
  les nœuds Coin de l'atelier n'est pas faisable proprement en 1.0 et 1.1 (ADR 0004, § Limites).
- Sens du fil (C10, C11) : mémoire commune à toutes les pièces ou sens par défaut des nouvelles
  pièces (la mémoire est propre à chaque pièce : Q5), mémoire par matériau, mémoire d'autres
  réglages que le fil (les surcotes suivent déjà la règle A7), interdiction de « Sans fil » sur
  un matériau avec fil (Q6).

## 8. Questions ouvertes pour jv

**Q1 — Masse volumique figée dans la pièce ou lue en direct dans la bibliothèque ?**
Si vous corrigez la densité du chêne dans votre fichier, faut-il que les pièces existantes changent
de masse ?
*Recommandation : figée (instantané au choix du matériau).* Un plan donne la même liste de débit sur
toutes les machines et dans le temps ; une commande explicite « Mettre à jour depuis la
bibliothèque » viendra plus tard. (ADR 0002)

**Q2 — Surcotes de débit par défaut.**
Proposition : surcotes **totales** (et non par face), massif : longueur + 20 mm, largeur + 5 mm,
épaisseur + 0 mm (l'épaisseur brute se choisit en débit) ; panneaux : 0 / 0 / 0.
*Recommandation : ces valeurs, modifiables par pièce ; une préférence globale viendra avec la page
de préférences.* Quelles valeurs utilisez-vous à l'atelier ?

**Q3 — Le type (massif / contreplaqué / MDF / mélaminé) est déduit du matériau.**
Le plan listait « essence » et « type » comme deux propriétés. Les rendre indépendantes permettrait
des combinaisons absurdes (« chêne » + « MDF »). Je propose que le type soit une caractéristique du
matériau de la bibliothèque, affiché en lecture seule sur la pièce et utilisé comme filtre dans le
panneau ; un contreplaqué plaqué chêne serait un matériau à part entière (`cp-chene`).
*Recommandation : type déduit du matériau.* (ADR 0002)

**Q4 — Filtre « Type » qui exclut le matériau de la pièce (ouverte le 2026-10-20, PR #15) —
tranchée par jv le 2026-10-20 : option (a), « Prend le 1er matériau de la liste ».**
La pièce est en chêne et vous choisissez le filtre « Contreplaqué » dans le panneau. Deux
comportements possibles :
(a) le premier contreplaqué de la liste (contreplaqué bouleau) est appliqué aussitôt : aperçu
immédiat ; parcourir les filtres change la pièce ;
(b) le filtre ne change rien à la pièce : le chêne reste affiché en tête de liste jusqu'à ce que
vous choisissiez un contreplaqué (un clic de plus).
**Décision : (a)**, déjà livrée dans la PR #15 (critère C12). La perte du sens du fil au passage
par un matériau sans fil, qui motivait la recommandation (b), disparaît avec la mémoire du fil
(C10) ; les surcotes non modifiées reprennent les valeurs de leur famille (A7) et celles que
vous avez saisies sont conservées. « Annuler » rétablit tout.

**Q5 — Mémoire du fil : par pièce ou pour tout l'atelier ? (ouverte le 2026-10-20, C10)**
« Le sens du fil doit être gardé en mémoire » peut s'entendre de deux façons :
(a) chaque pièce se souvient de **son** dernier sens du fil (spécifié en C10) ;
(b) en plus, une nouvelle pièce part du dernier sens choisi dans la session (ou d'un réglage).
*Recommandation : (a) seule.* Une nouvelle planche en Longueur est le cas courant ; (b) ferait
dépendre le résultat d'une commande de l'historique de la session, ce qui surprend et complique
les scripts. (b) pourra venir avec la page de préférences (sens par défaut des nouvelles pièces).

**Q6 — Garder le choix « Sans fil » pour un matériau avec fil ? (ouverte le 2026-10-20, C11)**
Avec C11, la ligne « Sens du fil » n'apparaît que pour un matériau avec fil ; elle propose
toujours Longueur, Largeur et Sans fil. « Sans fil » sur du chêne n'a guère de sens, mais sert
peut-être pour une pièce dont le fil est indifférent (tasseau caché, fond de tiroir en
contreplaqué) : la liste de débit (J2) ne la contraindra pas.
*Recommandation : garder les trois choix (comportement actuel, rien à changer).* Choisir « Sans
fil » n'efface pas la mémoire : un changement de matériau avec fil reprend le dernier sens
choisi. Si vous préférez retirer « Sans fil » pour les matériaux avec fil, c'est un petit
changement du panneau et de la règle A7.
