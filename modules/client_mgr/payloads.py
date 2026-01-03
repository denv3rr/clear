from __future__ import annotations

from typing import Any, Tuple


def normalize_clients_payload(payload: Any) -> Tuple[Any, bool]:
    if not isinstance(payload, list):
        return payload, False
    changed = False
    for client in payload:
        if not isinstance(client, dict):
            continue
        accounts = client.get("accounts", [])
        if not isinstance(accounts, list):
            continue
        for account in accounts:
            if not isinstance(account, dict):
                continue
            lots = account.get("lots", {})
            if not isinstance(lots, dict):
                continue
            for lot_list in lots.values():
                if not isinstance(lot_list, list):
                    continue
                for lot in lot_list:
                    if not isinstance(lot, dict):
                        continue
                    ts = lot.get("timestamp")
                    date_val = lot.get("date")
                    ts_clean = ts.strip() if isinstance(ts, str) else ""
                    new_ts = None
                    if not ts_clean or ts_clean.upper() == "LEGACY":
                        if isinstance(date_val, str) and date_val.strip():
                            new_ts = date_val.strip()
                    else:
                        new_ts = ts_clean
                    if isinstance(new_ts, str) and new_ts:
                        if " " in new_ts and "T" not in new_ts:
                            parts = new_ts.split()
                            if len(parts) >= 2:
                                new_ts = parts[0] + "T" + parts[1]
                        if len(new_ts) == 10 and "-" in new_ts:
                            new_ts = new_ts + "T00:00:00"
                        if ts != new_ts:
                            lot["timestamp"] = new_ts
                            changed = True
    return payload, changed
