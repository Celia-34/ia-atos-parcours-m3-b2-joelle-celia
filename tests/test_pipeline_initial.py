"""Tests de la pipeline existante — DOIVENT rester verts après vos ajouts.

C'est un test de **non-régression** : si vous cassez la pipeline initiale
en ajoutant votre nouvelle source, ces tests sautent et vous le saurez tout
de suite.
"""
from __future__ import annotations
import pytest
import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from src.models import Base, Mesure, Produit
from src.pipeline_existante import ingest_mesures, main


def test_produits_table_exists(tmp_engine):
    """La table produits existe après création du schéma."""
    with tmp_engine.connect() as connection:
        inspector_tables = list(tmp_engine.dialect.get_table_names(connection))
    assert "produits" in inspector_tables


def test_mesures_table_exists(tmp_engine):
    """La table mesures_iot existe apres creation du schema."""
    with tmp_engine.connect() as connection:
        inspector_tables = list(tmp_engine.dialect.get_table_names(connection))
    assert "mesures_iot" in inspector_tables


def test_produits_schema_attendu(tmp_session):
    """Les colonnes attendues de produits sont présentes."""
    # Insertion test
    p = Produit(produit_ref="TEST-01", nom="Test", categorie="aluminium", unite="kg")
    tmp_session.add(p)
    tmp_session.commit()

    # Lecture
    result = tmp_session.execute(select(Produit).where(Produit.produit_ref == "TEST-01")).scalar_one()
    assert result.nom == "Test"
    assert result.categorie == "aluminium"
    assert result.unite == "kg"


def test_mesures_schema_attendu(tmp_session):
    """Les colonnes Mesure acceptent une insertion conforme (vibration non nullable)."""
    m = Mesure(
        timestamp=pd.Timestamp("2026-04-01T00:00:00").to_pydatetime(),
        site="Lyon",
        line_id=1,
        sensor_id="SLYO-L1-T01",
        temperature_c=72.4,
        vibration_mms=3.2,
        debit_uh=105.8,
    )
    tmp_session.add(m)
    tmp_session.commit()

    result = tmp_session.execute(
        select(Mesure).where(
            Mesure.timestamp == pd.Timestamp("2026-04-01T00:00:00").to_pydatetime(),
            Mesure.sensor_id == "SLYO-L1-T01",
        )
    ).scalar_one()

    assert result.site == "Lyon"
    assert result.line_id == 1
    assert result.vibration_mms == 3.2


def test_ingest_mesures_normalise_dedoublonne_et_loggue_manquants(tmp_engine, tmp_path, monkeypatch, caplog):
    """L'ingestion Mesure applique typage, imputation médiane et dédoublonnage."""
    csv_path = tmp_path / "capteurs_iot_test.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-04-01T00:00:00",
                "site": "Lyon",
                "line_id": "1",
                "sensor_id": "SLYO-L1-T01",
                "temperature_c": "70.5",
                "vibration_mms": "5.2",
                "debit_uh": "101.0",
            },
            {
                "timestamp": "2026-04-01T00:00:00",
                "site": "Lyon",
                "line_id": "1",
                "sensor_id": "SLYO-L1-T01",
                "temperature_c": "70.5",
                "vibration_mms": "5.2",
                "debit_uh": "101.0",
            },
            {
                "timestamp": "2026-04-01T00:01:00",
                "site": "Roubaix",
                "line_id": "2",
                "sensor_id": "SROU-L2-T01",
                "temperature_c": "65.1",
                "vibration_mms": "",
                "debit_uh": "98.4",
            },
            {
                "timestamp": "2026-04-01T00:02:00",
                "site": "Roubaix",
                "line_id": "2",
                "sensor_id": "SROU-L2-T01",
                "temperature_c": "",
                "vibration_mms": "4.7",
                "debit_uh": "98.4",
            },
        ]
    ).to_csv(csv_path, index=False)

    def _get_session_for_test():
        Session = sessionmaker(bind=tmp_engine, expire_on_commit=False, autoflush=False)
        return Session()

    monkeypatch.setattr("src.ingest_mesures.MESURES_CSV", csv_path)
    monkeypatch.setattr("src.ingest_mesures.get_session", _get_session_for_test)

    inserted = ingest_mesures()

    assert inserted == 2
    assert "valeur(s) manquante(s)" in caplog.text
    assert "doublon(s) supprim" in caplog.text

    session = _get_session_for_test()
    try:
        rows = session.execute(select(Mesure).order_by(Mesure.timestamp, Mesure.sensor_id)).scalars().all()
        assert len(rows) == 2
        assert isinstance(rows[0].line_id, int)
        assert isinstance(rows[0].temperature_c, float)
        assert rows[1].vibration_mms == 5.2
    finally:
        session.close()


def test_main_lance_les_deux_ingestions_et_affiche_les_compteurs(tmp_engine, monkeypatch, caplog):
    """Le point d'entree appelle produits + mesures et affiche les deux comptes."""

    def _get_session_for_test():
        Session = sessionmaker(bind=tmp_engine, expire_on_commit=False, autoflush=False)
        return Session()

    # Créer les tables
    from src.db import engine as prod_engine
    def init_db_test():
        Base.metadata.create_all(tmp_engine)

    monkeypatch.setattr("src.pipeline_existante.init_db", lambda: None)
    monkeypatch.setattr("src.pipeline_existante.ingest_produits", lambda: 3)
    monkeypatch.setattr("src.pipeline_existante.ingest_mesures", lambda: 7)
    monkeypatch.setattr("src.pipeline_existante.get_session", _get_session_for_test)

    main()

    assert "3 produit(s)" in caplog.text
    assert "7 mesure(s)" in caplog.text


