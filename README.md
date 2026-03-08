# Portfolio USD MEP Analyzer (MVP)

App local en Streamlit para analizar carteras de clientes en USD MEP usando:
1. Movimientos históricos
2. Histórico FX (TC MEP)
3. Posición valorizada actual

## Ejecutar
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Reglas implementadas
- Fecha de cálculo: `fechaLiquidacion`.
- Moneda base: USD MEP.
- Conversión:
  - ARS -> divide por TC MEP de la fecha
  - USD -> 1:1
  - EXT -> 1:1
- Flujos externos:
  - Entradas: `Recibo de Cobro`, `Recibo de Cobro Dolares`, `Recibo de Cobro Ext`
  - Salidas: `Orden de Pago`, `Orden de Pago USD`
- Resto: movimientos internos (inversión, comisiones, IVA, etc.).

## Estructura
- `src/ingest`: parseo y validación de archivos.
- `src/normalization`: normalización de fechas/numéricos/texto.
- `src/classification`: clasificación de movimientos.
- `src/fx`: lookup y conversión de moneda a USD MEP.
- `src/portfolio`: valuación de cartera y costo promedio por instrumento.
- `src/metrics`: métricas + XIRR.
- `src/ui`: utilidades de formato.
- `docs/discovery_and_design.md`: inspección y diseño previo.

## Limitaciones MVP
- No reconstruye valuación histórica por instrumento para fechas intermedias.
- Para fechas históricas, valor inicial manual (ARS o USD).
- PnL implícito exacto por instrumento en USD queda preparado para v2 por falta de precio actual por ticker en USD MEP.
