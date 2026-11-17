# Fermer le caisson à partir du dessous ou du dessus

- Issue [#267](https://github.com/jvmenthon/freecad-menuiserie/issues/267), demande de jv (2026-11-17).
- Décision : [ADR 0064](../adr/0064-fermer-un-caisson-autour-d-une-piece-existante.md) (proposé).
- Statut : **proposée**, en attente des réponses de jv aux questions Q1 à Q9 (§ 7, choix
  recommandés marqués ★) et du choix de la maquette du panneau et de l'icône.

## 1. Besoin

Demande de jv : « en sélectionnant le dessous ou le dessus, les côtés sont générés ainsi que le
dessus ou le dessous. Dans un premier temps uniquement une base rectangulaire. Possibilité de
désactiver certains éléments. Choix des assemblages. Choix de la hauteur. »

Le menuisier a déjà dessiné une pièce (le **dessous** d'un meuble, ou son **dessus**), à sa place,
avec son matériau et son épaisseur. Il veut fermer la boîte autour d'elle en quelques clics, sans
recréer cette pièce ni perdre ce qu'il a déjà fait dessus (nom, finitions de chants, assemblages,
appartenance à un ensemble).

Hors du premier lot : base non rectangulaire (pièce dessinée, ADR 0020), étagères, portes,
tiroirs, socle et plinthe, régénération après coup (ADR 0010).

## 2. Vocabulaire

- **Ancre** : la pièce sélectionnée (le dessous ou le dessus). Elle n'est jamais déplacée ni
  redimensionnée (ADR 0064, point 1).
- **Pièce opposée** : le dessus quand l'ancre est le dessous, et inversement.
- **Éléments** : côté gauche, côté droit, arrière, avant, pièce opposée. Chacun peut être
  désactivé.
- **Jonctions** : côtés ↔ ancre et pièce opposée ; côtés ↔ avant et arrière (quand l'arrière ou
  l'avant est un panneau épais) ; fond ↔ son pourtour (quand l'arrière est un fond mince).

## 3. Comportement

1. Le menuisier sélectionne **une** pièce de bois rectangulaire (brute ou usinée), dans la vue 3D
   ou dans l'arbre, et lance **« Fermer le caisson »** (barre de l'atelier, à côté de
   « Caisson », et clic droit sur la pièce). Sans sélection valable, la commande est grisée et
   son infobulle dit pourquoi (ADR 0052).
2. **Sens du caisson.** Si une face de l'ancre est sélectionnée, le caisson monte depuis cette
   face. Sinon : si l'épaisseur de l'ancre est verticale, une ancre est prise pour le dessous et
   le caisson monte (+Z du document) ; sinon il part du côté +épaisseur de l'ancre. Le panneau
   permet d'inverser (« La pièce sélectionnée est : le dessous / le dessus »).
3. **Avant du caisson** (Q6) : par défaut le grand chant de l'ancre le plus proche de la caméra au
   lancement ; un bouton « Tourner l'avant » le fait passer au chant suivant (90°).
4. Un **panneau de tâche** s'ouvre (maquette au choix, § 6). Toute saisie met à jour l'**aperçu
   dans la vue 3D** aussitôt (règle de jv, `valueChanged`), dans une seule transaction
   « Fermer le caisson », comme le panneau du gabarit Caisson (J4d, K6).
5. **OK** crée les pièces, les assemblages et l'ensemble (une seule entrée d'annulation).
   **Annuler** ne laisse rien, l'ancre est intacte.

## 4. Géométrie (choix ★ des questions du § 7)

Repère du caisson = repère de l'ancre : X le long de sa longueur (largeur du caisson), Y le long
de sa largeur (profondeur, avant en 0), Z vers l'intérieur du caisson. L'ancre occupe
`[0, L] × [0, P] × [0, e]`. Notations : `H` hauteur hors tout (ancre comprise), `t` épaisseur des
panneaux créés, `f` épaisseur du fond, `r` profondeur de la feuillure du fond.

- **Ancre et pièce opposée filantes** (Q1 ★) : l'emprise du caisson est celle de l'ancre ; la
  pièce opposée a les mêmes longueur et largeur que l'ancre, en `z ∈ [H − t, H]`.
- **Côtés gauche et droit** posés sur l'ancre, entre l'ancre et la pièce opposée, pleine
  profondeur : `L × P` → côté de `(H − e − t) × P × t` (sans pièce opposée : `H − e`).
- **Arrière = fond mince en feuillure** (Q3 ★) des côtés, de l'ancre et de la pièce opposée,
  comme le gabarit Caisson (retraits fixes, feuillure filante). Variante : panneau épais entre
  les côtés.
- **Avant** (décoché par défaut, Q2) : panneau épais entre les côtés, au ras de l'avant.
- **Onglet** choisi aux angles : le côté passe à la hauteur hors tout et chevauche le bout de
  l'ancre et de la pièce opposée ; l'onglet coupe les deux à 45° (règle de chevauchement de J3,
  spec J3 § A2). L'ancre garde ses cotes : seule sa pièce usinée change.
- Pièces créées : épaisseur et matériau de l'ancre par défaut (Q8), modifiables.
- Ensemble : options « fixe » explicites (ADR 0010) ; côtés, pièce opposée et fond suivent
  `Height`, `Width` et `Depth` de l'ensemble.

## 5. Assemblages proposés (Q5)

| Jonction | Choix proposés | Défaut ★ |
| --- | --- | --- |
| Côtés ↔ dessous et dessus | Aucun (vissé, collé), Tourillons, Queues d'aronde, Onglet, Feuillure | Tourillons |
| Côtés ↔ avant et arrière épais | Aucun, Tourillons, Queues d'aronde, Onglet, Feuillure | Tourillons |
| Fond mince | Feuillure, Rainure, Aucun (vissé derrière) | Feuillure |

