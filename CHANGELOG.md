# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions
[SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté
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

### Corrigé
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
