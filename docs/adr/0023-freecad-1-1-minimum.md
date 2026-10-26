# ADR 0023 — FreeCAD 1.1 minimum

- Statut : **accepté** (demande de jv le 2026-10-26 : « Supprime la compatibilité avec FreeCAD 1.0 »)
- Date : 2026-10-26
- ADR liés : [0001 — Structure de l'atelier](0001-structure-de-l-atelier.md) (point 3 remplacé)

## Contexte

L'ADR 0001 visait FreeCAD ≥ 1.0. La CI testait donc chaque changement sur 1.0 et 1.1, et
plusieurs vérifications de compatibilité (ADR 0011, 0013) devaient être refaites sur les deux
versions. jv utilise FreeCAD 1.1 ; la 1.0 n'est plus une cible.

## Décision

1. La version minimale de FreeCAD est **1.1** (`<freecadmin>1.1.0</freecadmin>` dans
   `package.xml`) ; l'Addon Manager ne propose plus l'atelier aux versions antérieures.
2. La CI d'intégration et de chargement dans l'interface ne tourne plus que sur FreeCAD 1.1.
3. Python ≥ 3.10 et la compatibilité Qt 5 / Qt 6 sont **inchangés** : FreeCAD 1.1 existe encore
   en Qt 5 sur certaines distributions Linux, les deux replis Qt (`event.position()` /
   `event.pos()`, énumérations PySide6 / PySide2) restent donc.
4. Le code ne contenait aucun contournement propre à la 1.0 : seuls les commentaires qui la
   citaient sont mis à jour. Les précautions des vérifications d'interface (ramasse-miettes
   suspendu, formulaire non gardé entre deux panneaux), introduites pour des plantages vus
   en 1.0, sont gardées : elles ne coûtent rien et protègent d'une régression.

## Conséquences

- Une CI plus courte (un job d'intégration au lieu de deux).
- Les ADR et le journal des modifications antérieurs gardent leurs mentions de la 1.0 : ils
  décrivent ce qui était vérifié à leur date.
- Un utilisateur sur FreeCAD 1.0 doit passer à la 1.1.
