# Configuration de l'atelier : inventaire des points configurables

Annexe de [configuration-de-l-atelier.md](configuration-de-l-atelier.md). Relevé du code de `main`
(2026-11-25) et des PR ouvertes #247 (plans cotés), #250 (charnières) et #279 (poignées),
regroupé par fonctionnalité.

Légende de la colonne « Avis » :

- **R** : réglage utile, à proposer dans la page de préférences ;
- **E** : réglage possible pour un utilisateur averti (groupe « Avancé », replié) ;
- **M** : mémoire silencieuse du dernier choix, sans place dans la page ;
- **—** : règle de l'atelier ou limite technique, à ne pas exposer (sécurité, géométrie, norme).

Les cotes « 0 = automatique » des assemblages restent automatiques : ce sont les **règles du calcul
automatique** qui deviennent réglables, pas la valeur de chaque assemblage.

## 1. Pièce de bois (création)

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Dimensions d'une pièce neuve | 800 × 200 × 22 mm | `features/wood_part_schema.py` | R |
| Matériau d'une pièce neuve | premier de la bibliothèque | `features/wood_part_schema.py` | R |
| Sens du fil d'une pièce neuve | d'après le matériau | `features/wood_part_schema.py` | R |
| Surcotes de débit, massif | 20 / 5 / 0 mm | `core/part_model.py` | R |
| Surcotes de débit, panneau | 0 / 0 / 0 mm | `core/part_model.py` | R |
| Nom d'une pièce neuve | « Pièce de bois » | `features/part_names.py` | E |
| Marge de rabotage minimale du massif | 3 mm | `core/cutlist/_model.py` | E |
| Cotes minimale et maximale | 0,1 mm, 20 m | `core/_validation.py` | — |

## 2. Matériaux, épaisseurs, formats

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Épaisseurs personnelles (ajout, suppression) | `dimensions.json` | `features/user_dimensions.py` | R |
| Formats de panneaux personnels | 2500 × 1250, 2440 × 1220, 3050 × 1525 + perso | `core/user_dimensions.py` | R |
| Matériaux personnels | `materiaux.json` (édition à la main) | `features/library.py` | R (éditeur à part, hors page) |
| Bornes des fichiers (taille, nombre, densité) | 64 Kio, 50, 500… | `core/materials/` | — |

## 3. Finition des chants (profils d'arête)

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Arête cassée sur les pièces neuves | non (nouveau) | — | R |
| Taille de l'arête cassée | 1 mm | `core/edges/_families.py` | R |
| Profil proposé à l'ouverture du panneau | quart de rond, 1 mm | `features/edge_profile.py` | R |
| Vue du panneau (patron / boîte) | dernier choix | `gui/task_panels/edge_targets.py` | M (existe) |
| Angles acceptés, taille maximale | 30° à 150°, moitié de la pièce | `core/edges/` | — |

## 4. Assemblages

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Jeu de mortaise (tenon-mortaise) | 2 mm | `core/joints/mortise_tenon.py` | R |
| Mortaise débouchante par défaut | non | `core/joints/mortise_tenon.py` | R |
| Jeu de rainure | 1 mm | `core/joints/tongue_groove.py` | R |
| Longueur de languette | 10 mm | `core/joints/tongue_groove.py` | R |
| Rainure débouchante par défaut | oui | `core/joints/tongue_groove.py` | R |
| Feuillure débouchante par défaut | oui | `core/joints/rabbet.py` | R |
| Jeu de fond des tourillons | 1 mm | `core/joints/dowels.py` | R |
| Entraxe maximal des tourillons automatiques | 128 mm | `core/joints/dowels.py` | E |
| Angle de queue d'aronde | 10° | `core/joints/dovetail.py` | R |
| Queues sur la pièce hôte par défaut | non | `core/joints/dovetail.py` | E |
| Faux tenons : liste de tailles ou taille libre (mineur Q2) | liste | `features/joints/slots.py` | R |
| Faux tenons, biscuits : jeu, premier au bord, écart maximal | 1 mm, 50 mm, 150 mm | `core/joints/slots/_params.py` | E |
| Écart « pièces proches » qui ouvre la fenêtre Déplacer / Agrandir | 20 mm | `core/near_gap.py` | E |
| Matière minimale entre usinages, au fond d'un perçage | 2 mm, 3 mm | `core/joints/_base.py` | — |
| Angle maximal d'aronde, biais maximal | 30°, 70° | `core/joints/_base.py`, `core/geometry.py` | — |

