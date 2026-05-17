import pandas as pd


def build_seasonality_data(df: pd.DataFrame, years: list = None) -> pd.DataFrame:
    """Map weekly data onto a common year (2000) for year-over-year overlay.

    Returns df with added 'year' and 'plot_date' columns.
    """
    df = df.copy()
    df["year"] = df["date"].dt.year
    if years:
        df = df[df["year"].isin(years)]
    df["plot_date"] = df["date"].apply(lambda d: d.replace(year=2000))
    return df.sort_values(["year", "plot_date"]).reset_index(drop=True)


def build_5yr_avg(df: pd.DataFrame, current_year: int) -> pd.DataFrame:
    """Compute per-week mean over the five calendar years before current_year.

    Returns df with 'plot_date' and 'value' columns for charting alongside
    a seasonality chart.
    """
    hist = df[
        (df["date"].dt.year >= current_year - 5) &
        (df["date"].dt.year < current_year)
    ].copy()
    if hist.empty:
        return pd.DataFrame(columns=["plot_date", "value"])
    hist["plot_date"] = hist["date"].apply(lambda d: d.replace(year=2000))
    avg = hist.groupby("plot_date")["value"].mean().reset_index(name="value")
    return avg.sort_values("plot_date").reset_index(drop=True)


def build_timeline_data(df: pd.DataFrame, years: list = None) -> pd.DataFrame:
    """Filter to selected years (used as a date-range crop for timeline charts)."""
    df = df.copy()
    if years:
        df = df[df["date"].dt.year.isin(years)]
    return df.sort_values("date").reset_index(drop=True)


def build_padd_timeline(padd_df: pd.DataFrame, years: list = None) -> pd.DataFrame:
    """Prepare PADD breakdown data for a multi-line or stacked area timeline."""
    df = padd_df.copy()
    if years:
        df = df[df["date"].dt.year.isin(years)]
    return df.sort_values(["area", "date"]).reset_index(drop=True)
