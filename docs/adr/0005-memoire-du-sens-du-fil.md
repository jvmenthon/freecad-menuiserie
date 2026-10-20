# ADR 0005 — Mémoire du sens du fil dans la pièce de bois

- Statut : proposé (accepté avec la PR #15, lot J1c)
- Date : 2026-10-20
- Spécification : [docs/specs/J1-piece-de-bois.md](../specs/J1-piece-de-bois.md), § 4.4.6 et
  critères C10 et C11
- ADR liés : [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md) (sens du
  fil, contrat de persistance, `Version` et migration)

## Contexte

Exigence de jv (2026-10-20) : « Le sens du fils doit être garder en mémoire ainsi que on remet
ensuite un matériau avec un fils il est repris ». Aujourd'hui, une pièce en chêne fil en Largeur
qui passe en MDF prend `GrainDirection` = `None` (règle A7, voulue : un MDF n'a pas de fil), puis
revient en `Length` au retour vers un matériau avec fil : le choix du menuisier est perdu. Cela
arrive par le panneau de tâche (choix dans la liste ou filtre « Type », Q4 tranchée en faveur
d'un filtre qui applique le premier matériau du type), par l'éditeur de propriétés et par l'API.

La valeur `None` de `GrainDirection` est lue par la liste de débit (J2) et par la projection des
textures (J1d) ; elle doit garder son sens « sans fil ». Il faut donc une mémoire distincte, qui
survive à l'enregistrement, à la réouverture et à l'annulation.

## Décision

1. La mémoire est une propriété **de l'objet**, enregistrée dans le `.FCStd` :
   `PreferredGrainDirection`, `App::PropertyEnumeration` de valeurs stables `Length`, `Width`
   (mêmes chaînes que `GrainDirection`, ordre figé, ajouts en fin seulement), groupe
   « Matériau », masquée dans l'éditeur de propriétés. Elle ne prend jamais la valeur `None`.
2. Elle reçoit tout sens choisi (`Length` ou `Width`) dans `onChanged("GrainDirection")`, hors
   resynchronisation, restauration et annulation, dans la transaction de l'appelant : annuler et
   rétablir la restaurent avec `GrainDirection`. Choisir « Sans fil » ne l'efface pas.
3. Au retour vers un matériau avec fil, un fil `None` prend la valeur mémorisée
   (`grain_after_material_change(new, current, preferred)`, `core/`, pur) ; un fil déjà orienté
   est conservé, comme avant.
4. `MODEL_VERSION` passe de 1 à 2. La migration 1 → 2 (même fonction que 0 → 1 : ajout des
   propriétés manquantes) crée la propriété d'après `GrainDirection` (`Length` si `None`). Les
   contrôles de réouverture de l'ADR 0003 (type, valeur inconnue, version plus récente)
   s'appliquent à la nouvelle propriété.
5. La visibilité du fil (fil masqué pour un matériau sans fil, autre exigence de jv) n'est **pas**
   enregistrée : c'est un mode d'édition recalculé d'après le matériau à la création, à la
   réouverture et à chaque changement de matériau, annulation comprise.

Alternatives écartées :

- **Mémoire dans le proxy** (`dumps`/`loads`) : contraire aux proxies sans état de l'ADR 0003, et
  hors du mécanisme d'annulation de FreeCAD.
- **Mémoire de session** (dictionnaire en mémoire) : perdue à la fermeture du document, non
  annulable ; ne répond pas à l'exigence après réouverture.
- **Garder `Length`/`Width` dans `GrainDirection` pour un matériau sans fil** et déduire « sans
  fil » du matériau : pas de nouvelle propriété, mais `GrainDirection` changerait de sens pour les
  documents existants, J2 et J1d devraient consulter le matériau, et la règle A7 (critère B5)
  serait cassée.
- **Garder la `Version` à 1** et ajouter la propriété par simple réparation : contraire à la règle
  « toute évolution passe par `Version` + `_migrate` » de l'ADR 0003 ; un atelier plus ancien ne
  saurait pas qu'il ouvre un document plus récent.

## Conséquences

- Le nom `PreferredGrainDirection` et ses valeurs entrent dans le contrat de persistance : ils ne
  changeront plus. Défaire la décision demanderait une migration 2 → 3 qui supprime la propriété.
- Les documents de version 1 (enregistrés avec `main` après J1b, aucune version publiée) sont
  migrés à la réouverture ; une pièce déjà en MDF dans un tel document reprend `Length`, son
  ancien sens n'ayant été enregistré nulle part.
- Un document de version 2 ouvert avec l'atelier de J1b déclenche l'avertissement « version plus
  récente » ; la propriété est conservée telle quelle mais n'est pas mise à jour par cet atelier.
- La mémoire est propre à chaque pièce ; un sens par défaut pour les nouvelles pièces relèverait
  d'une préférence de l'atelier (question Q5 de la spécification).
- Coût : une propriété masquée, une branche de `onChanged`, deux fonctions pures dans `core/`,
  et les tests U et I du critère C10.
