from __future__ import annotations

import pandas as pd


class NormalizationError(ValueError):
    """Raised when a required normalization step fails."""


def normalize_movements(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["fechaLiquidacion"] = pd.to_datetime(out["fechaLiquidacion"], errors="coerce").dt.date
    if out["fechaLiquidacion"].isna().any():
        raise NormalizationError("Hay fechas de liquidación inválidas en movimientos.")

    out["tipoMovimiento"] = out["tipoMovimiento"].astype(str).str.strip()
    out["tipoMovimientoNorm"] = out["tipoMovimiento"].str.lower()
    out["moneda"] = out["moneda"].astype(str).str.strip().str.upper()
    out["monto"] = pd.to_numeric(out["monto"], errors="coerce")
    if out["monto"].isna().any():
        raise NormalizationError("Hay montos inválidos en movimientos.")

    if "cantidad" in out.columns:
        out["cantidad"] = pd.to_numeric(out["cantidad"], errors="coerce")
    if "precio" in out.columns:
        out["precio"] = pd.to_numeric(out["precio"], errors="coerce")

    return out


def normalize_fx(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce").dt.date
    out["tc_mep"] = pd.to_numeric(out["tc_mep"], errors="coerce")
    if "tc_cable" in out.columns:
        out["tc_cable"] = pd.to_numeric(out["tc_cable"], errors="coerce")

    bad = out["fecha"].isna() | out["tc_mep"].isna()
    if bad.any():
        raise NormalizationError("Hay filas inválidas en histórico FX.")

    out = out.sort_values("fecha").drop_duplicates(subset=["fecha"], keep="last")
    return out.reset_index(drop=True)


def normalize_position(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ticker"] = out["ticker"].astype(str).str.strip()
    out["instrumento"] = out["instrumento"].astype(str).str.strip()
    out["cantidad"] = pd.to_numeric(out["cantidad"], errors="coerce")
    out["monto"] = pd.to_numeric(out["monto"], errors="coerce")

    if out[["cantidad", "monto"]].isna().any().any():
        raise NormalizationError("Hay datos inválidos en posición valorizada.")

    return out
