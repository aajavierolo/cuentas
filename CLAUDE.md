# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

**Altium Financiero V16**: dashboard de finanzas personales en Streamlit. El usuario sube un libro `altium.xlsx` desde el navegador; nada se persiste (el volumen `/app/data` existe solo para uso futuro). Todo el código, la interfaz y los comentarios están en español.

## Comandos

```bash
# Local (Python 3.11 en Docker; requirements fija streamlit==1.40.2)
pip install -r requirements.txt
streamlit run app.py                 # http://localhost:8501

# Docker
docker compose up -d --build         # o iniciar_altium.bat / iniciar_altium.sh
docker compose logs -f
docker compose down                  # o detener_altium.bat / detener_altium.sh
```

No hay tests, linter ni build. Para verificar un cambio: `python -m py_compile app.py modules/*.py` y luego ejecutar la app con un Excel real.

Nota: el repositorio git detectado tiene su raíz en el home del usuario (`C:/Users/Javiomen`), no en esta carpeta. Evite `git add .`/commits sin confirmar con el usuario.

## Arquitectura

Tres archivos concentran todo el código:

- **`app.py`** (~9.700 líneas, script Streamlit plano, casi sin funciones). Hace `from modules.core import *`, así que cualquier nombre de `core.py` está disponible sin import explícito. Flujo:
  1. `st.file_uploader` → `cargar_excel(...)` devuelve una tupla de 10 elementos (gastos, ingresos, presupuesto_cat, presupuesto_sub, presupuesto_mensual, patrimonio, metas, personales, felicidad_trabajos, historico_presupuesto). Todo vive dentro de `if archivo:`.
  2. Sidebar con filtros (rango de fechas/periodo rápido, categorías, subcategorías) que producen `df`, `ingresos_filtrados`, `periodos_sel`, etc.
  3. KPIs globales y navegación por `st.radio` (`key="navegacion_principal_v13"`) sobre `etiquetas_pestanas`: Resumen, Gastos, Tendencias, Presupuesto, Ingresos, Deudas, Patrimonio, Score, Felicidad. Cada sección es un bloque `if pestana_activa == etiquetas_pestanas[i]:`; **algunos índices aparecen en dos bloques** (p. ej. 0, 1 y 2), así que busque todas las ocurrencias al modificar una pestaña.
- **`modules/core.py`**: lectura/normalización del Excel, cálculos y constructores de figuras Plotly (`fig_*`), paletas (`COLOR_INGRESOS`, `PALETA_*`), `THEME_CSS` (tema oscuro neón) y helpers de estilo (`estilo_grafico`, `preparar_grafico_resumen`). Varios lectores usan `@st.cache_data`.
- **`modules/report_pdf.py`**: `generar_informe_financiero_pdf(...)` (solo argumentos keyword) arma un PDF ReportLab apaisado con gráficos Matplotlib (backend `Agg`) organizado por las mismas "preguntas" que las pestañas (`QUESTIONS`). Parchea `hashlib.md5` al importarse por compatibilidad con ReportLab.

### Hojas del Excel que se leen

`Transaccional` (gastos en A:H/A:M y bloque de trabajos/ingresos en K:Q, renombrado **por posición** con soporte de formatos de 12 y 13 columnas), `Ingresos` (plantilla antigua, fallback), `Datos` (presupuesto por categoría/subcategoría y mensual general), `Historico_presupuesto`, `Patrimonio`, `Pasivos` o `Deudas`, `Dale`, `Metas`, `Personales`. Las columnas se comparan con `normalizar()` (sin tildes, mayúsculas). Mantenga la compatibilidad con plantillas anteriores: los lectores devuelven DataFrames vacíos con columnas esperadas en vez de fallar.

### Invariantes importantes (del README)

- Los flujos mensuales conservan año **y** mes (`MESES_ORDEN` = `ENE`…`DIC`, `normalizar_mes`); no mezclar periodos de años distintos.
- El presupuesto usa todos los meses del rango seleccionado, incluso sin gastos, y respeta los filtros de categoría/subcategoría.
- La pestaña Score y el PDF deben usar **el mismo** cálculo de seis componentes: `calcular_score_financiero` / `calcular_componentes_score` en `core.py`.
- El PDF se genera solo al pulsar el botón y se guarda en `st.session_state["informe_pdf_v9*"]`; se invalida mediante un hash SHA-256 del archivo + filtros (`contexto_pdf`). Si se agrega un filtro nuevo que afecte al informe, inclúyalo en ese hash.
- Patrimonio: el valor neto aplica `Porcentaje` de propiedad; activos positivos, pasivos negativos. Si existe la hoja `Pasivos`/`Deudas`, `Patrimonio` se usa solo para activos (evita duplicar). Valores en USD se convierten con la TRM (`obtener_trm_colombia`, cacheada 6 h, hace una petición HTTP externa).

### Convenciones

- Las claves de widgets llevan sufijo de versión (`_v13`, `_v920`, `_v9`); conserve las existentes para no resetear el estado de los usuarios y use claves únicas para widgets nuevos.
- Los tooltips de Plotly se escriben a mano con `hovertemplate` y formato `$%{y:,.0f}`; `tooltip_inventory.txt` (UTF-16) es un inventario de esos tooltips.
- No incluir Excel personales ni `.streamlit/secrets.toml` en la imagen Docker.
