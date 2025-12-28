from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple

from modules.client_mgr.client_model import Client
from modules.client_mgr.holdings import compute_weighted_avg_cost, normalize_ticker
from modules.client_mgr.valuation import ValuationEngine
from modules.market_data.trackers import GlobalTrackers
from modules.view_models import (
    account_dashboard,
    account_patterns,
    client_patterns,
    portfolio_dashboard,
)
from utils.report_synth import filter_fresh_news_items
from modules.market_data.intel import score_news_items


@dataclass
class ReportSection:
    title: str
    rows: List[List[str]]


@dataclass
class ReportPayload:
    report_type: str
    client_id: str
    client_name: str
    generated_at: str
    interval: str
    sections: List[ReportSection]
    data: Dict[str, Any]
    data_freshness: Dict[str, Any]
    methodology: List[str]


@dataclass
class ReportResult:
    content: str
    payload: ReportPayload
    output_format: str
    used_model: bool
    validation: Dict[str, Any]


class PriceService(Protocol):
    def get_quotes(self, tickers: Iterable[str]) -> Dict[str, float]:
        ...


class OfflinePriceService:
    def get_quotes(self, tickers: Iterable[str]) -> Dict[str, float]:
        return {}


class LivePriceService:
    def __init__(self, valuation: Optional[ValuationEngine] = None):
        self._valuation = valuation or ValuationEngine()

    def get_quotes(self, tickers: Iterable[str]) -> Dict[str, float]:
        quotes: Dict[str, float] = {}
        for ticker in tickers:
            data = self._valuation.get_quote_data(str(ticker))
            price = float(data.get("price", 0.0) or 0.0)
            if price > 0:
                quotes[normalize_ticker(ticker)] = price
        return quotes


class ModelRunner(Protocol):
    def available(self) -> bool:
        ...

    def generate(self, prompt: Dict[str, Any]) -> str:
        ...


class NoModelRunner:
    def available(self) -> bool:
        return False

    def generate(self, prompt: Dict[str, Any]) -> str:
        return ""


class OllamaRunner:
    def __init__(self, model_id: str = "llama3", host: str = "http://127.0.0.1:11434", timeout: int = 15):
        self.model_id = model_id
        self.host = host.rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        return bool(shutil.which("ollama"))

    def generate(self, prompt: Dict[str, Any]) -> str:
        try:
            import requests
        except Exception:
            return ""
        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model_id,
                    "prompt": json.dumps(prompt, separators=(",", ":")),
                    "stream": False,
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
            return str(data.get("response", ""))
        except Exception:
            return ""


class LocalHttpRunner:
    def __init__(self, model_id: str, endpoint: str, timeout: int = 12):
        self.model_id = model_id
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        if not self.endpoint:
            return False
        try:
            import requests
            resp = requests.get(f"{self.endpoint}/v1/models", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: Dict[str, Any]) -> str:
        if not self.endpoint:
            return ""
        try:
            import requests
        except Exception:
            return ""
        try:
            payload = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": json.dumps(prompt, separators=(",", ":"))}],
                "temperature": 0.2,
                "max_tokens": 1024,
            }
            resp = requests.post(f"{self.endpoint}/v1/chat/completions", json=payload, timeout=self.timeout)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return ""
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content
            text = choices[0].get("text")
            if isinstance(text, str):
                return text
        except Exception:
            return ""
        return ""


def _load_reporting_ai_settings() -> Dict[str, Any]:
    defaults = {
        "enabled": True,
        "provider": "auto",
        "model_id": "rule_based_v1",
        "endpoint": "",
        "timeout_seconds": 15,
        "news_freshness_hours": 4,
    }
    settings_path = os.path.join("config", "settings.json")
    if not os.path.exists(settings_path):
        return defaults
    try:
        with open(settings_path, "r", encoding="ascii") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return defaults
    except Exception:
        return defaults
    reporting = data.get("reporting", {})
    if isinstance(reporting, dict):
        reporting_ai = reporting.get("ai", {})
        if isinstance(reporting_ai, dict) and reporting_ai:
            return {**defaults, **reporting_ai}
    ai = data.get("ai", {})
    if not isinstance(ai, dict):
        return defaults
    return {**defaults, **ai}


