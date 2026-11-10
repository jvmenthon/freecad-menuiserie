# ADR 0046 — Panneau « Structure » : arbre simplifié pour les débutants

- Statut : **proposé** (demande de jv, 2026-11-08 ; panneau séparé retenu par jv le 2026-11-10)
- Date : 2026-11-10
- ADR liés : [0007 — Compatibilité avec les autres ateliers](0007-compatibilite-avec-les-autres-ateliers.md),
  [0008 — Ensemble, objet de cotes](0008-ensemble-objet-de-cotes.md),
  [0038 — Ensemble à la souris](0038-ensemble-a-la-souris.md) (Std Part par ensemble),
  [0037 — Sous-ensemble depuis des membres](0037-sous-ensemble-depuis-des-membres.md),
  [0043 — Répétition](0043-repetition-objet-de-cotes-et-copies-liees.md)

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

- Un composant d'interface à maintenir (rafraîchissement, sélection), mais isolé dans `gui/` : le
  cœur et les `features/` ne changent pas.
- Les quatre défauts du prototype disparaissent : plus de masquage à réappliquer, la suppression
  d'un ensemble ne dépend plus de l'affichage, le glisser-déposer est du code de l'atelier.
- Compatible avec ADR 0008 (l'Ensemble n'est toujours pas un conteneur) et ADR 0038.
- L'arbre natif reste complet : le débutant peut le voir à côté ; on peut proposer d'ouvrir le
  panneau en onglet de la vue combinée.

## Lots proposés

1. Panneau « Structure » en lecture seule (ensembles, pièces, « Assemblages (N) ») et commande
   d'ouverture.
2. Rafraîchissement et sélection synchronisés avec FreeCAD (arbre natif, 3D), double-clic.
3. Menu contextuel et glisser-déposer.
4. Répétition (« ×N »), liste de débit, objets d'autres ateliers.
5. Noms et vocabulaire (arbre natif compris), à décider avec jv.
