from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class Lot(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    qty: float
    basis: float
    timestamp: str

    @field_validator("timestamp")
    def format_timestamp(cls, v):
        if " " in v and "T" not in v:
            parts = v.split()
            if len(parts) >= 2:
                v = parts[0] + "T" + parts[1]
        if len(v) == 10 and "-" in v:
            v = v + "T00:00:00"
        return v


class Account(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    account_id: Optional[str] = Field(None, alias="account_uid")
    account_name: str = Field(..., alias="name")
    account_type: str
    current_value: float = 0.0
    active_interval: str = "1M"
    holdings: Dict[str, float] = Field(default_factory=dict, alias="holdings_map")
    manual_holdings: List[Dict[str, Any]] = Field(default_factory=list)
    lots: Dict[str, List[Lot]] = Field(default_factory=dict)
    ownership_type: str = "Individual"
    custodian: str = ""
    tags: List[str] = Field(default_factory=list)
    tax_settings: Dict[str, Any] = Field(default_factory=dict)
    extra: Dict[str, Any] = Field(default_factory=dict)


class Client(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    client_id: Optional[str] = Field(None, alias="client_uid")
    name: str
    risk_profile: str = "Not Assessed"
    risk_profile_source: str = "auto"
    active_interval: str = "1M"
    tax_profile: Dict[str, Any] = Field(default_factory=dict)
    accounts: List[Account] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)


class AccountPatch(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    account_name: Optional[str] = Field(None, alias="name")
    account_type: Optional[str] = None
    current_value: Optional[float] = None
    active_interval: Optional[str] = None
    holdings: Optional[Dict[str, float]] = Field(default=None, alias="holdings_map")
    manual_holdings: Optional[List[Dict[str, Any]]] = None
    lots: Optional[Dict[str, List[Lot]]] = None
    ownership_type: Optional[str] = None
    custodian: Optional[str] = None
    tags: Optional[List[str]] = None
    tax_settings: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None


class ClientPatch(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: Optional[str] = None
    risk_profile: Optional[str] = None
    risk_profile_source: Optional[str] = None
    active_interval: Optional[str] = None
    tax_profile: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None


class ClientPayload(BaseModel):
    clients: List[Client]
