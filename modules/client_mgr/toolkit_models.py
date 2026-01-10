from typing import List

from modules.client_mgr.client_model import Client


class ModelSelector:
    """
    Logic engine that determines which financial models are appropriate
    based on client risk profile, account types, and asset classes.
    """

    @staticmethod
    def analyze_suitability(client: Client) -> List[str]:
        recommendations = []

        account_types = [a.account_type.lower() for a in client.accounts]
        has_derivatives = any("option" in t or "derivative" in t for t in account_types)
        has_crypto = any("crypto" in t for t in account_types)

        if has_derivatives:
            recommendations.append(
                "Black-Scholes Option Pricing (Derivatives detected)"
            )

        if has_crypto or client.risk_profile == "Aggressive":
            recommendations.append(
                "[red]AGGRESSIVE WARN[/red]: Check Sortino Ratio (Downside volatility focus for high risk assets)\n"
                "  - see Multi-Model Risk Dashboard"
            )

        recommendations.append("CAPM (Capital Asset Pricing Model) - Standard Equity Baseline")

        return recommendations
