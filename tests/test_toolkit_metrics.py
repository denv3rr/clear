import math
import unittest
from datetime import datetime, timedelta

import pandas as pd

from modules.client_mgr.toolkit import FinancialToolkit
from modules.client_mgr.client_model import Client


class ToolkitMetricsTests(unittest.TestCase):
    def test_annualization_factor_from_index_daily(self):
        dates = pd.date_range(datetime(2025, 1, 1), periods=6, freq="D")
        returns = pd.Series([0.01, -0.005, 0.002, 0.0, 0.003], index=dates[1:])
        ann = FinancialToolkit._annualization_factor_from_index(returns)
        self.assertGreater(ann, 300.0)
        self.assertLess(ann, 400.0)

    def test_compute_risk_metrics_constant(self):
        dates = pd.date_range(datetime(2025, 1, 1), periods=10, freq="D")
        returns = pd.Series([0.01] * 9, index=dates[1:])
        toolkit = FinancialToolkit(Client())
        metrics = toolkit._compute_risk_metrics(returns, None, risk_free_annual=0.0)
        ann = FinancialToolkit._annualization_factor_from_index(returns)
        expected_mean = returns.mean() * ann
        self.assertAlmostEqual(metrics["vol_annual"], 0.0, places=6)
        self.assertAlmostEqual(metrics["mean_annual"], expected_mean, places=6)

    def test_compute_core_metrics_mean(self):
        dates = pd.date_range(datetime(2025, 1, 1), periods=6, freq="D")
        returns = pd.Series([0.01, 0.00, -0.01, 0.02, 0.01], index=dates[1:])
        metrics = FinancialToolkit._compute_core_metrics(returns)
        ann = FinancialToolkit._annualization_factor_from_index(returns)
        expected = returns.mean() * ann
        self.assertTrue(math.isfinite(metrics["mean_return"]))
        self.assertAlmostEqual(metrics["mean_return"], expected, places=6)

    def test_entropy_and_hurst_helpers(self):
        dates = pd.date_range(datetime(2025, 1, 1), periods=30, freq="D")
        returns = pd.Series([0.001] * 29, index=dates[1:])
        entropy = FinancialToolkit._shannon_entropy(returns, bins=6)
        values = FinancialToolkit._returns_to_values(returns)
        hurst = FinancialToolkit._hurst_exponent(values)
        self.assertTrue(entropy >= 0.0)
        self.assertTrue(0.0 <= hurst <= 2.0)


if __name__ == "__main__":
    unittest.main()
