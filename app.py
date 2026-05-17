import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from eia_data import SERIES, PADD_AREAS
from data_cache import get_series_cached, get_padd_cached
from chart_data import (
    build_seasonality_data,
    build_5yr_avg,
    build_timeline_data,
    build_padd_timeline,
)

# ---------------------------------------------------------------------------
# Palette — identical to UnitDown for visual consistency
# ---------------------------------------------------------------------------

PALETTE = [
    "#0047AB",  # cobalt blue
    "#CC0000",  # red
    "#00827F",  # teal
    "#E65C00",  # orange
    "#5C2D91",  # purple
    "#2E7D32",  # dark green
    "#8B4513",  # saddle brown
    "#1A237E",  # navy
]

# Ordered list of selectable series for the sidebar
SERIES_OPTIONS = [
    ("U.S. Crude Stocks",     "stocks_us"),
    ("Cushing, OK Stocks",    "stocks_cushing"),
    ("PADD Breakdown",        "padd"),
    ("Crude Production",      "production"),
    ("Crude Imports",         "imports"),
    ("Refinery Crude Inputs", "refinery_inputs"),
    ("Refinery Utilization",  "refinery_util"),
]
LABEL_TO_KEY = {label: key for label, key in SERIES_OPTIONS}
KEY_TO_LABEL = {key: label for label, key in SERIES_OPTIONS}

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_series(series_key: str, api_key: str) -> pd.DataFrame:
    return get_series_cached(series_key, api_key)


@st.cache_data(ttl=3600)
def get_padd_stocks(api_key: str) -> pd.DataFrame:
    return get_padd_cached(api_key)

# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def render_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <style>
        [data-testid="stToolbarActions"] {{display: none;}}
        .block-container {{padding-top: 1.5rem;}}
        </style>
        <h1 style='font-family:"Arial Black",Arial,sans-serif;
                   color:#000000; margin-bottom:2px; font-size:2rem;
                   padding-top:0.4rem;'>
            {title}
        </h1>
        <p style='color:#555555; font-size:15px; margin-top:0; margin-bottom:10px;'>
            {subtitle}
        </p>
        <hr style='border:none; border-top:3px solid #E3120B; margin-bottom:24px;'>
        """,
        unsafe_allow_html=True,
    )


def render_chart_title(text: str) -> None:
    st.markdown(
        f"<h3 style='font-family:\"Arial Black\",Arial,sans-serif; "
        f"color:#000000; font-size:1.1rem; margin-bottom:4px;'>{text}</h3>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Shared chart layout
# ---------------------------------------------------------------------------

def _apply_base_layout(
    fig: go.Figure,
    y_title: str,
    hovermode: str = "x",
    x_tickformat: str = None,
    x_dtick: str = None,
    height: int = 360,
) -> None:
    xaxis = dict(
        showgrid=False,
        showline=True,
        linecolor="#000000",
        linewidth=1.5,
        ticks="outside",
        ticklen=5,
        tickfont=dict(color="#000000", size=11),
    )
    if x_tickformat:
        xaxis["tickformat"] = x_tickformat
    if x_dtick:
        xaxis["dtick"] = x_dtick

    fig.update_layout(
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=11, color="#000000"),
        xaxis=xaxis,
        yaxis=dict(
            title=dict(text=y_title, font=dict(color="#000000", size=11)),
            tickfont=dict(color="#000000", size=11),
            showgrid=True,
            gridcolor="#E8E8E8",
            gridwidth=1,
            showline=False,
            zeroline=False,
            tickformat=",",
        ),
        legend=dict(
            orientation="h",
            y=-0.18,
            x=0,
            title_text="",
            font=dict(size=10, color="#000000"),
        ),
        margin=dict(l=60, r=10, t=30, b=80),
        hovermode=hovermode,
    )


def _add_today_vline(fig: go.Figure, x_val: str, label: bool = True) -> None:
    fig.add_vline(x=x_val, line_dash="dash", line_color="#555555", line_width=1.5)
    if label:
        fig.add_annotation(
            x=x_val, y=1.05, yref="paper", text="Today",
            showarrow=False, font=dict(size=10, color="#555555"), xanchor="center",
        )

# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def build_seasonality_chart(
    data: pd.DataFrame,
    display_units: str,
    show_5yr: bool,
    all_df: pd.DataFrame,
) -> go.Figure:
    fig = go.Figure()
    current_year = pd.Timestamp.today().year
    years = sorted(data["year"].unique())

    if show_5yr:
        avg_df = build_5yr_avg(all_df, current_year)
        if not avg_df.empty:
            fig.add_trace(go.Scatter(
                x=avg_df["plot_date"],
                y=avg_df["value"],
                mode="lines",
                name="5-year avg",
                line=dict(color="#AAAAAA", width=1.5, dash="dash"),
                hovertemplate="%{x|%d %b} · %{y:,.1f} " + display_units + "<extra>5-yr avg</extra>",
            ))

    for i, year in enumerate(years):
        year_data = data[data["year"] == year].sort_values("plot_date")
        fig.add_trace(go.Scatter(
            x=year_data["plot_date"],
            y=year_data["value"],
            mode="lines",
            name=str(year),
            line=dict(
                color=PALETTE[i % len(PALETTE)],
                width=2.5 if year == current_year else 1.5,
            ),
            hovertemplate="%{x|%d %b} · %{y:,.1f} " + display_units + "<extra>" + str(year) + "</extra>",
        ))

    today_plot = pd.Timestamp.today().replace(year=2004).normalize().strftime("%Y-%m-%d")
    _add_today_vline(fig, today_plot)
    _apply_base_layout(fig, display_units, hovermode="x", x_tickformat="%b", x_dtick="M1")
    return fig


def build_timeline_chart(data: pd.DataFrame, display_units: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data["date"],
        y=data["value"],
        mode="lines",
        name=display_units,
        line=dict(color=PALETTE[0], width=2),
        hovertemplate="%{x|%d %b %Y} · %{y:,.1f} " + display_units + "<extra></extra>",
    ))

    today = pd.Timestamp.today().normalize()
    x_min, x_max = data["date"].min(), data["date"].max()
    if x_min <= today <= x_max:
        _add_today_vline(fig, today.strftime("%Y-%m-%d"))

    _apply_base_layout(fig, display_units, hovermode="x")
    return fig


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def build_padd_chart(padd_df: pd.DataFrame, chart_type: str) -> go.Figure:
    fig = go.Figure()
    areas = sorted(padd_df["area"].unique())
    display_units = "Million Barrels"

    for i, area in enumerate(areas):
        area_data = padd_df[padd_df["area"] == area].sort_values("date")
        color = PALETTE[i % len(PALETTE)]
        if chart_type == "Stacked Timeline":
            fig.add_trace(go.Scatter(
                x=area_data["date"],
                y=area_data["value"],
                mode="lines",
                name=area,
                stackgroup="one",
                line=dict(width=0.5, color=color),
                fillcolor=_hex_to_rgba(color, 0.5),
                hovertemplate="%{x|%d %b %Y} · %{y:,.1f} " + display_units + "<extra>" + area + "</extra>",
            ))
        else:
            fig.add_trace(go.Scatter(
                x=area_data["date"],
                y=area_data["value"],
                mode="lines",
                name=area,
                line=dict(color=color, width=2),
                hovertemplate="%{x|%d %b %Y} · %{y:,.1f} " + display_units + "<extra>" + area + "</extra>",
            ))

    today = pd.Timestamp.today().normalize()
    x_min, x_max = padd_df["date"].min(), padd_df["date"].max()
    if x_min <= today <= x_max:
        _add_today_vline(fig, today.strftime("%Y-%m-%d"))

    _apply_base_layout(fig, display_units, hovermode="x unified")
    return fig

# ---------------------------------------------------------------------------
# Data table
# ---------------------------------------------------------------------------

def render_data_table(df: pd.DataFrame, display_units: str) -> None:
    """Show the most recent 52 weeks with week-over-week comparison."""
    recent = df.tail(52).copy().sort_values("date", ascending=False)

    recent["prior_week"] = recent["value"].shift(-1)
    recent["wow_chg"]    = (recent["value"] - recent["prior_week"]).round(1)
    recent["wow_pct"]    = (recent["wow_chg"] / recent["prior_week"] * 100).round(1)
    recent["date"]       = recent["date"].dt.strftime("%b %d, %Y")

    display = recent.rename(columns={
        "date":     "Week",
        "value":    display_units,
        "wow_chg":  "Chg vs Prior Week",
        "wow_pct":  "% Chg",
    })[["Week", display_units, "Chg vs Prior Week", "% Chg"]].reset_index(drop=True)

    st.dataframe(display, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Single-chart renderer — returns df for the data table (None on error)
# ---------------------------------------------------------------------------

def render_single_chart(
    key: str,
    chart_type: str,
    years: list,
    show_5yr: bool,
    api_key: str,
    padd_chart_type: str = "Timeline",
) -> pd.DataFrame | None:
    if key == "padd":
        render_chart_title("Crude Oil Stocks — PADD Breakdown")
        with st.spinner("Loading…"):
            try:
                padd_df = get_padd_stocks(api_key)
            except Exception as e:
                st.error(f"EIA API error: {e}")
                return None
        filtered = build_padd_timeline(padd_df, years=years or None)
        fig = build_padd_chart(filtered, padd_chart_type)
        st.plotly_chart(fig, use_container_width=True)
        return padd_df[padd_df["area"] == "PADD 3 (Gulf Coast)"].copy()

    meta = SERIES[key]
    render_chart_title(meta["label"])
    with st.spinner("Loading…"):
        try:
            df = get_series(key, api_key)
        except Exception as e:
            st.error(f"EIA API error: {e}")
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
    st.set_page_config(page_title="Stats-O-Rama — EIA Petroleum", layout="wide")
    render_header("Stats-O-Rama", "U.S. Weekly Petroleum Status  ·  EIA data")

    try:
        api_key = st.secrets["eia_api_key"]
    except Exception:
        st.error("EIA API key not found. Add `eia_api_key` to `.streamlit/secrets.toml`.")
        st.stop()

    # ---- Sidebar ----------------------------------------------------------------
    st.sidebar.header("Settings")

    all_labels = [label for label, _ in SERIES_OPTIONS]
    default_labels = ["U.S. Crude Stocks", "Crude Production", "Crude Imports"]
    selected_labels = st.sidebar.multiselect("Series", all_labels, default=default_labels)
    selected_keys = [LABEL_TO_KEY[l] for l in selected_labels]

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

    cur = pd.Timestamp.today().year
    all_years     = list(range(2000, cur + 1))
    default_years = list(range(cur - 4, cur + 1))
    years = st.sidebar.multiselect("Years", all_years, default=default_years, key="years")

    # ---- Main area --------------------------------------------------------------
    if not selected_keys:
        st.info("Select one or more series from the sidebar.")
        return

    # Render in rows of up to 4 charts; data table expander after each row
    for row_start in range(0, len(selected_keys), 4):
        row_keys = selected_keys[row_start : row_start + 4]
        cols     = st.columns(len(row_keys))
        row_dfs: dict[str, pd.DataFrame] = {}

        for col, key in zip(cols, row_keys):
            with col:
                df = render_single_chart(
                    key,
                    padd_chart_type if key == "padd" else chart_type,
                    years,
                    show_5yr,
                    api_key,
                    padd_chart_type,
                )
                if df is not None:
                    row_dfs[key] = df

        valid_keys = [k for k in row_keys if k in row_dfs]
        if not valid_keys:
            continue

        with st.expander("Recent data (last 52 weeks)"):
            if len(valid_keys) == 1:
                k = valid_keys[0]
                units = "Million Barrels" if k == "padd" else SERIES[k]["display_units"]
                render_data_table(row_dfs[k], units)
            else:
                short_labels = [
                    "PADD 3 (Gulf Coast)" if k == "padd" else SERIES[k]["label"]
                    for k in valid_keys
                ]
                tabs = st.tabs(short_labels)
                for tab, k in zip(tabs, valid_keys):
                    with tab:
                        units = "Million Barrels" if k == "padd" else SERIES[k]["display_units"]
                        render_data_table(row_dfs[k], units)


if __name__ == "__main__":
    main()