def _normalize_model_id(model_id: str) -> str:
    cleaned = (model_id or "").strip()
    if not cleaned or cleaned == "rule_based_v1":
        return "llama3"
    return cleaned


def select_model_runner(settings: Optional[Dict[str, Any]] = None) -> ModelRunner:
    ai = settings or _load_reporting_ai_settings()
    if not bool(ai.get("enabled", True)):
        return NoModelRunner()
    provider = str(ai.get("provider", "auto")).lower()
    model_id = _normalize_model_id(str(ai.get("model_id", "rule_based_v1")))
    endpoint = str(ai.get("endpoint", "") or "").strip()
    timeout = int(ai.get("timeout_seconds", 15) or 15)
    if provider == "ollama":
        runner = OllamaRunner(model_id=model_id, timeout=timeout)
        return runner if runner.available() else NoModelRunner()
    if provider == "local_http":
        runner = LocalHttpRunner(model_id=model_id, endpoint=endpoint, timeout=timeout)
        return runner if runner.available() else NoModelRunner()
    if provider == "auto":
        runner = OllamaRunner(model_id=model_id, timeout=timeout)
        if runner.available():
            return runner
        runner = LocalHttpRunner(model_id=model_id, endpoint=endpoint, timeout=timeout)
        if runner.available():
            return runner
    return NoModelRunner()


class PromptBuilder:
    @staticmethod
    def build(payload: ReportPayload) -> Dict[str, Any]:
        citations = payload.data.get("citations", [])
        return {
            "system": "You are a cautious financial analyst. Output valid JSON only.",
            "schema": {
                "summary": "list[str]",
                "sections": [{"title": "str", "rows": "list[list[str]]"}],
                "citations": "list[str]",
                "risks": "list[str]",
            },
            "report": {
                "type": payload.report_type,
                "client": payload.client_name,
                "generated_at": payload.generated_at,
                "sections": [section.__dict__ for section in payload.sections],
                "data": payload.data,
                "citations": citations,
                "methodology": payload.methodology,
            },
        }


class ReportRenderer:
    @staticmethod
    def render_markdown(payload: ReportPayload) -> str:
        lines = [
            f"# {payload.report_type.replace('_', ' ').title()}",
            f"Client: {payload.client_name}",
            f"Generated: {payload.generated_at}",
            f"Interval: {payload.interval}",
            "",
        ]
        for section in payload.sections:
            lines.append(f"## {section.title}")
            for row in section.rows:
                if len(row) == 2:
                    lines.append(f"- **{row[0]}**: {row[1]}")
                else:
                    lines.append(f"- {row[0]}")
            lines.append("")
        lines.append("## Data Freshness")
        for key, value in payload.data_freshness.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")
        lines.append("## Methodology")
        for note in payload.methodology:
            lines.append(f"- {note}")
        lines.append("")
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def render_json(payload: ReportPayload) -> str:
        return json.dumps(payload, default=lambda o: o.__dict__, indent=2)

    @staticmethod
    def render_terminal(payload: ReportPayload) -> str:
        lines = [
            f"{payload.report_type.replace('_', ' ').title()}",
            f"Client: {payload.client_name}",
            f"Generated: {payload.generated_at}",
            f"Interval: {payload.interval}",
            "",
        ]
        for section in payload.sections:
            lines.append(f"[{section.title}]")
            for row in section.rows:
                if len(row) == 2:
                    lines.append(f"{row[0]}: {row[1]}")
                else:
                    lines.append(str(row[0]))
            lines.append("")
        return "\n".join(lines).strip() + "\n"


