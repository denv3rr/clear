from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, JSON
from sqlalchemy.orm import relationship
from core.database import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    client_uid = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    risk_profile = Column(String)
    risk_profile_source = Column(String, default="auto")
    active_interval = Column(String, default="1M")
    tax_profile = Column(JSON, default=dict)
    extra = Column(JSON, default=dict)

    accounts = relationship(
        "Account",
        back_populates="client",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_uid = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    account_type = Column(String)
    current_value = Column(Float, default=0.0)
    active_interval = Column(String, default="1M")
    ownership_type = Column(String, default="Individual")
    custodian = Column(String, default="")
    tags = Column(JSON, default=list)
    tax_settings = Column(JSON, default=dict)
    holdings_map = Column(JSON, default=dict)
    lots = Column(JSON, default=dict)
    manual_holdings = Column(JSON, default=list)
    extra = Column(JSON, default=dict)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"))

    client = relationship("Client", back_populates="accounts")
    holdings = relationship(
        "Holding",
        back_populates="account",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    quantity = Column(Float)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"))

    account = relationship("Account", back_populates="holdings")
    lots = relationship(
        "Lot",
        back_populates="holding",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class Lot(Base):
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True, index=True)
    purchase_date = Column(Date)
    purchase_price = Column(Float)
    quantity = Column(Float)
    holding_id = Column(Integer, ForeignKey("holdings.id", ondelete="CASCADE"))

    holding = relationship("Holding", back_populates="lots")
