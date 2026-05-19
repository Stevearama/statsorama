"""Detail charts page — multi-series grid view."""

import streamlit as st
import pandas as pd

from eia_data import SERIES
from data_cache import get_series_cached, get_padd_cached
from chart_data import build_seasonality_data, build_timeline_data, build_padd_timeline
from ui import (
    render_header, render_chart_title,
    build_seasonality_chart, build_timeline_chart, build_padd_chart,
    render_data_table,
)

# ---------------------------------------------------------------------------
# Sidebar series options (ordered for display)
# ---------------------------------------------------------------------------

SERIES_OPTIONS = [
    ("U.S. Crude Stocks",     "stocks_us"),
    ("Cushing, OK Stocks",    "stocks_cushing"),
    ("PADD Breakdown",        "padd"),
    ("Gasoline Stocks",       "stocks_gasoline"),
    ("Distillate Stocks",     "stocks_distillate"),
    ("Jet Fuel Stocks",       "stocks_jet"),
    ("Propane Stocks",        "stocks_propane"),
    ("SPR Stocks",            "stocks_spr"),
    ("Crude Production",      "production"),
    ("Gasoline Production",   "prod_gasoline"),
    ("Distillate Production", "prod_distillate"),
    ("Crude Imports",         "imports"),
    ("Refinery Inputs",       "refinery_inputs"),
    ("Refinery Utilization",  "refinery_util"),
    ("WTI Spot Price",        "wti_spot"),
    ("Retail Gasoline Price", "gasoline_retail"),
    ("Retail Diesel Price",   "diesel_retail"),
]
LABEL_TO_KEY = {label: key for label, key in SERIES_OPTIONS}

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def _get_series(key: str, api_key: str) -> pd.DataFrame:
    try:
        return get_series_cached(key, api_key)
    except Exception:
        return pd.DataFrame(columns=["date", "value"])


@st.cache_data(ttl=3600)
def _get_padd(api_key: str) -> pd.DataFrame:
    try:
        return get_padd_cached(api_key)
    except Exception:
        return pd.DataFrame(columns=["date", "area", "value"])

# ---------------------------------------------------------------------------
# Single chart renderer
# ---------------------------------------------------------------------------

def _render_chart(
    key: str,
    chart_type: str,
    years: list,
    show_5yr: bool,
    api_key: str,
    padd_chart_type: str,
) -> pd.DataFrame | None:
    if key == "padd":
        render_chart_title("Crude Oil Stocks — PADD Breakdown")
        with st.spinner("Loading…"):
            padd_df = _get_padd(api_key)
        if padd_df.empty:
            st.warning("PADD data unavailable.")
            return None
        filtered = build_padd_timeline(padd_df, years=years or None)
        st.plotly_chart(build_padd_chart(filtered, padd_chart_type), use_container_width=True)
        return padd_df[padd_df["area"] == "PADD 3 (Gulf Coast)"].copy()

    meta = SERIES[key]
    render_chart_title(meta["label"])
    with st.spinner("Loading…"):
        df = _get_series(key, api_key)
    if df.empty:
        st.warning(f"Data for '{meta['label']}' not yet cached. Run refresh_bulk.py or wait for API fetch.")
        return None

    if chart_type == "Seasonality":
        data = build_seasonality_data(df, years=years or None)
        fig  = build_seasonality_chart(data, meta["display_units"], show_5yr, df)
    else:
        data = build_timeline_data(df, years=years or None)
        fig  = build_timeline_chart(data, meta["display_units"])

    st.plotly_chart(fig, use_container_width=True)
    return df

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Stats-O-Rama — Charts", layout="wide")
    render_header("Stats-O-Rama", "U.S. Weekly Petroleum Status  ·  EIA data")

    try:
        api_key = st.secrets["eia_api_key"]
    except Exception:
        st.error("EIA API key not found. Add `eia_api_key` to `.streamlit/secrets.toml`.")
        st.stop()

    # ── Sidebar ──────────────────────────────────────────────────────────────
    st.sidebar.header("Settings")

    all_labels = [label for label, _ in SERIES_OPTIONS]
    default_labels = ["U.S. Crude Stocks", "Crude Production", "Crude Imports"]
    selected_labels = st.sidebar.multiselect("Series", all_labels, default=default_labels)
    selected_keys   = [LABEL_TO_KEY[l] for l in selected_labels]

    has_padd     = "padd" in selected_keys
    has_non_padd = any(k != "padd" for k in selected_keys)

    padd_chart_type = "Timeline"
    if has_padd:
        padd_chart_type = st.sidebar.radio(
            "PADD chart type", ["Timeline", "Stacked Timeline"], horizontal=True, index=0
        )

    chart_type = "Seasonality"
    show_5yr   = False
    if has_non_padd:
        chart_type = st.sidebar.radio(
            "Chart type", ["Seasonality", "Timeline"], horizontal=True, index=0
        )
        if chart_type == "Seasonality":
            show_5yr = st.sidebar.checkbox("Show 5-year average", value=True)

    st.sidebar.divider()

    cur           = pd.Timestamp.today().year
    all_years     = list(range(2000, cur + 1))
    default_years = list(range(cur - 4, cur + 1))
    years = st.sidebar.multiselect("Years", all_years, default=default_years, key="years")

    st.sidebar.markdown("---")
    st.sidebar.page_link("app.py", label="← Back to summary", icon="🏠")

    # ── Chart grid ───────────────────────────────────────────────────────────
    if not selected_keys:
        st.info("Select one or more series from the sidebar.")
        return

    for row_start in range(0, len(selected_keys), 4):
        row_keys = selected_keys[row_start : row_start + 4]
        cols     = st.columns(len(row_keys))
        row_dfs: dict[str, pd.DataFrame] = {}

        for col, key in zip(cols, row_keys):
            with col:
                df = _render_chart(
                    key,
                    padd_chart_type if key == "padd" else chart_type,
                    years, show_5yr, api_key, padd_chart_type,
                )
                if df is not None:
                    row_dfs[key] = df

        valid_keys = [k for k in row_keys if k in row_dfs]
        if not valid_keys:
            continue

        with st.expander("Recent data (last 52 weeks)"):
            if len(valid_keys) == 1:
                k     = valid_keys[0]
                units = "Million Barrels" if k == "padd" else SERIES[k]["display_units"]
                render_data_table(row_dfs[k], units)
            else:
                tab_labels = [
                    "PADD 3 (Gulf Coast)" if k == "padd" else SERIES[k]["label"]
                    for k in valid_keys
                ]
                tabs = st.tabs(tab_labels)
                for tab, k in zip(tabs, valid_keys):
                    with tab:
                        units = "Million Barrels" if k == "padd" else SERIES[k]["display_units"]
                        render_data_table(row_dfs[k], units)


if __name__ == "__main__":
    main()