def test_ingest_mesures_est_idempotente(tmp_engine, tmp_path, monkeypatch):
    """Deux executions successives sur le meme CSV ne doivent pas dupliquer."""
    csv_path = tmp_path / "capteurs_iot_idempotent.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-04-01T00:00:00",
                "site": "Lyon",
                "line_id": "1",
                "sensor_id": "SLYO-L1-T01",
                "temperature_c": "70.5",
                "vibration_mms": "5.2",
                "debit_uh": "101.0",
            },
            {
                "timestamp": "2026-04-01T00:01:00",
                "site": "Roubaix",
                "line_id": "2",
                "sensor_id": "SROU-L2-T01",
                "temperature_c": "65.1",
                "vibration_mms": "",
                "debit_uh": "98.4",
            },
        ]
    ).to_csv(csv_path, index=False)

    def _get_session_for_test():
        Session = sessionmaker(bind=tmp_engine, expire_on_commit=False, autoflush=False)
        return Session()

    monkeypatch.setattr("src.ingest_mesures.MESURES_CSV", csv_path)
    monkeypatch.setattr("src.ingest_mesures.get_session", _get_session_for_test)

    inserted_first = ingest_mesures()
    inserted_second = ingest_mesures()

    assert inserted_first == 2
    assert inserted_second == 0

    session = _get_session_for_test()
    try:
        total = session.query(Mesure).count()
        assert total == 2
    finally:
        session.close()

def test_ingest_mesures_fichier_malforme_exception_bdd_inchangee(
    tmp_engine, tmp_path, monkeypatch
    ):
    """Un fichier malformé doit lever une erreur claire et ne rien insérer."""
    csv_path = tmp_path / "capteurs_iot_malforme.csv"

    # CSV malformé : colonne obligatoire sensor_id absente
    pd.DataFrame(
        [
            {
                "timestamp": "2026-04-01T00:00:00",
                "site": "Lyon",
                "line_id": "1",
                # "sensor_id" manquant volontairement
                "temperature_c": "99",
                "vibration_mms": "5.2",
                "debit_uh": "101.0",
            }
        ]
    ).to_csv(csv_path, index=False)

    def _get_session_for_test():
        Session = sessionmaker(bind=tmp_engine, expire_on_commit=False, autoflush=False)
        return Session()

    monkeypatch.setattr("src.ingest_mesures.MESURES_CSV", csv_path)
    monkeypatch.setattr("src.ingest_mesures.get_session", _get_session_for_test)

    with pytest.raises((ValueError, KeyError)):
        ingest_mesures()

    session = _get_session_for_test()
    try:
        total = session.query(Mesure).count()
        assert total == 0
    finally:
        session.close()


def test_ingest_mesures_exclut_valeurs_erratiques_sensor3_roubaix(
    tmp_engine, tmp_path, monkeypatch, caplog
):
    """Les mesures erratiques du capteur 3 de Roubaix sont exclues à l'ingestion."""
    csv_path = tmp_path / "capteurs_iot_erratiques.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-04-01T00:00:00",
                "site": "Roubaix",
                "line_id": "2",
                "sensor_id": "3",
                "temperature_c": "145.0",
                "vibration_mms": "4.2",
                "debit_uh": "100.0",
            },
            {
                "timestamp": "2026-04-01T00:01:00",
                "site": "Roubaix",
                "line_id": "2",
                "sensor_id": "3",
                "temperature_c": "85.0",
                "vibration_mms": "12.0",
                "debit_uh": "99.0",
            },
            {
                "timestamp": "2026-04-01T00:02:00",
                "site": "Roubaix",
                "line_id": "2",
                "sensor_id": "3",
                "temperature_c": "90.0",
                "vibration_mms": "5.0",
                "debit_uh": "98.0",
            },
            {
                "timestamp": "2026-04-01T00:03:00",
                "site": "Lyon",
                "line_id": "1",
                "sensor_id": "3",
                "temperature_c": "150.0",
                "vibration_mms": "5.5",
                "debit_uh": "102.0",
            },
        ]
    ).to_csv(csv_path, index=False)

    def _get_session_for_test():
        Session = sessionmaker(bind=tmp_engine, expire_on_commit=False, autoflush=False)
        return Session()

    monkeypatch.setattr("src.ingest_mesures.MESURES_CSV", csv_path)
    monkeypatch.setattr("src.ingest_mesures.get_session", _get_session_for_test)

    inserted = ingest_mesures()

    assert inserted == 2
    assert "valeurs erratiques du capteur 3 à Roubaix" in caplog.text

    session = _get_session_for_test()
    try:
        rows = session.execute(select(Mesure).order_by(Mesure.timestamp)).scalars().all()
        assert len(rows) == 2
        assert rows[0].site == "Roubaix"
        assert rows[0].sensor_id == "3"
        assert rows[0].temperature_c == 90.0
        assert rows[0].vibration_mms == 5.0
        assert rows[1].site == "Lyon"
        assert rows[1].sensor_id == "3"
        assert rows[1].temperature_c == 150.0
    finally:
        session.close()