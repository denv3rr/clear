import argparse
import sys

from modules.client_mgr.data_handler import DataHandler
from modules.reporting.engine import (
    LivePriceService,
    NoModelRunner,
    OllamaRunner,
    ReportEngine,
    report_health_check,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate offline client reports.")
    parser.add_argument("--client-id", help="Client ID (prefix allowed).")
    parser.add_argument("--format", default="md", choices=["md", "json", "terminal"])
    parser.add_argument("--output", help="Output file path.")
    parser.add_argument("--use-model", action="store_true", help="Enable local model runner.")
    parser.add_argument("--model-id", default="llama3", help="Local model ID.")
    parser.add_argument("--live-prices", action="store_true", help="Enable live price lookups.")
    parser.add_argument("--health-check", action="store_true", help="Run report engine health check.")
    args = parser.parse_args()

    if args.health_check:
        payload = report_health_check()
        print(payload)
        return 0

    if not args.client_id:
        print("Missing --client-id.")
        return 2

    clients = DataHandler.load_clients()
    client = next((c for c in clients if c.client_id.startswith(args.client_id)), None)
    if not client:
        print("Client not found.")
        return 1

    price_service = LivePriceService() if args.live_prices else None
    model_runner = OllamaRunner(model_id=args.model_id) if args.use_model else NoModelRunner()

    engine = ReportEngine(price_service=price_service, model_runner=model_runner)
    result = engine.generate_client_weekly_brief(client, output_format=args.format)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.content)
        print(f"Wrote report to {args.output}")
    else:
        print(result.content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
