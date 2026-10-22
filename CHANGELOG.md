# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions
[SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté
- Accrochage à la sélection (J6d, ADR 0011) : les faces, arêtes et sommets sélectionnés avant
  **Pièce de bois** (pièces de bois, Std Part, `App::Link`, objets d'autres ateliers) reçoivent la
  nouvelle pièce, en aperçu et en direct ; le panneau cite « Contre : … » et signale les éléments
  ignorés ou non touchés. Deux faces en vis-à-vis étirent la longueur (orientation de départ
  choisie par `initial_orientation` pour une tablette entre deux joues), la saisie du menuisier
  l'emporte ensuite. La pièce est créée dans le Std Part du premier élément (`placement` exprimé
  dans son repère), et une case **Ajouter à l'ensemble** (cochée) l'ajoute à l'ensemble de
  l'élément touché dans la même transaction. Les boutons X, Y, Z tournent autour des axes du
  document (axes du repère d'appui contre une face inclinée). Le sens du fil s'affiche en direct.
  `features/picked.py`, `snap_geometry.py`, `snap_targets.py`, `gui/selection.py`. Aucun objet
  sélectionné n'est modifié, aucun observateur installé.
- Aperçu et rotation de la pièce (J6c, ADR 0011) : en création, la pièce est affichée à 60 % de
  transparence tant que le panneau est ouvert (`PreviewStyle`, rétablie à « OK », rien n'est
  enregistré) ; trois boutons **X**, **Y**, **Z** (groupe « Position », icônes
  `Menuiserie_RotateX/Y/Z` générées) font tourner la pièce d'un quart de tour autour de l'axe du
  document : elle reste accrochée en création, tourne sur place (centre fixe) en modification,
  et le fil tourne avec elle ; boutons inactifs si une expression pilote sa position (membre
  d'un ensemble). `features/placement.py` (`to_placement`, `local_placement`,
  `add_to_container`, `SnapSession`, `snap_part`, `rotate_part`). Les cotes restent modifiables
  et la saisie l'emporte sur l'étirement de l'accrochage. Recette : `docs/recette/J6-scenarios-manuels.md`.
- Supprimer un assemblage ne montre plus l'avertissement « Les objets référencés suivants
  pourraient s'endommager » pour ses pièces usinées (`canDelete` de leur ViewProvider), qui sont
  recalculées sans la coupe.
- Nom d'un assemblage « {type} : {pièce hôte} {pièce invitée} » (par ex. « Tenon-mortaise : M1 T1 »),
  mis à jour quand une des deux pièces change de repère ou de nom ; doublons « (2) »
  (`features/joint_names.py`).
- Nom de la pièce = repère (J6b, ADR 0011) : `core/naming.py` (`label_for_mark`,
  `mark_from_label`, suffixe « M1 (2) » pour les doublons) ; le libellé suit le repère (panneau,
  éditeur de propriétés, script, expression) et inversement (renommage dans l'arborescence, de la
  brute ou de l'usinée) par `onBeforeChangeLabel` et `allowDuplicateLabel` de `WoodPart` et
  `MachinedPart` ; la pièce usinée s'appelle « {repère} (usinée) » ; une nouvelle pièce prend le
  libellé de son repère. Aucune synchronisation à la réouverture, en annulant ni en rétablissant :
  les documents existants ne sont renommés qu'à la première modification. Repère piloté par une
  expression : avertissement, le libellé revient à celui du repère. Aucune préférence de FreeCAD
  modifiée. Infobulle de `Mark` complétée.
- Géométrie de l'accrochage (J6a, ADR 0011), sans FreeCAD : `core/snap/` (`Frame`, `FaceTarget`,
  `EdgeTarget`, `VertexTarget`, `Orientation`, `Turn`, `snap`, `turned_in_place`,
  `tangent_frame`). Une pièce se pose contre une face, une arête ou un sommet (coin sur le coin,
  à plat sur la face d'appui) ; deux ou trois éléments la font toucher chacun, et deux faces en
  vis-à-vis étirent la longueur ou la largeur (jamais l'épaisseur) ; les boutons X, Y, Z
  (24 orientations) la gardent accrochée ; refus doux par avis (`ThicknessGap`, `GapOutOfRange`,
  `NotSquare`, `TooMany`, `Conflict`).
- Refus d'une commande (ajout à un ensemble, assemblage…) affiché aussi dans une boîte
  d'avertissement non modale, en plus de la barre d'état et de la vue rapport (recette J4, 2.4).
- Interface de l'ensemble (J4c) : commandes **Ensemble**, **Ajouter à l'ensemble**,
  **Retirer de l'ensemble** et **Relier les pièces** (une entrée d'annulation chacune, icônes
  générées) ; `ViewProviderFurniture` (membres, sous-ensembles et assemblages internes rangés
  sous l'ensemble, liaisons et propriétés de membre retirées à la suppression) ; panneau de
  tâche (cotes, membres avec leur position et ce qu'ils font quand une cote change, six
  distances aux bords et cases « fixe » du membre choisi, « Relier les pièces », refus et
  avertissements) ; `set_edge_distance` dans l'api ; scène des captures avec un ensemble.
- Gabarit « Caisson » (J4d, ADR 0010) : `core/templates/` (`PieceSpec`, `JointSpec`, `Layout`,
  `CarcassParams`, `carcass_layout`), constructeur unique `features/templates.py`,
  `make_carcass` (côtés, dessus, dessous, fond en feuillure, étagères, tourillons et un ensemble
  « Caisson » dont les options « fixe » sont données par le gabarit), commande **Caisson** avec
  panneau de paramètres et aperçu, une seule entrée d'annulation.
- Règles de suivi des ensembles (`core/furniture/`, J4a, ADR 0009), sans FreeCAD : étendue des
  membres et distance de chaque face au bord de son côté, options « fixe » par défaut (Q7 : la
  pièce bouge par défaut, toute distance est fixe ; « non fixe » au choix), règles de suivi
  (distance fixe, `Stay`, `Proportional`, épaisseur jamais étirée), expressions FreeCAD des
  liaisons (`<<Bureau>>.Depth - 40 mm`, positions relatives à `<<Bureau>>.Origin`), formules de
  l'utilisateur respectées, aperçu et refus d'un redimensionnement (pièce trop petite,
  assemblage qui perdrait son contact), sous-ensembles et refus d'un cycle d'ensembles.
- Ensemble dans le document (J4b′, ADR 0008 et 0009) : objet `Menuiserie::Furniture` (cotes
  `Width`, `Depth`, `Height`, `Origin`, `Template`, `Version`), propriétés de membre
  (`Furniture`, `PositionMode`, `FixedLeft` … `FixedTop`, `FurnitureBindings`) et liaisons par
  expressions natives ; `make_furniture`, `add_to_furniture`, `remove_from_furniture`,
  `set_member_options`, `rebind_furniture`, `resize_furniture` et `furniture_of`. Options
  changées dans l'éditeur de propriétés reliant le seul membre modifié, cote qui casse une
  pièce appliquée avec un avertissement, sous-ensembles, formules de l'utilisateur et
  contraintes de l'atelier Assembly respectées, liaisons reconnues après un renommage ou une
  copie, réouverture contrôlée ; déplacer une pièce usinée dont la brute est placée par une
  expression est refusé avec un message.
- Assemblage d'onglet (J4g) : stratégie `MiterStrategy` (deux pièces d'angle dessinées à leur
  longueur hors tout, qui se chevauchent au coin ; coupe du coin extérieur au coin intérieur,
  45° pour deux largeurs égales, enlèvement seulement), objet `Menuiserie::Miter` sans propriété
  propre, `make_miter`, commande **Onglet** et son icône, panneau générique qui affiche les
  angles de coupe.
- Queue d'aronde traversante (J4f) : solide `Prism` (polygone plan extrudé), stratégie
  `DovetailStrategy` (queues ajoutées au bout de la pièce à queues, logements traversants dans la
  pièce à griffes ; 3 queues environ par largeur de trois épaisseurs, griffes du tiers de
  l'épaisseur, angle des flancs de 10° par défaut, 30° au plus, en degrés), objet `Menuiserie::Dovetail`
  (`TailCount`, `PinWidth`, `Angle` en `App::PropertyAngle`), `make_dovetail(angle=…)`, commande
  **Queue d'aronde** et panneau générique (champ en degrés) ; une ancienne propriété `Slope`
  rouverte est convertie en `Angle`.
- Assemblage à mi-bois (J4e) : stratégie `HalfLapStrategy` (deux pièces de même épaisseur, à
  fleur, qui se chevauchent ; entaille de l'hôte par-dessus, de l'invitée par-dessous, profondeur
  automatique à la moitié de l'épaisseur), objet `Menuiserie::HalfLap` (`Depth`, `FlipSide`),
  `make_half_lap`, commande **Mi-bois** et panneau générique.
- Contrôles qualité : détection du code dupliqué (pylint) et limites de complexité (ruff) en CI ;
  grille « Conception et design patterns » pour l'architecte, le dev et le reviewer.
- Squelette de l'atelier : `package.xml`, enregistrement du workbench, icône.
- Outillage qualité : ruff, mypy, pytest, bandit, pre-commit.
- CI GitHub Actions : lint, typage, tests unitaires, tests d'intégration et test de chargement
  dans l'interface sur FreeCAD 1.0 et 1.1, analyse de sécurité (Bandit, Semgrep, gitleaks, CodeQL si public).
  Actions épinglées par SHA et tenues à jour par Dependabot.
- Définition des agents architecte, dev, testeur, sécurité et reviewer.
- ADR 0001 : structure de l'atelier.
- Bibliothèque de matériaux (`core/materials/`, J1a) : lecture sûre des fichiers JSON
  (format 1, 1 Mio maximum, `NaN`/`Infinity` refusés, BOM UTF-8 toléré), validation de chaque
  entrée avec anomalies traduisibles, fusion du fichier utilisateur par identifiant, indépendante
  de l'ordre des remplacements ; libellés normalisés en NFC ; `Material` et `LibraryIssue`
  hachables.
- Texture facultative des matériaux (`texture` : image relative au fichier de bibliothèque et
  taille réelle couverte en mm, `Material.texture`) ; la couleur reste le rendu de secours.
- Bibliothèque intégrée `data/materiaux.json` : 8 essences massives, 2 contreplaqués, MDF et
  mélaminé blanc.
- Les matériaux intégrés affichent leur photo (textures CC0 de `data/textures/`, taille réelle
  couverte d'après `SOURCES.md`).
- Modèle pur de la pièce de bois (`core/part_model.py`) : cotes finies (0,1 à 20 000 mm) et
  surcotes bornées, sens du fil, volume, masse, cotes de débit, épaisseurs standard et règles de
  changement de matériau ; la cote refusée est citée exactement dans le message.
- Marqueur de traduction `QT_TRANSLATE_NOOP` utilisable sans Qt (`core/i18n.py`).
- Pièce de bois paramétrique (J1b) : objet `WoodPart` (`Part::FeaturePython`, ADR 0003) aux
  cotes finies, avec matériau choisi dans la bibliothèque (identifiant, catégorie et masse
  volumique enregistrés dans le document), sens du fil, repère et surcotes de débit ; migration
  par `Version`, annuler / rétablir, recalcul en console (`freecadcmd`). La migration déduit
  les propriétés recréées du matériau de la pièce et aboutit même avec une bibliothèque vide
  (avertissement) ; un document créé par une version plus récente de l'atelier est signalé.
  Une cote ≤ 0 calculée par une expression met la pièce en erreur, sans exception.
- Commande **Pièce de bois** (`Menuiserie_WoodPart`, J1c) dans la barre d'outils et le menu
  Menuiserie : crée une planche de chêne 800 × 200 × 22 et ouvre son panneau de tâche ; inactive
  sans document ou si un panneau est déjà ouvert.
- Panneau de tâche de la pièce de bois (création et double-clic) : repère, filtre par type,
  matériau, sens du fil (libellés traduits), cotes finies et surcotes avec unités, épaisseurs
  standard en un clic, avertissement non bloquant pour un panneau d'épaisseur hors standard ;
  aperçu immédiat, « OK » = une entrée d'annulation (« Créer » ou « Modifier une pièce de
  bois »), « Annuler » ne laisse rien ; les cotes pilotées par une expression le restent.
- `core.part_model.is_nonstandard_panel_thickness()` : règle de l'avertissement d'épaisseur.
- Mémoire du sens du fil (exigence de jv, ADR 0005, C10) : propriété masquée
  `PreferredGrainDirection` (`Length` ou `Width`), enregistrée et annulable, mise à jour par
  chaque choix de `Length` ou `Width` ; en revenant à un matériau avec fil (panneau, éditeur de
  propriétés, `set_material`), la pièce reprend ce sens au lieu de `Length`.
- Fil masqué pour un matériau sans fil (exigence de jv, C11) : `GrainDirection` masquée dans
  l'éditeur de propriétés et ligne « Sens du fil » masquée dans le panneau ; le mode suit
  l'annulation et la réouverture. `features.wood_part.shows_grain()`.
- `core.part_model.remembered_grain()` et `core.part_model.material_has_grain()`.
- Capture `panneau.png` (panneau de tâche ouvert) publiée dans les PR ; vérifications
  d'interface hors écran de la commande et du panneau ; scénarios de recette manuelle J1c
  (`docs/recette/`).
- Façade `freecad.menuiserie.api.make_wood_part()` pour la console et les scripts ; les
  arguments sont validés avant de créer un document.
- Affichage de la pièce : icône de la pièce de bois et couleur du matériau, enregistrée dans la
  propriété de vue `MaterialColor`.
- Textures des matériaux dans la vue 3D (J1d, ADR 0004) : image du matériau affichée à
  l'échelle réelle et dans le sens du fil de la pièce (`GrainDirection`), sur FreeCAD 1.0 et 1.1,
  par des nœuds Coin propres à l'atelier ; image PNG ou JPEG décodée par Qt (décodeur imposé par
  l'extension, 16 Mio et 4 096 pixels au plus), partagée par toutes les pièces, jamais
  enregistrée dans le document ; couleur `MaterialColor` en secours, avec un seul avertissement
  par image. README : section « Ajouter une texture ». Captures de PR : texture de test
  quadrillée tous les 100 mm et gros plan `texture.png`.
- Bibliothèque vue de FreeCAD (`features/library.py`) : fichier utilisateur
  `<données utilisateur>/Menuiserie/materiaux.json` ou paramètre `UserLibraryPath`, lecture une
  fois par session (`reload_library()`), anomalies traduites dans la vue rapport.
- README : création d'une pièce depuis la console, section « Ajouter une essence ».
- Jeu d'icônes SVG 64 px pour l'atelier et les commandes prévues (pièce de bois, panneau,
  essences, liste de débit et export, assemblages, caisson), produit par
  `tools/generer_icones.py`.
- Géométrie pure des assemblages (`core/geometry.py`, J3a) : transformations rigides lues sur
  `Placement.toMatrix()`, axes relatifs de deux pièces d'équerre, classement contact /
  chevauchement / pièces séparées (tolérance 0,01 mm).
- Stratégies d'assemblage (`core/joints/`, J3a) : tenon-mortaise, rainure-languette et feuillure
  derrière un protocole commun et un registre figé ; proportions automatiques de menuisier
  (0 = automatique), plan d'usinage (tenon et languette ajoutés, mortaise, rainure et feuillure
  enlevées), refus par messages traduisibles ; paramètres immuables validés (dont ceux des
  tourillons) ; rôles hôte / invitée devinés d'après la position des pièces.
- Tenon-mortaise dans le document (J3b, ADR 0006) : `make_mortise_tenon(hôte, invitée, **params)`
  relie deux pièces de bois (ou leurs pièces usinées) ; chaque pièce assemblée a une **pièce
  usinée** (`Menuiserie::MachinedPart` : brute plus tenons, moins mortaises), la brute est
  masquée dessous. Tenons et mortaises suivent les cotes, la position et les expressions des
  pièces en un seul recalcul ; paramètres réglables dans l'éditeur de propriétés (0 =
  automatique) ; déplacer une pièce usinée déplace sa brute ; erreurs traduites dans l'état de
  l'objet, jamais de forme partielle ; réouverture contrôlée (`Version` 1), annuler / rétablir,
  `remove_machined_part`, `machined_part_of`, `blank_of`. Pièces usinées utilisables par
  `Part::Cut`, TechDraw et l'export STEP, et lisibles sans l'atelier (ADR 0007).
- Rainure-languette, feuillure et tourillons dans le document (J3c) : `make_tongue_groove`,
  `make_rabbet` et `make_dowels` (objets `Menuiserie::TongueGroove`, `Menuiserie::Rabbet` et
  `Menuiserie::Dowels`, mêmes règles de réouverture et d'annulation que le tenon-mortaise).
  Tourillons automatiques de menuisier : Ø 6, 8, 10 ou 12 mm sans dépasser la moitié de
  l'épaisseur (22 mm → Ø 10 x 40), à deux diamètres du bord, entraxe de 128 mm au plus ; leur
  nombre suit la longueur du contact ; la forme de l'assemblage montre les tourillons, les deux
  pièces usinées sont percées (jeu de fond de 1 mm, 3 mm de fond au moins).
- Commandes d'assemblage (J3d) dans la barre d'outils et le menu Menuiserie : **Tenon-mortaise**,
  **Rainure-languette**, **Feuillure**, **Tourillons** (base commune `JointCommand`), actives
  pour deux pièces distinctes sélectionnées (brutes ou usinées) et sans panneau ouvert ; rôles
  devinés d'après la position des pièces (ordre de sélection si c'est ambigu) ; une entrée
  d'annulation « Créer un assemblage … ». Un refus de la fabrique (pièces de deux conteneurs…)
  est affiché dans la barre d'état et la vue rapport.
- Affichage de la pièce usinée (`ViewProviderMachinedPart`) : icône de la pièce de bois,
  couleur et texture de sa brute (suivent le matériau et le fil), brute rangée dessous dans
  l'arbre ; le double-clic ouvre le panneau de la brute avec aperçu en direct ; suppression
  refusée tant qu'elle porte des assemblages, sinon la brute réapparaît. Assemblages
  (`ViewProviderJoint`) : icône de leur type, couleur hêtre. ViewProviders posés par l'api.
- Captures de PR : un cadre assemblé par quatre tenons-mortaises à côté du caisson, et le
  panneau d'un tenon-mortaise (`panneau-assemblage.png`).
- Panneau de tâche des assemblages (J3e), commun aux quatre types et construit d'après la
  description de leurs paramètres : pièces reliées, bouton **Inverser** (échange hôte et
  invitée), un champ par paramètre avec case **Auto** pour les cotes automatiques (le champ
  montre alors la valeur effective). Ouvert par les commandes d'assemblage (**Annuler** ne laisse
  ni assemblage ni pièce usinée, les brutes réapparaissent) et par double-clic sur un assemblage
  (entrée « Modifier un assemblage »). Aperçu en direct, erreur d'assemblage affichée dans le
  panneau, paramètre piloté par une expression jamais écrit.

### Modifié
- Panneau de la pièce de bois (J6c) : ordre des groupes **Identification** (repère / nom, premier
  champ du panneau), **Dimensions finies**, **Matériau**, puis **Rotation** (ancien groupe
  « Position », renommé, `objectName` `rotationGroup`) ; l'ordre des propriétés dans l'éditeur de
  propriétés de FreeCAD (ordre de création) est inchangé.
- `core/snap` (J6c, Q1 de jv) : `Turn` devient `X`, `Y`, `Z` (au lieu de `PIVOT` et `TILT`) ;
  `Orientation` porte l'une des 24 rotations d'une boîte ; `turned_in_place` tourne autour des
  axes du document.
- Panneau de la pièce de bois : ordre des groupes **Identification** (repère / nom, premier
  champ), **Dimensions finies**, **Matériau**, puis **Rotation** (ancien « Position ») ; l'ordre des propriétés dans l'éditeur de propriétés
  de FreeCAD (ordre de création) est inchangé.
- `core/snap` : `Turn` devient `X`, `Y`, `Z` (au lieu de `PIVOT` et `TILT`) ; `Orientation`
  porte l'une des 24 rotations d'une boîte ; `turned_in_place` tourne autour des axes du
  document.
- Panneaux de tâche : transactions, fermeture forcée et surveillance du document dans un socle
  commun (`gui/task_panels/base.py`, `ObjectTaskPanel`) partagé par la pièce de bois et les
  assemblages. L'aperçu de la pièce de bois ne recalcule plus les pages TechDraw ni les objets
  d'autres documents.
- `core/contact.py` : classement contact / chevauchement / pièces séparées sorti de
  `core/geometry.py` (limite de 400 lignes par module), sans changement de comportement.
- Apparence d'une pièce (texture et couleur) extraite du ViewProvider de la pièce de bois dans
  `gui/part_appearance.py` (`PartAppearance`), partagée avec la pièce usinée ; l'aperçu du
  panneau de la pièce recalcule aussi ses assemblages et sa pièce usinée.
- `features/schema.py` : ajout, contrôle de type, `Version` et modes d'édition des propriétés
  décrits par des `PropertySpec`, partagés par la pièce de bois, la pièce usinée et les
  assemblages (refactorisation sans changement de comportement).
- **Modèle de la pièce en version 2** (`MODEL_VERSION`) : migration 1 → 2 à la réouverture
  (ajout de `PreferredGrainDirection` d'après `GrainDirection`, `Length` pour une pièce sans
  fil) ; un document de version 2 ouvert par un atelier plus ancien est signalé comme plus
  récent.
- `core.part_model.grain_after_material_change(new, current, preferred=LENGTH)` : nouveau
  paramètre `preferred` (sens mémorisé repris quand le fil valait `NONE`) ; `NONE` refusé
  (`ValueError`).
- Filtre « Type » du panneau : un type qui exclut le matériau de la pièce applique le premier
  matériau de ce type, fil mémorisé et surcotes selon A7 (Q4 tranchée, C12).
- Bibliothèque de matériaux découpée en paquet `core/materials/` : façade à l'API publique figée
  (`__all__`) et modules privés (messages, modèle, anomalies, entrée, analyse, lecture, fusion) ;
  aides de validation partagées dans `core/_validation.py`, qui ne sont plus exposées par
  `core.materials` (`quoted_value`, `to_finite_float`) ; `quoted_value` est publique dans
  `core/text.py`.
- `Material(...)` et `Texture(...)` valident et normalisent tous leurs champs à la construction,
  avec les bornes de la lecture JSON (`ValueError` citant le champ).
- Épaisseur standard minimale d'un matériau : 0,1 mm (au lieu de « supérieure à 0 »), la plus
  petite cote d'une pièce : une bibliothèque qui déclare une épaisseur plus fine voit l'entrée
  rejetée.
- `features/wood_part.py` découpé (#11) : `wood_part_schema.py` (propriétés, énumérations,
  valeurs par défaut, modes d'édition) et `wood_part_restore.py` (contrôles de la réouverture) ;
  chemin de `WoodPart` inchangé. Alias de type et modes d'édition partagés dans
  `features/freecad_types.py`, `translated()` déplacée de `features/library.py` vers
  `features/i18n.py` ; bibliothèque lue une fois par réouverture d'une pièce.
- Suites de la revue de code J3, sans changement de comportement ni de document : type des
  paramètres d'assemblage déclaré par `PARAMS`, bases communes `StatelessProxy` (proxys) et
  `PanelEditing` (ViewProviders), aides partagées des panneaux (`UpdateGuard`,
  `expression_of`, `aborted_on_error`, `panel_title`) et de la vue rapport (`report_warning`),
  bornes du nombre de tourillons lues dans la propriété ; code mort retiré (`to_host`,
  `to_guest`, `TextureCache.usable`, `BudgetedCache.clear`, `JOINT_CLASSES`).

### Corrigé
- Revue finale de J6 : copier-coller, Std Dupliquer et fusion de documents ne donnent plus deux
  pièces (ni deux pièces usinées) de même libellé : la copie de « M1 » s'appelle « M1 (2) » et sa
  pièce usinée « M1 (2) (usinée) », repère inchangé ; une réouverture ordinaire et une annulation
  n'écrivent rien (spécification J6, L5 bis).
- Accrochage : un vecteur de norme nulle (arête de longueur nulle) lève une `ValueError` rattrapée
  par l'accrochage au lieu d'une `ZeroDivisionError`.
- Panneau de la pièce de bois : ensemble supprimé pendant que le panneau est ouvert, « OK »
  affiche le message de refus (pièce créée hors de l'ensemble) et rétablit la transparence ; les
  boutons X, Y, Z mettent aussitôt à jour la ligne « Contre » et les notices.
- Panneau de la brute ouvert depuis sa pièce usinée puis fermé par FreeCAD (brute supprimée,
  Édition > Annuler) : le mode édition est quitté même si la pièce usinée a perdu sa brute.
- Réouverture d'un document où une propriété de la pièce a un type inattendu (par exemple
  `Category` en texte) : la propriété est recréée avec sa valeur par défaut, avec
  avertissement, au lieu de faire échouer `record_of` (#11).
- Document créé par une version plus récente de l'atelier : une valeur d'énumération inconnue
  est gardée (avertissement) au lieu d'être remplacée, donc perdue à l'enregistrement (#11).
- `record_of(...).density` arrondie à 6 décimales : 710 au lieu de 709,9999999999999 après
  réouverture (#11).
- Panneau de la pièce de bois (J1c-1, J1c-2) : un double-clic sur une pièce pendant qu'un
  panneau est ouvert est refusé, au lieu de fermer le panneau en validant ses modifications.
- Panneau (J1c-4, J1c-5) : la pièce supprimée (Édition > Supprimer, console) ferme le panneau ;
  Édition > Annuler pendant le panneau le ferme et quitte le mode édition, au lieu de laisser
  des modifications hors transaction.
- « OK » ou « Annuler » sans modification juste après Édition > Annuler (J1c-6) : plus
  d'entrée « Modifier une pièce de bois » parasite, la pile « Rétablir » est conservée.
- Repère, matériau ou sens du fil pilotés par une expression (J1c-7 à J1c-9, C6) : champ
  inactif, jamais écrit par le panneau, filtre « Type » compris.
- Bibliothèque de matériaux vide : la commande « Pièce de bois » est inactive et, lancée
  quand même, affiche un message traduit au lieu d'une trace d'exception.
- Avertissement d'épaisseur hors standard affiché en texte brut (`textFormat` PlainText).
- Pièce d'un assemblage modifiée par un script (défaut D1, J3) : `HostPart` et `GuestPart` sont
  en lecture seule dans l'éditeur de propriétés (l'inversion reste possible par « Inverser ») ;
  modifiées quand même, l'assemblage passe en erreur avec un message traduit (supprimer puis
  recréer l'assemblage) au lieu de rester valide sans usiner les pièces.

### Sécurité
- Panneau des assemblages (audit de sécurité J3) : libellés des pièces hôte et invitée en texte
  brut, libellé de l'assemblage cité tronqué et échappé dans le titre.
- Tourillons automatiques plafonnés à 50 (`MAX_DOWEL_COUNT`), même sur un très long contact
  (20 m), comme le nombre saisi.
- Fermer le document pendant le panneau de création faisait planter FreeCAD 1.0 (J1c-3, audit
  B1) : le panneau est désormais fermé avec le document et la commande redevient active.
- Une exception à l'ouverture du panneau (création ou modification) ne laisse plus ni pièce ni
  transaction ouverte : le panneau est construit avant d'être affiché et la transaction est
  abandonnée avant de propager l'exception (audit A1).
- Bibliothèque de matériaux : lecture par un seul descripteur (`os.open` non bloquant, `fstat`,
  lecture bornée), clés JSON en double refusées, libellés sans caractère invisible, bidi, de
  contrôle ou demi-substitut, clés inconnues citées tronquées et échappées, au plus 200 anomalies
  par chargement, chemins de texture confinés au dossier du fichier de bibliothèque.
- Réouverture d'un document : libellé de la pièce, `MaterialId` et valeurs inconnues cités
  tronqués et échappés dans la vue rapport ; listes canoniques de `Category` et
  `GrainDirection` rétablies (valeur inconnue remplacée, avec avertissement) ; `Version` d'un
  type inattendu traitée comme un ancien fichier ; `ShapeAppearance` vide toléré.
- CI : dossier utilisateur FreeCAD temporaire pour les tests d'intégration.
- Images de texture (audit de sécurité J1d) : fichier ouvert une seule fois et décodé en mémoire
  (`core/texture_file.py` : confinement au dossier de la bibliothèque revérifié à chaque
  ouverture, `O_NOFOLLOW`, `O_NONBLOCK`, contrôle par `fstat`, lecture bornée), sans réouverture
  par le nom. JPEG de plus de 100 balayages refusé avant décodage (un JPEG
  progressif aux milliers de balayages vides figeait l'interface) ; PNG dont les données
  décompressées dépassent la taille de l'image annoncée refusé (bombe de décompression), sans
  décompresser au-delà ; mémoire des textures bornée à 256 Mio d'images décodées vivantes, y
  compris celles encore affichées, et nœud partagé par les liens physiques d'une même image ;
  chemin de l'image cité entier et échappé dans les avertissements.
