# ADR 0050 — Registre de gabarits et panneau généré

- Statut : **proposé** (décisions de jv du 2026-11-11 : socle d'abord, panneau essentiel + options
  avancées au repli mémorisé)
- Date : 2026-11-11
- Spécification : [docs/specs/gabarits-socle-et-personnels.md](../specs/gabarits-socle-et-personnels.md), § 3
- ADR liés : [0010 — Gabarits générateurs](0010-gabarits-generateurs.md) (inchangé),
  [0031 — Configuration de l'atelier](0031-configuration-de-l-atelier.md) (même idée de catalogue)

## Contexte

Chaque gabarit coûte aujourd'hui un module de règles, une commande et un panneau écrit à la main.
Avec les meubles prévus (Bibliothèque, Table, Cadre-porte, Tiroir) et les gabarits personnels, ces
panneaux divergeraient et la barre d'outils se chargerait (problématiques P1 à P3, P6 et P7).

Options :

1. **Un panneau et une commande par gabarit** : souple, mais coûteux et incohérent à la longue.
2. **Registre déclaratif + panneau généré + galerie** : chaque gabarit décrit ses paramètres ; un seul
   panneau et une seule commande les servent. Retenue.

## Décision

1. `core/templates/_registry.py` tient un registre figé de `TemplateEntry` (identifiant stable,
   libellé, catégorie, vignette, `fields`, `presets`, `build_params`, `layout`). Python pur.
2. `FieldSpec` décrit un champ : type (`length`, `count`, `choice`, `material`, `flag`), bornes,
   défaut, libellé, infobulle, `advanced`, `group`, `hidden_if`. Les règles entre plusieurs champs
   restent dans les `…Params` du gabarit ; leur refus cite le champ.
3. `TemplateTaskPanel` (seul panneau de gabarit) se construit depuis `fields` : taille usuelle,
   essentiel, options avancées repliables, état du repli mémorisé par gabarit
   (`Mod/Menuiserie/Templates/<id>/AdvancedOpen`), aperçu en direct dans une transaction.
4. Une commande `Menuiserie_Template` ouvre une galerie à vignettes par catégorie ;
   `Menuiserie_Carcass` reste comme raccourci.
5. Les gabarits personnels (ADR 0051) passent par le même panneau, leurs paramètres exposés étant
   traduits en `FieldSpec`.

## Conséquences

- Un nouveau gabarit intégré = un module `core` testé sans FreeCAD + une déclaration + une icône.
- Le panneau du caisson est migré ; ses critères K1 à K7 ne changent pas.
- Contrepartie : un affichage très particulier (schéma interactif) ne rentre pas dans un panneau
  généré ; il faudrait alors un champ de type nouveau, ajouté au registre une fois pour tous.
