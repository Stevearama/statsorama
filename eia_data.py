"""
EIA Open Data API — Reference Guide
=====================================
This module handles all EIA API interactions.  Read this docstring before
adding new series so you pick the most efficient method.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

METHOD A — Backward-compat seriesid endpoint  (quick, any single series)
─────────────────────────────────────────────────────────────────────────
  Add an entry to SERIES below.  fetch_series() handles everything.

  Fields:
    "id"            : v1 series ID from https://www.eia.gov/opendata/browser/
    "label"         : human-readable name for charts / tables
    "display_units" : shown on chart y-axis and in data tables
    "scale"         : divide raw API value by this number (None = no scaling)
                      e.g. source is thousand barrels → use 1_000 → result in MMbbl

  Series ID pattern for petroleum:  PET.{code}.W  (W = weekly)
  Find IDs: https://www.eia.gov/opendata/browser/petroleum


METHOD B — Native v2 endpoint  (preferred when you need 2+ related series)
────────────────────────────────────────────────────────────────────────────
  Use fetch_v2(route, api_key, facets, ...).  One API call returns many
  series simultaneously — exactly how fetch_padd_stocks() works.

  Base URL:  https://api.eia.gov/v2/{route}/data/
  Discovery: GET https://api.eia.gov/v2/{route}/ (no /data/) → returns
             available facets, frequency options, and column names.
  Explorer:  https://www.eia.gov/opendata/browser/

  See V2_ROUTES below for the full petroleum route reference.


METHOD C — Bulk download  (best for initial population of many series)
────────────────────────────────────────────────────────────────────────
  Run refresh_bulk.py to download PET.zip (~200 MB) from:
    https://www.eia.gov/opendata/bulk/PET.zip
  This contains ALL petroleum series in NDJSON format and is faster
  than hundreds of individual API calls.  Use it to seed the parquet
  cache; the incremental API approach (Method A) then handles updates.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COMMON FACET CODES  (used with Method B / fetch_v2)
────────────────────────────────────────────────────
  Product codes  (facets[product][]):
    EPC0    Crude oil
    EPM0    Total motor gasoline
    EPMR    Regular motor gasoline (all formulations)
    EPOBG   Oxygenated / blended gasoline
    EPD2    Distillate fuel oil (total)
    EPD2D   No. 2 diesel (distillate subset)
    EPJK    Kerosene-type jet fuel
    EPLLPZ  Propane / propylene
    EPLLP   Propane
    EPPR    Total petroleum products
    EPCO    Crude oil (import context)

  Geographic area codes  (facets[duoarea][]):
    NUS     United States total
    Y35NY   Cushing, Oklahoma  (WTI pricing hub)
    Y05NY   North Sea          (Brent pricing hub)
    R10     PADD 1 — East Coast
    R20     PADD 2 — Midwest
    R30     PADD 3 — Gulf Coast
    R40     PADD 4 — Rocky Mountain
    R50     PADD 5 — West Coast

  Process codes  (facets[process][]):
    SAE     Ending stocks
    PSA     Production (refinery / blender net output)
    PN0     Net production
    FPF     Field production (crude)
    VCS     Crude inputs to refineries
    YOP     Operable refinery utilization rate (%)
    IM0     Imports
    EX0     Exports
    VPP     Product supplied (demand proxy)
    PTE     Retail price
    PSP     Spot price

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import requests
import pandas as pd

_V2_SERIESID_URL = "https://api.eia.gov/v2/seriesid/"
_V2_BASE_URL     = "https://api.eia.gov/v2/"

# ---------------------------------------------------------------------------
# V2 Native Route Reference
# ---------------------------------------------------------------------------
# Consult this before choosing a route for fetch_v2().
# Strip /data/ from any route and GET it to inspect available facets live:
#   GET https://api.eia.gov/v2/petroleum/stoc/wstk/?api_key=KEY
# ---------------------------------------------------------------------------

V2_ROUTES = {
    # ── Petroleum Stocks ─────────────────────────────────────────────────
    "petroleum/stoc/wstk": {
        "desc":      "Weekly petroleum ending stocks by product and area",
        "frequency": "weekly",
        "value_col": "value",
        "scale":     1_000,   # source is thousand barrels
        "facets": {
            "product": {
                "EPC0":   "Crude oil (excl. SPR)",
                "EPCSPR": "Crude oil — SPR only",  # verify: may be EPCS
                "EPM0":   "Total motor gasoline",
                "EPMRU":  "Conventional (non-oxy) gasoline",
                "EPOBG":  "Oxygenated / reformulated gasoline",
                "EPD2":   "Distillate fuel oil (total)",
                "EPJK":   "Kerosene-type jet fuel",
                "EPLLPZ": "Propane / propylene",
                "EPPR":   "Total petroleum products",
            },
            "duoarea": {
                "NUS":   "U.S. total",
                "Y35NY": "Cushing, Oklahoma",
                "R10":   "PADD 1 — East Coast",
                "R20":   "PADD 2 — Midwest",
                "R30":   "PADD 3 — Gulf Coast",
                "R40":   "PADD 4 — Rocky Mountain",
                "R50":   "PADD 5 — West Coast",
            },
            "process": {"SAE": "Ending stocks"},
        },
        "note": "Divide by 1_000 to convert thousand barrels → million barrels.",
    },

    # ── Refinery Operations ───────────────────────────────────────────────
    "petroleum/pnp/wcrus": {
        "desc":      "Weekly crude inputs to refineries and utilization by PADD",
        "frequency": "weekly",
        "value_col": "value",
        "scale":     None,
        "facets": {
            "duoarea": {
                "NUS": "U.S. total",
                "R10": "PADD 1 — East Coast",
                "R20": "PADD 2 — Midwest",
                "R30": "PADD 3 — Gulf Coast",
                "R40": "PADD 4 — Rocky Mountain",
                "R50": "PADD 5 — West Coast",
            },
            "process": {
                "VCS": "Crude inputs (kb/d)",
                "YOP": "Operable utilization rate (%)",
            },
        },
        "note": "Returns kb/d for inputs and % for utilization.  No scaling needed.",
    },

    # ── Refinery / Blender Net Production ────────────────────────────────
    "petroleum/pnp/refp": {
        "desc":      "Weekly refinery and blender net production by product",
        "frequency": "weekly",
        "value_col": "value",
        "scale":     None,
        "facets": {
            "product": {
                "EPM0":  "Total motor gasoline",
                "EPD2":  "Distillate fuel oil",
                "EPJK":  "Kerosene-type jet fuel",
                "EPLLP": "Propane",
            },
            "duoarea":  {"NUS": "U.S. total"},
            "process":  {"PN0": "Net production (kb/d)"},
        },
    },

    # ── Crude Field Production ────────────────────────────────────────────
    "petroleum/pnp/wiup": {
        "desc":      "Weekly U.S. field production of crude oil (kb/d)",
        "frequency": "weekly",
        "value_col": "value",
        "scale":     None,
        "facets": {
            "product":  {"EPC0": "Crude oil"},
            "duoarea":  {"NUS": "U.S. total", "R10": "PADD 1", "R20": "PADD 2",
                         "R30": "PADD 3",     "R40": "PADD 4", "R50": "PADD 5"},
            "process":  {"FPF": "Field production"},
        },
    },

    # ── Weekly Imports ────────────────────────────────────────────────────
    "petroleum/move/wkly": {
        "desc":      "Weekly petroleum imports by product, area, and country of origin",
        "frequency": "weekly",
        "value_col": "value",
        "scale":     None,
        "facets": {
            "product":  {"EPC0": "Crude oil", "EPM0": "Motor gasoline", "EPD2": "Distillate"},
            "duoarea":  {"NUS": "U.S. total", "R10": "PADD 1", "R20": "PADD 2",
                         "R30": "PADD 3",     "R40": "PADD 4", "R50": "PADD 5"},
            "process":  {"IM0": "Imports (kb/d)"},
        },
        "note": "Also supports facets[sortid][] for country-of-origin breakdown.",
    },

    # ── Weekly Exports ────────────────────────────────────────────────────
    "petroleum/move/exp": {
        "desc":      "Weekly petroleum exports by product",
        "frequency": "weekly",
        "value_col": "value",
        "scale":     None,
        "facets": {
            "product":  {"EPC0": "Crude oil", "EPM0": "Motor gasoline",
                         "EPD2": "Distillate", "EPJK": "Jet fuel"},
            "duoarea":  {"NUS": "U.S. total"},
            "process":  {"EX0": "Exports (kb/d)"},
        },
        "note": "verify: route may differ in v2; check /v2/petroleum/move/ index.",
    },

    # ── Product Supplied (demand proxy) ───────────────────────────────────
    "petroleum/cons/wpsup": {
        "desc":      "Weekly product supplied — best available weekly demand proxy",
        "frequency": "weekly",
        "value_col": "value",
        "scale":     None,
        "facets": {
            "product": {
                "EPM0":  "Total motor gasoline",
                "EPD2":  "Distillate fuel oil",
                "EPJK":  "Kerosene-type jet fuel",
                "EPLLP": "Propane",
            },
            "duoarea":  {"NUS": "U.S. total"},
            "process":  {"VPP": "Product supplied (kb/d)"},
        },
        "note": "EIA reports this as 4-week moving average to smooth week-to-week noise.",
    },

    # ── Retail Fuel Prices (gasoline + diesel) ───────────────────────────────
    # petroleum/pri/wfr = heating oil + propane ONLY (seasonal, not what we want).
    # Weekly retail gasoline AND diesel are both in petroleum/pri/gnd.
    # Diesel series uses EMD_ prefix; gasoline uses EMM_ prefix.
    "petroleum/pri/gnd": {
        "desc":      "Weekly retail gasoline and diesel prices ($/gallon) by PADD",
        "frequency": "weekly",
        "value_col": "value",
        "scale":     None,
        "facets": {
            "product": {
                "EPMR":     "Regular gasoline (all-grades average)",
                "EPMM":     "Midgrade gasoline",
                "EPMP":     "Premium gasoline",
                "EPM0":     "Total gasoline (all grades)",
                "EPD2D":    "No. 2 diesel (ultra-low-sulfur post-Dec 2010)",
                "EPD2DXL0": "No. 2 diesel low-sulfur (0-15 ppm)",
            },
            "duoarea":  {"NUS": "U.S. total", "R10": "PADD 1", "R20": "PADD 2",
                         "R30": "PADD 3",     "R40": "PADD 4", "R50": "PADD 5"},
            "process":  {"PTE": "Retail sales price ($/gal)"},
        },
        "note": "Series ID prefixes differ by product: gasoline=EMM_, diesel=EMD_",
    },
    "petroleum/pri/wfr": {
        "desc":      "HEATING OIL + PROPANE weekly retail prices (seasonal Oct-Mar)",
        "note":      "Not gasoline/diesel. Use petroleum/pri/gnd for those.",
    },

    # ── Spot Prices ───────────────────────────────────────────────────────
    "petroleum/pri/spt": {
        "desc":      "Weekly spot prices at key trading hubs",
        "frequency": "weekly",
        "value_col": "value",
        "scale":     None,
        "facets": {
            "product": {
                "EPC0": "WTI crude (Cushing, OK)",
                "EPD0": "Brent crude (North Sea)",
                "EPM0": "Motor gasoline (NY Harbor)",
                "EPD2": "Heating oil / diesel (NY Harbor)",
            },
            "duoarea": {
                "Y35NY": "Cushing, Oklahoma (WTI)",
                "Y05NY": "North Sea (Brent)",
                "Y35NY": "New York Harbor (products)",  # same hub, different products
            },
            "process":  {"PSP": "Spot price"},
        },
        "note": "WTI weekly spot: product=EPC0, duoarea=Y35NY.  Values in $/bbl for crude.",
    },
}

# ---------------------------------------------------------------------------
# Series registry  (Method A — seriesid backward-compat endpoint)
# ---------------------------------------------------------------------------
# Add new single-series entries here.  Verify IDs at:
#   https://www.eia.gov/opendata/browser/petroleum
# ---------------------------------------------------------------------------

SERIES = {
    # ── Crude Stocks ─────────────────────────────────────────────────────
    "stocks_us": {
        "id":            "PET.WCRSTUS1.W",
        "label":         "U.S. Crude Oil Stocks (excl. SPR)",
        "display_units": "Million Barrels",
        "scale":         1_000,
    },
    "stocks_cushing": {
        "id":            "PET.WCSOKLC1.W",
        "label":         "Cushing, OK Crude Oil Stocks",
        "display_units": "Million Barrels",
        "scale":         1_000,
    },
    "stocks_spr": {
        "id":            "PET.WCSSTUS1.W",   # verify at opendata browser
        "label":         "Strategic Petroleum Reserve",
        "display_units": "Million Barrels",
        "scale":         1_000,
    },

    # ── Product Stocks ────────────────────────────────────────────────────
    "stocks_gasoline": {
        "id":            "PET.WGTSTUS1.W",
        "label":         "U.S. Total Motor Gasoline Stocks",
        "display_units": "Million Barrels",
        "scale":         1_000,
    },
    "stocks_distillate": {
        "id":            "PET.WDISTUS1.W",
        "label":         "U.S. Distillate Fuel Oil Stocks",
        "display_units": "Million Barrels",
        "scale":         1_000,
    },
    "stocks_jet": {
        "id":            "PET.WKJSTUS1.W",   # verify — may be WKJSTUS2
        "label":         "U.S. Kerosene-Type Jet Fuel Stocks",
        "display_units": "Million Barrels",
        "scale":         1_000,
    },
    "stocks_propane": {
        "id":            "PET.WPRSTUS1.W",
        "label":         "U.S. Propane / Propylene Stocks",
        "display_units": "Million Barrels",
        "scale":         1_000,
    },

    # ── Production ────────────────────────────────────────────────────────
    "production": {
        "id":            "PET.WCRFPUS2.W",
        "label":         "U.S. Crude Oil Production",
        "display_units": "kb/d",
        "scale":         None,
    },
    "prod_gasoline": {
        "id":            "PET.WGFUPUS2.W",
        "label":         "U.S. Gasoline Production",
        "display_units": "kb/d",
        "scale":         None,
    },
    "prod_distillate": {
        "id":            "PET.WDIRPUS2.W",   # verify at opendata browser
        "label":         "U.S. Distillate Production",
        "display_units": "kb/d",
        "scale":         None,
    },

    # ── Imports ───────────────────────────────────────────────────────────
    "imports": {
        "id":            "PET.WCRIMUS2.W",
        "label":         "U.S. Crude Oil Imports",
        "display_units": "kb/d",
        "scale":         None,
    },

    # ── Refinery Operations ───────────────────────────────────────────────
    "refinery_inputs": {
        "id":            "PET.WCRRIUS2.W",
        "label":         "U.S. Refinery Crude Inputs",
        "display_units": "kb/d",
        "scale":         None,
    },
    "refinery_util": {
        "id":            "PET.WPULEUS3.W",
        "label":         "U.S. Refinery Utilization",
        "display_units": "%",
        "scale":         None,
    },

    # ── Prices ────────────────────────────────────────────────────────────
    "wti_spot": {
        "id":            "PET.RWTC.W",
        "label":         "WTI Crude Oil Spot Price",
        "display_units": "$/bbl",
        "scale":         None,
    },
    "gasoline_retail": {
        "id":            "PET.EMM_EPMR_PTE_NUS_DPG.W",  # verify at opendata browser
        "label":         "U.S. Regular Gasoline Retail Price",
        "display_units": "$/gal",
        "scale":         None,
    },
    "diesel_retail": {
        "id":            "PET.EMD_EPD2D_PTE_NUS_DPG.W",  # EMD prefix, not EMM — confirmed via api
        "label":         "U.S. No. 2 Diesel Retail Price",
        "display_units": "$/gal",
        "scale":         None,
    },
}

# EIA v2 facet codes for the five PADDs  (used by fetch_padd_stocks)
PADD_AREAS = {
    "PADD 1 (East Coast)":       "R10",
    "PADD 2 (Midwest)":          "R20",
    "PADD 3 (Gulf Coast)":       "R30",
    "PADD 4 (Rocky Mountain)":   "R40",
    "PADD 5 (West Coast)":       "R50",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_seriesid_response(payload: dict, scale) -> pd.DataFrame:
    """Parse either v1-format (series[0].data) or v2-format (response.data)."""
    if "series" in payload and payload["series"]:
        raw = payload["series"][0]["data"]
        df = pd.DataFrame(raw, columns=["date", "value"])
    elif "response" in payload and payload["response"].get("data"):
        df = pd.DataFrame(payload["response"]["data"])
        df = df.rename(columns={"period": "date"})[["date", "value"]]
    else:
        return pd.DataFrame(columns=["date", "value"])

    df["date"]  = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if scale:
        df["value"] = df["value"] / scale
    return df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)


def _raise_with_detail(resp: requests.Response) -> None:
    try:
        body = resp.json()
    except Exception:
        body = resp.text[:500]
    raise requests.HTTPError(
        f"EIA API returned {resp.status_code}: {body}",
        response=resp,
    )

# ---------------------------------------------------------------------------
# Method A — seriesid backward-compat fetchers
# ---------------------------------------------------------------------------

def fetch_series(series_key: str, api_key: str) -> pd.DataFrame:
    """Fetch full history for a named series via the EIA v2 seriesid endpoint."""
    meta = SERIES[series_key]
    resp = requests.get(
        f"{_V2_SERIESID_URL}{meta['id']}",
        params={"api_key": api_key, "data[0]": "value", "length": "5000"},
        timeout=30,
    )
    if not resp.ok:
        _raise_with_detail(resp)
    return _parse_seriesid_response(resp.json(), meta["scale"])


def fetch_series_since(series_key: str, api_key: str, since: pd.Timestamp) -> pd.DataFrame:
    """Fetch only weeks after `since` — used for incremental cache updates."""
    meta = SERIES[series_key]
    resp = requests.get(
        f"{_V2_SERIESID_URL}{meta['id']}",
        params={"api_key": api_key, "data[0]": "value", "start": since.strftime("%Y%m%d")},
        timeout=30,
    )
    if not resp.ok:
        _raise_with_detail(resp)
    return _parse_seriesid_response(resp.json(), meta["scale"])

# ---------------------------------------------------------------------------
# Method B — native v2 endpoint fetcher
# ---------------------------------------------------------------------------

def fetch_v2(
    route: str,
    api_key: str,
    facets: dict,
    frequency: str = "weekly",
    value_col: str = "value",
    scale: float | None = None,
    length: int = 5000,
    start: str | None = None,
) -> pd.DataFrame:
    """Fetch data from a native EIA v2 endpoint with facet filtering.

    More efficient than fetch_series() when you need multiple related series
    (e.g., all PADD crude stocks in one call).  See V2_ROUTES for route
    reference and available facets.

    Args:
        route:     EIA v2 route, e.g. "petroleum/stoc/wstk"  (no leading slash)
        api_key:   EIA API key
        facets:    dict of facet_name → list[str], e.g.
                   {"product": ["EPC0"], "duoarea": ["NUS", "R10", "R20"]}
        frequency: "weekly", "monthly", or "annual"
        value_col: name of the value column (almost always "value")
        scale:     divide raw values by this (e.g. 1_000 for kb → MMbbl)
        length:    rows per request — EIA caps at 5_000; paginate if needed
        start:     ISO date for incremental fetch, e.g. "2024-01-01"

    Returns:
        DataFrame with 'date' column plus all facet columns and value_col.
        Not yet deduplicated or sorted — caller handles that.

    Notes:
        • 5_000 row limit: for 10 products × 6 PADDs × 30 yrs ≈ 93k rows,
          you will need to paginate (add offset param or filter by date range).
        • Discover facets:  GET /v2/{route}/?api_key=KEY
    """
    url = f"{_V2_BASE_URL}{route}/data/"
    params = [
        ("api_key",            api_key),
        ("frequency",          frequency),
        (f"data[0]",           value_col),
        ("sort[0][column]",    "period"),
        ("sort[0][direction]", "asc"),
        ("length",             str(length)),
    ]
    if start:
        params.append(("start", start))
    for facet_name, codes in facets.items():
        for code in codes:
            params.append((f"facets[{facet_name}][]", code))

    resp = requests.get(url, params=params, timeout=30)
    if not resp.ok:
        _raise_with_detail(resp)

    records = resp.json().get("response", {}).get("data", [])
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.rename(columns={"period": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    if scale:
        df[value_col] = df[value_col] / scale
    return df.dropna(subset=[value_col]).reset_index(drop=True)

# ---------------------------------------------------------------------------
# Weekly retail fuel prices — gasoline + diesel for all PADDs  (Method B)
# ---------------------------------------------------------------------------
# Route:    petroleum/pri/gnd  (NOT wfr — wfr is heating oil/propane only)
#
# Gasoline product codes (all prefix EMM_):
#   EPMR    Regular gasoline, all formulations (combined US-level average)
#   EPMRU   Regular conventional gasoline  (PADDs 2, 3, 4 and most of 1/5)
#   EPMRR   Regular reformulated gasoline  (PADD 1 cities, California, etc.)
#   EPMM    Midgrade, all formulations
#   EPMMU   Midgrade conventional
#   EPMMR   Midgrade reformulated
#   EPMP    Premium, all formulations
#   EPMPU   Premium conventional
#   EPMPR   Premium reformulated
#   EPM0    Total gasoline (all grades)
#   EPM0U   Conventional gasoline (no oxy, all grades)
#   EPM0R   Reformulated gasoline (all grades)
#
# Diesel product codes (prefix EMD_):
#   EPD2D      No. 2 diesel, all types (legacy — use EPD2DXL0 instead)
#   EPD2DXL0   No. 2 diesel low-sulfur 0–15 ppm (ULSD; current live series)
#   EPD2DM10   No. 2 diesel low-sulfur 15–500 ppm (phased out)
#
# Series ID pattern: EMM_{product}_PTE_{area}_DPG  (gasoline)
#                    EMD_{product}_PTE_{area}_DPG  (diesel — note EMD not EMM)
# Areas:    NUS (US total), R10 (PADD 1), R20 (PADD 2), R30 (PADD 3),
#           R40 (PADD 4), R50 (PADD 5)
# Process:  PTE = retail sales price ($/gallon)
# ---------------------------------------------------------------------------

def fetch_fuel_prices(api_key: str, start: str = None) -> pd.DataFrame:
    """Fetch weekly retail gasoline + diesel prices for US total and all PADDs.

    Returns DataFrame with columns: date, product, duoarea, value ($/gallon).
    One call returns all products × areas — no separate fetches per PADD.

    product codes fetched:
        EPMR    = regular gasoline, all formulations (combined)
        EPMRU   = regular conventional gasoline
        EPMRR   = regular reformulated gasoline
        EPD2DXL0= No. 2 diesel ULSD (0-15 ppm)
    duoarea codes:  NUS, R10, R20, R30, R40, R50
    """
    return fetch_v2(
        route="petroleum/pri/gnd",
        api_key=api_key,
        facets={
            "product":  ["EPMR", "EPMRU", "EPMRR", "EPD2DXL0"],
            "duoarea":  ["NUS", "R10", "R20", "R30", "R40", "R50"],
            "process":  ["PTE"],
        },
        start=start,
    )


# PADD crude stocks  (Method B example — multi-area in one call)
# ---------------------------------------------------------------------------

def fetch_padd_stocks(api_key: str) -> pd.DataFrame:
    """Fetch full weekly crude stock history for all five PADDs."""
    df = fetch_v2(
        route="petroleum/stoc/wstk",
        api_key=api_key,
        facets={
            "product":  ["EPC0"],
            "duoarea":  list(PADD_AREAS.values()),
            "process":  ["SAE"],
        },
        scale=1_000,
    )
    if df.empty:
        return pd.DataFrame(columns=["date", "area", "value"])

    area_names = {v: k for k, v in PADD_AREAS.items()}
    df["area"] = df["duoarea"].map(area_names)
    return (
        df[["date", "area", "value"]]
        .dropna()
        .sort_values(["area", "date"])
        .reset_index(drop=True)
    )


def fetch_padd_stocks_since(api_key: str, since: pd.Timestamp) -> pd.DataFrame:
    """Incremental PADD stocks fetch — only weeks after `since`."""
    df = fetch_v2(
        route="petroleum/stoc/wstk",
        api_key=api_key,
        facets={
            "product":  ["EPC0"],
            "duoarea":  list(PADD_AREAS.values()),
            "process":  ["SAE"],
        },
        scale=1_000,
        start=since.strftime("%Y-%m-%d"),
    )
    if df.empty:
        return pd.DataFrame(columns=["date", "area", "value"])

    area_names = {v: k for k, v in PADD_AREAS.items()}
    df["area"] = df["duoarea"].map(area_names)
    return (
        df[["date", "area", "value"]]
        .dropna()
        .sort_values(["area", "date"])
        .reset_index(drop=True)
    )
