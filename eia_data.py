import requests
import pandas as pd

_V2_SERIESID_URL = "https://api.eia.gov/v2/seriesid/"   # backward-compat for legacy series IDs
_V2_STOCKS_URL   = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"

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


def _parse_v1_response(payload: dict, scale) -> pd.DataFrame:
    if "series" not in payload or not payload["series"]:
        return pd.DataFrame(columns=["date", "value"])
    raw = payload["series"][0]["data"]
    df = pd.DataFrame(raw, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if scale:
        df["value"] = df["value"] / scale
    return df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)


def _raise_with_detail(resp: requests.Response) -> None:
    """Raise an HTTPError that includes the response body — useful for debugging API errors."""
    try:
        body = resp.json()
    except Exception:
        body = resp.text[:500]
    raise requests.HTTPError(
        f"EIA API returned {resp.status_code}: {body}",
        response=resp,
    )


def fetch_series(series_key: str, api_key: str) -> pd.DataFrame:
    """Fetch full history for a named weekly series via the EIA v2 seriesid endpoint."""
    meta = SERIES[series_key]
    resp = requests.get(
        f"{_V2_SERIESID_URL}{meta['id']}",
        params={"api_key": api_key},
        timeout=30,
    )
    if not resp.ok:
        _raise_with_detail(resp)
    return _parse_v1_response(resp.json(), meta["scale"])


def fetch_series_since(series_key: str, api_key: str, since: pd.Timestamp) -> pd.DataFrame:
    """Fetch only weeks after `since` — used for incremental cache updates."""
    meta = SERIES[series_key]
    resp = requests.get(
        f"{_V2_SERIESID_URL}{meta['id']}",
        params={"api_key": api_key, "start": since.strftime("%Y%m%d")},
        timeout=30,
    )
    if not resp.ok:
        _raise_with_detail(resp)
    return _parse_v1_response(resp.json(), meta["scale"])


def _fetch_padd(params: list) -> pd.DataFrame:
    resp = requests.get(_V2_STOCKS_URL, params=params, timeout=30)
    if not resp.ok:
        _raise_with_detail(resp)
    records = resp.json().get("response", {}).get("data", [])
    if not records:
        return pd.DataFrame(columns=["date", "area", "value"])
    df = pd.DataFrame(records)
    df = df.rename(columns={"period": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce") / 1_000
    area_names = {v: k for k, v in PADD_AREAS.items()}
    df["area"] = df["duoarea"].map(area_names)
    return (
        df[["date", "area", "value"]]
        .dropna()
        .sort_values(["area", "date"])
        .reset_index(drop=True)
    )


def fetch_padd_stocks(api_key: str) -> pd.DataFrame:
    """Fetch full weekly crude stocks history for all five PADDs."""
    params = [
        ("api_key",            api_key),
        ("frequency",          "weekly"),
        ("data[0]",            "value"),
        ("facets[product][]",  "EPC0"),
        ("sort[0][column]",    "period"),
        ("sort[0][direction]", "asc"),
        ("length",             "5000"),
    ]
    for code in PADD_AREAS.values():
        params.append(("facets[duoarea][]", code))
    return _fetch_padd(params)


def fetch_padd_stocks_since(api_key: str, since: pd.Timestamp) -> pd.DataFrame:
    """Fetch only PADD stock weeks after `since` — used for incremental cache updates."""
    params = [
        ("api_key",            api_key),
        ("frequency",          "weekly"),
        ("data[0]",            "value"),
        ("facets[product][]",  "EPC0"),
        ("sort[0][column]",    "period"),
        ("sort[0][direction]", "asc"),
        ("length",             "500"),
        ("start",              since.strftime("%Y-%m-%d")),
    ]
    for code in PADD_AREAS.values():
        params.append(("facets[duoarea][]", code))
    return _fetch_padd(params)
