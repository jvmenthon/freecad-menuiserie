# Ensembles : épaisseurs fixes, partage au prorata, pièces verrouillées

- Demande de jv (2026-10-23, recette J4/J6), décision : [ADR 0019](../adr/0019-rangees-epaisseurs-fixes-et-partage-au-prorata.md)
- Complète la spécification [J4 — Ensembles](J4-ensembles.md) (F5 à F10, N3, N4, P3) ; tout ce
  qui n'est pas dit ici reste valable.
- Lecture retenue en attendant jv : « configurées comme fixes » = nouvelle option de membre
  **`Locked`** (« Cotes fixes ») ; les options « distance fixe » de J4 gardent leur sens pour les
  écarts aux bords.

## 1. Règle de calcul (`core/furniture/`, Python pur)

Notations : axe A de l'ensemble (X, Y ou Z), cote C de l'ensemble sur A, tolérance
`CONTACT_TOLERANCE_MM` (0,01 mm). Seuls les membres d'équerre comptent (`square_spans`).

1. **Vis-à-vis** : deux membres sont en vis-à-vis sur A si leurs étendues se recouvrent de plus de
   la tolérance sur **chacun** des deux autres axes.
2. **Rangée** de M sur A : M et ses vis-à-vis sur A (pas de fermeture transitive).
3. **Points de coupe** : 0, C, et les bornes `lo`, `hi` sur A de chaque membre de la rangée,
   confondus à la tolérance près, triés. Deux points consécutifs bornent une **cellule**.
4. **Nature d'une cellule** (première règle qui s'applique) :
   1. hors de [0, C] → rigide, constante ;
   2. couverte par l'épaisseur d'une pièce (axe `Thickness`) ou par l'étendue d'un membre
      verrouillé → **rigide** ; elle vaut `<<Pièce>>.Thickness` si elle est exactement
      l'épaisseur entière de cette pièce (première pièce par clé en cas d'égalité), sinon sa
      longueur actuelle (constante) ;
   3. couverte par une cote étirable d'un membre non verrouillé → **libre** ;
   4. non couverte, entre deux cellules couvertes → **libre** (écart entre pièces) ;
   5. non couverte, au bord : ses **propriétaires** sont les membres de la rangée dont la face
      la borne. Distance fixe pour l'un d'eux → **rigide** constante ; sinon, mode `Stay` pour
      tous → **absorbante** ; sinon **libre**.
5. **Répartition** de la différence (R = somme des cellules rigides, avec les épaisseurs
   actuelles ; L₀, B₀ = sommes actuelles des cellules libres et absorbantes) :
   1. s'il y a des cellules absorbantes : si les deux bords le sont, celle du **début** devient
      rigide (la pièce ne bouge pas) ; chaque absorbante vaut `(C − R − L₀) × b / B₀` (parts
      égales si B₀ = 0), les libres gardent leur longueur ;
   2. sinon, s'il y a des cellules libres (L₀ > 0) : chacune vaut `(C − R) × l / L₀` ;
   3. sinon, si un écart au bord est rigide (distance fixe) : le plus long (égalité → fin)
      devient absorbant et on applique 5.1 ; notice `ThicknessKept` si la rangée est M seul et A
      l'axe de son épaisseur (comportement F7 conservé) ;
   4. sinon la rangée est **bloquée** : les cellules gardent leur valeur (épaisseurs vivantes
      comprises) et la rangée est notée bloquée, avec ses membres verrouillés.
6. **Coordonnées** : un point de coupe vaut la somme des cellules qui le précèdent depuis 0
   (constante pour un point négatif). C'est une fonction affine de C et des épaisseurs :
   `Linear(coef, const, thickness)` où `thickness` associe une clé de membre à son
   coefficient. La position liée de M est la coordonnée de son origine locale (`span.origin`) ;
   la cote étirée est `hi − lo`. Une épaisseur n'est jamais étirée.
