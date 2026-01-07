from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from core.db_management import create_db_and_tables
from core.database import SessionLocal
from core import models
from modules.client_mgr.client_model import Account, Client
from modules.client_mgr.holdings import normalize_ticker
from modules.client_mgr.payloads import normalize_clients_payload

CLIENTS_JSON_PATH = os.path.join("data", "clients.json")

DEFAULT_TAX_PROFILE = {
    "residency_country": "",
    "tax_country": "",
    "reporting_currency": "USD",
    "treaty_country": "",
    "tax_id": "",
}

DEFAULT_TAX_SETTINGS = {
    "jurisdiction": "",
    "account_currency": "USD",
    "withholding_rate": None,
    "tax_exempt": False,
}


def _split_extra(payload: Dict[str, Any], allowed_keys: Iterable[str]) -> Dict[str, Any]:
    allowed = set(allowed_keys)
    return {k: v for k, v in payload.items() if k not in allowed}


def _merge_extra(payload: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    existing = payload.get("extra")
    if isinstance(existing, dict):
        merged = dict(existing)
    else:
        merged = {}
    merged.update(extra)
    return merged


def _normalize_holdings_map(raw: Any) -> Dict[str, Any]:
    holdings: Dict[str, Any] = {}
    if not isinstance(raw, dict):
        return holdings
    for ticker, qty in raw.items():
        if not isinstance(ticker, str):
            continue
        holdings[normalize_ticker(ticker)] = _normalize_number(qty)
    return holdings


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalize_number(value: Any, *, precision: int = 8) -> float:
    try:
        return round(float(value), precision)
    except (TypeError, ValueError):
        return 0.0


def _normalize_tags(tags: Any) -> List[str]:
    if not isinstance(tags, (list, tuple, set)):
        return []
    return sorted({t for t in (_normalize_text(t) for t in tags) if t})


def _normalize_dict_payload(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    normalized: Dict[str, Any] = {}
    for key in sorted(payload.keys()):
        value = payload.get(key)
        if isinstance(value, dict):
            normalized[key] = _normalize_dict_payload(value)
        elif isinstance(value, list):
            normalized[key] = _normalize_list_payload(value)
        elif isinstance(value, (int, float)):
            normalized[key] = _normalize_number(value)
        elif isinstance(value, str):
            normalized[key] = value.strip()
        else:
            normalized[key] = value
    return normalized


def _normalize_list_payload(items: Any) -> List[Any]:
    if not isinstance(items, list):
        return []
    normalized: List[Any] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(_normalize_dict_payload(item))
        elif isinstance(item, list):
            normalized.append(_normalize_list_payload(item))
        elif isinstance(item, (int, float)):
            normalized.append(_normalize_number(item))
        elif isinstance(item, str):
            normalized.append(item.strip())
        else:
            normalized.append(item)
    normalized.sort(key=lambda entry: json.dumps(entry, sort_keys=True, default=str))
    return normalized


def _normalize_lots_payload(raw: Any) -> Dict[str, List[Dict[str, Any]]]:
    lots: Dict[str, List[Dict[str, Any]]] = {}
    if not isinstance(raw, dict):
        return lots
    for ticker, entries in raw.items():
        if not isinstance(ticker, str):
            continue
        normalized_entries: List[Dict[str, Any]] = []
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                qty = entry.get("qty")
                if qty is None:
                    qty = entry.get("quantity", entry.get("shares"))
                basis = entry.get("basis")
                if basis is None:
                    basis = entry.get("price", entry.get("cost_basis"))
                timestamp = entry.get("timestamp")
                if timestamp is None:
                    timestamp = entry.get("date", entry.get("purchase_date"))
                normalized_entries.append(
                    {
                        "qty": _normalize_number(qty),
                        "basis": _normalize_number(basis),
                        "timestamp": str(timestamp).strip() if timestamp else "",
                    }
                )
        if normalized_entries:
            normalized_entries.sort(
                key=lambda row: (row.get("timestamp", ""), row.get("qty", 0.0), row.get("basis", 0.0))
            )
            lots[normalize_ticker(ticker)] = normalized_entries
    return lots


def _normalize_account_payload(payload: Dict[str, Any]) -> Dict[str, Any]:      
    account = Account.from_dict(payload)
    normalized = account.to_dict()
    extra = _split_extra(
        payload,
        {
            "account_id",
            "account_name",
            "account_type",
            "current_value",
            "active_interval",
            "holdings",
            "manual_holdings",
            "lots",
            "ownership_type",
            "custodian",
            "tags",
            "tax_settings",
            "extra",
        },
    )
    normalized["extra"] = _merge_extra(payload, extra)
    normalized["holdings"] = _normalize_holdings_map(normalized.get("holdings"))
    return normalized


def _account_fingerprint(account: models.Account) -> str:
    holdings = account.holdings_map or {}
    if not holdings and account.holdings:
        holdings = {row.ticker: row.quantity for row in account.holdings}
    lots = account.lots or {}
    if not lots and account.holdings:
        recovered: Dict[str, List[Dict[str, Any]]] = {}
        for holding in account.holdings:
            entries = []
            for lot in getattr(holding, "lots", []) or []:
                ts = None
                if lot.purchase_date is not None:
                    ts = lot.purchase_date.isoformat() + "T00:00:00"
                entries.append(
                    {
                        "qty": lot.quantity,
                        "basis": lot.purchase_price,
                        "timestamp": ts or "LEGACY",
                        "source": "LEGACY_DB",
                        "kind": "lot",
                    }
                )
            if entries:
                recovered[holding.ticker] = entries
        lots = recovered or lots
    payload: Dict[str, Any] = {
        "name": _normalize_text(account.name),
        "account_type": _normalize_text(account.account_type),
        "ownership_type": _normalize_text(account.ownership_type),
        "custodian": _normalize_text(account.custodian),
        "tags": _normalize_tags(account.tags or []),
        "tax_settings": _normalize_dict_payload(account.tax_settings or {}),
        "holdings_map": _normalize_holdings_map(holdings),
        "lots": _normalize_lots_payload(lots),
        "manual_holdings": _normalize_list_payload(account.manual_holdings or []),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _normalize_client_payload(payload: Dict[str, Any]) -> Dict[str, Any]:       
    client = Client.from_dict(payload)
    normalized = client.to_dict()
    extra = _split_extra(
        payload,
        {
            "client_id",
            "name",
            "risk_profile",
            "risk_profile_source",
            "active_interval",
            "tax_profile",
            "accounts",
            "extra",
        },
    )
    normalized["extra"] = _merge_extra(payload, extra)
    accounts = []
    for acc in normalized.get("accounts", []) or []:
        if isinstance(acc, dict):
            accounts.append(_normalize_account_payload(acc))
    normalized["accounts"] = accounts
    return normalized


@contextmanager
def _session_scope(db: Optional[Session] = None):
    if db is not None:
        yield db
        return
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class DbClientStore:
    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def ensure_schema(self) -> None:
        if self._db is None:
            create_db_and_tables()

    def fetch_all_clients(self) -> List[Dict[str, Any]]:
        self.ensure_schema()
        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            clients = db.query(models.Client).all()
            return [self._client_to_dict(client) for client in clients]

    def fetch_client(self, client_ref: Any) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            client = self._find_client(db, client_ref)
            if client is None:
                return None
            return self._client_to_dict(client)

    def create_client(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_schema()
        migrated, _ = normalize_clients_payload([payload])
        payload = migrated[0] if isinstance(migrated, list) and migrated else payload
        normalized = _normalize_client_payload(payload)
        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            client = models.Client(
                client_uid=normalized.get("client_id") or str(uuid.uuid4()),
                name=normalized.get("name", "New Client"),
                risk_profile=normalized.get("risk_profile", "Not Assessed"),
                risk_profile_source=normalized.get("risk_profile_source", "auto"),
                active_interval=normalized.get("active_interval", "1M"),
                tax_profile=normalized.get("tax_profile") or dict(DEFAULT_TAX_PROFILE),
                extra=normalized.get("extra") or {},
            )
            db.add(client)
            db.flush()
            self._sync_accounts(db, client, normalized.get("accounts", []))
            db.commit()
            db.refresh(client)
            return self._client_to_dict(client)

    def update_client(self, client_ref: Any, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            client = self._find_client(db, client_ref)
            if client is None:
                return None
            updates = dict(payload or {})
            if "name" in updates and updates["name"] is not None:
                client.name = str(updates["name"]).strip()
            if "risk_profile" in updates and updates["risk_profile"] is not None:
                cleaned = str(updates["risk_profile"]).strip()
                client.risk_profile = cleaned or "Not Assessed"
            if "risk_profile_source" in updates and updates["risk_profile_source"] is not None:
                client.risk_profile_source = str(updates["risk_profile_source"]).strip() or "auto"
            if "active_interval" in updates and updates["active_interval"] is not None:
                client.active_interval = str(updates["active_interval"]).strip().upper() or "1M"
            if "tax_profile" in updates and updates["tax_profile"] is not None:
                client.tax_profile = updates["tax_profile"]
            if "extra" in updates and updates["extra"] is not None:
                client.extra = updates["extra"]
            db.commit()
            db.refresh(client)
            return self._client_to_dict(client)

    def sync_clients(
        self,
        payloads: List[Dict[str, Any]],
        *,
        delete_missing: bool = True,
        overwrite: bool = True,
    ) -> None:
        self.ensure_schema()
        migrated, _ = normalize_clients_payload(payloads)
        source_payloads = migrated if isinstance(migrated, list) else payloads
        normalized_payloads = [_normalize_client_payload(payload) for payload in source_payloads]
        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            existing = {client.client_uid: client for client in db.query(models.Client).all()}
            existing_by_name = {
                str(client.name).strip().lower(): client
                for client in existing.values()
                if client.name
            }
            incoming_ids = set()
            for payload in normalized_payloads:
                client_uid = payload.get("client_id") or str(uuid.uuid4())
                client = existing.get(client_uid)
                if client is None:
                    name_key = str(payload.get("name", "")).strip().lower()
                    if name_key:
                        client = existing_by_name.get(name_key)
                if client is not None:
                    incoming_ids.add(client.client_uid)
                else:
                    incoming_ids.add(client_uid)
                if client is None:
                    client = models.Client(
                        client_uid=client_uid,
                        name=payload.get("name", "New Client"),
                        risk_profile=payload.get("risk_profile", "Not Assessed"),
                        risk_profile_source=payload.get("risk_profile_source", "auto"),
                        active_interval=payload.get("active_interval", "1M"),
                        tax_profile=payload.get("tax_profile") or dict(DEFAULT_TAX_PROFILE),
                        extra=payload.get("extra") or {},
                    )
                    db.add(client)
                    db.flush()
                    name_key = str(client.name or "").strip().lower()
                    if name_key:
                        existing_by_name.setdefault(name_key, client)
                elif overwrite:
                    client.name = payload.get("name", client.name)
                    client.risk_profile = payload.get("risk_profile", client.risk_profile)
                    client.risk_profile_source = payload.get("risk_profile_source", client.risk_profile_source)
                    client.active_interval = payload.get("active_interval", client.active_interval)
                    client.tax_profile = payload.get("tax_profile") or client.tax_profile
                    client.extra = payload.get("extra") or client.extra
                self._sync_accounts(
                    db,
                    client,
                    payload.get("accounts", []),
                    delete_missing=delete_missing,
                    overwrite=overwrite,
                )
            if delete_missing:
                for client_uid, client in existing.items():
                    if client_uid not in incoming_ids:
                        db.delete(client)
            db.commit()

    def create_account(self, client_ref: Any, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        normalized = _normalize_account_payload(payload)
        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            client = self._find_client(db, client_ref)
            if client is None:
                return None
            account = models.Account(
                account_uid=normalized.get("account_id") or str(uuid.uuid4()),
                name=normalized.get("account_name", "Brokerage Account"),
                account_type=normalized.get("account_type", "Taxable"),
                current_value=normalized.get("current_value", 0.0) or 0.0,
                active_interval=normalized.get("active_interval", "1M"),
                ownership_type=normalized.get("ownership_type", "Individual"),
                custodian=normalized.get("custodian", ""),
                tags=normalized.get("tags") or [],
                tax_settings=normalized.get("tax_settings") or dict(DEFAULT_TAX_SETTINGS),
                holdings_map=normalized.get("holdings") or {},
                lots=normalized.get("lots") or {},
                manual_holdings=normalized.get("manual_holdings") or [],
                extra=normalized.get("extra") or {},
                client_id=client.id,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            return self._account_to_dict(account)

    def update_account(self, client_ref: Any, account_ref: Any, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.ensure_schema()
        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            client = self._find_client(db, client_ref)
            if client is None:
                return None
            account = self._find_account(db, client.id, account_ref)
            if account is None:
                return None
            updates = dict(payload or {})
            if "account_name" in updates and updates["account_name"] is not None:
                account.name = str(updates["account_name"]).strip()
            if "account_type" in updates and updates["account_type"] is not None:
                account.account_type = updates["account_type"]
            if "ownership_type" in updates and updates["ownership_type"] is not None:
                account.ownership_type = updates["ownership_type"]
            if "custodian" in updates and updates["custodian"] is not None:
                account.custodian = updates["custodian"]
            if "tags" in updates and updates["tags"] is not None:
                account.tags = updates["tags"]
            if "tax_settings" in updates and updates["tax_settings"] is not None:
                account.tax_settings = updates["tax_settings"]
            if "holdings" in updates and updates["holdings"] is not None:
                account.holdings_map = _normalize_holdings_map(updates["holdings"])
            if "lots" in updates and updates["lots"] is not None:
                account.lots = updates["lots"]
            if "manual_holdings" in updates and updates["manual_holdings"] is not None:
                account.manual_holdings = updates["manual_holdings"]
            if "extra" in updates and updates["extra"] is not None:
                account.extra = updates["extra"]
            db.commit()
            db.refresh(account)
            return self._account_to_dict(account)

    def find_duplicate_accounts(self) -> Dict[str, Any]:
        self.ensure_schema()
        with _session_scope(self._db) as db:
            duplicates: List[Dict[str, Any]] = []
            total_duplicates = 0
            client_count = 0
            for client in db.query(models.Client).all():
                groups: Dict[str, List[models.Account]] = {}
                for account in client.accounts:
                    key = _account_fingerprint(account)
                    groups.setdefault(key, []).append(account)
                has_duplicates = False
                for accounts in groups.values():
                    if len(accounts) <= 1:
                        continue
                    has_duplicates = True
                    accounts_sorted = sorted(accounts, key=lambda item: item.id or 0)
                    keeper = accounts_sorted[0]
                    dupes = accounts_sorted[1:]
                    duplicates.append(
                        {
                            "client_id": client.client_uid or str(client.id),
                            "client_name": client.name or "",
                            "account_name": keeper.name or "",
                            "account_type": keeper.account_type or "",
                            "keep_account_id": keeper.account_uid or str(keeper.id),
                            "duplicate_ids": [
                                dup.account_uid or str(dup.id) for dup in dupes
                            ],
                            "duplicate_count": len(dupes),
                        }
                    )
                    total_duplicates += len(dupes)
                if has_duplicates:
                    client_count += 1
            return {
                "count": total_duplicates,
                "clients": client_count,
                "details": duplicates,
            }

    def remove_duplicate_accounts(self) -> Dict[str, Any]:
        self.ensure_schema()
        with _session_scope(self._db) as db:
            removed = 0
            client_count = 0
            for client in db.query(models.Client).all():
                groups: Dict[str, List[models.Account]] = {}
                for account in client.accounts:
                    key = _account_fingerprint(account)
                    groups.setdefault(key, []).append(account)
                removed_for_client = False
                for accounts in groups.values():
                    if len(accounts) <= 1:
                        continue
                    accounts_sorted = sorted(accounts, key=lambda item: item.id or 0)
                    dupes = accounts_sorted[1:]
                    for account in dupes:
                        db.delete(account)
                        removed += 1
                        removed_for_client = True
                if removed_for_client:
                    client_count += 1
            if removed:
                db.commit()
            remaining_store = self
            if self._db is not None:
                remaining_store = DbClientStore()
            remaining = remaining_store.find_duplicate_accounts()
            return {
                "removed": removed,
                "clients": client_count,
                "remaining": {
                    "count": int(remaining.get("count", 0) or 0),
                    "clients": int(remaining.get("clients", 0) or 0),
                },
            }

    def _sync_accounts(
        self,
        db: Session,
        client: models.Client,
        accounts: List[Dict[str, Any]],
        *,
        delete_missing: bool = True,
        overwrite: bool = True,
    ) -> None:
        existing = {acc.account_uid: acc for acc in client.accounts}
        incoming_ids = set()
        for payload in accounts:
            normalized = _normalize_account_payload(payload)
            account_uid = normalized.get("account_id") or str(uuid.uuid4())
            incoming_ids.add(account_uid)
            account = existing.get(account_uid)
            if account is None:
                account = models.Account(
                    account_uid=account_uid,
                    name=normalized.get("account_name", "Brokerage Account"),
                    account_type=normalized.get("account_type", "Taxable"),
                    current_value=normalized.get("current_value", 0.0) or 0.0,
                    active_interval=normalized.get("active_interval", "1M"),
                    ownership_type=normalized.get("ownership_type", "Individual"),
                    custodian=normalized.get("custodian", ""),
                    tags=normalized.get("tags") or [],
                    tax_settings=normalized.get("tax_settings") or dict(DEFAULT_TAX_SETTINGS),
                    holdings_map=normalized.get("holdings") or {},
                    lots=normalized.get("lots") or {},
                    manual_holdings=normalized.get("manual_holdings") or [],
                    extra=normalized.get("extra") or {},
                    client_id=client.id,
                )
                db.add(account)
                db.flush()
            elif overwrite:
                account.name = normalized.get("account_name", account.name)
                account.account_type = normalized.get("account_type", account.account_type)
                account.current_value = normalized.get("current_value", account.current_value)
                account.active_interval = normalized.get("active_interval", account.active_interval)
                account.ownership_type = normalized.get("ownership_type", account.ownership_type)
                account.custodian = normalized.get("custodian", account.custodian)
                account.tags = normalized.get("tags") or account.tags
                account.tax_settings = normalized.get("tax_settings") or account.tax_settings
                account.holdings_map = normalized.get("holdings") or account.holdings_map
                account.lots = normalized.get("lots") or account.lots
                account.manual_holdings = normalized.get("manual_holdings") or account.manual_holdings
                account.extra = normalized.get("extra") or account.extra
        if delete_missing:
            for acc_uid, account in existing.items():
                if acc_uid not in incoming_ids:
                    db.delete(account)

    def _ensure_identifiers(self, db: Session) -> None:
        dirty = False
        for client in db.query(models.Client).filter(
            (models.Client.client_uid.is_(None)) | (models.Client.client_uid == "")
        ):
            client.client_uid = str(uuid.uuid4())
            dirty = True
        for account in db.query(models.Account).filter(
            (models.Account.account_uid.is_(None)) | (models.Account.account_uid == "")
        ):
            account.account_uid = str(uuid.uuid4())
            dirty = True
        if dirty:
            db.commit()

    def _find_client(self, db: Session, client_ref: Any) -> Optional[models.Client]:
        if client_ref is None:
            return None
        ref_text = str(client_ref)
        if ref_text.isdigit():
            client = db.query(models.Client).filter(models.Client.id == int(ref_text)).first()
            if client is not None:
                return client
        return db.query(models.Client).filter(models.Client.client_uid == ref_text).first()

    def _find_account(self, db: Session, client_id: int, account_ref: Any) -> Optional[models.Account]:
        if account_ref is None:
            return None
        ref_text = str(account_ref)
        if ref_text.isdigit():
            account = db.query(models.Account).filter(
                models.Account.id == int(ref_text),
                models.Account.client_id == client_id,
            ).first()
            if account is not None:
                return account
        return db.query(models.Account).filter(
            models.Account.account_uid == ref_text,
            models.Account.client_id == client_id,
        ).first()

    def _account_to_dict(self, account: models.Account) -> Dict[str, Any]:
        holdings = account.holdings_map or {}
        if not holdings and account.holdings:
            holdings = {row.ticker: row.quantity for row in account.holdings}
        lots = account.lots or {}
        if not lots and account.holdings:
            recovered: Dict[str, List[Dict[str, Any]]] = {}
            for holding in account.holdings:
                entries = []
                for lot in getattr(holding, "lots", []) or []:
                    ts = None
                    if lot.purchase_date is not None:
                        ts = lot.purchase_date.isoformat() + "T00:00:00"
                    entries.append(
                        {
                            "qty": lot.quantity,
                            "basis": lot.purchase_price,
                            "timestamp": ts or "LEGACY",
                            "source": "LEGACY_DB",
                            "kind": "lot",
                        }
                    )
                if entries:
                    recovered[holding.ticker] = entries
            lots = recovered or lots
        return {
            "account_id": account.account_uid or str(account.id),
            "account_name": account.name,
            "account_type": account.account_type,
            "current_value": float(account.current_value or 0.0),
            "active_interval": account.active_interval or "1M",
            "holdings": holdings,
            "lots": lots,
            "manual_holdings": account.manual_holdings or [],
            "ownership_type": account.ownership_type or "Individual",
            "custodian": account.custodian or "",
            "tags": account.tags or [],
            "tax_settings": account.tax_settings or dict(DEFAULT_TAX_SETTINGS),
            "extra": account.extra or {},
        }

    def _client_to_dict(self, client: models.Client) -> Dict[str, Any]:
        return {
            "client_id": client.client_uid or str(client.id),
            "name": client.name,
            "risk_profile": client.risk_profile or "Not Assessed",
            "risk_profile_source": client.risk_profile_source or "auto",
            "active_interval": client.active_interval or "1M",
            "tax_profile": client.tax_profile or dict(DEFAULT_TAX_PROFILE),
            "accounts": [self._account_to_dict(account) for account in client.accounts],
            "extra": client.extra or {},
        }


def bootstrap_clients_from_json() -> bool:
    create_db_and_tables()
    if not os.path.exists(CLIENTS_JSON_PATH):
        return False
    session = SessionLocal()
    try:
        if session.query(models.Client).first() or session.query(models.Account).first():
            return False
    finally:
        session.close()
    try:
        with open(CLIENTS_JSON_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return False
    payload, _ = normalize_clients_payload(payload)
    if not isinstance(payload, list) or not payload:
        return False
    store = DbClientStore()
    store.sync_clients(payload, delete_missing=False, overwrite=False)
    return True
