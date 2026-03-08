import pandas as pd

from src.fx.conversion import FXSeries, amount_to_usd_mep
from src.metrics.performance import compute_metrics


def test_fx_conversion_rules():
    assert amount_to_usd_mep(1000, "ARS", 1000) == 1
    assert amount_to_usd_mep(5, "USD", 1200) == 5
    assert amount_to_usd_mep(5, "EXT", 1200) == 5


def test_metrics_basic():
    flows = pd.DataFrame(
        {
            "fechaLiquidacion": [pd.Timestamp("2024-01-10").date(), pd.Timestamp("2024-02-10").date()],
            "flow_class": ["external_inflow", "external_outflow"],
            "amount_usd_mep": [10.0, 3.0],
        }
    )
    res = compute_metrics(
        start_value_usd=100,
        end_value_usd=120,
        external_flows=flows,
        start_date=pd.Timestamp("2024-01-01").date(),
        end_date=pd.Timestamp("2024-03-01").date(),
    )
    assert round(res.resultado_neto_usd, 8) == 13.0


def test_fx_lookup_asof():
    fx = FXSeries(
        pd.DataFrame({
            "fecha": [pd.Timestamp("2024-01-01").date(), pd.Timestamp("2024-01-03").date()],
            "tc_mep": [1000, 1100],
        })
    )
    assert fx.mep_on(pd.Timestamp("2024-01-02").date()) == 1000


def test_metrics_irr_uses_investor_sign_convention_with_account_signs():
    flows = pd.DataFrame(
        {
            "fechaLiquidacion": [
                pd.Timestamp("2024-01-10").date(),
                pd.Timestamp("2024-02-10").date(),
            ],
            "flow_class": ["external_inflow", "external_outflow"],
            # Signo contable de cuenta: entrada positiva, salida negativa
            "amount_usd_mep": [100.0, -20.0],
        }
    )

    res = compute_metrics(
        start_value_usd=200,
        end_value_usd=350,
        external_flows=flows,
        start_date=pd.Timestamp("2024-01-01").date(),
        end_date=pd.Timestamp("2024-03-01").date(),
    )

    # Resultado económico = Vf - Vi - aportes + retiros
    assert round(res.resultado_neto_usd, 8) == 70.0
    # Flujo neto contable conserva signo de cuenta
    assert round(res.flujo_neto_usd, 8) == 80.0
    assert res.tir_usd is not None
