# ADR 0067 — « Dissocier » libère toute la répétition et la supprime ; copies numérotées « (n) »

- Statut : **accepté** (demande de jv du 2026-11-23)
- Date : 2026-11-23
- ADR liés : [0043](0043-repetition-objet-de-cotes-et-copies-liees.md) (remplace son point 4,
  « dissocier une copie »), [0044](0044-repetition-d-ensembles-et-liaisons-des-copies.md), [0045](0045-repetition-en-grille.md)

## Contexte

« Dissocier la copie » détachait une seule copie : elle gardait ses valeurs et devenait libre,
la répétition gardait les autres et son décompte (les rangs suivants ne bougeaient pas). À
l'usage (fil « Corriger queue d'aronde avec copies », 2026-11-17), jv n'y voyait aucune réaction :
rien ne bouge à l'écran et la répétition reste. Il demande (2026-11-23) que la dissociation
s'applique **à l'ensemble des copies et supprime l'élément répétition**, et que le numéro de la
copie soit **entre parenthèses**.

## Décision

1. `api.dissociate(obj)` accepte la répétition ou l'une de ses copies liées (pièce, pièce en
   bois, ensemble, membre copié d'un ensemble). Dans un seul bloc annulable « Dissocier la
   répétition » : un recalcul (valeurs à jour), puis chaque copie (hors membres d'un ensemble
   copie, emportés par leur ensemble) est dissociée comme avant (`repeat_links.unlink_copy` :
   expressions et propriétés `Repeat*` retirées, assemblages enfants libérés, ensemble relié par
   ses liaisons normales), puis l'objet répétition est supprimé. Plus aucune copie n'étant liée,
   sa suppression n'emporte rien. Les pièces d'origine ne changent pas.
2. La commande devient « Dissocier la répétition » (même nom interne
   `Menuiserie_RepeatDissociate`, même icône) ; elle est active sur une sélection faite de
   répétitions et de copies liées (une pièce usinée compte pour sa brute) et dissocie chaque
   répétition une fois. L'entrée du menu du panneau « Structure » fait de même.
3. Une copie seule ne se dissocie plus par l'interface. Le détachement d'une copie reste en
   interne : supprimer une pièce d'origine d'une répétition à plusieurs sources détache ses
   seules copies (`detach_copies`), la répétition garde les autres.
4. Nom automatique d'une copie : « Barreau (2) », « Barreau (3) »… (`core.repeat.copy_name`),
   au lieu de « Barreau 2 ». Les copies d'un document plus ancien gardent leur nom ; quand le
   rang change, l'ancien nom automatique est reconnu (`is_copy_name`) et remplacé par le nouveau.
   Pour une pièce, le nom est écrit comme **repère** (le libellé suit) : un libellé saisi
   « Barreau (3) » serait lu comme le doublon du repère « Barreau » (convention J6b,
   `mark_from_label`).

## Conséquences

- Plus de « trou » dans les rangs par la commande ; les cas limites de rangs après un
  détachement restent couverts par les tests (aide `detach_one_copy`).
- Une annulation rend la répétition et toutes ses copies liées.
- Le repère d'une copie (liste de débit) est « Barreau (2) » au lieu de « Barreau 2 ».
