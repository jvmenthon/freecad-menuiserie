# ADR 0068 — Poignées en étiquettes de cote, poignées impossibles grisées

- Statut : **proposé** (jv a demandé les poignées grisées et un nouveau design le 2026-11-24, puis a
  choisi la maquette I « étiquette de cote » parmi trois séries de trois propositions)
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

1. **Étiquette de cote** (maquette I) : chaque poignée est une pastille arrondie posée devant le
   milieu de sa face, reliée à lui par un trait. Elle porte une double flèche dans l'axe de la
   cote (orientée comme l'axe à l'écran, au pas de 5°) et la **valeur de la cote** qu'elle change
   (au millimètre, au dixième sinon), mise à jour pendant qu'on tire. États : normale (orange),
   survolée (jaune, halo), impossible (gris clair, cadenas à la place de la double flèche),
   impossible survolée (bord plus sombre, halo gris). Le même dessin sert à la pièce et à
   l'ensemble (fin des doubles flèches et des cubes).
2. L'étiquette est une image peinte par Qt (lissage, ombre, halo : `gui/drag/badges.py`) et posée
   par un `SoImage` (taille fixe à l'écran, multipliée par le rapport de pixels de l'écran) ;
   les images sont gardées en cache (vidé au retrait du glissement : `clear_badge_cache`).
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
5. **Saisie** : une poignée se saisit par le milieu de sa face, par son trait et par toute son
   étiquette (segment horizontal, tolérance de sa demi-hauteur : `PixelTarget.radius`). À distance
   égale, une flèche l'emporte sur une étiquette qui la chevauche (ordre de `pixel_targets`).
6. Les poignées grisées n'apparaissent que là où les poignées apparaissent (panneau de la pièce
   ouvert) ; hors panneau, rien ne change.

## Conséquences

- On voit d'un coup d'œil quelle cote chaque poignée change, et ce qui est bloqué avec la raison.
- Les étiquettes sont plus grandes que les anciens cubes : elles sont posées plus loin de la face
  (1,9 unité de poignée) pour ne pas la couvrir.
- L'orientation de la double flèche suit la vue à chaque mouvement de la souris (la disposition
  est recalculée et redessinée si un angle change de plus d'un pas).
- Un ensemble n'a pas encore de poignée impossible (ses cotes refusées le restent par le message
  près de la souris, ADR 0038).