7. **Expressions** (ADR 0009, F8) : `<<Ensemble>>.Origin.x + <<Ensemble>>.Width * r +
   <<Pièce>>.Thickness * t − k mm`, termes d'épaisseur triés par clé, coefficient 1 omis, signe
   `-` pour un coefficient négatif, mêmes arrondis (9 décimales pour r et t, 6 pour k). Une pièce
   au libellé inutilisable (`label_reference` le refuserait) est citée par son `Name`
   (`WoodPart001.Thickness`). Aucune liaison pour une valeur qui ne dépend ni de C ni d'une
   épaisseur (sauf `nested`).
8. **Membre** : `Member` reçoit `locked: bool = False`. Une pièce verrouillée ne reçoit aucune
   liaison de cote ; sa position suit la rangée.

### Critères (unitaires, **U**)

Bureau de référence de J4 (§ 3), options par défaut, libellés P = « Plateau », JG = « Joue
gauche », JD = « Joue droite », V = « Voile ».

| N° | Critère |
|---|---|
| E1 | Expressions : P `Length` = `<<Bureau>>.Width`, `Width` = `<<Bureau>>.Depth`, `Placement.Base.z` = `<<Bureau>>.Origin.z + <<Bureau>>.Height - <<Plateau>>.Thickness` ; JG `Length` = `<<Bureau>>.Height - <<Plateau>>.Thickness`, `Width` = `<<Bureau>>.Depth - 40 mm`, `Placement.Base.x` = `<<Bureau>>.Origin.x + <<Joue gauche>>.Thickness` ; JD `Placement.Base.x` = `<<Bureau>>.Origin.x + <<Bureau>>.Width` ; V `Length` = `<<Bureau>>.Width - <<Joue droite>>.Thickness - <<Joue gauche>>.Thickness` (ordre des clés), `Placement.Base.x` = `<<Bureau>>.Origin.x + <<Joue gauche>>.Thickness`, `Width` = `<<Bureau>>.Height - <<Plateau>>.Thickness - 320 mm`, `Placement.Base.y` = `<<Bureau>>.Origin.y + <<Bureau>>.Depth - 141 mm`. |
| E2 | Aperçu (`predict`) : Width → 1400 : JD x ∈ [1378, 1400], V 1356 ; Depth → 800 : V y ∈ [641, 659], JG/JD l = 760 ; Height → 800 : P z = 770, V l = 450 (valeurs de F10, inchangées). |
| E3 | **Épaisseur** (`predict` avec épaisseurs nouvelles, ou évaluation des `Linear`) : JG épaisseur 25 → JG x ∈ [0, 25], V x ∈ [25, 1178], V `Length` 1153, JD inchangée, l'ensemble reste à 1200. |
| E4 | **Prorata** : rangée joue 22 | étagère S1 400 | montant D 18 | étagère S2 600 | joue 22 (C = 1062) ; Width + 100 → S1 440, S2 660, D x ∈ [462, 480]. S1 verrouillée → S1 400, S2 700. |
| E5 | **Mode** : JG `FixedBack` décoché (`Stay`) → l'écart arrière absorbe, JG garde 560 (F10) ; V `FixedBack` décoché, `Stay` → aucune liaison sur Y ; `Proportional` → les deux écarts gardent leur proportion : Depth → 800, V y = 441 × 782 / 582 ≈ 592,546. |
| E6 | **Bloqué** : V verrouillé → rangée JG, V, JD bloquée ; `check_resize` Width → 1300 lève `BlockedRowError` (sous-classe de `FurnitureError`) dont `locked` = clés des verrouillés de la rangée (`("V",)`) et le message cite la cote et les pièces ; Depth → 800 accepté. Une rangée bloquée sans pièce verrouillée (deux pièces d'épaisseur qui remplissent C) donne le même refus avec `locked` vide. |
| E7 | `check_thickness(box, members, key, thickness, joined)` : mêmes contrôles que `check_resize` (bornes, `JOINT_LOST`, `OutsideBox`, `BlockedRowError`) pour une épaisseur nouvelle de la pièce `key`. JG à 25 accepté (E3) ; V verrouillé → refus, `locked` = `("V",)`. |
| E8 | Notices existantes conservées (`NotSquare`, `UserFormula`, `ThicknessKept`, `OutsideBox`) ; une propriété pilotée par l'utilisateur ne reçoit toujours aucune liaison (F9). |
| E9 | `follow_summary` : un membre verrouillé montre `Locked` (nouvelle valeur de `Follow`, après `Formula`) en plus de ce qu'il fait ; une liaison qui ne dépend que d'épaisseurs compte comme `Moved`/`Stretched`. |

## 2. Document (`features/`, `api.py`) — critères **I** (freecadcmd 1.0 et 1.1)

| N° | Critère |
|---|---|
| D1 | Propriété de membre `Locked` (`App::PropertyBool`, groupe « Ensemble », infobulle « Cotes fixes : la pièce ne change pas de cotes quand l'ensemble change. », faux par défaut), ajoutée et retirée avec les autres ; réouverture contrôlée comme `FixedTop` (N12) ; absente → faux, sans réécriture. |
| D2 | Bureau : `JG.Thickness = 25`, un recompute → JG x ∈ [0, 25], V `Length` 1153 en x ∈ [25, 1178], `Bureau.Width` = 1200, tourillons JG–V valides, rien de « Touched ». Idem JD. |
| D3 | `Width` = 1400 → seuls P (pleine largeur) et V changent de cote. |
| D4 | `api.set_member_options(V, locked=True)` relie **tout** l'ensemble ; `api.resize_furniture(bureau, width=1300)` → `LockedPiecesError` (sous-classe de `ValueError`, message traduit) dont `members` = (V,) ; rien n'est modifié. `api.unlock_and_resize(bureau, [V], width=1300)` (ou nom équivalent) : une transaction, V déverrouillé, tout relié, cote appliquée. |
| D5 | Éditeur de propriétés : `V.Locked = True` → ses liaisons de cote sont retirées ; si d'autres membres ont des liaisons à refaire, avertissement « Relier les pièces » dans la vue rapport. `Bureau.Width` saisi alors que la rangée est bloquée : appliqué, avertissement (Q4). `JG.Thickness` saisi dans l'éditeur alors que la rangée est bloquée : appliqué, avertissement. |
| D6 | Gabarit caisson (J4) : créé, puis plus large et plus haut, tout valide ; ses tests mis à jour aux nouvelles expressions. |

## 3. Interface — critères **G** et recette manuelle

| N° | Critère |
|---|---|
| G1 | Panneau de l'ensemble : une case « Cotes fixes » pour le membre choisi, à côté du mode ; la cocher relie tout l'ensemble (une transaction, aperçu immédiat). |
| G2 | Panneau de l'ensemble : une cote refusée par une rangée bloquée affiche le refus **et** une case à cocher par pièce verrouillée de la rangée (cochées par défaut), puis un bouton « Déverrouiller et appliquer » ; « OK » reste inactif tant que le refus dure. Le bouton déverrouille les pièces cochées, relie, applique la cote ; si la rangée reste bloquée, le refus se met à jour. |
| G3 | Panneau de la pièce de bois : une épaisseur refusée (rangée bloquée) affiche le même refus et les mêmes cases ; « Déverrouiller et appliquer » fait de même pour l'épaisseur. |
| G4 | Recette (`docs/recette/`) : scénarios de jv — largeur du bureau, épaisseur d'une joue, deux étagères au prorata, voile verrouillé puis déverrouillé par la case. |

## 4. Hors périmètre

Migration des documents existants (« Relier les pièces » suffit) ; épaisseur vivante d'une
cellule coupée par une autre face ; rangées qui se contredisent (ADR 0019, limite connue).
