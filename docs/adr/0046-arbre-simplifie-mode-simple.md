# ADR 0046 — Panneau « Structure » : arbre simplifié pour les débutants

- Statut : **accepté** (jv, 2026-11-10 : panneau séparé retenu, « go » pour le développement)
- Date : 2026-11-10
- ADR liés : [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0038 — Ensemble à la souris](0038-ensemble-a-la-souris.md) (Std Part par ensemble),
  [0037 — Sous-ensemble depuis des membres](0037-sous-ensemble-depuis-des-membres.md),
  0043 — Répétition (à venir : PR #181 non fusionnée, pas encore de lien)

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
   - un nœud replié **« Assemblages (N) »** qui regroupe assemblages, quincaillerie et Distances ;
   - une répétition est une seule ligne **« <nom> ×N »** dépliable en ses copies ;
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
- L'arbre natif reste complet : le débutant peut le voir à côté ; on peut proposer d'ouvrir le
  panneau en onglet de la vue combinée.

## Lots proposés

1. Panneau « Structure » en lecture seule (ensembles, pièces, « Assemblages (N) ») et commande
   d'ouverture.
2. Rafraîchissement et sélection synchronisés avec FreeCAD (arbre natif, 3D), double-clic.
3. Menu contextuel et glisser-déposer.
4. Répétition (« ×N »), liste de débit, objets d'autres ateliers.
5. Noms et vocabulaire (arbre natif compris), à décider avec jv.
