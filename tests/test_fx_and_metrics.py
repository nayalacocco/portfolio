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
