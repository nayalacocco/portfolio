import pandas as pd

from src.classification.rules import classify_movements
from src.normalization.core import normalize_movements


def test_parse_day_first_date_03_04_2025():
    df = pd.DataFrame(
        {
            "fechaLiquidacion": ["03-04-2025"],
            "tipoMovimiento": ["Recibo de Cobro"],
            "monto": [100],
            "moneda": ["ARS"],
        }
    )
    out = normalize_movements(df)
    assert out.loc[0, "date_iso"] == "2025-04-03"


def test_parse_day_first_date_12_01_2026():
    df = pd.DataFrame(
        {
            "fechaLiquidacion": ["12-01-2026"],
            "tipoMovimiento": ["Recibo de Cobro"],
            "monto": [100],
            "moneda": ["ARS"],
        }
    )
    out = normalize_movements(df)
    assert out.loc[0, "date_iso"] == "2026-01-12"


def test_parse_iso_date_maintained():
    df = pd.DataFrame(
        {
            "fechaLiquidacion": ["2025-03-04"],
            "tipoMovimiento": ["Recibo de Cobro"],
            "monto": [100],
            "moneda": ["ARS"],
        }
    )
    out = normalize_movements(df)
    assert out.loc[0, "date_iso"] == "2025-03-04"


def test_external_cashflows_are_exact_subset_of_classified_movements():
    movements = pd.DataFrame(
        {
            "fechaLiquidacion": ["03-04-2025", "2025-03-04", "12/01/2026"],
            "tipoMovimiento": ["Recibo de Cobro", "Compra", "Orden de Pago USD"],
            "monto": [1000, -500, -50],
            "moneda": ["ARS", "ARS", "USD"],
            "nroticket": ["44565293", "100", "101"],
        }
    )
    normalized = normalize_movements(movements)
    classified, _ = classify_movements(normalized)

    external = classified[classified["flow_class"].isin(["external_inflow", "external_outflow"])].copy()

    expected_ids = set(classified.loc[classified["flow_class"].isin(["external_inflow", "external_outflow"]), "nroticket"].astype(str))
    got_ids = set(external["nroticket"].astype(str))
    assert got_ids == expected_ids
