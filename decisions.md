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


## 2. Stratégie de gestion des doublons, des manquants et des valeurs erratiques

### Gestion des doublons

**Choix** : Suppression des doublons durant l'ingest. On garde le dernier.

**Argument** : Les doublons sont détectés sur la clé "timestamp"-"sensor_id". Le traitement est fait durant l'ingest lors du traitement des données. En gardant le dernier, on conserve la dernière donnée insérée dans le fichier.

### Gestion des manquants

**Choix** : Conservation des manquants.

**Argument** : Les manquants sont actuellement présents sur la donnée vibration ("vibration_mms") et représentent 1.5% des données. Ils sont donc peu représentatifs. En DB ils ont d'abord été géré en acceptant le null, puis nous avons décidé de remplacer la valeur manquante par la médiane. Malgré le traitement, si un absent est encore présent, il sera supprimé et loggué en warning lors de l'ingestion. Ainsi, nous avons choisis de conserver les lignes contenant des manquants (vibration_mms), mais nous préconisons de vérifier à l'entrainement s'il est pertinent de les conserver ou s'il vaut mieux les supprimer.

### Gestion des valeurs erratiques

**Choix** : Suppression des valeurs erratiques du capteurs 3 sur le site de Roubaix.

**Argument** : Les valeurs erratiques du capteur 3 du site de Roubaix sont très éloignées des autres (T° 140-160 °C, vibration figée à 12.0). Pour ne pas biaiser le jeu de données fournit au modèle, nous avons décidé de les supprimer.

## 3. Stratégie de tests

> Quels 3 tests minimum allez-vous écrire ?

1. Ils vérifient que les tables produits et mesures_iot existent bien dans la base SQLite.
tests/test_pipeline_initial.py::test_produits_table_exists
tests/test_pipeline_initial.py::test_mesures_table_exists

2. Ils vérifient que le modèle fonctionne correctement
tests/test_pipeline_initial.py::test_produits_schema_attendu PASSED
tests/test_pipeline_initial.py::test_mesures_schema_attendu

3. crée un CSV temporaire contenant des lignes valides, un doublon et des valeurs manquantes. Il vérifie que l’ingestion insère uniquement les lignes attendues, que les doublons sont supprimés, que les types sont convertis correctement et que les anomalies sont logguées.
tests/test_pipeline_initial.py::test_ingest_mesures_normalise_dedoublonne_et_loggue_manquants

4. vérifie que le point d’entrée de la pipeline appelle bien les deux ingestions et affiche les bons compteurs.
tests/test_pipeline_initial.py::test_main_lance_les_deux_ingestions_et_affiche_les_compteurs

5. vérifie l’idempotence de l’ingestion
tests/test_pipeline_initial.py::test_ingest_mesures_est_idempotente

6. vérifie que la pipeline réagit correctement quand le fichier CSV d’entrée est malformé
tests/test_pipeline_initial.py::test_ingest_mesures_fichier_malforme_exception_bdd_inchangee

## 4. Convention binôme

- Driver / Navigator switch toutes les **30 min** : oui, et répartition des taches avec relecture croisée
- Tous les commits significatifs ont `Co-authored-by:` : oui 
- Branche perso ou main partagée : main partagée

## 5. Conformité au contrat de données

> Confrontez votre livraison à `ressources/contrat_donnees_modele.md`. Pour
> chaque clause de qualité **honorée** : laquelle, comment, et **où** dans le
> code. (Documenté ici — c'est ce que vous montrez au RDV vendredi.)

| Clause du contrat | Honorée ? | Comment / où dans le code |
|---|---|---|
| Unicité respectée (ingestion idempotente) | [x] | Le pipeline n'insère pas plusieurs fois les memes données. Clé d'unicité des mesures composée de "timestamp"+"sensor_id". Unicité double : en DB (primary_key) et lors de l'ingestion car on supprime les doublons avant insertion en table.|
| Manquants traités explicitement | [x] | Nous avons choisi de conserver les manquants de la donnée vibration_mms (1,5%) par la médiane de la serie. En effet, dans une premier temps nous préconisons de le conserver, et de vérifier si cela est pertinent lors de l'entrainement du modèle. |
| Capteur défaillant Roubaix L3 : repéré + décision tracée (écarter / marquer / aval)  | [x] | Nous avons décidé de supprimer les valeurs erratiques du capteur 3 du site de Roubaix. Le nettoyage est réalisé lors de l'ingestion des données dans ingest_mesures.py |
| Types conformes (DateTime, numériques typés) | [x] | Mapping dans le type des colonnes en DB ainsi que lors de l'ingestion dans ingest_mesures.py |

---

*Décisions tracées par le binôme `Joelle` × `Célia` — `01/07/2026`.*
