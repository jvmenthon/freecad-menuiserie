# ADR 0051 — Gabarit personnel : description JSON d'un ensemble, dossier global

- Statut : **proposé** (décisions de jv : description JSON le 2026-11-11, dossier global et portée
  globale seule le 2026-11-06 et le 2026-11-11)
- Date : 2026-11-11
- Spécification : [docs/specs/gabarits-socle-et-personnels.md](../specs/gabarits-socle-et-personnels.md), § 4
- ADR liés : [0010 — Gabarits générateurs](0010-gabarits-generateurs.md),
  [0008 — L'Ensemble](0008-ensemble-objet-de-cotes.md),
  [0043 — Répétition](0043-repetition-objet-de-cotes-et-copies-liees.md),
  [0031 — Configuration de l'atelier](0031-configuration-de-l-atelier.md),
  [0050 — Registre de gabarits](0050-registre-de-gabarits-et-panneau-genere.md)

## Contexte

jv veut enregistrer un meuble dessiné (un ensemble) comme gabarit, tel quel ou modulaire, le
réutiliser dans tous ses projets, et plus tard le faire enrichir par l'IA du SaaS (P11 à P22).

Options de format (P14) :

1. **Fichier `.FCStd` modèle** : fidèle, mais lourd, lié à la version de FreeCAD, invérifiable avant
   ouverture, peut contenir des objets d'autres ateliers.
2. **Code Python** : tout est possible, mais exécuter un fichier reçu est un risque. Rejeté.
3. **Description JSON** d'un `Layout` étendu (pièces, assemblages, répétitions, sous-ensembles,
   paramètres exposés, groupes optionnels). Retenue.

## Décision

1. Un gabarit personnel est un fichier `<nom>.gabarit.json` (+ vignette PNG) dans
   `<données utilisateur FreeCAD>/Menuiserie/gabarits/`, chemin que le réglage « Dossier de
   l'atelier » (ADR 0031) reprendra sans migration. Portée globale seule ; la portée « projet »
   viendra plus tard avec le même format.
2. Format versionné (`"format": 1`), lu strictement par `core` (taille, nombres, matériaux,
   paramètres d'assemblage revalidés), refusé entier s'il est invalide ; écrit de façon atomique.
   Aucun code exécuté.
3. La description est un `Layout` sérialisé : un seul constructeur (`features/templates.py`). Le
   « Suivre » est celui de l'Ensemble (options « fixe ») et le « Répéter » est l'objet `Repeat`
   existant : aucun mécanisme de déformation nouveau.
4. Un gabarit se construit à sa taille d'origine, puis l'ensemble prend les cotes saisies et les
   paramètres exposés s'appliquent par les API existantes (redimensionnement, `edit_repeat`,
   matériau d'ensemble).
5. Les groupes optionnels sont vérifiés à l'enregistrement pour toutes leurs combinaisons (au plus
   5 groupes) ; une combinaison qui casserait une butée ou une liaison est refusée.

## Conséquences

- Les gabarits personnels se partagent par simple copie de fichier ; le futur SaaS et l'IA
  produiront ce même format.
- Ce qui ne se décrit pas est refusé à l'enregistrement (pièce enveloppe d'un corps, assemblage vers
  l'extérieur), avec un message qui liste les objets.
- Toute évolution du format passe par un nouveau numéro de `format` et une lecture des anciens.
