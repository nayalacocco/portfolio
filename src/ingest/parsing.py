from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd


class IngestError(ValueError):
    """Raised when an input file cannot be parsed into required columns."""


@dataclass(frozen=True)
class InputFrames:
    movements: pd.DataFrame
    fx: pd.DataFrame
    position: pd.DataFrame


REQUIRED_MOVEMENT_COLUMNS = {"fechaLiquidacion", "tipoMovimiento", "moneda", "monto"}
REQUIRED_FX_COLUMNS = {"fecha", "tc_mep"}
REQUIRED_POSITION_COLUMNS = {"ticker", "instrumento", "cantidad", "monto"}

ALIASES: Dict[str, str] = {
    "fecha liquidacion": "fechaLiquidacion",
    "fecha_liquidacion": "fechaLiquidacion",
    "fecha ejecución": "fechaEjecucion",
    "fecha ejecucion": "fechaEjecucion",
    "tipo movimiento": "tipoMovimiento",
    "tipo_movimiento": "tipoMovimiento",
    "movimiento": "tipoMovimiento",
    "currency": "moneda",
    "importe": "monto",
    "valor": "monto",
    "tc mep": "tc_mep",
    "mep": "tc_mep",
    "tc cable": "tc_cable",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for c in df.columns:
        key = str(c).strip()
        key_l = key.lower()
        mapping[c] = ALIASES.get(key_l, key)
    return df.rename(columns=mapping)


def _read_excel(file) -> pd.DataFrame:
    try:
        df = pd.read_excel(file)
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"No se pudo leer el archivo Excel: {exc}") from exc
    return _normalize_columns(df)


def _validate_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise IngestError(
            f"El archivo '{name}' no contiene columnas requeridas: {sorted(missing)}"
        )


def load_inputs(movements_file, fx_file, position_file) -> InputFrames:
    movements = _read_excel(movements_file)
    fx = _read_excel(fx_file)
    position = _read_excel(position_file)

    _validate_columns(movements, REQUIRED_MOVEMENT_COLUMNS, "movimientos")
    _validate_columns(fx, REQUIRED_FX_COLUMNS, "fx")
    _validate_columns(position, REQUIRED_POSITION_COLUMNS, "posicion")

    return InputFrames(movements=movements, fx=fx, position=position)
