"""Tests de la pipeline existante — DOIVENT rester verts après vos ajouts.

C'est un test de **non-régression** : si vous cassez la pipeline initiale
en ajoutant votre nouvelle source, ces tests sautent et vous le saurez tout
de suite.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from src.models import Mesure, Produit
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

    monkeypatch.setattr("src.pipeline_existante.MESURES_CSV", csv_path)
    monkeypatch.setattr("src.pipeline_existante.get_session", _get_session_for_test)

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


def test_main_lance_les_deux_ingestions_et_affiche_les_compteurs(monkeypatch, capsys):
    """Le point d'entree appelle produits + mesures et affiche les deux comptes."""
    monkeypatch.setattr("src.pipeline_existante.init_db", lambda: None)
    monkeypatch.setattr("src.pipeline_existante.ingest_produits", lambda: 3)
    monkeypatch.setattr("src.pipeline_existante.ingest_mesures", lambda: 7)

    main()

    captured = capsys.readouterr()
    output = captured.out
    assert "3 produit(s)" in output
    assert "7 mesure(s)" in output


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

    monkeypatch.setattr("src.pipeline_existante.MESURES_CSV", csv_path)
    monkeypatch.setattr("src.pipeline_existante.get_session", _get_session_for_test)

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
