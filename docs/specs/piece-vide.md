# Pièce vide (« local ») pour placer un meuble

- Statut : **proposée**, en attente des réponses de jv (§ 8).
- Demande de jv (2026-11-07) : « je veux une feature pour créer une pièce vide qui permet de positionner un meuble ».
- ADR : **[0042 — Pièce vide, objet de contexte hors débit](../adr/0042-piece-vide-contexte-hors-debit.md)** (proposé).
- ADR liés : 0008 (Ensemble, objet de cotes), 0010 (gabarits générateurs), 0021 (glissement à la souris et aimantation), 0007 (compatibilité avec les autres ateliers).
- Branche de jalon : `jalon/piece-vide`, partie de `main`.

**Lecture retenue de la demande.** « Pièce » = une pièce d'habitation (salle, chambre, cuisine) :
un volume vide, avec sol, murs et éventuellement plafond et ouvertures, qui sert de **contexte**
pour poser un meuble à sa place réelle. Ce n'est pas une pièce de bois et elle ne figure jamais
dans la liste de débit. (Si jv voulait un simple bloc repère, les lots PV-a et PV-b suffisent.)

**Vocabulaire.** *Local* : l'objet « pièce vide ». *Mur* : face intérieure verticale du local.
*Ouverture* : porte ou fenêtre percée dans un mur, avec ses cotes. *Contexte* : objet affiché
et aimanté mais jamais compté.

## 1. Problème

Aujourd'hui un meuble se dessine dans le vide. Le menuisier doit vérifier à part qu'il passe sous
la pente du plafond, qu'il tient entre deux murs, qu'il ne bouche pas une fenêtre ni le
débattement d'une porte. Les outils de FreeCAD (Arch/BIM) existent mais sont lourds et leurs
objets ne s'aimantent pas aux nôtres.

## 2. Ce que fait la fonction

1. Commande **« Créer une pièce vide »** (menu et barre de l'atelier) : panneau avec longueur,
   largeur, hauteur sous plafond, épaisseur des murs. Aperçu en direct dans la vue 3D.
2. Le local est affiché en **transparence** : sol, quatre murs vus de l'intérieur, plafond
   masquable. Il ne gêne pas la sélection des meubles (clic traversant, comme les repères).
3. Les meubles et pièces **s'aimantent** aux murs, au sol et au plafond avec le glissement à la
   souris existant (ADR 0021) ; les cotes « distance au mur » sont lisibles et saisissables
   (ADR 0022).
4. Des **ouvertures** (porte, fenêtre) s'ajoutent à un mur : position, largeur, hauteur, hauteur
   d'allège. Elles se voient et servent de repère (un meuble qui les masque est signalé).
5. Le local est **exclu** de la liste de débit, du CSV et des fournitures. Il apparaît dans une
   section « Contexte » de l'arbre.
6. Tout est modifiable après coup (cotes du local, des ouvertures) ; les meubles posés
   gardent leur distance au mur choisie (« fixe / non fixe », ADR 0009).

## 3. Hors périmètre

Plan d'étage à plusieurs pièces, murs non rectangulaires (en L, pente de toit), import IFC/BIM,
électricité et plomberie, calcul de surface habitable.

## 4. Découpage proposé

| Lot | Contenu |
|---|---|
| PV-a | Modèle pur `core/room/` (cotes validées, murs, ouvertures) + objet `Local` + exclusion du débit |
| PV-b | Commande et panneau de création, aperçu en direct, transparence, clic traversant |
| PV-c | Aimantation des pièces aux murs, sol et plafond ; cotes de distance au mur |
| PV-d | Ouvertures (porte, fenêtre), signalement d'un meuble qui les masque |
| PV-e | Gabarit de local réutilisable (lien avec les gabarits de meubles, ADR 0035/0036) |

## 5. Critères d'acceptation (extrait)

- R1 : créer un local 4000 × 3000 × 2500 : un sol, quatre murs, un plafond, en une transaction.
- R2 : le local n'apparaît ni dans la liste de débit ni dans le CSV.
- R3 : glisser une armoire vers un mur : elle s'aimante au contact, sans traverser.
- R4 : modifier la longueur du local déplace les murs ; une pièce « fixe » à 50 mm d'un mur le suit.
- R5 : une porte de 830 mm ajoutée à un mur se voit et ne perce pas les pièces posées.
- R6 : le fichier s'ouvre sans l'atelier : le local est un objet Part standard (ADR 0007).

## 6. Compatibilité avec les autres ateliers

Le local est une forme Part ordinaire (solides murs, sol, plafond) avec un `Proxy` Python
dans notre espace de noms. Pas de dépendance à Arch. Sans notre atelier, on voit les solides.

## 7. Risques

- Un local épais gêne l'aimantation par erreur : le contexte doit avoir sa propre priorité.
- Transparence et clic traversant : piège connu de la vue (ViewObject), voir la reprise sur la transparence en édition.

## 8. Questions pour jv

Les choix ★ sont mes recommandations.

- **Q1.** Qu'est-ce qu'une « pièce vide » ? ★ (a) une pièce d'habitation (sol, murs, plafond) ;
  (b) un simple volume repère sans murs ; (c) une pièce de bois fantôme.
- **Q2.** Forme : ★ rectangle seul au début ; (b) rectangle + pan coupé / forme en L plus tard ?
- **Q3.** Murs : ★ épaisseur réelle (ex. 100 mm, on voit la face intérieure) ; (b) simples plans.
- **Q4.** Plafond : ★ présent mais masquable ; (b) absent.
- **Q5.** Ouvertures dès cette première livraison ? ★ oui, porte et fenêtre simples (PV-d) ; (b) plus tard.
- **Q6.** Aimantation aux murs : ★ activée par défaut, désactivable ; (b) seulement à la demande.
- **Q7.** Cotes types par défaut : ★ 4000 × 3000 × 2500 mm ; autre valeur ?
- **Q8.** Un fichier peut-il avoir plusieurs locaux ? ★ oui (un par pièce de la maison) mais sans mise en relation.
- **Q9.** Lien avec les gabarits de meubles : ★ un gabarit de meuble peut demander « se caler dans ce local » plus tard (PV-e) ; (b) séparer complètement.
