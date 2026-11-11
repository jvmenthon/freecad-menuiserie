# ADR 0046 — Panneau « Structure » : arbre simplifié pour les débutants

- Statut : **accepté** (jv, 2026-11-10 : panneau séparé retenu, « go » pour le développement)
- Date : 2026-11-10
- ADR liés : [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0038 — Ensemble à la souris](0038-ensemble-a-la-souris.md) (Std Part par ensemble),
  [0037 — Sous-ensemble depuis des membres](0037-sous-ensemble-depuis-des-membres.md),
  [0043 — Répétition, objet de cotes et copies liées](0043-repetition-objet-de-cotes-et-copies-liees.md),
  [0044 — Répétition d'ensembles et liaisons des copies](0044-repetition-d-ensembles-et-liaisons-des-copies.md)

## Contexte

L'arbre de FreeCAD est trop chargé pour un débutant. Sur deux caissons répétés ×3, jv voit plus
de 100 lignes une fois tout déplié : Ensemble > Std Part > pièces usinées (brute en enfant), huit
assemblages à plat par caisson, une Origine par ensemble, des copies de répétition qui sont des
Std Part complets, un objet « Répétition » à la racine, un tableur par liste de débit. Les noms
(« (usinée) », « (Std Part) », « Caisson001 ») sont techniques.

## Options étudiées

1. **Masquer et regrouper dans l'arbre natif** (`ShowInTree`, `claimChildren`, dossier
   « Assemblages »). Prototype sur FreeCAD 1.1.4 (2026-11-09) : faisable, mais l'Ensemble et le
   Std Part ne se fusionnent à l'écran que si les **deux** réglages sont combinés, et il reste
   quatre défauts : supprimer l'Ensemble laisse ses objets à la racine ; le Std Part masqué
   réapparaît après un double-clic ou une copie ; le glisser-déposer est refusé par FreeCAD dans un
   groupe réclamé ; les copies de répétition doivent être masquées à leur tour. Elle ajoute aussi
   un objet-dossier au document. Rejetée.
2. **Fusionner Ensemble et Std Part en un objet** : ramène la référence cyclique de l'ADR 0008
   (un conteneur dépend de ses enfants, qui lisent ses cotes). Rejetée.
3. **Panneau « Structure » séparé**, à côté de l'arbre natif. **Retenue.**

## Décision

1. Un **panneau ancré** (dock Qt) « Structure », ouvert par une commande de l'atelier, montre
   l'arbre simplifié du document actif. L'arbre natif de FreeCAD n'est **ni modifié ni masqué** :
   le mode « expert » est simplement l'arbre natif, toujours présent.
