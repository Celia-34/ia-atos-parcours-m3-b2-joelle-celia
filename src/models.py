"""Modèles SQLAlchemy — schéma BDD Acerox.

Schéma initial : 1 table `produits` (référentiel produits, déjà
peuplé depuis `data/produits.csv` par `pipeline_existante.py`).

TODO binôme : ajouter ICI le modèle de votre nouvelle table
(`MesuresIoT` ou `OrdresErp` selon votre choix).
"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Produit(Base):
    """Référentiel produits Acerox (table existante, ne pas modifier)."""

    __tablename__ = "produits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    produit_ref = Column(String(20), unique=True, nullable=False, index=True)
    nom = Column(String(100), nullable=False)
    categorie = Column(String(20), nullable=False)  # "aluminium" / "inox"
    unite = Column(String(10), nullable=False, default="kg")

    def __repr__(self) -> str:
        return f"Produit(ref={self.produit_ref!r}, nom={self.nom!r})"

class Mesure(Base):
    """Mesures IoT Acerox destinées au modèle (option A du contrat)."""

    __tablename__ = "measures"
    timestamp = Column(DateTime, primary_key=True, nullable=False, index=True)
    site = Column(String(50), nullable=False)
    line_id = Column(Integer, nullable=False)
    sensor_id = Column(String(50), primary_key=True, nullable=False)
    temperature_c = Column(Float, nullable=False)
    vibration_mms = Column(Float, nullable=False)
    debit_uh = Column(Float, nullable=False)

    def __repr__(self) -> str:
        return (
            "Measure("
            f"timestamp={self.timestamp!r}, "
            f"sensor_id={self.sensor_id!r}, "
            f"site={self.site!r}, "
            f"line_id={self.line_id!r}"
            ")"
        )