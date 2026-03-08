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


def test_load_inputs_detects_fx_table_and_normalizes_schema(monkeypatch, capsys):
    movements_df = pd.DataFrame(
        {
            "fechaLiquidacion": ["2024-01-02"],
            "tipoOperacion": ["Compra"],
            "total": [-10121],
            "moneda": ["ARS"],
        }
    )
    fx_raw_df = pd.DataFrame(
        [
            ["Reporte FX", None, None],
            ["Generado", "hoy", None],
            ["Fecha", "TC MEP", "TC Cable"],
            ["2024-01-02", "1.100,50", "1.120,00"],
            ["2024-01-03", None, "1.130,00"],
            ["2024-01-04", "1.140,00", "1.150,00"],
        ]
    )
    position_df = pd.DataFrame(
        {"ticker": ["AL30"], "instrumento": ["AL30"], "cantidad": [10], "monto": [10000]}
    )

    def fake_read_excel(_file, **kwargs):
        if kwargs.get("header", "default") is None:
            return fx_raw_df
        if _file == "movements.xlsx":
            return movements_df
        if _file == "position.xlsx":
            return position_df
        raise AssertionError(f"Unexpected call: {_file}, {kwargs}")

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    out = load_inputs("movements.xlsx", "fx.xlsx", "position.xlsx")

    assert list(out.fx.columns) == ["fecha", "tc_mep", "tc_cable"]
    assert out.fx["fecha"].astype(str).tolist() == ["2024-01-02", "2024-01-03", "2024-01-04"]
    assert out.fx["tc_mep"].tolist() == [1100.5, 1100.5, 1140.0]
    assert out.fx["tc_cable"].tolist() == [1120.0, 1130.0, 1150.0]

    captured = capsys.readouterr()
    assert "Preview FX normalizado:" in captured.out
