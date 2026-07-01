"""Pipeline Acerox produite par le binôme."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from src.db import get_session
from src.models import Mesure

MESURES_CSV: Path = Path(__file__).parent.parent / "data" / "capteurs_iot.csv"

logger = logging.getLogger(__name__)


def ingest_mesures() -> int:
    """Charge les mesures IoT depuis le CSV vers la table `mesures_iot`.

    Normalisation appliquée :
    - typage conforme à la BDD,
    - imputation des `vibration_mms` manquantes par la médiane de série,
    - suppression des doublons sur (timestamp, sensor_id),
    - warning sur les manquants et exclusion des lignes invalides.
    """
    df: pd.DataFrame = pd.read_csv(MESURES_CSV)

    # Typage conforme au modèle SQLAlchemy.
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["line_id"] = pd.to_numeric(df["line_id"], errors="coerce")
    df["temperature_c"] = pd.to_numeric(df["temperature_c"], errors="coerce")
    df["vibration_mms"] = pd.to_numeric(df["vibration_mms"], errors="coerce")
    df["debit_uh"] = pd.to_numeric(df["debit_uh"], errors="coerce")

    required_cols: list[str] = [
        "timestamp",
        "site",
        "line_id",
        "sensor_id",
        "temperature_c",
        "vibration_mms",
        "debit_uh",
    ]

    # Vérificaiton des valeurs manquantes sur les colonnes obligatoires. Les warnings sont loggés, mais la pipeline continue.
    missing_counts: pd.Series = df[required_cols].isna().sum()
    for col, count in missing_counts.items():
        if int(count) > 0:
            logger.warning(
                "Colonne '%s' contient %s valeur(s) manquante(s).", col, int(count)
            )

    # Remplacement des valeurs manquantes de vibration_mms par la médiane de la série.
    median_raw = df["vibration_mms"].median(skipna=True)
    median_vibration: float | None = (
        float(median_raw) if pd.notna(median_raw) else None
    )
    if median_vibration is not None:
        df["vibration_mms"] = df["vibration_mms"].fillna(median_vibration)
    else:
        logger.warning(
            "Impossible d'imputer vibration_mms: série sans valeur exploitable, "
            "les lignes resteront invalides si vibration_mms est manquante."
        )

    # Tous les champs sont obligatoires
    before_drop_missing: int = len(df)
    df = df.dropna(subset=required_cols)
    dropped_missing: int = before_drop_missing - len(df)
    if dropped_missing > 0:
        logger.warning(
            "%s ligne(s) supprimée(s) à cause de champs obligatoires manquants.",
            dropped_missing,
        )

    # Suppression des doublons dans le fichier source.
    before_drop_duplicates: int = len(df)
    df = df.drop_duplicates(subset=["timestamp", "sensor_id"], keep="last")
    dropped_duplicates: int = before_drop_duplicates - len(df)
    if dropped_duplicates > 0:
        logger.warning(
            "%s doublon(s) supprimé(s) sur (timestamp, sensor_id).", dropped_duplicates
        )

    session: Session = get_session()
    inserted: int = 0
    try:
        existing_keys: set[tuple[datetime, str]] = {
            (m.timestamp, m.sensor_id)
            for m in session.query(Mesure.timestamp, Mesure.sensor_id).all()
        }
        for _, row in df.iterrows():
            key: tuple[datetime, str] = (
                row["timestamp"].to_pydatetime(),
                str(row["sensor_id"]),
            )
            if key in existing_keys:
                continue

            session.add(
                Mesure(
                    timestamp=row["timestamp"].to_pydatetime(),
                    site=str(row["site"]),
                    line_id=int(row["line_id"]),
                    sensor_id=str(row["sensor_id"]),
                    temperature_c=float(row["temperature_c"]),
                    vibration_mms=float(row["vibration_mms"]),
                    debit_uh=float(row["debit_uh"]),
                )
            )
            inserted += 1
        session.commit()
    finally:
        session.close()

    return inserted
