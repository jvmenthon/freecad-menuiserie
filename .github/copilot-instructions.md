# Consignes pour GitHub Copilot : atelier FreeCAD « Menuiserie »

Rédige tes commentaires de revue **en français**.

## Le projet

Atelier (workbench) FreeCAD de menuiserie paramétrique, licence LGPL, **FreeCAD ≥ 1.1**
(ADR 0023). Python 3, Qt par la couche `PySide` de FreeCAD. Règles détaillées :
`CONTRIBUTING.md` ; décisions d'architecture : `docs/adr/` (toute décision structurante
passe par un nouvel ADR). Docs, messages utilisateur et commits en français, identifiants en anglais.

Arborescence : `freecad/menuiserie/core/` (logique pure, aucun import FreeCAD ni Qt),
`features/` (objets du document, aucun import FreeCADGui ni Qt), `gui/` (commandes,
ViewProviders, panneaux). Dépendances `gui → features → core`, jamais l'inverse.

L'atelier doit rester **compatible avec les autres ateliers et addons** (ADR 0007) : solides
valides dans `Shape`, aucun monkey-patching, aucun observateur global laissé en place,
préférences sous `Mod/Menuiserie` seulement, noms `Menuiserie_…` / `Menuiserie::…`, aucune
dépendance hors FreeCAD et bibliothèque standard.

## Classement obligatoire des points

Commence **chaque** commentaire par son niveau :

- **[Bloquant]** : résultat faux, plantage ou blocage de FreeCAD, perte de données, fichier
  `.FCStd` existant illisible, faille de sécurité, violation de la séparation App / Gui.
- **[Majeur]** : comportement gênant mais contournable, règle de `CONTRIBUTING.md` ou d'un
  ADR non respectée, test manquant pour un critère ou un garde-fou, incompatibilité avec un
  autre atelier.
- **[Mineur]** : confort, lisibilité, nommage, docs, dette de test.

Ne signale pas ce que ruff, mypy et pylint contrôlent déjà (format, imports, complexité),
sauf si la CI l'a laissé passer. Pas de remarque de pur goût.

## Grille de revue

1. **Conformité** : la PR fait ce que disent l'issue, la spécification et les ADR cités, ni
   plus ni moins ; un ADR contredit sans nouvel ADR est un point majeur.
2. **Tests** : `tests/unit` (logique pure), `tests/integration` (FreeCAD réel), `tests/qtest`
   (scénarios d'interface). Cas limites (0, juste sous le minimum, au minimum, valeur énorme),
   recalcul, sauvegarde puis réouverture, annuler / rétablir. Ne jamais affaiblir ni
   supprimer un test existant.
3. **Sécurité** : pas de `eval`, `exec`, `compile`, `pickle`, `marshal`, `subprocess`, ni
   d'accès réseau ; données utilisateur lues en JSON et validées ; chemins d'export choisis par
   l'utilisateur, jamais construits depuis le contenu d'un document ; rien d'exécuté à
   l'ouverture d'un `.FCStd` hors restauration des proxies ; aucun secret ; workflows GitHub
   sans injection de `${{ … }}` non fiable dans `run:`.
4. **Bonnes pratiques FreeCAD et pièges connus** : voir
   `.github/instructions/freecad-python.instructions.md`.
5. **Entrées utilisateur** : bornes dans `core/`, aucune boucle sans plafond, champ qui
   recalcule le document en `setKeyboardTracking(False)`, refus traduit et jamais
   d'exception qui remonte dans une boucle Qt.
6. **Conception** : patterns du tableau de `CONTRIBUTING.md` (Proxy FeaturePython, Command,
   Fabrique, Strategy + registre, objets valeur `dataclass(frozen=True)`), pas d'état global,
   pas de duplication de logique, pas de code mort, typage complet.
7. **Versions et docs** : version identique dans `package.xml`, `pyproject.toml` et
   `freecad/menuiserie/__init__.py` ; `CHANGELOG.md` à jour pour toute évolution notable.

## Suivi des points mineurs

Les points bloquants et majeurs sont corrigés dans la PR ; s'il y en a, les mineurs aussi.
Quand il ne reste que des mineurs, ils peuvent être reportés dans
`docs/corrections-mineures.md` (tableau par relecture : n°, niveau, où, problème,
correction proposée). Vérifie qu'une PR qui corrige un mineur listé le retire du fichier.
