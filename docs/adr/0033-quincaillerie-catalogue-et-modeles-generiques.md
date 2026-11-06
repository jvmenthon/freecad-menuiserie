# ADR 0033 — Quincaillerie : catalogue de références et modèles génériques

- Statut : **accepté** (étude de l'issue #159, « Go » de jv le 2026-11-06)
- Date : 2026-11-06
- ADR liés : [0002 — Matériaux](0002-bibliotheque-de-materiaux.md),
  [0006 — Brute et usinée](0006-piece-brute-et-piece-usinee.md),
  [0007 — Compatibilité](0007-compatibilite-avec-les-autres-ateliers.md),
  [0028 — Dimensions personnelles](0028-dimensions-personnelles-partagees.md),
  [0031 — Configuration de l'atelier](0031-configuration-de-l-atelier.md)

## Contexte

jv veut une quincaillerie facile à utiliser, avec de vraies références de fournisseurs (voir
`docs/specs/quincaillerie.md`). Les fabricants publient des modèles 3D, mais rien n'autorise à notre
connaissance leur redistribution, et ils sont lourds et non paramétriques.

## Décision

1. **Catalogue de références** en JSON strict `{"format": 1, "items": […]}` (lecture bornée comme
   l'ADR 0028). Une entrée : `id` (fabricant + référence), fabricant, référence, `family`, libellé,
   `params` (cotes fonctionnelles en mm), `source`.
2. **Sources fusionnées par `id`**, la plus proche de l'utilisateur l'emporte : catalogue personnel,
   paquets déposés dans le dossier de l'atelier (ADR 0031), catalogue intégré. Le téléchargement de
   paquets (SaaS, issue #161) ne fera que déposer des fichiers : aucun changement de format.
3. **Catalogue intégré local et minimal**, hors ligne, saisi à la main depuis des fiches techniques
   publiques (faits techniques) ; aucun fichier de fabricant embarqué, ni prix, ni image de marque.
4. **Modèles génériques paramétriques** par famille, construits en Python pur dans `core/hardware/`
   à partir des `params` : enveloppe, point de pose, perçages et logements à usiner. Une famille
   inconnue reste dans la liste de débit, sans forme.
5. **STEP du fabricant en option**, importé par l'utilisateur (lot ultérieur) ; il remplace
   l'affichage, jamais les cotes d'usinage.
6. **Pose** comme un assemblage : plan d'usinage appliqué à la pièce usinée (ADR 0006), suivi des
   pièces par expressions natives, aperçu en direct.
7. **Compatibilité** : formes `Part` standard, aucune dépendance à l'addon Fasteners.

## Conséquences

- Aucun risque de licence dans le dépôt ; le catalogue grandit par ajout de JSON.
- Les cotes saisies à la main doivent être relues ; chaque entrée cite sa source.
- Les modèles génériques sont moins fidèles que ceux des fabricants (accepté).
