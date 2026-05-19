"""Summary / home page — Weekly EIA petroleum snapshot."""

import streamlit as st
import pandas as pd

from eia_data import SERIES, PADD_AREAS
from data_cache import get_series_cached, get_padd_cached, get_fuel_prices_cached
from ui import render_header, section_label

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def _series(key: str, api_key: str) -> pd.DataFrame:
    try:
        return get_series_cached(key, api_key)
    except Exception:
        return pd.DataFrame(columns=["date", "value"])


@st.cache_data(ttl=3600)
def _padd(api_key: str) -> pd.DataFrame:
    try:
        return get_padd_cached(api_key)
    except Exception:
        return pd.DataFrame(columns=["date", "area", "value"])


@st.cache_data(ttl=3600)
def _fuel_prices(api_key: str) -> pd.DataFrame:
    try:
        return get_fuel_prices_cached(api_key)
    except Exception:
        return pd.DataFrame(columns=["date", "product", "duoarea", "value"])


# Maps sidebar geo label → EIA duoarea code
_GEO_TO_DUOAREA = {
    "US Total": "NUS",
    "PADD 1":   "R10",
    "PADD 2":   "R20",
    "PADD 3":   "R30",
    "PADD 4":   "R40",
    "PADD 5":   "R50",
}

# ---------------------------------------------------------------------------
# Stat helpers
# ---------------------------------------------------------------------------

def _latest(df: pd.DataFrame) -> tuple:
    """Return (value, date, wow_change) or (None, None, None) if empty."""
    if df.empty or len(df) < 1:
        return None, None, None
    latest = df.iloc[-1]
    val  = float(latest["value"])
    date = pd.Timestamp(latest["date"])
    wow  = float(df.iloc[-1]["value"] - df.iloc[-2]["value"]) if len(df) >= 2 else None
    return val, date, wow


def _gauge_stats(df: pd.DataFrame) -> dict | None:
    """Compute inventory gauge statistics vs 5-year same-week history."""
    if df.empty or len(df) < 2:
        return None

    latest     = df.iloc[-1]
    current    = float(latest["value"])
    curr_date  = pd.Timestamp(latest["date"])
    wow_chg    = current - float(df.iloc[-2]["value"])

    year_ago_cut = curr_date - pd.DateOffset(years=1)
    past         = df[df["date"] <= year_ago_cut]
    yoy_chg      = (current - float(past.iloc[-1]["value"])) if not past.empty else None

    this_week = curr_date.isocalendar().week
    this_year = curr_date.year
    hist = df[
        (df["date"].dt.isocalendar().week == this_week) &
        (df["date"].dt.year >= this_year - 5) &
        (df["date"].dt.year <  this_year)
    ]

    if hist.empty:
        return {"current": current, "wow_chg": wow_chg, "yoy_chg": yoy_chg,
                "pct_vs_5yr": None, "gauge_pct": 50}

    avg = float(hist["value"].mean())
    lo  = float(hist["value"].min())
    hi  = float(hist["value"].max())
    pct = (current - avg) / avg * 100 if avg else None
    gp  = max(0, min(100, (current - lo) / (hi - lo) * 100)) if hi != lo else 50

    return {"current": current, "wow_chg": wow_chg, "yoy_chg": yoy_chg,
            "pct_vs_5yr": pct, "gauge_pct": gp}

# ---------------------------------------------------------------------------
# Rendered components
# ---------------------------------------------------------------------------

