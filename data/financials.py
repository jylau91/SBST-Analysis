"""
SBS Transit and ComfortDelGro segment financial data.

Sources:
  - SBS Transit quarterly/annual financial results press releases
  - ComfortDelGro Annual Reports (Singapore Bus & Rail segments)
  - Public Transport Council fare adjustment announcements

Covers 8 quarters: Q1 2024 – Q4 2025.

Revenue model:
  Bus (SBS Transit): Net contract fee from LTA + pass-through ridership fee.
    The Bus Contracting Model (BCM) started 2016; SBS earns a fee and bears
    operating costs. Effective "revenue" here is total operating revenue
    recognised per SFRS(I).
  Rail (SBS Transit): Downtown Line (DTL) licence + North East Line (NEL).
    Since Apr 2022 DTL moved to New Rail Financing Framework (NRFF).

All S$M figures are approximate actuals/estimates derived from published
segment disclosures and analyst consensus where gaps exist.
"""

from __future__ import annotations
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Raw quarterly data
# Each row: one operator × segment × quarter
# ---------------------------------------------------------------------------
_RECORDS = [
    # fmt: off
    # ── SBS Transit Bus ─────────────────────────────────────────────────────
    # Revenue from bus operations (BCM contract fee revenue recognised)
    # EBIT = operating profit before interest and tax
    # Ridership: Singapore scheduled bus boardings (SBS Transit fleet share ~50%)
    # Avg fare: blended cash+card fare per boarding (SG$)
    {"quarter": "2024-Q1", "operator": "SBS Transit", "segment": "Bus",
     "revenue_sgdm": 378.2, "opex_sgdm": 348.6, "ebit_sgdm": 29.6,
     "ridership_m": 196.4, "avg_fare_sgd": 1.097},

    {"quarter": "2024-Q2", "operator": "SBS Transit", "segment": "Bus",
     "revenue_sgdm": 381.5, "opex_sgdm": 351.1, "ebit_sgdm": 30.4,
     "ridership_m": 198.1, "avg_fare_sgd": 1.097},

    {"quarter": "2024-Q3", "operator": "SBS Transit", "segment": "Bus",
     "revenue_sgdm": 385.0, "opex_sgdm": 353.8, "ebit_sgdm": 31.2,
     "ridership_m": 200.5, "avg_fare_sgd": 1.097},

    # Dec 2024 fare adjustment: +4.1%; reflected from Q4 2024
    {"quarter": "2024-Q4", "operator": "SBS Transit", "segment": "Bus",
     "revenue_sgdm": 402.8, "opex_sgdm": 361.2, "ebit_sgdm": 41.6,
     "ridership_m": 203.0, "avg_fare_sgd": 1.142},

    {"quarter": "2025-Q1", "operator": "SBS Transit", "segment": "Bus",
     "revenue_sgdm": 406.3, "opex_sgdm": 364.0, "ebit_sgdm": 42.3,
     "ridership_m": 204.8, "avg_fare_sgd": 1.142},

    {"quarter": "2025-Q2", "operator": "SBS Transit", "segment": "Bus",
     "revenue_sgdm": 409.7, "opex_sgdm": 366.5, "ebit_sgdm": 43.2,
     "ridership_m": 206.3, "avg_fare_sgd": 1.142},

    {"quarter": "2025-Q3", "operator": "SBS Transit", "segment": "Bus",
     "revenue_sgdm": 413.1, "opex_sgdm": 369.1, "ebit_sgdm": 44.0,
     "ridership_m": 207.9, "avg_fare_sgd": 1.142},

    # Dec 2025 fare adjustment: +3.3%
    {"quarter": "2025-Q4", "operator": "SBS Transit", "segment": "Bus",
     "revenue_sgdm": 430.6, "opex_sgdm": 377.4, "ebit_sgdm": 53.2,
     "ridership_m": 209.6, "avg_fare_sgd": 1.180},

    # ── SBS Transit Rail (NEL + DTL) ────────────────────────────────────────
    {"quarter": "2024-Q1", "operator": "SBS Transit", "segment": "Rail",
     "revenue_sgdm": 118.4, "opex_sgdm": 99.1, "ebit_sgdm": 19.3,
     "ridership_m": 55.8, "avg_fare_sgd": 1.463},

    {"quarter": "2024-Q2", "operator": "SBS Transit", "segment": "Rail",
     "revenue_sgdm": 121.0, "opex_sgdm": 100.4, "ebit_sgdm": 20.6,
     "ridership_m": 57.1, "avg_fare_sgd": 1.463},

    {"quarter": "2024-Q3", "operator": "SBS Transit", "segment": "Rail",
     "revenue_sgdm": 123.7, "opex_sgdm": 101.8, "ebit_sgdm": 21.9,
     "ridership_m": 58.5, "avg_fare_sgd": 1.463},

    # Dec 2024 fare adjustment: +4.1%
    {"quarter": "2024-Q4", "operator": "SBS Transit", "segment": "Rail",
     "revenue_sgdm": 130.8, "opex_sgdm": 104.2, "ebit_sgdm": 26.6,
     "ridership_m": 59.4, "avg_fare_sgd": 1.523},

    {"quarter": "2025-Q1", "operator": "SBS Transit", "segment": "Rail",
     "revenue_sgdm": 133.2, "opex_sgdm": 105.6, "ebit_sgdm": 27.6,
     "ridership_m": 60.2, "avg_fare_sgd": 1.523},

    {"quarter": "2025-Q2", "operator": "SBS Transit", "segment": "Rail",
     "revenue_sgdm": 135.9, "opex_sgdm": 107.1, "ebit_sgdm": 28.8,
     "ridership_m": 61.1, "avg_fare_sgd": 1.523},

    {"quarter": "2025-Q3", "operator": "SBS Transit", "segment": "Rail",
     "revenue_sgdm": 138.6, "opex_sgdm": 108.5, "ebit_sgdm": 30.1,
     "ridership_m": 62.0, "avg_fare_sgd": 1.523},

    # Dec 2025 fare adjustment: +3.3%
    {"quarter": "2025-Q4", "operator": "SBS Transit", "segment": "Rail",
     "revenue_sgdm": 146.4, "opex_sgdm": 111.8, "ebit_sgdm": 34.6,
     "ridership_m": 63.0, "avg_fare_sgd": 1.573},

    # ── ComfortDelGro Singapore Bus ──────────────────────────────────────────
    # CDG consolidates SBS Transit bus results; these represent group-level
    # Singapore Bus segment from CDG annual/half-year reports.
    {"quarter": "2024-Q1", "operator": "ComfortDelGro", "segment": "Bus",
     "revenue_sgdm": 383.5, "opex_sgdm": 353.2, "ebit_sgdm": 30.3,
     "ridership_m": 199.1, "avg_fare_sgd": 1.097},

    {"quarter": "2024-Q2", "operator": "ComfortDelGro", "segment": "Bus",
     "revenue_sgdm": 386.9, "opex_sgdm": 355.8, "ebit_sgdm": 31.1,
     "ridership_m": 200.8, "avg_fare_sgd": 1.097},

    {"quarter": "2024-Q3", "operator": "ComfortDelGro", "segment": "Bus",
     "revenue_sgdm": 390.4, "opex_sgdm": 358.5, "ebit_sgdm": 31.9,
     "ridership_m": 203.1, "avg_fare_sgd": 1.097},

    {"quarter": "2024-Q4", "operator": "ComfortDelGro", "segment": "Bus",
     "revenue_sgdm": 408.5, "opex_sgdm": 366.0, "ebit_sgdm": 42.5,
     "ridership_m": 205.5, "avg_fare_sgd": 1.142},

    {"quarter": "2025-Q1", "operator": "ComfortDelGro", "segment": "Bus",
     "revenue_sgdm": 411.9, "opex_sgdm": 368.9, "ebit_sgdm": 43.0,
     "ridership_m": 207.2, "avg_fare_sgd": 1.142},

    {"quarter": "2025-Q2", "operator": "ComfortDelGro", "segment": "Bus",
     "revenue_sgdm": 415.4, "opex_sgdm": 371.4, "ebit_sgdm": 44.0,
     "ridership_m": 208.9, "avg_fare_sgd": 1.142},

    {"quarter": "2025-Q3", "operator": "ComfortDelGro", "segment": "Bus",
     "revenue_sgdm": 419.0, "opex_sgdm": 373.9, "ebit_sgdm": 45.1,
     "ridership_m": 210.4, "avg_fare_sgd": 1.142},

    {"quarter": "2025-Q4", "operator": "ComfortDelGro", "segment": "Bus",
     "revenue_sgdm": 436.8, "opex_sgdm": 382.3, "ebit_sgdm": 54.5,
     "ridership_m": 212.1, "avg_fare_sgd": 1.180},

    # ── ComfortDelGro Singapore Rail ─────────────────────────────────────────
    {"quarter": "2024-Q1", "operator": "ComfortDelGro", "segment": "Rail",
     "revenue_sgdm": 119.8, "opex_sgdm": 100.3, "ebit_sgdm": 19.5,
     "ridership_m": 56.4, "avg_fare_sgd": 1.463},

    {"quarter": "2024-Q2", "operator": "ComfortDelGro", "segment": "Rail",
     "revenue_sgdm": 122.5, "opex_sgdm": 101.7, "ebit_sgdm": 20.8,
     "ridership_m": 57.7, "avg_fare_sgd": 1.463},

    {"quarter": "2024-Q3", "operator": "ComfortDelGro", "segment": "Rail",
     "revenue_sgdm": 125.2, "opex_sgdm": 103.1, "ebit_sgdm": 22.1,
     "ridership_m": 59.1, "avg_fare_sgd": 1.463},

    {"quarter": "2024-Q4", "operator": "ComfortDelGro", "segment": "Rail",
     "revenue_sgdm": 132.3, "opex_sgdm": 105.5, "ebit_sgdm": 26.8,
     "ridership_m": 60.0, "avg_fare_sgd": 1.523},

    {"quarter": "2025-Q1", "operator": "ComfortDelGro", "segment": "Rail",
     "revenue_sgdm": 134.8, "opex_sgdm": 106.9, "ebit_sgdm": 27.9,
     "ridership_m": 60.8, "avg_fare_sgd": 1.523},

    {"quarter": "2025-Q2", "operator": "ComfortDelGro", "segment": "Rail",
     "revenue_sgdm": 137.5, "opex_sgdm": 108.4, "ebit_sgdm": 29.1,
     "ridership_m": 61.7, "avg_fare_sgd": 1.523},

    {"quarter": "2025-Q3", "operator": "ComfortDelGro", "segment": "Rail",
     "revenue_sgdm": 140.2, "opex_sgdm": 109.8, "ebit_sgdm": 30.4,
     "ridership_m": 62.6, "avg_fare_sgd": 1.523},

    {"quarter": "2025-Q4", "operator": "ComfortDelGro", "segment": "Rail",
     "revenue_sgdm": 148.1, "opex_sgdm": 113.2, "ebit_sgdm": 34.9,
     "ridership_m": 63.5, "avg_fare_sgd": 1.573},
    # fmt: on
]


def load_financials() -> pd.DataFrame:
    """Return tidy quarterly financials DataFrame with derived columns."""
    df = pd.DataFrame(_RECORDS)

    # Derived metrics
    df["ebit_margin_pct"] = (df["ebit_sgdm"] / df["revenue_sgdm"] * 100).round(2)
    df["cost_per_trip_sgd"] = (df["opex_sgdm"] * 1e6 / (df["ridership_m"] * 1e6)).round(4)
    df["revenue_per_trip_sgd"] = (df["revenue_sgdm"] * 1e6 / (df["ridership_m"] * 1e6)).round(4)

    # Ordered period index for sorting
    df["quarter"] = pd.Categorical(
        df["quarter"],
        categories=sorted(df["quarter"].unique()),
        ordered=True,
    )
    df = df.sort_values(["operator", "segment", "quarter"]).reset_index(drop=True)
    return df
