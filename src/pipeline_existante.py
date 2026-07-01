"""Pipeline Acerox existante — référentiel produits.

Le binôme **ne doit pas modifier** ce fichier. Il sert de référence :
la pipeline doit continuer de fonctionner après vos ajouts.

Usage::

    python -m src.pipeline_existante
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.db import engine, get_session
from src.models import Base, Mesure, Produit

PRODUITS_CSV: Path = Path(__file__).parent.parent / "data" / "produits.csv"
MESURES_CSV: Path = Path(__file__).parent.parent / "data" / "capteurs_iot.csv"

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Crée toutes les tables déclarées dans `models.Base.metadata`.

    En prod, c'est Alembic qui gère ça. Ici, init brutal pour bootstrap.
    """
    Base.metadata.create_all(engine)


def ingest_produits() -> int:
    """Charge le référentiel produits depuis le CSV vers la table `produits`.

    Idempotent : si un `produit_ref` existe déjà, il n'est pas réinséré.
    Retourne le nombre de produits effectivement insérés.
    """
    df = pd.read_csv(PRODUITS_CSV)
    session = get_session()
    inserted = 0
    try:
        existing_refs = {p.produit_ref for p in session.query(Produit.produit_ref).all()}
        for _, row in df.iterrows():
            if row["produit_ref"] in existing_refs:
                continue
            session.add(
                Produit(
                    produit_ref=row["produit_ref"],
                    nom=row["nom"],
                    categorie=row["categorie"],
                    unite=row["unite"],
                )
            )
            inserted += 1
        session.commit()
    finally:
        session.close()
    return inserted


def ingest_mesures() -> int:
    """Charge les mesures IoT depuis le CSV vers la table `mesures_iot`.

    Normalisation appliquée :
    - typage conforme à la BDD,
    - suppression des doublons sur (timestamp, sensor_id),
    - warning sur les manquants et exclusion des lignes invalides.
    """
    df = pd.read_csv(MESURES_CSV)

    # Typage conforme au modèle SQLAlchemy.
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["line_id"] = pd.to_numeric(df["line_id"], errors="coerce")
    df["temperature_c"] = pd.to_numeric(df["temperature_c"], errors="coerce")
    df["vibration_mms"] = pd.to_numeric(df["vibration_mms"], errors="coerce")
    df["debit_uh"] = pd.to_numeric(df["debit_uh"], errors="coerce")

    required_cols = [
        "timestamp",
        "site",
        "line_id",
        "sensor_id",
        "temperature_c",
        "debit_uh",
    ]

    missing_counts = df[required_cols + ["vibration_mms"]].isna().sum()
    for col, count in missing_counts.items():
        if int(count) > 0:
            logger.warning("Colonne '%s' contient %s valeur(s) manquante(s).", col, int(count))

    # La vibration peut être null selon le contrat; les autres champs obligatoires non.
    before_drop_missing = len(df)
    df = df.dropna(subset=required_cols)
    dropped_missing = before_drop_missing - len(df)
    if dropped_missing > 0:
        logger.warning("%s ligne(s) supprimée(s) à cause de champs obligatoires manquants.", dropped_missing)

    # Suppression des doublons dans le fichier source.
    before_drop_duplicates = len(df)
    df = df.drop_duplicates(subset=["timestamp", "sensor_id"], keep="first")
    dropped_duplicates = before_drop_duplicates - len(df)
    if dropped_duplicates > 0:
        logger.warning("%s doublon(s) supprimé(s) sur (timestamp, sensor_id).", dropped_duplicates)

    session = get_session()
    inserted = 0
    try:
        existing_keys = {(m.timestamp, m.sensor_id) for m in session.query(Mesure.timestamp, Mesure.sensor_id).all()}
        for _, row in df.iterrows():
            key = (row["timestamp"].to_pydatetime(), str(row["sensor_id"]))
            if key in existing_keys:
                continue

            session.add(
                Mesure(
                    timestamp=row["timestamp"].to_pydatetime(),
                    site=str(row["site"]),
                    line_id=int(row["line_id"]),
                    sensor_id=str(row["sensor_id"]),
                    temperature_c=float(row["temperature_c"]),
                    vibration_mms=(
                        None if pd.isna(row["vibration_mms"]) else float(row["vibration_mms"])
                    ),
                    debit_uh=float(row["debit_uh"]),
                )
            )
            inserted += 1
        session.commit()
    finally:
        session.close()

    return inserted


def main() -> None:
    """Init BDD + chargement référentiel produits."""
    init_db()
    n = ingest_produits()
    print(f"Pipeline existante : {n} produit(s) inséré(s) (idempotent — relancer ne duplique pas).")


if __name__ == "__main__":
    main()
