import pandas as pd


def _iso_week_to_plot_date(week: int) -> pd.Timestamp:
    """Return a consistent x-axis date for a given ISO week number, anchored to year 2000."""
    return pd.Timestamp.fromisocalendar(2000, int(week), 5)  # Friday of that week


def build_seasonality_data(df: pd.DataFrame, years: list = None) -> pd.DataFrame:
    """Map weekly data onto a common year (2000) for year-over-year overlay.

    Uses ISO week number so the same week aligns across years regardless of
    the exact calendar date (EIA weekly data doesn't fall on the same date each year).
    Returns df with added 'year' and 'plot_date' columns.
    """
    df = df.copy()
    df["year"] = df["date"].dt.year
    if years:
        df = df[df["year"].isin(years)]
    df["plot_date"] = df["date"].dt.isocalendar()["week"].apply(_iso_week_to_plot_date)
    return df.sort_values(["year", "plot_date"]).reset_index(drop=True)


def build_5yr_avg(df: pd.DataFrame, current_year: int) -> pd.DataFrame:
    """Compute per-week mean over the five calendar years before current_year.

    Groups by ISO week number so that the same seasonal week is averaged across
    years even when EIA reports fall on different calendar dates.
    Returns df with 'plot_date' and 'value' columns for charting alongside
    a seasonality chart.
    """
    hist = df[
        (df["date"].dt.year >= current_year - 5) &
        (df["date"].dt.year < current_year)
    ].copy()
    if hist.empty:
        return pd.DataFrame(columns=["plot_date", "value"])
    hist["iso_week"] = hist["date"].dt.isocalendar()["week"]
    avg = hist.groupby("iso_week")["value"].mean().reset_index(name="value")
    avg["plot_date"] = avg["iso_week"].apply(_iso_week_to_plot_date)
    return avg.sort_values("plot_date").drop(columns="iso_week").reset_index(drop=True)


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
