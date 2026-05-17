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
                   color:#000000; margin-bottom:2px; font-size:2rem;'>
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
# Metrics row
# ---------------------------------------------------------------------------

def render_metrics(df: pd.DataFrame, display_units: str) -> None:
    """Four headline metrics: latest, year-ago delta, 4-week avg, 5-year avg."""
    latest = df.iloc[-1]
    latest_val = float(latest["value"])
    latest_date = pd.Timestamp(latest["date"])

    # Year-ago: nearest data point at or before (today - 1 year)
    year_ago_cutoff = latest_date - pd.DateOffset(years=1)
    past = df[df["date"] <= year_ago_cutoff]
    year_ago_val = float(past.iloc[-1]["value"]) if not past.empty else None

    four_week_avg = float(df.tail(4)["value"].mean())

    # 5-year same-week average
    this_iso_week = latest_date.isocalendar().week
    five_yr_rows = df[
        (df["date"].dt.isocalendar().week == this_iso_week) &
        (df["date"].dt.year >= latest_date.year - 5) &
        (df["date"].dt.year < latest_date.year)
    ]
    five_yr_avg = float(five_yr_rows["value"].mean()) if not five_yr_rows.empty else None

    fmt = lambda v: f"{v:,.1f} {display_units}"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Latest  ({latest_date.strftime('%b %d, %Y')})", fmt(latest_val))

    if year_ago_val is not None:
        delta = latest_val - year_ago_val
        c2.metric("Year Ago", fmt(year_ago_val), delta=f"{delta:+,.1f}")
    else:
        c2.metric("Year Ago", "N/A")

    c3.metric("4-Week Average", fmt(four_week_avg))

    if five_yr_avg is not None:
        delta5 = latest_val - five_yr_avg
        c4.metric("5-Year Avg (this week)", fmt(five_yr_avg), delta=f"{delta5:+,.1f}")
    else:
        c4.metric("5-Year Average", "N/A")

# ---------------------------------------------------------------------------
# Shared chart layout
# ---------------------------------------------------------------------------

def _apply_base_layout(
    fig: go.Figure,
    y_title: str,
    hovermode: str = "x",
    x_tickformat: str = None,
    x_dtick: str = None,
) -> None:
    xaxis = dict(
        showgrid=False,
        showline=True,
        linecolor="#000000",
        linewidth=1.5,
        ticks="outside",
        ticklen=5,
        tickfont=dict(color="#000000", size=12),
    )
    if x_tickformat:
        xaxis["tickformat"] = x_tickformat
    if x_dtick:
        xaxis["dtick"] = x_dtick

    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=12, color="#000000"),
        xaxis=xaxis,
        yaxis=dict(
            title=dict(text=y_title, font=dict(color="#000000")),
            tickfont=dict(color="#000000"),
            showgrid=True,
            gridcolor="#E8E8E8",
            gridwidth=1,
            showline=False,
            zeroline=False,
            tickformat=",",
        ),
        legend=dict(
            orientation="h",
            y=-0.15,
            x=0,
            title_text="",
            font=dict(size=11, color="#000000"),
        ),
        margin=dict(l=70, r=20, t=40, b=90),
        hovermode=hovermode,
    )


def _add_today_vline(fig: go.Figure, x_val: str, label: bool = True) -> None:
    fig.add_vline(x=x_val, line_dash="dash", line_color="#555555", line_width=1.5)
    if label:
        fig.add_annotation(
            x=x_val, y=1.05, yref="paper", text="Today",
            showarrow=False, font=dict(size=11, color="#555555"), xanchor="center",
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
    """Year-over-year seasonality chart — one line per year on a Jan-Dec x-axis."""
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
                width=2.5 if year == current_year else 2,
            ),
            hovertemplate="%{x|%d %b} · %{y:,.1f} " + display_units + "<extra>" + str(year) + "</extra>",
        ))

    today_plot = pd.Timestamp.today().replace(year=2000).normalize().strftime("%Y-%m-%d")
    _add_today_vline(fig, today_plot)
    _apply_base_layout(fig, display_units, hovermode="x", x_tickformat="%b", x_dtick="M1")
    return fig


