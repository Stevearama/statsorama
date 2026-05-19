"""
Bulk data refresh from EIA PET.zip download.

Use this to initially populate (or fully refresh) all parquet cache files
from EIA's bulk petroleum data download.  Much faster than individual API
calls — one ~200-300 MB ZIP contains all ~12,000 petroleum series.

Usage:
    python refresh_bulk.py              # refresh all series in SERIES dict
    python refresh_bulk.py --list       # show which series are in SERIES dict

When to run:
    • First time setup (seeds all parquet files)
    • If you add new series to SERIES and want historical data immediately
    • The app's incremental cache (data_cache.py) handles weekly updates after this

EIA bulk download info:  https://www.eia.gov/opendata/bulk/
File format: ZIP containing one or more NDJSON files.
Each line is one complete series:
    {"series_id": "PET.WCRSTUS1.W", "name": "...", "units": "...",
     "f": "W", "data": [["2024-01-05", 412345], ["2024-01-12", 415678], ...]}
"""

import io
import json
import sys
import zipfile

import pandas as pd
import requests

from data_cache import CACHE_DIR, _save
from eia_data import SERIES

BULK_URL = "https://www.eia.gov/opendata/bulk/PET.zip"


def _list_series() -> None:
    print("Series registered in SERIES dict:")
    for key, meta in SERIES.items():
        p = CACHE_DIR / f"{key}.parquet"
        status = f"cached ({pd.read_parquet(p)['date'].max().date()})" if p.exists() else "not cached"
        print(f"  {key:22s}  {meta['id']:35s}  [{status}]")


def refresh_from_bulk(dry_run: bool = False) -> None:
    # Build reverse lookup: series_id (from EIA) → our cache key
    id_to_key = {meta["id"]: key for key, meta in SERIES.items()}

    print(f"Downloading {BULK_URL}")
    print("(This is ~200-300 MB — may take a minute on slow connections)")

    resp = requests.get(BULK_URL, timeout=600, stream=True)
    resp.raise_for_status()

    chunks = []
    total  = 0
    for chunk in resp.iter_content(chunk_size=1024 * 1024):
        chunks.append(chunk)
        total += len(chunk)
        print(f"\r  {total / 1e6:.1f} MB downloaded", end="", flush=True)
    print()

    raw_zip = b"".join(chunks)
    print(f"Download complete ({total / 1e6:.1f} MB).  Parsing ZIP...")

    CACHE_DIR.mkdir(exist_ok=True)

    found: dict[str, bool] = {key: False for key in SERIES}

    with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
        names = z.namelist()
        print(f"  ZIP contains {len(names)} file(s): {names}")

        for fname in names:
            print(f"  Scanning {fname} ...")
            with z.open(fname) as f:
                for line_bytes in f:
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    sid = obj.get("series_id", "")
                    if sid not in id_to_key:
                        continue

                    key  = id_to_key[sid]
                    meta = SERIES[key]
                    raw  = obj.get("data", [])
                    if not raw:
                        continue

                    df = pd.DataFrame(raw, columns=["date", "value"])
                    df["date"]  = pd.to_datetime(df["date"])
                    df["value"] = pd.to_numeric(df["value"], errors="coerce")
                    if meta.get("scale"):
                        df["value"] = df["value"] / meta["scale"]
                    df = df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)

                    if not dry_run:
                        _save(key, df)
                    found[key] = True

                    date_range = f"{df['date'].min().date()} – {df['date'].max().date()}"
                    print(f"  OK {key:22s}  {len(df):5d} rows  ({date_range})")

    # Report anything missing from the bulk file
    missing = [k for k, v in found.items() if not v]
    if missing:
        print(f"\nNot found in bulk file ({len(missing)} series):")
        for k in missing:
            print(f"  {k:22s}  {SERIES[k]['id']}")
        print("These will be fetched individually from the API on first app load.")
    else:
        print("\nAll series found and cached.")

    print(f"\nParquet files written to: {CACHE_DIR.resolve()}")


if __name__ == "__main__":
    if "--list" in sys.argv:
        _list_series()
    elif "--dry-run" in sys.argv:
        refresh_from_bulk(dry_run=True)
    else:
        refresh_from_bulk()
