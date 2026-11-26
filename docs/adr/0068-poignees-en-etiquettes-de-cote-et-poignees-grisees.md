# ADR 0068 — Poignées en étiquettes de cote, poignées impossibles grisées

- Statut : **proposé** (jv a demandé les poignées grisées et un nouveau design le 2026-11-24, puis a
  choisi la maquette I « étiquette de cote » parmi trois séries de trois propositions ; après
  l'avoir essayée le 2026-11-25 (étiquettes qui se superposent, « trop difficile de comprendre
  quelle flèche correspond à quoi »), il a choisi la maquette K « une étiquette par cote »)
- Date : 2026-11-24 (numéro 0067 pris par une autre branche en cours)
- ADR liés : [0021](0021-deplacement-a-la-souris-avec-aimantation.md) (flèches et poignées), [0038](0038-ensemble-a-la-souris.md)
  (poignées d'un ensemble), [0019](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md) (« Cotes fixes »)

## Contexte

Les poignées de taille étaient une tige orange terminée par un cube (doubles flèches pour un
ensemble). Une cote qui ne se tire pas (pièce verrouillée, pièce en bois, épaisseur d'un panneau,
formule de l'utilisateur) n'avait **pas** de poignée : rien ne disait qu'elle existait ni
pourquoi elle manquait. jv a demandé (2026-11-24) :

- qu'une poignée impossible soit **grisée**, avec une infobulle au survol qui dit **pourquoi** ;
- un autre design des poignées, « plus élaboré, plus design ».

## Décision

1. **Une étiquette par cote** (maquette K, remplace la maquette I) : chaque cote a une seule
   étiquette, une pastille blanche bordée de la couleur de son axe (rouge, vert, bleu, comme le
   trièdre et les flèches), qui porte à gauche son **nom court** en blanc sur cette couleur
   (« Long. », « Larg. », « Ép. » pour une pièce ; « Larg. », « Prof. », « Haut. » pour un
   ensemble) et à droite sa **valeur** (au millimètre, au dixième sinon), mise à jour pendant
   qu'on tire. Elle est reliée par un trait au rond de la face **tournée vers la caméra**
   (`badge_place.facing_ends`) ; la face d'en face n'a qu'un rond de la même couleur, qui se tire
   aussi. Chaque rond porte une petite double flèche blanche dans la direction de son axe à
   l'écran (`badge_place.screen_angle`, au pas de 15° ; aucune sur un rond grisé ni sur un axe
   vu de bout). Le rond n'est pas au milieu de la face mais décalé d'un quart de la largeur (faces
   de bout) ou de la longueur vers le début (`core.magnet.handle_point`) : le milieu tombe sur le
   tracé de la flèche de déplacement de son axe, et les deux ronds d'un axe restent alignés sur
   une parallèle à cet axe (jv, 2026-11-26) ; un ensemble suit la même règle
   (`furniture_layout`). Une étiquette ne couvre ni une autre étiquette, ni un rond, ni une
   flèche de déplacement : elle recule le long de son axe (`badge_place.spread`), du recul qui
   touche le moins si rien n'est libre. Au survol d'une poignée, son rond grossit, son étiquette
   a un halo et **la face qui va bouger s'allume** en transparence, à la couleur de l'axe. Une cote
   impossible est grise, avec un cadenas après la valeur. Le même dessin sert à la pièce et à
   l'ensemble (fin des doubles flèches et des cubes).
2. L'étiquette est une image peinte par Qt (lissage, ombre, halo : `gui/drag/badges.py`) et posée
   par un `SoImage` (taille fixe à l'écran, multipliée par le rapport de pixels de l'écran) ;
   le rond de chaque face est peint de même (`knob_pixels`), à la couleur exacte de
   son étiquette ; les images sont gardées en cache (vidé au retrait du glissement :
   `clear_badge_cache`).
   `overlay.py` reste le seul module qui importe pivy. La cote est écrite par `core.text.mm_text`,
   commun à l'étiquette et à l'infobulle d'épaisseur.
3. **Poignées impossibles** : `DragLimits.locked_sizes` donne, pour chaque axe qui ne se tire
   pas, sa raison traduite (`core.magnet.Blocker` : titre, explication, piste « → … »), choisie par
   `features/drag_blockers.py` dans cet ordre : pièce en bois (cotes du dessin ; membre d'un ensemble, elle est toujours
   « Cotes fixes »), « Cotes fixes »,
   formule sur la cote, formule sur la position de l'axe, épaisseur d'un panneau. La disposition
   (`Layout.locked`) les dessine grisées ; leur clé (`locked…`) est survolable mais jamais saisie
   (`parse_key` la refuse). Un clic dessus est consommé sans rien faire (la pièce reste
   sélectionnée).
4. **Infobulle** : au survol d'une poignée grisée, le filtre d'évènements montre un `QToolTip`
   (titre en gras, explication, piste en italique, texte échappé) et le retire quand la souris
   la quitte, quand la souris sort de la vue et quand la sélection change. Une traduction fautive
   (champ `{…}` inconnu ou mal formé) retombe sur le texte français (`features.i18n.translated`).
5. **Saisie** : une poignée se saisit par le rond de sa face, par son trait et par toute son
   étiquette (segment horizontal, tolérance de sa demi-hauteur : `PixelTarget.radius`). À distance
   égale, une flèche l'emporte sur une étiquette qui la chevauche (ordre de `pixel_targets`).
   Une poignée grisée ne se cherche qu'après les flèches, les poignées et les anneaux (`key_at`) :
   elle ne cache jamais ce qui se tire. Un **clic** sur l'étiquette (bouton relâché à moins de
   4 pixels : `states.BadgePressed`) ne tire rien : il met le curseur dans le champ de la cote
   du panneau (`size_fields` donné à `PanelDrag`, `PanelContext.edit_size`), valeur sélectionnée, pour
   la taper directement (jv, 2026-11-26) ; glisser depuis l'étiquette tire la poignée.
6. Les poignées grisées n'apparaissent que là où les poignées apparaissent (panneau de la pièce
   ouvert) ; hors panneau, rien ne change.

## Conséquences

- On voit d'un coup d'œil quelle cote chaque poignée change, et ce qui est bloqué avec la raison.
- Les étiquettes sont plus grandes que les anciens cubes : elles sont posées plus loin de la face
  (1,9 unité de poignée, plus si elles se touchent) pour ne pas la couvrir.
- La face qui porte l'étiquette suit la vue : la disposition est recalculée à chaque mouvement
  de la souris et redessinée si elle change.
- L'aperçu de la pièce pendant qu'on tire l'épaisseur d'une pièce assemblée (pièce qui se
  déplace au lieu de grandir) n'est pas traité ici : la PR #264 (ADR 0060) le corrige.
- Un ensemble n'a pas encore de poignée impossible (ses cotes refusées le restent par le message
  près de la souris, ADR 0038).