def _price_strip(api_key: str, geo: str) -> None:
    """Top bar: latest week date + WTI / retail gas / retail diesel for selected geo."""
    area  = _GEO_TO_DUOAREA.get(geo, "NUS")
    df_wti  = _series("wti_spot", api_key)
    df_fuel = _fuel_prices(api_key)

    def _latest_fuel(product: str):
        sub = df_fuel[
            (df_fuel["product"]  == product) &
            (df_fuel["duoarea"] == area)
        ].sort_values("date")
        if sub.empty:
            return None, None
        val = float(sub.iloc[-1]["value"])
        wow = float(sub.iloc[-1]["value"] - sub.iloc[-2]["value"]) if len(sub) >= 2 else None
        return val, wow

    wti_val, _, wti_wow = _latest(df_wti)
    conv_val, conv_wow  = _latest_fuel("EPMRU")
    ref_val,  ref_wow   = _latest_fuel("EPMRR")
    dsl_val,  dsl_wow   = _latest_fuel("EPD2DXL0")

    def _fmt(val, wow, decimals=3):
        val_str = f"${val:,.{decimals}f}" if val is not None else "—"
        if wow is None or val is None:
            return val_str, ""
        sign  = "▲" if wow > 0 else "▼"
        color = "#b91c1c" if wow > 0 else "#15803d"
        chg   = (f"<span style='color:{color};font-size:11px;margin-left:4px;'>"
                 f"{sign} {abs(wow):.3f} wk</span>")
        return val_str, chg

    wti_str,  wti_chg  = _fmt(wti_val,  wti_wow,  decimals=2)
    conv_str, conv_chg = _fmt(conv_val, conv_wow)
    ref_str,  ref_chg  = _fmt(ref_val,  ref_wow)
    dsl_str,  dsl_chg  = _fmt(dsl_val,  dsl_wow)

    snap_date = ""
    for df in [df_wti, df_fuel]:
        if not df.empty:
            snap_date = pd.Timestamp(df.iloc[-1]["date"]).strftime("Week ended %b %-d, %Y")
            break

    geo_sfx = "" if geo == "US Total" else f" ({geo})"
    items = [
        ("WTI spot",                          wti_str,  wti_chg),
        (f"Regular conv.{geo_sfx}",           conv_str, conv_chg),
        (f"Regular ref.{geo_sfx}",            ref_str,  ref_chg),
        (f"Diesel (ULSD){geo_sfx}",           dsl_str,  dsl_chg),
    ]
    price_html = "".join(
        f"<div style='text-align:right;'>"
        f"<span style='font-size:11px;color:#999;display:block;margin-bottom:2px;'>{lbl}</span>"
        f"<span style='font-size:14px;font-weight:600;'>{val}{chg}</span>"
        f"</div>"
        for lbl, val, chg in items
    )

    st.markdown(
        f"""<div style='display:flex;align-items:center;justify-content:space-between;
                        padding-bottom:12px;border-bottom:1px solid #ddd;margin-bottom:16px;'>
              <div style='display:flex;align-items:baseline;gap:10px;'>
                <span style='font-size:15px;font-weight:600;'>Weekly snapshot</span>
                <span style='font-size:12px;color:#777;'>{snap_date}</span>
              </div>
              <div style='display:flex;gap:24px;'>{price_html}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def _kpi_card(label: str, val, units: str, wow) -> str:
    """Return HTML for a single KPI card (refinery activity row)."""
    val_str = f"{val:,.0f}" if val is not None else "—"
    if wow is not None:
        sign  = "+" if wow >= 0 else ""
        color = "#b91c1c" if wow >= 0 else "#15803d"
        sub   = (f"<div style='font-size:11px;margin-top:3px;color:{color};'>"
                 f"{sign}{wow:,.0f} vs last wk</div>")
    else:
        sub = "<div style='font-size:11px;margin-top:3px;color:#999;'>—</div>"

    return (
        f"<div style='background:#ede9e0;border-radius:8px;padding:10px 12px;'>"
        f"<div style='font-size:11px;color:#666;margin-bottom:3px;'>{label}</div>"
        f"<div style='font-size:19px;font-weight:600;line-height:1.2;'>"
        f"{val_str}<span style='font-size:11px;color:#999;font-weight:400;'> {units}</span></div>"
        f"{sub}</div>"
    )


def _refinery_kpis(api_key: str) -> None:
    section_label("Refinery activity")
    keys = ["refinery_inputs", "refinery_util", "prod_gasoline",
            "prod_distillate", "production", "imports"]
    dfs  = {k: _series(k, api_key) for k in keys}

    def _kv(key):
        val, _, wow = _latest(dfs[key])
        return val, wow

    cards = [
        ("Crude inputs",        *_kv("refinery_inputs"),  SERIES["refinery_inputs"]["display_units"]),
        ("Utilization",         *_kv("refinery_util"),    SERIES["refinery_util"]["display_units"]),
        ("Gasoline production", *_kv("prod_gasoline"),    SERIES["prod_gasoline"]["display_units"]),
        ("Distillate prod.",    *_kv("prod_distillate"),  SERIES["prod_distillate"]["display_units"]),
        ("Crude production",    *_kv("production"),       SERIES["production"]["display_units"]),
        ("Crude imports",       *_kv("imports"),          SERIES["imports"]["display_units"]),
    ]

    html = "".join(_kpi_card(lbl, val, units, wow) for lbl, val, wow, units in cards)
    st.markdown(
        f"<div style='display:grid;grid-template-columns:repeat(6,1fr);gap:8px;"
        f"margin-bottom:22px;'>{html}</div>",
        unsafe_allow_html=True,
    )


def _inv_card(label: str, stats: dict | None, units: str) -> str:
    """Return HTML for one inventory gauge card."""
    if stats is None:
        return (
            f"<div style='background:#fff;border:1px solid #e5e5e5;border-radius:10px;"
            f"padding:12px 14px;'>"
            f"<div style='font-size:12px;color:#666;margin-bottom:4px;'>{label}</div>"
            f"<div style='font-size:14px;color:#aaa;'>Data not yet cached</div>"
            f"</div>"
        )

    pct  = stats["pct_vs_5yr"]
    gp   = stats["gauge_pct"]
    cur  = stats["current"]
    wow  = stats["wow_chg"]
    yoy  = stats["yoy_chg"]

    if pct is None:
        tag  = "<span style='font-size:11px;color:#aaa;'>N/A</span>"
        bar  = "#aaa"
    elif pct >= 5:
        tag  = (f"<span style='font-size:11px;font-weight:600;padding:2px 7px;"
                f"border-radius:4px;background:#dcfce7;color:#166534;'>+{pct:.1f}%</span>")
        bar  = "#16a34a"
    elif pct <= -5:
        tag  = (f"<span style='font-size:11px;font-weight:600;padding:2px 7px;"
                f"border-radius:4px;background:#fee2e2;color:#991b1b;'>{pct:.1f}%</span>")
        bar  = "#dc2626"
    else:
        tag  = (f"<span style='font-size:11px;font-weight:600;padding:2px 7px;"
                f"border-radius:4px;background:#fef3c7;color:#92400e;'>{pct:+.1f}%</span>")
        bar  = "#d97706"

    wow_str = f"{wow:+.1f} {units} wk/wk"  if wow  is not None else "—"
    yoy_str = f"{yoy:+.1f} vs yr ago"       if yoy  is not None else "—"

    return (
        f"<div style='background:#fff;border:1px solid #e5e5e5;border-radius:10px;"
        f"padding:12px 14px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start;"
        f"margin-bottom:4px;'>"
        f"<span style='font-size:12px;color:#666;'>{label}</span>{tag}</div>"
        f"<div style='font-size:18px;font-weight:600;margin-bottom:8px;'>"
        f"{cur:,.1f} <span style='font-size:12px;font-weight:400;color:#999;'>{units}</span></div>"
        f"<div style='height:5px;background:#e5e5e5;border-radius:3px;position:relative;margin-bottom:4px;'>"
        f"<div style='width:{gp:.0f}%;height:100%;background:{bar};border-radius:3px;'></div>"
        f"<div style='position:absolute;top:-3px;left:50%;width:2px;height:11px;"
        f"background:#999;border-radius:1px;'></div></div>"
        f"<div style='display:flex;justify-content:space-between;font-size:10px;"
        f"color:#bbb;margin-bottom:6px;'><span>5yr low</span><span>5yr avg</span><span>5yr high</span></div>"
        f"<div style='font-size:11px;color:#888;'>{wow_str} &nbsp;·&nbsp; {yoy_str}</div>"
        f"</div>"
    )


_PADD_FULL = {
    "PADD 1": "PADD 1 (East Coast)",
    "PADD 2": "PADD 2 (Midwest)",
    "PADD 3": "PADD 3 (Gulf Coast)",
    "PADD 4": "PADD 4 (Rocky Mountain)",
    "PADD 5": "PADD 5 (West Coast)",
}


def _inventory_gauges(api_key: str, geo: str) -> None:
    section_label("Inventory status — vs 5-year average")

    if geo == "US Total":
        crude_lbl = "Crude oil (excl. SPR)"
        crude_df  = _series("stocks_us", api_key)
    else:
        full_name = _PADD_FULL[geo]
        crude_lbl = f"Crude — {full_name}"
        padd_all  = _padd(api_key)
        crude_df  = padd_all[padd_all["area"] == full_name].copy()

    product_series = [
        ("Motor gasoline",      "stocks_gasoline"),
        ("Distillate fuel oil", "stocks_distillate"),
        ("Kerosene / jet fuel", "stocks_jet"),
        ("Propane / propylene", "stocks_propane"),
        ("SPR crude",           "stocks_spr"),
    ]

    cards_html = _inv_card(crude_lbl, _gauge_stats(crude_df), "mb")
    for label, key in product_series:
        cards_html += _inv_card(label, _gauge_stats(_series(key, api_key)), "mb")

    st.markdown(
        f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:10px;"
        f"margin-bottom:22px;'>{cards_html}</div>",
        unsafe_allow_html=True,
    )


def _movers_panel(api_key: str) -> None:
    """Biggest week-over-week movers across loaded series."""
    watch = [
        ("stocks_us",          "Crude oil stocks",       "mb"),
        ("stocks_gasoline",    "Gasoline stocks",        "mb"),
        ("stocks_distillate",  "Distillate stocks",      "mb"),
        ("stocks_jet",         "Jet fuel stocks",        "mb"),
        ("stocks_propane",     "Propane stocks",         "mb"),
        ("production",         "Crude production",       "kb/d"),
        ("imports",            "Crude imports",          "kb/d"),
        ("refinery_inputs",    "Refinery inputs",        "kb/d"),
        ("refinery_util",      "Refinery utilization",   "%"),
    ]
    rows = []
    for key, label, units in watch:
        df = _series(key, api_key)
        if df.empty or len(df) < 2:
            continue
        val, _, wow = _latest(df)
        if wow is None:
            continue
        rows.append((label, units, wow, val))

    if not rows:
        st.caption("No mover data available yet.")
        return

    rows.sort(key=lambda r: abs(r[2]), reverse=True)

    html_rows = ""
    for label, units, wow, val in rows[:6]:
        sign  = "▲" if wow >= 0 else "▼"
        color = "#b91c1c" if wow >= 0 else "#15803d"
        html_rows += (
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"padding:7px 0;border-bottom:1px solid #f0f0f0;'>"
            f"<div><div style='font-size:12px;font-weight:500;'>{label}</div>"
            f"<div style='font-size:11px;color:#888;'>now {val:,.1f} {units}</div></div>"
            f"<div style='text-align:right;'>"
            f"<div style='font-size:13px;font-weight:600;color:{color};'>"
            f"{sign} {abs(wow):,.1f} {units}</div></div></div>"
        )

    st.markdown(
        f"<div style='background:#fff;border:1px solid #e5e5e5;border-radius:10px;"
        f"padding:14px 16px;'>"
        f"<div style='font-size:13px;font-weight:600;margin-bottom:12px;color:#333;'>"
        f"Biggest movers this week</div>"
        f"{html_rows}</div>",
        unsafe_allow_html=True,
    )


def _padd_table(api_key: str) -> None:
    """PADD crude stocks table — latest week."""
    df = _padd(api_key)
    if df.empty:
        st.caption("PADD data not yet cached.")
        return

    padd_order = list(PADD_AREAS.keys())
    rows_html  = ""
    for area in padd_order:
        sub = df[df["area"] == area].sort_values("date")
        if sub.empty:
            continue
        cur = float(sub.iloc[-1]["value"])
        wow = float(sub.iloc[-1]["value"] - sub.iloc[-2]["value"]) if len(sub) >= 2 else None

        wow_html = ""
        if wow is not None:
            bg    = "#fee2e2" if wow >= 0 else "#dcfce7"
            color = "#991b1b" if wow >= 0 else "#166534"
            sign  = "+" if wow >= 0 else ""
            wow_html = (f"<span style='display:inline-block;padding:1px 6px;"
                        f"border-radius:3px;font-size:10px;font-weight:600;"
                        f"background:{bg};color:{color};'>{sign}{wow:.1f}</span>")

        rows_html += (
            f"<tr>"
            f"<td style='padding:6px 8px 6px 0;font-size:12px;color:#555;"
            f"border-bottom:1px solid #f5f5f5;'>{area}</td>"
            f"<td style='padding:6px 8px;text-align:right;font-size:12px;"
            f"border-bottom:1px solid #f5f5f5;font-weight:600;'>{cur:.1f}</td>"
            f"<td style='padding:6px 0 6px 8px;text-align:right;"
            f"border-bottom:1px solid #f5f5f5;'>{wow_html}</td>"
            f"</tr>"
        )

    st.markdown(
        f"<div style='background:#fff;border:1px solid #e5e5e5;border-radius:10px;"
        f"padding:14px 16px;'>"
        f"<div style='font-size:13px;font-weight:600;margin-bottom:12px;color:#333;'>"
        f"PADD crude oil stocks</div>"
        f"<table style='width:100%;border-collapse:collapse;'>"
        f"<thead><tr>"
        f"<th style='font-size:11px;color:#999;font-weight:500;padding:0 8px 8px 0;"
        f"text-align:left;border-bottom:1px solid #eee;'>District</th>"
        f"<th style='font-size:11px;color:#999;font-weight:500;padding:0 8px 8px;"
        f"text-align:right;border-bottom:1px solid #eee;'>MMbbl</th>"
        f"<th style='font-size:11px;color:#999;font-weight:500;padding:0 0 8px 8px;"
        f"text-align:right;border-bottom:1px solid #eee;'>wk/wk</th>"
        f"</tr></thead>"
        f"<tbody>{rows_html}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def _nav_buttons() -> None:
    section_label("Explore detail charts")
    st.link_button("Open detail charts →", url="Charts", type="primary")

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

    # ── Sidebar ──────────────────────────────────────────────────────────────
    st.sidebar.header("Settings")
    geo = st.sidebar.radio(
        "Crude stocks geography",
        ["US Total", "PADD 1", "PADD 2", "PADD 3", "PADD 4", "PADD 5"],
        index=0,
    )

    # ── Summary sections ─────────────────────────────────────────────────────
    _price_strip(api_key, geo)
    _refinery_kpis(api_key)
    _inventory_gauges(api_key, geo)

    col_l, col_r = st.columns(2)
    with col_l:
        _movers_panel(api_key)
    with col_r:
        _padd_table(api_key)

    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    _nav_buttons()


if __name__ == "__main__":
    main()
