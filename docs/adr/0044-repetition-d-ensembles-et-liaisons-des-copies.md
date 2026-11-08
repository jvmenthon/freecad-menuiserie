# ADR 0044 — Répétition d'ensembles : liaisons des copies, rangées, « Suivre le redimensionnement »

- Statut : **proposé** (lot R-b3 ; règle de liaison proposée à jv)
- Date : 2026-11-08
- Spécification : [docs/specs/repetition.md](../specs/repetition.md), § 2 bis et § 3.4
- ADR liés : [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi des pièces par expressions natives](0009-suivi-par-expressions-natives.md),
  [0019 — Rangées de pièces](0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md),
  [0043 — Répétition](0043-repetition-objet-de-cotes-et-copies-liees.md)

## Contexte

Une copie de répétition est liée à sa source par des expressions (ADR 0043). Quand la source est
membre d'un ensemble, ou est elle-même un ensemble, deux mécanismes veulent écrire dans la même
propriété : les liaisons de l'ensemble (ADR 0009, `FurnitureBindings`) et les expressions de la
copie. L'ADR 0009 traite déjà une expression étrangère comme une formule de l'utilisateur (jamais
écrasée, avertissement à chaque redimensionnement), ce qui serait faux ici : les copies n'ont pas
de formule de l'utilisateur. Il faut aussi que la copie compte dans les rangées de ses voisines
(ADR 0019) sans créer de cycle : la source citerait l'épaisseur de la copie, qui est celle de la
source.

## Décision

1. **Copie liée d'une pièce membre** : elle entre dans l'ensemble de sa source avec les mêmes
   options (mode, options « fixe », verrou). Elle suit sa source, qui suit l'ensemble : elle n'a
   donc **aucune liaison d'ensemble** (`Member.linked` dans `core.furniture`). Elle reste un
   membre des rangées de ses voisines (sa géométrie compte), mais n'a ni règle ni liaison, ni
   avertissement. Son épaisseur, citée par une voisine, est toujours **figée en constante**
   (mécanisme de l'ADR 0019 pour les cycles) : la source citerait sinon la voisine qui cite la
   copie qui cite la source. « Relier les pièces » la laisse intacte ; la figer a la limite
   connue de l'ADR 0019 (relier de nouveau après un changement d'épaisseur de la source, ce que
   fait déjà le changement d'épaisseur par l'API, qui l'applique aux copies de la pièce).
2. **Copie dissociée** : ses expressions et ses propriétés de copie sont retirées, puis l'ensemble
   est relié (`rebind`) : elle retrouve des liaisons normales, d'après ses options.
3. **Copie d'ensemble** : un nouvel ensemble (sous-ensemble du même parent, comme copie liée au
   sens du point 1) dont `Width`, `Depth`, `Height` et `Origin` sont des expressions sur
   l'ensemble source et sur la répétition. Chaque membre est copié dedans, récursivement, avec ses
   options. Pour une copie `M'` d'un membre `M` :
   - les propriétés que l'ensemble de `M` lie (`FurnitureBindings`) viennent des **liaisons
     normales de l'ensemble copie** (`Member.repeated` écarte l'avertissement des autres) ;
   - les autres suivent `M` par expression (épaisseur, matériau, rotation, cote non étirée,
     position pilotée par une formule : `M.position + décalage de l'ensemble copie`) ;
   - un ensemble copie dont l'`Origin` suit la source lie **toutes** les positions de ses membres
     (comme un sous-ensemble, ADR 0009, mise à jour du 2026-10-21).
   Les assemblages entre membres (cas A) et vers une pièce extérieure (cas B) sont recopiés selon
   `CopyJoints` ; dissocier un ensemble copie dissocie l'ensemble et tous ses membres copiés.
