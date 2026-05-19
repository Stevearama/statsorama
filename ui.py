"""Shared UI helpers: palette, header, chart builders, data table."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chart_data import build_5yr_avg, build_seasonality_data, build_timeline_data

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
# Page chrome
# ---------------------------------------------------------------------------

def render_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <style>
        [data-testid="stToolbarActions"] {{display: none;}}
        .block-container {{padding-top: 3.5rem;}}
        </style>
        <h1 style='font-family:"Arial Black",Arial,sans-serif;
                   color:#000000; margin-bottom:2px; font-size:2rem;
                   padding-top:0.6rem; line-height:1.3; overflow:visible;'>
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
# Section label (small all-caps divider label, like the mockup)
# ---------------------------------------------------------------------------

def section_label(text: str) -> None:
    st.markdown(
        f"<p style='font-size:10px;font-weight:600;color:#999;letter-spacing:0.07em;"
        f"text-transform:uppercase;margin-bottom:8px;margin-top:4px;'>{text}</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Plotly chart layout
# ---------------------------------------------------------------------------

def apply_base_layout(
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


def add_today_vline(fig: go.Figure, x_val: str, label: bool = True) -> None:
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
                x=avg_df["plot_date"], y=avg_df["value"],
                mode="lines", name="5-year avg",
                line=dict(color="#AAAAAA", width=1.5, dash="dash"),
                hovertemplate="%{x|%d %b} · %{y:,.1f} " + display_units + "<extra>5-yr avg</extra>",
            ))

    for i, year in enumerate(years):
        year_data = data[data["year"] == year].sort_values("plot_date")
        fig.add_trace(go.Scatter(
            x=year_data["plot_date"], y=year_data["value"],
            mode="lines", name=str(year),
            line=dict(
                color=PALETTE[i % len(PALETTE)],
                width=2.5 if year == current_year else 1.5,
            ),
            hovertemplate="%{x|%d %b} · %{y:,.1f} " + display_units + "<extra>" + str(year) + "</extra>",
        ))

    today_plot = pd.Timestamp.today().replace(year=2004).normalize().strftime("%Y-%m-%d")
    add_today_vline(fig, today_plot)
    apply_base_layout(fig, display_units, hovermode="x", x_tickformat="%b", x_dtick="M1")
    return fig


def build_timeline_chart(data: pd.DataFrame, display_units: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data["date"], y=data["value"],
        mode="lines", name=display_units,
        line=dict(color=PALETTE[0], width=2),
        hovertemplate="%{x|%d %b %Y} · %{y:,.1f} " + display_units + "<extra></extra>",
    ))
    today = pd.Timestamp.today().normalize()
    x_min, x_max = data["date"].min(), data["date"].max()
    if x_min <= today <= x_max:
        add_today_vline(fig, today.strftime("%Y-%m-%d"))
    apply_base_layout(fig, display_units, hovermode="x")
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
                x=area_data["date"], y=area_data["value"],
                mode="lines", name=area, stackgroup="one",
                line=dict(width=0.5, color=color),
                fillcolor=_hex_to_rgba(color, 0.5),
                hovertemplate="%{x|%d %b %Y} · %{y:,.1f} " + display_units + "<extra>" + area + "</extra>",
            ))
        else:
            fig.add_trace(go.Scatter(
                x=area_data["date"], y=area_data["value"],
                mode="lines", name=area,
                line=dict(color=color, width=2),
                hovertemplate="%{x|%d %b %Y} · %{y:,.1f} " + display_units + "<extra>" + area + "</extra>",
            ))

    today = pd.Timestamp.today().normalize()
    if not padd_df.empty:
        x_min, x_max = padd_df["date"].min(), padd_df["date"].max()
        if x_min <= today <= x_max:
            add_today_vline(fig, today.strftime("%Y-%m-%d"))

    apply_base_layout(fig, display_units, hovermode="x unified")
    return fig

# ---------------------------------------------------------------------------
# Data table
# ---------------------------------------------------------------------------

def render_data_table(df: pd.DataFrame, display_units: str) -> None:
    """Last 52 weeks with week-over-week change."""
    recent = df.tail(52).copy().sort_values("date", ascending=False)
    recent["prior_week"] = recent["value"].shift(-1)
    recent["wow_chg"]    = (recent["value"] - recent["prior_week"]).round(1)
    recent["wow_pct"]    = (recent["wow_chg"] / recent["prior_week"] * 100).round(1)
    recent["date"]       = recent["date"].dt.strftime("%b %d, %Y")

    display = recent.rename(columns={
        "date":    "Week",
        "value":   display_units,
        "wow_chg": "Chg vs Prior Week",
        "wow_pct": "% Chg",
    })[["Week", display_units, "Chg vs Prior Week", "% Chg"]].reset_index(drop=True)

    st.dataframe(display, use_container_width=True, hide_index=True)
