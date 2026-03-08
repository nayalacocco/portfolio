from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fx.conversion import FXSeries, amount_to_usd_mep


@dataclass(frozen=True)
class PeriodInputs:
    start_date: object
    end_date: object
    start_value_usd: float
    end_value_usd: float


def current_value_usd_from_position(position_df: pd.DataFrame, fx: FXSeries, end_date) -> float:
    total_ars = float(position_df["monto"].sum())
    tc_mep = fx.mep_on(end_date)
    return total_ars / tc_mep


def infer_start_value_usd(
    manual_value: float | None,
    manual_ccy: str,
    start_date,
    fx: FXSeries,
) -> float:
    if manual_value is None:
        return 0.0
    if manual_ccy.upper() == "ARS":
        return manual_value / fx.mep_on(start_date)
    return float(manual_value)


def movement_amount_usd(row: pd.Series, fx: FXSeries) -> float:
    tc = fx.mep_on(row["fechaLiquidacion"])
    return amount_to_usd_mep(float(row["monto"]), row["moneda"], tc)


def instrument_cost_basis(movements_df: pd.DataFrame, position_df: pd.DataFrame, fx: FXSeries) -> pd.DataFrame:
    required = {"ticker", "cantidad", "monto", "tipoMovimientoNorm", "fechaLiquidacion", "moneda"}
    if not required.issubset(set(movements_df.columns)):
        base = position_df[["ticker", "instrumento", "cantidad", "monto"]].copy()
        base["avg_cost_usd"] = np.nan
        base["implicit_pnl_usd"] = np.nan
        base["itm_pct"] = np.nan
        return base

    df = movements_df.copy()
    df = df[df["ticker"].notna()]
    df["is_buy"] = df["tipoMovimientoNorm"].str.contains("compra", na=False)
    df["is_sell"] = df["tipoMovimientoNorm"].str.contains("venta", na=False)
    df["amount_usd"] = df.apply(lambda r: movement_amount_usd(r, fx), axis=1)

    buy_grp = (
        df[df["is_buy"]]
        .groupby("ticker", as_index=False)
        .agg(buy_qty=("cantidad", "sum"), buy_amount_usd=("amount_usd", "sum"))
    )
    pos = position_df[["ticker", "instrumento", "cantidad", "monto"]].copy()
    out = pos.merge(buy_grp, on="ticker", how="left")
    out["avg_cost_usd"] = out["buy_amount_usd"] / out["buy_qty"]
    out["current_px_usd"] = np.where(out["cantidad"] != 0, out["monto"] / out["cantidad"], np.nan)
    # monto de posición está en ARS (input), por lo tanto PnL implícito queda limitado para MVP.
    out["implicit_pnl_note"] = "pendiente conversion puntual por instrumento a USD MEP"
    out["implicit_pnl_usd"] = np.nan
    out["itm_pct"] = np.where(
        out["avg_cost_usd"].notna() & out["current_px_usd"].notna() & (out["current_px_usd"] > out["avg_cost_usd"]),
        1.0,
        0.0,
    )
    return out
