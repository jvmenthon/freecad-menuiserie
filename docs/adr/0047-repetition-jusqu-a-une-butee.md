# ADR 0047 — Répétition jusqu'à une butée : longueur calculée, suivie, épaisseur déduite ou non

- Statut : **accepté** (jv, 2026-11-10 : Q1 à Q3 et option « Déduire l'épaisseur de la pièce »)
- Date : 2026-11-10
- Spécification : [docs/specs/repetition.md](../specs/repetition.md), § 10 « Jusqu'à une butée »
- ADR liés : [0043 — Répétition](0043-repetition-objet-de-cotes-et-copies-liees.md),
  [0045 — Répétition en grille](0045-repetition-en-grille.md),
  [0003 — Contrat de persistance](0003-contrat-de-persistance.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md)

## Contexte

Dans les modes « nombre sur une longueur » et « pas sur une longueur », l'utilisateur saisit la
longueur à remplir. jv veut qu'elle soit **calculée jusqu'à une butée** (face, sommet ou pièce
entière choisis dans la vue 3D), qu'elle **suive** la butée si elle bouge, et pouvoir **ne pas
déduire l'épaisseur** de la pièce répétée.

## Décision

1. **Q1 — la longueur est calculée.** C'est la distance, sur l'axe et dans le sens de la répétition,
   entre la face de départ des sources (leur bas sur l'axe, leur haut si `Reverse`) et la butée.
   Elle remplace la longueur saisie ; l'utilisateur garde le choix de ce qui est fixé (le nombre en
   `CountOnSpan`, le pas en `StepOnSpan`), l'autre se calcule. En `CountAndStep` il n'y a pas de
   longueur : une butée est refusée (ou retirée par `edit_repeat` sans `stops`).
2. **Q2 — la butée.** Face (`FaceN`), sommet (`VertexN`) ou pièce entière (sous-élément vide) d'un
   objet du document, éventuellement hors du conteneur. On prend son bord le plus proche dans le sens
   de la répétition (minimum sur l'axe, maximum si `Reverse`) dans le repère du conteneur des
   sources : une face oblique ou une pièce donne donc son point le plus proche. Refus traduits : butée
   derrière l'original (distance ≤ 0), plus proche que l'épaisseur (case cochée), pièce répétée, une
   de ses copies ou un membre d'un ensemble source, autre document, objet sans forme, sous-élément
   absent, sous-élément qui n'est ni une face ni un sommet.
3. **Q3 — la longueur suit la butée.** `Repeat` gagne un `execute` (sans forme) qui relit les butées
   à chaque recalcul et réécrit `Span` et, en `CountOnSpan`, `Step` (sorties de la répétition, comme
   l'exception de l'ADR 0020) ; les copies, liées à `Step` par expression, suivent. Les expressions
   natives ne peuvent pas lire une face : un calcul dans `execute` est le « mécanisme existant »
   étendu (même principe que `repeat_follow` : l'API écrit la structure, le recalcul ne fait que
   suivre). **Limite documentée** : un recalcul n'écrit pas la structure du document ; en
   `StepOnSpan`, le nombre de copies ne change qu'à l'édition de la répétition (un avertissement
   le dit). Butée et « Suivre le redimensionnement » se contredisent (deux longueurs calculées) :
   refus.
4. **Option « Déduire l'épaisseur de la pièce »** (`RepeatParams.deduct_thickness`, propriété
   `DeductThickness`, défaut vrai). Cochée, c'est le comportement des modes sur une longueur
   depuis l'ADR 0043 : place utile = longueur − cote des sources, la dernière copie arrive **à
   fleur** de la butée. Décochée : place utile = longueur, la dernière copie **commence** à la
   butée et est en collision avec elle (avertissement non bloquant dans le panneau). S'applique à
   la longueur saisie comme à la butée. « Suivre le redimensionnement » en tient compte.
5. **Grille (ADR 0045).** Une butée par axe : `Stop`, `Stop2`, `Stop3` (`App::PropertyLinkSubGlobal`,
   hors conteneur permis) et `StopLabel*` (libellé, lecture seule). `StopHolders`
   (`PropertyLinkListGlobal`) garde les conteneurs de butées qui ne contiennent pas la répétition,
   pour que déplacer un conteneur recalcule la longueur (sans eux, le lien vers la pièce seule ne
   verrait pas le déplacement de son conteneur) ; ceux qui contiennent la répétition sont exclus
   (cycle).
6. **Butée supprimée.** FreeCAD vide le lien ; `execute` voit un `StopLabel` sans lien, avertit
   (traduit, une fois) et vide le libellé : la répétition garde `Span` (dernière valeur) et repasse
   en longueur saisie. Aucune erreur.
7. **API.** `make_repeat(..., stops=)` et `edit_repeat(..., stops=)` (`Stop(obj, sub)`) ; `stops=None`
   garde les butées de la répétition en édition. `AxisRepeat.span` d'un axe à butée est une valeur
   positive de départ, remplacée.
8. **Persistance (ADR 0003).** Propriétés facultatives (`Stop*`, `StopLabel*`, `StopHolders`,
   `DeductThickness`) ajoutées à l'ouverture d'un document plus ancien ; `Version` reste 1. Un
   document existant a la case cochée : rien ne change.

## Conséquences

- `Repeat` n'est plus tout à fait inerte : son `execute` est un no-op sans butée.
- `Repeat` dépend de sa butée (lien) : supprimer la butée vide le lien sans casser le document.
- Panneau : bouton « Butée… » par axe, sélection par un observateur `Gui.Selection` posé le temps
  du choix et retiré à la fermeture (ADR 0007), longueur calculée en lecture seule, case d'épaisseur.
- Limites : un document dont la butée est une face qui change de numéro (topologie) la perd ; le
  sommet et la face oblique ne donnent que leur bord le plus proche (boîte englobante).
