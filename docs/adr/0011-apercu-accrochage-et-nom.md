# ADR 0011 — Aperçu par l'objet réel, accrochage ponctuel calculé dans `core/`, nom = repère

- Statut : **accepté** (jv, 2026-10-22 ; réponses aux questions de la spécification J6)
- Date : 2026-10-22
- Spécification : [docs/specs/J6-interface.md](../specs/J6-interface.md), § 4
- ADR liés : [0001 — Structure de l'atelier](0001-structure-de-l-atelier.md),
  [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — L'Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0009 — Suivi par expressions natives](0009-suivi-par-expressions-natives.md)

## Contexte

jv demande (issue #37) qu'une nouvelle pièce de bois apparaisse en aperçu pendant son réglage,
qu'elle vienne toucher les faces, arêtes ou sommets sélectionnés, qu'un bouton la fasse tourner, et
que son nom soit son repère. Trois choix sont difficiles à défaire : comment montrer l'aperçu, si
l'accrochage crée un lien durable, et qui détient le nom de la pièce.

### Aperçu — options étudiées

1. **Nœud Coin3D temporaire** (forme dessinée hors du document, objet créé à « OK ») : aucune
   trace dans le document pendant le réglage. Mais il faut redessiner la forme, la texture et les
   assemblages à part ; les champs à expression (`Gui.ExpressionBinding`) exigent un objet ; et
   l'aperçu diffère du résultat. Rejetée.
2. **Objet réel dans la transaction du panneau** (mécanisme actuel de J1c/J3e), affiché
   semi-transparent le temps du panneau. Ce qu'on voit est ce qu'on obtient ; « Annuler »
   abandonne la transaction. Retenue.

### Accrochage — options étudiées

1. **Attachement natif** (`Part::AttachExtension`, mode « FlatFace » etc.) : la pièce suit la face
   si celle-ci bouge. Mais il dépend des noms topologiques (`Face3`), fragiles quand la pièce visée
   change ; il entre en conflit avec les liaisons de `Placement` des ensembles (ADR 0009) ; il ne
   sait pas toucher deux éléments à la fois ni étirer une cote ; et il ajoute à notre objet des
   propriétés d'un autre mécanisme. Rejetée.
2. **Placement calculé une fois** à la création, d'après les éléments sélectionnés, par des règles
   pures (`core/snap/`), la lecture des formes dans `features/` et la sélection dans `gui/`.
   Aucune propriété ajoutée ; le suivi paramétrique reste celui de l'Ensemble. Retenue.

### Nom — options étudiées

1. **Libellé indépendant** (état actuel) : le repère n'est visible que dans les propriétés. Ne
   répond pas à la demande.
2. **Repère dérivé du libellé** : un libellé est unique dans un document, alors que des pièces
   identiques doivent pouvoir partager un repère (liste de débit). Rejetée.
3. **Libellé dérivé du repère**, rendu unique par un suffixe de l'atelier (« M1 (2) »), avec retour
   du libellé saisi vers le repère (suffixe retiré). Retenue.

## Décision

1. **Aperçu** : la pièce en création est l'objet réel, dans la transaction ouverte par la commande ;
   `PreviewStyle` (dans `gui/`) pose une transparence de 60 % et la rétablit avant la validation.
   Rien de l'aperçu n'est enregistré.
2. **Accrochage ponctuel** : `core/snap/` calcule, sans FreeCAD, un `RigidTransform` (et au plus
   une cote étirée, jamais l'épaisseur) d'après des cibles valeur (`FaceTarget`, `EdgeTarget`,
   `VertexTarget`) exprimées en coordonnées globales ; une Strategy par type de cible fournit le
   repère d'appui et la contrainte d'un élément suivant. `features/snap_targets.py` convertit les
   formes Part (de tout atelier) en cibles ; `gui/` lit la sélection, la direction de vue et le
   conteneur. Le `Placement` est écrit une fois, dans le repère du Std Part qui reçoit la pièce ;
   aucun lien vers l'élément touché ne subsiste.
3. **Conteneur** : le dernier `App::Part` du chemin de sélection du premier élément, sans
   traverser un `App::Link` ; jamais un `PartDesign::Body` ni un assemblage.
4. **Nom = repère** : `Mark` reste la donnée ; `Label` en est le reflet (`core/naming.py`),
   synchronisé dans les deux sens par le `onChanged` (et `onBeforeChangeLabel`) de la pièce, hors
   restauration et annulation. **Exception** à la règle « l'objet n'écrit que dans lui-même » de
   l'ADR 0009 : la brute écrit le `Label` de sa pièce usinée (« M1 (usinée) »), et seulement lui,
   parce que l'usinée est sa face visible (ADR 0006). Aucune préférence de FreeCAD n'est lue ni
   modifiée (pas de « libellés en double »). Les documents existants ne sont pas renommés à
   l'ouverture. Copier-coller, Std Dupliquer et
   fusion de documents restaurent le libellé du modèle sans passer par `onBeforeChangeLabel` :
   `onDocumentRestored` rend alors le libellé unique quand il est déjà pris (« M1 (2) »), sans
   toucher au repère.

## Conséquences

- Aucune propriété, aucune `Version` ni migration nouvelles : les documents restent lisibles par
  les versions précédentes de l'atelier et sans l'atelier.
- Une pièce posée contre une autre ne la suit pas si elle bouge ; pour un meuble qui doit suivre
  ses cotes, le menuisier passe par l'Ensemble (la case « Ajouter à l'ensemble » l'y aide).
- La géométrie d'accrochage est testée sans FreeCAD ; seules la lecture des formes et la sélection
  demandent les tests d'intégration et d'interface, sur 1.0 et 1.1.
- Le suffixe « (n) » est réservé : un repère qui finit par « (2) » saisi dans l'arborescence perd
  ce suffixe (limite documentée).
- `onBeforeChangeLabel` doit être vérifié sur FreeCAD 1.0 et 1.1 avant J6b ; un repli sans lui est
  prévu par la spécification (§ 4.4).
