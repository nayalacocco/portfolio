from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MetricsResult:
    valor_inicial_usd: float
    valor_final_usd: float
    flujos_entrada_usd: float
    flujos_salida_usd: float
    flujo_neto_usd: float
    resultado_neto_usd: float
    retorno_nominal: float
    tasa_efectiva_periodo: float
    tasa_efectiva_anual: float
    tir_usd: float | None


def xnpv(rate: float, cash_flows: list[tuple[date, float]]) -> float:
    t0 = cash_flows[0][0]
    return sum(cf / ((1 + rate) ** (((d - t0).days) / 365.0)) for d, cf in cash_flows)


def xirr(cash_flows: list[tuple[date, float]], max_iter: int = 100, tol: float = 1e-7) -> float | None:
    if not cash_flows:
        return None
    values = [v for _, v in cash_flows]
    if not (any(v < 0 for v in values) and any(v > 0 for v in values)):
        return None

    low, high = -0.9999, 10.0
    f_low = xnpv(low, cash_flows)
    f_high = xnpv(high, cash_flows)
    if f_low * f_high > 0:
        return None

    for _ in range(max_iter):
        mid = (low + high) / 2
        f_mid = xnpv(mid, cash_flows)
        if abs(f_mid) < tol:
            return mid
        if f_low * f_mid < 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid
    return mid


def compute_metrics(
    start_value_usd: float,
    end_value_usd: float,
    external_flows: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> MetricsResult:
    inflow = float(external_flows.loc[external_flows["flow_class"] == "external_inflow", "amount_usd_mep"].sum())
    outflow = float(external_flows.loc[external_flows["flow_class"] == "external_outflow", "amount_usd_mep"].sum())
    net_flow = inflow - outflow

    result = end_value_usd - start_value_usd - inflow + outflow
    nominal = (end_value_usd + outflow - inflow) / start_value_usd - 1 if start_value_usd else np.nan
    period_rate = result / start_value_usd if start_value_usd else np.nan

    days = (end_date - start_date).days
    annual = (1 + period_rate) ** (365 / days) - 1 if days > 0 and pd.notna(period_rate) and period_rate > -1 else np.nan

    cash_flows = [(start_date, -start_value_usd)]
    cash_flows.extend(
        (r.fechaLiquidacion, -r.amount_usd_mep if r.flow_class == "external_inflow" else r.amount_usd_mep)
        for r in external_flows.itertuples()
    )
    cash_flows.append((end_date, end_value_usd))
    irr = xirr(cash_flows)

    return MetricsResult(
        valor_inicial_usd=start_value_usd,
        valor_final_usd=end_value_usd,
        flujos_entrada_usd=inflow,
        flujos_salida_usd=outflow,
        flujo_neto_usd=net_flow,
        resultado_neto_usd=result,
        retorno_nominal=nominal,
        tasa_efectiva_periodo=period_rate,
        tasa_efectiva_anual=annual,
        tir_usd=irr,
    )
