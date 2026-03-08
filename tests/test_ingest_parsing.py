import io

import pandas as pd
import pytest

from src.ingest.parsing import IngestError, load_inputs


def _excel_bytes_from_sheet(raw_rows: list[list[object]], sheet_name: str = "Data"):
    buffer = io.BytesIO()
    pd.DataFrame(raw_rows).to_excel(buffer, index=False, header=False, sheet_name=sheet_name)
    buffer.seek(0)
    return buffer


def test_load_inputs_detects_headers_aliases_and_normalizes_position():
    movements_file = _excel_bytes_from_sheet(
        [
            ["reporte", None, None, None],
            ["fecha liquidación", "tipo operación", "total", "moneda"],
            ["2024-01-02", "Compra", "-10.121,50", "ARS"],
        ],
        sheet_name="Movs",
    )
    fx_file = _excel_bytes_from_sheet(
        [
            ["Reporte FX", None, None],
            ["Fecha", "TC MEP", "TC Cable"],
            ["2024-01-02", "1.100,50", "1.120,00"],
            ["2024-01-03", None, "1.130,00"],
        ],
        sheet_name="FX",
    )
    position_file = _excel_bytes_from_sheet(
        [
            ["Posición valorizada", None, None, None],
            [" Símbolo ", "Descripción", "Nominales", "Valuación"],
            ["AL30", "AL30 GD", "100", "150.000,25"],
            ["TOTAL", "", "", ""],
        ],
        sheet_name="Posicion",
    )

    out = load_inputs(movements_file, fx_file, position_file)

    assert set(["ticker", "instrumento", "cantidad", "monto"]).issubset(out.position.columns)
    assert out.position.shape[0] == 1
    assert out.position.loc[0, "ticker"] == "AL30"
    assert out.position.loc[0, "cantidad"] == 100
    assert out.position.loc[0, "monto"] == 150000.25

    assert out.diagnostics["posicion"].sheet_name == "Posicion"
    assert out.diagnostics["posicion"].header_row == 1
    assert "ticker" in out.diagnostics["posicion"].normalized_columns
    assert out.diagnostics["posicion"].aliases_applied["ticker"].strip() == "Símbolo"


def test_load_inputs_missing_position_columns_raises():
    movements_file = _excel_bytes_from_sheet(
        [
            ["fechaLiquidacion", "tipoOperacion", "total", "moneda"],
            ["2024-01-02", "Compra", "-100", "ARS"],
        ]
    )
    fx_file = _excel_bytes_from_sheet([["fecha", "tc_mep"], ["2024-01-02", "1100"]])
    position_file = _excel_bytes_from_sheet(
        [
            ["reporte", None],
            ["descripcion", "valuacion"],
            ["AL30", "100"],
        ]
    )

    with pytest.raises(IngestError, match="posicion"):
        load_inputs(movements_file, fx_file, position_file)
