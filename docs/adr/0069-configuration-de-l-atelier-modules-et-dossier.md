# ADR 0069 — Configuration de l'atelier : modules génériques, dossier de l'atelier, « dernier utilisé »

- Statut : **accepté** (« go » de jv le 2026-11-25 sur les choix ★ de la spécification)
- Date : 2026-11-25
- Complète : [0031 — Configuration de l'atelier](0031-configuration-de-l-atelier.md)
- ADR liés : 0002 (matériaux), 0007 (compatibilité), 0028 (dimensions personnelles),
  0033 (quincaillerie)
- Spécification : [configuration-de-l-atelier.md](../specs/configuration-de-l-atelier.md) et son
  [inventaire](../specs/configuration-de-l-atelier-inventaire.md)

## Contexte

L'ADR 0031 fixe la page de préférences, le dossier de l'atelier et l'export. Depuis, trois besoins
sont apparus : jv veut des fonctionnalités **découpées au maximum, réutilisables dans un autre
atelier** ; `dimensions.json` et `quincaillerie.json` vivent déjà à côté de `UserLibraryPath` ;
jv veut pouvoir proposer **le dernier choix** au lieu d'une valeur fixe.

## Décision

1. **Modules génériques.** La mécanique de configuration vit dans un sous-paquet
   `freecad/menuiserie/kit/config/`, qui n'importe rien du reste de l'atelier :
   - `catalog` : description d'un réglage (`Setting` : clé, type, bornes, défaut, unité, libellé,
     infobulle, groupe, niveau principal / avancé, « dernier possible ») et validation bornée ;
     Python pur ;
   - `store` : interface `ParamStore` (lire, écrire, effacer une clé) ; une implémentation
     FreeCAD (`App.ParamGet` sous un chemin reçu) et une en mémoire pour les tests ;
   - `folder` : résolution du dossier de l'atelier (réglage, ancien chemin, repli) et écriture
     atomique ; FreeCAD seul ;
   - `exchange` : export / import JSON versionné, lecture stricte, aperçu des changements ;
     Python pur ;
   - `page` : page de préférences Qt construite à partir d'un catalogue ; seul module Qt.

   Le reste de l'atelier fournit le catalogue de la menuiserie (`features/settings.py`), le chemin
   `Mod/Menuiserie`, les traductions et les points de lecture. Dépendances dans un seul sens
   (menuiserie → kit) ; un test unitaire refuse tout `import freecad.menuiserie` hors de
   `freecad.menuiserie.kit` dans ce sous-paquet. Un autre atelier copie ou extrait le dossier tel
   quel.
2. **Dossier de l'atelier.** Défaut : le dossier de `UserLibraryPath` s'il est renseigné, sinon
   `<données FreeCAD>/Menuiserie/`. Il contient `materiaux.json`, `dimensions.json`,
   `quincaillerie.json`, `gabarits/` et `atelier.json`. Aucun fichier n'est déplacé.
   `UserLibraryPath` reste lu pour `materiaux.json` mais disparaît de l'interface.
3. **Dossier des projets** : réglage séparé du dossier de l'atelier (défaut `Documents/Menuiserie`),
   lu par l'assistant « Nouveau projet ».
4. **« Dernier utilisé ».** Un réglage marqué « dernier possible » a deux clés : le mode
   (`fixe` / `dernier`) et la valeur. Case cochée (mode `dernier`), la commande qui crée l'objet écrit la
   valeur retenue après validation ; la lecture reste bornée par le catalogue. Retenu pour les
   trois réglages des chants et tous les réglages principaux des assemblages. Les réglages d'assemblage ne valent que pour les
   assemblages créés par l'utilisateur : les gabarits imposent leurs propres choix.
5. **Page (maquette B, choix de jv)** : une seule page qui défile, groupes repliables avec le
   nombre de réglages modifiés, champ de recherche, case « Afficher les réglages avancés » (niveau
   donné par le catalogue). Chaque réglage « dernier possible » a une case à cocher « Dernier
   utilisé » ; chaque réglage a un bouton « Rétablir », la valeur par défaut est affichée.
6. **Export** : réglages et dimensions seulement ; les autres fichiers se partagent en copiant le
   dossier de l'atelier.
7. **Textes de l'interface** : libellés courts, infobulle d'une phrase qui dit l'effet et l'unité,
   style professionnel (consigne de jv).

## Conséquences

- Un réglage de plus = une entrée du catalogue ; page, export, « Rétablir » et « dernier utilisé »
  suivent sans autre code.
- Les modules `catalog` et `exchange` se testent sans FreeCAD ; `store`, `folder` avec le faux
  jeu de paramètres ; `page` dans les tests GUI hors écran.
- Laissés de côté pour l'instant (jv) : ensembles et gabarits, pieds et coulisses.
- Une version plus ancienne de l'atelier ignore les clés nouvelles.
