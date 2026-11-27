# Statistiques d'usage (télémétrie) : spécification

- Statut : **brouillon**. Maquette retenue par jv le 2026-11-27 : **C** (question au premier
  lancement + case dans la page). Développement reporté (jv : « ne dev pas tout de suite »).
- Demande : jv, 2026-11-27 (« comprendre comment les utilisateurs utilisent l'atelier »).
- ADR : [0071 — Statistiques d'usage](../adr/0071-statistiques-d-usage.md) (proposé).
- ADR liés : 0007 (compatibilité avec les autres ateliers), 0031 et 0069 (configuration,
  page de préférences, modules génériques `kit/`).
- Maquettes : `/mnt/project-files/telemetrie/maquettes/maquette-{A,B,C}.png` (**C retenue**).

## 1. But

Savoir quelles fonctions servent, lesquelles échouent et sur quelles versions, pour décider des
priorités avec des chiffres plutôt qu'à l'intuition. Sans jamais collecter le travail de
l'utilisateur.

## 2. À quoi cela sert (usages concrets)

| Usage | Question à laquelle on répond | Donnée nécessaire |
|---|---|---|
| Prioriser | Quelles commandes servent vraiment ? Lesquelles jamais ? | compteur par commande |
| Simplifier | Quels types d'assemblage, de profil d'arête, de répétition sont utilisés ? | compteur par variante |
| Repérer les erreurs | Quelle commande échoue, où, combien de fois ? | type d'exception + fichier:ligne de l'atelier |
| Abandons | Un panneau est-il souvent annulé (fonction mal comprise) ? | panneau ouvert / validé / annulé |
| Versions supportées | Peut-on abandonner FreeCAD 1.1.x ? Windows / Linux / macOS ? | versions FreeCAD, atelier, système |
| Adoption | Une nouveauté est-elle utilisée après sa sortie ? | compteurs + version de l'atelier |
| Réglages par défaut | Quelles valeurs par défaut sont presque toujours changées ? | réglage modifié oui/non (pas la valeur) |
| Lenteurs | Quelles commandes sont lentes ? | durée par tranches (< 1 s, 1-5 s, > 5 s) |
| SaaS (plus tard) | Quelle part des utilisateurs fait listes de débit et plans ? | compteurs des commandes d'export |

Ce que la télémétrie ne dit pas : *pourquoi* l'utilisateur fait quelque chose. Les entretiens et
les tickets restent nécessaires.

## 3. Principes (non négociables)

1. **Désactivée par défaut** (opt-in). Aucun envoi, aucune écriture tant que l'utilisateur n'a rien
   choisi.
2. **Compteurs seulement.** Jamais de géométrie, de dimension, de nom de document, d'objet, de
   fichier ou de chemin, de texte saisi. Les messages d'erreur ne sont pas envoyés (ils peuvent
   contenir des noms) : seulement le type d'exception et `fichier:ligne` dans `freecad/menuiserie/`.
3. **Liste fermée.** Seuls les noms de commandes et de variantes déclarés par l'atelier sont
   comptés ; toute autre valeur devient `autre`.
4. **Transparence.** L'utilisateur voit le paquet exact avant l'envoi, peut l'exporter, l'effacer
   et changer d'identifiant.
5. **Identifiant aléatoire** (UUID 4), sans lien avec la machine ni le compte ; réinitialisable.
6. **Agrégé et rare.** Un paquet par semaine au plus, pas d'événement en temps réel.
7. **Discret.** Envoi en arrière-plan, délai court, aucune erreur affichée si le réseau manque ;
   rien au chargement de l'atelier (pas de réseau à l'import, règle FreeCAD).
8. **Compatible avec les autres ateliers** (ADR 0007) : on ne compte que nos propres commandes,
   depuis notre classe de base de commande. Aucun crochet global (`Gui.runCommand`,
   `sys.excepthook`) n'est remplacé.

## 4. Choix de la solution

### ELK (Elasticsearch, Logstash, Kibana)

Possible, mais **non recommandé** :

