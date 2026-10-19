# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions
[SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté
- Squelette de l'atelier : `package.xml`, enregistrement du workbench, icône.
- Outillage qualité : ruff, mypy, pytest, bandit, pre-commit.
- CI GitHub Actions : lint, typage, tests unitaires, tests d'intégration et test de chargement
  dans l'interface sur FreeCAD 1.0 et 1.1, analyse de sécurité (Bandit, Semgrep, gitleaks, CodeQL si public).
  Actions épinglées par SHA et tenues à jour par Dependabot.
- Définition des agents architecte, dev, testeur, sécurité et reviewer.
- ADR 0001 : structure de l'atelier.
- Bibliothèque de matériaux (`core/materials.py`, J1a) : lecture sûre des fichiers JSON
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

### Sécurité
- Bibliothèque de matériaux : lecture par un seul descripteur (`os.open` non bloquant, `fstat`,
  lecture bornée), clés JSON en double refusées, libellés sans caractère invisible, bidi, de
  contrôle ou demi-substitut, clés inconnues citées tronquées et échappées, au plus 200 anomalies
  par chargement, chemins de texture confinés au dossier du fichier de bibliothèque.
