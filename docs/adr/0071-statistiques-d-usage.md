# ADR 0071 — Statistiques d'usage : opt-in, compteurs agrégés, fichier local puis envoi

- Statut : **proposé** (brouillon, en attente des choix de jv)
- Date : 2026-11-27
- ADR liés : 0007 (compatibilité), 0031 et 0069 (configuration, `kit/`)
- Spécification : [statistiques-d-usage.md](../specs/statistiques-d-usage.md)

## Contexte

jv veut savoir comment l'atelier est utilisé (fonctions utilisées, erreurs, versions) pour
prioriser. L'atelier tourne chez des menuisiers dans FreeCAD, à côté d'autres ateliers ; leurs
projets sont confidentiels. Toute collecte doit donc être consentie, minimale et vérifiable.
ELK a été proposé.

## Décision

1. **Opt-in** : statistiques désactivées par défaut ; trois modes `off`, `local`, `send`.
2. **Compteurs agrégés** sur une liste fermée (commandes, variantes, panneaux validés / annulés,
   tranches de durée, type d'erreur + `fichier:ligne`, versions, système, langue). Jamais de
   géométrie, de nom, de chemin ni de message libre.
3. **Identifiant aléatoire** UUID 4 réinitialisable, sans empreinte de la machine.
4. **Étape 1 : fichier local** dans le dossier de l'atelier, exportable pour un ticket.
5. **Étape 2 : envoi hebdomadaire** en HTTPS (`urllib`, aucune dépendance) vers **PostHog Cloud UE**
   (proposé), IP non conservée, derrière une interface `Sink` remplaçable. **Plateforme unique**
   (jv, 2026-11-27) : le même compte PostHog servira au SaaS, dans un projet séparé, pour ses
   statistiques produit, ses erreurs et ses activations de fonctions.
6. **ELK écarté** : coût et maintenance d'un serveur, point d'entrée public à protéger, outil
   pensé pour des journaux de serveurs. À reconsidérer seulement si le SaaS dispose déjà d'ELK.
7. **Module générique** `freecad/menuiserie/kit/telemetry/` sans dépendance au reste de l'atelier
   (même règle que `kit/config`, ADR 0069).
8. **Compatibilité** (ADR 0007) : comptage dans notre classe de base de commande seulement ; aucun
   crochet global remplacé ; aucune activité réseau à l'import.

## Conséquences

- Les décisions de priorité s'appuient sur des chiffres, mais seulement des utilisateurs qui ont
  accepté (échantillon biaisé, à garder en tête).
- Chaque nouvelle commande doit être ajoutée à la liste fermée pour être comptée.
- L'étape 2 demande un compte chez le service, une page « Confidentialité » et une clé
  d'ingestion (écriture seule) gérée par jv.
- Aucun coût ni serveur à l'étape 1.

## Options écartées

- **ELK** : voir point 6.
- **Sentry** pour les erreurs : SDK lourd, traces susceptibles de contenir des noms de fichiers ;
  seconde plateforme à côté de PostHog, contraire au choix d'une plateforme unique.
- **Aptabase** : limité aux applications, ne couvre pas les besoins du SaaS.
- **Matomo / Plausible** : conçus pour des sites web.
- **Envoi par défaut (opt-out)** : contraire au RGPD / nLPD pour un identifiant persistant et mal
  reçu par la communauté FreeCAD.
