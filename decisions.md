# Decisions — Binôme `Joelle` × `Celia` (M3-B2 Acerox)

> Document à compléter à 2 pendant la phase sync (15 min avant de coder).
> Servira de référence pendant la phase async + RDV vendredi.

## 1. Source choisie pour l'ingestion

> Quelle source intégrez-vous en M3-B2 ? Argumentez en 3 lignes max.

**Choix** : 
* [x] `capteurs_iot.csv` (CSV ~51k lignes)
* [ ] `erp_export.json` (JSON ~2k ordres)

**Argument** :
- Métier: source de données pertinentes pour anticiper les phases de maintenance
- Volume : source avec un volume de données important (~51k mesures), ce qui permettra d'alimenter le modèle avec une granularité plus fine.
- Type : donnée structurée de type CSV

**Choix de la BDD: SQLite**
- Axe 1 — Nature de la donnée
SQLite : choisi car données structurées (lignes/colonnes) → besoin de schéma fixe et contraintes
- Axe 2 — Motif d’accès
SQLite : OLTP léger (insertions + lectures simples)
- Axe 3 — Volume & fraîcheur
SQLite : volume faible (<1 Go)
- Axe 4 — Échelle 
SQLite : pas de contrainte technique → solution la plus simple et suffisante

Quand MongoDB?
données semi‑structurées (JSON imbriqué)

Quand Parquet?
Donnée structurée, avec faible stockage, mais pour le requetage et une mise à jour régulière des données, il vaut mieux utiliser un OLTP léger (SQLite).


## 2. Stratégie de gestion des doublons et des manquants

**Choix** : Suppression des doublons durant l'ingest. On garde le dernier.

**Argument** : Les doublons sont détectés sur la clé "timestamp"-"sensor_id". Le traitement est fait durant l'ingest lors du traitement des données. En gardant le dernier, on conserve la dernière donnée insérée dans le fichier.

**Choix** : Conservation des manquants.

**Argument** : Les manquants sont actuellement présents sur la donnée vibration ("vibration_mms") et représentent 1.5% des données. Ils sont donc peu représentatifs. En DB ils ont d'abord été géré en acceptant le null, puis nous avons décidé de remplacer la valeur manquante par la médiane. Malgré le traitement, si un absent est encore présent, il sera supprimé et loggué en warning lors de l'ingestion. Ainsi, nous avons choisis de conserver les lignes contenant des manquants (vibration_mms), mais nous préconisons de vérifier à l'entrainement s'il est pertinent de les conserver ou s'il vaut mieux les supprimer.


## 3. Stratégie de tests

> Quels 3 tests minimum allez-vous écrire ?

1. Migration appliquée → la table existe : ...
2. Ingestion d'un fichier valide → N lignes insérées sans doublon : ...
3. Ingestion fichier malformé → exception claire, BDD inchangée : ...

## 4. Convention binôme

- Driver / Navigator switch toutes les **30 min** : oui
- Tous les commits significatifs ont `Co-authored-by:` : oui 
- Branche perso ou main partagée : main partagée

## 5. Conformité au contrat de données

> Confrontez votre livraison à `ressources/contrat_donnees_modele.md`. Pour
> chaque clause de qualité **honorée** : laquelle, comment, et **où** dans le
> code. (Documenté ici — c'est ce que vous montrez au RDV vendredi.)

| Clause du contrat | Honorée ? | Comment / où dans le code |
|---|---|---|
| Unicité respectée (ingestion idempotente) | ☐ | ... |
| Manquants traités explicitement | ☐ | ... |
| Capteur défaillant Roubaix L3 : repéré + décision tracée (écarter / marquer / aval) *(option A)* | ☐ / s.o. | ... |
| `ouvrier_id` hashé ou retiré, jamais en clair *(option B)* | ☐ / s.o. | ... |
| Types conformes (DateTime, numériques typés) | ☐ | ... |

---

*Décisions tracées par le binôme `Joelle` × `Célia` — `01/07/2026`.*