def validate_report_schema(raw: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    if not isinstance(raw, dict):
        return False, ["Payload is not a dict."]
    for key in ("summary", "sections", "citations", "risks"):
        if key not in raw:
            errors.append(f"Missing key: {key}")
    if "sections" in raw and not isinstance(raw["sections"], list):
        errors.append("sections must be a list.")
    return (len(errors) == 0), errors


class ReportEngine:
    def __init__(
        self,
        price_service: Optional[PriceService] = None,
        model_runner: Optional[ModelRunner] = None,
    ):
        self.price_service = price_service or OfflinePriceService()
        self.model_runner = model_runner or select_model_runner()

    def generate_client_weekly_brief(
        self,
        client: Client,
        output_format: str = "md",
    ) -> ReportResult:
        payload = self._build_weekly_brief_payload(client)
        validation = {"mode": "template", "errors": []}
        used_model = False

        if self.model_runner.available():
            prompt = PromptBuilder.build(payload)
            raw = self.model_runner.generate(prompt)
            parsed = _safe_json_load(raw)
            ok, errors = validate_report_schema(parsed)
            validation = {"mode": "model", "errors": errors}
            if ok:
                payload = _payload_from_model(payload, parsed)
                used_model = True
            else:
                validation["mode"] = "fallback"

        content = _render_payload(payload, output_format)
        return ReportResult(
            content=content,
            payload=payload,
            output_format=output_format,
            used_model=used_model,
            validation=validation,
        )

    def generate_client_portfolio_report(
        self,
        client: Client,
        output_format: str = "md",
        interval: str = "1M",
        detailed: bool = False,
    ) -> ReportResult:
        payload = self._build_client_portfolio_payload(
            client,
            interval=interval,
            detailed=detailed,
        )
        content = _render_payload(payload, output_format)
        return ReportResult(
            content=content,
            payload=payload,
            output_format=output_format,
            used_model=False,
            validation={"mode": "template", "errors": []},
        )

    def generate_account_portfolio_report(
        self,
        client: Client,
        account,
        output_format: str = "md",
        interval: str = "1M",
    ) -> ReportResult:
        payload = self._build_account_portfolio_payload(client, account, interval=interval)
        content = _render_payload(payload, output_format)
        return ReportResult(
            content=content,
            payload=payload,
            output_format=output_format,
            used_model=False,
            validation={"mode": "template", "errors": []},
        )

    def _build_weekly_brief_payload(self, client: Client) -> ReportPayload:
        generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        interval = "1W"
        holdings = _aggregate_holdings(client)
        lot_map = _aggregate_lots(client)
        prices = self.price_service.get_quotes(holdings.keys())
        portfolio_rows, portfolio_meta = _portfolio_snapshot(holdings, lot_map, prices)

        news_items = _load_cached_news()
        ai_settings = _load_reporting_ai_settings()
        freshness_hours = int(ai_settings.get("news_freshness_hours", 4) or 4)
        news_items = filter_fresh_news_items(news_items, max_age_hours=freshness_hours)
        news_rows, news_meta = _news_section(news_items, holdings.keys())

        tracker_rows, tracker_meta = _tracker_section()

        risk_rows = [
            ["Risk Notes", "Risk metrics require market history; offline mode uses templates."],
        ]
        conflict_rows = _conflict_rows(news_items)

        sections = [
            ReportSection("Portfolio Snapshot", portfolio_rows),
            ReportSection("Ticker News", news_rows),
            ReportSection("Risk Notes", risk_rows),
            ReportSection("Conflict/Geo Notes", conflict_rows),
            ReportSection("Aviation/Maritime Notes", tracker_rows),
        ]

        data = {
            "citations": portfolio_meta.get("citations", []) + news_meta.get("citations", []) + tracker_meta.get("citations", []),
            "news_count": news_meta.get("news_count", 0),
        }
        data_freshness = {
            "portfolio": portfolio_meta.get("as_of", "unknown"),
            "news_cache": news_meta.get("cache_ts", "unknown"),
            "trackers_cache": tracker_meta.get("cache_ts", "unknown"),
        }
        methodology = [
            "Cost basis uses weighted average of lots and aggregate entries.",
            "Market value uses offline prices unless a live price service is enabled.",
            "News section uses cached feeds only unless refresh is explicitly run.",
        ]
        return ReportPayload(
            report_type="client_weekly_brief",
            client_id=client.client_id,
            client_name=client.name,
            generated_at=generated_at,
            interval=interval,
            sections=sections,
            data=data,
            data_freshness=data_freshness,
            methodology=methodology,
        )

    def _build_client_portfolio_payload(
        self,
        client: Client,
        interval: str = "1M",
        detailed: bool = False,
    ) -> ReportPayload:
        generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        interval = str(interval or "1M").upper()
        holdings = _aggregate_holdings(client)
        lot_map = _aggregate_lots(client)
        prices = self.price_service.get_quotes(holdings.keys())
        client_manual = sum(_manual_holdings_total(acc.manual_holdings) for acc in client.accounts)
        totals = _portfolio_totals(holdings, lot_map, prices, manual_value=client_manual)
        portfolio_rows, portfolio_meta = _portfolio_snapshot(holdings, lot_map, prices)

        account_rows = []
        account_sections = []
        for account in client.accounts:
            account_holdings = _account_holdings(account)
            account_lots = _account_lots(account)
            account_prices = self.price_service.get_quotes(account_holdings.keys())
            account_manual = _manual_holdings_total(account.manual_holdings)
            account_totals = _portfolio_totals(
                account_holdings,
                account_lots,
                account_prices,
                manual_value=account_manual,
            )
            account_rows.append([
                account.account_name,
                account.account_type,
                str(len(account_holdings)),
                f"${account_totals['total_cost']:,.2f}",
                _format_value(account_totals["total_value"]),
                _format_value(account_totals["manual_value"]),
            ])
            if detailed:
                account_detail_rows, _ = _portfolio_snapshot(account_holdings, account_lots, account_prices)
                account_sections.append(ReportSection(f"Account Detail: {account.account_name}", account_detail_rows))

        profile_rows = [
            ["Client ID", client.client_id],
            ["Risk Profile", client.risk_profile],
            ["Reporting Currency", (client.tax_profile or {}).get("reporting_currency", "USD")],
            ["Accounts", str(len(client.accounts))],
            ["Holdings", str(len(holdings))],
        ]
        totals_rows = [
            ["Total Cost Basis", f"${totals['total_cost']:,.2f}"],
            ["Total Market Value", _format_value(totals["total_value"])],
            ["Manual Holdings", _format_value(totals["manual_value"])],
        ]
        account_header = ["Account", "Type", "Holdings", "Cost Basis", "Market Value", "Manual Value"]
        sections = [
            ReportSection("Client Profile", profile_rows),
            ReportSection("Portfolio Totals", totals_rows),
            ReportSection("Accounts Summary", [account_header] + account_rows if account_rows else [["No accounts"]]),
            ReportSection("Holdings Detail", portfolio_rows),
        ]
        if detailed:
            dashboard = portfolio_dashboard(client, interval=interval)
            patterns = client_patterns(client, interval=interval)
            interval_rows = [
                ["Interval", interval],
                ["Total Value", _format_value(dashboard["totals"].get("total_value"))],
                ["Market Value", _format_value(dashboard["totals"].get("market_value"))],
                ["Manual Value", _format_value(dashboard["totals"].get("manual_value"))],
                ["Holdings Count", str(dashboard["totals"].get("holdings_count", 0))],
                ["Manual Assets", str(dashboard["totals"].get("manual_count", 0))],
            ]
            sections.append(ReportSection("Interval Overview", interval_rows))

            risk_payload = dashboard.get("risk", {}) or {}
            metrics = risk_payload.get("metrics", {}) or {}
            metric_labels = {
                "mean_annual": "Annual Return",
                "vol_annual": "Volatility",
                "sharpe": "Sharpe",
                "sortino": "Sortino",
                "beta": "Beta",
                "alpha_annual": "Alpha",
                "r_squared": "R-Squared",
                "max_drawdown": "Max Drawdown",
                "var_95": "VaR 95%",
                "cvar_95": "CVaR 95%",
                "points": "Sample Points",
            }
            risk_rows = []
            for key, label in metric_labels.items():
                if key in metrics:
                    value = metrics.get(key)
                    if key in ("mean_annual", "vol_annual", "alpha_annual", "max_drawdown", "var_95", "cvar_95"):
                        risk_rows.append([label, _format_pct(value)])
                    elif key == "r_squared":
                        risk_rows.append([label, _format_number(value, 3)])
                    elif key == "points":
                        risk_rows.append([label, str(int(value or 0))])
                    else:
                        risk_rows.append([label, _format_number(value, 3)])
            if risk_rows:
                sections.append(ReportSection("Risk Metrics", risk_rows))
            distribution = risk_payload.get("distribution", []) or []
            if distribution:
                dist_rows = []
                for row in distribution[:10]:
                    dist_rows.append([
                        f"{row.get('bin_start', 0):.3f} to {row.get('bin_end', 0):.3f}",
                        str(row.get("count", 0)),
                    ])
                sections.append(ReportSection("Return Distribution", dist_rows))

            regime = dashboard.get("regime", {}) or {}
            if not regime.get("error"):
                regime_rows = [
                    ["Current Regime", regime.get("current_regime", "N/A")],
                    ["Confidence", _format_pct(regime.get("confidence"))],
                    ["Expected Next", str((regime.get("expected_next") or {}).get("regime", "N/A"))],
                    ["Stability", _format_pct(regime.get("stability"))],
                    ["Samples", str(regime.get("samples", 0))],
                ]
                metrics = regime.get("metrics", {}) or {}
                if metrics:
                    regime_rows.extend(
                        [
                            ["Avg Return (annual)", _format_pct(metrics.get("avg_return"))],
                            ["Volatility (annual)", _format_pct(metrics.get("volatility"))],
                        ]
                    )
                sections.append(ReportSection("Regime Snapshot", regime_rows))

            diagnostics = dashboard.get("diagnostics", {}) or {}
            sector_rows = diagnostics.get("sectors", []) or []
            if sector_rows:
                rows = [
                    [row.get("sector", "N/A"), _format_pct(row.get("pct"))]
                    for row in sector_rows
                ]
                rows.append(["HHI", _format_number(diagnostics.get("hhi"), 3)])
                sections.append(ReportSection("Sector Concentration", rows))
            movers = []
            for row in diagnostics.get("gainers", []) or []:
                movers.append([f"Top Gainer {row.get('ticker', '-')}", _format_pct(row.get("pct"))])
            for row in diagnostics.get("losers", []) or []:
                movers.append([f"Top Loser {row.get('ticker', '-')}", _format_pct(row.get("pct"))])
            if movers:
                sections.append(ReportSection("Top Movers", movers))

            if patterns and not patterns.get("error"):
                pattern_rows = [
                    ["Entropy", _format_number(patterns.get("entropy"), 4)],
                    ["Perm Entropy", _format_number(patterns.get("perm_entropy"), 4)],
                    ["Hurst", _format_number(patterns.get("hurst"), 4)],
                    ["Change Points", str(len(patterns.get("change_points", []) or []))],
                    ["Motifs", str(len(patterns.get("motifs", []) or []))],
                ]
                sections.append(ReportSection("Pattern Analysis", pattern_rows))
                axis_rows = []
                wave_axis = (patterns.get("wave_surface") or {}).get("axis") or {}
                fft_axis = (patterns.get("fft_surface") or {}).get("axis") or {}
                if wave_axis:
                    axis_rows.append([
                        "Wave Surface",
                        f"X={wave_axis.get('x_label','X')} ({wave_axis.get('x_unit','')}) | "
                        f"Y={wave_axis.get('y_label','Y')} ({wave_axis.get('y_unit','')}) | "
                        f"Z={wave_axis.get('z_label','Z')} ({wave_axis.get('z_unit','')})"
                    ])
                if fft_axis:
                    axis_rows.append([
                        "FFT Surface",
                        f"X={fft_axis.get('x_label','X')} ({fft_axis.get('x_unit','')}) | "
                        f"Y={fft_axis.get('y_label','Y')} ({fft_axis.get('y_unit','')}) | "
                        f"Z={fft_axis.get('z_label','Z')} ({fft_axis.get('z_unit','')})"
                    ])
                if axis_rows:
                    sections.append(ReportSection("3D Axis Context", axis_rows))

            if account_sections:
                sections.extend(account_sections)

        data_freshness = {
            "portfolio": portfolio_meta.get("as_of", generated_at),
            "interval": interval,
        }
        methodology = [
            "Account cost basis uses weighted average of lots and aggregate entries.",
            "Market value uses offline prices unless a live price service is enabled.",
            "Manual holdings are included when explicit total values are provided.",
            "Interval analytics match the report interval selection.",
        ]
        return ReportPayload(
            report_type="client_portfolio_detail" if detailed else "client_portfolio_export",
            client_id=client.client_id,
            client_name=client.name,
            generated_at=generated_at,
            interval=interval,
            sections=sections,
            data={"citations": portfolio_meta.get("citations", [])},
            data_freshness=data_freshness,
            methodology=methodology,
        )

    def _build_account_portfolio_payload(
        self,
        client: Client,
        account,
        interval: str = "1M",
    ) -> ReportPayload:
        generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        interval = str(interval or "1M").upper()
        holdings = _account_holdings(account)
        lot_map = _account_lots(account)
        prices = self.price_service.get_quotes(holdings.keys())
        manual_value = _manual_holdings_total(account.manual_holdings)
        totals = _portfolio_totals(holdings, lot_map, prices, manual_value=manual_value)
        rows, meta = _portfolio_snapshot(holdings, lot_map, prices)

        profile_rows = [
            ["Client", client.name],
            ["Account ID", account.account_id],
            ["Account Name", account.account_name],
            ["Account Type", account.account_type],
            ["Holdings", str(len(holdings))],
        ]
        totals_rows = [
            ["Total Cost Basis", f"${totals['total_cost']:,.2f}"],
            ["Total Market Value", _format_value(totals["total_value"])],
            ["Manual Holdings", _format_value(totals["manual_value"])],
        ]
        sections = [
            ReportSection("Account Profile", profile_rows),
            ReportSection("Account Totals", totals_rows),
            ReportSection("Holdings Detail", rows),
        ]
        dashboard = account_dashboard(client, account, interval=interval)
        patterns = account_patterns(client, account, interval=interval)
        interval_rows = [
            ["Interval", interval],
            ["Total Value", _format_value(dashboard["totals"].get("total_value"))],
            ["Market Value", _format_value(dashboard["totals"].get("market_value"))],
            ["Manual Value", _format_value(dashboard["totals"].get("manual_value"))],
        ]
        sections.append(ReportSection("Interval Overview", interval_rows))
        risk_payload = dashboard.get("risk", {}) or {}
        metrics = risk_payload.get("metrics", {}) or {}
        risk_rows = []
        for key, value in metrics.items():
            risk_rows.append([key.replace("_", " ").title(), _format_number(value, 3)])
        if risk_rows:
            sections.append(ReportSection("Risk Metrics", risk_rows))
        if patterns and not patterns.get("error"):
            pattern_rows = [
                ["Entropy", _format_number(patterns.get("entropy"), 4)],
                ["Perm Entropy", _format_number(patterns.get("perm_entropy"), 4)],
                ["Hurst", _format_number(patterns.get("hurst"), 4)],
            ]
            sections.append(ReportSection("Pattern Analysis", pattern_rows))
        return ReportPayload(
            report_type="account_portfolio_export",
            client_id=client.client_id,
            client_name=client.name,
            generated_at=generated_at,
            interval=interval,
            sections=sections,
            data={"citations": meta.get("citations", [])},
            data_freshness={"portfolio": meta.get("as_of", generated_at), "interval": interval},
            methodology=[
                "Account cost basis uses weighted average of lots and aggregate entries.",
                "Market value uses offline prices unless a live price service is enabled.",
                "Interval analytics match the report interval selection.",
            ],
        )


def report_health_check() -> Dict[str, Any]:
    ai = _load_reporting_ai_settings()
    ollama_installed = bool(shutil.which("ollama"))
    ollama_reachable = False
    if ollama_installed:
        try:
            import requests
            resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
            ollama_reachable = resp.status_code == 200
        except Exception:
            ollama_reachable = False
    local_endpoint = str(ai.get("endpoint", "") or "").strip()
    local_reachable = False
    if local_endpoint:
        try:
            import requests
            resp = requests.get(f"{local_endpoint.rstrip('/')}/v1/models", timeout=2)
            local_reachable = resp.status_code == 200
        except Exception:
            local_reachable = False
    return {
        "ollama_installed": ollama_installed,
        "ollama_reachable": ollama_reachable,
        "local_http_endpoint": local_endpoint or None,
        "local_http_reachable": local_reachable,
        "report_engine": "ok",
        "timestamp": int(time.time()),
    }


def _render_payload(payload: ReportPayload, output_format: str) -> str:
    fmt = (output_format or "md").lower()
    if fmt == "json":
        return ReportRenderer.render_json(payload)
    if fmt == "terminal":
        return ReportRenderer.render_terminal(payload)
    return ReportRenderer.render_markdown(payload)


def _safe_json_load(raw: str) -> Dict[str, Any]:
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _payload_from_model(base: ReportPayload, parsed: Dict[str, Any]) -> ReportPayload:
    sections = []
    for section in parsed.get("sections", []) or []:
        title = str(section.get("title", "Section"))
        rows = section.get("rows", []) or []
        rows_clean = [[str(cell) for cell in row] for row in rows]
        sections.append(ReportSection(title, rows_clean))
    base.sections = sections if sections else base.sections
    return base


def _aggregate_holdings(client: Client) -> Dict[str, float]:
    holdings: Dict[str, float] = {}
    for acc in client.accounts:
        for ticker, qty in (acc.holdings or {}).items():
            t = normalize_ticker(ticker)
            holdings[t] = holdings.get(t, 0.0) + float(qty or 0.0)
    return holdings


def _aggregate_lots(client: Client) -> Dict[str, List[Dict[str, Any]]]:
    lots: Dict[str, List[Dict[str, Any]]] = {}
    for acc in client.accounts:
        for ticker, entries in (acc.lots or {}).items():
            t = normalize_ticker(ticker)
            lots.setdefault(t, []).extend(entries or [])
    return lots


def _account_holdings(account) -> Dict[str, float]:
    holdings: Dict[str, float] = {}
    for raw_ticker, qty in (account.holdings or {}).items():
        ticker = normalize_ticker(raw_ticker)
        try:
            holdings[ticker] = holdings.get(ticker, 0.0) + float(qty or 0.0)
        except Exception:
            holdings[ticker] = holdings.get(ticker, 0.0)
    return holdings


def _account_lots(account) -> Dict[str, List[Dict[str, Any]]]:
    lots: Dict[str, List[Dict[str, Any]]] = {}
    for raw_ticker, entries in (account.lots or {}).items():
        ticker = normalize_ticker(raw_ticker)
        lots[ticker] = list(entries or [])
    return lots


def _format_value(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def _format_number(value: Optional[float], precision: int = 4) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{precision}f}"


def _format_pct(value: Optional[float], precision: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.{precision}f}%"


def _portfolio_snapshot(
    holdings: Dict[str, float],
    lot_map: Dict[str, List[Dict[str, Any]]],
    prices: Dict[str, float],
) -> Tuple[List[List[str]], Dict[str, Any]]:
    rows: List[List[str]] = []
    total_cost = 0.0
    total_value = 0.0
    citations = []
    for ticker, qty in holdings.items():
        lots = lot_map.get(ticker, [])
        avg_cost = compute_weighted_avg_cost(lots)
        total_cost_t = avg_cost * qty
        price = prices.get(ticker)
        if price:
            market_value = price * qty
            total_value += market_value
            pl = market_value - total_cost_t
            rows.append([ticker, f"{qty:,.4f} sh | avg ${avg_cost:,.2f} | mv ${market_value:,.2f} | P/L ${pl:,.2f}"])
        else:
            rows.append([ticker, f"{qty:,.4f} sh | avg ${avg_cost:,.2f} | mv N/A"])
        total_cost += total_cost_t
    rows.append(["Total Cost Basis", f"${total_cost:,.2f}"])
    if total_value > 0:
        rows.append(["Total Market Value", f"${total_value:,.2f}"])
    return rows, {"citations": citations, "as_of": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")}


def _portfolio_totals(
    holdings: Dict[str, float],
    lot_map: Dict[str, List[Dict[str, Any]]],
    prices: Dict[str, float],
    manual_value: float = 0.0,
) -> Dict[str, Optional[float]]:
    total_cost = 0.0
    total_value = 0.0
    for ticker, qty in holdings.items():
        lots = lot_map.get(ticker, [])
        avg_cost = compute_weighted_avg_cost(lots)
        total_cost += avg_cost * qty
        price = prices.get(ticker)
        if price:
            total_value += price * qty
    return {
        "total_cost": total_cost,
        "total_value": total_value if total_value > 0 else None,
        "manual_value": manual_value if manual_value > 0 else None,
    }


def _manual_holdings_total(entries: List[Dict[str, Any]]) -> float:
    total = 0.0
    for entry in entries or []:
        try:
            total += float(entry.get("total_value", 0.0) or 0.0)
        except Exception:
            continue
    return total


def _load_cached_news() -> List[Dict[str, Any]]:
    path = os.path.join("data", "intel_news.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("items", []) if isinstance(payload, dict) else []
    except Exception:
        return []


def _news_section(items: List[Dict[str, Any]], tickers: Iterable[str]) -> Tuple[List[List[str]], Dict[str, Any]]:
    tickers_upper = [normalize_ticker(t) for t in tickers]
    rows: List[List[str]] = []
    citations = []
    scored = score_news_items(items, tickers=tickers_upper)
    threshold = 4 if tickers_upper else 1
    for score, item in scored:
        if score < threshold:
            continue
        title = str(item.get("title", ""))
        source = str(item.get("source", ""))
        rows.append([source or "News", title[:120]])
        if source:
            citations.append(source)
    if not rows:
        rows.append(["News", "No cached news matched holdings."])
    cache_ts = "-"
    try:
        cache_ts = datetime.fromtimestamp(int(os.path.getmtime(os.path.join("data", "intel_news.json"))), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        cache_ts = "unknown"
    return rows[:8], {"citations": citations, "news_count": len(rows), "cache_ts": cache_ts}


def _conflict_rows(items: List[Dict[str, Any]]) -> List[List[str]]:
    rows = []
    for item in items:
        tags = [str(t).lower() for t in (item.get("tags") or [])]
        title = str(item.get("title", ""))
        if "conflict" in tags or any(word in title.lower() for word in ("conflict", "war", "strike", "attack")):
            rows.append([item.get("source", "News"), title[:120]])
    if not rows:
        rows.append(["Conflict", "No conflict-tagged cached news found."])
    return rows[:6]


def _tracker_section() -> Tuple[List[List[str]], Dict[str, Any]]:
    tracker = GlobalTrackers()
    snapshot = tracker.get_snapshot(mode="combined", allow_refresh=False)
    points = snapshot.get("flights", []) + snapshot.get("ships", [])
    rows = []
    if points:
        rows.append(["Tracker Points", f"{len(points)} cached entities"])
    else:
        rows.append(["Tracker Points", "No cached tracker points available."])
    cache_ts = tracker._last_refresh if hasattr(tracker, "_last_refresh") else None
    cache_label = "unknown"
    if cache_ts:
        cache_label = datetime.fromtimestamp(int(cache_ts), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return rows, {"citations": ["Flight Feed", "Shipping Feed"], "cache_ts": cache_label}
