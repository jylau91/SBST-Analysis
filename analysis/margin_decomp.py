"""
Margin decomposition engine.

Decomposes quarter-on-quarter EBIT margin changes into three drivers:

  1. Volume effect  – pure ridership growth (at prior-period fare and cost-per-trip)
  2. Fare / yield effect – fare change × current period ridership
  3. Cost efficiency effect – change in cost-per-trip × current ridership (sign-reversed:
     cost reduction improves margin)

Framework (additive bridge, S$M):

  ΔRevenue = Fare effect + Volume (revenue) effect
    Fare effect            = (avg_fare_t − avg_fare_t-1) × ridership_t
    Volume (revenue) effect = avg_fare_t-1 × (ridership_t − ridership_t-1)

  ΔOpEx    = Cost volume effect + Cost efficiency effect
    Cost volume effect     = cost_per_trip_t-1 × (ridership_t − ridership_t-1)
    Cost efficiency effect = (cost_per_trip_t − cost_per_trip_t-1) × ridership_t

  ΔEBIT = ΔRevenue − ΔOpEx
        = Fare effect
          + (Volume revenue effect − Cost volume effect)   ← "Net volume effect"
          − Cost efficiency effect                         ← positive = cost saved

  Residual = actual ΔEBIT − sum of above (should be ~0 or small rounding).

All amounts in S$M.
"""

from __future__ import annotations

import pandas as pd
import numpy as np


def _safe_diff(series: pd.Series) -> pd.Series:
    """First difference, first row is NaN."""
    return series.diff()


def compute_decomposition(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given the tidy financials DataFrame (from data.financials.load_financials),
    return a DataFrame with the bridge columns for each operator × segment ×
    quarter (excluding the first quarter which has no prior period).

    Output columns added (all in S$M):
      delta_revenue, delta_opex, delta_ebit,
      fare_effect, vol_revenue_effect, cost_volume_effect,
      cost_efficiency_effect, net_volume_effect, residual,
      ebit_margin_pct_chg   (percentage-point change in margin)
    """
    results = []

    for (operator, segment), grp in df.groupby(["operator", "segment"], observed=True):
        grp = grp.sort_values("quarter").reset_index(drop=True)

        for i in range(1, len(grp)):
            prev = grp.iloc[i - 1]
            curr = grp.iloc[i]

            delta_ridership = curr["ridership_m"] - prev["ridership_m"]
            delta_fare = curr["avg_fare_sgd"] - prev["avg_fare_sgd"]
            delta_cost_per_trip = curr["cost_per_trip_sgd"] - prev["cost_per_trip_sgd"]

            # Revenue bridge (S$M; ridership in M, fare in S$)
            fare_effect = delta_fare * curr["ridership_m"]                  # S$M
            vol_revenue_effect = prev["avg_fare_sgd"] * delta_ridership     # S$M

            # Cost bridge (S$M)
            cost_volume_effect = prev["cost_per_trip_sgd"] * delta_ridership   # S$M
            cost_efficiency_effect = delta_cost_per_trip * curr["ridership_m"] # S$M
            # note: positive cost_efficiency_effect means costs went UP per trip (bad)

            delta_revenue = curr["revenue_sgdm"] - prev["revenue_sgdm"]
            delta_opex = curr["opex_sgdm"] - prev["opex_sgdm"]
            delta_ebit = curr["ebit_sgdm"] - prev["ebit_sgdm"]

            # Net volume effect = volume revenue uplift minus cost of serving extra volume
            net_volume_effect = vol_revenue_effect - cost_volume_effect

            # Cost efficiency contribution to EBIT: negative of cost_efficiency_effect
            # (rising cost per trip hurts EBIT)
            cost_efficiency_ebit = -cost_efficiency_effect

            explained = fare_effect + net_volume_effect + cost_efficiency_ebit
            residual = delta_ebit - explained

            results.append(
                {
                    "operator": operator,
                    "segment": segment,
                    "quarter": str(curr["quarter"]),
                    "prev_quarter": str(prev["quarter"]),
                    # Actuals
                    "revenue_sgdm": curr["revenue_sgdm"],
                    "opex_sgdm": curr["opex_sgdm"],
                    "ebit_sgdm": curr["ebit_sgdm"],
                    "ebit_margin_pct": curr["ebit_margin_pct"],
                    "ridership_m": curr["ridership_m"],
                    "avg_fare_sgd": curr["avg_fare_sgd"],
                    # Changes
                    "delta_revenue": round(delta_revenue, 3),
                    "delta_opex": round(delta_opex, 3),
                    "delta_ebit": round(delta_ebit, 3),
                    "ebit_margin_pct_chg": round(
                        curr["ebit_margin_pct"] - prev["ebit_margin_pct"], 3
                    ),
                    # Driver bridge
                    "fare_effect": round(fare_effect, 3),
                    "vol_revenue_effect": round(vol_revenue_effect, 3),
                    "cost_volume_effect": round(cost_volume_effect, 3),
                    "net_volume_effect": round(net_volume_effect, 3),
                    "cost_efficiency_effect": round(cost_efficiency_ebit, 3),
                    "residual": round(residual, 3),
                }
            )

    return pd.DataFrame(results)


def dominant_driver(row: pd.Series) -> str:
    """
    Label the dominant EBIT driver for a single bridge row.

    Returns one of: 'Fare', 'Volume', 'Cost Efficiency', 'Mixed', 'Residual'
    """
    drivers = {
        "Fare": abs(row["fare_effect"]),
        "Volume": abs(row["net_volume_effect"]),
        "Cost Efficiency": abs(row["cost_efficiency_effect"]),
    }
    total = sum(drivers.values())
    if total < 1e-9:
        return "Residual"
    shares = {k: v / total for k, v in drivers.items()}
    top_key = max(shares, key=shares.__getitem__)
    if shares[top_key] >= 0.50:
        return top_key
    return "Mixed"


def add_dominant_driver(df: pd.DataFrame) -> pd.DataFrame:
    """Append dominant_driver column to decomposition output."""
    df = df.copy()
    df["dominant_driver"] = df.apply(dominant_driver, axis=1)
    return df


def driver_share_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute percentage share of each driver in explaining EBIT change.
    Only uses rows where |delta_ebit| > 0.
    """
    sub = df[df["delta_ebit"].abs() > 0.001].copy()
    total = sub["delta_ebit"].abs()
    sub["share_fare_pct"] = (sub["fare_effect"] / sub["delta_ebit"] * 100).round(1)
    sub["share_volume_pct"] = (sub["net_volume_effect"] / sub["delta_ebit"] * 100).round(1)
    sub["share_cost_pct"] = (sub["cost_efficiency_effect"] / sub["delta_ebit"] * 100).round(1)
    return sub
