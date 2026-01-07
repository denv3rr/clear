from __future__ import annotations

import math
from typing import Tuple, List, Dict, Any, Optional

import numpy as np
import pandas as pd


def annualization_factor_from_index(returns: pd.Series) -> float:
    try:
        idx = returns.index
        if not isinstance(idx, pd.DatetimeIndex) or len(idx) < 2:
            return 252.0
        deltas = idx.to_series().diff().dropna().dt.total_seconds()
        deltas = deltas[deltas > 0]
        if deltas.empty:
            return 252.0
        avg_delta = float(deltas.mean())
        seconds_per_year = 365.25 * 24 * 60 * 60
        return seconds_per_year / avg_delta
    except Exception:
        return 252.0


def compute_core_metrics(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
) -> Dict[str, Any]:
    """Centralized math engine for chart-ready summary metrics."""
    if returns.empty:
        return {}

    ann_factor = annualization_factor_from_index(returns)
    std_dev = returns.std(ddof=1)
    vol = std_dev * np.sqrt(ann_factor)
    sharpe = (returns.mean() / std_dev) * np.sqrt(ann_factor) if std_dev != 0 else 0.0

    metrics = {
        "volatility_annual": float(vol),
        "sharpe": float(sharpe),
        "mean_return": float(returns.mean() * ann_factor),
    }

    if benchmark_returns is not None and not benchmark_returns.empty:
        combined = pd.concat([returns, benchmark_returns], axis=1).dropna()
        if len(combined) > 5:
            cov = np.cov(combined.iloc[:, 0], combined.iloc[:, 1])[0, 1]
            mkt_var = np.var(combined.iloc[:, 1])
            beta = cov / mkt_var if mkt_var != 0 else 1.0
            metrics["beta"] = float(beta)

    return metrics


