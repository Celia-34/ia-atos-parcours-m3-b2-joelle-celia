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
from src.ingest_mesures import ingest_mesures
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
        existing_refs = {
            p.produit_ref for p in session.query(Produit.produit_ref).all()
        }
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


def main() -> None:
    """Init BDD + chargement référentiel produits et mesures."""
    init_db()
    n_produits = ingest_produits()
    n_mesures = ingest_mesures()
    # Fais une requete pour afficher le nombre de produits et mesures existants, pour vérification rapide
    session = get_session()
    try:
        n_produits_existants = session.query(Produit).count()
        n_mesures_existantes = session.query(Mesure).count()
    finally:
        session.close()

    logger.info(
        "Pipeline : "
        f"{n_produits} produit(s) inséré(s), "
        f"{n_mesures} mesure(s) insérée(s) "
        f"({n_produits_existants} produit(s) existant(s), "
        f"{n_mesures_existantes} mesure(s) existante(s)) "
        "(idempotent — relancer ne duplique pas)."
    )


if __name__ == "__main__":
    main()