def build_timeline_chart(data: pd.DataFrame, display_units: str) -> go.Figure:
    """Single continuous line chart over actual dates."""
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
    """Multi-line or stacked area chart of crude stocks across the five PADDs."""
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
    """Show the most recent 52 weeks with year-ago comparison."""
    recent = df.tail(52).copy().sort_values("date", ascending=False)

    def _year_ago(row_date):
        cutoff = row_date - pd.DateOffset(years=1)
        past = df[df["date"] <= cutoff]
        return float(past.iloc[-1]["value"]) if not past.empty else None

    recent["year_ago"] = recent["date"].apply(_year_ago)
    recent["yoy_chg"]  = (recent["value"] - recent["year_ago"]).round(1)
    recent["yoy_pct"]  = (recent["yoy_chg"] / recent["year_ago"] * 100).round(1)
    recent["date"]     = recent["date"].dt.strftime("%b %d, %Y")

    display = recent.rename(columns={
        "date":     "Week",
        "value":    display_units,
        "year_ago": "Year Ago",
        "yoy_chg":  "Chg vs Year Ago",
        "yoy_pct":  "% Chg",
    }).reset_index(drop=True)

    st.dataframe(display, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Section renderer (shared by Production, Imports, Refinery)
# ---------------------------------------------------------------------------

def render_series_section(
    series_key: str,
    chart_type: str,
    years: list,
    show_5yr: bool,
    api_key: str,
) -> None:
    meta = SERIES[series_key]
    with st.spinner("Loading data…"):
        try:
            df = get_series(series_key, api_key)
        except Exception as e:
            st.error(f"EIA API error: {e}")
            st.stop()

    render_chart_title(meta["label"])
    render_metrics(df, meta["display_units"])

    if chart_type == "Seasonality":
        data = build_seasonality_data(df, years=years or None)
        fig  = build_seasonality_chart(data, meta["display_units"], show_5yr, df)
    else:
        data = build_timeline_data(df, years=years or None)
        fig  = build_timeline_chart(data, meta["display_units"])

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Recent data (last 52 weeks)"):
        render_data_table(df, meta["display_units"])

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Statsorama — EIA Petroleum", layout="wide")
    render_header("Statsorama", "U.S. Weekly Petroleum Status  ·  EIA data")

    try:
        api_key = st.secrets["eia_api_key"]
    except Exception:
        st.error("EIA API key not found. Add `eia_api_key` to `.streamlit/secrets.toml`.")
        st.stop()

    # ---- Sidebar ----------------------------------------------------------------
    st.sidebar.header("Settings")

    section = st.sidebar.radio(
        "Section",
        ["Crude Stocks", "Crude Production", "Crude Imports", "Refinery"],
        index=0,
    )

    geo = None
    if section == "Crude Stocks":
        geo = st.sidebar.radio(
            "Geography",
            ["US Total", "Cushing, OK", "PADD Breakdown"],
            horizontal=True,
            index=0,
        )

    refinery_metric = None
    if section == "Refinery":
        refinery_metric = st.sidebar.radio(
            "Metric",
            ["Crude Inputs (kb/d)", "Utilization (%)"],
            horizontal=True,
            index=0,
        )

    is_padd = (section == "Crude Stocks" and geo == "PADD Breakdown")
    if is_padd:
        chart_type = st.sidebar.radio(
            "Chart type", ["Timeline", "Stacked Timeline"], horizontal=True, index=0
        )
        show_5yr = False
    else:
        chart_type = st.sidebar.radio(
            "Chart type", ["Seasonality", "Timeline"], horizontal=True, index=0
        )
        show_5yr = (
            st.sidebar.checkbox("Show 5-year average", value=True)
            if chart_type == "Seasonality"
            else False
        )

    st.sidebar.divider()

    cur = pd.Timestamp.today().year
    all_years = list(range(2000, cur + 1))
    default_years = list(range(cur - 4, cur + 1))
    years = st.sidebar.multiselect("Years", all_years, default=default_years, key="years")

    # ---- Main area --------------------------------------------------------------

    if section == "Crude Stocks":
        if geo == "PADD Breakdown":
            with st.spinner("Loading PADD data…"):
                try:
                    padd_df = get_padd_stocks(api_key)
                except Exception as e:
                    st.error(f"EIA API error: {e}")
                    st.stop()
            padd_filtered = build_padd_timeline(padd_df, years=years or None)
            render_chart_title("Crude Oil Stocks — PADD Breakdown")
            fig = build_padd_chart(padd_filtered, chart_type)
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("Recent data (last 52 weeks)"):
                render_data_table(
                    padd_df[padd_df["area"] == "PADD 3 (Gulf Coast)"].copy(),
                    "Million Barrels",
                )
        else:
            series_key = "stocks_us" if geo == "US Total" else "stocks_cushing"
            render_series_section(series_key, chart_type, years, show_5yr, api_key)

    elif section == "Crude Production":
        render_series_section("production", chart_type, years, show_5yr, api_key)

    elif section == "Crude Imports":
        render_series_section("imports", chart_type, years, show_5yr, api_key)

    else:  # Refinery
        series_key = "refinery_inputs" if refinery_metric == "Crude Inputs (kb/d)" else "refinery_util"
        render_series_section(series_key, chart_type, years, show_5yr, api_key)


if __name__ == "__main__":
    main()
