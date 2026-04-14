"""
Bus & Rail Margin Driver Dashboard
===================================
Streamlit app showing whether SBS Transit / ComfortDelGro margin changes
over the last 8 quarters were volume-, fare-, or cost-led.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import io
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from data.financials import load_financials
from data.fare_events import load_fare_events
from data.lta_datamall import load_service_quality, DataMallClient
from analysis.margin_decomp import compute_decomposition, add_dominant_driver, driver_share_table
from charts.export import (
    build_pptx,
    fig_to_png_bytes,
    ppt_layout,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SG Bus & Rail Margin Driver Dashboard",
    page_icon=":bus:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
COLOURS = {
    "Fare": "#1f77b4",
    "Volume": "#2ca02c",
    "Cost Efficiency": "#d62728",
    "Residual": "#9467bd",
    "Mixed": "#8c564b",
    "Bus": "#ff7f0e",
    "Rail": "#1f77b4",
    "SBS Transit": "#2ca02c",
    "ComfortDelGro": "#9467bd",
}

DRIVER_ORDER = ["Fare", "Volume", "Cost Efficiency", "Residual"]

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_data():
    financials = load_financials()
    fare_events = load_fare_events()
    service_quality = load_service_quality()

    # Try live DataMall pull; falls back gracefully
    api_key = st.session_state.get("datamall_key", os.getenv("LTA_DATAMALL_KEY", ""))
    client = DataMallClient(api_key=api_key)
    live_bus = client.fetch_bus_ridership() if client.available() else pd.DataFrame()
    live_rail = client.fetch_mrt_ridership() if client.available() else pd.DataFrame()

    decomp = compute_decomposition(financials)
    decomp = add_dominant_driver(decomp)
    decomp = driver_share_table(decomp)

    return financials, fare_events, service_quality, decomp, client.available()


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def margin_trend_chart(
    financials: pd.DataFrame,
    operator: str,
    fare_events: pd.DataFrame,
) -> go.Figure:
    sub = financials[financials["operator"] == operator].copy()
    fig = go.Figure()
    for segment, color in [("Bus", COLOURS["Bus"]), ("Rail", COLOURS["Rail"])]:
        s = sub[sub["segment"] == segment]
        fig.add_trace(
            go.Scatter(
                x=s["quarter"].astype(str),
                y=s["ebit_margin_pct"],
                mode="lines+markers",
                name=segment,
                line=dict(color=color, width=2.5),
                marker=dict(size=7),
            )
        )

    # Mark fare adjustment quarters (use add_shape for categorical axes)
    quarters = sorted(sub["quarter"].astype(str).unique())
    for _, ev in fare_events.iterrows():
        q = ev["effective_quarter"]
        if q in quarters:
            fig.add_shape(
                type="line",
                xref="x",
                yref="paper",
                x0=q, x1=q,
                y0=0, y1=1,
                line=dict(color="gray", width=1.5, dash="dot"),
            )
            fig.add_annotation(
                x=q,
                yref="paper",
                y=1.05,
                text=f'+{ev["headline_pct"]}% fare',
                showarrow=False,
                font=dict(size=9, color="gray"),
                xanchor="left",
            )

    fig.update_layout(
        title=f"{operator} – EBIT Margin by Segment (8 Quarters)",
        xaxis_title="Quarter",
        yaxis_title="EBIT Margin (%)",
        yaxis=dict(ticksuffix="%"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        paper_bgcolor="white",
        width=SCREEN_WIDTH,
        height=SCREEN_HEIGHT,
        margin=dict(l=60, r=40, t=70, b=50),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#e5e5e5")
    return fig


def waterfall_chart(
    decomp: pd.DataFrame,
    operator: str,
    segment: str,
) -> go.Figure:
    sub = decomp[(decomp["operator"] == operator) & (decomp["segment"] == segment)].copy()
    sub = sub.sort_values("quarter")

    quarters = sub["quarter"].tolist()
    fare_vals = sub["fare_effect"].tolist()
    vol_vals = sub["net_volume_effect"].tolist()
    cost_vals = sub["cost_efficiency_effect"].tolist()
    residual_vals = sub["residual"].tolist()

    fig = go.Figure()
    for label, vals, color in [
        ("Fare Effect", fare_vals, COLOURS["Fare"]),
        ("Net Volume Effect", vol_vals, COLOURS["Volume"]),
        ("Cost Efficiency", cost_vals, COLOURS["Cost Efficiency"]),
        ("Residual", residual_vals, COLOURS["Residual"]),
    ]:
        fig.add_trace(
            go.Bar(
                name=label,
                x=quarters,
                y=vals,
                marker_color=color,
                text=[f"{v:+.1f}" for v in vals],
                textposition="outside",
                textfont=dict(size=10),
            )
        )

    fig.update_layout(
        title=f"{operator} {segment} – QoQ EBIT Bridge (S$M)",
        xaxis_title="Quarter",
        yaxis_title="ΔEBIT Contribution (S$M)",
        barmode="relative",
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        width=SCREEN_WIDTH,
        height=SCREEN_HEIGHT,
        margin=dict(l=60, r=40, t=70, b=50),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#e5e5e5")
    return fig


def ridership_trend_chart(
    financials: pd.DataFrame,
    operator: str,
) -> go.Figure:
    sub = financials[financials["operator"] == operator].copy()
    fig = go.Figure()
    for segment, color in [("Bus", COLOURS["Bus"]), ("Rail", COLOURS["Rail"])]:
        s = sub[sub["segment"] == segment]
        fig.add_trace(
            go.Scatter(
                x=s["quarter"].astype(str),
                y=s["ridership_m"],
                mode="lines+markers",
                name=f"{segment} Ridership",
                line=dict(color=color, width=2.5),
                marker=dict(size=7),
            )
        )
    fig.update_layout(
        title=f"{operator} – Ridership Trend (M boardings/quarter)",
        xaxis_title="Quarter",
        yaxis_title="Boardings (M)",
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        width=SCREEN_WIDTH,
        height=SCREEN_HEIGHT,
        margin=dict(l=60, r=40, t=70, b=50),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#e5e5e5")
    return fig


def fare_cost_chart(
    financials: pd.DataFrame,
    operator: str,
    segment: str,
    fare_events: pd.DataFrame,
) -> go.Figure:
    sub = financials[
        (financials["operator"] == operator) & (financials["segment"] == segment)
    ].copy()
    quarters = sub["quarter"].astype(str).tolist()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=quarters,
            y=sub["avg_fare_sgd"],
            mode="lines+markers",
            name="Avg Fare (S$/trip)",
            line=dict(color=COLOURS["Fare"], width=2.5),
            marker=dict(size=7),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=quarters,
            y=sub["cost_per_trip_sgd"],
            mode="lines+markers",
            name="Cost/trip (S$)",
            line=dict(color=COLOURS["Cost Efficiency"], width=2.5, dash="dash"),
            marker=dict(size=7),
        )
    )
    # Shade fare adjustment quarters
    for _, ev in fare_events.iterrows():
        q = ev["effective_quarter"]
        if q in quarters:
            fig.add_vrect(
                x0=quarters.index(q) - 0.5,
                x1=quarters.index(q) + 0.5,
                fillcolor="lightblue",
                opacity=0.2,
                layer="below",
                line_width=0,
            )

    fig.update_layout(
        title=f"{operator} {segment} – Average Fare vs Cost per Trip (S$)",
        xaxis_title="Quarter",
        yaxis_title="S$ per trip",
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        width=SCREEN_WIDTH,
        height=SCREEN_HEIGHT,
        margin=dict(l=60, r=40, t=70, b=50),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#e5e5e5")
    return fig


def driver_heatmap(decomp: pd.DataFrame, operator: str) -> go.Figure:
    sub = decomp[decomp["operator"] == operator].copy()
    sub["quarter_str"] = sub["quarter"].astype(str)

    pivot_fare = sub.pivot(index="segment", columns="quarter_str", values="share_fare_pct")
    pivot_vol = sub.pivot(index="segment", columns="quarter_str", values="share_volume_pct")
    pivot_cost = sub.pivot(index="segment", columns="quarter_str", values="share_cost_pct")

    # Stack the three driver rows per segment
    rows, row_labels, col_labels = [], [], None
    for seg in ["Bus", "Rail"]:
        for driver, pivot in [
            ("Fare %", pivot_fare),
            ("Volume %", pivot_vol),
            ("Cost Eff. %", pivot_cost),
        ]:
            row_labels.append(f"{seg} – {driver}")
            try:
                rows.append(pivot.loc[seg].tolist())
                if col_labels is None:
                    col_labels = pivot.columns.tolist()
            except KeyError:
                rows.append([None] * (len(col_labels) if col_labels else 7))

    z_vals = rows
    text_vals = [
        [f"{v:.0f}%" if v is not None else "" for v in row] for row in z_vals
    ]

    fig = go.Figure(
        go.Heatmap(
            z=z_vals,
            x=col_labels,
            y=row_labels,
            text=text_vals,
            texttemplate="%{text}",
            colorscale="RdYlGn",
            zmid=50,
            zmin=0,
            zmax=100,
            showscale=True,
            colorbar=dict(title="Share %"),
        )
    )
    fig.update_layout(
        title=f"{operator} – Driver Share Heat Map (% of ΔEBIT explained)",
        xaxis_title="Quarter",
        yaxis_title="",
        plot_bgcolor="white",
        paper_bgcolor="white",
        width=SCREEN_WIDTH,
        height=SCREEN_HEIGHT,
        margin=dict(l=160, r=40, t=70, b=50),
    )
    return fig


def revenue_cost_index_chart(
    financials: pd.DataFrame,
    operator: str,
    segment: str,
) -> go.Figure:
    sub = financials[
        (financials["operator"] == operator) & (financials["segment"] == segment)
    ].sort_values("quarter").copy()

    base_rev = sub.iloc[0]["revenue_sgdm"]
    base_cost = sub.iloc[0]["opex_sgdm"]
    base_rid = sub.iloc[0]["ridership_m"]

    quarters = sub["quarter"].astype(str).tolist()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=quarters,
            y=(sub["revenue_sgdm"] / base_rev * 100).round(1),
            mode="lines+markers",
            name="Revenue Index",
            line=dict(color=COLOURS["Fare"], width=2.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=quarters,
            y=(sub["opex_sgdm"] / base_cost * 100).round(1),
            mode="lines+markers",
            name="OpEx Index",
            line=dict(color=COLOURS["Cost Efficiency"], width=2.5, dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=quarters,
            y=(sub["ridership_m"] / base_rid * 100).round(1),
            mode="lines+markers",
            name="Ridership Index",
            line=dict(color=COLOURS["Volume"], width=2.5, dash="dot"),
        )
    )
    fig.add_hline(y=100, line_dash="solid", line_color="black", line_width=1)
    fig.update_layout(
        title=f"{operator} {segment} – Revenue / OpEx / Ridership (indexed, base = 2024-Q1)",
        xaxis_title="Quarter",
        yaxis_title="Index (base = 100)",
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        width=SCREEN_WIDTH,
        height=SCREEN_HEIGHT,
        margin=dict(l=60, r=40, t=70, b=50),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#e5e5e5")
    return fig


# ---------------------------------------------------------------------------
# Notes / narrative generation
# ---------------------------------------------------------------------------

def generate_notes(
    financials: pd.DataFrame,
    decomp: pd.DataFrame,
    fare_events: pd.DataFrame,
    operator: str,
    segment: str,
) -> str:
    sub_f = financials[
        (financials["operator"] == operator) & (financials["segment"] == segment)
    ].sort_values("quarter")
    sub_d = decomp[
        (decomp["operator"] == operator) & (decomp["segment"] == segment)
    ].sort_values("quarter")

    if sub_f.empty or sub_d.empty:
        return "No data available for this selection."

    first = sub_f.iloc[0]
    last = sub_f.iloc[-1]

    margin_change = last["ebit_margin_pct"] - first["ebit_margin_pct"]
    rev_growth = (last["revenue_sgdm"] / first["revenue_sgdm"] - 1) * 100
    rid_growth = (last["ridership_m"] / first["ridership_m"] - 1) * 100

    total_fare_effect = sub_d["fare_effect"].sum()
    total_vol_effect = sub_d["net_volume_effect"].sum()
    total_cost_effect = sub_d["cost_efficiency_effect"].sum()
    total_delta_ebit = sub_d["delta_ebit"].sum()

    total_driver = abs(total_fare_effect) + abs(total_vol_effect) + abs(total_cost_effect)
    fare_share = total_fare_effect / total_driver * 100 if total_driver else 0
    vol_share = total_vol_effect / total_driver * 100 if total_driver else 0
    cost_share = total_cost_effect / total_driver * 100 if total_driver else 0

    dominant = max(
        [("Fare", fare_share), ("Volume", vol_share), ("Cost Efficiency", cost_share)],
        key=lambda x: abs(x[1]),
    )[0]

    # Find fare event quarters in scope
    fare_qs = fare_events[
        fare_events["effective_quarter"].isin(sub_d["quarter"].tolist())
    ]

    fare_lines = "\n".join(
        [
            f"  • {row['effective_quarter']}: +{row['headline_pct']}% fare adjustment "
            f"({row['description'][:80]}...)"
            for _, row in fare_qs.iterrows()
        ]
    )

    lines = [
        f"=== {operator} | {segment} | 2024-Q1 → 2025-Q4 ===",
        "",
        "SUMMARY",
        f"  Revenue grew {rev_growth:+.1f}% ({first['revenue_sgdm']:.1f} → {last['revenue_sgdm']:.1f} S$M).",
        f"  Ridership up {rid_growth:+.1f}% ({first['ridership_m']:.1f}M → {last['ridership_m']:.1f}M boardings/qtr).",
        f"  EBIT margin: {first['ebit_margin_pct']:.1f}% → {last['ebit_margin_pct']:.1f}% ({margin_change:+.1f} pp).",
        f"  Cumulative ΔEBIT over 7 QoQ periods: S${total_delta_ebit:+.1f}M.",
        "",
        "DRIVER DECOMPOSITION (cumulative, S$M)",
        f"  Fare effect:           S${total_fare_effect:+.1f}M  ({fare_share:+.0f}% of movement)",
        f"  Net volume effect:     S${total_vol_effect:+.1f}M  ({vol_share:+.0f}% of movement)",
        f"  Cost efficiency effect: S${total_cost_effect:+.1f}M  ({cost_share:+.0f}% of movement)",
        "",
        f"  DOMINANT DRIVER: {dominant}",
        "",
        "FARE ADJUSTMENT EVENTS IN PERIOD",
        fare_lines if fare_lines else "  None in this selection.",
        "",
        "INTERPRETATION",
    ]

    # Contextual interpretation
    if dominant == "Fare":
        lines.append(
            f"  Margin improvement was primarily fare-driven. PTC fare adjustments accounted "
            f"for the majority ({abs(fare_share):.0f}%) of cumulative EBIT gains. "
            f"Ridership and cost trends were secondary factors."
        )
    elif dominant == "Volume":
        lines.append(
            f"  Margin improvement was primarily volume-driven. Passenger growth of "
            f"{rid_growth:.1f}% contributed the largest share ({abs(vol_share):.0f}%) of gains, "
            f"with fare and cost moves playing supporting roles."
        )
    elif dominant == "Cost Efficiency":
        direction = "improving" if total_cost_effect > 0 else "pressuring"
        lines.append(
            f"  Cost efficiency was the dominant factor, {direction} margins. "
            f"Changes in operating cost per trip drove {abs(cost_share):.0f}% of cumulative EBIT movement."
        )
    else:
        lines.append(
            "  No single driver dominated. Margin changes reflect a combination of "
            "fare adjustments, ridership shifts, and operating cost dynamics."
        )

    lines += [
        "",
        "DATA SOURCES",
        "  • SBS Transit / ComfortDelGro quarterly financial results",
        "  • Public Transport Council fare adjustment press releases",
        "  • LTA Annual Reports / DataMall service performance data",
        "  • Bus Contracting Model (BCM) and New Rail Financing Framework (NRFF) disclosures",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar():
    st.sidebar.title("Controls")

    operator = st.sidebar.selectbox(
        "Operator", ["SBS Transit", "ComfortDelGro"], index=0
    )
    segment = st.sidebar.selectbox("Segment", ["Bus", "Rail"], index=0)

    st.sidebar.markdown("---")
    st.sidebar.subheader("LTA DataMall (optional)")
    api_key_input = st.sidebar.text_input(
        "API Key",
        value=os.getenv("LTA_DATAMALL_KEY", ""),
        type="password",
        help="Account key from datamall.lta.gov.sg — leave blank to use embedded data.",
    )
    if api_key_input:
        st.session_state["datamall_key"] = api_key_input

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Data covers Q1 2024 – Q4 2025. "
        "Figures are derived from published segment disclosures and analyst consensus "
        "where gaps exist. Not investment advice."
    )
    return operator, segment


# ---------------------------------------------------------------------------
# Export panel
# ---------------------------------------------------------------------------

def render_export_panel(
    figures: list[dict],
    financials: pd.DataFrame,
    decomp: pd.DataFrame,
):
    with st.expander("Export charts", expanded=False):
        st.markdown(
            "Charts are sized for **PowerPoint (10 × 5.6 in, 144 dpi)**. "
            "Download as PNG (individual) or PPTX (full deck)."
        )

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Individual PNGs**")
            for item in figures:
                fig_ppt = go.Figure(item["fig"])
                fig_ppt.update_layout(**ppt_layout(item["title"]))
                png_bytes = fig_to_png_bytes(fig_ppt, ppt=True)
                if png_bytes:
                    fname = item["title"].replace(" ", "_").replace("/", "-")[:50] + ".png"
                    st.download_button(
                        label=f"Download: {item['title'][:45]}",
                        data=png_bytes,
                        file_name=fname,
                        mime="image/png",
                        key=f"png_{fname}",
                    )
                else:
                    st.info(
                        "PNG export requires kaleido. "
                        "Install with: `pip install kaleido`"
                    )
                    break

        with col2:
            st.markdown("**Full PPTX deck**")
            try:
                pptx_bytes = build_pptx(figures)
                st.download_button(
                    label="Download PPTX deck",
                    data=pptx_bytes,
                    file_name="SG_BusRail_Margin_Dashboard.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            except RuntimeError as e:
                st.warning(str(e))

        st.markdown("**Raw data (Excel)**")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            financials.to_excel(writer, sheet_name="Financials", index=False)
            decomp.to_excel(writer, sheet_name="Decomposition", index=False)
        st.download_button(
            label="Download Excel workbook",
            data=buf.getvalue(),
            file_name="SG_BusRail_Data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

def main():
    operator, segment = render_sidebar()

    st.title("Singapore Bus & Rail – Margin Driver Dashboard")
    st.caption(
        "8-quarter view (2024-Q1 – 2025-Q4) | SBS Transit & ComfortDelGro | "
        "Decomposing EBIT margin changes into volume, fare and cost drivers"
    )

    # Load data
    with st.spinner("Loading data..."):
        financials, fare_events, service_quality, decomp, live_api = get_data()

    if live_api:
        st.sidebar.success("LTA DataMall connected")
    else:
        st.sidebar.info("Using embedded data (no API key)")

    # ---------- Row 0: KPI scorecards ----------
    sub_f = financials[
        (financials["operator"] == operator) & (financials["segment"] == segment)
    ].sort_values("quarter")
    sub_d = decomp[
        (decomp["operator"] == operator) & (decomp["segment"] == segment)
    ].sort_values("quarter")

    if not sub_f.empty:
        first, last = sub_f.iloc[0], sub_f.iloc[-1]
        kpis = st.columns(5)
        kpis[0].metric(
            "EBIT Margin (latest)",
            f"{last['ebit_margin_pct']:.1f}%",
            delta=f"{last['ebit_margin_pct'] - first['ebit_margin_pct']:+.1f} pp vs base",
        )
        kpis[1].metric(
            "Revenue (latest qtr)",
            f"S${last['revenue_sgdm']:.1f}M",
            delta=f"{(last['revenue_sgdm']/first['revenue_sgdm']-1)*100:+.1f}%",
        )
        kpis[2].metric(
            "Ridership (latest qtr)",
            f"{last['ridership_m']:.1f}M",
            delta=f"{(last['ridership_m']/first['ridership_m']-1)*100:+.1f}%",
        )
        kpis[3].metric(
            "Avg Fare (latest)",
            f"S${last['avg_fare_sgd']:.3f}",
            delta=f"{(last['avg_fare_sgd']/first['avg_fare_sgd']-1)*100:+.1f}%",
        )
        kpis[4].metric(
            "Cost/Trip (latest)",
            f"S${last['cost_per_trip_sgd']:.3f}",
            delta=f"{(last['cost_per_trip_sgd']/first['cost_per_trip_sgd']-1)*100:+.1f}%",
            delta_color="inverse",
        )

    st.markdown("---")

    # ---------- Tab layout ----------
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Margin Trend",
        "QoQ Bridge",
        "Fare vs Cost",
        "Indexed Growth",
        "Driver Heatmap",
    ])

    figures_for_export: list[dict] = []

    with tab1:
        st.subheader(f"{operator} – EBIT Margin Trend")
        fig1 = margin_trend_chart(financials, operator, fare_events)
        st.plotly_chart(fig1, use_container_width=True)
        notes1 = generate_notes(financials, decomp, fare_events, operator, "Bus")
        notes1_rail = generate_notes(financials, decomp, fare_events, operator, "Rail")
        figures_for_export.append({
            "fig": fig1,
            "title": f"{operator} EBIT Margin Trend",
            "notes": notes1 + "\n\n" + notes1_rail,
        })

    with tab2:
        st.subheader(f"{operator} {segment} – Quarter-on-Quarter EBIT Bridge")
        fig2 = waterfall_chart(decomp, operator, segment)
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            "**Blue = Fare effect** (PTC fare change × current ridership) | "
            "**Green = Net volume effect** (ridership growth net of variable costs) | "
            "**Red = Cost efficiency** (cost/trip change × current ridership; negative = costs rising)"
        )
        figures_for_export.append({
            "fig": fig2,
            "title": f"{operator} {segment} QoQ EBIT Bridge",
            "notes": generate_notes(financials, decomp, fare_events, operator, segment),
        })

    with tab3:
        st.subheader(f"{operator} {segment} – Average Fare vs Cost per Trip")
        fig3 = fare_cost_chart(financials, operator, segment, fare_events)
        st.plotly_chart(fig3, use_container_width=True)
        # Fare events table
        rel_events = fare_events[
            fare_events["effective_quarter"].isin(
                decomp[decomp["operator"] == operator]["quarter"].tolist()
            )
        ][["effective_quarter", "headline_pct", "bus_fare_pct", "rail_fare_pct", "description"]]
        if not rel_events.empty:
            st.markdown("**PTC Fare Adjustment Events**")
            st.dataframe(rel_events, use_container_width=True, hide_index=True)
        figures_for_export.append({
            "fig": fig3,
            "title": f"{operator} {segment} Fare vs Cost per Trip",
            "notes": generate_notes(financials, decomp, fare_events, operator, segment),
        })

    with tab4:
        st.subheader(f"{operator} {segment} – Revenue / OpEx / Ridership (Indexed)")
        fig4 = revenue_cost_index_chart(financials, operator, segment)
        st.plotly_chart(fig4, use_container_width=True)
        st.caption("Base = 2024-Q1 = 100. Revenue growing faster than OpEx indicates margin expansion.")
        figures_for_export.append({
            "fig": fig4,
            "title": f"{operator} {segment} Indexed Growth",
            "notes": generate_notes(financials, decomp, fare_events, operator, segment),
        })

    with tab5:
        st.subheader(f"{operator} – Driver Share Heat Map")
        fig5 = driver_heatmap(decomp, operator)
        st.plotly_chart(fig5, use_container_width=True)
        st.caption(
            "Each cell shows the % of QoQ ΔEBIT explained by that driver. "
            "Green = high share; Red = low share. Values > 100% or negative "
            "indicate partially offsetting drivers."
        )
        figures_for_export.append({
            "fig": fig5,
            "title": f"{operator} Driver Share Heatmap",
            "notes": "",
        })

    # Also add ridership chart to export deck
    fig_rid = ridership_trend_chart(financials, operator)
    figures_for_export.append({
        "fig": fig_rid,
        "title": f"{operator} Ridership Trend",
        "notes": "",
    })

    st.markdown("---")

    # ---------- Notes panel ----------
    with st.expander("Driver Analysis Notes", expanded=True):
        notes_text = generate_notes(financials, decomp, fare_events, operator, segment)
        st.text(notes_text)
        st.download_button(
            "Download notes as .txt",
            data=notes_text.encode(),
            file_name=f"notes_{operator.replace(' ', '_')}_{segment}.txt",
            mime="text/plain",
        )

    # ---------- Export panel ----------
    render_export_panel(figures_for_export, financials, decomp)

    # ---------- Raw data ----------
    with st.expander("Raw data tables", expanded=False):
        t1, t2, t3 = st.tabs(["Financials", "Decomposition", "Service Quality"])
        with t1:
            st.dataframe(
                financials[financials["operator"] == operator].reset_index(drop=True),
                use_container_width=True,
            )
        with t2:
            cols_show = [
                "quarter", "segment", "ebit_sgdm", "ebit_margin_pct",
                "delta_ebit", "fare_effect", "net_volume_effect",
                "cost_efficiency_effect", "residual", "dominant_driver",
            ]
            st.dataframe(
                decomp[decomp["operator"] == operator][cols_show].reset_index(drop=True),
                use_container_width=True,
            )
        with t3:
            st.dataframe(
                service_quality[service_quality["operator"] == operator].reset_index(drop=True),
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
