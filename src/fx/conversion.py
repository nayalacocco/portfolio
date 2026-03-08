from __future__ import annotations

import pandas as pd


class FXError(ValueError):
    """Raised when FX conversion is not possible."""


class FXSeries:
    def __init__(self, fx_df: pd.DataFrame):
        self.fx = fx_df.sort_values("fecha").copy()

    def mep_on(self, dt):
        hits = self.fx[self.fx["fecha"] <= dt]
        if hits.empty:
            raise FXError(f"No existe TC MEP para fecha {dt} ni fechas anteriores.")
        return float(hits.iloc[-1]["tc_mep"])


def amount_to_usd_mep(amount: float, currency: str, tc_mep: float) -> float:
    ccy = str(currency).upper().strip()
    if ccy == "ARS":
        return amount / tc_mep
    if ccy in {"USD", "EXT"}:
        return amount
    raise FXError(f"Moneda no soportada: {currency}")