4. **Pas de cycle** : une copie dépend de sa source, jamais l'inverse (les liaisons de la source
   citent l'épaisseur figée de ses copies, point 1) ; une copie de membre dépend de son original et
   de son ensemble copie, qui dépend de l'ensemble source. Sélection refusée si une pièce est
   répétée avec son propre ensemble (copiée deux fois).
5. **`FollowResize`** : le pas devient une expression. La répétition passe en « nombre sur une
   longueur » : `Span = <ensemble>.<cote de l'axe> - retraits`, `Step = (Span - cote des sources)
   / Count`. Les retraits (au début et à la fin, ensemble) sont ceux d'aujourd'hui, figés au
   moment de l'écriture : le pas ne bouge pas à l'écriture. Les sources doivent toutes être
   membres du même ensemble (refus traduit sinon). Décocher retire les expressions, le pas garde
   sa valeur.

## Conséquences

- `core.furniture.Member` gagne `linked` et `repeated` (défauts faux et vide : aucun effet sur les
  documents existants), à côté de `carried` (ADR 0038) ; `break_cycles` gagne le paramètre `frozen`. Aucune propriété persistante
  nouvelle : les propriétés de copie (`Repeat`, `RepeatSource`, `RepeatIndex`) existent déjà et
  sont ajoutées aussi aux ensembles copie.
- Un ensemble avec des copies liées partage les redimensionnements entre la source et ses
  copies au prorata (elles comptent comme membres), alors que leur pas reste fixe, sauf
  « Suivre le redimensionnement » : des copies d'un pas serré peuvent alors se chevaucher.
- Limites : la cote des sources écrite dans `Step` est figée (changer la source ne redistribue
  qu'à la prochaine modification de la répétition) ; une pièce en bois à forme libre dans un
  ensemble répété est refusée ; les Distances gardées d'un ensemble source ne sont pas copiées.
- **Membre ajouté à l'ensemble source après coup** : « Modifier la répétition » ajoute à chaque
  ensemble copie la copie du membre qui n'en a encore aucune dans la répétition (sous-ensembles
  compris). Un membre dont la copie a été supprimée ou dissociée à la main ne revient pas tant qu'il
  a une copie à un autre rang. Un membre retiré de l'ensemble source garde ses copies.

## Std Part de l'ensemble (fusion avec l'ADR 0038)

L'ADR 0038 range chaque ensemble dans un Std Part (`App::Part`) qui porte sa position
(`Placement`), ses membres, ses assemblages et ses Distances. La répétition d'un ensemble s'y
adapte au plus simple : **la copie d'un ensemble qui a un Std Part reçoit le sien**, créé comme
celui d'un ensemble neuf (`create_with_std_part`), puis tout ce qui était décidé plus haut se
transpose ainsi.

