from __future__ import annotations

import pandas as pd


def fmt_pct(x):
    return "-" if pd.isna(x) else f"{x:.2%}"


def fmt_usd(x):
    return "-" if pd.isna(x) else f"USD {x:,.2f}"
