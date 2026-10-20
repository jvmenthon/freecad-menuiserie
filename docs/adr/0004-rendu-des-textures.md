# ADR 0004 — Rendu des textures des matériaux

- Statut : accepté (lot J1d)
- Date : 2026-10-20
- Spécification : [docs/specs/J1-piece-de-bois.md](../specs/J1-piece-de-bois.md), § 4.6 et
  critères D1 à D7
- ADR liés : [0002 — Bibliothèque de matériaux](0002-bibliotheque-de-materiaux.md) (champ
  `texture`), [0003 — Modèle de la pièce de bois](0003-modele-de-la-piece-de-bois.md) (repère
  local, sens du fil, contrat de persistance)

## Contexte

jv veut voir les pièces avec « des textures, pas juste une couleur ». Depuis J1a, un matériau
peut déclarer une `texture` : une image (chemin absolu résolu, confiné au dossier de la
bibliothèque) et la taille réelle qu'elle couvre en mm, le fil du bois suivant la largeur de
l'image. Il reste à l'afficher dans la vue 3D de FreeCAD 1.0 et 1.1 :

- à l'**échelle réelle** (une image de 600 mm doit couvrir 600 mm de pièce, quelle que soit sa
  taille) et **dans le sens du fil** de la pièce (`GrainDirection`, relatif au repère local) ;
- sans casser l'ouverture des documents dans `freecadcmd` ni sur une machine qui n'a pas l'image ;
- avec la couleur du matériau comme secours, sans exception.

Options étudiées :

1. **Textures natives de FreeCAD** (`ShapeAppearance` / `App::Material` munis d'une image) : en
   1.0, le code d'application d'une texture 2D de `ViewProviderTextureExtension` est désactivé
   (`#if 0`) et aucune coordonnée de texture n'est générée ; inutilisable aujourd'hui.
2. **`SoTextureCoordinateCube` / `SoTextureCoordinateSphere`** de Coin : projections normalisées sur
   la boîte englobante, donc pas d'échelle réelle (l'image s'étire avec la pièce).
3. **Coordonnées UV par sommet** (`SoTextureCoordinate2`) calculées sur le maillage produit par
   FreeCAD : exactes par face, mais dépendantes de la structure interne du graphe de scène de
   `ViewProviderPartExt`, qui change entre versions, et à recalculer à chaque recalcul.
4. **Nœuds Coin propres à l'atelier** : un `SoTextureCoordinatePlane` (projection plane en
   coordonnées locales) et un `SoTexture2`, insérés par le ViewProvider avant le sélecteur de
   modes d'affichage.

Pour charger l'image : `SoTexture2.filename` dépend de la bibliothèque `simage`, absente de
certaines compilations de Coin ; Qt (`QImageReader`) est toujours présent dans l'interface.

## Décision

1. **Option 4.** Le ViewProvider insère dans `vobj.RootNode`, juste avant `vobj.SwitchNode`, un
   `SoSwitch` nommé `MenuiserieTexture` contenant un `SoTextureCoordinatePlane` propre à la pièce
   et un `SoTexture2` partagé. Projection en mm⁻¹ dans le repère local : S = coordonnée selon
   l'axe du fil / largeur de l'image, T = somme des deux autres coordonnées / hauteur de l'image.
   Parement et chants parallèles au fil sont justes et à l'échelle ; le bois de bout montre une
   bande étirée (limite acceptée). La projection ne dépend ni des cotes ni du `Placement`.
2. **Modèle `MODULATE` sur une couleur diffuse blanche** : la texture garde ses vraies couleurs
   et l'éclairage de la scène (les modèles `DECAL`/`REPLACE` perdraient l'ombrage). Le
   ViewProvider devient seul responsable de la couleur diffuse de `ShapeAppearance` : blanc quand
   une texture est affichée, sinon la couleur du matériau.
3. **Couleur de secours persistée dans une propriété de vue masquée `MaterialColor`**, écrite au
   choix du matériau (instantané, comme la masse volumique de l'ADR 0002) : sans elle, un plan
   ouvert sans l'image, ou sans le matériau, s'afficherait en blanc.
4. **La texture n'est pas enregistrée** dans le document : elle est recalculée depuis la
   bibliothèque locale à l'ouverture (`finishRestoring`) et à chaque changement de `MaterialId` ou
   de `GrainDirection`. Aucune propriété n'est ajoutée à `WoodPart` (`Version` reste 1).
5. **Chargement par Qt dans `gui/` uniquement**, décodeur PNG ou JPEG imposé par l'extension
   (détection automatique désactivée), fichier ≤ 16 Mio contrôlé par `stat` dans `features/`,
   dimensions ≤ 4 096 pixels lues dans l'en-tête avant décodage, conversion en RGB opaque.
6. **Un nœud `SoTexture2` par image**, partagé par toutes les pièces (cache poids-mouche explicite
   et réinitialisable de `gui/textures.py`) : une seule copie en mémoire graphique. Les échecs
   sont mémorisés aussi : un seul avertissement par image et par session.
7. Logique testable hors interface : projection et choix couleur/texture dans `core/appearance.py`,
   contrôle du fichier dans `features/appearance.py` ; `gui/` ne fait que décoder et brancher.

## Conséquences

- Les pièces s'affichent avec leur veinage, à l'échelle et dans le sens du fil, sur FreeCAD 1.0 et
  1.1, sans dépendre de `simage` ni de la structure interne de `ViewProviderPartExt`.
- Les fichiers `.FCStd` restent légers et portables : aucune image embarquée ; sur une autre
  machine, la texture apparaît si la bibliothèque la fournit, sinon la couleur enregistrée.
- Une couleur choisie à la main sur une pièce est remplacée au prochain changement de matériau ou
  à la réouverture : la couleur diffuse appartient au ViewProvider. Une option « utiliser la
  couleur du matériau » (comme dans l'atelier BIM) pourra s'ajouter si le besoin apparaît.
- Toutes les pièces d'un matériau commencent l'image à leur coin d'origine ; le bois de bout n'est
  pas représenté fidèlement. Une projection plus riche (par face, décalage par pièce) pourra
  remplacer celle-ci sans toucher au document, puisque rien de la texture n'y est enregistré.
- Le jour où FreeCAD applique lui-même les textures de `ShapeAppearance`, la bascule ne concerne
  que le ViewProvider ; `MaterialColor` reste la couleur de secours.
- La vérification automatique porte sur le graphe de scène (le rendu hors écran n'est pas garanti
  en CI) ; l'aspect visuel est vérifié à la main sur 1.0 et 1.1 à chaque évolution du rendu.
