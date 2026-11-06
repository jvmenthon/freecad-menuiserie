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

## 5. Pistes de jv (2026-11-05 et 2026-11-06), à approfondir

### 5.1 Gabarit personnel : local ou par le SaaS et l'IA

Idée de jv : on sélectionne un ensemble. S'il est **fixe**, il est enregistré tel quel, en local.
Si on veut quelque chose de **modulaire**, on passe par le cloud : l'IA propose des dimensions
personnalisées que l'utilisateur accepte ou refuse. Tout se passe dans l'interface de FreeCAD, par
des appels REST.

Problématiques soulevées :

- **P17 — Format de règles d'abord.** L'IA ne peut proposer que ce que le format sait dire. Elle
  renvoie une **description** (paramètres, bornes, répétitions), jamais du code ; `core` la revalide
  entière avant l'aperçu.
- **P18 — Fiabilité.** Propositions fausses possibles (jeux absurdes, pièces qui se traversent) :
  tout est revalidé par les règles de l'atelier. Deux demandes identiques donnent deux réponses :
  on enregistre le résultat accepté, on ne le regénère pas.
- **P19 — Confidentialité.** Les plans de clients partent dans le cloud : consentement explicite,
  affichage de ce qui est envoyé, RGPD.
- **P20 — Hors ligne et Addon Manager.** Sans connexion, pas de mode modulaire par l'IA. Un addon
  libre qui appelle un service payant doit rester utile sans lui ; l'appel réseau est volontaire.
- **P21 — Technique.** Appels asynchrones (réseau Qt) pour ne pas figer FreeCAD, réponses bornées
  en taille, jeton hors des préférences en clair, format versionné des deux côtés.
- **P22 — Coût.** Chaque appel coûte : quotas liés à l'abonnement.

### 5.2 Éditeur de règles local

Piste : quatre verbes, pas de langage de programmation.

1. **Suivre** : chaque pièce s'étire, se déplace ou ne bouge pas quand le meuble change de taille.
   C'est le « fixe / non fixe » des distances de l'Ensemble (ADR 0008, 0009), montré par un cadenas
   sur chaque face dans la vue 3D.
2. **Répéter** : une pièce (et ses assemblages) se répète entre deux autres, par un nombre ou un
   espacement maximal (« un montant au moins tous les 600 mm »).
3. **Exposer** : une valeur devient un paramètre nommé, avec bornes et défaut.
4. **Optionnel** : une pièce ou un groupe peut être coché ou décoché (socle, entretoise).

Parcours : clic droit sur l'ensemble → « Créer un gabarit… » → panneau en trois étapes (cotes,
répétitions et options, paramètres et essai avec curseurs et aperçu). Les règles « Suivre » sont
pré-remplies d'après la géométrie. Champ « formule » facultatif et replié : paramètres nommés et
quatre opérations, évalué par `core`, sans exécuter de code. Pas de conditions, de solveur ni de
script. L'IA du SaaS (§ 5.1) pré-remplirait ces mêmes règles.

### 5.3 Couleurs par rôle (demande de jv, 2026-11-06)

Dans l'éditeur de règles, chaque pièce prend une **couleur selon son rôle** : totalement fixe, qui
se redimensionne, qui se déplace, qui se répète, optionnelle. Une légende dans le panneau.

Problématiques :

- **P23 — Couleur du matériau.** Décision de jv (2026-10-20) : la couleur d'une pièce suit toujours
  son matériau. Les couleurs de rôle ne sont donc qu'un **affichage temporaire** pendant
  l'éditeur, rétabli à la fermeture, et posé hors transaction pour ne pas créer d'entrée
  d'annulation (même mécanisme que la transparence en édition, PR #132).
- **P24 — Rôles cumulés.** Une étagère peut à la fois se répéter et s'étirer. Il faut une règle
  d'affichage. **Tranché par jv (2026-11-06) : une couleur (rôle principal) plus un marqueur**
  (contour, icône) pour le rôle cumulé.
- **P25 — Lisibilité.** Palette lisible par les daltoniens et sur fond clair comme sombre ;
  cinq couleurs au plus ; la légende donne aussi le nom du rôle.
- **P26 — Pièces non fixes « par axe ».** Une pièce peut s'étirer en largeur et rester fixe en
  hauteur. La couleur dit « elle bouge » ; le détail par face reste porté par les cadenas.

### 5.4 Emplacement des gabarits (exigence de jv, 2026-11-06)

Les gabarits personnels doivent être **utilisables dans différents projets**. Complément de jv
(même jour) : on doit pouvoir **choisir** d'enregistrer un gabarit **pour le projet seul**, puis, si
on le souhaite, **le rendre disponible pour les autres projets**. Deux portées donc :

**Décision de jv (2026-11-06) : dans un premier temps, seule la portée globale (atelier) est
livrée.** La portée « projet » et les commandes de copie restent décrites pour plus tard ; le
format est choisi pour qu'elles s'ajoutent sans migration.

- Gabarits intégrés : livrés avec l'atelier (code de `core/templates/`).
- Gabarits personnels : `<dossier de l'atelier>/gabarits/`, un fichier par gabarit plus sa
  vignette. Le dossier de l'atelier (ADR 0031, issue #148) contient déjà `materiaux.json` et
  `dimensions.json` ; on peut le placer dans un dossier synchronisé pour le retrouver sur plusieurs
  machines. Partager un gabarit = copier son fichier (puis, plus tard, par le SaaS).
- *(Plus tard)* Gabarits du projet : rangés **dans le document `.FCStd`**, même format que dans le dossier de
  l'atelier. Ils voyagent avec le fichier (un collègue qui l'ouvre les a). Commande « Rendre
  disponible pour les autres projets » : copie le gabarit dans le dossier de l'atelier.
  L'inverse (« Copier dans ce projet ») sert à envoyer un projet avec ses gabarits.
- Un meuble créé ne dépend pas du fichier : modifier ou supprimer un gabarit ne change pas les
  meubles déjà faits (ADR 0010) ; l'ensemble ne garde que le nom du gabarit (`Template`).

Problématique : **P27 — Dépendance.** Ce rangement suppose le dossier de l'atelier de l'ADR 0031
(proposé, non livré). Soit il est livré avant les gabarits personnels, soit ceux-ci utilisent en
attendant un dossier par défaut `<données utilisateur FreeCAD>/Menuiserie/gabarits/`, repris
ensuite par le réglage.

Problématiques des deux portées (P28 à P31 : pour le lot « portée projet », plus tard) :

- **P28 — Rangement dans le document.** Un fichier joint au document (`App::PropertyFileIncluded`,
  inclus dans le `.FCStd`) porté par un objet caché « Gabarits du projet » ; ou un texte JSON dans une
  propriété. Cet objet ne crée aucune forme : les autres ateliers l'ignorent (ADR 0007). Il ne
  contredit pas l'ADR 0010 : il garde la **définition** du gabarit, pas un générateur vivant.
- **P29 — Doublons de nom.** Un gabarit du projet et un de l'atelier peuvent porter le même nom ;
  à la copie, demander « remplacer / renommer », et dans la galerie afficher la portée (« Projet »,
  « Atelier »).
- **P30 — Versions divergentes.** Après copie, les deux exemplaires vivent séparément ; modifier
  l'un ne change pas l'autre. Faut-il le signaler (date, numéro de version du gabarit) ?
- **P31 — Ouverture par une version plus ancienne de l'atelier** ou sans l'atelier : le document
  s'ouvre, l'objet caché est ignoré, les meubles restent intacts.