2. **Contenu** (lecture seule du document, aucun objet créé) :
   - un nœud par **Ensemble** (le Std Part de l'atelier et son Origine ne sont pas montrés ;
     un sous-ensemble est un nœud enfant) ;
   - sous chaque ensemble, ses **pièces** (la brute et la pièce usinée forment une seule ligne) ;
   - un nœud replié **« Assemblages (N) »** (assemblages taillés dans le bois et Distances) et un
     nœud replié **« Quincaillerie (N) »** (objets du commerce : voir « Quincaillerie » ci-dessous) ;
   - une répétition (objet `Repeat`, ADR 0043) est une seule ligne **« <nom> ×N »** dépliable en
     ses copies de premier niveau, à la racine ou dans l'ensemble de sa source. Une copie de pièce
     est une ligne ; une copie d'ensemble (ADR 0044 : ensemble complet avec son Std Part, jamais
     montré) est une ligne qui porte son contenu (pièces, assemblages), dont les copies des
     membres (copies « internes » de la même répétition) ; aucune copie n'est montrée une
     seconde fois comme pièce ordinaire (`features/structure_repetitions.py`, lecteur réel) ;
   - la liste de débit est une ligne (son tableur n'apparaît pas) ; les sources des pièces en
     forme (Body, esquisse) ne sont pas montrées.
3. **Synchronisation** : le panneau se met à jour quand le document change (observateur de
   document, regroupé pour ne pas recalculer à chaque propriété) ; sélectionner une ligne
   sélectionne l'objet dans FreeCAD (et la 3D), et inversement (observateur de sélection).
   Double-clic : même panneau de tâche que dans l'arbre natif.
4. **Actions** : menu contextuel (supprimer avec la fenêtre « assemblage lié » existante,
   renommer, ajouter au sous-ensemble) et **glisser-déposer** (voulu par jv) : déposer une pièce
   sur un ensemble l'y range, comme la commande de l'ADR 0037 ; refus expliqué si la pièce porte
   un assemblage vers l'extérieur (ADR 0026). Toute action passe par l'api de l'atelier, avec une
   transaction.
5. **Vocabulaire** : le panneau utilise les mots du débutant (« pièce », « assemblage », « ×3 »),
   sans « (usinée) » ni « Std Part ». Les noms internes et les libellés de l'arbre natif ne
   changent pas ici ; leur revue est un lot suivant (jv : « on changera les noms plus tard »).
6. **Aucune donnée ajoutée au document** : le panneau ne crée ni objet, ni propriété, ni dossier.
   Un fichier s'ouvre identique avec ou sans l'atelier.

## Compatibilité avec les autres addons

Aucun objet de FreeCAD n'est masqué, réclamé ou modifié : les Std Part, `App::Link`, Assembly,
TechDraw et l'export STEP voient le document tel quel (ADR 0007). Le panneau ne montre que les
objets de l'atelier ; les objets des autres ateliers apparaissent sous « Autres objets » (replié)
ou ne sont pas montrés, au choix du lot 1.

## Conséquences

- Un composant d'interface à maintenir (rafraîchissement, sélection), dans `gui/`. **Le cœur et
  `features/` ont changé aussi** (la première version de cet ADR disait le contraire) :
  - `add_members(…, move=True)` : des objets déjà membres d'un autre ensemble en sortent
    (`detach_members(…, keep_properties=True)` puis `leave`, ADR 0038) et entrent dans le nouvel
    ensemble par `adopt` ; `build_furniture` fait de même pour un sous-ensemble créé depuis des
    membres (ADR 0037) ;
  - `detach_members(objects, keep_properties=False)` et `remove_members(…, keep_properties=…)` :
    l'option garde les propriétés de membre (voir « État d'orphelin ») ;
  - le contrôle de conteneur d'un membre qui change d'ensemble compare les conteneurs hors Std
    Parts d'ensemble (`outer_container`) ;
  - `check_assembled` suit le critère pur `core/assembly_scope` (voir ci-dessous) ;
  - `features/furniture_resize.py` (contrôle puis écriture des cotes d'un ensemble) est celui de
    l'ADR 0038 ; `furniture_children` (enfants d'un ensemble dans l'arbre) a quitté le
    ViewProvider pour `features/furniture_view.py`, car le panneau et l'arbre natif le partagent ;
  - `api.rename(obj, name)` : « Renommer » du panneau passe par l'api (contrôle
    `decide_rename`, `ValueError` traduite, brute d'une pièce usinée), comme toute écriture.
- **Assemblage vers l'extérieur et « parent le plus proche »** (décision de jv ; critère unique,
  `core/assembly_scope`, partagé par `decide_drop`, `decide_create` et l'api `add_members` /
  `build_furniture`). FreeCAD range toute la fermeture de liens d'une pièce dans le Std Part
  d'arrivée (essai de l'ADR 0038, confirmé par la CI) : deux pièces assemblées doivent donc être
  dans le même ensemble (ou toutes deux hors de tout ensemble). Au lieu de refuser, quand
  l'endroit demandé séparerait un assemblage, la pièce P (avec les pièces qui lui sont assemblées
  parmi celles qu'on déplace) va à l'endroit cohérent le plus proche, et le panneau dit où elle est
  allée :
  - P assemblée à Q, Q dans A, P déposée sur un sous-ensemble S de A : P **reste dans A**, avec Q ;
    rien n'est rangé dans S et le message l'explique ;
  - P et Q (et toutes les pièces liées entre elles) déposées ensemble sur S : elles vont toutes dans
    S, sans message ;
  - P déposée sur A alors que Q est dans un sous-ensemble S de A : P va dans **S**, comme Q ;
  - P assemblée à Q hors de tout ensemble : P reste (ou passe) hors ensemble avec Q ;
  - création d'un sous-ensemble avec P seule, assemblée à Q dans A : rien à créer, P reste dans A
    (refus expliqué) ; avec d'autres pièces libres de tout assemblage, le sous-ensemble ne reçoit
    qu'elles et P reste dans A (avertissement) ; P et Q choisies ensemble forment le sous-ensemble ;
  - **refus** seulement s'il n'existe aucun rangement cohérent : l'autre pièce est dans une autre
    branche (autre ensemble de plus haut niveau) ou deux exigences se contredisent.
  Règle : l'endroit cohérent est l'ensemble de la pièce qui reste, s'il est dans la même branche
  que l'endroit demandé (un ensemble commun existe). Une pièce assemblée à une pièce hors ensemble
  est rangée avec elle par l'api (avertissement, ADR 0038) ; le panneau, lui, la laisse hors
  ensemble.
