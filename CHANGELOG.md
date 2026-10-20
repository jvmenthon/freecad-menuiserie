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
- Modèle pur de la pièce de bois (`core/part_model.py`) : cotes finies (0,1 à 20 000 mm) et
  surcotes bornées, sens du fil, volume, masse, cotes de débit, épaisseurs standard et règles de
  changement de matériau ; la cote refusée est citée exactement dans le message.
- Marqueur de traduction `QT_TRANSLATE_NOOP` utilisable sans Qt (`core/i18n.py`).
- Pièce de bois paramétrique (J1b) : objet `WoodPart` (`Part::FeaturePython`, ADR 0003) aux
  cotes finies, avec matériau choisi dans la bibliothèque (identifiant, catégorie et masse
  volumique enregistrés dans le document), sens du fil, repère et surcotes de débit ; migration
  par `Version`, annuler / rétablir, recalcul en console (`freecadcmd`).
- Façade `freecad.menuiserie.api.make_wood_part()` pour la console et les scripts.
- Affichage de la pièce : icône de la pièce de bois et couleur du matériau, enregistrée dans la
  propriété de vue `MaterialColor`.
- Bibliothèque vue de FreeCAD (`features/library.py`) : fichier utilisateur
  `<données utilisateur>/Menuiserie/materiaux.json` ou paramètre `UserLibraryPath`, lecture une
  fois par session (`reload_library()`), anomalies traduites dans la vue rapport.
- README : création d'une pièce depuis la console, section « Ajouter une essence ».
- Jeu d'icônes SVG 64 px pour l'atelier et les commandes prévues (pièce de bois, panneau,
  essences, liste de débit et export, assemblages, caisson), produit par
  `tools/generer_icones.py`.

### Modifié
- Bibliothèque de matériaux découpée en paquet `core/materials/` : façade à l'API publique figée
  (`__all__`) et modules privés (messages, modèle, anomalies, entrée, analyse, lecture, fusion) ;
  aides de validation partagées dans `core/_validation.py`, qui ne sont plus exposées par
  `core.materials` (`quoted_value`, `to_finite_float`).
- `Material(...)` et `Texture(...)` valident et normalisent tous leurs champs à la construction,
  avec les bornes de la lecture JSON (`ValueError` citant le champ).
- Épaisseur standard minimale d'un matériau : 0,1 mm (au lieu de « supérieure à 0 »), la plus
  petite cote d'une pièce : une bibliothèque qui déclare une épaisseur plus fine voit l'entrée
  rejetée.

### Sécurité
- Bibliothèque de matériaux : lecture par un seul descripteur (`os.open` non bloquant, `fstat`,
  lecture bornée), clés JSON en double refusées, libellés sans caractère invisible, bidi, de
  contrôle ou demi-substitut, clés inconnues citées tronquées et échappées, au plus 200 anomalies
  par chargement, chemins de texture confinés au dossier du fichier de bibliothèque.
