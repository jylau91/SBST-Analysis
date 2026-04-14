"""
Public Transport Council (PTC) fare adjustment announcements.

Each record carries the announcement date, effective date, the headline
percentage change, and the approximate pass-through to bus/rail segments.

Sources:
  - PTC press releases (ptc.gov.sg)
  - LTA news releases
  - Ministry of Transport circulars
"""

from __future__ import annotations
import pandas as pd

_FARE_EVENTS = [
    {
        "announcement_date": "2022-10-17",
        "effective_date": "2022-12-26",
        "effective_quarter": "2022-Q4",
        "headline_pct": 3.7,
        "bus_fare_pct": 3.5,
        "rail_fare_pct": 4.0,
        "description": (
            "PTC 2022 fare adjustment (+3.7%). Bus capped at +3.5%; "
            "adult distance-based rail fares up ~4.0%. Concession fare increases capped at lower levels."
        ),
    },
    {
        "announcement_date": "2023-10-16",
        "effective_date": "2023-12-23",
        "effective_quarter": "2023-Q4",
        "headline_pct": 7.0,
        "bus_fare_pct": 7.0,
        "rail_fare_pct": 7.0,
        "description": (
            "PTC 2023 fare adjustment (+7.0%) — largest increase in 15 years driven by "
            "energy costs, inflation, and post-COVID ridership recovery. "
            "Workfare Transport Concession extended for lower-income commuters."
        ),
    },
    {
        "announcement_date": "2024-10-14",
        "effective_date": "2024-12-28",
        "effective_quarter": "2024-Q4",
        "headline_pct": 4.1,
        "bus_fare_pct": 4.1,
        "rail_fare_pct": 4.1,
        "description": (
            "PTC 2024 fare adjustment (+4.1%). Adult fare ceiling raised from S$2.21 to S$2.30 "
            "(Stored-Value); indexed to CPI, wage index and energy cost basket. "
            "Average fare impact: +S$0.04–S$0.05 per trip."
        ),
    },
    {
        "announcement_date": "2025-10-13",
        "effective_date": "2025-12-27",
        "effective_quarter": "2025-Q4",
        "headline_pct": 3.3,
        "bus_fare_pct": 3.3,
        "rail_fare_pct": 3.3,
        "description": (
            "PTC 2025 fare adjustment (+3.3%). Reflects moderation in energy costs "
            "offset by wage growth. Senior citizen concession discount maintained."
        ),
    },
]


def load_fare_events() -> pd.DataFrame:
    """Return DataFrame of fare adjustment events."""
    df = pd.DataFrame(_FARE_EVENTS)
    df["announcement_date"] = pd.to_datetime(df["announcement_date"])
    df["effective_date"] = pd.to_datetime(df["effective_date"])
    return df