- **État d'orphelin.** FreeCAD 1.1.3 ne rétablit pas, à Ctrl+Z, une propriété dynamique retirée
  puis recréée dans la même transaction. Changer d'ensemble, sortir et créer un sous-ensemble ne
  retirent donc plus les propriétés de membre : seuls le lien `Furniture` (remis à zéro) et les
  liaisons sont retirés. Une pièce sortie par le panneau garde ses propriétés de membre
  (`PositionMode`, `Fixed…`, `Locked`, `FurnitureBindings` vide) sans ensemble ; c'est l'état
  qu'a déjà une pièce dont l'ensemble est supprimé. Il est inoffensif (`furniture_of` rend
  `None`, la pièce est « hors ensemble » partout), `add_to_furniture` et `make_furniture`
  réécrivent ces propriétés à l'entrée suivante, et le fichier s'enregistre et se rouvre à
  l'identique. La commande native « Retirer de l'ensemble » est alignée sur le panneau
  (`keep_properties=True`) : un seul comportement, sans nettoyage à la réouverture. Seule la
  suppression d'un ensemble (`remove_members` sans option) retire encore les propriétés.
- Les quatre défauts du prototype disparaissent : plus de masquage à réappliquer, la suppression
  d'un ensemble ne dépend plus de l'affichage, le glisser-déposer est du code de l'atelier.
- Compatible avec ADR 0008 (l'Ensemble n'est toujours pas un conteneur) et ADR 0038 : le Std Part
  et son Origine ne sont jamais des lignes du panneau, ni « Autres objets », ni ensemble.
- Qt : `gui/` n'importe que `from PySide import …` (ADR 0023, Qt 5 compatible) ; l'existence de
  l'arbre Qt se suit par son signal `destroyed`, pas par `shiboken` (un test l'interdit).
- **Icônes et ouverture par défaut.** Chaque ligne porte l'icône de son genre
  (`core/structure_icons`, icônes de l'atelier réutilisées ; « Répétition » et « Autre objet »
  ajoutées au générateur) ; un fichier absent donne une ligne sans icône. Le panneau s'ouvre seul à
  l'activation de l'atelier, en onglet avec la vue combinée et sans prendre le premier plan, tant
  que l'utilisateur ne l'a pas fermé (réglage `StructureClosedByUser` des préférences de l'atelier,
  pas dans le document) ; la commande et l'ouverture par défaut partagent `show_panel`.
