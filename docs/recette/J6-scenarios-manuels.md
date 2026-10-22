# J6 — Scénarios de recette manuelle (partie aperçu et rotation, J6c)

Critères V1 à V7 de la [spécification J6](../specs/J6-interface.md) (réponses de jv du
2026-10-22 : trois boutons X, Y, Z), à dérouler à la main sur **FreeCAD 1.1.4** (Windows) et, si
possible, **FreeCAD 1.0**, atelier installé depuis la branche du lot. Les parties accrochage à la
sélection (T1 à T9) seront ajoutées par le lot J6d.

V1 à V7 sont aussi vérifiés hors écran par `tests/gui/verifier_atelier.py`
(`verifications_apercu.py`) et, côté document, par `tests/integration/test_apercu_rotation.py`.

## Aperçu et rotation (J6c)

Nouveau document, atelier **Menuiserie**, rien de sélectionné.

| N° | Action | Résultat attendu |
|---|---|---|
| 1 | Bouton **Pièce de bois**. | La pièce (800 × 200 × 22) apparaît **semi-transparente** (60 %), texture et couleur du chêne visibles ; panneau « Nouvelle pièce de bois ». |
| 2 | Lire l'ordre des groupes du panneau, de haut en bas. | **Matériau**, puis **Dimensions finies** (et « Surcotes de débit »), puis **Identification**, puis **Position** avec trois boutons **X**, **Y**, **Z** (icônes en couleur, infobulles « Quart de tour autour de l'axe X du document… »). |
| 3 | Changer la longueur, le matériau, le sens du fil. | L'aperçu suit chaque saisie, toujours semi-transparent. |
| 4 | Cliquer **X**. | La pièce fait un quart de tour autour de l'axe X du document (elle se met sur chant) et reste posée sur le plan XY, coin à l'origine. Le sens du fil et la texture tournent avec la pièce ; `GrainDirection` est inchangé dans l'éditeur de propriétés. |
| 5 | Cliquer quatre fois sur **Y**, puis quatre fois sur **Z**. | Chaque série de quatre clics ramène la pièce à sa position de départ. Les 24 orientations sont atteignables en combinant les trois boutons. |
| 6 | Saisir le repère « E2 », **OK**. | Pièce opaque (transparence d'origine rétablie), nommée « E2 » dans l'arborescence. |
| 7 | *Édition › Annuler*. | La pièce disparaît ; une seule entrée « Créer une pièce de bois » (aucune pour la rotation ni la transparence). *Rétablir* : pièce, orientation et transparence d'origine reviennent. |
| 8 | **Pièce de bois**, cliquer **Z**, **Annuler** (bouton du panneau). | Aucune pièce dans l'arborescence ; *Édition* ne propose aucune annulation nouvelle. |
| 9 | Double-clic sur une pièce existante, cliquer **Z**. | La pièce tourne **sur place** : son centre ne bouge pas ; affichage non transparent. Si elle porte un assemblage, sa pièce usinée suit. **Annuler** : cotes, position et repère d'origine. |
| 10 | Faire de la pièce un membre d'un ensemble (**Ajouter à l'ensemble**), puis double-clic sur elle. | Boutons X, Y, Z **grisés** ; infobulle « Cette pièce suit l'ensemble « … » : tournez-la avec Std Transform après l'avoir retirée de l'ensemble. » |
| 11 | Sur une pièce libre, poser une expression sur `Placement.Base.x` (`10 mm`), double-clic. | Boutons grisés, infobulle expliquant que la position est pilotée par une expression. |
| 12 | Fermer le panneau, ouvrir *Édition › Préférences*. | Aucune rubrique ni réglage créé par l'aperçu ; la sélection de la vue 3D n'est ni filtrée ni modifiée. |
