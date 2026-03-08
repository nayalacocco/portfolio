from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd


class IngestError(ValueError):
    """Raised when an input file cannot be parsed into required columns."""


@dataclass(frozen=True)
class FileIngestDiagnostics:
    file_key: str
    sheet_name: str
    header_row: int
    raw_columns: list[str]
    normalized_columns: list[str]
    aliases_applied: dict[str, str]
    preview: pd.DataFrame


@dataclass(frozen=True)
class InputFrames:
    movements: pd.DataFrame
    fx: pd.DataFrame
    position: pd.DataFrame
    diagnostics: dict[str, FileIngestDiagnostics]


REQUIRED_MOVEMENT_COLUMNS = {"fechaLiquidacion", "tipoMovimiento", "monto", "moneda"}
REQUIRED_FX_COLUMNS = {"fecha", "tc_mep"}
REQUIRED_POSITION_COLUMNS = {"ticker", "instrumento", "cantidad", "monto"}


COLUMN_ALIASES: dict[str, dict[str, list[str]]] = {
    "movimientos": {
        "fechaLiquidacion": [
            "fechaliquidacion",
            "fecha_liquidacion",
            "fecha liquidacion",
            "fecha de liquidacion",
        ],
        "tipoMovimiento": [
            "tipooperacion",
            "tipo_operacion",
            "tipo movimiento",
            "tipo_movimiento",
            "movimiento",
        ],
        "monto": ["total", "monto", "monto_bruto", "montobruto", "importe", "valor"],
        "moneda": ["moneda", "currency", "divisa"],
        "instrumento": ["instrumento", "descripcion", "nombre", "especie"],
        "cantidad": ["cantidad", "nominales", "tenencia"],
        "precio": ["precio", "precio_unitario"],
    },
    "fx": {
        "fecha": ["fecha"],
        "tc_mep": ["tc_mep", "tc mep", "mep", "tipo_cambio_mep"],
        "tc_cable": ["tc_cable", "tc cable", "cable", "tipo_cambio_cable"],
    },
    "posicion": {
        "ticker": ["ticker", "simbolo", "especie"],
        "instrumento": ["instrumento", "descripcion", "nombre"],
        "cantidad": ["cantidad", "nominales", "tenencia"],
        "monto": ["monto", "valuacion", "valor", "importe"],
    },
}


def _normalize_column_name(value: Any) -> str:
    txt = str(value or "").strip().lower()
    txt = "".join(
        c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c)
    )
    txt = "_".join(txt.split())
    while "__" in txt:
        txt = txt.replace("__", "_")
    return txt


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


def _read_excel_sheets(file) -> dict[str, pd.DataFrame]:
    try:
        if hasattr(file, "seek"):
            file.seek(0)
        sheets = pd.read_excel(file, sheet_name=None, header=None)
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"No se pudo leer el archivo Excel: {exc}") from exc

    if isinstance(sheets, pd.DataFrame):
        return {"Sheet1": sheets}
    return sheets


def _build_alias_index(alias_groups: dict[str, list[str]]) -> dict[str, str]:
    alias_index: dict[str, str] = {}
    for canonical, aliases in alias_groups.items():
        alias_index[_normalize_column_name(canonical)] = canonical
        for alias in aliases:
            alias_index[_normalize_column_name(alias)] = canonical
    return alias_index


def _detect_header_row(
    sheets: dict[str, pd.DataFrame],
    alias_index: dict[str, str],
    required_columns: set[str],
    file_key: str,
) -> tuple[str, int]:
    best_match: tuple[str, int, int] | None = None

    for sheet_name, raw in sheets.items():
        for row_idx in range(len(raw)):
            row = raw.iloc[row_idx].dropna().tolist()
            normalized = [_normalize_column_name(v) for v in row if _normalize_column_name(v)]
            mapped = {alias_index.get(v, v) for v in normalized}
            score = len(required_columns.intersection(mapped))
            if score < len(required_columns):
                continue
            if best_match is None or score > best_match[2] or (
                score == best_match[2] and row_idx < best_match[1]
            ):
                best_match = (sheet_name, row_idx, score)

    if best_match is None:
        raise IngestError(
            f"El archivo '{file_key}' no contiene una cabecera válida con las columnas requeridas."
        )

    return best_match[0], best_match[1]


def _collapse_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for column in df.columns.unique():
        cols = df.loc[:, df.columns == column]
        out[column] = cols.bfill(axis=1).iloc[:, 0]
    return out


