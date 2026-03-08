from __future__ import annotations

from datetime import date, datetime
import re

import pandas as pd


ISO_LIKE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$")
DAY_FIRST_RE = re.compile(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}$")


def parse_official_date(value: object) -> pd.Timestamp:
    """Parse dates with explicit, non-ambiguous rules for the project."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return value.normalize()

    if isinstance(value, datetime):
        return pd.Timestamp(value).normalize()

    if isinstance(value, date):
        return pd.Timestamp(value)

    txt = str(value).strip()
    if not txt:
        return pd.NaT

    if ISO_LIKE_RE.match(txt):
        normalized = txt.replace("/", "-")
        return pd.to_datetime(normalized, format="%Y-%m-%d", errors="coerce")

    if DAY_FIRST_RE.match(txt):
        normalized = txt.replace("/", "-")
        return pd.to_datetime(normalized, format="%d-%m-%Y", errors="coerce")

    return pd.NaT


def normalize_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.map(parse_official_date), errors="coerce")
