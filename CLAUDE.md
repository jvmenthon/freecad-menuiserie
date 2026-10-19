# Atelier FreeCAD « Menuiserie »

Workbench FreeCAD (≥ 1.0) de menuiserie paramétrique. Langue du projet : français
(docs, messages utilisateur, commits) ; identifiants de code en anglais.

- Règles de code, FreeCAD et git : voir `CONTRIBUTING.md` (à respecter strictement).
- Décisions d'architecture : `docs/adr/`. Toute décision structurante passe par un nouvel ADR.
- Rôles : `.claude/agents/` (architecte → dev → testeur ∥ securite → reviewer). Seul un humain fusionne.
- Vérifications avant toute PR :
  `ruff check . && ruff format --check . && mypy freecad tests && pytest tests/unit`
