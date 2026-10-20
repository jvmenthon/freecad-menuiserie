# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages du document : base commune (:mod:`.base`), un module par type, fabriques
(:mod:`.factories`).

Ce paquet n'importe rien : FreeCAD importe chaque module de proxy par son chemin à la
réouverture d'un document, et :mod:`..machined_part` dépend de :mod:`.base` alors que les
fabriques dépendent de :mod:`..machined_part`.
"""