- conçu pour les journaux de serveurs, pas pour des compteurs envoyés par des postes clients ;
- lourd à héberger : Elasticsearch demande 2 à 4 Go de mémoire, un serveur dédié (environ
  20 à 40 €/mois) ou Elastic Cloud (à partir d'environ 100 $/mois) ;
- il faut exposer soi-même un point d'entrée public (Logstash ou une API) et le protéger contre
  les abus : surface d'attaque et maintenance (mises à jour, sauvegardes) à notre charge ;
- Kibana est puissant pour fouiller des journaux, moins direct pour « combien d'utilisateurs actifs
  par version ».

ELK n'a de sens que si une infrastructure ELK existe déjà (par exemple pour le futur SaaS).

### Comparatif

| Solution | Usage visé | Hébergement | Coût au départ | Effort | RGPD / nLPD |
|---|---|---|---|---|---|
| **Fichier local** + export joint à un ticket | erreurs, cas précis | aucun | 0 | très faible | rien n'est transmis automatiquement |
| **PostHog Cloud UE** | usage produit (entonnoirs, rétention, versions) | Francfort, géré | offre gratuite (≈ 1 M d'événements/mois) | faible (API HTTP simple) | région UE, option « ne pas stocker l'IP », DPA |
| Aptabase | statistiques d'applications de bureau, sobre | UE, géré ou auto-hébergé | offre gratuite limitée | faible | conçu sans données personnelles |
| Sentry | erreurs uniquement | UE, géré | offre gratuite (quelques milliers d'erreurs/mois) | moyen (SDK lourd, traces à nettoyer) | région UE ; risque de fuite de noms dans les traces |
| Matomo / Plausible | sites web | géré ou auto-hébergé | payant ou serveur PHP | moyen | bons, mais modèle « page vue » mal adapté |
| ELK | journaux de serveurs | serveur à gérer | 20 à 100 $/mois | élevé | dépend de notre hébergement |
| Point d'entrée maison (fonction sans serveur + base) | sur mesure | à gérer | ≈ 0 | moyen | à notre charge |

### Recommandation

1. **Étape 1 : mode local seul.** Les compteurs s'enregistrent dans un fichier JSON du dossier de
   l'atelier ; « Exporter… » produit le fichier à joindre à un ticket. Zéro serveur, zéro coût,
   utile tout de suite pour les rapports de bug.
2. **Étape 2 : envoi opt-in vers PostHog Cloud UE**, un paquet agrégé par semaine, en HTTPS avec
   la bibliothèque standard (`urllib`, aucune dépendance ajoutée), IP non conservée. Le module
   d'envoi a une interface `Sink` : changer de service (Aptabase, point d'entrée maison, ELK plus
   tard) ne touche qu'un fichier.
3. Les erreurs passent par le même paquet (type + `fichier:ligne`), sans Sentry.

## 5. Données du paquet (schéma 1)

```json
{
  "schema": 1,
  "id": "uuid4 aléatoire",
  "periode": "2026-11-20 / 2026-11-27",
  "atelier": "1.6.0", "freecad": "1.1.4", "systeme": "Windows", "langue": "fr",
  "commandes": {"Menuiserie_NewPart": 41, "Menuiserie_Joint.tenon": 12},
  "panneaux": {"Menuiserie_Joint": {"valide": 10, "annule": 2}},
  "durees": {"Menuiserie_CutList": {"<1s": 2, "1-5s": 1, ">5s": 0}},
  "erreurs": {"JointError@joints/dovetail.py:212": 2},
  "reglages_modifies": ["Joints.MortiseClearance"]
}
```

Le fichier local garde au plus 8 semaines ; au-delà, les plus anciennes sont effacées.

## 6. Architecture (règle de modularité)

Sous-paquet générique `freecad/menuiserie/kit/telemetry/`, sans import du reste de l'atelier
(même règle et même test que `kit/config`, ADR 0069) :

- `schema` : construction et validation du paquet, liste fermée des clés ; Python pur ;
- `recorder` : compteurs en mémoire, écriture atomique du fichier local, rotation ; Python pur ;
- `sink` : interface `Sink` ; `NullSink`, `FileSink`, `HttpSink` (`urllib`, délai 5 s, fil
  d'arrière-plan, aucune exception remontée) ;
- `consent` : mode (`off` / `local` / `send`), identifiant, date du dernier envoi, via `ParamStore`
  de `kit/config` ;
- `page` : groupe Qt pour la page de préférences (seul module Qt).

L'atelier fournit : la liste des commandes et variantes comptées, l'adresse du service, le point
d'appel dans la classe de base des commandes et des panneaux.

## 7. Interface (maquette C retenue par jv)

- **A — Une case** : « Envoyer des statistiques d'usage anonymes » + « Voir les données… ».
- **B ★ — Trois niveaux, aperçu dans la page** : Désactivées / Enregistrées sur cet ordinateur /
  Enregistrées et envoyées chaque semaine ; aperçu permanent du paquet ; Exporter…, Effacer,
  Nouvel identifiant. Recommandée : le mode local répond à l'étape 1 sans serveur.
- **C (retenue) — Question au premier lancement** : barre non bloquante une seule fois + case dans la
  page « Envoyer des statistiques d'usage anonymes », « Voir les données… », « Effacer ». Fermer la
  barre vaut refus. Le mode local (étape 1) reste à placer dans cette maquette.

## 8. Questions pour jv

- **Q1** Maquette : **C** (jv, 2026-11-27).
- **Q2** Question au premier lancement : **oui** (choix de la maquette C).
- **Q3** Service d'envoi à l'étape 2 : ★ PostHog Cloud UE, ou Aptabase, ou point d'entrée maison ?
- **Q4** Qui ouvre le compte du service et détient la clé d'ingestion (clé publique, écriture
  seule) ? ★ jv.
- **Q5** Page « Confidentialité » publiée (README ou wiki) avant l'étape 2 : ★ oui, obligatoire.
- **Q6** Compter aussi les réglages modifiés (sans valeur) ? ★ oui.

## 9. Critères d'acceptation (étape 1)

- Mode `off` par défaut : aucun fichier créé, aucune connexion réseau (test).
- Le paquet ne contient que les clés du schéma ; une commande inconnue devient `autre` (test).
- Aucune chaîne libre (nom de document, chemin, message) n'apparaît dans le paquet (test).
- « Exporter… », « Effacer », « Nouvel identifiant » font ce qu'ils disent.
- Aucun import de `freecad.menuiserie` dans `kit/telemetry` hors `kit` (test).
- Désactiver l'atelier ou un autre atelier ne change rien (aucun crochet global).

## 10. Lots

- **T-a** : `kit/telemetry` (schema, recorder, consent, FileSink), compteurs des commandes,
  groupe de la page (maquette retenue), mode local.
- **T-b** : erreurs, panneaux validés / annulés, durées.
- **T-c** (après Q3 à Q5) : `HttpSink`, envoi hebdomadaire, page « Confidentialité ».
