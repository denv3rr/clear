from __future__ import annotations

import json
import os
import uuid
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.db_management import create_db_and_tables
from core.database import SessionLocal
from core import models
from modules.client_mgr.schema import Client, Account, ClientPatch, AccountPatch


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


class DuplicateClientError(ValueError):
    def __init__(self, message: str, *, existing_client_id: str = "", incoming_client_id: str = ""):
        super().__init__(message)
        self.existing_client_id = existing_client_id
        self.incoming_client_id = incoming_client_id


class DuplicateAccountError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        existing_account_id: str = "",
        incoming_account_id: str = "",
        client_id: str = "",
    ):
        super().__init__(message)
        self.existing_account_id = existing_account_id
        self.incoming_account_id = incoming_account_id
        self.client_id = client_id


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().casefold()


def _canonicalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonicalize_value(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        normalized = [_canonicalize_value(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, str):
        return _normalize_text(value)
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _canonicalize_value(value),
        sort_keys=True,
        separators=(",", ":"),
    )


def _client_name_key(name: Any) -> str:
    return _normalize_text(name)


def _account_field(source: Any, *names: str) -> Any:
    if isinstance(source, dict):
        for name in names:
            if name in source:
                return source.get(name)
        return None
    for name in names:
        if hasattr(source, name):
            return getattr(source, name)
    return None


def _account_identity_key(account: Any) -> str:
    parts = [
        _normalize_text(_account_field(account, "account_name", "name")),
        _normalize_text(_account_field(account, "account_type")),
        _normalize_text(_account_field(account, "ownership_type")),
        _normalize_text(_account_field(account, "custodian")),
    ]
    return "|".join(parts)


def _account_fingerprint(account: models.Account) -> str:
    pydantic_account = Account.model_validate(account)
    payload = pydantic_account.model_dump(
        exclude={"account_id", "current_value", "active_interval", "extra"}
    )
    return _canonical_json(payload)


@contextmanager
def _session_scope(db: Optional[Session] = None):
    if db is not None:
        yield db
        return
    session = SessionLocal()
    try:
        yield session
        # session.commit()
    except Exception:
        # session.rollback()
        raise
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
        try:
            validated_client = Client.model_validate(payload)
        except ValidationError as e:
            logging.error(f"Client data validation failed: {e}")
            raise

        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            client_uid = validated_client.client_id or str(uuid.uuid4())
            name_key = _client_name_key(validated_client.name)
            existing = self._find_client_by_name_key(db, name_key)
            if existing is not None:
                raise DuplicateClientError(
                    "Client already exists under the same normalized name.",
                    existing_client_id=existing.client_uid or str(existing.id),
                    incoming_client_id=client_uid,
                )
            client = models.Client(
                client_uid=client_uid,
                name=validated_client.name,
                name_key=name_key,
                risk_profile=validated_client.risk_profile,
                risk_profile_source=validated_client.risk_profile_source,
                active_interval=validated_client.active_interval,
                tax_profile=validated_client.tax_profile or dict(DEFAULT_TAX_PROFILE),
                extra=validated_client.extra or {},
            )
            db.add(client)
            db.flush()
            self._sync_accounts(db, client, validated_client.accounts)
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
            
            try:
                validated_payload = ClientPatch.model_validate(payload, from_attributes=True)
            except ValidationError as e:
                logging.error(f"Client data validation failed: {e}")
                raise

            if validated_payload.name is not None:
                name_key = _client_name_key(validated_payload.name)
                existing = self._find_client_by_name_key(
                    db,
                    name_key,
                    exclude_client_uid=client.client_uid or "",
                )
                if existing is not None:
                    raise DuplicateClientError(
                        "Client already exists under the same normalized name.",
                        existing_client_id=existing.client_uid or str(existing.id),
                        incoming_client_id=client.client_uid or str(client.id),
                    )

            if validated_payload.name is not None:
                client.name = validated_payload.name
                client.name_key = _client_name_key(validated_payload.name)
            if validated_payload.risk_profile is not None:
                client.risk_profile = validated_payload.risk_profile
            if validated_payload.risk_profile_source is not None:
                client.risk_profile_source = validated_payload.risk_profile_source
            if validated_payload.active_interval is not None:
                client.active_interval = validated_payload.active_interval
            if validated_payload.tax_profile is not None:
                client.tax_profile = validated_payload.tax_profile
            if validated_payload.extra is not None:
                client.extra = validated_payload.extra
            db.commit()
            db.refresh(client)
            return self._client_to_dict(client)

    def sync_clients(
        self,
        payloads: List[Dict[str, Any]],
        *,
        delete_missing: bool = False,
        overwrite: bool = True,
        allow_name_merge: bool = False,
    ) -> None:
        self.ensure_schema()
        
        try:
            validated_payloads = [Client.model_validate(p) for p in payloads]
        except ValidationError as e:
            logging.error(f"Client data validation failed: {e}")
            raise

        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            existing = {client.client_uid: client for client in db.query(models.Client).all()}
            existing_by_name = {
                client.name_key or _client_name_key(client.name): client
                for client in existing.values()
                if client.name_key or client.name
            }
            incoming_ids = set()

            for payload in validated_payloads:
                client_uid = payload.client_id or str(uuid.uuid4())
                client = existing.get(client_uid)
                name_key = _client_name_key(payload.name)
                if client is None and allow_name_merge and name_key:
                    client = existing_by_name.get(name_key)
                elif client is None and name_key and name_key in existing_by_name:
                    existing_client = existing_by_name[name_key]
                    raise DuplicateClientError(
                        "Client already exists under the same normalized name.",
                        existing_client_id=existing_client.client_uid or str(existing_client.id),
                        incoming_client_id=client_uid,
                    )
                
                if client is not None:
                    incoming_ids.add(client.client_uid)
                else:
                    incoming_ids.add(client_uid)

                if client is None:
                    client = models.Client(
                        client_uid=client_uid,
                        name=payload.name,
                        name_key=name_key,
                        risk_profile=payload.risk_profile,
                        risk_profile_source=payload.risk_profile_source,
                        active_interval=payload.active_interval,
                        tax_profile=payload.tax_profile or dict(DEFAULT_TAX_PROFILE),
                        extra=payload.extra or {},
                    )
                    db.add(client)
                    db.flush()
                    if name_key:
                        existing_by_name.setdefault(name_key, client)
                elif overwrite:
                    existing_client = self._find_client_by_name_key(
                        db,
                        name_key,
                        exclude_client_uid=client.client_uid or "",
                    )
                    if existing_client is not None:
                        raise DuplicateClientError(
                            "Client already exists under the same normalized name.",
                            existing_client_id=existing_client.client_uid or str(existing_client.id),
                            incoming_client_id=client.client_uid or str(client.id),
                        )
                    client.name = payload.name
                    client.name_key = name_key
                    client.risk_profile = payload.risk_profile
                    client.risk_profile_source = payload.risk_profile_source
                    client.active_interval = payload.active_interval
                    client.tax_profile = payload.tax_profile or client.tax_profile
                    client.extra = payload.extra or client.extra

                self._sync_accounts(
                    db,
                    client,
                    payload.accounts,
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
        try:
            validated_account = Account.model_validate(payload)
        except ValidationError as e:
            logging.error(f"Account data validation failed: {e}")
            raise

        with _session_scope(self._db) as db:
            self._ensure_identifiers(db)
            client = self._find_client(db, client_ref)
            if client is None:
                return None
            account_uid = validated_account.account_id or str(uuid.uuid4())
            identity_key = _account_identity_key(validated_account)
            existing = self._find_conflicting_account(
                db,
                client.id,
                identity_key,
            )
            if existing is not None:
                raise DuplicateAccountError(
                    "Account already exists under the same normalized identity.",
                    existing_account_id=existing.account_uid or str(existing.id),
                    incoming_account_id=account_uid,
                    client_id=client.client_uid or str(client.id),
                )
            account = models.Account(
                account_uid=account_uid,
                name=validated_account.account_name,
                identity_key=identity_key,
                account_type=validated_account.account_type,
                current_value=validated_account.current_value,
                active_interval=validated_account.active_interval,
                ownership_type=validated_account.ownership_type,
                custodian=validated_account.custodian,
                tags=validated_account.tags,
                tax_settings=validated_account.tax_settings or dict(DEFAULT_TAX_SETTINGS),
                holdings_map=validated_account.holdings or {},
                lots={k: [lot.model_dump() for lot in v] for k, v in validated_account.lots.items()} or {},
                manual_holdings=validated_account.manual_holdings or [],
                extra=validated_account.extra or {},
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
            
            try:
                validated_payload = AccountPatch.model_validate(payload, from_attributes=True)
            except ValidationError as e:
                logging.error(f"Account data validation failed: {e}")
                raise

            proposed_identity_key = _account_identity_key(
                {
                    "name": validated_payload.account_name
                    if validated_payload.account_name is not None
                    else account.name,
                    "account_type": validated_payload.account_type
                    if validated_payload.account_type is not None
                    else account.account_type,
                    "ownership_type": validated_payload.ownership_type
                    if validated_payload.ownership_type is not None
                    else account.ownership_type,
                    "custodian": validated_payload.custodian
                    if validated_payload.custodian is not None
                    else account.custodian,
                }
            )
            existing = self._find_conflicting_account(
                db,
                client.id,
                proposed_identity_key,
                exclude_account_uid=account.account_uid or "",
            )
            if existing is not None:
                raise DuplicateAccountError(
                    "Account already exists under the same normalized identity.",
                    existing_account_id=existing.account_uid or str(existing.id),
                    incoming_account_id=account.account_uid or str(account.id),
                    client_id=client.client_uid or str(client.id),
                )

            if validated_payload.account_name is not None:
                account.name = validated_payload.account_name
            account.identity_key = proposed_identity_key
            if validated_payload.account_type is not None:
                account.account_type = validated_payload.account_type
            if validated_payload.current_value is not None:
                account.current_value = validated_payload.current_value
            if validated_payload.active_interval is not None:
                account.active_interval = validated_payload.active_interval
            if validated_payload.ownership_type is not None:
                account.ownership_type = validated_payload.ownership_type
            if validated_payload.custodian is not None:
                account.custodian = validated_payload.custodian
            if validated_payload.tags is not None:
                account.tags = validated_payload.tags
            if validated_payload.tax_settings is not None:
                account.tax_settings = validated_payload.tax_settings
            if validated_payload.holdings is not None:
                account.holdings_map = validated_payload.holdings
            if validated_payload.lots is not None:
                account.lots = {
                    k: [lot.model_dump() for lot in v]
                    for k, v in validated_payload.lots.items()
                }
            if validated_payload.manual_holdings is not None:
                account.manual_holdings = validated_payload.manual_holdings
            if validated_payload.extra is not None:
                account.extra = validated_payload.extra
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

    def find_duplicate_clients(self) -> Dict[str, Any]:
        self.ensure_schema()
        with _session_scope(self._db) as db:
            groups: Dict[str, List[models.Client]] = {}
            for client in db.query(models.Client).all():
                key = client.name_key or _client_name_key(client.name)
                if not key:
                    continue
                groups.setdefault(key, []).append(client)

            duplicates: List[Dict[str, Any]] = []
            total_duplicates = 0
            duplicate_groups = 0
            for name_key, clients in groups.items():
                if len(clients) <= 1:
                    continue
                duplicate_groups += 1
                clients_sorted = sorted(clients, key=lambda item: item.id or 0)
                keeper = clients_sorted[0]
                dupes = clients_sorted[1:]
                duplicates.append(
                    {
                        "normalized_name": name_key,
                        "client_name": keeper.name or "",
                        "keep_client_id": keeper.client_uid or str(keeper.id),
                        "duplicate_ids": [
                            dup.client_uid or str(dup.id) for dup in dupes
                        ],
                        "duplicate_names": [dup.name or "" for dup in dupes],
                        "duplicate_count": len(dupes),
                    }
                )
                total_duplicates += len(dupes)
            return {
                "count": total_duplicates,
                "groups": duplicate_groups,
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
        accounts: List[Account],
        *,
        delete_missing: bool = False,
        overwrite: bool = True,
    ) -> None:
        existing = {acc.account_uid: acc for acc in client.accounts}
        existing_by_identity = {
            acc.identity_key or _account_identity_key(acc): acc
            for acc in client.accounts
        }
        incoming_ids = set()
        for payload in accounts:
            account_uid = payload.account_id or str(uuid.uuid4())
            identity_key = _account_identity_key(payload)
            incoming_ids.add(account_uid)
            account = existing.get(account_uid)
            if account is None:
                conflicting = existing_by_identity.get(identity_key)
                if conflicting is not None:
                    raise DuplicateAccountError(
                        "Account already exists under the same normalized identity.",
                        existing_account_id=conflicting.account_uid or str(conflicting.id),
                        incoming_account_id=account_uid,
                        client_id=client.client_uid or str(client.id),
                    )
                account = models.Account(
                    account_uid=account_uid,
                    name=payload.account_name,
                    identity_key=identity_key,
                    account_type=payload.account_type,
                    current_value=payload.current_value,
                    active_interval=payload.active_interval,
                    ownership_type=payload.ownership_type,
                    custodian=payload.custodian,
                    tags=payload.tags,
                    tax_settings=payload.tax_settings or dict(DEFAULT_TAX_SETTINGS),
                    holdings_map=payload.holdings or {},
                    lots={k: [lot.model_dump() for lot in v] for k, v in payload.lots.items()} or {},
                    manual_holdings=payload.manual_holdings or [],
                    extra=payload.extra or {},
                    client_id=client.id,
                )
                db.add(account)
                db.flush()
            elif overwrite:
                conflicting = self._find_conflicting_account(
                    db,
                    client.id,
                    identity_key,
                    exclude_account_uid=account.account_uid or "",
                )
                if conflicting is not None:
                    raise DuplicateAccountError(
                        "Account already exists under the same normalized identity.",
                        existing_account_id=conflicting.account_uid or str(conflicting.id),
                        incoming_account_id=account.account_uid or str(account.id),
                        client_id=client.client_uid or str(client.id),
                    )
                account.name = payload.account_name
                account.identity_key = identity_key
                account.account_type = payload.account_type
                account.current_value = payload.current_value
                account.active_interval = payload.active_interval
                account.ownership_type = payload.ownership_type
                account.custodian = payload.custodian
                account.tags = payload.tags
                account.tax_settings = payload.tax_settings or account.tax_settings
                account.holdings_map = payload.holdings or account.holdings_map
                account.lots = {k: [lot.model_dump() for lot in v] for k, v in payload.lots.items()} or account.lots
                account.manual_holdings = payload.manual_holdings or account.manual_holdings
                account.extra = payload.extra or account.extra
            existing[account.account_uid] = account
            existing_by_identity[identity_key] = account
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
        for client in db.query(models.Client).all():
            name_key = _client_name_key(client.name)
            if (client.name_key or "") != name_key:
                client.name_key = name_key
                dirty = True
        for account in db.query(models.Account).filter(
            (models.Account.account_uid.is_(None)) | (models.Account.account_uid == "")
        ):
            account.account_uid = str(uuid.uuid4())
            dirty = True
        for account in db.query(models.Account).all():
            identity_key = _account_identity_key(account)
            if (account.identity_key or "") != identity_key:
                account.identity_key = identity_key
                dirty = True
        if dirty:
            db.commit()

    def _find_client_by_name_key(
        self,
        db: Session,
        name_key: str,
        *,
        exclude_client_uid: str = "",
    ) -> Optional[models.Client]:
        if not name_key:
            return None
        query = db.query(models.Client).filter(models.Client.name_key == name_key)
        if exclude_client_uid:
            query = query.filter(models.Client.client_uid != exclude_client_uid)
        return query.first()

    def _find_conflicting_account(
        self,
        db: Session,
        client_id: int,
        identity_key: str,
        *,
        exclude_account_uid: str = "",
    ) -> Optional[models.Account]:
        if not identity_key:
            return None
        query = db.query(models.Account).filter(
            models.Account.client_id == client_id,
            models.Account.identity_key == identity_key,
        )
        if exclude_account_uid:
            query = query.filter(models.Account.account_uid != exclude_account_uid)
        return query.first()

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
        return Account.model_validate(account).model_dump()

    def _client_to_dict(self, client: models.Client) -> Dict[str, Any]:
        return Client.model_validate(client).model_dump()


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
    
    if not isinstance(payload, list) or not payload:
        return False
    store = DbClientStore()
    store.sync_clients(payload, delete_missing=False, overwrite=False)
    return True