- **Où.** Le Std Part de la copie est rangé dans le conteneur du Std Part de la source (la
  racine, ou le `App::Part` de l'utilisateur) ; pour un sous-ensemble copié avec son parent, dans
  le Std Part de la copie du parent. La répétition (`Repeat`) est rangée dans ce même conteneur
  (`placement_container`), comme les copies de pièces d'un conteneur.
- **Position.** C'est le Std Part de la copie qui porte le décalage : `Placement.Base.c` = celui
  du Std Part de la source (+ `k * (Reverse ? -1 : 1) * Step` sur l'axe) et `Placement.Rotation` =
  celle du Std Part de la source, en expressions natives. `Origin` de la copie est celle de la
  source, sans décalage. Une source déplacée ou tournée à la souris entraîne donc ses copies, et
  le pas reste mesuré dans le repère du conteneur (les cotes liées sont `Width`, `Depth`,
  `Height`, `Origin`, `Placement` du Std Part). Une source sans Std Part (ancien document) garde
  l'ancien régime : copie sans Std Part, décalage dans son `Origin`.
- **Membres.** Les copies des membres sont créées dans le Std Part de la copie, **à la même place
  locale** que leur original dans le Std Part de la source (aucun décalage dans leurs `Placement`
  ; leur position globale est celle de la source plus le décalage du Std Part). Une formule de
  l'utilisateur sur la position d'un membre est donc recopiée telle quelle, sans le décalage
  `E'.Origin - E.Origin` des copies sans Std Part. Les liaisons de l'ensemble copie (`rebind`)
  s'appliquent comme avant ; `nested` (« mon `Origin` bouge ») ne vaut que pour un ensemble sans
  Std Part.
- **Sous-ensemble (`carried`).** Le sous-ensemble copié avec son parent a son propre Std Part,
  rangé dans celui de la copie du parent, et son `Origin` vaut celle de l'original (nulle) : sa
  position est portée par le `Placement.Base` de son Std Part, que les liaisons de la copie du
  parent écrivent (règle `carried` de l'ADR 0038 ; `member_expressions` et `set_member_expression`
  lisent et écrivent sur le bon objet). Un sous-ensemble **répété** (copie liée du même parent)
  est `carried` et `linked` : son Std Part suit le Std Part de la source (Base + pas, rotation) et
  le parent ne le lie pas.
- **Liens hors portée.** Les copies sont rangées dans des conteneurs différents de ceux de leurs
  sources (Std Part de la copie, conteneur de la répétition). `Source` devient
  `App::PropertyLinkListGlobal`, `Repeat` et `RepeatSource` `App::PropertyLinkGlobal` (comme
  `Furniture`, ADR 0038), `RepeatJoint` aussi : sans cela FreeCAD refuse le lien « hors de la
  portée » du conteneur. Les propriétés n'ont pas encore été publiées : aucune migration.
- **Dissociation.** `dissociate` retire aussi les expressions du Std Part de la copie (le Std
  Part cité est celui de la source) : la copie reste un ensemble normal, avec son Std Part
  (qu'on déplace ou tourne à la souris). Les copies de ses membres sont dissociées avec elle.
- **Suppression, sans Std Part orphelin.**
  - Nombre réduit (`edit_repeat`) : `drop_copy` supprime les copies des membres, fait sortir les
    pièces ajoutées à la main (elles gardent leur position globale), supprime le Std Part vide puis
    l'ensemble copie.
  - Suppression d'une copie d'ensemble dans l'interface : les copies de ses membres sont
    dissociées (elles restent des pièces libres), puis les membres sortent et le Std Part vide est
    supprimé comme pour tout ensemble (`release_furniture`, utilisée par `onDelete`).
  - Suppression de la source (ou de son Std Part à la main) : ses copies sont dissociées d'abord
    (`detach_copies`), sans quoi leurs expressions citeraient un objet absent et leurs pièces,
    liées à celles de la source, ne pourraient pas sortir du Std Part. Supprimer la répétition
    dissocie ses copies, qui gardent leur Std Part.
  - FreeCAD garde dans `InList` l'objet qui vient de perdre une expression ; `_closure`
    (fermeture de liens des entrées et sorties du Std Part) vérifie donc que le lien existe
    encore. On ne dissocie jamais un objet juste avant de le supprimer (le lien resterait
    pendant dans `InList` de la source).
- **Inchangé.** « Suivre le redimensionnement » (le pas suit la cote de l'ensemble parent des
  sources) et les assemblages recopiés (`create_joint` les range dans le conteneur de la pièce
  hôte, donc dans le Std Part de la copie). L'axe du pas reste celui du conteneur : pour un Std
  Part de la source tourné, les copies sont décalées dans le repère du conteneur et tournées
  comme la source.
- **Copie par glissement (Ctrl, lot R-d).** Elle ne concerne que les pièces : l'abstraction
  `Target` de l'ADR 0038 donne `PartTarget` pour la brute d'une pièce ; sur un ensemble
  (`FurnitureTarget`), Ctrl + clic n'est pas pris (le clic reste à FreeCAD). La copie utilise les
  guides, le repère et la tolérance de la cible.
