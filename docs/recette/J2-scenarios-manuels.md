# J2 — Scénarios de recette manuelle (liste de débit)

Critère G4 (et parties visuelles de S3, S6, G1 à G3) de la
[spécification J2](../specs/J2-liste-de-debit.md), à dérouler à la main sur **FreeCAD 1.1.4**
(Windows) et, si possible, **FreeCAD 1.0**, atelier installé depuis la branche du lot ; le CSV
est ouvert dans **LibreOffice Calc** et dans **Excel**, en interface française. Les résultats
et les captures sont reportés dans la PR.

G1 à G3, la création du PDF (en-tête %PDF) et la numérotation sont aussi vérifiés hors écran par `tests/gui/verifier_atelier.py`
(`verifications_debit.py`), le calcul, la feuille et le CSV par `tests/integration/` et
`tests/unit/` ; cette recette ne vérifie que ce qu'un écran et un tableur montrent.

## Préparation : scène de référence

Nouveau document **enregistré** (par exemple `recette-debit.FCStd`), atelier **Menuiserie**.

1. Gabarit **Caisson** (J4d) avec ses paramètres par défaut (600 mm de large, une étagère,
   assemblage par tourillons), **OK**. L'ensemble « Caisson » est créé.
2. Une tablette posée par **Pièce de bois** entre les faces intérieures des deux côtés (J6d,
   scénario 13 de la [recette J6](J6-scenarios-manuels.md)), repère « Tablette », ajoutée à
   l'ensemble.
3. Une traverse à tenons : deux pièces de chêne « Montant » (600 × 60 × 60) et « Traverse »
   (280 × 60 × 22), reliées par **Tenon-mortaise** (panneau laissé aux valeurs par défaut),
   hors de l'ensemble.
4. Un lien vers une pièce : sélectionner « Tablette », *Édition › Lien* (**Std Link**,
   `App::Link`) ; le lien « Tablette001 » apparaît dans l'arbre.

Cliquer dans le vide de la vue 3D pour ne rien sélectionner.

## Feuille « Liste de débit »

| N° | Action | Résultat attendu |
|---|---|---|
| 1 | Survoler les boutons **Liste de débit** et **Exporter la liste de débit (CSV)…** de la barre d'outils, puis le menu **Menuiserie**. | Deux boutons à icône (feuille de tableau avec une planche ; feuille avec une flèche verte), placés **après** les assemblages et les ensembles ; mêmes entrées dans le menu. Infobulle de la liste : elle précise que la feuille **n'est pas recalculée toute seule**. |
| 2 | Rien de sélectionné : **Liste de débit**. | Une feuille « Liste de débit » apparaît dans l'arbre **et s'ouvre dans un onglet** de la vue centrale. Titre en gras, ligne « Calculée le … ; mise à jour automatiquement à chaque recalcul du document. », portée **« Tout le document »**. |
| 3 | Lire le tableau. | Colonnes Repère, Qté, cotes finies, cotes de débit, Matériau, Fil, Ensemble, Volume, Masse, Surface, Remarque ; en-tête en gras ; nombres alignés à droite ; une ligne par groupe de pièces identiques. **Les deux côtés du caisson sont sur une seule ligne de quantité 2.** |
| 4 | Ligne de « Traverse ». | Longueur de débit **plus grande** que la longueur finie (280 mm) de la longueur des tenons ; la colonne Remarque indique « Ajouts compris (L / l / e) : … mm ». |
| 5 | Ligne de « Tablette ». | **Quantité 2** : la pièce d'origine et son lien. |
| 6 | Sous le tableau. | **Totaux par matériau** (quantité, volume en m³, masse en kg, surface des panneaux en m²) avec le total général, puis **Fournitures** : les tourillons du caisson regroupés par diamètre et longueur. Aucun avertissement s'il n'y a rien à signaler (sinon ils sont en bas de la feuille et dans la **vue rapport**, préfixés « Menuiserie : »). |
| 7 | Cliquer dans une cellule du tableau. | Du texte et des nombres, jamais de formule (la barre de contenu ne montre ni `=` ni formule). |
| 8 | *Édition › Annuler*. | La feuille **disparaît** (et son onglet se ferme) ; une seule entrée d'annulation « Liste de débit ». *Rétablir* la ramène, remplie. |

## Mise à jour

