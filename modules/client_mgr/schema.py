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
    holdings: Dict[str, float] = Field({}, alias="holdings_map")
    manual_holdings: List[Dict[str, Any]] = []
    lots: Dict[str, List[Lot]] = {}
    ownership_type: str = "Individual"
    custodian: str = ""
    tags: List[str] = []
    tax_settings: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}


class Client(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    client_id: Optional[str] = Field(None, alias="client_uid")
    name: str
    risk_profile: str = "Not Assessed"
    risk_profile_source: str = "auto"
    active_interval: str = "1M"
    tax_profile: Dict[str, Any] = {}
    accounts: List[Account] = []
    extra: Dict[str, Any] = {}


class ClientPayload(BaseModel):
    clients: List[Client]