def black_scholes_price(
    spot_price: float,
    strike_price: float,
    time_years: float,
    volatility: float,
    risk_free: float,
) -> Tuple[float, float]:
    """
    Calculates European Call/Put prices using Black-Scholes-Merton.
    """
    if spot_price <= 0 or strike_price <= 0 or time_years <= 0 or volatility <= 0:
        return float("nan"), float("nan")

    d1 = (math.log(spot_price / strike_price) + (risk_free + 0.5 * volatility ** 2) * time_years) / (volatility * math.sqrt(time_years))
    d2 = d1 - volatility * math.sqrt(time_years)

    def N(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    call_price = spot_price * N(d1) - strike_price * math.exp(-risk_free * time_years) * N(d2)
    put_price = strike_price * math.exp(-risk_free * time_years) * N(-d2) - spot_price * N(-d1)
    return float(call_price), float(put_price)


def calculate_max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    cumulative_returns = (1 + returns).cumprod()
    peak = cumulative_returns.expanding(min_periods=1).max()
    drawdown = (cumulative_returns - peak) / peak
    return drawdown.min()


def calculate_var_cvar(returns: pd.Series, confidence_level: float) -> Tuple[float, float]:
    if returns.empty:
        return 0.0, 0.0
    var = returns.quantile(1 - confidence_level)
    cvar = returns[returns <= var].mean()
    return float(var), float(cvar)


def shannon_entropy(returns: pd.Series, bins: int = 12) -> float:
    values = np.array(returns, dtype=float)
    if len(values) < 5:
        return 0.0
    counts, _ = np.histogram(values, bins=bins, density=False)
    total = float(counts.sum())
    if total <= 0:
        return 0.0
    probs = counts / total
    probs = probs[probs > 0]
    entropy = float(-np.sum(probs * np.log2(probs)))
    return max(0.0, entropy)


def permutation_entropy(values: List[float], order: int = 3, delay: int = 1) -> float:
    if not values or order < 2 or delay < 1:
        return 0.0
    n = len(values)
    max_start = n - delay * (order - 1)
    if max_start <= 0:
        return 0.0
    patterns = {}
    for start in range(max_start):
        window = [values[start + i * delay] for i in range(order)]
        ranks = tuple(np.argsort(window))
        patterns[ranks] = patterns.get(ranks, 0) + 1
    total = float(sum(patterns.values()))
    if total <= 0:
        return 0.0
    probs = np.array([count / total for count in patterns.values()], dtype=float)
    entropy = float(-np.sum(probs * np.log2(probs)))
    max_entropy = math.log2(math.factorial(order))
    if max_entropy <= 0:
        return 0.0
    return max(0.0, min(1.0, entropy / max_entropy))


def hurst_exponent(values: List[float]) -> float:
    if not values or len(values) < 20:
        return 0.5
    
    series = np.array(values, dtype=float)
    n_min = 10
    n_max = len(series) // 2
    lags = range(n_min, n_max)
    
    rs_values = []
    for lag in lags:
        # Create sub-series of length `lag`
        sub_series_count = len(series) // lag
        if sub_series_count == 0:
            continue
            
        rs_sub_values = []
        for i in range(sub_series_count):
            sub_series = series[i*lag : (i+1)*lag]
            mean = np.mean(sub_series)
            deviates = sub_series - mean
            cumulative_deviates = np.cumsum(deviates)
            r = np.max(cumulative_deviates) - np.min(cumulative_deviates)
            s = np.std(sub_series)
            if s > 0:
                rs_sub_values.append(r / s)
        
        if rs_sub_values:
            rs_values.append(np.mean(rs_sub_values))

    if not rs_values:
        return 0.5

    poly = np.polyfit(np.log(lags[:len(rs_values)]), np.log(rs_values), 1)
    return float(poly[0])


def fft_spectrum(values: List[float], top_n: int = 6) -> List[Tuple[float, float]]:
    if not values or len(values) < 8:
        return []
    series = np.array(values, dtype=float)
    series = series - series.mean()
    spec = np.fft.rfft(series)
    power = np.abs(spec) ** 2
    freqs = np.fft.rfftfreq(len(series), d=1.0)
    pairs = list(zip(freqs[1:], power[1:]))
    pairs.sort(key=lambda item: item[1], reverse=True)
    return pairs[:top_n]


def cusum_change_points(returns: pd.Series, threshold: float = 5.0) -> List[int]:
    values = np.array(returns, dtype=float)
    if len(values) < 10:
        return []
    mean = values.mean()
    std = values.std(ddof=1) or 1e-6
    k = 0.5 * std
    h = threshold * std
    pos = 0.0
    neg = 0.0
    change_points = []
    for i, x in enumerate(values):
        pos = max(0.0, pos + x - mean - k)
        neg = min(0.0, neg + x - mean + k)
        if pos > h or abs(neg) > h:
            change_points.append(i)
            pos = 0.0
            neg = 0.0
    return change_points


def motif_similarity(returns: pd.Series, window: int = 20, top: int = 3) -> List[Dict[str, Any]]:
    values = np.array(returns, dtype=float)
    if len(values) < window * 2:
        return []
    current = values[-window:]
    current = (current - current.mean()) / (current.std(ddof=1) or 1.0)
    step = max(1, window // 3)
    matches = []
    for start in range(0, len(values) - window * 2, step):
        seg = values[start:start + window]
        seg = (seg - seg.mean()) / (seg.std(ddof=1) or 1.0)
        dist = float(np.linalg.norm(current - seg))
        matches.append((start, dist))
    matches.sort(key=lambda item: item[1])
    results = []
    index = returns.index
    for start, dist in matches[:top]:
        end = start + window
        label = f"{start}-{end}"
        if isinstance(index, pd.DatetimeIndex):
            label = f"{index[start].date()} to {index[end-1].date()}"
        results.append({"window": label, "distance": dist})
    return results


def ewma_vol_forecast(returns: pd.Series, lam: float = 0.94, steps: int = 6) -> List[float]:
    values = np.array(returns, dtype=float)
    if len(values) < 2:
        return []
    var = np.var(values, ddof=1)
    for r in values:
        var = lam * var + (1.0 - lam) * (r ** 2)
    forecast = []
    for _ in range(steps):
        var = lam * var
        forecast.append(math.sqrt(var))
    return forecast


def compute_capm_metrics_from_returns(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_annual: float = 0.04,
    min_points: int = 30,
) -> Dict[str, Any]:
    if returns is None or benchmark_returns is None:
        return {"error": "Missing returns", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
    if returns.empty or benchmark_returns.empty:
        return {"error": "No return history", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}

    joined = pd.concat(
        [returns.rename("p"), benchmark_returns.rename("m")],
        axis=1,
    ).dropna()
    if joined.empty or len(joined) < min_points:
        return {
            "error": "Insufficient return history",
            "beta": None,
            "alpha_annual": None,
            "r_squared": None,
            "sharpe": None,
            "vol_annual": None,
            "points": int(len(joined)),
        }

    ann_factor = annualization_factor_from_index(joined["p"])
    p = joined["p"].values
    m = joined["m"].values

    var_m = float(np.var(m, ddof=1))
    cov_pm = float(np.cov(p, m, ddof=1)[0][1])
    beta = (cov_pm / var_m) if var_m > 0 else None

    rf_daily = float(risk_free_annual) / ann_factor
    avg_p = float(np.mean(p))
    avg_m = float(np.mean(m))

    alpha_daily = None
    alpha_annual = None
    if beta is not None:
        alpha_daily = avg_p - (rf_daily + beta * (avg_m - rf_daily))
        alpha_annual = alpha_daily * ann_factor

    corr = float(np.corrcoef(p, m)[0][1])
    r_squared = corr * corr

    std_p = float(np.std(p, ddof=1))
    sharpe = ((avg_p - rf_daily) / std_p * (ann_factor ** 0.5)) if std_p > 0 else None
    vol_annual = std_p * (ann_factor ** 0.5)

    neg = p[p < rf_daily]
    downside_std = float(np.std(neg, ddof=1)) if len(neg) > 1 else None
    downside_vol_annual = downside_std * (ann_factor ** 0.5) if downside_std else None

    sortino = None
    if downside_std and downside_std > 0:
        sortino = (avg_p - rf_daily) / downside_std * (ann_factor ** 0.5)

    jensen_alpha = alpha_annual

    excess = p - m
    te = float(np.std(excess, ddof=1))
    information_ratio = None
    if te > 0:
        information_ratio = (avg_p - avg_m) / te * (ann_factor ** 0.5)

    std_m = float(np.std(m, ddof=1))
    m_squared = None
    if std_p > 0:
        m_squared = ((avg_p - rf_daily) / std_p) * std_m * ann_factor + risk_free_annual

    return {
        "error": "",
        "beta": beta,
        "alpha_annual": alpha_annual,
        "jensen_alpha": jensen_alpha,
        "r_squared": r_squared,
        "sharpe": sharpe,
        "sortino": sortino,
        "information_ratio": information_ratio,
        "m_squared": m_squared,
        "vol_annual": vol_annual,
        "downside_vol_annual": downside_vol_annual,
        "points": int(len(joined)),
    }


def compute_risk_metrics(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series],
    risk_free_annual: float,
) -> Dict[str, Any]:
    ann_factor = annualization_factor_from_index(returns)
    rf_daily = risk_free_annual / ann_factor
    avg_daily = float(returns.mean())
    std_daily = float(returns.std(ddof=1))

    vol_annual = std_daily * (ann_factor ** 0.5)
    mean_annual = avg_daily * ann_factor

    sharpe = None
    if std_daily > 0:
        sharpe = (avg_daily - rf_daily) / std_daily * (ann_factor ** 0.5)

    downside = returns[returns < rf_daily]
    downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = None
    if downside_std > 0:
        sortino = (avg_daily - rf_daily) / downside_std * (ann_factor ** 0.5)

    max_drawdown = calculate_max_drawdown(returns)
    var_95, cvar_95 = calculate_var_cvar(returns, 0.95)
    var_99, cvar_99 = calculate_var_cvar(returns, 0.99)

    beta = None
    alpha_annual = None
    r_squared = None
    information_ratio = None
    treynor = None
    m_squared = None
    tracking_error = None

    if benchmark_returns is not None and not benchmark_returns.empty:
        aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
        if not aligned.empty and len(aligned) > 10:
            p = aligned.iloc[:, 0].values
            m = aligned.iloc[:, 1].values
            var_m = float(np.var(m, ddof=1))
            cov_pm = float(np.cov(p, m, ddof=1)[0][1])
            beta = (cov_pm / var_m) if var_m > 0 else None

            avg_m = float(np.mean(m))
            alpha_annual = (avg_daily - (rf_daily + (beta or 0.0) * (avg_m - rf_daily))) * ann_factor

            corr = float(np.corrcoef(p, m)[0][1])
            r_squared = corr * corr

            active_return = returns - benchmark_returns
            tracking_error = active_return.std() * (ann_factor ** 0.5)
            if tracking_error > 0:
                information_ratio = (returns.mean() - benchmark_returns.mean()) * ann_factor / tracking_error

            if beta is not None and beta != 0:
                treynor = (mean_annual - risk_free_annual) / beta

            m_squared = risk_free_annual + sharpe * (benchmark_returns.std()) * (ann_factor ** 0.5) if sharpe is not None else None

    return {
        "mean_annual": mean_annual,
        "vol_annual": vol_annual,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "var_95": var_95,
        "cvar_95": cvar_95,
        "var_99": var_99,
        "cvar_99": cvar_99,
        "beta": beta,
        "alpha_annual": alpha_annual,
        "r_squared": r_squared,
        "tracking_error": tracking_error,
        "information_ratio": information_ratio,
        "treynor": treynor,
        "m_squared": m_squared,
    }
