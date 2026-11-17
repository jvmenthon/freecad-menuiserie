# ADR 0052 — Prérequis d'une commande dans son infobulle

- Statut : **accepté** (jv, 2026-11-12 : « laisser grisé », « uniquement prérequis », même texte
  que le bouton soit grisé ou non)
- Date : 2026-11-12
- Issue : #221 (revue UX de novembre 2026, point A3)
- ADR liés : [0007](0007-compatibilite-avec-les-autres-ateliers.md),
  [0048](0048-selection-par-ensemble-dans-la-vue-3d.md) (abandonné le 2026-11-13)

## Contexte

Les commandes d'assemblage, de quincaillerie, d'ensemble, de répétition, « Définir une distance »
et « Convertir en pièce en bois » demandent une sélection faite **avant** le clic. Sans elle, le
bouton est grisé et son infobulle décrit la commande, pas ce qui manque : un débutant voit une
barre d'outils grise sans savoir quoi sélectionner.

## Options

1. **Bouton grisé, prérequis dans l'infobulle.** Retenue par jv. L'infobulle de chaque commande à
   sélection se termine par une ligne « Prérequis : … ». Le texte est fixe : il ne dit pas
   « indisponible » et reste le même quand le bouton est actif. Le grisé garde son rôle (voir d'un
   coup d'œil ce qui s'applique à la sélection).
2. **Commandes toujours actives, explication au clic** (première version de la PR #245) : le
   bouton ne renseigne plus sur la sélection et une boîte s'ouvre sur un clic raté. Rejetée par jv.
3. **Infobulle réécrite selon la sélection** (« Indisponible : … » seulement quand le bouton est
   grisé) : réécriture de l'action Qt à chaque rafraîchissement, pour un texte que jv ne veut pas.
   Rejetée.
4. **Panneau de choix guidé** (« choisissez la première pièce, puis la seconde ») : un panneau et
   un mode de sélection par commande. Reporté ; l'option 1 ne l'empêche pas.

## Décision

- `IsActive` et `Activated` ne changent pas : une commande reste grisée tant que sa sélection ne
  convient pas.
- Chaque commande à sélection fixe `PREREQUISITE`, une phrase de `gui/commands/hints.py` qui
  décrit la sélection attendue (« deux pièces sélectionnées (Ctrl+clic sur chacune…) »). Les
  phrases citent Ctrl+clic pour ajouter une pièce à la sélection.
- `tool_tip` (socle des commandes) compose l'infobulle : le texte de la commande, une ligne vide,
  puis « Prérequis : … ». Une commande sans prérequis garde son infobulle telle quelle.
- La barre d'état, qui reprend l'infobulle au survol du menu *Menuiserie*, montre le même texte.

## Conséquences

- Un clic sur un bouton grisé ne fait toujours rien : il faut survoler le bouton pour lire le
  prérequis.
- L'infobulle d'une commande à prérequis est traduite par l'atelier au moment où la commande est
  enregistrée (les deux textes sont marqués pour la traduction), et non plus par FreeCAD : après
  un changement de langue, elle suit au redémarrage de FreeCAD.
- Aucun effet hors de l'atelier (ADR 0007).
- Une nouvelle commande à sélection doit fixer `PREREQUISITE` ; un test statique le contrôle
  (`tests/unit/test_selection_attendue.py`).
