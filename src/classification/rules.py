from __future__ import annotations

import numpy as np
import pandas as pd


EXTERNAL_INFLOW = {
    "recibo de cobro": "ARS",
    "recibo de cobro dolares": "USD",
    "recibo de cobro ext": "EXT",
}

EXTERNAL_OUTFLOW = {
    "orden de pago": "ARS",
    "orden de pago usd": "USD",
}


INTERNAL_KEYWORDS = {
    "compra",
    "venta",
    "senebi",
    "dólar mep",
    "dolar mep",
    "rescate",
    "rentas",
    "amortizaciones",
    "dividendos",
    "comisiones",
    "iva",
}


def classify_movements(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    tm = out["tipoMovimientoNorm"]

    out["flow_class"] = np.where(
        tm.isin(EXTERNAL_INFLOW),
        "external_inflow",
        np.where(tm.isin(EXTERNAL_OUTFLOW), "external_outflow", "internal"),
    )

    unclassified_mask = (out["flow_class"] == "internal") & (~tm.apply(_looks_internal))
    warnings = out.loc[unclassified_mask, ["fechaLiquidacion", "tipoMovimiento", "moneda", "monto"]]
    return out, warnings


def _looks_internal(value: str) -> bool:
    return any(token in value for token in INTERNAL_KEYWORDS)
