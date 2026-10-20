# Sources des textures intégrées

Toutes les images de ce dossier sont sous licence
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.fr) (domaine public) :
aucune attribution n'est exigée, elle est donnée ici pour la traçabilité.

Préparation commune : carte de couleur seule (la version 1K JPEG de la source),
pivotée de 90° si besoin pour que **le fil suive la largeur de l'image**, réduite à
1024 px de large au plus, réencodée en JPEG progressif (≤ 200 Ko). Aucun recadrage :
les images restent raccordables (*tileable*) comme à la source.

La « taille couverte » est la dimension réelle représentée par l'image entière,
largeur (le long du fil) × hauteur, en mm. Elle vient de la source quand elle est
publiée (ambientCG la donne en cm, Poly Haven en mm) ; sinon elle est **estimée** à
l'œil d'après la largeur des cernes et des veines, et signalée par « ≈ ».

| Fichier | Source | Identifiant | Taille couverte (mm) | Pivotée | Remarque |
|---|---|---|---|---|---|
| `chene.jpg` | Poly Haven | [`oak_veneer_01`](https://polyhaven.com/a/oak_veneer_01) | 1830 × 1830 | oui | placage de chêne, sur dosse |
| `hetre.jpg` | ambientCG | [`Wood095`](https://ambientcg.com/view?id=Wood095) | ≈ 1000 × 500 | non | essence non précisée par la source, aspect proche du hêtre |
| `frene.jpg` | Poly Haven | [`ash_veneer`](https://polyhaven.com/a/ash_veneer) | 1000 × 1000 | non | placage de frêne |
| `noyer.jpg` | ambientCG | [`Wood066`](https://ambientcg.com/view?id=Wood066) | 400 × 400 | non | bois foncé, aspect noyer |
| `merisier.jpg` | ambientCG | [`Wood069`](https://ambientcg.com/view?id=Wood069) | 400 × 400 | non | bois rouge orangé, aspect merisier verni |
| `pin-sylvestre.jpg` | ambientCG | [`Wood092`](https://ambientcg.com/view?id=Wood092) | 800 × 800 | oui | résineux à nœud, photogrammétrie |
| `sapin-epicea.jpg` | ambientCG | [`Wood096`](https://ambientcg.com/view?id=Wood096) | 500 × 500 | oui | résineux clair à nœuds |
| `douglas.jpg` | ambientCG | [`Wood081`](https://ambientcg.com/view?id=Wood081) | ≈ 400 × 400 | oui | essence non précisée, cernes marqués rouge orangé proches du douglas |
| `cp-bouleau.jpg` | ambientCG | [`Wood094`](https://ambientcg.com/view?id=Wood094) | ≈ 600 × 600 | non | face déroulée (motif ondulé de contreplaqué) |
| `cp-peuplier.jpg` | Poly Haven | [`white_maple_veneer`](https://polyhaven.com/a/white_maple_veneer) | 1000 × 1000 | non | placage d'érable blanc, teinte crème proche du peuplier |
| `mdf.jpg` | ambientCG | [`Wood054`](https://ambientcg.com/view?id=Wood054) | 400 × 400 | non | surface fine et uniforme ; aucune photo de MDF disponible en CC0 |
| `melamine-blanc.jpg` | générée | — | indifférente (uni) | — | couleur unie `#F2F1EC`, 64 × 64 px |

Les cartes Poly Haven sont des *albédos* (éclairage neutralisé) : elles paraissent un
peu plus mates que celles d'ambientCG, ce qui convient au rendu FreeCAD.
