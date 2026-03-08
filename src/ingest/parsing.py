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


REQUIRED_MOVEMENT_SOURCE_COLUMNS = {"fechaLiquidacion", "tipoOperacion", "total", "moneda"}
REQUIRED_FX_COLUMNS = {"fecha", "tc_mep"}
REQUIRED_POSITION_COLUMNS = {"ticker", "instrumento", "cantidad", "monto"}

FX_COLUMN_ALIASES: Dict[str, list[str]] = {
    "fecha": ["fecha", "Fecha"],
    "tc_mep": ["tc_mep", "TC MEP", "tc mep"],
    "tc_cable": ["tc_cable", "TC Cable", "tc cable"],
}

MOVEMENT_COLUMN_MAPPING: Dict[str, str] = {
    "fechaLiquidacion": "date",
    "tipoOperacion": "tipoMovimiento",
    "total": "monto",
    "moneda": "moneda",
    "instrumento": "instrumento",
    "cantidad": "cantidad",
    "precio": "precio",
}

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


def _normalize_column_name(value) -> str:
    return "_".join(str(value).strip().lower().split())


def _to_numeric_local(series: pd.Series) -> pd.Series:
    def _convert(value):
        if pd.isna(value):
            return value
        if isinstance(value, (int, float)):
            return value

        txt = str(value).strip().replace(" ", "")
        if not txt:
            return pd.NA

        if "," in txt and "." in txt:
            if txt.rfind(",") > txt.rfind("."):
                txt = txt.replace(".", "").replace(",", ".")
            else:
                txt = txt.replace(",", "")
        elif "," in txt:
            txt = txt.replace(".", "").replace(",", ".")

        return txt

    return pd.to_numeric(series.map(_convert), errors="coerce")


def _read_excel(file) -> pd.DataFrame:
    try:
        df = pd.read_excel(file)
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"No se pudo leer el archivo Excel: {exc}") from exc
    return _normalize_columns(df)


def _read_excel_with_reset(file, **kwargs) -> pd.DataFrame:
    if hasattr(file, "seek"):
        file.seek(0)
    return pd.read_excel(file, **kwargs)


def _read_fx_excel(file) -> pd.DataFrame:
    try:
        raw = _read_excel_with_reset(file, header=None)
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"No se pudo leer el archivo Excel: {exc}") from exc

    alias_to_canonical = {
        _normalize_column_name(alias): canonical
        for canonical, aliases in FX_COLUMN_ALIASES.items()
        for alias in aliases
    }

    header_row_idx = None
    for idx in range(len(raw)):
        row_values = {_normalize_column_name(v) for v in raw.iloc[idx].dropna().tolist()}
        mapped = {alias_to_canonical[v] for v in row_values if v in alias_to_canonical}
        if {"fecha", "tc_mep"}.issubset(mapped):
            header_row_idx = idx
            break

    if header_row_idx is None:
        raise IngestError(
            "El archivo 'fx' no contiene una cabecera válida con columnas de fecha y TC MEP."
        )

    header = raw.iloc[header_row_idx].tolist()
    fx = raw.iloc[header_row_idx + 1 :].copy()
    fx.columns = header
    fx = fx.dropna(how="all")

    rename_map = {}
    for c in fx.columns:
        norm = _normalize_column_name(c)
        if norm in alias_to_canonical:
            rename_map[c] = alias_to_canonical[norm]
    fx = fx.rename(columns=rename_map)

    _validate_columns(fx, REQUIRED_FX_COLUMNS, "fx")

    out = fx.copy()
    out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce").dt.date
    out["tc_mep"] = _to_numeric_local(out["tc_mep"])
    if "tc_cable" in out.columns:
        out["tc_cable"] = _to_numeric_local(out["tc_cable"])

    out = out[out["fecha"].notna()].copy()
    out = out.sort_values("fecha").drop_duplicates(subset=["fecha"], keep="last")
    out["tc_mep"] = out["tc_mep"].ffill()
    if "tc_cable" in out.columns:
        out["tc_cable"] = out["tc_cable"].ffill()

    if out["tc_mep"].isna().any():
        raise IngestError("El archivo 'fx' contiene valores inválidos de TC MEP.")

    out = out.reset_index(drop=True)
    print("Preview FX normalizado:")
    print(out.head())
    return out


def _validate_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise IngestError(
            f"El archivo '{name}' no contiene columnas requeridas: {sorted(missing)}"
        )


def _standardize_movements_schema(df: pd.DataFrame) -> pd.DataFrame:
    _validate_columns(df, REQUIRED_MOVEMENT_SOURCE_COLUMNS, "movimientos")

    available_mapping = {
        source: target for source, target in MOVEMENT_COLUMN_MAPPING.items() if source in df.columns
    }
    out = df.rename(columns=available_mapping).copy()
    # Compatibilidad con módulos existentes que todavía esperan fechaLiquidacion.
    out["fechaLiquidacion"] = out["date"]
    return out


def load_inputs(movements_file, fx_file, position_file) -> InputFrames:
    movements = _read_excel(movements_file)
    fx = _read_fx_excel(fx_file)
    position = _read_excel(position_file)

    movements = _standardize_movements_schema(movements)
    _validate_columns(position, REQUIRED_POSITION_COLUMNS, "posicion")

    return InputFrames(movements=movements, fx=fx, position=position)
