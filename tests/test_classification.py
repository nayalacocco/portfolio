import pandas as pd

from src.classification.rules import classify_movements


def test_external_classification():
    df = pd.DataFrame(
        {
            "fechaLiquidacion": [pd.Timestamp("2024-01-01").date()] * 3,
            "tipoMovimiento": ["Recibo de Cobro", "Orden de Pago USD", "Compra"],
            "tipoMovimientoNorm": ["recibo de cobro", "orden de pago usd", "compra"],
            "moneda": ["ARS", "USD", "ARS"],
            "monto": [1000, 50, 10],
        }
    )
    out, warns = classify_movements(df)
    assert list(out["flow_class"]) == ["external_inflow", "external_outflow", "internal"]
    assert warns.empty
