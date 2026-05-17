import requests
import pandas as pd

_V1_URL = "https://api.eia.gov/series/"
_V2_STOCKS_URL = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"

# All weekly crude series available via the v1 series API
SERIES = {
    "stocks_us": {
        "id":            "PET.WCRSTUS1.W",
        "label":         "U.S. Crude Oil Stocks",
        "display_units": "Million Barrels",
        "scale":         1_000,   # source is thousand barrels; divide to get MMbbl
    },
    "stocks_cushing": {
        "id":            "PET.WCSOKLC1.W",
        "label":         "Cushing, OK Crude Oil Stocks",
        "display_units": "Million Barrels",
        "scale":         1_000,
    },
    "production": {
        "id":            "PET.WCRFPUS2.W",
        "label":         "U.S. Crude Oil Production",
        "display_units": "kb/d",
        "scale":         None,
    },
    "imports": {
        "id":            "PET.WCRIMUS2.W",
        "label":         "U.S. Crude Oil Imports",
        "display_units": "kb/d",
        "scale":         None,
    },
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
}

# EIA v2 API duoarea codes for the five PADDs
PADD_AREAS = {
    "PADD 1 (East Coast)":       "R10",
    "PADD 2 (Midwest)":          "R20",
    "PADD 3 (Gulf Coast)":       "R30",
    "PADD 4 (Rocky Mountain)":   "R40",
    "PADD 5 (West Coast)":       "R50",
}


def fetch_series(series_key: str, api_key: str) -> pd.DataFrame:
    """Fetch a named weekly series from the EIA v1 API.

    Returns a DataFrame with 'date' (datetime) and 'value' (float) columns,
    sorted oldest-first. Values are scaled to display units as defined in SERIES.
    """
    meta = SERIES[series_key]
    resp = requests.get(
        _V1_URL,
        params={"api_key": api_key, "series_id": meta["id"], "out": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "series" not in payload or not payload["series"]:
        raise ValueError(f"No data returned for series {meta['id']}")
    raw = payload["series"][0]["data"]
    df = pd.DataFrame(raw, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if meta["scale"]:
        df["value"] = df["value"] / meta["scale"]
    return df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)


def fetch_padd_stocks(api_key: str) -> pd.DataFrame:
    """Fetch weekly crude oil stocks for all five PADDs from the EIA v2 API.

    Returns a DataFrame with 'date', 'area' (PADD name), and 'value' (MMbbl) columns.
    """
    params = [
        ("api_key",               api_key),
        ("frequency",             "weekly"),
        ("data[0]",               "value"),
        ("facets[product][]",     "EPC0"),
        ("sort[0][column]",       "period"),
        ("sort[0][direction]",    "asc"),
        ("length",                "5000"),
    ]
    for code in PADD_AREAS.values():
        params.append(("facets[duoarea][]", code))

    resp = requests.get(_V2_STOCKS_URL, params=params, timeout=30)
    resp.raise_for_status()
    records = resp.json().get("response", {}).get("data", [])
    if not records:
        raise ValueError("No PADD stock data returned from EIA v2 API")

    df = pd.DataFrame(records)
    df = df.rename(columns={"period": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce") / 1_000   # Mbbl → MMbbl
    area_names = {v: k for k, v in PADD_AREAS.items()}
    df["area"] = df["duoarea"].map(area_names)
    return (
        df[["date", "area", "value"]]
        .dropna()
        .sort_values(["area", "date"])
        .reset_index(drop=True)
    )