- **Complétude** (correctif). Tout objet de l'atelier apparaît exactement une fois dans le panneau.
  Les assemblages, quincaillerie (pieds, coulisses, LR32, tenons…) et Distances qu'aucun ensemble
  ne range (pièce hors ensemble, pièces d'ensembles sans ensemble commun) forment un nœud replié
  « Assemblages (N) » à la racine (`StructureSource.loose_joints`) ; tout objet de l'atelier encore
  invisible va sous « Autres objets de l'atelier (N) » (`StructureExtras.workshop_objects`) plutôt
  que d'être perdu. Mêmes actions et icônes que sous un ensemble.
- **Quincaillerie** (demande de jv, ADR 0033). Un type d'assemblage est de la quincaillerie quand
  l'ADR 0033 le pose depuis une référence du catalogue : pieds, coulisses, taquets LR32,
  tourillons, faux tenons, biscuits (`core/structure_hardware.HARDWARE_KINDS`, testée contre les
  familles du catalogue). Tenon-mortaise, rainure-languette, feuillure, mi-bois, queue d'aronde et
  onglet restent des « Assemblages », avec les Distances. Genres de ligne `HARDWARE` et
  `HARDWARE_ITEM`, mêmes actions que `JOINT` ; sous un ensemble comme à la racine pour les objets
  libres.
- **Icônes par type.** `StructureNode.subtype` (valeur de `JointKind`, « distance », « shaped »)
  choisit l'icône (`core/structure_icons.ICON_BY_SUBTYPE`) : chaque assemblage a l'icône de sa
  commande, la Distance et la pièce en forme celles de leur objet. Seule « Quincaillerie »
  (`Menuiserie_Hardware.svg`) a été ajoutée au générateur ; un type inconnu retombe sur l'icône du
  genre, un fichier absent sur l'absence d'icône.
- L'arbre natif reste complet : le débutant peut le voir à côté ; on peut proposer d'ouvrir le
  panneau en onglet de la vue combinée.

## Sélection et tâche en cours

Demande de jv : cliquer une ligne rend l'objet transparent « comme en cas de modification, mais
d'une autre couleur » ; double-cliquer une autre ligne pendant une tâche règle d'abord la tâche.

- **Deux calques d'affichage indépendants** (`core/display_layers`, `gui/display_layers`). La
  transparence de la tâche en cours (« édition », 60 %, couleur d'origine, ADR 0011) et celle de la
  ligne sélectionnée (« sélection », 50 %, teinte bleu clair `SELECTION_TINT`, le bois n'étant
  jamais bleu) sont deux calques d'une même pile par objet. L'état d'origine (transparence et
  couleur diffuse) est retenu **une fois**, au premier calque posé, et n'est rendu qu'au retrait du
  dernier : aucun calque ne restaure ni n'écrase l'autre. Si l'objet porte les deux, l'édition
  l'emporte visuellement (priorité). `PartsPreview` (édition) passe par le même gestionnaire
  (`DISPLAY`, cache explicite et réinitialisable). Une propriété modifiée par un tiers pendant un
  calque devient la nouvelle origine, jamais écrasée par l'ancienne valeur.
- **Étendue** (`core/structure_highlight`, `features/highlight_targets`) : une pièce, ses
  objets affichés (la pièce usinée à la place de sa brute) ; un ensemble, toutes ses pièces et
  celles de ses sous-ensembles ; un assemblage ou une quincaillerie, ses deux pièces. Les nœuds
  repliés, la liste de débit et les objets d'autres ateliers ne mettent rien en évidence.
  Seul le choix d'une ligne par l'utilisateur rend transparent : une sélection faite dans l'arbre natif ou la 3D ne change aucun affichage, et reprise par le panneau elle retire la transparence du choix précédent.
- **Sorties.** Les propriétés du ViewObject sont enregistrées dans le fichier et dans la
  transaction ouverte (revue finale) :
  (1) le calque d'édition est posé à l'ouverture du panneau, la transaction d'une modification
  (encore vide à cet instant seulement) étant refermée puis rouverte : « OK » sans changement ne
  laisse aucune entrée d'annulation ; la transaction n'est **jamais** abandonnée ailleurs (rien ne
  dit alors qu'elle est vide) ;
  (2) le calque de **sélection** n'est ni posé ni retiré tant qu'une transaction est ouverte (tâche
  en cours, commande) : la demande est mémorisée (`DisplayLayers.show(..., deferrable=True)`) et
  jouée à la fermeture de la tâche (`flush`, après le solde de la transaction) ou à la demande
  suivante. Une ligne choisie **avant** la tâche reste affichée pendant elle ; une ligne choisie
  **pendant** la tâche s'affiche à sa fermeture ;
  (3) l'origine est rendue avant tout enregistrement du document (`slotStartSaveDocument`, chaque
  objet isolément : une erreur est écrite dans le rapport sans interrompre les autres) et les
  calques reposés après (`slotFinishSaveDocument`) ; si l'enregistrement échoue, la demande
  suivante réécrit le calque (`_already_shown` exige l'écriture faite) ;
  (4) objet supprimé : son origine lui est rendue avant l'oubli (la transaction de suppression garde
  son ViewObject, Ctrl+Z ne le recrée pas teinté) ; document fermé : calque oublié ;
  (5) calque de sélection retiré à la désélection, au masquage ou à la destruction du panneau ;
  calque d'édition à toute fermeture de la tâche. L'observateur de document n'existe que tant
  qu'un calque existe (ADR 0007), son retrait est différé hors de la notification en cours.
  **Limite connue** : les fichiers de récupération automatique de FreeCAD ne passent pas par
  `slotStartSaveDocument` ; une récupération après plantage peut contenir la teinte de la ligne
  choisie à cet instant (un calque ne survit pas à la fermeture normale).
  **Exception documentée** : `gui/view_providers/wood_part.py` dit que le ViewProvider écrit la
  couleur diffuse ; `gui/display_layers` en est l'unique autre écrivain, et toujours temporaire.
- **Déplacer et tourner à la souris** depuis une ligne : les flèches et anneaux (ADR 0038, #65,
  #117) suivent `Gui.Selection` par un observateur ; le panneau écrit dans cette sélection, ils
  s'activent donc déjà comme pour une sélection faite en 3D, avec les mêmes conditions (un seul
  objet sélectionné, aucune tâche ouverte). Aucun branchement n'a été nécessaire ; le calque de
  sélection est un affichage sans lien avec leurs nœuds Coin ni leurs transactions. Contrôlé par
  `tests/gui/verifications_structure_selection.py`.
- **Double-clic pendant une tâche** (`core/task_switch`, `gui/structure_switch`). Le panneau de
  l'atelier ouvert s'inscrit dans `gui/task_panels/active` (FreeCAD ne rend pas le panneau Python) :
  une tâche non inscrite est d'un autre atelier et le double-clic est refusé avec un message. Sinon :
  sans modification, la tâche est fermée comme « Annuler » (rien n'est écrit) puis la pièce s'ouvre ;
  avec des modifications, une boîte (texte brut) propose « Appliquer les modifications » (« OK » de la
  tâche, puis la pièce), « Annuler les modifications » (« Annuler » de la tâche : rien n'est
  conservé, aucune entrée d'annulation, puis la pièce) ou « Poursuivre la tâche en cours » (Échap et
  fermeture de la boîte valent ce bouton : on reste sur la tâche). Une tâche de création est toujours
  traitée comme modifiée (« Annuler » supprimerait l'objet). Si « OK » est refusé (erreur à
  corriger), on reste sur la tâche.
- **Détecter « modifié ».** FreeCAD n'indique pas si la transaction ouverte est vide. Le panneau
  prend à son ouverture une photo des propriétés saisies de tous les objets (`features/document_snapshot`,
  filtre pur `core/document_state` : ni `Output`, ni `Transient`, ni forme, ni proxy, ni visibilité ; « lecture seule » est un simple mode d'éditeur et des panneaux écrivent de telles propriétés, par exemple « Inverser » sur HostPart et GuestPart)
  et la compare au seul double-clic (jamais à un clic de ligne) : lecture seule, la transaction et Ctrl+Z ne sont pas touchés, un
  recalcul n'est pas une modification.

## Lots proposés

1. Panneau « Structure » en lecture seule (ensembles, pièces, « Assemblages (N) ») et commande
   d'ouverture.
2. Rafraîchissement et sélection synchronisés avec FreeCAD (arbre natif, 3D), double-clic.
3. Menu contextuel et glisser-déposer.
4. Répétition (« ×N »), liste de débit, objets d'autres ateliers. **Lot complet** : la ligne
   « <nom> ×N » et ses copies lisent l'objet Répétition de l'ADR 0043 ; double-clic sur la
   répétition ou une copie = « Modifier la répétition » (pièce ou ensemble copie) ; menu : Modifier
   la répétition, Renommer (la répétition aussi), Dissocier la copie (`api.dissociate`, une
   transaction), Supprimer ; une copie ou une répétition ne se glisse pas, ne se range pas et ne
   reçoit aucun dépôt ; sélectionner la répétition met toutes ses copies en transparence (calque de
   sélection ; une copie d'ensemble : toutes ses pièces) ; icône `Menuiserie_Repeat.svg`.
5. Noms et vocabulaire (arbre natif compris), à décider avec jv.