def _extract_table_with_diagnostics(
    file,
    file_key: str,
    required_columns: set[str],
    alias_groups: dict[str, list[str]],
) -> tuple[pd.DataFrame, FileIngestDiagnostics]:
    sheets = _read_excel_sheets(file)
    alias_index = _build_alias_index(alias_groups)
    sheet_name, header_row = _detect_header_row(sheets, alias_index, required_columns, file_key)

    raw = sheets[sheet_name]
    raw_columns = [str(c).strip() for c in raw.iloc[header_row].tolist()]
    table = raw.iloc[header_row + 1 :].copy()
    table.columns = raw_columns
    table = table.dropna(how="all")

    normalized_cols = [_normalize_column_name(c) for c in raw_columns]
    canonical_cols = [alias_index.get(col, col) for col in normalized_cols]

    aliases_applied: dict[str, str] = {}
    for raw_col, canonical in zip(raw_columns, canonical_cols, strict=False):
        if _normalize_column_name(raw_col) != _normalize_column_name(canonical):
            aliases_applied[canonical] = raw_col

    table.columns = canonical_cols
    table = _collapse_duplicate_columns(table)

    diagnostics = FileIngestDiagnostics(
        file_key=file_key,
        sheet_name=sheet_name,
        header_row=header_row,
        raw_columns=raw_columns,
        normalized_columns=canonical_cols,
        aliases_applied=aliases_applied,
        preview=table.head(10).copy(),
    )
    return table, diagnostics


def _validate_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise IngestError(
            f"El archivo '{name}' no contiene columnas requeridas: {sorted(missing)}"
        )


def _parse_movements(file) -> tuple[pd.DataFrame, FileIngestDiagnostics]:
    out, diagnostics = _extract_table_with_diagnostics(
        file=file,
        file_key="movimientos",
        required_columns=REQUIRED_MOVEMENT_COLUMNS,
        alias_groups=COLUMN_ALIASES["movimientos"],
    )
    _validate_columns(out, REQUIRED_MOVEMENT_COLUMNS, "movimientos")

    out = out.copy()
    out["fechaLiquidacion"] = pd.to_datetime(out["fechaLiquidacion"], errors="coerce").dt.date
    out["monto"] = _to_numeric_local(out["monto"])
    if "cantidad" in out.columns:
        out["cantidad"] = _to_numeric_local(out["cantidad"])
    if "precio" in out.columns:
        out["precio"] = _to_numeric_local(out["precio"])

    out = out[out["fechaLiquidacion"].notna()].copy()
    out = out[out["tipoMovimiento"].astype(str).str.strip().ne("")]
    out = out[out["monto"].notna()].copy()

    diagnostics = FileIngestDiagnostics(
        **{**diagnostics.__dict__, "preview": out.head(10).copy()}
    )
    return out.reset_index(drop=True), diagnostics


def _parse_fx(file) -> tuple[pd.DataFrame, FileIngestDiagnostics]:
    out, diagnostics = _extract_table_with_diagnostics(
        file=file,
        file_key="fx",
        required_columns=REQUIRED_FX_COLUMNS,
        alias_groups=COLUMN_ALIASES["fx"],
    )
    _validate_columns(out, REQUIRED_FX_COLUMNS, "fx")

    out = out.copy()
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

    diagnostics = FileIngestDiagnostics(
        **{**diagnostics.__dict__, "preview": out.head(10).copy()}
    )
    return out.reset_index(drop=True), diagnostics


def _parse_position(file) -> tuple[pd.DataFrame, FileIngestDiagnostics]:
    out, diagnostics = _extract_table_with_diagnostics(
        file=file,
        file_key="posicion",
        required_columns=REQUIRED_POSITION_COLUMNS,
        alias_groups=COLUMN_ALIASES["posicion"],
    )
    _validate_columns(out, REQUIRED_POSITION_COLUMNS, "posicion")

    out = out.copy()
    out["ticker"] = out["ticker"].astype(str).str.strip()
    out["instrumento"] = out["instrumento"].astype(str).str.strip()
    out["cantidad"] = _to_numeric_local(out["cantidad"])
    out["monto"] = _to_numeric_local(out["monto"])

    text_mask = (
        out["ticker"].map(_normalize_column_name).str.contains("total", na=False)
        | out["instrumento"].map(_normalize_column_name).str.contains("total", na=False)
    )

    out = out[~text_mask].copy()
    out = out.dropna(subset=["cantidad", "monto"], how="any")
    out = out[(out["ticker"].ne("")) | (out["instrumento"].ne(""))].copy()

    diagnostics = FileIngestDiagnostics(
        **{**diagnostics.__dict__, "preview": out.head(10).copy()}
    )
    return out.reset_index(drop=True), diagnostics


def load_inputs(movements_file, fx_file, position_file) -> InputFrames:
    movements, mov_diag = _parse_movements(movements_file)
    fx, fx_diag = _parse_fx(fx_file)
    position, pos_diag = _parse_position(position_file)

    return InputFrames(
        movements=movements,
        fx=fx,
        position=position,
        diagnostics={"movimientos": mov_diag, "fx": fx_diag, "posicion": pos_diag},
    )
