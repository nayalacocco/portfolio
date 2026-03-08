import pandas as pd
import pytest

from src.ingest.parsing import IngestError, load_inputs


def test_load_inputs_maps_real_movements_columns(monkeypatch):
    movements_df = pd.DataFrame(
        {
            "fechaEjecucion": ["2024-01-01"],
            "fechaLiquidacion": ["2024-01-02"],
            "tipoOperacion": ["Compra"],
            "instrumento": ["AL30"],
            "moneda": ["ARS"],
            "cantidad": [10],
            "precio": [1000],
            "montoBruto": [10000],
            "comision": [100],
            "iva": [21],
            "otros": [0],
            "total": [-10121],
        }
    )
    fx_df = pd.DataFrame({"fecha": ["2024-01-02"], "tc_mep": [1100]})
    position_df = pd.DataFrame(
        {"ticker": ["AL30"], "instrumento": ["AL30"], "cantidad": [10], "monto": [10000]}
    )

    frames = iter([movements_df, fx_df, position_df])
    monkeypatch.setattr(pd, "read_excel", lambda _file: next(frames))

    out = load_inputs("movements.xlsx", "fx.xlsx", "position.xlsx")

    assert "date" in out.movements.columns
    assert "tipoMovimiento" in out.movements.columns
    assert "monto" in out.movements.columns
    assert out.movements.loc[0, "date"] == "2024-01-02"
    assert out.movements.loc[0, "fechaLiquidacion"] == "2024-01-02"
    assert out.movements.loc[0, "tipoMovimiento"] == "Compra"
    assert out.movements.loc[0, "monto"] == -10121


def test_load_inputs_requires_real_movements_source_columns(monkeypatch):
    movements_df = pd.DataFrame(
        {
            "fechaLiquidacion": ["2024-01-02"],
            "moneda": ["ARS"],
            "cantidad": [10],
        }
    )
    fx_df = pd.DataFrame({"fecha": ["2024-01-02"], "tc_mep": [1100]})
    position_df = pd.DataFrame(
        {"ticker": ["AL30"], "instrumento": ["AL30"], "cantidad": [10], "monto": [10000]}
    )

    frames = iter([movements_df, fx_df, position_df])
    monkeypatch.setattr(pd, "read_excel", lambda _file: next(frames))

    with pytest.raises(IngestError, match="movimientos"):
        load_inputs("movements.xlsx", "fx.xlsx", "position.xlsx")
