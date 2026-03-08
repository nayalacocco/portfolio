from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from classification.rules import classify_movements
from fx.conversion import FXSeries
from ingest.parsing import IngestError, load_inputs
from metrics.performance import compute_metrics
from normalization.core import NormalizationError, normalize_fx, normalize_movements, normalize_position
from portfolio.valuation import (
    current_value_usd_from_position,
    infer_start_value_usd,
    instrument_cost_basis,
    movement_amount_usd,
)
from ui.formatting import fmt_pct, fmt_usd

st.set_page_config(layout="wide", page_title="Portfolio USD MEP Analyzer")
st.title("Análisis de cartera en USD MEP")


def _id_series(df: pd.DataFrame) -> pd.Series:
    if "nroticket" in df.columns:
        return df["nroticket"].astype(str)
    return df.index.astype(str)


def _display_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["fechaLiquidacion", "fecha"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%d-%m-%Y")
    return out


col1, col2, col3 = st.columns(3)
mov_file = col1.file_uploader("Movimientos históricos (Excel)", type=["xlsx", "xls"])
fx_file = col2.file_uploader("Histórico FX (Excel)", type=["xlsx", "xls"])
pos_file = col3.file_uploader("Posición valorizada actual (Excel)", type=["xlsx", "xls"])

if not (mov_file and fx_file and pos_file):
    st.info("Cargar los 3 archivos para continuar.")
    st.stop()

try:
    frames = load_inputs(mov_file, fx_file, pos_file)
    movements = normalize_movements(frames.movements)
    fx_df = normalize_fx(frames.fx)
    position = normalize_position(frames.position)
except (IngestError, NormalizationError) as exc:
    st.error(str(exc))
    st.stop()

fx = FXSeries(fx_df)
movements, warn_df = classify_movements(movements)
movements["amount_usd_mep"] = movements.apply(lambda r: movement_amount_usd(r, fx), axis=1)

st.subheader("Preview y validación")
with st.expander("Movimientos"):
    st.dataframe(_display_dates(movements.head(50)), use_container_width=True)
with st.expander("FX"):
    st.dataframe(_display_dates(fx_df.head(50)), use_container_width=True)
with st.expander("Posición"):
    st.dataframe(position.head(50), use_container_width=True)

st.subheader("Diagnóstico de ingestión")
for file_key, diag in frames.diagnostics.items():
    with st.expander(f"Archivo: {file_key}"):
        st.markdown(f"**Hoja usada:** `{diag.sheet_name}`")
        st.markdown(f"**Fila detectada como header:** `{diag.header_row}`")
        st.markdown("**Columnas crudas detectadas:**")
        st.code(", ".join(diag.raw_columns) if diag.raw_columns else "(sin columnas detectadas)")
        st.markdown("**Columnas normalizadas:**")
        st.code(
            ", ".join(diag.normalized_columns)
            if diag.normalized_columns
            else "(sin columnas normalizadas)"
        )
        st.markdown("**Aliases aplicados:**")
        st.json(diag.aliases_applied or {"detalle": "sin aliases aplicados"})
        st.markdown("**Preview normalizado (10 filas):**")
        st.dataframe(diag.preview, use_container_width=True)

if not warn_df.empty:
    st.warning("Se detectaron movimientos no reconocibles con reglas internas/externas.")
    st.dataframe(_display_dates(warn_df), use_container_width=True)

min_date = movements["fechaLiquidacion"].min()
max_date = movements["fechaLiquidacion"].max()

d1, d2 = st.columns(2)
start_date = d1.date_input("Fecha inicial", value=min_date.date(), min_value=min_date.date(), max_value=max_date.date())
end_date = d2.date_input("Fecha final", value=max_date.date(), min_value=min_date.date(), max_value=max_date.date())
if start_date > end_date:
    st.error("Fecha inicial no puede ser mayor a fecha final.")
    st.stop()

start_date_ts = pd.Timestamp(start_date)
end_date_ts = pd.Timestamp(end_date)

st.subheader("Valor inicial manual (opcional)")
m1, m2 = st.columns(2)
manual = m1.number_input("Valor inicial", min_value=0.0, value=0.0, step=100.0)
manual_ccy = m2.selectbox("Moneda valor inicial", ["USD", "ARS"])

period_mov = movements[
    (movements["fechaLiquidacion"] >= start_date_ts) & (movements["fechaLiquidacion"] <= end_date_ts)
].copy()
external = period_mov[period_mov["flow_class"].isin(["external_inflow", "external_outflow"])].copy()
external["fecha_cashflow"] = external["fechaLiquidacion"]

start_value = infer_start_value_usd(manual if manual > 0 else None, manual_ccy, start_date_ts, fx)
end_value = current_value_usd_from_position(position, fx, end_date_ts)
result = compute_metrics(start_value, end_value, external, start_date_ts, end_date_ts)

classified_external = period_mov[period_mov["flow_class"].isin(["external_inflow", "external_outflow"])].copy()
classified_ids = set(_id_series(classified_external))
external_ids = set(_id_series(external))
missing_in_external = sorted(classified_ids - external_ids)
missing_in_classified = sorted(external_ids - classified_ids)

st.markdown("**Chequeos de consistencia de fechas y flujos externos**")
st.dataframe(
    _display_dates(
        period_mov[[
            c for c in ["fechaLiquidacion_raw", "fechaLiquidacion", "date_iso", "flow_class", "tipoMovimiento", "nroticket"]
            if c in period_mov.columns
        ]].head(30)
    ),
    use_container_width=True,
)
st.write(f"External flows en movimientos clasificados: {len(classified_external)}")
st.write(f"External flows en cash flows externos: {len(external)}")
st.write({"ids_en_clasificados_no_en_cashflows": missing_in_external})
st.write({"ids_en_cashflows_no_en_clasificados": missing_in_classified})

movement_debug = movements[movements["tipoMovimiento"].eq("Recibo de Cobro")].copy()
movement_debug = movement_debug[movement_debug["date_iso"].eq("2025-04-03")]
if "nroticket" in movement_debug.columns:
    movement_debug = movement_debug[movement_debug["nroticket"].astype(str).eq("44565293")]

st.markdown("**Diagnóstico bug objetivo (Recibo de Cobro 03-04-2025, ticket 44565293)**")
exists_normalized = not movement_debug.empty
is_external_inflow = bool(exists_normalized and movement_debug["flow_class"].eq("external_inflow").any())
real_date = movement_debug["date_iso"].iloc[0] if exists_normalized else "N/A"
in_external = bool(exists_normalized and _id_series(movement_debug).isin(external_ids).any())
st.write(
    {
        "a_existe_en_movimientos_normalizados": exists_normalized,
        "b_flow_class_external_inflow": is_external_inflow,
        "c_fechaLiquidacion_normalizada": real_date,
        "d_aparece_en_dataframe_cashflows_externos": in_external,
        "e_mismatch_potencial": {
            "filtro": not in_external and exists_normalized,
            "sort_merge_dedupe_paginacion": False,
        },
    }
)
if exists_normalized:
    st.dataframe(_display_dates(movement_debug), use_container_width=True)

st.subheader("Dashboard de métricas")
mc = st.columns(5)
mc[0].metric("Valor inicial (USD MEP)", fmt_usd(result.valor_inicial_usd))
mc[1].metric("Valor final (USD MEP)", fmt_usd(result.valor_final_usd))
mc[2].metric("Entradas externas", fmt_usd(result.flujos_entrada_usd))
mc[3].metric("Salidas externas", fmt_usd(result.flujos_salida_usd))
mc[4].metric("Resultado neto", fmt_usd(result.resultado_neto_usd))

mc2 = st.columns(4)
mc2[0].metric("Flujo neto", fmt_usd(result.flujo_neto_usd))
mc2[1].metric("Retorno nominal", fmt_pct(result.retorno_nominal))
mc2[2].metric("Tasa efectiva período", fmt_pct(result.tasa_efectiva_periodo))
mc2[3].metric("TIR USD MEP", fmt_pct(result.tir_usd))

st.caption(f"Tasa efectiva anual: {fmt_pct(result.tasa_efectiva_anual)}")

st.subheader("Gráfico de evolución de flujos")
graph_df = external.groupby(["fechaLiquidacion", "flow_class"], as_index=False)["amount_usd_mep"].sum()
if not graph_df.empty:
    fig = px.bar(
        graph_df,
        x="fechaLiquidacion",
        y="amount_usd_mep",
        color="flow_class",
        barmode="relative",
        title="Flujos externos en USD MEP",
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Tabla de movimientos clasificados")
st.dataframe(_display_dates(period_mov), use_container_width=True)

st.subheader("Tabla de cash flows externos")
st.dataframe(_display_dates(external), use_container_width=True)

st.subheader("Tabla de posición actual")
st.dataframe(position, use_container_width=True)

st.subheader("Análisis por instrumento (MVP costo promedio)")
instr = instrument_cost_basis(movements, position, fx)
st.dataframe(instr, use_container_width=True)

st.subheader("Fórmulas implementadas")
st.markdown(
    """
- Resultado neto: `Vf - Vi - Entradas + Salidas`
- Retorno nominal: `(Vf + Salidas - Entradas) / Vi - 1`
- Tasa efectiva del período: `Resultado neto / Vi`
- Tasa efectiva anual: `(1 + tasa_periodo)^(365/días) - 1`
- TIR (XIRR): raíz de `Σ (CF_t / (1+r)^(días_t/365)) = 0`, usando flujos externos fechados y valor final como flujo terminal.

Limitaciones MVP:
- Valuación histórica por instrumento no reconstruida.
- Para fechas históricas se usa valor inicial manual opcional.
- `implicit_pnl_usd` por instrumento queda pendiente por falta de precio actual en USD por ticker.
"""
)
