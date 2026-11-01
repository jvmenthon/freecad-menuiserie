# ADR 0030 — Bande de chant : solide séparé, cotes finies incluant la bande

- Statut : **accepté** (jv, 2026-11-01)
- Date : 2026-11-01
- Spécification : [docs/specs/finition-des-chants.md](../specs/finition-des-chants.md), § 4.6
- ADR liés : [0002 — Bibliothèque de matériaux](0002-bibliotheque-de-materiaux.md) (complété),
  [0006 — Pièce brute et pièce usinée](0006-piece-brute-et-piece-usinee.md),
  [0029 — Profils d'arête](0029-profils-d-arete-par-balayage.md),
  [0012 — Liste de débit à la demande](0012-liste-de-debit-a-la-demande.md)

## Contexte

Un panneau mélaminé ou de contreplaqué reçoit sur ses chants une bande (ABS, mélaminé, placage) de
0,4 à 2 mm, d'un autre matériau que le panneau. jv veut la dessiner, la voir d'une autre couleur
et la retrouver dans la liste de débit (longueur à commander par matériau). L'issue laisse ouvert
si la bande ajoute son épaisseur aux cotes ou la retire du panneau.

Le contact, les assemblages, l'accrochage et les ensembles raisonnent tous sur la **boîte** de la
pièce (`Length` x `Width` x `Thickness`).

Options étudiées pour les cotes :

1. **La bande s'ajoute à l'extérieur** : la boîte de la pièce n'est plus l'encombrement réel ; il
   faut revoir contacts, accrochage, ensembles et assemblages, et une pièce bandée aurait deux
   jeux de cotes. Rejetée.
2. **Cotes finies, bande comprise** : la boîte est l'encombrement ; la bande occupe l'épaisseur
   extérieure et le coeur est plus petit d'autant. C'est la pratique d'atelier (on commande le
   panneau à la cote de coupe = fini − bandes). Retenue.

Options pour la forme :

- (a) un seul solide, la bande en couleurs de faces : impossible à texturer proprement, faces
  renumérotées à chaque recalcul ; (b) **bande en solide séparé**, avec son aspect. Retenue.

## Décision

1. **Cotes** : `Length`, `Width`, `Thickness` restent les cotes finies, bandes comprises. La liste
   de débit ajoute la **cote de coupe** (`core_box`).
2. **Objet `EdgeBanding`** (`Part::FeaturePython`, « Bande de chant »), lié à une brute :
   `Sides` (chants ±X, ±Y, codes d'une énumération fermée), `Thickness`, `BandMaterial`. Sa forme =
   les bandes (une boîte par chant, la bande selon la plus grande dimension prenant le coin).
   Elle reçoit les profils d'arête de la pièce, pour que l'arête reste continue.
3. **Pièce usinée** : elle retire le volume des bandes de sa forme (aucun recouvrement) ; la bande
   s'affiche comme un objet à part, de l'aspect de son matériau. Graphe sans cycle :
   brute → profil → bande → pièce usinée ; la bande ne lit que sa brute et les profils de celle-ci.
4. **Matériaux** : nouveau `MaterialKind.BANDING = "banding"` dans la bibliothèque existante
   (`format` inchangé). Les menus de matériaux de pièce l'excluent. Huit bandes intégrées. Une
   version plus ancienne de l'atelier ignore ces entrées (entrée invalide ignorée seule, ADR 0002).
5. **Liste de débit** : cote de coupe pour une pièce bandée ; clé de regroupement qui inclut les
   bandes ; section « Chants » par matériau et épaisseur (longueur nette, arrondie au 0,1 m).
6. **Limites assumées** : une bande n'est pas percée par un assemblage (tourillons au chant) ;
   un assemblage qui touche un chant plaqué est signalé par un avertissement.
7. **Persistance** : chemin figé `freecad.menuiserie.features.edge_banding.EdgeBanding`, proxy sans
   état, `Version` = 1.

## Conséquences

- Contacts, assemblages, accrochage et ensembles fonctionnent sans modification sur un panneau
  bandé.
- Une pièce bandée compte un objet de plus (bande) ; toujours des solides `Part` ordinaires
  (STEP, TechDraw, lecture sans l'atelier).
- Le volume et la masse de la liste de débit restent ceux de la boîte finie ; l'écart avec le
  panneau nu (quelques dixièmes de pour cent) est documenté.
- Si jv préfère l'option 1 (bande en plus), la décision 1 est à reprendre avant tout code : c'est
  pourquoi la question Q2 est posée dès la spécification.
