# Gabarits : les problématiques avant les choix

- Statut : **exposé des problématiques**, aucun choix fait (demande de jv du 2026-11-05 : « exposez-moi
  les problématiques avant de faire des choix »).
- Questions de jv : comment intégrer les gabarits facilement ? comment garder une interface simple ?
  comment ajouter un gabarit personnalisé ?
- Contexte : [gabarits-meubles.md](gabarits-meubles.md), ADR [0010](../adr/0010-gabarits-generateurs.md)
  (gabarit générateur), [0031](../adr/0031-configuration-de-l-atelier.md) (dossier de l'atelier),
  [0032](../adr/0032-gabarits-composes-dans-une-ouverture.md) (ouverture, proposé).

## 0. D'où l'on part

Aujourd'hui un gabarit (le Caisson) **crée un Ensemble ordinaire puis disparaît** (ADR 0010).
Ensuite, on modifie le meuble comme tout ensemble : cotes globales, distances « fixe / non fixe »,
retouches à la main. Un gabarit coûte : un module de règles (`core`), une commande, un panneau
écrit à la main, une icône.

Ce choix de départ conditionne tout le reste : il rend les meubles simples à retoucher, mais un
meuble « oublie » d'où il vient.

## 1. Intégrer facilement de nouveaux gabarits

**P1 — Coût de chaque gabarit.** Avec un panneau écrit à la main par gabarit, cinq gabarits font
cinq panneaux à maintenir, à tester et à garder cohérents (même ordre des champs, mêmes messages,
même aperçu). Plus il y a de gabarits, plus l'interface dérive.

**P2 — Décrire les paramètres d'un gabarit.** Pour générer le panneau automatiquement, il faut
décrire chaque paramètre (type, unité, bornes, défaut, libellé, avancé ou non). Mais certaines
règles portent sur plusieurs champs à la fois (« l'étagère doit tenir », « le pied plus étroit que
la moitié du plateau ») : elles ne se décrivent pas par des bornes simples et resteront du code.

**P3 — Paramètres qui dépendent les uns des autres.** Exemple : changer l'épaisseur des panneaux
change le nombre maximal d'étagères ; choisir « sans fond » fait disparaître trois champs. Un
panneau générique gère mal ces cas, un panneau à la main les gère bien.

**P4 — Gabarits qui s'emboîtent.** Une porte ou un tiroir a besoin des cotes d'un autre meuble
(l'ouverture). Une bibliothèque peut contenir des caissons. Il faut savoir qui commande qui, et ce
qui se passe si le meuble hôte change ensuite (ADR 0032 proposé).

**P5 — Changer la structure après coup.** Passer de 1 à 3 étagères ou de 2 à 3 travées après
création n'est pas possible (ADR 0010) : il faut relancer le gabarit et on perd ses retouches. C'est
la contrepartie d'un gabarit qui disparaît. L'inverse (un gabarit qui reste vivant) écrase les
retouches et complique beaucoup FreeCAD (créer et supprimer des objets pendant un recalcul).

## 2. Garder une interface simple

**P6 — Nombre de boutons.** Un bouton par gabarit encombre la barre d'outils, déjà chargée
(pièces, assemblages, ensembles, débit). Un seul bouton qui ouvre un choix ajoute un clic.

**P7 — Nombre de champs.** Un gabarit réaliste a 10 à 20 paramètres (épaisseurs, jeux, débords,
assemblages, matériaux). Tout montrer décourage le débutant ; tout cacher frustre le menuisier
expérimenté, qui veut ses jeux.

**P8 — Vocabulaire et valeurs par défaut.** Le menuisier raisonne en « table de 1,60 », « caisson
bas de cuisine 60 », pas en paramètres. De bonnes valeurs par défaut et des tailles usuelles font
l'essentiel de la simplicité, mais elles varient d'un atelier à l'autre (normes cuisine, habitudes).

**P9 — Deux façons de modifier un meuble.** Après création, le meuble se modifie par le panneau de
l'Ensemble (cotes hors tout), pas par le panneau du gabarit (nombre d'étagères…). L'utilisateur peut
chercher à « rouvrir le gabarit » et ne pas le trouver. Il faut l'expliquer ou le permettre.

**P10 — Placement.** Où apparaît le meuble créé : à l'origine, contre la pièce sélectionnée (comme
une pièce neuve en J6), dans le caisson sélectionné (porte, tiroir) ? Plus c'est automatique, plus
il y a de cas à expliquer quand le résultat surprend.

## 3. Ajouter un gabarit personnalisé

Trois besoins différents se cachent derrière « gabarit personnalisé » :

**P11 — « Mes valeurs »** : le même gabarit avec mes épaisseurs, mes matériaux, mes jeux
(« caisson cuisine 60 »). Le plus fréquent et le plus simple : il suffit de mémoriser des valeurs.
Question : où les ranger pour les retrouver sur une autre machine (dossier de l'atelier, ADR 0031) ?

**P12 — « Mon meuble »** : un meuble dessiné une fois, à réutiliser à d'autres cotes. La difficulté
est de dire **comment il se déforme** : quelles pièces s'allongent, lesquelles gardent leur taille,
lesquelles se déplacent. L'atelier a déjà la réponse pour un ensemble (distances fixes ou non,
proportionnel), mais ce réglage demande de la rigueur au menuisier ; un réglage oublié donne un
meuble déformé de façon inattendue.

**P13 — Nombre variable** : « mon meuble, mais avec n étagères » ou « n tiroirs ». Un meuble dessiné
ne sait pas répéter une pièce. Il faut soit des règles de répétition (complexe à exprimer sans
programmer), soit du code Python.

**P14 — Format et sécurité.** Un gabarit personnel doit se partager (collègue, futur SaaS). Les
options :
- un **fichier de description** (JSON) : léger, lisible, vérifiable avant ouverture, sans code
  exécuté ; mais il ne sait décrire que ce qu'on a prévu ;
- un **fichier FreeCAD modèle** (`.FCStd`) : fidèle, rien à inventer ; mais lourd, lié à la version de
  FreeCAD, impossible à vérifier avant de l'ouvrir, et il peut contenir des objets d'autres addons ;
- du **code Python** : tout est possible ; mais exécuter un fichier reçu est un risque réel, à réserver
  aux addons installés volontairement.

**P15 — Évolution.** Un gabarit personnel enregistré aujourd'hui doit encore s'ouvrir quand
l'atelier évolue (nouveaux assemblages, paramètres renommés). Il faut une version du format et des
règles de compatibilité, comme pour `materiaux.json`.

**P16 — Lien avec les autres chantiers.** Dossier de l'atelier et préférences (#148, ADR 0031),
quincaillerie (#159 : un tiroir sans coulisse est incomplet), export d'échange et SaaS (#151 : un
même format de description servirait aux deux), plans cotés (#153).

## 4. Les choix qui en découleront

Une fois les problématiques partagées, il restera à trancher, dans cet ordre :

1. Le gabarit reste-t-il « générateur qui disparaît » (P5, P9), ou faut-il un moyen de rouvrir ou
   régénérer un meuble ?
2. Un seul point d'entrée avec un choix visuel, ou un bouton par gabarit (P6) ?
3. Quels champs montrer d'emblée, lesquels replier (P7, P8) ?
4. Quel besoin personnel d'abord : « mes valeurs », « mon meuble », « nombre variable » (P11 à P13) ?
5. Quel format pour les gabarits personnels (P14, P15) ?
6. Faut-il bâtir le socle commun (description des paramètres, panneau unique) avant les nouveaux
   gabarits, ou après les premiers (P1 à P3) ?