| N° | Action | Résultat attendu |
|---|---|---|
| 9 | Dans la feuille, écrire « à vérifier » en **P2** (colonne P, à droite de Remarque). Allonger « Traverse » de 20 mm (double-clic, Longueur). Relancer **Liste de débit**. | **La même feuille** est réécrite (pas de seconde feuille), datée de l'instant ; la longueur de la traverse a changé ; **« à vérifier » est toujours en P2**. |
| 10 | Renommer la feuille (F2) « Débit v1 », modifier une pièce, relancer **Liste de débit**. | La feuille renommée est retrouvée et mise à jour : pas de nouvelle feuille « Liste de débit ». |
| 11 | *Édition › Annuler*. | La feuille revient à son état d'avant la dernière mise à jour (ancienne longueur, ancienne date), « à vérifier » toujours là. |
| 12 | Modifier une pièce **sans** relancer la commande (cote dans l'éditeur de propriétés), puis recalculer (Ctrl+R). | La feuille change toute seule au recalcul (liste vivante, ADR 0013) ; Annuler restaure la pièce et la feuille. Un objet « Mise à jour de la liste de débit » est visible dans l'arbre. |

## Portée : sélection

| N° | Action | Résultat attendu |
|---|---|---|
| 13 | Dans l'arbre, sélectionner **l'ensemble « Caisson » seul**, puis **Liste de débit**. | Portée « Sélection : 1 objet » ; toutes les pièces du caisson (côtés, dessus, dessous, fond, étagère, tablette) et **ses** tourillons, mais ni « Montant », ni « Traverse ». La **sélection reste celle de départ** (l'ensemble est toujours surligné). |
| 14 | Sélectionner « Montant » et « Traverse » (Ctrl), **Liste de débit**. | Portée « Sélection : 2 objets » ; seules ces deux pièces sont listées, la traverse tenons compris. |
| 15 | Dans la vue 3D, sélectionner **plusieurs faces d'une même pièce** (Ctrl), **Liste de débit**. | Portée « Sélection : 1 objet » : l'objet n'est compté qu'une fois. |

## Export CSV

| N° | Action | Résultat attendu |
|---|---|---|
| 16 | Sans sélection, **Exporter la liste de débit (CSV)…**. | Boîte d'enregistrement du système, **dossier du document** (celui de `recette-debit.FCStd`), nom proposé **« recette-debit - liste de débit.csv »**, filtre « Fichiers CSV (*.csv) ». |
| 17 | **Annuler** la boîte. | Rien ne se passe : aucun fichier, aucun message. |
| 18 | Relancer, valider le nom proposé. | Le fichier est créé ; la **barre d'état** affiche « Liste de débit exportée dans « … » ». Aucune entrée d'annulation n'est ajoutée : l'export ne modifie pas le document (hormis un recalcul si des objets étaient à recalculer). La sélection n'a pas bougé. |
| 19 | Écraser le même fichier (relancer, même nom). | Le fichier est remplacé sans message d'erreur (écriture atomique) ; aucun fichier temporaire `.…tmp` ne reste dans le dossier. |
| 20 | Ouvrir le CSV dans **LibreOffice Calc** (double-clic, ou *Fichier › Ouvrir*). | Le CSV est au format **international** (virgule, point décimal, UTF-8 avec BOM) : Calc peut ouvrir l'assistant d'import, qui doit proposer **UTF-8** et le séparateur **virgule** ; une fois validé, accents corrects (« Épaisseur », « Chêne », « m³ »), colonnes séparées, nombres reconnus (alignés à droite, additionnables). Totaux et fournitures sous le tableau, séparés par une ligne vide. |
| 21 | Ouvrir le même CSV dans **Excel en interface française** par double-clic. | Noter précisément ce qui s'affiche : le BOM fait reconnaître l'UTF-8 (accents corrects), mais Excel français attend le **point-virgule** et la **virgule décimale** : le séparateur virgule peut laisser chaque ligne dans **une seule colonne** et les nombres à point peuvent être lus comme du texte ou des dates. Si c'est le cas, vérifier que *Données › À partir du texte/CSV* (origine UTF-8, délimiteur virgule) les lit bien, et que `api.export_cut_list_csv(doc, "debit.csv", dialect=api.FRENCH_CSV)` s'ouvre, lui, directement. Reporter le comportement observé dans la PR (il décide si le dialecte français doit devenir un choix de l'interface). |
| 22 | Nommer une pièce `=1+1` (repère) et exporter. | Le tableur affiche le **texte** `'=1+1` (apostrophe comprise) : aucune formule n'est exécutée. |
| 23 | Exporter vers un nom **sans extension** (« essai »). | « essai.csv » est créé. |
| 24 | Exporter vers un nom d'une autre extension (« essai.txt »). | Une **boîte d'avertissement** « Menuiserie : action refusée » s'affiche (« n'a pas l'extension .csv ») ; le message figure aussi dans la barre d'état et la vue rapport ; aucun fichier créé. |
| 25 | Exporter vers un fichier ouvert en écriture dans Excel (Windows). | Boîte d'avertissement « l'écriture de … a échoué » : aucun fichier abîmé (le précédent reste lisible). |
| 26 | Sélectionner **l'ensemble seul**, exporter. | Le CSV ne contient que les pièces du caisson, sans « Montant » ni « Traverse ». |

## Export PDF

| N° | Action | Résultat attendu |
|---|---|---|
| 32 | Sans sélection, **Exporter la liste de débit (PDF)…**. | Boîte d'enregistrement du système, dossier du document, nom proposé **« recette-debit - liste de débit.pdf »**, filtre « Fichiers PDF (*.pdf) ». |
| 33 | **Annuler** la boîte. | Rien ne se passe : aucun fichier, aucun message. |
| 34 | Relancer, valider. Ouvrir le PDF dans un lecteur. | Fichier créé, **barre d'état** « Liste de débit exportée dans « … » ». Page **A4 paysage**, marges d'environ 10 mm ; titre « Liste de débit - recette-debit », date, portée « Tout le document » ; tableau des pièces lisible (rien de coupé à droite, accents corrects), totaux par matériau, fournitures (tourillons), avertissements éventuels. Plusieurs pages si besoin : aucune ligne coupée en deux. |
| 35 | Imprimer le PDF (ou l'aperçu avant impression). | Rien ne déborde de la feuille ; texte net. |
| 36 | Sélectionner « Montant » et « Traverse », exporter en PDF. | Portée « Sélection : 2 objets » ; seules ces pièces. Le document n'a pas changé (aucune entrée d'annulation). |
| 37 | Exporter vers « essai » (sans extension), puis vers « essai.csv ». | « essai.pdf » est créé ; le second est refusé en boîte d'avertissement (« n'a pas l'extension .pdf »), aucun fichier créé. |
| 38 | Écraser un PDF ouvert dans le lecteur (Windows). | Soit le PDF est remplacé, soit une boîte d'avertissement d'échec s'affiche ; jamais un PDF abîmé. |

## Numérotation des repères

Préparation : dans un document neuf, trois pièces de chêne sans repère (800 × 100 × 22 deux
fois, 300 × 100 × 22 une fois), une quatrième déjà repérée « M7 ».

| N° | Action | Résultat attendu |
|---|---|---|
| 39 | Sans sélection, **Numéroter les repères**. | Les deux pièces identiques reçoivent le **même** repère « M1 », la petite « M2 » (numéros sans trou, « M7 » sauté ni modifié) ; le libellé de chaque pièce suit son repère (« M1 », « M1 (2) », « M2 »). Barre d'état : bilan du nombre de pièces et de repères. |
| 40 | *Édition › Annuler*. | Tous les repères reviennent d'un coup (une seule entrée « Numéroter les repères »). |
| 41 | Refaire, puis relancer **Numéroter les repères**. | Rien ne change ; la barre d'état indique qu'aucune pièce n'est sans repère. |
| 42 | Si la liste de débit existe, la regarder après la numérotation. | Elle s'est mise à jour toute seule : une ligne « M1 » de quantité 2. |
| 43 | Ajouter une pièce sans repère, la sélectionner seule, **Numéroter les repères**. | Seule cette pièce reçoit le premier numéro libre ; les autres sont inchangées. |

## Robustesse

| N° | Action | Résultat attendu |
|---|---|---|
| 27 | Modifier la longueur d'un montant de l'assemblage **sans** recalculer (modifier une propriété sans appuyer sur F5), puis lancer **Liste de débit** ou l'export. | Le document est **recalculé** avant le calcul (la forme usinée de la traverse est à jour : tenons comptés) ; pas d'avertissement « forme non recalculée ». |
| 28 | Ouvrir un panneau de tâche (double-clic sur une pièce), regarder les quatre boutons. | Les quatre boutons sont **grisés** tant que le panneau est ouvert ; actifs après **OK** ou **Annuler**. |
| 29 | Sans document ouvert, regarder les boutons. | Grisés. |
| 30 | Enregistrer, fermer, rouvrir le document **sans l'atelier** (autre atelier actif, ou `freecadcmd`). | La feuille est une feuille FreeCAD ordinaire, lisible ; aucune erreur ni message d'objet inconnu. |
| 31 | Ouvrir *Édition › Préférences* après toutes ces opérations. | Aucune rubrique ni réglage créé par la liste de débit. |