Ne sont proposés que les assemblages déjà présents dans l'atelier (J3, biais). Un choix
impossible avec les cotes saisies (tourillons dans moins de 12 mm, queues d'aronde trop courtes)
est grisé avec la raison en infobulle. Les lamelles et faux tenons (quincaillerie, issue #159)
viendront quand ils seront dans `main`.

## 6. Panneau : trois maquettes (règle « nouvelle interface »)

Maquettes dans [`fermer-le-caisson/`](fermer-le-caisson/) (images) :

- **A — Formulaire** : champs (hauteur, épaisseur, matériau), cases à cocher des éléments, trois
  listes d'assemblages. Le plus proche des panneaux actuels, le plus simple à coder.
- **B — Schéma cliquable ★** : un dessin du caisson en perspective, chaque élément d'une couleur ;
  un clic sur un élément l'active ou le désactive (grisé, croix rouge), les jonctions portent
  leur liste d'assemblage. Même langage que la maquette A retenue pour les profils d'arête.
- **C — Tableau par élément** : une ligne par élément (case, épaisseur, matériau, assemblage) ;
  le plus de réglages, le plus dense.

Trois propositions d'icône dans le même dossier.

## 7. Questions pour jv (★ = recommandation)

| N° | Question | Choix ★ | Autres choix |
| --- | --- | --- | --- |
| Q1 | Place du dessous et du dessus par rapport aux côtés | Filants : sous et sur les côtés, l'emprise reste celle de la pièce sélectionnée | Entre les côtés (le caisson s'élargit de deux épaisseurs) ; au choix dans le panneau |
| Q2 | Éléments cochés par défaut | Côtés, fond, pièce opposée ; avant décoché | Tout coché |
| Q3 | Arrière | Fond mince en feuillure (comme le gabarit Caisson), panneau épais au choix | Toujours un panneau épais |
| Q4 | Hauteur saisie | Hors tout, ancre comprise | Intérieure ; au choix |
| Q5 | Assemblages | Une liste par jonction (§ 5), tourillons et feuillure par défaut | Une seule liste pour tout le caisson |
| Q6 | Avant du caisson | Grand chant de l'ancre le plus proche de la caméra, bouton « Tourner l'avant » | Toujours le chant −Y de l'ancre |
| Q7 | Ensemble | Nouvel ensemble « Caisson » avec l'ancre ; sous-ensemble si l'ancre était dans un ensemble (ADR 0037) | Ajouter les pièces à l'ensemble de l'ancre ; pas d'ensemble |
| Q8 | Épaisseur et matériau des pièces créées | Ceux de l'ancre, modifiables (panneaux, fond) | Ceux du gabarit Caisson (18 mm, contreplaqué bouleau) |
| Q9 | Maquette du panneau et icône | Panneau B, icône A (côtés en transparence et flèche : lisible en 16 px, distincte de « Caisson ») | Panneau A ou C ; icône B ou C |

## 8. Critères d'acceptation

U = test unitaire (sans FreeCAD), I = intégration FreeCAD, G = interface (QTest, ADR 0059).

| N° | Critère | Type |
| --- | --- | --- |
| FC1 | Ancre 600 × 400 × 18 à plat en (0, 0, 0), hauteur 720, défauts : côtés 684 × 400 × 18 en `x ∈ [0, 18]` et `[582, 600]`, `z ∈ [18, 702]` ; dessus 600 × 400 × 18 en `z ∈ [702, 720]` ; fond en feuillure ; 4 jonctions à tourillons, 4 feuillures. | U |
| FC2 | Même ancre prise pour le dessus (hauteur 720) : le caisson descend, `z ∈ [−702, 18]`. | U |
| FC3 | Pièce opposée décochée : côtés de 702 ; fond décoché : aucun fond ni feuillure ; côté droit décoché : ni côté droit ni ses assemblages. | U |
| FC4 | Onglet aux angles : côtés de 720 qui chevauchent l'ancre et la pièce opposée, 4 onglets ; l'ancre garde `Length`, `Width`, `Thickness`, `Placement`. | I |
| FC5 | Ancre tournée (90° autour de X, debout) : toutes les pièces sont dans son repère, l'ensemble porte sa rotation. | I |
| FC6 | Ancre membre d'un ensemble E : elle en sort, le caisson devient sous-ensemble de E, une seule annulation remet tout. | I |
| FC7 | Refus avec message : pièce dessinée, plusieurs pièces, hauteur ≤ e + t, tourillons sous 12 mm, matériau inconnu. | U |
| FC8 | Panneau : chaque saisie met l'aperçu à jour ; OK = une entrée « Fermer le caisson » ; Annuler : document identique (ancre comprise). | G |
| FC9 | Le gabarit Caisson existant donne exactement les mêmes pièces qu'avant (non-régression de `Layout`). | U |
| FC10 | La liste de débit liste les pièces créées ; les pièces sont des `Part::Feature` lisibles hors de l'atelier. | I |

## 9. Lots

- **FC-a** (core) : `Layout.anchor`, `core/templates/closing.py`, tests FC1–FC3, FC7, FC9.
- **FC-b** (features, api) : `build_layout(existing=…)`, ensemble et sous-ensemble, classes
  d'assemblage ajoutées, tests FC4–FC6, FC10.
- **FC-c** (gui) : commande, icône retenue, panneau retenu, aperçu, scénario QTest FC8, captures
  de la PR.

Une branche, revue complète (testeur, sécurité, reviewer) avec sévérités et corrections, CI verte
avant d'annoncer la PR prête. jv seul fusionne.