## 5. Quincaillerie

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Catalogue personnel | `quincaillerie.json` | `features/hardware.py` | R (dossier de l'atelier) |
| Pieds : tige, embase, hauteur, logement | Ø10, Ø50, 15 mm, 12 mm | `core/joints/feet.py` | E |
| Pieds : distance au bord, écart maximal | 50 mm, 800 mm | `core/joints/feet.py` | E |
| Matière des pieds | plastique | `core/joints/feet.py` | E |
| Coulisses : longueurs proposées | 250 à 600 mm, pas de 50 | `core/joints/slides.py` | E |
| Coulisses : épaisseur, hauteur, perçage | 12,7 mm, 45 mm, Ø5 × 12, 3 trous | `core/joints/slides.py` | E |
| Taquets (système 32) : pas, Ø, profondeur | 32 mm, Ø5, 12 mm | `core/joints/shelf_pins/_params.py` | R |
| Taquets : colonnes au bord, marge aux bouts, saillie | 37 mm, 64 mm, 7 mm | `core/joints/shelf_pins/_params.py` | E |
| Taquets : percer le montant opposé, poser les taquets | oui, oui | `core/joints/shelf_pins/_params.py` | E |
| Charnières à cuvette : réglages par défaut (PR #250) | voir la PR | `core/joints/` | E (après fusion) |
| Premier trou des coulisses, pas du système 32 | 37 mm, 32 mm | `core/joints/slides.py` | — (norme) |

## 6. Ensembles et gabarits

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Caisson : L × P × H | 600 × 400 × 720 mm | `core/templates/carcass.py` | R |
| Caisson : épaisseur, fond, feuillure du fond | 18, 8, 10 mm | `core/templates/carcass.py` | R |
| Caisson : nombre d'étagères, jeu des étagères | 1, 1 mm | `core/templates/carcass.py` | E |
| Fermer le caisson : hauteur, fond mince, recul de rainure | 720, 8, 10 mm | `core/templates/closing_params.py` | E |
| Pièce intérieure d'un ensemble : reste / suit | reste en place | `features/furniture.py` | E |
| Palette des rôles des gabarits (PR #162) | esthétique ; daltonien, perso | à venir | R (avec les gabarits) |
| Dossier des gabarits personnels | `<dossier de l'atelier>/gabarits/` | à venir | R (dossier de l'atelier) |

## 7. Répétition

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Pas proposé | 100 mm | `features/repeat_props.py` | E |
| Copier les assemblages | oui | `core/repeat/_model.py` | E |
| Déduire l'épaisseur, suivre la taille | oui, non | `core/repeat/_model.py` | E |
| Nombre de copies maximal | 100 | `core/repeat/_model.py` | — |

## 8. Souris, aimantation, rotation, alignement

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Tolérance de l'aimant | 10 px | `gui/drag/geometry.py` | R |
| Tolérance de saisie des anneaux | 8 px | `gui/drag/rings.py` | E |
| Pas de rotation aimanté | 15° | `core/rotation/_turn.py` | R |
| Aimant des flèches des champs (coplanarité) | 1 mm | `core/magnet/_coplanar.py` | E |
| Longueur des flèches, taille des étiquettes (PR #279) | 80 px ; 66 × 24 px, texte 13 px | `gui/drag/` | E (taille d'affichage, une seule échelle) |
| Couleurs : poignées, guides, fantôme, refus, axes X/Y/Z | orange, magenta, bleu, rouge, R/V/B | `gui/drag/geometry.py` | E (thème ; mode daltonien) |
| Déplacement minimal d'une copie | 0,01 mm | `gui/drag/copy_rules.py` | — |

## 9. Affichage

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Pièce en transparence pendant l'édition | oui, 60 % | `core/display_layers.py` | R (oui / non) ; E (taux) |
| Transparence et teinte de la sélection | 50 %, bleu clair | `core/display_layers.py` | E |
| Double flèche du sens du fil : couleur, transparence | orange, 70 % | `gui/task_panels/part_axes_drawing.py` | E |
| Textures des matériaux affichées | toujours | `gui/textures.py` | R (oui / non, pour les grosses scènes) |
| Couleur des tourillons, pieds, taquets | hêtre, plastique, acier | `gui/view_providers/joint.py` | — |

## 10. Panneau « Structure »

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Ouverture automatique du panneau | oui, sauf s'il a été fermé | `core/structure_autostart.py` | R |
| Panneau fermé par l'utilisateur | dernier choix | `gui/structure_preferences.py` | M (existe) |

## 11. Liste de débit et exports

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Préfixe des repères | « M » | `core/cutlist/_marks.py` | R |
| Format du CSV (français, international) | dernier choix | `gui/commands/cutlist.py` | M (existe) |
| Marge du PDF | 10 mm | `gui/cutlist_pdf.py` | E |
| Vignettes dans la liste | oui, 120 × 80 px | `core/cutlist/_thumbnail.py` | E |
| Dossier d'export | dossier du document | `gui/commands/cutlist.py` | R |

## 12. Plans cotés (PR #247)

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Format de feuille | A3 | plans cotés | R |
| Échelles proposées | 5:1 à 1:100 | plans cotés | E |
| Marges, écart entre vues | 20 mm, 30 mm | plans cotés | E |
| Écartement de la vue éclatée | 0,6 | plans cotés | E |
| Cartouche : modèle préféré | ISO 7200 | plans cotés | R |
| Cartouche : nom de l'atelier, auteur | absent | à venir | R (identité de l'atelier) |

## 13. Stockage et projets

| Point | Valeur actuelle | Où | Avis |
|---|---|---|---|
| Dossier de l'atelier | `<données FreeCAD>/Menuiserie/` | `features/library.py` | R |
| Chemin de la bibliothèque de matériaux | `UserLibraryPath` | `features/library.py` | R (repris par le dossier, Q3) |
| Dossier des projets (« Nouveau projet ») | à venir | — | R |
| Nom de fichier d'un projet : année, client | `2026-Client-nom.FCStd` | à venir | E |

## Synthèse

- **R (page de préférences)** : environ 40 réglages ; le lot 1 en reprend une partie (lignes ★ du § 3 de la spec).
- **E (groupe Avancé)** : environ 30 réglages, surtout les règles des valeurs automatiques
  (quincaillerie, faux tenons, gabarits) et l'affichage.
- **M** : 3 mémoires existantes (vue des arêtes, format CSV, panneau Structure), qui restent hors
  de la page.
- Points nouveaux par rapport à l'ADR 0031 : quincaillerie, caisson et « Fermer le caisson »,
  répétition, Structure, textures, plans cotés (format, cartouche, identité de l'atelier).
