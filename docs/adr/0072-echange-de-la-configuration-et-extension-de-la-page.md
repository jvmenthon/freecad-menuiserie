# ADR 0072 — Échange de la configuration de l'atelier et extension de la page

- Statut : **accepté** (choix de jv : export « réglages et dimensions seulement », Q5 de la
  spécification, 2026-11-25 ; maquette A pour l'export / import, 2026-11-26)
- Date : 2026-11-27
- Complète : [0069 — Configuration de l'atelier](0069-configuration-de-l-atelier-modules-et-dossier.md)
- ADR liés : 0028 (dimensions personnelles), 0070 (valeur copiée à la création)

## Contexte

Les lots CA-c et CA-d (issue #148) ajoutent l'export et l'import des réglages dans
`atelier.json`, l'édition de `dimensions.json` dans la page de préférences et les derniers
réglages de l'inventaire. Plusieurs choix touchent les modules génériques de `kit/config/`,
réutilisables par un autre atelier : ils sont fixés ici.

## Décision

1. **Format d'échange.** `atelier.json` = `{"format": 1, "settings": {clé: valeur}, <section>:
   {…}}`. Les sections (ici « dimensions ») sont opaques pour `kit/config/exchange` : l'appelant
   fournit leur validateur. Les cases « Dernier utilisé » circulent sous `<clé>RememberLast`.
2. **Lecture stricte, refus entier.** Taille bornée (64 Kio), UTF-8 et JSON stricts (ni NaN, ni
   clé en double), `format` entier égal à 1 (plus récent : refusé), valeurs validées par le
   catalogue. Une seule valeur fausse refuse tout le fichier (`ExchangeError`, raison codée,
   traduite par l'atelier). Une clé inconnue est ignorée et signalée.
3. **Chemins exclus.** Les réglages `Kind.PATH` (dossier de l'atelier, des projets, d'export)
   sont propres à une machine : ni exportés ni importés.
4. **Import sans écriture.** L'import remplit les champs de la page (`SettingsPage.set_pending`)
   après un aperçu où l'utilisateur coche les lignes à reprendre ; l'écriture se fait à OK ou
   Appliquer, comme toute modification de la page. L'export écrit les valeurs enregistrées.
5. **Relations entre réglages.** Le catalogue peut déclarer des contrôles croisés (`Relation`,
   `Catalog.violations`), vérifiés à l'import (fichier refusé) et à l'enregistrement de la page
   (paire incohérente non écrite, message). Premier usage : pas et diamètre des taquets.
6. **Lignes propres à l'atelier.** La page générique accepte des lignes fournies par l'appelant
   (`ExtraRow`, dans un groupe existant ou nouveau), qui suivent le chargement, l'enregistrement
   et la recherche. L'éditeur des épaisseurs et formats en est une : il reste dans `gui/`, hors du
   kit. « Rétablir tout » ne touche pas à `dimensions.json`.
7. **Copie à la création, interface à l'usage.** Un réglage qui influence un document est copié
   dans l'objet à sa création et jamais relu au recalcul (principe de l'ADR 0070) ; un réglage
   d'interface (pas de rotation, panneau Structure, dossier d'export) est lu à l'usage.
8. **Lecture tolérante du stockage.** Un choix écrit à la main dans une autre casse (« a4 ») est
   reconnu à la lecture des préférences ; l'import, lui, reste strict.

## Conséquences

- Un fichier d'une version plus récente est lu tant que son format vaut 1 : ses réglages inconnus
  sont ignorés et listés. Un format 2 demandera un convertisseur.
- Un fichier partagé ne peut ni imposer un dossier ni écrire sans l'accord de l'utilisateur
  (aperçu, puis OK). Les textes venus du fichier sont affichés en texte brut et tronqués.
- Matériaux, quincaillerie et gabarits se partagent en copiant le dossier de l'atelier (Q5).
- Le kit gagne trois points d'extension (`sections`, `Relation`, `ExtraRow`) sans dépendre de
  la menuiserie ; un test vérifie toujours l'absence d'import de l'atelier dans `kit/`.
