# ADR 0070 — Entraxe maximal des tourillons et des lamellos, réglable et gardé par l'assemblage

- Statut : **proposé** (2026-11-26, à valider par jv)
- Date : 2026-11-26
- Complète : [0069 — Configuration de l'atelier](0069-configuration-de-l-atelier-modules-et-dossier.md)
- ADR liés : 0007 (compatibilité des documents), 0033 (quincaillerie : faux tenons et lamellos)

## Contexte

Le nombre automatique de tourillons (`Count` = 0) découle d'un entraxe maximal fixe,
`MAX_SPACING_MM` = 128 mm dans `core/joints/dowels.py`. Les faux tenons et les lamellos
(`core/joints/slots`) suivent la même règle avec deux autres constantes : `AUTO_SPACING_MM`
= 150 mm entre deux mortaises et `AUTO_EDGE_MM` = 50 mm du bord à la première.

Le lot CA-b affiche le réglage « Entraxe maximal des tourillons » sans le lire : le nombre est
recalculé à chaque recalcul du document. Lire la préférence à ce moment-là ferait changer en
silence le nombre de tourillons des meubles déjà dessinés dès qu'on modifie le réglage, et un
même fichier donnerait un résultat différent d'un poste à l'autre.

## Décision

1. **Le noyau reçoit l'entraxe en paramètre.** `DowelParams` gagne `max_spacing` (mm, 0 =
   valeur historique 128 mm) ; `SlotParams` gagne `max_spacing` (0 = 150 mm) et le bord
   automatique reste `AUTO_EDGE_MM`. `auto_count` et `_auto_count` prennent l'entraxe en
   argument : plus de constante lue en dur. Bornes : 10 à 1 000 mm, comme le réglage.
2. **La valeur est copiée dans l'assemblage à sa création.** Propriété `MaxSpacing` (catégorie
   avancée, visible dans l'éditeur de propriétés) sur les assemblages tourillons, faux tenons
   et lamellos. La commande de création y écrit le réglage de l'atelier ; le recalcul ne lit
   que la propriété. Changer le réglage ne touche que les assemblages créés ensuite.
3. **Compatibilité (ADR 0007).** Un document plus ancien n'a pas la propriété : elle est
   ajoutée à l'ouverture avec 0, donc l'entraxe historique (128 / 150 mm) et le même nombre de
   tourillons ou de lamellos qu'avant. Une version plus ancienne de l'atelier ignore la
   propriété et retombe aussi sur la constante.
4. **Réglages.** « Entraxe maximal des tourillons » (`DowelMaxSpacing`, 128 mm) devient lu ; un
   réglage « Entraxe maximal des lamellos et faux tenons » (`SlotMaxSpacing`, 150 mm) est
   ajouté au groupe Assemblages, avec « Dernier utilisé » comme les autres réglages
   d'assemblage. Un nombre saisi à la main (`Count` > 0) reste prioritaire.
5. **Panneau de l'assemblage.** Pas de nouveau champ dans le panneau de tâche (jv pourra le
   demander) : l'entraxe se règle dans les préférences, ou dans la propriété avancée pour un
   assemblage déjà créé.

## Conséquences

- Les documents existants s'ouvrent à l'identique ; le nombre automatique ne change que pour
  les assemblages créés après une modification du réglage.
- Les gabarits gardent leurs propres choix (ADR 0069 point 4) : ils créent leurs assemblages
  avec `MaxSpacing` = 0, donc l'entraxe historique.
- Une propriété de plus par assemblage tourillons ou lamellos, sans effet sur les autres types.
- Tests : `auto_count` avec plusieurs entraxes, propriété absente (ancien document),
  propriété écrite à la création depuis le réglage, nombre inchangé quand le réglage change
  après coup.
