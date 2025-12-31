from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from core.database import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    risk_profile = Column(String)

    accounts = relationship("Account", back_populates="client")

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    account_type = Column(String)
    client_id = Column(Integer, ForeignKey("clients.id"))

    client = relationship("Client", back_populates="accounts")
    holdings = relationship("Holding", back_populates="account")

class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    quantity = Column(Float)
    account_id = Column(Integer, ForeignKey("accounts.id"))

    account = relationship("Account", back_populates="holdings")
    lots = relationship("Lot", back_populates="holding")

class Lot(Base):
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True, index=True)
    purchase_date = Column(Date)
    purchase_price = Column(Float)
    quantity = Column(Float)
    holding_id = Column(Integer, ForeignKey("holdings.id"))

    holding = relationship("Holding", back_populates="lots")
