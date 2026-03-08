# Inspección y diseño previo (antes de implementar)

## 1) Inspección de archivos reales
En el repositorio no se encontraron archivos Excel de muestra ni código base de la app.

Estructura detectada al inicio:
- `init`
- `.git/*`

Conclusión: se implementa MVP con validación fuerte de columnas y mapeo de alias.

## 2) Estructura detectada esperada para inputs

### Movimientos
Columnas mínimas:
- `fechaLiquidacion`
- `tipoMovimiento`
- `moneda`
- `monto`

Columnas opcionales para análisis por instrumento:
- `ticker`
- `cantidad`
- `precio`

### FX
Columnas mínimas:
- `fecha`
- `tc_mep`

Opcional:
- `tc_cable`

### Posición actual valorizada
Columnas mínimas:
- `ticker`
- `instrumento`
- `cantidad`
- `monto` (ARS)

## 3) Ambigüedades identificadas
1. Nombres reales de columnas pueden variar entre exportes.
2. No hay definición cerrada de signo de `monto` en movimientos (positivo/negativo). MVP toma reglas por tipo de flujo.
3. No se dispone de precio actual por ticker en USD MEP; solo `monto` agregado en ARS.
4. Para cálculo exacto de costo y PnL por instrumento faltan convenciones homogéneas de `cantidad` y eventos corporativos.

## 4) Arquitectura propuesta
- `ingest/`: lectura de excels y validación estructural.
- `normalization/`: tipos, fechas y limpieza de columnas.
- `classification/`: reglas de flujos externos vs internos.
- `fx/`: lookup de TC MEP y conversiones a USD MEP.
- `portfolio/`: valuación de cartera y base de costo promedio por instrumento.
- `metrics/`: métricas de performance y TIR (XIRR).
- `ui/`: presentación y formateo.
- `app.py`: orquestación Streamlit.

## 5) Modelo de datos interno
DataFrames normalizados:
- `movements`: fechaLiquidacion, tipoMovimiento, tipoMovimientoNorm, moneda, monto, flow_class, amount_usd_mep, opcionales de instrumento.
- `fx`: fecha, tc_mep, tc_cable(opcional).
- `position`: ticker, instrumento, cantidad, monto(ARS).

## 6) Fórmulas de métricas
- Valor inicial (USD MEP): manual o 0 (MVP), con conversión ARS/TC MEP fecha inicio.
- Valor final (USD MEP): `sum(monto_ars_posicion)/TC_MEP(fecha_final)`.
- Entradas: suma de flujos externos de entrada en USD MEP.
- Salidas: suma de flujos externos de salida en USD MEP.
- Flujo neto: `Entradas - Salidas`.
- Resultado neto: `Vf - Vi - Entradas + Salidas`.
- Retorno nominal: `(Vf + Salidas - Entradas)/Vi - 1`.
- Tasa efectiva período: `Resultado/Vi`.
- Tasa efectiva anual: `(1+tasa_periodo)^(365/días)-1`.
- TIR: XIRR con fecha inicio (`-Vi`), flujos externos fechados (entradas negativas, salidas positivas desde óptica de cartera) y valor final terminal positivo.
