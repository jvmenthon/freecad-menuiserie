# Répétition de pièces

- Issue [#180](https://github.com/jvmenthon/freecad-menuiserie/issues/180), demande de jv (2026-11-07).
- Décision : [ADR 0043](../adr/0043-repetition-par-copies-ordinaires.md) (proposé).
- Statut : **en attente des réponses de jv** (§ 6). Les choix ★ s'appliquent par défaut.

## 1. Besoin

Répéter une sélection (une ou plusieurs pièces, avec leurs assemblages) N fois à pas régulier :
tasseaux d'un lattis, lames d'un bardage, barreaux d'un garde-corps ou d'une chaise, étagères,
pieds, tiroirs d'un module. Aujourd'hui on doit copier à la main chaque pièce, puis recréer ses
assemblages. Le gabarit « Caisson » sait déjà répartir des étagères, mais seulement lui.

Hors périmètre : répétition en grille 2D ou selon une courbe, répétition d'un usinage seul dans
une pièce (les tourillons et les tasseaux de pied ont déjà leurs assemblages à plusieurs
éléments), liaison par expressions entre copies (voir Q6).

## 2. Comportement proposé

Commande **« Répéter »** (barre d'outils et menu) : l'utilisateur sélectionne des pièces ou des
ensembles, lance la commande ; un panneau de tâche propose :

| Champ | Sens |
|---|---|
| Mode | « Nombre et pas » · « Nombre sur une longueur » · « Pas sur une longueur » |
| Nombre N | copies **en plus** de la source (la source reste n° 1), 1 à 100 |
| Pas | entraxe (mm) entre deux copies, de point homologue à point homologue |
| Longueur | étendue totale (du début de la source à la fin de la dernière copie), mode 2 et 3 |
| Direction | axe X, Y ou Z du repère global, avec bouton « Inverser » |

Les trois modes donnent la même chose : une liste de décalages `k × pas`, k = 1..N.
Mode 2 : `pas = (longueur − étendue de la source) / N` ; mode 3 : `N = ⌊(longueur − étendue) / pas⌋`.
Un pas inférieur à l'étendue de la source sur l'axe fait se chevaucher les copies : avertissement
(non bloquant) « les copies se touchent ou se chevauchent ».

Aperçu en direct dans la vue 3D à chaque saisie (règle de jv du 2026-10-22), refus en rouge
si N ou le pas sont hors bornes. **OK** crée tout dans une seule transaction (une annulation).

## 3. Ce que « copier » veut dire

1. Chaque copie d'une pièce est une **pièce ordinaire** (brute + usinée, ADR 0006), mêmes cotes,
   matériau, sens du fil, finitions et options, décalée de `k × pas`. Nom : « {nom} {k+1} ».
2. Assemblage entre deux pièces **toutes deux sélectionnées** : recréé pour chaque copie entre
   les copies homologues (mêmes paramètres).
3. Assemblage entre une pièce sélectionnée et une pièce **non sélectionnée** (ex. barreau avec
   tenons dans deux traverses) : recréé pour chaque copie, la pièce non sélectionnée gardant son
   rôle (hôte ou invitée). Si l'assemblage ne tient plus géométriquement (copie qui sort de la
   traverse), il est créé quand même et la vérification J3 signale le problème sur la copie.
4. Quincaillerie : référence et modèle repris comme les assemblages.
5. Si la source est membre d'un ensemble, les copies le sont aussi, avec les mêmes options
   (mode, « fixe », verrou). Les copies ne sont **pas** réparties à nouveau quand on redimensionne
   l'ensemble : pour des étagères qui doivent suivre, rester sur le gabarit Caisson.
6. Les copies sont indépendantes (pas d'expression vers la source) sauf choix de jv en Q6.
7. Chaque copie porte `RepeatGroup` (identifiant de la répétition) et `RepeatIndex`, en lecture
   seule : base d'une future commande « Changer le nombre ».

## 4. Compatibilité avec les autres ateliers

Les copies sont des `Part::FeaturePython` ordinaires avec forme `Part` standard : elles se
déplacent, se mesurent et s'exportent comme toute pièce. Aucune modification globale de FreeCAD,
propriétés dans l'espace de noms de l'atelier (ADR 0007).

## 5. Découpage et critères (tests)

| Lot | Contenu | Tests |
|---|---|---|
| R-a | `core/repeat/` (Python pur) : décalages des trois modes, bornes, détection du chevauchement | unitaires : R1 N+pas, R2 sur longueur, R3 pas sur longueur (N entier), R4 pas ≤ 0, N hors 1..100 refusés, R5 chevauchement signalé, R6 inversion |
| R-b | `features/repeat.py` + `_api/repeat.py` : copies, assemblages, quincaillerie, ensemble, une transaction | intégration FreeCAD : R7 trois barreaux entre deux traverses = 3 × 2 assemblages, R8 annulation en un bloc, R9 ensemble : copies membres, R10 liste de débit : N+1 lignes regroupées |
| R-c | commande, panneau, aperçu, icône, traductions | GUI hors écran : R11 aperçu = copies créées, R12 refus affiché |
| R-d | recette manuelle `docs/recette/` + captures | — |

## 6. Questions à jv (★ = recommandé)

- **Q1 — Nature.** ★ A : copies ordinaires, aucun objet « Répétition » gardé (comme les gabarits,
  ADR 0010) ; B : objet persistant dont N et le pas se modifient après coup (FreeCAD interdit de
  créer/supprimer des pièces pendant un recalcul, donc copies virtuelles non usinables) ;
  C : comme A + commande « Changer le nombre » plus tard grâce à `RepeatGroup`.
  ★ A maintenant, C dans un lot ultérieur.
- **Q2 — Modes.** ★ Les trois (nombre+pas, nombre sur une longueur, pas sur une longueur) ; ou
  seulement nombre+pas.
- **Q3 — Direction.** ★ Axe X/Y/Z global + « Inverser » ; ou aussi les axes de la pièce quand
  elle est tournée ; ou choix d'une arête.
- **Q4 — Assemblages.** ★ Recréés comme au § 3 (internes et vers les pièces non sélectionnées) ;
  ou pièces seules (plus simple, mais il faut tout réassembler à la main).
- **Q5 — Ensemble.** ★ Copies membres de l'ensemble de la source, sans redistribution au
  redimensionnement ; ou aussi les mettre dans un sous-ensemble « Répétition ».
- **Q6 — Cotes liées.** ★ Copies indépendantes ; ou cotes (section, longueur) liées à la source
  par expressions natives : changer la source change toutes les copies. Lien plus fragile (une
  copie modifiée à la main casse la liaison).
- **Q7 — Maximum.** ★ 100 copies ; autre valeur ?
- **Q8 — Nom.** ★ « Barreau 2 », « Barreau 3 »… (suit le renommage de la source seulement à la
  création) ; ou « Barreau (2/5) ».
