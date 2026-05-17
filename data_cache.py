"""Persistent parquet cache for EIA series data.

On first call the full history is fetched from the API and saved to data/.
On subsequent calls only weeks newer than the latest saved date are fetched,
then appended — so the API round-trip is tiny after the first run.
"""

from pathlib import Path

import pandas as pd

from eia_data import fetch_series, fetch_padd_stocks, fetch_series_since, fetch_padd_stocks_since

CACHE_DIR = Path(__file__).parent / "data"


def _path(key: str) -> Path:
    return CACHE_DIR / f"{key}.parquet"


def _load(key: str) -> pd.DataFrame | None:
    p = _path(key)
    return pd.read_parquet(p) if p.exists() else None


def _save(key: str, df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    df.to_parquet(_path(key), index=False)


def get_series_cached(series_key: str, api_key: str) -> pd.DataFrame:
    """Return full history for a named series, updating the local cache."""
    cached = _load(series_key)

    if cached is None:
        df = fetch_series(series_key, api_key)
        _save(series_key, df)
        return df

    latest = pd.Timestamp(cached["date"].max())
    new = fetch_series_since(series_key, api_key, latest)
    if new.empty:
        return cached

    new_rows = new[new["date"] > latest]
    if new_rows.empty:
        return cached

    combined = pd.concat([cached, new_rows], ignore_index=True).sort_values("date").reset_index(drop=True)
    _save(series_key, combined)
    return combined


def get_padd_cached(api_key: str) -> pd.DataFrame:
    """Return full PADD stocks history, updating the local cache."""
    cached = _load("padd_stocks")

    if cached is None:
        df = fetch_padd_stocks(api_key)
        _save("padd_stocks", df)
        return df

    latest = pd.Timestamp(cached["date"].max())
    new = fetch_padd_stocks_since(api_key, latest)
    if new.empty:
        return cached

    new_rows = new[new["date"] > latest]
    if new_rows.empty:
        return cached

    combined = pd.concat([cached, new_rows], ignore_index=True).sort_values(["area", "date"]).reset_index(drop=True)
    _save("padd_stocks", combined)
    return combined
