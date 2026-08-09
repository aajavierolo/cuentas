# Archivo principal del dashboard Altium Financiero
# Ejecuta con: streamlit run app.py

from modules.core import *
from modules.report_pdf import generar_informe_financiero_pdf

st.markdown(THEME_CSS, unsafe_allow_html=True)
encabezado_principal = st.empty()
with encabezado_principal.container():
    titulo_col, boton_col = st.columns([5.2, 1.8])
    with titulo_col:
        st.markdown('<p class="hero-title">Altium Financiero V13</p>', unsafe_allow_html=True)
    with boton_col:
        st.button(
            "📄 Descargar informe PDF",
            disabled=True,
            use_container_width=True,
            help="Carga el archivo Excel para habilitar el informe.",
            key="pdf_deshabilitado",
        )
st.markdown(
    '<p class="hero-sub">Panel de control presupuestal · seguimiento de gastos e ingresos</p>',
    unsafe_allow_html=True,
)
st.markdown('<div class="hero-accent"></div>', unsafe_allow_html=True)

archivo = st.file_uploader("Sube altium.xlsx", type=["xlsx"])


@st.cache_data(show_spinner=False, max_entries=3)
def cargar_hoja_deudas(file):
    """Lee la hoja Deudas una sola vez por archivo cargado."""
    file.seek(0)
    return pd.read_excel(file, sheet_name="Deudas", usecols="A:F")

if archivo:

    gastos, ingresos, presupuesto_cat_base, presupuesto_sub_base, presupuesto_mensual_base, patrimonio, metas, personales, felicidad_trabajos, historico_presupuesto = cargar_excel(archivo)

    # ============================================================
    # CORRECCIÓN SEGURA DE LOS MESES DE INGRESOS
    # ============================================================
    # Se conserva íntegramente el DataFrame generado por cargar_excel(),
    # porque otras zonas como Ejecutivo, Score Financiero y Felicidad
    # dependen de su estructura original.
    #
    # Solo se recalculan MES y ANIO a partir de INGRESOS_FECHA.
    # Así, un movimiento fechado en julio se contabiliza en julio aunque
    # la columna auxiliar del Excel tenga un concepto como "Prima".
    if not ingresos.empty and "INGRESOS_FECHA" in ingresos.columns:
        ingresos = ingresos.copy()

        ingresos["INGRESOS_FECHA"] = pd.to_datetime(
            ingresos["INGRESOS_FECHA"],
            errors="coerce",
            dayfirst=True,
        )

        meses_desde_fecha = {
            1: "ENERO",
            2: "FEBRERO",
            3: "MARZO",
            4: "ABRIL",
            5: "MAYO",
            6: "JUNIO",
            7: "JULIO",
            8: "AGOSTO",
            9: "SEPTIEMBRE",
            10: "OCTUBRE",
            11: "NOVIEMBRE",
            12: "DICIEMBRE",
        }

        fechas_validas_ingresos = ingresos["INGRESOS_FECHA"].notna()

        ingresos.loc[fechas_validas_ingresos, "MES"] = (
            ingresos.loc[fechas_validas_ingresos, "INGRESOS_FECHA"]
            .dt.month
            .map(meses_desde_fecha)
        )

        ingresos.loc[fechas_validas_ingresos, "ANIO"] = (
            ingresos.loc[fechas_validas_ingresos, "INGRESOS_FECHA"]
            .dt.year
        )

    # ============================================================
    # HOJA DEUDAS
    # Columnas esperadas:
    # A = nombre, B = deuda inicial, C = interés mensual,
    # D = saldo, E = avance, F = inicio del crédito
    # ============================================================
    try:
        deudas_raw = cargar_hoja_deudas(archivo)

        # Se renombran por posición para aceptar encabezados con mayúsculas,
        # minúsculas o columnas sin nombre.
        deudas_raw = deudas_raw.iloc[:, :6].copy()
        deudas_raw.columns = [
            "Nombre",
            "Deuda inicial",
            "Interés",
            "Saldo",
            "Avance Excel",
            "Inicio del crédito",
        ]

        deudas = deudas_raw.copy()
        deudas["Nombre"] = deudas["Nombre"].astype("string").str.strip()
        deudas = deudas[
            deudas["Nombre"].notna()
            & deudas["Nombre"].ne("")
            & deudas["Nombre"].str.lower().ne("nan")
        ].copy()

        for columna in ["Deuda inicial", "Interés", "Saldo", "Avance Excel"]:
            deudas[columna] = pd.to_numeric(
                deudas[columna],
                errors="coerce",
            )

        deudas["Inicio del crédito"] = pd.to_datetime(
            deudas["Inicio del crédito"],
            errors="coerce",
            dayfirst=True,
        )

        deudas["Deuda inicial"] = deudas["Deuda inicial"].fillna(0).clip(lower=0)
        deudas["Interés"] = deudas["Interés"].fillna(0).clip(lower=0)
        deudas["Saldo"] = deudas["Saldo"].fillna(
            deudas["Deuda inicial"]
        ).clip(lower=0)

        # El avance se recalcula para no depender de fórmulas guardadas en Excel.
        deudas["Pagado"] = (
            deudas["Deuda inicial"] - deudas["Saldo"]
        ).clip(lower=0)

        deuda_inicial_valida = deudas["Deuda inicial"].where(deudas["Deuda inicial"].gt(0))
        deudas["Avance"] = deudas["Pagado"].div(deuda_inicial_valida).mul(100).fillna(0.0)

        # Prioridad tipo avalancha:
        # 1. Mayor interés.
        # 2. En empate, mayor saldo pendiente.
        deudas = deudas.sort_values(
            ["Interés", "Saldo"],
            ascending=[False, False],
        ).reset_index(drop=True)

    except Exception:
        deudas = pd.DataFrame(
            columns=[
                "Nombre",
                "Deuda inicial",
                "Interés",
                "Saldo",
                "Pagado",
                "Avance",
                "Inicio del crédito",
            ]
        )

    with st.sidebar:
        st.markdown("### ✦ Filtros inteligentes")
        st.markdown(
            '<div class="filter-card"><p style="margin:0;color:#DDF8FF;">'
            'Personaliza el período y la clasificación del análisis.</p></div>',
            unsafe_allow_html=True,
        )

        # ============================================================
        # Filtro de fechas simplificado: periodos rápidos o rango personalizado.
        # ============================================================
        fechas_gastos_validas = gastos["GASTOS_FECHA"].dropna()
        fecha_minima = fechas_gastos_validas.min().date() if not fechas_gastos_validas.empty else pd.Timestamp.today().date()
        fecha_ultima_dato = fechas_gastos_validas.max().date() if not fechas_gastos_validas.empty else fecha_minima
        fecha_hoy = pd.Timestamp.today().date()
        fecha_maxima = max(fecha_hoy, fecha_minima, fecha_ultima_dato)

        st.markdown('<div class="filter-card">', unsafe_allow_html=True)
        periodo_rapido = st.selectbox(
            "🗓️ Período",
            [
                "Todo el historial",
                "Mes actual",
                "Mes anterior",
                "Últimos 3 meses",
                "Últimos 6 meses",
                "Último año",
                "Año actual",
                "Personalizado",
            ],
            index=0,
            help="Selecciona un periodo rápido o elige Personalizado para definir ambas fechas.",
            key="filtro_periodo_rapido_v13",
        )

        hoy_ts = pd.Timestamp(fecha_hoy)
        ultima_fecha_ts = pd.Timestamp(fecha_ultima_dato)
        if periodo_rapido == "Mes actual":
            fecha_desde = hoy_ts.replace(day=1).date()
            fecha_hasta = min(fecha_hoy, fecha_maxima)
        elif periodo_rapido == "Mes anterior":
            inicio_mes_actual = hoy_ts.replace(day=1)
            fecha_desde = (inicio_mes_actual - pd.offsets.MonthBegin(1)).date()
            fecha_hasta = (inicio_mes_actual - pd.Timedelta(days=1)).date()
        elif periodo_rapido == "Últimos 3 meses":
            fecha_desde = (hoy_ts.replace(day=1) - pd.DateOffset(months=2)).date()
            fecha_hasta = min(fecha_hoy, fecha_maxima)
        elif periodo_rapido == "Últimos 6 meses":
            fecha_desde = (
                ultima_fecha_ts.replace(day=1) - pd.DateOffset(months=5)
            ).date()
            fecha_hasta = fecha_ultima_dato
        elif periodo_rapido == "Último año":
            fecha_desde = (
                ultima_fecha_ts.replace(day=1) - pd.DateOffset(months=11)
            ).date()
            fecha_hasta = fecha_ultima_dato
        elif periodo_rapido == "Año actual":
            fecha_desde = hoy_ts.replace(month=1, day=1).date()
            fecha_hasta = min(fecha_hoy, fecha_maxima)
        elif periodo_rapido == "Personalizado":
            rango_personalizado = st.date_input(
                "📅 Desde y hasta",
                value=(fecha_minima, fecha_maxima),
                min_value=fecha_minima,
                max_value=fecha_maxima,
                help="Selecciona la fecha inicial y luego la fecha final en el mismo calendario.",
                key="filtro_rango_personalizado_v13",
            )
            if isinstance(rango_personalizado, (tuple, list)) and len(rango_personalizado) == 2:
                fecha_desde, fecha_hasta = rango_personalizado
            elif isinstance(rango_personalizado, (tuple, list)) and len(rango_personalizado) == 1:
                fecha_desde = fecha_hasta = rango_personalizado[0]
            else:
                fecha_desde = fecha_hasta = rango_personalizado
        else:
            fecha_desde, fecha_hasta = fecha_minima, fecha_maxima

        fecha_desde = max(fecha_desde, fecha_minima)
        fecha_hasta = min(fecha_hasta, fecha_maxima)
        if fecha_desde > fecha_hasta:
            fecha_desde, fecha_hasta = fecha_minima, fecha_maxima
            st.info("Ese periodo está fuera del historial disponible; se mostrará todo el historial.")

        st.caption(f"Aplicado: {fecha_desde:%d/%m/%Y} → {fecha_hasta:%d/%m/%Y}")
        st.markdown("</div>", unsafe_allow_html=True)

        fecha_desde_ts = pd.Timestamp(fecha_desde)
        fecha_hasta_ts = pd.Timestamp(fecha_hasta) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        gastos_por_fecha = gastos[
            gastos["GASTOS_FECHA"].between(fecha_desde_ts, fecha_hasta_ts, inclusive="both")
        ].copy()

        meses_sel = sorted(
            gastos_por_fecha["MES"].dropna().astype(str).str.upper().unique(),
            key=lambda m: MESES_NUM.get(str(m).upper(), 99),
        )
        anios_sel = sorted(gastos_por_fecha["ANIO"].dropna().astype(int).unique())

        categorias = sorted(gastos_por_fecha["GASTOS_CATEGORIA"].dropna().unique())

        st.markdown('<div class="filter-card">', unsafe_allow_html=True)
        categorias_elegidas = st.multiselect(
            "Categorías",
            categorias,
            default=[],
            placeholder="Todas las categorías",
            help="Déjalo vacío para incluir todas las categorías.",
            key="filtro_categorias_v13",
        )
        categorias_sel = categorias_elegidas or categorias
        st.caption("Vacío = todas las categorías")
        st.markdown("</div>", unsafe_allow_html=True)

        subcategorias = sorted(
            gastos_por_fecha.loc[
                gastos_por_fecha["GASTOS_CATEGORIA"].isin(categorias_sel),
                "GASTOS_SUBCATEGORIA",
            ].dropna().unique()
        )
        clave_filtro_subcategorias = "filtro_subcategorias_v13"
        if clave_filtro_subcategorias in st.session_state:
            st.session_state[clave_filtro_subcategorias] = [
                subcategoria
                for subcategoria in st.session_state[clave_filtro_subcategorias]
                if subcategoria in subcategorias
            ]
        st.markdown('<div class="filter-card">', unsafe_allow_html=True)
        subcategorias_elegidas = st.multiselect(
            "Subcategorías",
            subcategorias,
            default=[],
            placeholder="Todas las subcategorías",
            help="Déjalo vacío para incluir todas las subcategorías disponibles.",
            key=clave_filtro_subcategorias,
        )
        subcategorias_sel = subcategorias_elegidas or subcategorias
        st.caption("Vacío = todas las subcategorías")
        st.markdown("</div>", unsafe_allow_html=True)

    df = gastos_por_fecha[
        gastos_por_fecha["GASTOS_CATEGORIA"].isin(categorias_sel)
        & gastos_por_fecha["GASTOS_SUBCATEGORIA"].isin(subcategorias_sel)
    ].copy()

    # Presupuesto aplicable al periodo filtrado. Cada mes toma su valor específico
    # de Historico_presupuesto; una celda vacía ya fue reemplazada por propuesto.
    presupuesto_cat, presupuesto_sub, presupuesto_mensual_general, presupuesto_mensual_por_periodo = (
        presupuestos_para_dataframe(historico_presupuesto, df)
    )
    if not presupuesto_cat and presupuesto_cat_base:
        presupuesto_cat = presupuesto_cat_base
        presupuesto_sub = presupuesto_sub_base
        presupuesto_mensual_general = presupuesto_mensual_base
        presupuesto_mensual_por_periodo = {}


    if not ingresos.empty:
        ingresos_tmp = ingresos.copy()
        ingresos_tmp["INGRESOS_FECHA"] = pd.to_datetime(ingresos_tmp["INGRESOS_FECHA"], errors="coerce")
        ingresos_filtrados = ingresos_tmp[
            ingresos_tmp["INGRESOS_FECHA"].between(fecha_desde_ts, fecha_hasta_ts, inclusive="both")
        ].copy()
    else:
        ingresos_filtrados = ingresos.copy()

    # La pestaña Felicidad debe respetar el mismo filtro global de fechas.
    # Antes usaba felicidad_trabajos sin filtrar, por eso sus métricas y gráficas
    # no cambiaban al modificar Desde/Hasta en la barra lateral.
    if not felicidad_trabajos.empty:
        felicidad_tmp = felicidad_trabajos.copy()
        felicidad_tmp["FECHA"] = pd.to_datetime(felicidad_tmp["FECHA"], errors="coerce")
        felicidad_trabajos_filtrados = felicidad_tmp[
            felicidad_tmp["FECHA"].between(fecha_desde_ts, fecha_hasta_ts, inclusive="both")
        ].copy()
    else:
        felicidad_trabajos_filtrados = felicidad_trabajos.copy()

    total_ingresos = ingresos_filtrados["INGRESOS_CANTIDAD"].sum() if not ingresos_filtrados.empty else 0
    total_gastos = df["GASTOS_CANTIDAD"].sum()
    balance = total_ingresos - total_gastos

    nombre_persona = personales.get("nombre", "Sin registrar") if isinstance(personales, dict) else "Sin registrar"
    edad_persona = personales.get("edad") if isinstance(personales, dict) else None

    # Base mensual compartida por la aplicación y el informe PDF.
    flujo_reporte = construir_flujo_mensual(
        gastos_df=df,
        ingresos_df=ingresos_filtrados,
        meses_sel=meses_sel,
        presupuesto_mensual=presupuesto_mensual_por_periodo or presupuesto_mensual_general,
    )

    # El PDF se construye únicamente cuando el usuario lo solicita.
    # Los bytes quedan en session_state para que el botón de descarga no
    # vuelva a ejecutar todo el informe durante cada interacción.
    encabezado_principal.empty()
    with encabezado_principal.container():
        titulo_col, boton_col = st.columns([5.2, 1.8])
        with titulo_col:
            st.markdown('<p class="hero-title">Altium Financiero V13</p>', unsafe_allow_html=True)
        with boton_col:
            generar_pdf_click = st.button(
                "📄 Preparar informe PDF",
                use_container_width=True,
                help="Genera el informe consolidado con los filtros activos.",
                key="preparar_informe_pdf_v9",
            )

    if generar_pdf_click:
        try:
            with st.spinner("Preparando informe PDF..."):
                st.session_state["informe_pdf_v9"] = generar_informe_financiero_pdf(
                    nombre_persona=nombre_persona,
                    edad_persona=edad_persona if edad_persona is not None else "Sin registrar",
                    fecha_desde=fecha_desde.strftime("%d/%m/%Y"),
                    fecha_hasta=fecha_hasta.strftime("%d/%m/%Y"),
                    total_ingresos=float(total_ingresos),
                    total_gastos=float(total_gastos),
                    balance=float(balance),
                    gastos=df,
                    ingresos=ingresos_filtrados,
                    flujo=flujo_reporte,
                    deudas=deudas,
                    patrimonio=patrimonio,
                    metas=metas,
                    felicidad=felicidad_trabajos_filtrados,
                    presupuesto_mensual=float(presupuesto_mensual_general or 0),
                )
                nombre_pdf_seguro = normalizar(nombre_persona).title().replace(" ", "_")
                nombre_pdf_seguro = "".join(
                    caracter for caracter in nombre_pdf_seguro
                    if caracter.isalnum() or caracter in {"_", "-"}
                ).strip("_") or "Persona"
                st.session_state["informe_pdf_v9_nombre"] = (
                    f"{nombre_pdf_seguro}_{fecha_desde:%Y-%m-%d}_{fecha_hasta:%Y-%m-%d}.pdf"
                )
                st.session_state.pop("informe_pdf_v9_error", None)
        except Exception as error_pdf:
            st.session_state.pop("informe_pdf_v9", None)
            st.session_state["informe_pdf_v9_error"] = f"{type(error_pdf).__name__}: {error_pdf}"

    if st.session_state.get("informe_pdf_v9"):
        st.download_button(
            "⬇️ Descargar informe PDF preparado",
            data=st.session_state["informe_pdf_v9"],
            file_name=st.session_state.get("informe_pdf_v9_nombre", "altium_financiero_v13.pdf"),
            mime="application/pdf",
            use_container_width=True,
            key="descargar_informe_pdf_v9",
        )

    if st.session_state.get("informe_pdf_v9_error"):
        st.error(
            "No fue posible crear el PDF. Detalle técnico: "
            + st.session_state["informe_pdf_v9_error"]
        )

    p1, p2 = st.columns([2, 1])
    p1.metric("Persona", nombre_persona)
    p2.metric("Edad", f"{edad_persona}" if edad_persona is not None else "Sin registrar")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ingresos", f"${total_ingresos:,.0f}")
    c2.metric("Gastos", f"${total_gastos:,.0f}")
    delta_balance = f"{(balance / total_ingresos * 100):+.1f}% de ingresos" if total_ingresos else None
    c3.metric("Balance", f"${balance:,.0f}", delta=delta_balance)
    c4.metric("Transacciones", len(df))

    etiquetas_pestanas = [
        "📈 Resumen",
        "🧾 Gastos",
        "📅 Tendencias",
        "🎯 Presupuesto",
        "💰 Ingresos",
        "💳 Deudas",
        "🏠 Patrimonio",
        "🏆 Score",
        "😊 Felicidad",
    ]
    pestana_activa = st.radio(
        "Sección del informe",
        etiquetas_pestanas,
        horizontal=True,
        label_visibility="collapsed",
        key="navegacion_principal_v13",
    )

    # Tooltips de navegación: cada pestaña explica la pregunta que responde.
    st.markdown(
        """
        <style>
        [data-testid="stRadio"] [role="radiogroup"] {
            gap: 0.38rem;
            flex-wrap: wrap;
            padding: 0.35rem 0 0.7rem 0;
        }
        [data-testid="stRadio"] [role="radiogroup"] label {
            border: 1px solid rgba(56, 189, 248, 0.30);
            border-radius: 999px;
            padding: 0.38rem 0.72rem;
            background: linear-gradient(145deg, rgba(15,23,42,0.90), rgba(2,6,23,0.96));
            transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
        }
        [data-testid="stRadio"] [role="radiogroup"] label:hover {
            border-color: rgba(0, 240, 255, 0.85);
            box-shadow: 0 0 14px rgba(0, 240, 255, 0.18);
            transform: translateY(-1px);
        }
        [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
            border-color: #00F0FF;
            background: linear-gradient(145deg, rgba(0,240,255,0.18), rgba(123,47,255,0.16));
            box-shadow: 0 0 18px rgba(0, 240, 255, 0.24);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    def contexto_pestana(pregunta, respuesta):
        st.markdown(
            f"""
            <div style="
                margin: 0.2rem 0 1.2rem 0;
                padding: 14px 16px;
                border-radius: 14px;
                border: 1px solid rgba(56,189,248,0.38);
                background: linear-gradient(135deg, rgba(15,23,42,0.92), rgba(2,6,23,0.96));
            ">
                <div style="color:#38BDF8;font-weight:800;font-size:1rem;">{pregunta}</div>
                <div style="color:#CBD5E1;margin-top:5px;line-height:1.45;">{respuesta}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def seccion_resumen(numero, titulo, descripcion):
        st.markdown(
            f"""
            <div style="
                margin: 1.55rem 0 0.85rem 0;
                padding: 13px 16px;
                border-left: 5px solid #38BDF8;
                border-radius: 12px;
                background: linear-gradient(90deg, rgba(56,189,248,0.13), rgba(15,23,42,0.25));
            ">
                <div style="font-size:1.12rem;font-weight:800;color:#F8FAFC;">{numero}. {titulo}</div>
                <div style="font-size:0.88rem;color:#94A3B8;margin-top:4px;">{descripcion}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if pestana_activa == etiquetas_pestanas[0]:
        contexto_pestana("¿Cómo estoy hoy?", "Entrega una lectura inmediata de ingresos, gastos, balance, ahorro, proyección y alertas financieras.")
        st.markdown("## Resumen financiero")
        st.caption("Una lectura jerarquizada del estado actual. Todos los indicadores respetan los filtros activos.")
        seccion_resumen("1", "Estado general", "Persona, periodo, ingresos, gastos, balance y volumen de transacciones.")

        # ======================================================
        # INDICADORES EJECUTIVOS DEL RESUMEN
        # ======================================================
        # Ya fue calculado para los indicadores globales y el PDF.
        resumen_flujo = flujo_reporte

        tipo_df_resumen = agregar_tipo_gasto(df)
        gastos_fijos = float(tipo_df_resumen.loc[tipo_df_resumen["TIPO_GASTO"].eq("Fijo"), "GASTOS_CANTIDAD"].sum()) if not tipo_df_resumen.empty else 0.0
        gastos_variables = float(tipo_df_resumen.loc[tipo_df_resumen["TIPO_GASTO"].eq("Variable"), "GASTOS_CANTIDAD"].sum()) if not tipo_df_resumen.empty else 0.0
        pct_fijos = (gastos_fijos / total_gastos * 100) if total_gastos else 0.0
        pct_variables = (gastos_variables / total_gastos * 100) if total_gastos else 0.0

        meses_con_movimiento = resumen_flujo[resumen_flujo["Gastos"].gt(0)]
        n_meses_gasto = max(len(meses_con_movimiento), 1)
        gasto_promedio_mensual = float(meses_con_movimiento["Gastos"].mean()) if not meses_con_movimiento.empty else 0.0
        ahorro_mensual = float(resumen_flujo["Balance"].mean()) if not resumen_flujo.empty else 0.0
        ahorro_anual_proyectado = ahorro_mensual * 12
        pct_ahorro = (balance / total_ingresos * 100) if total_ingresos else 0.0
        capacidad_ahorro = pct_ahorro

        # Recomendaciones calculadas sobre el promedio mensual real de ingresos.
        meses_con_ingresos = resumen_flujo[resumen_flujo["Ingresos"].gt(0)]
        ingreso_promedio_mensual = (
            float(meses_con_ingresos["Ingresos"].mean())
            if not meses_con_ingresos.empty
            else 0.0
        )
        recomendado_inversion_mensual = ingreso_promedio_mensual * 0.20
        recomendado_ahorro_mensual = ingreso_promedio_mensual * 0.10

        dias_periodo = max(df["GASTOS_FECHA"].dropna().dt.date.nunique(), 1) if not df.empty else 1
        gasto_promedio_diario = total_gastos / dias_periodo if dias_periodo else 0.0
        gasto_promedio_semanal = gasto_promedio_diario * 7

        texto_deuda = (
            df.get("GASTOS_CATEGORIA", pd.Series(dtype=str)).astype(str).map(normalizar) + " " +
            df.get("GASTOS_SUBCATEGORIA", pd.Series(dtype=str)).astype(str).map(normalizar) + " " +
            df.get("GASTOS_SUBCATEGORIA_2", pd.Series(dtype=str)).astype(str).map(normalizar) + " " +
            df.get("GASTOS_DESCRIPCION", pd.Series(dtype=str)).astype(str).map(normalizar)
        ) if not df.empty else pd.Series(dtype=str)
        claves_deuda = ["DEUDA", "CREDITO", "PRESTAMO", "CUOTA", "HIPOTECA", "TARJETA", "LIBRANZA"]
        mask_deuda = texto_deuda.map(lambda x: any(k in x for k in claves_deuda)) if not texto_deuda.empty else pd.Series(dtype=bool)
        pagos_deuda = float(df.loc[mask_deuda, "GASTOS_CANTIDAD"].sum()) if not df.empty and len(mask_deuda) == len(df) else 0.0
        pct_ingresos_deuda = (pagos_deuda / total_ingresos * 100) if total_ingresos else 0.0
        capacidad_endeudamiento_valor = max((total_ingresos * 0.30) - pagos_deuda, 0.0)
        capacidad_endeudamiento_pct = (capacidad_endeudamiento_valor / total_ingresos * 100) if total_ingresos else 0.0

        gastos_por_mes_resumen = resumen_flujo[resumen_flujo["Gastos"].gt(0)].copy()
        variacion_mes_anterior = 0.0
        variacion_texto = "Sin comparación"
        if len(gastos_por_mes_resumen) >= 2:
            gasto_actual = float(gastos_por_mes_resumen.iloc[-1]["Gastos"])
            gasto_anterior = float(gastos_por_mes_resumen.iloc[-2]["Gastos"])
            variacion_mes_anterior = ((gasto_actual - gasto_anterior) / gasto_anterior * 100) if gasto_anterior else 0.0
            variacion_texto = f"{variacion_mes_anterior:+.1f}%"

        presupuesto_anual_estimado = (float(presupuesto_mensual_general or 0) / max(len(presupuesto_mensual_por_periodo), 1)) * 12
        gasto_proyectado_diciembre = gasto_promedio_mensual * 12
        diferencia_meta_anual = presupuesto_anual_estimado - gasto_proyectado_diciembre
        if presupuesto_anual_estimado > 0:
            estado_proyeccion = (
                f"Te quedarían ${diferencia_meta_anual:,.0f} disponibles frente a la meta anual."
                if diferencia_meta_anual >= 0
                else f"Te faltarían ${abs(diferencia_meta_anual):,.0f} para cumplir la meta anual."
            )
        else:
            estado_proyeccion = "Completa propuesto o los valores mensuales en Historico_presupuesto para calcular la meta anual."

        def tarjeta_kpi(titulo, valor, subtitulo="", color="#38BDF8", icono="📊"):
            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(135deg, rgba(15,23,42,0.98), rgba(2,6,23,0.98));
                    border: 1px solid {color};
                    border-radius: 18px;
                    padding: 18px 18px 14px 18px;
                    min-height: 132px;
                    box-shadow: 0 12px 30px rgba(0,0,0,0.42);
                ">
                    <div style="display:flex; align-items:center; gap:10px; color:#cbd5e1; font-weight:700; font-size:0.92rem;">
                        <span style="font-size:1.65rem;">{icono}</span>
                        <span>{titulo}</span>
                    </div>
                    <div style="font-size:1.72rem; font-weight:800; color:{color}; margin-top:12px; letter-spacing:-0.02em;">
                        {valor}
                    </div>
                    <div style="color:#94a3b8; font-size:0.88rem; margin-top:6px; line-height:1.35;">
                        {subtitulo}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        seccion_resumen("2", "Ahorro y liquidez", "Capacidad de ahorro actual, proyección anual y referencias mensuales para ahorrar e invertir.")

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            tarjeta_kpi("Ahorro mensual", f"${ahorro_mensual:,.0f}", "Promedio de los meses filtrados", COLOR_BALANCE, "🐷")
        with k2:
            tarjeta_kpi("Ahorro anual", f"${ahorro_anual_proyectado:,.0f}", "Proyección con el ahorro mensual", COLOR_INGRESOS, "📈")
        with k3:
            tarjeta_kpi(
                "Recomendado para invertir",
                f"${recomendado_inversion_mensual:,.0f}",
                "20% del ingreso promedio mensual",
                "#C084FC",
                "📊",
            )
        with k4:
            tarjeta_kpi(
                "Recomendado para ahorrar",
                f"${recomendado_ahorro_mensual:,.0f}",
                "10% del ingreso promedio mensual",
                "#FDBA74",
                "🏦",
            )

        seccion_resumen("3", "Riesgos principales", "Endeudamiento, presión de las deudas y variación reciente del gasto.")

        k5, k6, k7, k8 = st.columns(4)
        with k5:
            tarjeta_kpi("Capacidad de ahorro", f"{capacidad_ahorro:.1f}%", "Entre más alto, mejor margen", "#2DD4BF", "⚡")
        with k6:
            tarjeta_kpi("Deudas / ingresos", f"{pct_ingresos_deuda:.1f}%", f"Pagos detectados: ${pagos_deuda:,.0f}", "#FBBF24", "💳")
        with k7:
            tarjeta_kpi("Capacidad endeudamiento", f"{capacidad_endeudamiento_pct:.1f}%", f"Margen disponible: ${capacidad_endeudamiento_valor:,.0f}", "#FB7185", "🛡️")
        with k8:
            tarjeta_kpi("Variación mensual", variacion_texto, "Gasto actual vs mes anterior", "#93C5FD", "🔁")

        st.markdown("#### Indicadores de riesgo y composición")
        g1, g2, g3 = st.columns([1.05, 1.05, 1.2])

        with g1:
            fig_comp = go.Figure(go.Pie(
                labels=["Gastos fijos", "Gastos variables"],
                values=[gastos_fijos, gastos_variables],
                hole=0.62,
                marker=dict(colors=["#38BDF8", "#FB7185"], line=dict(color="#000000", width=2)),
                textinfo="percent+label",
                hovertemplate=(
                    "<b>🧩 %{label}</b><br><br>"
                    "💰 Valor acumulado: <b>$%{value:,.0f}</b><br>"
                    "📊 Participación en el gasto: %{percent}<br>"
                    "📌 Comparación entre gastos fijos y variables"
                    "<extra></extra>"
                ),
            ))
            fig_comp.add_annotation(text=f"${total_gastos:,.0f}<br><span style='font-size:12px'>Total gastos</span>", x=0.5, y=0.5, showarrow=False, font=dict(color="#F8FAFC", size=17))
            fig_comp.update_layout(height=360, margin=dict(t=55,b=20,l=20,r=20))
            st.plotly_chart(
                preparar_grafico_resumen(
                    fig_comp,
                    titulo="Composición de gastos fijos y variables",
                    leyenda="Tipo de gasto",
                    mostrar_leyenda=True,
                ),
                use_container_width=True,
            )

        with g2:
            fig_deuda = go.Figure(go.Indicator(
                mode="gauge+number",
                value=pct_ingresos_deuda,
                number={"suffix":"%", "font":{"color":"#F8FAFC", "size":38}},
                title={"text":"Ingresos destinados a deudas", "font":{"color":"#c7d2fe"}},
                gauge={
                    "axis":{"range":[0,60], "tickcolor":"#94a3b8"},
                    "bar":{"color":"#FBBF24"},
                    "bgcolor":"#0a0a0a",
                    "borderwidth":1,
                    "bordercolor":"#6366f1",
                    "steps":[
                        {"range":[0,20], "color":"#064e3b"},
                        {"range":[20,35], "color":"#713f12"},
                        {"range":[35,60], "color":"#7f1d1d"},
                    ],
                    "threshold":{"line":{"color":"#F8FAFC", "width":3}, "thickness":0.75, "value":30},
                },
            ))
            fig_deuda.update_layout(height=360, paper_bgcolor="#000000", plot_bgcolor="#000000", font=dict(color="#e2e8f0"), margin=dict(t=55,b=20,l=20,r=20))
            st.plotly_chart(
                preparar_grafico_resumen(
                    fig_deuda,
                    titulo="Porcentaje de ingresos destinados a deudas",
                    mostrar_leyenda=False,
                ),
                use_container_width=True,
            )

        with g3:
            barras_pct = pd.DataFrame({
                "Indicador": ["% ahorro", "% fijos", "% variables", "% deudas", "Capacidad deuda"],
                "Porcentaje": [pct_ahorro, pct_fijos, pct_variables, pct_ingresos_deuda, capacidad_endeudamiento_pct],
            })
            fig_barras_pct = px.bar(
                barras_pct,
                x="Porcentaje",
                y="Indicador",
                orientation="h",
                text="Porcentaje",
                color="Indicador",
                color_discrete_sequence=PALETA_NEON,
            )
            fig_barras_pct.update_traces(
                texttemplate="%{text:.1f}%",
                textposition="outside",
                hovertemplate=(
                    "<b>📊 %{y}</b><br><br>"
                    "🎯 Resultado: <b>%{x:.1f}%</b><br>"
                    "📌 Indicador calculado sobre el período filtrado"
                    "<extra></extra>"
                ),
            )
            fig_barras_pct.update_layout(height=360, showlegend=False, yaxis=dict(autorange="reversed"), margin=dict(t=55,b=35,l=10,r=30))
            st.plotly_chart(
                preparar_grafico_resumen(
                    fig_barras_pct,
                    titulo="Indicadores porcentuales clave",
                    x="Porcentaje",
                    y="Indicador",
                    mostrar_leyenda=False,
                ),
                use_container_width=True,
            )

        seccion_resumen("5", "Evolución rápida", "Compara ingresos, gastos y balance por mes sin sustituir el análisis detallado de Tendencias.")
        st.markdown("#### Evolución mensual y proyección")
        ev1, ev2 = st.columns([1.45, 1])
        with ev1:
            resumen_plot = resumen_flujo.copy()
            fig_evo = go.Figure()
            datos_evolucion_resumen = resumen_plot[["Ingresos", "Gastos", "Balance"]]
            tooltip_evolucion_resumen = (
                "<b>📅 %{x}</b><br><br>"
                "💵 Ingresos: $%{customdata[0]:,.0f}<br>"
                "🧾 Gastos: $%{customdata[1]:,.0f}<br>"
                "⚖️ Balance: <b>$%{customdata[2]:,.0f}</b>"
                "<extra></extra>"
            )
            fig_evo.add_trace(go.Bar(x=resumen_plot["MES"], y=resumen_plot["Ingresos"], name="Ingresos", marker_color=COLOR_INGRESOS, opacity=0.72, customdata=datos_evolucion_resumen, hovertemplate=tooltip_evolucion_resumen))
            fig_evo.add_trace(go.Bar(x=resumen_plot["MES"], y=resumen_plot["Gastos"], name="Gastos", marker_color=COLOR_GASTOS, opacity=0.72, customdata=datos_evolucion_resumen, hovertemplate=tooltip_evolucion_resumen))
            fig_evo.add_trace(go.Scatter(x=resumen_plot["MES"], y=resumen_plot["Balance"], name="Ahorro / Balance", mode="lines+markers", line=dict(color=COLOR_BALANCE, width=4, shape="spline"), marker=dict(size=10), customdata=datos_evolucion_resumen, hovertemplate=tooltip_evolucion_resumen))
            fig_evo.update_layout(barmode="group", height=430, xaxis=dict(categoryorder="array", categoryarray=MESES_ORDEN), yaxis=dict(tickformat=",.0f"), legend=dict(orientation="h", y=1.08), margin=dict(t=70,b=35,l=35,r=20))
            st.plotly_chart(
                preparar_grafico_resumen(
                    fig_evo,
                    titulo="Ingresos, gastos y ahorro por mes",
                    x="Mes",
                    y="Valor",
                    leyenda="Concepto",
                    mostrar_leyenda=True,
                ),
                use_container_width=True,
            )

        with ev2:
            proy_df = pd.DataFrame({
                "Concepto": ["Gasto proyectado a diciembre", "Meta anual presupuesto"],
                "Valor": [gasto_proyectado_diciembre, presupuesto_anual_estimado],
            })
            fig_proy = px.bar(
                proy_df,
                x="Concepto",
                y="Valor",
                text="Valor",
                color="Concepto",
                color_discrete_map={"Gasto proyectado a diciembre": COLOR_GASTOS, "Meta anual presupuesto": COLOR_PRESUPUESTO},
            )
            fig_proy.update_traces(
                texttemplate="$%{text:,.0f}",
                textposition="outside",
                hovertemplate=(
                    "<b>🔮 %{x}</b><br><br>"
                    "💰 Valor estimado: <b>$%{y:,.0f}</b><br>"
                    "📅 Proyección calculada al cierre de diciembre"
                    "<extra></extra>"
                ),
            )
            fig_proy.update_layout(height=430, showlegend=False, margin=dict(t=70,b=70,l=30,r=20))
            st.plotly_chart(
                preparar_grafico_resumen(
                    fig_proy,
                    titulo="Proyección anual de gasto frente al presupuesto",
                    x="Concepto",
                    y="Valor",
                    mostrar_leyenda=False,
                ),
                use_container_width=True,
            )

        seccion_resumen("6", "Proyección", "Estima el cierre anual y compara el ritmo actual de gasto con la meta presupuestal.")

        avance_meta = (gasto_proyectado_diciembre / presupuesto_anual_estimado * 100) if presupuesto_anual_estimado else 0
        st.markdown(
            f"""
            <div style="background:#0a0a0a; border:1px solid rgba(99,102,241,0.45); border-radius:18px; padding:18px; margin-top:4px;">
                <div style="font-size:1.15rem; font-weight:800; color:#f8fafc; margin-bottom:8px;">🔮 Lectura automática de la proyección</div>
                <div style="color:#cbd5e1; line-height:1.6;">
                    Si continúas gastando igual, en diciembre habrías gastado aproximadamente
                    <b style="color:#FB7185;">${gasto_proyectado_diciembre:,.0f}</b>.
                    Meta anual estimada: <b style="color:#FDE68A;">${presupuesto_anual_estimado:,.0f}</b>.
                    {estado_proyeccion}
                </div>
                <div style="margin-top:14px; height:16px; background:#111827; border-radius:999px; overflow:hidden; border:1px solid rgba(148,163,184,0.28);">
                    <div style="height:100%; width:{min(avance_meta,100):.1f}%; background:linear-gradient(90deg,#38BDF8,#FDE68A,#FB7185); border-radius:999px;"></div>
                </div>
                <div style="color:#94a3b8; font-size:0.88rem; margin-top:6px;">Avance proyectado frente a la meta anual: {avance_meta:.1f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ======================================================
        # CAPACIDAD DE AHORRO MENSUAL: VALOR Y PORCENTAJE
        # Ambos gráficos respetan el periodo y los filtros activos.
        # Valor en pesos = ingresos del mes - gastos del mes.
        # Porcentaje = ahorro del mes / ingresos del mes * 100.
        # ======================================================
        st.markdown("#### Ahorro mensual: valor y porcentaje")
        st.caption(
            "Comparación mensual del dinero disponible después de gastos, "
            "expresado en pesos y como porcentaje de los ingresos del mismo mes."
        )

        capacidad_ahorro_df = resumen_flujo.copy()
        capacidad_ahorro_df["Ahorro mensual"] = (
            capacidad_ahorro_df["Ingresos"] - capacidad_ahorro_df["Gastos"]
        )
        capacidad_ahorro_df["Capacidad de ahorro %"] = capacidad_ahorro_df.apply(
            lambda fila: (
                fila["Ahorro mensual"] / fila["Ingresos"] * 100
                if fila["Ingresos"] > 0
                else 0.0
            ),
            axis=1,
        )

        ahorro_col1, ahorro_col2 = st.columns(2)

        with ahorro_col1:
            fig_ahorro_pesos = go.Figure()
            fig_ahorro_pesos.add_trace(go.Scatter(
                x=capacidad_ahorro_df["MES"],
                y=capacidad_ahorro_df["Ahorro mensual"],
                name="Ahorro mensual",
                mode="lines+markers+text",
                line=dict(color=COLOR_BALANCE, width=4, shape="spline"),
                marker=dict(size=10, color=COLOR_BALANCE),
                text=capacidad_ahorro_df["Ahorro mensual"],
                texttemplate="$%{text:,.0f}",
                textposition="top center",
                customdata=capacidad_ahorro_df[["Ingresos", "Gastos"]],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Ahorro: $%{y:,.0f}<br>"
                    "Ingresos: $%{customdata[0]:,.0f}<br>"
                    "Gastos: $%{customdata[1]:,.0f}"
                    "<extra></extra>"
                ),
            ))
            fig_ahorro_pesos.add_hline(
                y=0,
                line_width=1.5,
                line_dash="dash",
                line_color="rgba(248,113,113,0.75)",
            )
            fig_ahorro_pesos.update_layout(
                height=420,
                xaxis=dict(
                    categoryorder="array",
                    categoryarray=MESES_ORDEN,
                ),
                yaxis=dict(tickprefix="$", tickformat=",.0f"),
                margin=dict(t=65, b=35, l=55, r=25),
                showlegend=False,
            )
            st.plotly_chart(
                preparar_grafico_resumen(
                    fig_ahorro_pesos,
                    titulo="Capacidad de ahorro mensual en pesos",
                    x="Mes",
                    y="Ahorro mensual",
                    mostrar_leyenda=False,
                ),
                use_container_width=True,
                key="resumen_capacidad_ahorro_pesos",
            )

        with ahorro_col2:
            fig_ahorro_pct = go.Figure()
            fig_ahorro_pct.add_trace(go.Scatter(
                x=capacidad_ahorro_df["MES"],
                y=capacidad_ahorro_df["Capacidad de ahorro %"],
                name="Capacidad de ahorro",
                mode="lines+markers+text",
                line=dict(color="#2DD4BF", width=4, shape="spline"),
                marker=dict(size=10, color="#2DD4BF"),
                text=capacidad_ahorro_df["Capacidad de ahorro %"],
                texttemplate="%{text:.1f}%",
                textposition="top center",
                customdata=capacidad_ahorro_df[["Ahorro mensual", "Ingresos"]],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Capacidad de ahorro: %{y:.1f}%<br>"
                    "Ahorro: $%{customdata[0]:,.0f}<br>"
                    "Ingresos: $%{customdata[1]:,.0f}"
                    "<extra></extra>"
                ),
            ))
            fig_ahorro_pct.add_hline(
                y=0,
                line_width=1.5,
                line_dash="dash",
                line_color="rgba(248,113,113,0.75)",
            )
            fig_ahorro_pct.add_hline(
                y=20,
                line_width=2,
                line_dash="dot",
                line_color="rgba(253,230,138,0.85)",
                annotation_text="Meta 20%",
                annotation_position="top left",
            )
            fig_ahorro_pct.update_layout(
                height=420,
                xaxis=dict(
                    categoryorder="array",
                    categoryarray=MESES_ORDEN,
                ),
                yaxis=dict(ticksuffix="%", tickformat=".1f"),
                margin=dict(t=65, b=35, l=55, r=25),
                showlegend=False,
            )
            st.plotly_chart(
                preparar_grafico_resumen(
                    fig_ahorro_pct,
                    titulo="Capacidad de ahorro mensual en porcentaje",
                    x="Mes",
                    y="Porcentaje de ahorro",
                    mostrar_leyenda=False,
                ),
                use_container_width=True,
                key="resumen_capacidad_ahorro_porcentaje",
            )

        seccion_resumen("4", "Distribución general del dinero", "Muestra cómo se reparten los gastos y qué parte de los ingresos permanece disponible.")

        col1, col2 = st.columns(2)
        with col1:
            pie = df.groupby("GASTOS_CATEGORIA")["GASTOS_CANTIDAD"].sum().reset_index()
            total_pie = pie["GASTOS_CANTIDAD"].sum()
            fig_pie = px.pie(
                pie,
                names="GASTOS_CATEGORIA",
                values="GASTOS_CANTIDAD",
                hole=0.45,
                color="GASTOS_CATEGORIA",
                color_discrete_sequence=PALETA_NEON,
            )
            fig_pie.update_traces(
                textposition="inside",
                textinfo="percent+label",
                textfont=dict(color="#ffffff", size=12, family="DM Sans, sans-serif"),
                insidetextorientation="radial",
                marker=dict(line=dict(color="#000000", width=2.5)),
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Gasto: $%{value:,.0f}<br>"
                    "Participación: %{percent}<extra></extra>"
                ),
            )
            fig_pie.update_layout(hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="#38BDF8", font=dict(size=13, color="#f8fafc")))
            fig_pie.add_annotation(
                text=f"${total_pie:,.0f}",
                x=0.5, y=0.5, font=dict(size=18, color=COLOR_INGRESOS), showarrow=False,
            )
            st.plotly_chart(
                preparar_grafico_resumen(
                    fig_pie,
                    titulo="Distribución de gastos por categoría",
                    leyenda="Categoría",
                    mostrar_leyenda=True,
                ),
                use_container_width=True,
            )
        with col2:
            # Distribución general de los ingresos en tres grupos:
            # 1. Entretenimiento: gastos cuya categoría sea GUSTOS.
            # 2. Fijos: todos los demás gastos (nombre usado solo en este gráfico).
            # 3. No utilizado: ingresos menos gastos, sin permitir valores negativos.
            categorias_normalizadas = df["GASTOS_CATEGORIA"].astype(str).map(normalizar)
            mask_gustos = categorias_normalizadas.eq("GUSTOS")

            gasto_entretenimiento = float(
                df.loc[mask_gustos, "GASTOS_CANTIDAD"].sum()
            ) if not df.empty else 0.0
            gasto_fijos_grafico = max(float(total_gastos) - gasto_entretenimiento, 0.0)
            no_utilizado_resumen = max(float(total_ingresos) - float(total_gastos), 0.0)

            pie_general = pd.DataFrame({
                "Concepto": ["No utilizado", "Entretenimiento", "Fijos"],
                "Monto": [
                    no_utilizado_resumen,
                    gasto_entretenimiento,
                    gasto_fijos_grafico,
                ],
            })

            # Se eliminan solamente porciones de valor cero para evitar segmentos vacíos.
            pie_general = pie_general[pie_general["Monto"].gt(0)].copy()

            base_porcentaje_general = (
                float(total_ingresos)
                if total_ingresos > 0
                else float(pie_general["Monto"].sum())
            )
            pie_general["% de ingresos"] = (
                pie_general["Monto"] / base_porcentaje_general * 100
                if base_porcentaje_general > 0
                else 0.0
            )
            pie_general["Etiqueta"] = pie_general["% de ingresos"].map(
                lambda x: f"{x:.1f}%"
            )

            colores_grupos = {
                "No utilizado": "#00FF66",
                "Entretenimiento": "#C084FC",
                "Fijos": "#38BDF8",
            }

            fig_pie_general = go.Figure(go.Pie(
                labels=pie_general["Concepto"],
                values=pie_general["Monto"],
                hole=0.45,
                marker=dict(
                    colors=[colores_grupos.get(c, "#94A3B8") for c in pie_general["Concepto"]],
                    line=dict(color="#000000", width=2.5),
                ),
                text=pie_general["Etiqueta"],
                textposition="inside",
                textinfo="label+text",
                textfont=dict(color="#ffffff", size=12, family="DM Sans, sans-serif"),
                insidetextorientation="radial",
                customdata=pie_general[["% de ingresos"]],
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Valor: $%{value:,.0f}<br>"
                    "Porcentaje de los ingresos: %{customdata[0]:.2f}%"
                    "<extra></extra>"
                ),
            ))
            fig_pie_general.update_layout(
                hoverlabel=dict(
                    bgcolor="#0a0a0a",
                    bordercolor="#38BDF8",
                    font=dict(size=13, color="#f8fafc"),
                )
            )
            fig_pie_general.add_annotation(
                text=f"${total_ingresos:,.0f}<br><span style='font-size:11px'>Ingresos</span>",
                x=0.5,
                y=0.5,
                font=dict(size=17, color=COLOR_INGRESOS),
                showarrow=False,
            )
            st.plotly_chart(
                preparar_grafico_resumen(
                    fig_pie_general,
                    titulo="Distribución general sobre los ingresos",
                    leyenda="Uso de los ingresos",
                    mostrar_leyenda=True,
                ),
                use_container_width=True,
                key="resumen_distribucion_general_ingresos",
            )

            if total_gastos > total_ingresos and total_ingresos > 0:
                st.warning(
                    f"Los gastos superan los ingresos en ${total_gastos - total_ingresos:,.0f}; "
                    "por eso no existe una porción de dinero no utilizado."
                )

        seccion_resumen("7", "Análisis complementario", "Promedios de gasto y distribución de los tamaños de las transacciones; útiles para profundizar, no para la lectura inicial.")

        st.markdown("#### ⏱️ Promedios de gasto")
        promedios_df = pd.DataFrame({
            "Periodo": ["Diario", "Semanal", "Mensual"],
            "Valor": [gasto_promedio_diario, gasto_promedio_semanal, gasto_promedio_mensual],
        })
        fig_prom = px.bar(
            promedios_df,
            x="Periodo",
            y="Valor",
            text="Valor",
            color="Periodo",
            color_discrete_sequence=["#38BDF8", "#C084FC", "#34D399"],
        )
        fig_prom.update_traces(
            texttemplate="$%{text:,.0f}",
            textposition="outside",
            hovertemplate=(
                "<b>⏱️ Promedio %{x}</b><br><br>"
                "💰 Gasto promedio: <b>$%{y:,.0f}</b><br>"
                "📅 Calculado con las fechas del período filtrado"
                "<extra></extra>"
            ),
        )
        fig_prom.update_layout(height=360, showlegend=False, margin=dict(t=40,b=30,l=30,r=30))
        st.plotly_chart(
            preparar_grafico_resumen(
                fig_prom,
                titulo="Gasto promedio diario, semanal y mensual",
                x="Periodo",
                y="Valor promedio",
                mostrar_leyenda=False,
            ),
            use_container_width=True,
        )

        # Se conserva el histograma original de distribución de montos de gasto.
        st.markdown("#### Distribución de montos de gasto")
        fig_hist = px.histogram(
            df,
            x="GASTOS_CANTIDAD",
            nbins=30,
        )
        fig_hist.update_traces(
            marker=dict(
                color="#38BDF8",
                line=dict(color="#A78BFA", width=1.3),
            ),
            hovertemplate=(
                "<b>📦 Rango de gasto: $%{x:,.0f}</b><br><br>"
                "🔢 Transacciones en este rango: <b>%{y}</b><br>"
                "📊 Una barra más alta indica mayor frecuencia de movimientos"
                "<extra></extra>"
            ),
        )
        fig_hist.update_layout(
            hoverlabel=dict(
                bgcolor="#0a0a0a",
                bordercolor="#38BDF8",
                font=dict(size=13, color="#f8fafc"),
            )
        )
        fig_hist.update_xaxes(title_text="Monto del gasto")
        fig_hist.update_yaxes(title_text="Número de transacciones")
        st.plotly_chart(
            preparar_grafico_resumen(
                fig_hist,
                titulo="Distribución de montos de gasto",
                x="Monto del gasto",
                y="Número de transacciones",
                mostrar_leyenda=False,
            ),
            use_container_width=True,
            key="resumen_distribucion_montos_gasto",
        )

    if pestana_activa == etiquetas_pestanas[0]:
        st.divider()
        st.markdown("## Profundización ejecutiva")
        st.subheader("Ingresos, gastos, presupuesto y balance")
        st.caption("Cruce de ingresos transaccionales, clasificados por su fecha real, contra los gastos filtrados.")

        flujo = construir_flujo_mensual(
            gastos_df=df,
            ingresos_df=ingresos_filtrados,
            meses_sel=meses_sel,
            presupuesto_mensual=presupuesto_mensual_por_periodo or presupuesto_mensual_general,
        )

        c5, c6, c7 = st.columns(3)
        c5.metric("Capacidad de ahorro", f"{(balance / total_ingresos * 100):.1f}%" if total_ingresos else "0%")
        c6.metric("Promedio ingresos/mes", f"${flujo['Ingresos'].mean():,.0f}" if not flujo.empty else "$0")
        c7.metric("Promedio gastos/mes", f"${flujo['Gastos'].mean():,.0f}" if not flujo.empty else "$0")

        col1, col2 = st.columns(2)
        with col1:
            fig_cmp = go.Figure()

            # Color dinámico de la barra de gastos:
            # Azul neón  = gastos por debajo o igual al presupuesto mensual.
            # Rosa neón  = gastos por encima del presupuesto, pero sin superar los ingresos.
            # Rojo fuerte = gastos por encima de los ingresos del mes.
            def color_gasto_ejecutivo(gasto, presupuesto, ingreso):
                if gasto > ingreso and ingreso > 0:
                    return "#FF0033"  # rojo fuerte
                if presupuesto > 0 and gasto > presupuesto:
                    return "#FF2E9A"  # rosa neón
                return "#00F0FF"      # azul neón

            colores_gastos = [
                color_gasto_ejecutivo(g, p, i)
                for g, p, i in zip(
                    flujo["Gastos"],
                    flujo["Presupuesto mensual"],
                    flujo["Ingresos"],
                )
            ]

            fig_cmp.add_trace(go.Bar(
                x=flujo["MES"], y=flujo["Gastos"], name="Gastos",
                marker=dict(
                    color=colores_gastos,
                    line=dict(color=colores_gastos, width=1.5)
                ),
                customdata=flujo[["Ingresos", "Presupuesto mensual", "Balance"]],
                text=flujo["Gastos"], texttemplate="$%{text:,.0f}", textposition="outside",
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Gastos: $%{y:,.0f}<br>"
                    "Ingresos: $%{customdata[0]:,.0f}<br>"
                    "Presupuesto: $%{customdata[1]:,.0f}<br>"
                    "Balance: $%{customdata[2]:,.0f}"
                    "<extra></extra>"
                ),
            ))
            fig_cmp.add_trace(go.Scatter(
                x=flujo["MES"], y=flujo["Ingresos"], name="Ingresos",
                mode="lines+markers+text", line=dict(color=COLOR_INGRESOS, width=4, shape="spline"),
                marker=dict(size=10, color=COLOR_INGRESOS), text=flujo["Ingresos"],
                texttemplate="$%{text:,.0f}", textposition="top center",
                customdata=flujo[["Gastos", "Presupuesto mensual", "Balance"]],
                hovertemplate=(
                    "<b>📅 %{x}</b><br><br>"
                    "💵 Ingresos: <b>$%{y:,.0f}</b><br>"
                    "🧾 Gastos: $%{customdata[0]:,.0f}<br>"
                    "🎯 Presupuesto: $%{customdata[1]:,.0f}<br>"
                    "⚖️ Balance: $%{customdata[2]:,.0f}"
                    "<extra></extra>"
                ),
            ))
            fig_cmp.add_trace(go.Scatter(
                x=flujo["MES"], y=flujo["Presupuesto mensual"], name="Presupuesto Datos!O19",
                mode="lines+markers", line=dict(color=COLOR_PRESUPUESTO, width=3, dash="dash"),
                marker=dict(size=8, color=COLOR_PRESUPUESTO),
                hovertemplate="🎯 <b>%{x}</b><br>Meta presupuestal: <b>$%{y:,.0f}</b><br>Esta línea representa el límite planificado para el mes.<extra></extra>",
            ))
            fig_cmp.add_trace(go.Scatter(
                x=flujo["MES"], y=flujo["Balance"], name="Balance",
                mode="lines+markers", line=dict(color="#B026FF", width=2.4),
                marker=dict(size=7, color="#B026FF"),
                customdata=flujo[["Ingresos", "Gastos"]],
                hovertemplate=(
                    "<b>⚖️ Balance de %{x}</b><br><br>"
                    "💵 Ingresos: $%{customdata[0]:,.0f}<br>"
                    "🧾 Gastos: $%{customdata[1]:,.0f}<br>"
                    "💰 Resultado neto: <b>$%{y:,.0f}</b>"
                    "<extra></extra>"
                ),
            ))
            fig_cmp.update_layout(
                hovermode="x unified",
                xaxis=dict(title="Mes", categoryorder="array", categoryarray=MESES_ORDEN),
                yaxis=dict(title="Valor", tickformat=",.0f"),
                bargap=0.28,
            )
            st.plotly_chart(estilo_grafico(fig_cmp, "Ejecutivo mensual: gastos, ingresos, presupuesto y balance"), use_container_width=True)
        with col2:
            st.plotly_chart(crear_gauge_salud(balance, total_ingresos), use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            fig_acum = px.area(flujo, x="MES", y="Balance acumulado", markers=True, color_discrete_sequence=["#00F0FF"])
            fig_acum.update_traces(
                customdata=flujo[["Balance", "Ingresos", "Gastos"]],
                hovertemplate=(
                    "<b>💼 Flujo acumulado · %{x}</b><br><br>"
                    "⚖️ Balance del mes: $%{customdata[0]:,.0f}<br>"
                    "💵 Ingresos: $%{customdata[1]:,.0f}<br>"
                    "🧾 Gastos: $%{customdata[2]:,.0f}<br>"
                    "📈 Balance acumulado: <b>$%{y:,.0f}</b>"
                    "<extra></extra>"
                ),
                line=dict(width=3), marker=dict(size=7, color="#00F0FF"),
                fillcolor="rgba(0,240,255,0.18)",
            )
            st.plotly_chart(estilo_grafico(fig_acum, "Flujo de caja acumulado"), use_container_width=True)
        with col4:
            fig_ahorro = px.line(flujo, x="MES", y="Capacidad ahorro %", markers=True, color_discrete_sequence=["#00F0FF"])
            fig_ahorro.add_hline(y=20, line_dash="dot", line_color="#FFEE00", annotation_text="Meta 20%")
            fig_ahorro.update_traces(
                customdata=flujo[["Balance", "Ingresos", "Gastos"]],
                hovertemplate=(
                    "<b>🏦 Capacidad de ahorro · %{x}</b><br><br>"
                    "📊 Ahorro del mes: <b>%{y:.1f}%</b><br>"
                    "⚖️ Balance: $%{customdata[0]:,.0f}<br>"
                    "💵 Ingresos: $%{customdata[1]:,.0f}<br>"
                    "🧾 Gastos: $%{customdata[2]:,.0f}<br>"
                    "🎯 Referencia recomendada: 20%"
                    "<extra></extra>"
                ),
                marker=dict(size=8),
            )
            st.plotly_chart(estilo_grafico(fig_ahorro, "Capacidad de ahorro mensual"), use_container_width=True)

        st.markdown("#### Resumen mensual ejecutivo")
        st.dataframe(flujo, use_container_width=True, hide_index=True)

    if pestana_activa == etiquetas_pestanas[1]:
        contexto_pestana("¿En qué se me va el dinero?", "Organiza todos los gastos por categoría, subcategoría, naturaleza y transacciones para identificar qué movimientos explican el uso del dinero.")

        # ======================================================
        # 1. PANORAMA GENERAL DEL GASTO
        # ======================================================
        st.markdown("## 1. Panorama general del gasto")
        st.caption("Respuesta rápida antes de entrar en categorías, subcategorías y movimientos individuales.")

        gastos_panorama = agregar_tipo_gasto(df)
        resumen_cat_panorama = (
            df.groupby("GASTOS_CATEGORIA", dropna=False)["GASTOS_CANTIDAD"]
            .sum().sort_values(ascending=False)
        ) if not df.empty else pd.Series(dtype=float)
        resumen_sub_panorama = (
            df.groupby("GASTOS_SUBCATEGORIA", dropna=False)["GASTOS_CANTIDAD"]
            .sum().sort_values(ascending=False)
        ) if not df.empty else pd.Series(dtype=float)

        categoria_principal = str(resumen_cat_panorama.index[0]) if not resumen_cat_panorama.empty else "Sin datos"
        subcategoria_principal = str(resumen_sub_panorama.index[0]) if not resumen_sub_panorama.empty else "Sin datos"
        total_panorama = float(df["GASTOS_CANTIDAD"].sum()) if not df.empty else 0.0
        fijo_panorama = float(gastos_panorama.loc[gastos_panorama["TIPO_GASTO"].eq("Fijo"), "GASTOS_CANTIDAD"].sum()) if not gastos_panorama.empty else 0.0
        variable_panorama = float(gastos_panorama.loc[gastos_panorama["TIPO_GASTO"].eq("Variable"), "GASTOS_CANTIDAD"].sum()) if not gastos_panorama.empty else 0.0
        pct_fijo_panorama = fijo_panorama / total_panorama * 100 if total_panorama else 0.0
        pct_variable_panorama = variable_panorama / total_panorama * 100 if total_panorama else 0.0

        gp1, gp2, gp3 = st.columns(3)
        gp1.metric("Gasto total", f"${total_panorama:,.0f}")
        gp2.metric("Transacciones", f"{len(df):,}")
        gp3.metric("Categoría principal", categoria_principal)
        gp4, gp5, gp6 = st.columns(3)
        gp4.metric("Subcategoría principal", subcategoria_principal)
        gp5.metric("Gasto fijo", f"{pct_fijo_panorama:.1f}%")
        gp6.metric("Gasto variable", f"{pct_variable_panorama:.1f}%")

        # ======================================================
        # 2. CONCENTRACIÓN Y NATURALEZA DEL GASTO
        # ======================================================
        st.markdown("## 2. Concentración y naturaleza del gasto")
        st.caption("Identifica si el gasto está concentrado en pocas categorías o en movimientos excepcionales.")

        top3_monto = float(resumen_cat_panorama.head(3).sum()) if not resumen_cat_panorama.empty else 0.0
        top3_pct = top3_monto / total_panorama * 100 if total_panorama else 0.0
        top10_tx_monto = float(df.nlargest(min(10, len(df)), "GASTOS_CANTIDAD")["GASTOS_CANTIDAD"].sum()) if not df.empty else 0.0
        top10_tx_pct = top10_tx_monto / total_panorama * 100 if total_panorama else 0.0
        extraordinario_panorama = float(
            gastos_panorama.loc[gastos_panorama["TIPO_GASTO"].eq("Extraordinario"), "GASTOS_CANTIDAD"].sum()
        ) if not gastos_panorama.empty else 0.0
        gasto_habitual = max(total_panorama - extraordinario_panorama, 0.0)
        pct_extraordinario_panorama = extraordinario_panorama / total_panorama * 100 if total_panorama else 0.0

        cg1, cg2, cg3, cg4 = st.columns(4)
        cg1.metric("Top 3 categorías", f"{top3_pct:.1f}%", f"${top3_monto:,.0f}")
        cg2.metric("Top 10 movimientos", f"{top10_tx_pct:.1f}%", f"${top10_tx_monto:,.0f}")
        cg3.metric("Gasto habitual", f"${gasto_habitual:,.0f}")
        cg4.metric("Extraordinario", f"{pct_extraordinario_panorama:.1f}%", f"${extraordinario_panorama:,.0f}")

        if top3_pct >= 70:
            st.warning(f"El gasto está muy concentrado: las tres categorías principales explican el {top3_pct:.1f}% del total.")
        elif top3_pct >= 50:
            st.info(f"Las tres categorías principales explican el {top3_pct:.1f}% del gasto.")
        else:
            st.success(f"El gasto está relativamente distribuido: las tres categorías principales representan el {top3_pct:.1f}%.")

        st.divider()
        st.markdown("## 3. ¿En qué categorías gasto?")
        st.caption(
            "Pasa el mouse sobre cada bloque para ver gasto, presupuesto, diferencia, "
            "porcentajes y número de transacciones."
        )
        st.plotly_chart(
            fig_jerarquia_categorias(df, presupuesto_cat, presupuesto_sub, tipo="treemap"),
            use_container_width=True,
        )
        st.plotly_chart(
            fig_jerarquia_categorias(df, presupuesto_cat, presupuesto_sub, tipo="sunburst"),
            use_container_width=True,
        )

        # ======================================================
        st.divider()
        st.markdown("## 4. ¿En qué subcategorías gasto?")
        st.subheader("📂 Análisis por subcategorías")
        st.caption(
            "Pasa el mouse sobre cualquier barra, porción, bloque o celda para ver el detalle completo: "
            "gasto, presupuesto, diferencia, % del total y número de transacciones."
        )
        sub_df = df.copy()
        sub_df["GASTOS_SUBCATEGORIA"] = sub_df["GASTOS_SUBCATEGORIA"].fillna("Sin subcategoría")
        sub_df["GASTOS_SUBCATEGORIA_2"] = sub_df["GASTOS_SUBCATEGORIA_2"].fillna("Sin detalle")

        total_sub = float(sub_df["GASTOS_CANTIDAD"].sum()) or 1.0

        # Presupuesto por subcategoría (toma el mayor valor si el nombre se repite entre categorías)
        lookup_sub = {}
        for cat, sub in sub_df[["GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA"]].drop_duplicates().itertuples(index=False):
            pres = buscar_presupuesto_sub(cat, sub, presupuesto_sub)
            lookup_sub[sub] = max(lookup_sub.get(sub, 0), pres)

        resumen_corto = (
            sub_df.groupby("GASTOS_SUBCATEGORIA")
            .agg(monto=("GASTOS_CANTIDAD", "sum"), transacciones=("GASTOS_CANTIDAD", "count"))
            .reset_index()
            .sort_values("monto", ascending=False)
        )
        resumen_corto["presupuesto"] = resumen_corto["GASTOS_SUBCATEGORIA"].map(lambda s: lookup_sub.get(s, 0))
        resumen_corto["pct_total"] = resumen_corto["monto"] / total_sub * 100
        resumen_corto["hover"] = [
            tooltip_jerarquia("", r.GASTOS_SUBCATEGORIA, r.monto, r.presupuesto, r.transacciones, r.pct_total)
            for r in resumen_corto.itertuples()
        ]

        col1, col2 = st.columns(2)
        with col1:
            fig_bar_sub = go.Figure(
                go.Bar(
                    x=resumen_corto["monto"],
                    y=resumen_corto["GASTOS_SUBCATEGORIA"],
                    orientation="h",
                    marker=dict(
                        color=resumen_corto["monto"],
                        colorscale=COLORSCALE_SUBCATEGORIAS,
                        line=dict(color="rgba(196,181,253,0.6)", width=1),
                    ),
                    customdata=resumen_corto["hover"],
                    hovertemplate="%{customdata}<extra></extra>",
                )
            )
            fig_bar_sub.update_layout(
                xaxis_title="Monto",
                yaxis_title="Subcategoría",
                yaxis=dict(autorange="reversed"),
                hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="#6366f1", font=dict(size=13, color="#f8fafc")),
            )
            st.plotly_chart(
                estilo_grafico(fig_bar_sub, titulo="Gasto total por subcategoría"),
                use_container_width=True,
            )
        with col2:
            top10 = resumen_corto.head(10)
            fig_pie_sub = go.Figure(
                go.Pie(
                    labels=top10["GASTOS_SUBCATEGORIA"],
                    values=top10["monto"],
                    hole=0.4,
                    marker=dict(colors=PALETA_SUBCATEGORIAS, line=dict(color="#000000", width=2)),
                    textposition="inside",
                    textinfo="percent+label",
                    textfont=dict(color="#ffffff", size=11),
                    customdata=top10["hover"],
                    hovertemplate="%{customdata}<extra></extra>",
                )
            )
            fig_pie_sub.update_layout(
                hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="#6366f1", font=dict(size=13, color="#f8fafc")),
            )
            st.plotly_chart(
                estilo_grafico(fig_pie_sub, titulo="Top 10 subcategorías"),
                use_container_width=True,
            )

        st.markdown("#### Jerarquía: categoría → subcategoría → detalle")
        st.plotly_chart(
            fig_jerarquia_subcategorias(sub_df, presupuesto_sub, tipo="treemap"),
            use_container_width=True,
        )

    if pestana_activa == etiquetas_pestanas[1]:
        st.divider()
        # ======================================================
        # 4. TRANSACCIONES QUE EXPLICAN EL GASTO
        # ======================================================
        st.markdown("## 5. ¿Qué movimientos explican el gasto?")
        st.caption("Identifica las operaciones individuales de mayor valor y las descripciones que más se repiten.")

        if df.empty:
            st.info("No hay transacciones para mostrar con los filtros actuales.")
        else:
            columnas_top = [c for c in [
                "GASTOS_FECHA", "GASTOS_DESCRIPCION", "GASTOS_CATEGORIA",
                "GASTOS_SUBCATEGORIA", "GASTOS_SUBCATEGORIA_2", "GASTOS_CANTIDAD"
            ] if c in df.columns]
            top_movimientos = df[columnas_top].sort_values("GASTOS_CANTIDAD", ascending=False).head(20).copy()
            if "GASTOS_FECHA" in top_movimientos.columns:
                top_movimientos["GASTOS_FECHA"] = pd.to_datetime(top_movimientos["GASTOS_FECHA"], errors="coerce").dt.strftime("%d/%m/%Y")

            tm1, tm2 = st.columns([1.35, 1])
            with tm1:
                st.markdown("#### Top 20 transacciones")
                st.dataframe(top_movimientos, use_container_width=True, hide_index=True)
            with tm2:
                if "GASTOS_DESCRIPCION" in df.columns:
                    descripcion_resumen = (
                        df.assign(GASTOS_DESCRIPCION=df["GASTOS_DESCRIPCION"].fillna("Sin descripción"))
                        .groupby("GASTOS_DESCRIPCION", as_index=False)
                        .agg(Monto=("GASTOS_CANTIDAD", "sum"), Transacciones=("GASTOS_CANTIDAD", "count"))
                        .sort_values("Monto", ascending=False).head(12)
                    )
                    descripcion_resumen["Promedio"] = (
                        descripcion_resumen["Monto"] / descripcion_resumen["Transacciones"]
                    )
                    fig_desc = px.bar(
                        descripcion_resumen.sort_values("Monto"), x="Monto", y="GASTOS_DESCRIPCION",
                        orientation="h", text="Monto", color="Monto", color_continuous_scale="Turbo",
                        custom_data=["Transacciones", "Promedio"],
                    )
                    fig_desc.update_traces(
                        texttemplate="$%{text:,.0f}",
                        textposition="outside",
                        hovertemplate=(
                            "<b>🧾 %{y}</b><br><br>"
                            "💰 Gasto acumulado: <b>$%{x:,.0f}</b><br>"
                            "🔁 Número de movimientos: %{customdata[0]}<br>"
                            "📊 Promedio por movimiento: $%{customdata[1]:,.0f}"
                            "<extra></extra>"
                        ),
                    )
                    st.plotly_chart(estilo_grafico(fig_desc, "Descripciones con mayor gasto acumulado"), use_container_width=True)

        st.divider()
        st.markdown("## 6. Recurrencia, frecuencia y monto")
        st.caption("Distingue cobros repetitivos, gastos hormiga y compras de alto impacto.")

        analisis_mov = df.copy()
        analisis_mov["DESCRIPCION_ANALISIS"] = analisis_mov.get(
            "GASTOS_DESCRIPCION", pd.Series(index=analisis_mov.index, dtype=str)
        ).fillna("Sin descripción").astype(str).str.strip()

        recurrentes = (
            analisis_mov.groupby("DESCRIPCION_ANALISIS", dropna=False)
            .agg(Monto=("GASTOS_CANTIDAD", "sum"), Frecuencia=("GASTOS_CANTIDAD", "count"))
            .reset_index()
        ) if not analisis_mov.empty else pd.DataFrame(columns=["DESCRIPCION_ANALISIS", "Monto", "Frecuencia"])
        recurrentes = recurrentes[recurrentes["Frecuencia"] >= 2].sort_values("Monto", ascending=False)
        monto_recurrente = float(recurrentes["Monto"].sum()) if not recurrentes.empty else 0.0
        pct_recurrente = monto_recurrente / total_panorama * 100 if total_panorama else 0.0

        umbral_hormiga = st.number_input(
            "Umbral para gasto pequeño",
            min_value=0,
            value=30000,
            step=5000,
            help="Los movimientos iguales o inferiores a este valor se analizan como gastos pequeños acumulados.",
            key="umbral_gasto_hormiga_v913",
        )
        gastos_pequenos = analisis_mov[analisis_mov["GASTOS_CANTIDAD"] <= umbral_hormiga] if not analisis_mov.empty else analisis_mov
        monto_pequeno = float(gastos_pequenos["GASTOS_CANTIDAD"].sum()) if not gastos_pequenos.empty else 0.0
        pct_pequeno = monto_pequeno / total_panorama * 100 if total_panorama else 0.0

        rr1, rr2, rr3, rr4 = st.columns(4)
        rr1.metric("Descripciones recurrentes", len(recurrentes))
        rr2.metric("Monto recurrente", f"${monto_recurrente:,.0f}", f"{pct_recurrente:.1f}%")
        rr3.metric("Movimientos pequeños", len(gastos_pequenos))
        rr4.metric("Acumulado pequeño", f"${monto_pequeno:,.0f}", f"{pct_pequeno:.1f}%")

        frecuencia_sub = (
            analisis_mov.groupby("GASTOS_SUBCATEGORIA", dropna=False)
            .agg(Monto=("GASTOS_CANTIDAD", "sum"), Frecuencia=("GASTOS_CANTIDAD", "count"), Promedio=("GASTOS_CANTIDAD", "mean"))
            .reset_index()
            .rename(columns={"GASTOS_SUBCATEGORIA": "Subcategoría"})
        ) if not analisis_mov.empty else pd.DataFrame(columns=["Subcategoría", "Monto", "Frecuencia", "Promedio"])

        frecuencia_sub["Subcategoría"] = frecuencia_sub["Subcategoría"].fillna(
            "Sin subcategoría"
        )
        frecuencia_sub["Etiqueta"] = ""
        frecuencia_sub["Posición etiqueta"] = "top center"
        indices_etiquetados = list(dict.fromkeys(
            frecuencia_sub.nlargest(10, "Monto").index.tolist()
            + frecuencia_sub.nlargest(6, "Frecuencia").index.tolist()
        ))
        posiciones_etiqueta = [
            "top center", "bottom center", "top left", "top right",
            "bottom left", "bottom right", "middle left", "middle right",
        ]
        for orden_etiqueta, indice_etiqueta in enumerate(indices_etiquetados):
            frecuencia_sub.loc[indice_etiqueta, "Etiqueta"] = frecuencia_sub.loc[
                indice_etiqueta, "Subcategoría"
            ]
            frecuencia_sub.loc[indice_etiqueta, "Posición etiqueta"] = (
                posiciones_etiqueta[orden_etiqueta % len(posiciones_etiqueta)]
            )

        fig_frecuencia = px.scatter(
            frecuencia_sub,
            x="Frecuencia",
            y="Monto",
            size="Promedio",
            size_max=34,
            color="Monto",
            color_continuous_scale=["#075985", "#00E5FF", "#00FF88", "#FFEE00"],
            hover_name="Subcategoría",
            text="Etiqueta",
            custom_data=["Promedio"],
            title="Frecuencia frente a monto por subcategoría",
        )
        fig_frecuencia.update_traces(
            textposition=frecuencia_sub["Posición etiqueta"].tolist(),
            textfont=dict(color="#F8FAFC", size=10),
            marker=dict(
                opacity=0.82,
                line=dict(color="rgba(255,255,255,0.58)", width=1),
            ),
            hovertemplate=(
                "<b>%{hovertext}</b><br>"
                "Transacciones: %{x}<br>"
                "Monto acumulado: $%{y:,.0f}<br>"
                "Promedio por movimiento: $%{customdata[0]:,.0f}"
                "<extra></extra>"
            ),
        )
        fig_frecuencia.update_layout(
            height=650,
            margin=dict(l=85, r=85, t=85, b=75),
            coloraxis_colorbar=dict(
                title="Monto acumulado",
                tickprefix="$",
                tickformat="~s",
            ),
            hoverlabel=dict(
                bgcolor="#07111F",
                bordercolor="#00E5FF",
                font=dict(color="#F8FAFC", size=13),
            ),
        )
        fig_frecuencia.update_xaxes(
            title="Número de transacciones",
            dtick=1,
            automargin=True,
        )
        fig_frecuencia.update_yaxes(
            title="Monto acumulado",
            tickprefix="$",
            tickformat="~s",
            automargin=True,
        )
        st.caption(
            "Se etiquetan las subcategorías de mayor monto o frecuencia para evitar cruces. "
            "Pasa el cursor sobre cualquier burbuja para ver su detalle."
        )
        fig_frecuencia = estilo_grafico(
            fig_frecuencia,
            "Frecuencia frente a monto por subcategoría",
        )
        fig_frecuencia.update_layout(margin=dict(l=85, r=85, t=85, b=75))
        st.plotly_chart(
            fig_frecuencia,
            use_container_width=True,
        )

        st.markdown("#### Cobros y descripciones recurrentes")
        st.caption(
            "Listado de descripciones que aparecen dos o más veces en el período filtrado, "
            "ordenadas por su monto acumulado."
        )
        st.dataframe(recurrentes.head(15), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("## 7. Calidad de los registros")
        st.caption("Mide qué tan confiable es la clasificación utilizada por los gráficos.")

        sin_categoria = int(analisis_mov.get("GASTOS_CATEGORIA", pd.Series(dtype=object)).isna().sum())
        sin_subcategoria = int(analisis_mov.get("GASTOS_SUBCATEGORIA", pd.Series(dtype=object)).isna().sum())
        sin_descripcion = int(analisis_mov["DESCRIPCION_ANALISIS"].isin(["", "Sin descripción", "nan", "None"]).sum())
        cols_dup = [c for c in ["GASTOS_FECHA", "GASTOS_CANTIDAD", "GASTOS_DESCRIPCION", "GASTOS_CATEGORIA"] if c in analisis_mov.columns]
        posibles_duplicados = int(analisis_mov.duplicated(subset=cols_dup, keep=False).sum()) if cols_dup else 0

        dq1, dq2, dq3, dq4 = st.columns(4)
        dq1.metric("Sin categoría", sin_categoria)
        dq2.metric("Sin subcategoría", sin_subcategoria)
        dq3.metric("Sin descripción", sin_descripcion)
        dq4.metric("Posibles duplicados", posibles_duplicados)

        if posibles_duplicados:
            with st.expander("Revisar posibles duplicados"):
                st.dataframe(
                    analisis_mov[analisis_mov.duplicated(subset=cols_dup, keep=False)].sort_values(cols_dup),
                    use_container_width=True,
                    hide_index=True,
                )

        st.divider()
        st.markdown("## 8. ¿Qué gastos son fijos, variables o extraordinarios?")
        st.markdown("## Clasificación: fijos, variables y otros tipos")
        st.subheader("🔁 Gastos por tipo")
        st.caption(
            "El dashboard respeta la columna Fijo/Variable de la hoja Transaccional. "
            "Acepta Fijo, Variable, Extraordinario y Prescindible; si la celda está vacía, clasifica automáticamente."
        )

        df_tipo = agregar_tipo_gasto(df)

        if df_tipo.empty:
            st.warning("No hay gastos para clasificar con los filtros seleccionados.")
        else:
            tipo_resumen = (
                df_tipo.groupby("TIPO_GASTO", as_index=False)["GASTOS_CANTIDAD"]
                .sum()
                .sort_values("GASTOS_CANTIDAD", ascending=False)
            )
            total_tipo = float(tipo_resumen["GASTOS_CANTIDAD"].sum()) or 1.0
            tipo_resumen["PARTICIPACION"] = tipo_resumen["GASTOS_CANTIDAD"] / total_tipo * 100

            fijo_total = float(tipo_resumen.loc[tipo_resumen["TIPO_GASTO"] == "Fijo", "GASTOS_CANTIDAD"].sum())
            variable_total = float(tipo_resumen.loc[tipo_resumen["TIPO_GASTO"] == "Variable", "GASTOS_CANTIDAD"].sum())
            extraordinario_total = float(tipo_resumen.loc[tipo_resumen["TIPO_GASTO"] == "Extraordinario", "GASTOS_CANTIDAD"].sum())
            prescindible_total = float(tipo_resumen.loc[tipo_resumen["TIPO_GASTO"] == "Prescindible", "GASTOS_CANTIDAD"].sum())
            pct_fijo = fijo_total / total_tipo * 100
            pct_variable = variable_total / total_tipo * 100
            pct_extraordinario = extraordinario_total / total_tipo * 100
            pct_prescindible = prescindible_total / total_tipo * 100

            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.metric("Fijos", f"${fijo_total:,.0f}", f"{pct_fijo:.1f}%")
            k2.metric("Variables", f"${variable_total:,.0f}", f"{pct_variable:.1f}%")
            k3.metric("Extraordinarios", f"${extraordinario_total:,.0f}", f"{pct_extraordinario:.1f}%")
            k4.metric("Prescindibles", f"${prescindible_total:,.0f}", f"{pct_prescindible:.1f}%")
            k5.metric("Total clasificado", f"${total_tipo:,.0f}")
            k6.metric("Transacciones", len(df_tipo))

            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(fig_fijos_variables_pie(tipo_resumen), use_container_width=True)
            with col2:
                tipo_mes = (
                    df_tipo.groupby(["MES", "TIPO_GASTO"], as_index=False)["GASTOS_CANTIDAD"]
                    .sum()
                )
                tipo_mes = ordenar_por_mes(tipo_mes)
                st.plotly_chart(fig_fijos_variables_mensual(tipo_mes), use_container_width=True)

            st.markdown("#### Detalle por categoría")
            detalle_categoria = (
                df_tipo.groupby(["TIPO_GASTO", "GASTOS_CATEGORIA"], as_index=False)
                .agg(
                    MONTO=("GASTOS_CANTIDAD", "sum"),
                    TRANSACCIONES=("GASTOS_CANTIDAD", "count"),
                )
                .sort_values(["TIPO_GASTO", "MONTO"], ascending=[True, False])
            )
            detalle_categoria["PARTICIPACION_%"] = detalle_categoria["MONTO"] / total_tipo * 100
            st.dataframe(detalle_categoria, use_container_width=True, hide_index=True)

            st.markdown("#### Auditoría de clasificación")
            st.dataframe(
                df_tipo[[
                    "TIPO_GASTO", "MES", "GASTOS_FECHA", "GASTOS_CANTIDAD",
                    "GASTOS_DESCRIPCION", "GASTOS_CATEGORIA",
                    "GASTOS_SUBCATEGORIA", "GASTOS_SUBCATEGORIA_2"
                ]].sort_values(["TIPO_GASTO", "MES", "GASTOS_CANTIDAD"], ascending=[True, True, False]),
                use_container_width=True,
                hide_index=True,
            )
            csv_tipo = df_tipo.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar gastos clasificados (CSV)",
                csv_tipo,
                "gastos_por_tipo.csv",
                "text/csv",
            )

    if pestana_activa == etiquetas_pestanas[2]:
        contexto_pestana("¿Cómo he evolucionado?", "Compara el comportamiento mensual de ingresos, gastos, balance y desviaciones para reconocer mejoras o deterioros.")
        st.markdown("## Evolución mensual")
        st.subheader("📅 Tendencias mensuales")
        dias_con_gasto_tendencias = max(df["GASTOS_FECHA"].dropna().dt.normalize().nunique(), 1) if not df.empty else 1
        gasto_promedio_diario = total_gastos / dias_con_gasto_tendencias
        st.caption(
            "Barras = gastos mensuales filtrados · Línea verde = ingresos mensuales · "
            "la línea del balance permite reconocer mejoras o deterioros. El cumplimiento presupuestal se analiza en Presupuesto."
        )

        # ======================================================
        # BASE MENSUAL ÚNICA: INGRESOS + GASTOS + PRESUPUESTO
        # ======================================================
        tendencia = construir_flujo_mensual(
            gastos_df=df,
            ingresos_df=ingresos_filtrados,
            meses_sel=meses_sel,
            presupuesto_mensual=presupuesto_mensual_por_periodo or presupuesto_mensual_general,
        )

        # ======================================================
        # 1. RESUMEN DE LA EVOLUCIÓN
        # ======================================================
        tendencia = tendencia.copy()
        tendencia["Ingresos"] = pd.to_numeric(tendencia["Ingresos"], errors="coerce").fillna(0.0)
        tendencia["Gastos"] = pd.to_numeric(tendencia["Gastos"], errors="coerce").fillna(0.0)
        tendencia["Balance"] = pd.to_numeric(tendencia["Balance"], errors="coerce").fillna(0.0)

        meses_movimiento = tendencia[(tendencia["Ingresos"] != 0) | (tendencia["Gastos"] != 0)].copy()
        if meses_movimiento.empty:
            meses_movimiento = tendencia.copy()

        mes_mayor_ingreso = (
            str(meses_movimiento.loc[meses_movimiento["Ingresos"].idxmax(), "MES"])
            if not meses_movimiento.empty else "Sin datos"
        )
        mes_mayor_gasto = (
            str(meses_movimiento.loc[meses_movimiento["Gastos"].idxmax(), "MES"])
            if not meses_movimiento.empty else "Sin datos"
        )
        mejor_mes = (
            str(meses_movimiento.loc[meses_movimiento["Balance"].idxmax(), "MES"])
            if not meses_movimiento.empty else "Sin datos"
        )
        peor_mes = (
            str(meses_movimiento.loc[meses_movimiento["Balance"].idxmin(), "MES"])
            if not meses_movimiento.empty else "Sin datos"
        )
        tendencia_actual = "Sin comparación"
        if len(meses_movimiento) >= 2:
            cambio_balance = float(meses_movimiento.iloc[-1]["Balance"] - meses_movimiento.iloc[-2]["Balance"])
            tendencia_actual = "Mejorando" if cambio_balance > 0 else "Deteriorándose" if cambio_balance < 0 else "Estable"

        st.markdown("### 1. Resumen de la evolución")
        tr1, tr2, tr3, tr4, tr5 = st.columns(5)
        tr1.metric("Periodo analizado", f"{len(meses_movimiento)} mes(es)")
        tr2.metric("Mayor ingreso", mes_mayor_ingreso)
        tr3.metric("Mayor gasto", mes_mayor_gasto)
        tr4.metric("Mejor balance", mejor_mes)
        tr5.metric("Tendencia actual", tendencia_actual)

        # ======================================================
        # 2. CAMBIO FRENTE AL MES ANTERIOR
        # ======================================================
        st.markdown("### 2. Cambios frente al mes anterior")
        if len(meses_movimiento) >= 2:
            anterior = meses_movimiento.iloc[-2]
            actual = meses_movimiento.iloc[-1]

            def variacion_pct(actual_val, anterior_val):
                return ((actual_val - anterior_val) / abs(anterior_val) * 100) if anterior_val else 0.0

            ci = variacion_pct(float(actual["Ingresos"]), float(anterior["Ingresos"]))
            cg = variacion_pct(float(actual["Gastos"]), float(anterior["Gastos"]))
            cb = float(actual["Balance"] - anterior["Balance"])
            c21, c22, c23, c24 = st.columns(4)
            c21.metric("Mes comparado", f"{anterior['MES']} → {actual['MES']}")
            c22.metric("Cambio ingresos", f"{ci:+.1f}%", delta=f"${actual['Ingresos']-anterior['Ingresos']:,.0f}")
            c23.metric("Cambio gastos", f"{cg:+.1f}%", delta=f"${actual['Gastos']-anterior['Gastos']:,.0f}", delta_color="inverse")
            c24.metric("Cambio del balance", f"${cb:,.0f}", delta=f"{cb:+,.0f}")
        else:
            st.info("Se necesitan al menos dos meses con movimiento para calcular la variación mensual.")

        # ======================================================
        # GRÁFICO PRINCIPAL: GASTOS + INGRESOS + BALANCE
        # ======================================================
        fig_tend = go.Figure()

        fig_tend.add_trace(go.Bar(
            x=tendencia["MES"],
            y=tendencia["Gastos"],
            name="Gastos",
            marker=dict(
                color="rgba(96,165,250,0.78)",
                line=dict(color="rgba(147,197,253,1)", width=1.5),
            ),
            text=tendencia["Gastos"],
            texttemplate="$%{text:,.0f}",
            textposition="outside",
            customdata=tendencia[["Ingresos", "Balance", "Estado balance", "Presupuesto mensual", "Diferencia vs presupuesto", "Estado presupuesto"]],
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Gastos: $%{y:,.0f}<br>"
                "Ingresos: $%{customdata[0]:,.0f}<br>"
                "Balance: $%{customdata[1]:,.0f}<br>"
                "%{customdata[2]}<br><br>"
                "Presupuesto: $%{customdata[3]:,.0f}<br>"
                "Dif. vs presupuesto: $%{customdata[4]:,.0f}<br>"
                "%{customdata[5]}<extra></extra>"
            ),
        ))

        fig_tend.add_trace(go.Scatter(
            x=tendencia["MES"],
            y=tendencia["Ingresos"],
            name="Ingresos",
            mode="lines+markers+text",
            line=dict(color=COLOR_INGRESOS, width=4, shape="spline"),
            marker=dict(size=11, color=COLOR_INGRESOS, line=dict(color="#052e16", width=1.6)),
            text=tendencia["Ingresos"],
            texttemplate="$%{text:,.0f}",
            textposition="top center",
            customdata=tendencia[["Gastos", "Balance", "Presupuesto mensual"]],
            hovertemplate=(
                "<b>📅 %{x}</b><br><br>"
                "💵 Ingresos: <b>$%{y:,.0f}</b><br>"
                "🧾 Gastos: $%{customdata[0]:,.0f}<br>"
                "⚖️ Balance: $%{customdata[1]:,.0f}<br>"
                "🎯 Presupuesto: $%{customdata[2]:,.0f}"
                "<extra></extra>"
            ),
        ))

        fig_tend.update_layout(
            template="plotly_dark",
            height=620,
            paper_bgcolor="#000000",
            plot_bgcolor="#000000",
            font=dict(color="#E2E8F0"),
            title=dict(text="Evolución mensual de ingresos y gastos", font=dict(color="#F8FAFC")),
            xaxis=dict(
                title="Mes",
                categoryorder="array",
                categoryarray=MESES_ORDEN,
                gridcolor="rgba(148,163,184,0.12)",
            ),
            yaxis=dict(title="Valor", tickformat=",.0f", gridcolor="rgba(148,163,184,0.14)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=90, b=45, l=55, r=40),
            hoverlabel=dict(bgcolor="#0F172A", bordercolor="#38BDF8", font=dict(color="#F8FAFC")),
            bargap=0.28,
        )
        st.plotly_chart(fig_tend, use_container_width=True)

        # ======================================================
        # BARRAS DE BALANCE SEPARADAS PARA NO CONFUNDIR EL GRÁFICO PRINCIPAL
        # ======================================================
        tendencia["Color balance"] = tendencia["Balance"].apply(lambda x: COLOR_INGRESOS if x >= 0 else COLOR_GASTOS)
        fig_balance = go.Figure(go.Bar(
            x=tendencia["MES"],
            y=tendencia["Balance"],
            name="Balance",
            marker=dict(color=tendencia["Color balance"], opacity=0.82),
            text=tendencia["Balance"],
            texttemplate="$%{text:,.0f}",
            textposition="outside",
            customdata=tendencia[["Estado balance"]],
            hovertemplate=(
                "<b>⚖️ Balance de %{x}</b><br><br>"
                "💰 Resultado neto: <b>$%{y:,.0f}</b><br>"
                "📌 %{customdata[0]}"
                "<extra></extra>"
            ),
        ))
        fig_balance.add_hline(y=0, line_width=1, line_dash="dot", line_color="rgba(226,232,240,0.5)")
        fig_balance.update_layout(
            template="plotly_dark",
            height=360,
            paper_bgcolor="#000000",
            plot_bgcolor="#000000",
            title=dict(text="Balance mensual: ingresos - gastos", font=dict(color="#F8FAFC")),
            xaxis=dict(title="Mes", categoryorder="array", categoryarray=MESES_ORDEN),
            yaxis=dict(title="Balance", tickformat=",.0f"),
            showlegend=False,
            margin=dict(t=70, b=35, l=55, r=35),
        )
        st.plotly_chart(fig_balance, use_container_width=True)

        # ==============================
        # RESUMEN EJECUTIVO MENSUAL
        # ==============================
        cta, ctb, ctc, ctd = st.columns(4)
        meses_superavit = int((tendencia["Balance"] > 0).sum())
        meses_deficit = int((tendencia["Balance"] < 0).sum())
        ahorro_pct = (tendencia["Balance"].sum() / tendencia["Ingresos"].sum() * 100) if tendencia["Ingresos"].sum() else 0
        gasto_vs_ingreso_pct = (tendencia["Gastos"].sum() / tendencia["Ingresos"].sum() * 100) if tendencia["Ingresos"].sum() else 0

        cta.metric("Meses con superávit", meses_superavit)
        ctb.metric("Meses con déficit", meses_deficit)
        ctc.metric("Ahorro acumulado", f"{ahorro_pct:.1f}%")
        ctd.metric("Gasto / ingreso", f"{gasto_vs_ingreso_pct:.1f}%")

        st.dataframe(
            tendencia[[
                "MES", "Ingresos", "Gastos", "Balance",
                "Estado balance"
            ]],
            use_container_width=True,
            hide_index=True,
        )

        # ======================================================
        # 3. RANKING DE CAMBIOS POR CATEGORÍA
        # ======================================================
        st.divider()
        st.markdown("## Ranking de cambios")
        st.caption("Compara cuánto subió o bajó el gasto de cada categoría frente al mes anterior.")
        datos_cambio = df.copy()
        clave_mes_ant = None
        clave_mes_act = None
        if not datos_cambio.empty and "GASTOS_FECHA" in datos_cambio.columns:
            datos_cambio["_PERIODO_CAMBIO"] = pd.to_datetime(
                datos_cambio["GASTOS_FECHA"], errors="coerce"
            ).dt.to_period("M").astype(str)
            datos_cambio = datos_cambio[
                datos_cambio["_PERIODO_CAMBIO"].ne("NaT")
            ].copy()
            periodos_cambio = sorted(datos_cambio["_PERIODO_CAMBIO"].unique())

            if len(periodos_cambio) >= 2:
                clave_mes_ant, clave_mes_act = periodos_cambio[-2:]
                datos_cambio = datos_cambio[
                    datos_cambio["_PERIODO_CAMBIO"].isin([clave_mes_ant, clave_mes_act])
                ].copy()
            elif len(periodos_cambio) == 1:
                clave_mes_act = periodos_cambio[0]
                clave_mes_ant = str(pd.Period(clave_mes_act, freq="M") - 1)

                # Recupera el mes calendario anterior desde todo el historial,
                # respetando los filtros actuales de categoría y subcategoría.
                gastos_mes_anterior = gastos.copy()
                gastos_mes_anterior["_PERIODO_CAMBIO"] = pd.to_datetime(
                    gastos_mes_anterior["GASTOS_FECHA"], errors="coerce"
                ).dt.to_period("M").astype(str)
                gastos_mes_anterior = gastos_mes_anterior[
                    gastos_mes_anterior["_PERIODO_CAMBIO"].eq(clave_mes_ant)
                ].copy()
                if set(categorias_sel) != set(categorias):
                    gastos_mes_anterior = gastos_mes_anterior[
                        gastos_mes_anterior["GASTOS_CATEGORIA"].isin(categorias_sel)
                    ]
                if set(subcategorias_sel) != set(subcategorias):
                    gastos_mes_anterior = gastos_mes_anterior[
                        gastos_mes_anterior["GASTOS_SUBCATEGORIA"].isin(subcategorias_sel)
                    ]
                datos_cambio = pd.concat(
                    [gastos_mes_anterior, datos_cambio], ignore_index=True
                )

        if clave_mes_ant and clave_mes_act and not datos_cambio.empty:
            periodo_ant = pd.Period(clave_mes_ant, freq="M")
            periodo_act = pd.Period(clave_mes_act, freq="M")
            mes_ant = f"{MESES_ORDEN[periodo_ant.month - 1].title()} {periodo_ant.year}"
            mes_act = f"{MESES_ORDEN[periodo_act.month - 1].title()} {periodo_act.year}"

            def nombre_ranking(valor, reemplazo):
                texto = limpiar_undefined_texto(valor, "").strip()
                return texto if texto else reemplazo

            datos_cambio["GASTOS_CATEGORIA"] = datos_cambio[
                "GASTOS_CATEGORIA"
            ].map(lambda valor: nombre_ranking(valor, "Sin categoría"))
            datos_cambio["GASTOS_SUBCATEGORIA"] = datos_cambio[
                "GASTOS_SUBCATEGORIA"
            ].map(lambda valor: nombre_ranking(valor, "Sin subcategoría"))

            comp_categorias = (
                datos_cambio.pivot_table(
                    index="GASTOS_CATEGORIA",
                    columns="_PERIODO_CAMBIO",
                    values="GASTOS_CANTIDAD",
                    aggfunc="sum",
                    fill_value=0,
                )
                .reset_index()
            )
            if clave_mes_ant not in comp_categorias.columns:
                comp_categorias[clave_mes_ant] = 0.0
            if clave_mes_act not in comp_categorias.columns:
                comp_categorias[clave_mes_act] = 0.0
            comp_categorias["GASTOS_CATEGORIA"] = comp_categorias["GASTOS_CATEGORIA"].apply(
                lambda categoria: nombre_ranking(categoria, "Sin categoría")
            )
            comp_categorias["Cambio"] = (
                comp_categorias[clave_mes_act] - comp_categorias[clave_mes_ant]
            )
            comp_categorias["Cambio %"] = comp_categorias.apply(
                lambda r: (
                    r["Cambio"] / abs(r[clave_mes_ant]) * 100
                    if r[clave_mes_ant] else 0.0
                ),
                axis=1,
            )

            col_suben, col_bajan = st.columns(2)
            with col_suben:
                top_suben = comp_categorias[
                    comp_categorias["Cambio"] > 0
                ].nlargest(8, "Cambio").copy()
                if not top_suben.empty:
                    fig_suben = px.bar(
                        top_suben,
                        x="Cambio",
                        y="GASTOS_CATEGORIA",
                        orientation="h",
                        text="Cambio",
                        title=f"Categorías donde aumentó el gasto · {mes_act} vs {mes_ant}",
                        labels={
                            "Cambio": "Aumento del gasto",
                            "GASTOS_CATEGORIA": "Categoría",
                        },
                    )
                    fig_suben.update_traces(
                        name="Categorías con aumento",
                        texttemplate="$%{text:,.0f}",
                        textposition="outside",
                        marker_color="#FF2E6E",
                        customdata=top_suben[[clave_mes_ant, clave_mes_act, "Cambio %"]],
                        hovertemplate=(
                            "<b>%{y}</b><br>"
                            f"Gasto en {mes_ant}: $%{{customdata[0]:,.0f}}<br>"
                            f"Gasto en {mes_act}: $%{{customdata[1]:,.0f}}<br>"
                            "Aumento: <b>$%{x:,.0f}</b><br>"
                            "Variación: %{customdata[2]:+.1f}%<extra></extra>"
                        ),
                    )
                    fig_suben.update_layout(
                        xaxis_title="Aumento del gasto",
                        yaxis_title="Categoría",
                        yaxis=dict(autorange="reversed"),
                        showlegend=False,
                        height=390,
                    )
                    st.plotly_chart(
                        estilo_grafico(
                            fig_suben,
                            f"Categorías donde aumentó el gasto · {mes_act} vs {mes_ant}",
                        ),
                        use_container_width=True,
                    )
                else:
                    st.success(f"Ninguna categoría aumentó su gasto en {mes_act} frente a {mes_ant}.")
            with col_bajan:
                top_bajan = comp_categorias[
                    comp_categorias["Cambio"] < 0
                ].nsmallest(8, "Cambio").copy()
                if not top_bajan.empty:
                    top_bajan["Reducción"] = -top_bajan["Cambio"]
                    fig_bajan = px.bar(
                        top_bajan,
                        x="Reducción",
                        y="GASTOS_CATEGORIA",
                        orientation="h",
                        text="Reducción",
                        title=f"Categorías donde bajó el gasto · {mes_act} vs {mes_ant}",
                        labels={
                            "Reducción": "Reducción del gasto",
                            "GASTOS_CATEGORIA": "Categoría",
                        },
                    )
                    fig_bajan.update_traces(
                        name="Categorías con reducción",
                        texttemplate="$%{text:,.0f}",
                        textposition="outside",
                        marker_color="#00FF9C",
                        customdata=top_bajan[[clave_mes_ant, clave_mes_act, "Cambio %"]],
                        hovertemplate=(
                            "<b>%{y}</b><br>"
                            f"Gasto en {mes_ant}: $%{{customdata[0]:,.0f}}<br>"
                            f"Gasto en {mes_act}: $%{{customdata[1]:,.0f}}<br>"
                            "Reducción: <b>$%{x:,.0f}</b><br>"
                            "Variación: %{customdata[2]:+.1f}%<extra></extra>"
                        ),
                    )
                    fig_bajan.update_layout(
                        xaxis_title="Reducción del gasto",
                        yaxis_title="Categoría",
                        yaxis=dict(autorange="reversed"),
                        showlegend=False,
                        height=390,
                    )
                    st.plotly_chart(
                        estilo_grafico(
                            fig_bajan,
                            f"Categorías donde bajó el gasto · {mes_act} vs {mes_ant}",
                        ),
                        use_container_width=True,
                    )
                else:
                    st.info(f"Ninguna categoría redujo su gasto en {mes_act} frente a {mes_ant}.")

            st.markdown("### Ranking de cambios por subcategoría")
            st.caption(
                "Muestra los conceptos específicos que explican el aumento o la reducción "
                f"del gasto entre {mes_ant} y {mes_act}."
            )
            comp_subcategorias = (
                datos_cambio.pivot_table(
                    index=["GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA"],
                    columns="_PERIODO_CAMBIO",
                    values="GASTOS_CANTIDAD",
                    aggfunc="sum",
                    fill_value=0,
                )
                .reset_index()
            )
            if clave_mes_ant not in comp_subcategorias.columns:
                comp_subcategorias[clave_mes_ant] = 0.0
            if clave_mes_act not in comp_subcategorias.columns:
                comp_subcategorias[clave_mes_act] = 0.0
            comp_subcategorias["Concepto"] = (
                comp_subcategorias["GASTOS_CATEGORIA"].map(
                    lambda valor: nombre_ranking(valor, "Sin categoría")
                )
                + " › "
                + comp_subcategorias["GASTOS_SUBCATEGORIA"].map(
                    lambda valor: nombre_ranking(valor, "Sin subcategoría")
                )
            )
            comp_subcategorias["Cambio"] = (
                comp_subcategorias[clave_mes_act] - comp_subcategorias[clave_mes_ant]
            )
            comp_subcategorias["Cambio %"] = comp_subcategorias.apply(
                lambda fila: (
                    fila["Cambio"] / abs(fila[clave_mes_ant]) * 100
                    if fila[clave_mes_ant] else 0.0
                ),
                axis=1,
            )
            comp_subcategorias["Variación"] = comp_subcategorias.apply(
                lambda fila: (
                    f"{fila['Cambio %']:+.1f}%"
                    if fila[clave_mes_ant] else "Nuevo gasto en el mes"
                ),
                axis=1,
            )

            col_subcat_suben, col_subcat_bajan = st.columns(2)
            with col_subcat_suben:
                subcat_suben = comp_subcategorias[
                    comp_subcategorias["Cambio"] > 0
                ].nlargest(8, "Cambio").copy()
                if not subcat_suben.empty:
                    fig_subcat_suben = px.bar(
                        subcat_suben,
                        x="Cambio",
                        y="Concepto",
                        orientation="h",
                        text="Cambio",
                        labels={
                            "Cambio": "Aumento del gasto",
                            "Concepto": "Subcategoría",
                        },
                    )
                    fig_subcat_suben.update_traces(
                        name="Subcategorías con aumento",
                        texttemplate="$%{text:,.0f}",
                        textposition="outside",
                        marker_color="#FF2E6E",
                        customdata=subcat_suben[
                            [clave_mes_ant, clave_mes_act, "Variación"]
                        ],
                        hovertemplate=(
                            "<b>%{y}</b><br>"
                            f"Gasto en {mes_ant}: $%{{customdata[0]:,.0f}}<br>"
                            f"Gasto en {mes_act}: $%{{customdata[1]:,.0f}}<br>"
                            "Aumento: <b>$%{x:,.0f}</b><br>"
                            "Variación: %{customdata[2]}<extra></extra>"
                        ),
                    )
                    fig_subcat_suben.update_layout(
                        xaxis_title="Aumento del gasto",
                        yaxis_title="Subcategoría",
                        yaxis=dict(autorange="reversed"),
                        showlegend=False,
                        height=430,
                    )
                    st.plotly_chart(
                        estilo_grafico(
                            fig_subcat_suben,
                            f"Subcategorías donde aumentó el gasto · {mes_act} vs {mes_ant}",
                        ),
                        use_container_width=True,
                    )
                else:
                    st.success(
                        f"Ninguna subcategoría aumentó su gasto en {mes_act} frente a {mes_ant}."
                    )

            with col_subcat_bajan:
                subcat_bajan = comp_subcategorias[
                    comp_subcategorias["Cambio"] < 0
                ].nsmallest(8, "Cambio").copy()
                if not subcat_bajan.empty:
                    subcat_bajan["Reducción"] = -subcat_bajan["Cambio"]
                    fig_subcat_bajan = px.bar(
                        subcat_bajan,
                        x="Reducción",
                        y="Concepto",
                        orientation="h",
                        text="Reducción",
                        labels={
                            "Reducción": "Reducción del gasto",
                            "Concepto": "Subcategoría",
                        },
                    )
                    fig_subcat_bajan.update_traces(
                        name="Subcategorías con reducción",
                        texttemplate="$%{text:,.0f}",
                        textposition="outside",
                        marker_color="#00FF9C",
                        customdata=subcat_bajan[
                            [clave_mes_ant, clave_mes_act, "Variación"]
                        ],
                        hovertemplate=(
                            "<b>%{y}</b><br>"
                            f"Gasto en {mes_ant}: $%{{customdata[0]:,.0f}}<br>"
                            f"Gasto en {mes_act}: $%{{customdata[1]:,.0f}}<br>"
                            "Reducción: <b>$%{x:,.0f}</b><br>"
                            "Variación: %{customdata[2]}<extra></extra>"
                        ),
                    )
                    fig_subcat_bajan.update_layout(
                        xaxis_title="Reducción del gasto",
                        yaxis_title="Subcategoría",
                        yaxis=dict(autorange="reversed"),
                        showlegend=False,
                        height=430,
                    )
                    st.plotly_chart(
                        estilo_grafico(
                            fig_subcat_bajan,
                            f"Subcategorías donde bajó el gasto · {mes_act} vs {mes_ant}",
                        ),
                        use_container_width=True,
                    )
                else:
                    st.info(
                        f"Ninguna subcategoría redujo su gasto en {mes_act} frente a {mes_ant}."
                    )
        else:
            st.info("Selecciona al menos un mes con gastos para calcular el cambio frente al mes anterior.")

        # ======================================================
        # 4. EVOLUCIÓN DEL AHORRO Y COMPARACIÓN CON PROMEDIO
        # ======================================================
        st.divider()
        st.markdown("## Evolución del ahorro")
        tendencia["Ahorro %"] = tendencia.apply(
            lambda r: (r["Balance"] / r["Ingresos"] * 100) if r["Ingresos"] else 0.0, axis=1
        )
        ahorro_cols = st.columns(2)
        with ahorro_cols[0]:
            fig_ahorro_t = go.Figure(go.Bar(
                x=tendencia["MES"], y=tendencia["Balance"],
                marker_color=[COLOR_INGRESOS if v >= 0 else COLOR_GASTOS for v in tendencia["Balance"]],
                text=tendencia["Balance"], texttemplate="$%{text:,.0f}", textposition="outside",
                customdata=tendencia[["Ingresos", "Gastos", "Ahorro %"]],
                hovertemplate=(
                    "<b>🏦 Ahorro mensual · %{x}</b><br><br>"
                    "💵 Ingresos: $%{customdata[0]:,.0f}<br>"
                    "🧾 Gastos: $%{customdata[1]:,.0f}<br>"
                    "💰 Ahorro neto: <b>$%{y:,.0f}</b><br>"
                    "📊 Capacidad de ahorro: %{customdata[2]:.1f}%"
                    "<extra></extra>"
                )
            ))
            fig_ahorro_t.update_layout(height=390, showlegend=False, xaxis=dict(categoryorder="array", categoryarray=MESES_ORDEN))
            st.plotly_chart(estilo_grafico(fig_ahorro_t, "Ahorro mensual en pesos"), use_container_width=True)
        with ahorro_cols[1]:
            fig_ahorro_pct_t = go.Figure(go.Scatter(
                x=tendencia["MES"], y=tendencia["Ahorro %"], mode="lines+markers+text",
                line=dict(color="#2DD4BF", width=4, shape="spline"), marker=dict(size=10),
                text=tendencia["Ahorro %"], texttemplate="%{text:.1f}%", textposition="top center",
                customdata=tendencia[["Balance", "Ingresos", "Gastos"]],
                hovertemplate=(
                    "<b>📊 Capacidad de ahorro · %{x}</b><br><br>"
                    "🏦 Porcentaje ahorrado: <b>%{y:.1f}%</b><br>"
                    "⚖️ Balance: $%{customdata[0]:,.0f}<br>"
                    "💵 Ingresos: $%{customdata[1]:,.0f}<br>"
                    "🧾 Gastos: $%{customdata[2]:,.0f}<br>"
                    "🎯 Referencia: 20%"
                    "<extra></extra>"
                )
            ))
            fig_ahorro_pct_t.add_hline(y=20, line_dash="dot", line_color="#FFEE00", annotation_text="Referencia 20%")
            fig_ahorro_pct_t.update_layout(height=390, showlegend=False, xaxis=dict(categoryorder="array", categoryarray=MESES_ORDEN))
            st.plotly_chart(estilo_grafico(fig_ahorro_pct_t, "Ahorro como porcentaje del ingreso"), use_container_width=True)

        promedio_ingresos = float(meses_movimiento["Ingresos"].mean()) if not meses_movimiento.empty else 0.0
        promedio_gastos = float(meses_movimiento["Gastos"].mean()) if not meses_movimiento.empty else 0.0
        promedio_balance = float(meses_movimiento["Balance"].mean()) if not meses_movimiento.empty else 0.0
        ultimo = meses_movimiento.iloc[-1] if not meses_movimiento.empty else None
        if ultimo is not None:
            cp1, cp2, cp3 = st.columns(3)
            cp1.metric("Ingreso actual vs promedio", f"${ultimo['Ingresos']:,.0f}", delta=f"{((ultimo['Ingresos']/promedio_ingresos-1)*100) if promedio_ingresos else 0:+.1f}%")
            cp2.metric("Gasto actual vs promedio", f"${ultimo['Gastos']:,.0f}", delta=f"{((ultimo['Gastos']/promedio_gastos-1)*100) if promedio_gastos else 0:+.1f}%", delta_color="inverse")
            cp3.metric("Balance actual vs promedio", f"${ultimo['Balance']:,.0f}", delta=f"${ultimo['Balance']-promedio_balance:,.0f}")

        # ======================================================
        # 5. PREDICCIÓN SIMPLE DEL SIGUIENTE MES
        # ======================================================
        st.divider()
        st.markdown("## Proyección simple del próximo mes")
        ventana = meses_movimiento.tail(3)
        ingreso_prox = float(ventana["Ingresos"].mean()) if not ventana.empty else 0.0
        gasto_prox = float(ventana["Gastos"].mean()) if not ventana.empty else 0.0
        balance_prox = ingreso_prox - gasto_prox
        pr1, pr2, pr3 = st.columns(3)
        pr1.metric("Ingreso estimado", f"${ingreso_prox:,.0f}")
        pr2.metric("Gasto estimado", f"${gasto_prox:,.0f}")
        pr3.metric("Balance estimado", f"${balance_prox:,.0f}")
        st.caption("Estimación descriptiva basada en el promedio de los últimos tres meses disponibles; no es una predicción estadística ni una garantía.")

        # ======================================================
        # 6. CALENDARIO FINANCIERO
        # ======================================================
        st.divider()
        st.markdown("## Calendario financiero por intensidad de gasto")
        control_meses_cal, control_promedio_cal = st.columns([1, 1.6])
        with control_meses_cal:
            ventana_calendario = st.selectbox(
                "Meses visibles",
                ["Últimos 3 meses", "Últimos 12 meses", "Últimos 24 meses"],
                index=1,
                help="Limita la altura del mapa tomando los meses más recientes del período filtrado.",
                key="calendario_ventana_meses_v13",
            )
        with control_promedio_cal:
            modo_promedio_calendario = st.radio(
                "Comparar cada día contra:",
                ["Período filtrado", "Cada mes"],
                horizontal=True,
                index=0,
                help=(
                    "Período filtrado usa un único promedio para todas las celdas. "
                    "Cada mes calcula un promedio diferente para cada fila."
                ),
                key="calendario_base_promedio_v13",
            )
        cantidad_meses_calendario = {
            "Últimos 3 meses": 3,
            "Últimos 12 meses": 12,
            "Últimos 24 meses": 24,
        }[ventana_calendario]
        texto_base_promedio = (
            "el promedio diario de todo el período filtrado"
            if modo_promedio_calendario == "Período filtrado"
            else "el promedio diario de cada mes"
        )
        st.caption(
            f"🎨 El color muestra cuántas veces el gasto del día representa {texto_base_promedio}. "
            "⚖️ La alerta se activa al superar 1,5 veces el presupuesto diario; si no hay presupuesto, "
            f"se usa 1,5 veces {texto_base_promedio}. ⚠ identifica los días que excedieron ese límite."
        )
        if not df.empty and "GASTOS_FECHA" in df.columns:
            calendario = df.dropna(subset=["GASTOS_FECHA"]).copy()
            calendario["Fecha"] = pd.to_datetime(calendario["GASTOS_FECHA"], errors="coerce")
            calendario = calendario.dropna(subset=["Fecha"])
            calendario["Día"] = calendario["Fecha"].dt.day
            calendario["Periodo calendario"] = calendario["Fecha"].dt.to_period("M").astype(str)
            periodos_disponibles_calendario = sorted(
                calendario["Periodo calendario"].dropna().unique()
            )
            periodos_visibles_calendario = set(
                periodos_disponibles_calendario[-cantidad_meses_calendario:]
            )
            calendario = calendario[
                calendario["Periodo calendario"].isin(periodos_visibles_calendario)
            ].copy()

            cal_tabla = calendario.pivot_table(
                index="Periodo calendario",
                columns="Día",
                values="GASTOS_CANTIDAD",
                aggfunc="sum",
                fill_value=0,
            ).reindex(columns=range(1, 32), fill_value=0)
            if not cal_tabla.empty:
                conteo_movimientos = calendario.groupby(
                    ["Periodo calendario", "Día"]
                ).size().to_dict()
                gasto_categoria_dia = (
                    calendario.groupby(
                        ["Periodo calendario", "Día", "GASTOS_CATEGORIA"],
                        dropna=False,
                    )["GASTOS_CANTIDAD"]
                    .sum()
                    .reset_index()
                    .sort_values("GASTOS_CANTIDAD", ascending=False)
                    .drop_duplicates(["Periodo calendario", "Día"])
                )
                categoria_principal_dia = {
                    (fila["Periodo calendario"], int(fila["Día"])): (
                        "Sin categoría"
                        if str(fila["GASTOS_CATEGORIA"]).strip().lower()
                        in {"", "undefined", "none", "nan"}
                        else str(fila["GASTOS_CATEGORIA"])
                    )
                    for _, fila in gasto_categoria_dia.iterrows()
                }
                promedio_diario_mes = (
                    calendario.groupby("Periodo calendario")["GASTOS_CANTIDAD"].sum()
                    / calendario.groupby("Periodo calendario")["Día"].nunique().clip(lower=1)
                ).to_dict()

                filtros_clasificacion_activos = (
                    set(categorias_sel) != set(categorias)
                    or set(subcategorias_sel) != set(subcategorias)
                )

                etiquetas_meses = []
                matriz_gasto = []
                matriz_personalizada = []
                mascara_sobre_promedio = []
                mascara_bajo_promedio = []
                alertas_x = []
                alertas_y = []

                for periodo_clave in cal_tabla.index:
                    periodo = pd.Period(periodo_clave, freq="M")
                    etiqueta_mes = f"{MESES_ORDEN[periodo.month - 1].title()} {periodo.year}"
                    etiquetas_meses.append(etiqueta_mes)
                    dias_del_mes = int(periodo.days_in_month)
                    promedio_mes = float(promedio_diario_mes.get(periodo_clave, 0.0))
                    promedio_referencia = (
                        float(gasto_promedio_diario)
                        if modo_promedio_calendario == "Período filtrado"
                        else promedio_mes
                    )

                    presupuesto_mes = 0.0
                    if not filtros_clasificacion_activos and isinstance(
                        presupuesto_mensual_por_periodo, dict
                    ):
                        for (anio_pres, mes_pres), valor_pres in presupuesto_mensual_por_periodo.items():
                            if (
                                int(anio_pres) == int(periodo.year)
                                and normalizar_mes(mes_pres)
                                == normalizar_mes(MESES_ORDEN[periodo.month - 1])
                            ):
                                presupuesto_mes = float(valor_pres or 0.0)
                                break
                    if (
                        presupuesto_mes <= 0
                        and not filtros_clasificacion_activos
                        and float(presupuesto_mensual_base or 0.0) > 0
                    ):
                        presupuesto_mes = float(presupuesto_mensual_base)

                    if presupuesto_mes > 0:
                        base_limite = presupuesto_mes / max(dias_del_mes, 1)
                        fuente_limite = "Presupuesto diario"
                    else:
                        base_limite = promedio_referencia
                        fuente_limite = (
                            "Promedio diario del período filtrado"
                            if modo_promedio_calendario == "Período filtrado"
                            else "Promedio diario del mes"
                        )
                    limite_equilibrado = base_limite * 1.5

                    fila_gasto = []
                    fila_personalizada = []
                    fila_sobre = []
                    fila_bajo = []
                    for dia in range(1, 32):
                        fecha_celda_valida = dia <= dias_del_mes
                        if fecha_celda_valida:
                            fecha_celda = pd.Timestamp(periodo.year, periodo.month, dia)
                            fecha_celda_valida = fecha_desde_ts.normalize() <= fecha_celda <= fecha_hasta_ts.normalize()

                        if not fecha_celda_valida:
                            fila_gasto.append(None)
                            fila_personalizada.append([None] * 8)
                            fila_sobre.append(None)
                            fila_bajo.append(None)
                            continue

                        gasto_dia = float(cal_tabla.loc[periodo_clave, dia])
                        movimientos_dia = int(conteo_movimientos.get((periodo_clave, dia), 0))
                        categoria_principal = categoria_principal_dia.get(
                            (periodo_clave, dia), "Sin movimientos"
                        )
                        diferencia_promedio_pct = (
                            (gasto_dia - promedio_referencia) / promedio_referencia * 100
                            if promedio_referencia > 0 else 0.0
                        )
                        veces_promedio = (
                            gasto_dia / promedio_referencia
                            if promedio_referencia > 0 else 0.0
                        )
                        if diferencia_promedio_pct > 0:
                            lectura_promedio = f"{diferencia_promedio_pct:.1f}% por encima"
                            sobre_promedio = True
                        elif diferencia_promedio_pct < 0:
                            lectura_promedio = f"{abs(diferencia_promedio_pct):.1f}% por debajo"
                            sobre_promedio = False
                        else:
                            lectura_promedio = "Igual al promedio"
                            sobre_promedio = False

                        if limite_equilibrado > 0 and gasto_dia > limite_equilibrado:
                            exceso_limite = gasto_dia - limite_equilibrado
                            exceso_limite_pct = exceso_limite / limite_equilibrado * 100
                            lectura_limite = (
                                f"Excedido por ${exceso_limite:,.0f} ({exceso_limite_pct:.1f}%)"
                            )
                            alertas_x.append(dia)
                            alertas_y.append(etiqueta_mes)
                        else:
                            margen_limite = max(limite_equilibrado - gasto_dia, 0.0)
                            lectura_limite = f"Dentro del límite · margen ${margen_limite:,.0f}"

                        datos_tooltip = [
                            gasto_dia,
                            promedio_referencia,
                            lectura_promedio,
                            limite_equilibrado,
                            lectura_limite,
                            movimientos_dia,
                            categoria_principal,
                            fuente_limite,
                        ]
                        # La intensidad se limita visualmente a 2x. Los valores
                        # superiores conservan su dato real en el tooltip.
                        fila_gasto.append(min(veces_promedio, 2.0))
                        fila_personalizada.append(datos_tooltip)
                        fila_sobre.append(1 if sobre_promedio else None)
                        fila_bajo.append(1 if not sobre_promedio else None)

                    matriz_gasto.append(fila_gasto)
                    matriz_personalizada.append(fila_personalizada)
                    mascara_sobre_promedio.append(fila_sobre)
                    mascara_bajo_promedio.append(fila_bajo)

                fig_cal = go.Figure()
                fig_cal.add_trace(go.Heatmap(
                    z=matriz_gasto,
                    x=list(range(1, 32)),
                    y=etiquetas_meses,
                    zmin=0,
                    zmax=2.0,
                    colorscale="Turbo",
                    colorbar=dict(
                        title="Veces el<br>promedio diario",
                        tickmode="array",
                        tickvals=[0, 0.5, 1.0, 1.5, 2.0],
                        ticktext=["0x", "0,5x", "1x", "1,5x", "2x+"],
                        thickness=16,
                    ),
                    hoverinfo="skip",
                    hoverongaps=False,
                ))

                if alertas_x:
                    fig_cal.add_trace(go.Scatter(
                        x=alertas_x,
                        y=alertas_y,
                        mode="text",
                        text=["⚠"] * len(alertas_x),
                        textfont=dict(color="#FFFFFF", size=15),
                        hoverinfo="skip",
                        showlegend=False,
                    ))

                etiqueta_promedio_tooltip = (
                    "Promedio diario del período filtrado"
                    if modo_promedio_calendario == "Período filtrado"
                    else "Promedio diario del mes"
                )
                tooltip_calendario = (
                    "<b>%{y}</b><br>"
                    "Día del mes: %{x}<br><br>"
                    "Gasto del día: <b>$%{customdata[0]:,.0f}</b><br>"
                    f"{etiqueta_promedio_tooltip}: $%{{customdata[1]:,.0f}}<br>"
                    "Comparación: <b>%{customdata[2]}</b><br><br>"
                    "Límite equilibrado: $%{customdata[3]:,.0f}<br>"
                    "Estado: <b>%{customdata[4]}</b><br>"
                    "Base aplicada: %{customdata[7]} × 1,5<br><br>"
                    "Movimientos: %{customdata[5]}<br>"
                    "Categoría principal: %{customdata[6]}"
                    "<extra></extra>"
                )
                escala_transparente = [
                    [0, "rgba(0,0,0,0)"],
                    [1, "rgba(0,0,0,0)"],
                ]
                fig_cal.add_trace(go.Heatmap(
                    z=mascara_sobre_promedio,
                    x=list(range(1, 32)),
                    y=etiquetas_meses,
                    customdata=matriz_personalizada,
                    colorscale=escala_transparente,
                    showscale=False,
                    hovertemplate=tooltip_calendario,
                    hoverlabel=dict(
                        bgcolor="#4A0713",
                        bordercolor="#FF1744",
                        font=dict(color="#FFFFFF", size=12),
                    ),
                    hoverongaps=False,
                ))
                fig_cal.add_trace(go.Heatmap(
                    z=mascara_bajo_promedio,
                    x=list(range(1, 32)),
                    y=etiquetas_meses,
                    customdata=matriz_personalizada,
                    colorscale=escala_transparente,
                    showscale=False,
                    hovertemplate=tooltip_calendario,
                    hoverlabel=dict(
                        bgcolor="#06351D",
                        bordercolor="#00E676",
                        font=dict(color="#FFFFFF", size=12),
                    ),
                    hoverongaps=False,
                ))
                fig_cal.update_layout(
                    height=max(340, 58 * len(cal_tabla) + 175),
                    title="Intensidad diaria del gasto · ⚠ supera el límite equilibrado",
                    xaxis_title="Día del mes",
                    yaxis_title="Mes y año",
                    showlegend=False,
                )
                st.plotly_chart(
                    estilo_grafico(
                        fig_cal,
                        "Intensidad diaria del gasto · ⚠ supera el límite equilibrado",
                    ),
                    use_container_width=True,
                )
            else:
                st.info("No hay fechas válidas para construir el calendario.")

        # ======================================================
        # 7. WATERFALL: QUÉ EXPLICA EL CAMBIO DEL GASTO
        # ======================================================
        st.divider()
        st.markdown("## ¿Qué explica el cambio del gasto?")
        if len(meses_movimiento) >= 2 and 'comp_categorias' in locals() and not comp_categorias.empty:
            contrib = comp_categorias.sort_values("Cambio", key=lambda serie: serie.abs(), ascending=False).head(10)
            total_anterior = float(meses_movimiento.iloc[-2]["Gastos"])
            total_actual = float(meses_movimiento.iloc[-1]["Gastos"])
            fig_water = go.Figure(go.Waterfall(
                orientation="v",
                measure=["absolute"] + ["relative"] * len(contrib) + ["total"],
                x=[f"Gasto {meses_movimiento.iloc[-2]['MES']}"] + contrib["GASTOS_CATEGORIA"].astype(str).tolist() + [f"Gasto {meses_movimiento.iloc[-1]['MES']}"] ,
                y=[total_anterior] + contrib["Cambio"].tolist() + [total_actual],
                text=[f"${total_anterior:,.0f}"] + [f"${v:+,.0f}" for v in contrib["Cambio"]] + [f"${total_actual:,.0f}"],
                textposition="outside",
                increasing={"marker": {"color": "#FF2E6E"}},
                decreasing={"marker": {"color": "#00FF9C"}},
                totals={"marker": {"color": "#00E5FF"}},
                connector={"line": {"color": "#94A3B8"}},
            ))
            fig_water.update_layout(height=500, xaxis_tickangle=-35, showlegend=False)
            st.plotly_chart(estilo_grafico(fig_water, "Contribución de las categorías al cambio mensual"), use_container_width=True)
        else:
            st.info("Se necesitan dos meses para explicar el cambio mediante un gráfico waterfall.")

    if pestana_activa == etiquetas_pestanas[2]:
        st.divider()
        st.markdown("## Mapa de calor por categoría")
        st.subheader("🔥 Mapa de calor: gasto vs presupuesto por categoría")
        sub_df_tendencias = df.copy()
        sub_df_tendencias["GASTOS_SUBCATEGORIA"] = sub_df_tendencias["GASTOS_SUBCATEGORIA"].fillna("Sin subcategoría")
        st.caption(
            "🟢 Verde = muy por debajo del presupuesto · 🔴 Rojo = muy sobre el presupuesto. "
            "Pasa el mouse sobre cualquier celda para ver gasto, presupuesto, diferencia y número de transacciones."
        )
        tabla = pd.pivot_table(
            df, values="GASTOS_CANTIDAD", index="GASTOS_CATEGORIA",
            columns="MES", aggfunc="sum", fill_value=0,
        )
        tabla_trans = pd.pivot_table(
            df, values="GASTOS_CANTIDAD", index="GASTOS_CATEGORIA",
            columns="MES", aggfunc="count", fill_value=0,
        )
        fig_heat = crear_heatmap_presupuesto(
            tabla,
            lambda cat, mes: presupuesto_categoria_mes(historico_presupuesto, cat, mes),
            etiqueta_fila="Categoría",
            tabla_transacciones=tabla_trans,
        )
        st.plotly_chart(fig_heat, use_container_width=True)

        st.divider()
        st.markdown("## Mapa de calor por subcategoría")
        st.caption("La intensidad mensual permite identificar subcategorías que crecen, disminuyen o se desvían de su referencia.")
        st.markdown("#### Mapa de calor por subcategoría")
        tabla_sub = pd.pivot_table(
            sub_df_tendencias, values="GASTOS_CANTIDAD", index="GASTOS_SUBCATEGORIA",
            columns="MES", aggfunc="sum", fill_value=0,
        )
        tabla_sub_trans = pd.pivot_table(
            sub_df_tendencias, values="GASTOS_CANTIDAD", index="GASTOS_SUBCATEGORIA",
            columns="MES", aggfunc="count", fill_value=0,
        )
        fig_sub_heat = crear_heatmap_presupuesto(
            tabla_sub,
            lambda sub, mes: float(historico_presupuesto[(historico_presupuesto["CONCEPTO"] == normalizar(sub)) & (historico_presupuesto["MES"] == normalizar_mes(mes))]["PRESUPUESTO"].sum()) if not historico_presupuesto.empty else 0.0,
            etiqueta_fila="Subcategoría",
            tabla_transacciones=tabla_sub_trans,
            colorscale=COLORSCALE_NEON_CALOR,
            colorbar_title="Desviación subcategoría",
        )
        st.plotly_chart(fig_sub_heat, use_container_width=True)

        st.divider()
        ingresos_laborales_proyeccion = ingresos_filtrados.copy()
        if not ingresos_laborales_proyeccion.empty:
            ingresos_laborales_proyeccion["INGRESOS_FECHA"] = pd.to_datetime(
                ingresos_laborales_proyeccion["INGRESOS_FECHA"], errors="coerce"
            )
            ingresos_laborales_proyeccion = ingresos_laborales_proyeccion.dropna(
                subset=["INGRESOS_FECHA"]
            )
            ingresos_laborales_proyeccion["TIPO_PROYECCION"] = (
                ingresos_laborales_proyeccion["INGRESOS_CATEGORIA"].map(etiqueta_tipo_ingreso)
            )
            ingresos_laborales_proyeccion = ingresos_laborales_proyeccion[
                ingresos_laborales_proyeccion["TIPO_PROYECCION"].eq("Laborales")
            ].copy()
            ingresos_laborales_proyeccion["PERIODO_PROYECCION"] = (
                ingresos_laborales_proyeccion["INGRESOS_FECHA"].dt.to_period("M")
            )

        gastos_proyeccion = df.copy()
        if not gastos_proyeccion.empty:
            gastos_proyeccion["GASTOS_FECHA"] = pd.to_datetime(
                gastos_proyeccion["GASTOS_FECHA"], errors="coerce"
            )
            gastos_proyeccion = gastos_proyeccion.dropna(subset=["GASTOS_FECHA"])
            gastos_proyeccion["PERIODO_PROYECCION"] = (
                gastos_proyeccion["GASTOS_FECHA"].dt.to_period("M")
            )

        valor_real_inversion = float(
            ingresos_laborales_proyeccion["INGRESOS_CANTIDAD"].sum()
            if not ingresos_laborales_proyeccion.empty else 0.0
        ) - float(
            gastos_proyeccion["GASTOS_CANTIDAD"].sum()
            if not gastos_proyeccion.empty else 0.0
        )

        salarios_mensuales_proyeccion = (
            ingresos_laborales_proyeccion.groupby("PERIODO_PROYECCION")["INGRESOS_CANTIDAD"].sum()
            if not ingresos_laborales_proyeccion.empty else pd.Series(dtype=float)
        )
        gastos_mensuales_proyeccion = (
            gastos_proyeccion.groupby("PERIODO_PROYECCION")["GASTOS_CANTIDAD"].sum()
            if not gastos_proyeccion.empty else pd.Series(dtype=float)
        )
        periodos_conocidos_proyeccion = sorted(
            set(salarios_mensuales_proyeccion.index).union(gastos_mensuales_proyeccion.index)
        )

        if periodos_conocidos_proyeccion:
            periodos_observados_proyeccion = pd.period_range(
                start=periodos_conocidos_proyeccion[0],
                end=periodos_conocidos_proyeccion[-1],
                freq="M",
            )
            salarios_observados = salarios_mensuales_proyeccion.reindex(
                periodos_observados_proyeccion, fill_value=0.0
            ).astype(float).tolist()
            gastos_observados = gastos_mensuales_proyeccion.reindex(
                periodos_observados_proyeccion, fill_value=0.0
            ).astype(float).tolist()

            cantidad_observada = max(len(periodos_observados_proyeccion), 1)
            salario_mensual_tendencia = sum(salarios_observados) / cantidad_observada
            gasto_mensual_tendencia = sum(gastos_observados) / cantidad_observada
            saldo_mensual_tendencia = (
                salario_mensual_tendencia - gasto_mensual_tendencia
            )

            maximo_inversion_disponible = max(int(round(valor_real_inversion)), 0)
            maximo_inversion_texto = f"${maximo_inversion_disponible:,.0f}".replace(",", ".")
            clave_inversion_inicial = "tendencias_capital_inicial_proyeccion_v13"
            if clave_inversion_inicial not in st.session_state:
                st.session_state[clave_inversion_inicial] = maximo_inversion_disponible
            else:
                st.session_state[clave_inversion_inicial] = min(
                    max(int(st.session_state[clave_inversion_inicial]), 0),
                    maximo_inversion_disponible,
                )

            st.markdown(
                """
                <style>
                .st-key-tendencias_control_inversion,
                .st-key-tendencias_control_tasa {
                    background:linear-gradient(145deg,rgba(0,230,118,.18),rgba(0,45,25,.76));
                    border:1px solid rgba(0,255,136,.72) !important;
                    border-radius:18px;
                    box-shadow:0 0 24px rgba(0,255,136,.18);
                    min-height:250px;
                }
                .st-key-tendencias_control_inversion [data-testid="stSlider"] > div,
                .st-key-tendencias_control_tasa [data-testid="stSlider"] > div {
                    padding-top:.15rem;
                }
                .st-key-tendencias_control_inversion [data-testid="stSlider"],
                .st-key-tendencias_control_tasa [data-testid="stSlider"] {
                    --primary-color:#00FF88;
                    accent-color:#00FF88;
                }
                .st-key-tendencias_control_inversion div[data-baseweb="slider"] [role="slider"],
                .st-key-tendencias_control_tasa div[data-baseweb="slider"] [role="slider"] {
                    background:#00FF88 !important;
                    border-color:#B7FFD8 !important;
                    box-shadow:0 0 0 4px rgba(0,255,136,.18),0 0 16px rgba(0,255,136,.72) !important;
                }
                .st-key-tendencias_control_inversion div[data-baseweb="slider"] > div > div,
                .st-key-tendencias_control_tasa div[data-baseweb="slider"] > div > div {
                    background:linear-gradient(90deg,#064E3B,#00FF88) !important;
                }
                .st-key-tendencias_control_inversion [data-baseweb="slider"] *,
                .st-key-tendencias_control_tasa [data-baseweb="slider"] *,
                .st-key-tendencias_control_inversion [data-testid="stTickBar"] *,
                .st-key-tendencias_control_tasa [data-testid="stTickBar"] * {
                    color:#B7FFD8 !important;
                    border-color:#5EEBAD !important;
                }
                .st-key-tendencias_control_inversion [data-testid="stThumbValue"],
                .st-key-tendencias_control_tasa [data-testid="stThumbValue"],
                .st-key-tendencias_control_inversion [data-testid="stSliderThumbValue"],
                .st-key-tendencias_control_tasa [data-testid="stSliderThumbValue"] {
                    background:#123D31 !important;
                    color:#DFFFF0 !important;
                    border:1px solid #5EEBAD !important;
                }
                .proyeccion-control-disponible {
                    display:inline-block;
                    margin-top:8px;
                    padding:5px 10px;
                    border-radius:999px;
                    color:#CFFFE3;
                    background:rgba(0,255,136,.10);
                    border:1px solid rgba(94,235,173,.34);
                    font-size:12px;
                }
                .proyeccion-control-numero {
                    margin-top:5px;
                    color:#8FFFC4;
                    font-size:32px;
                    line-height:1.05;
                    font-weight:850;
                    letter-spacing:-.035em;
                    font-variant-numeric:tabular-nums;
                    text-shadow:0 0 18px rgba(0,255,136,.34);
                }
                .proyeccion-control-detalle {
                    margin-top:8px;
                    color:#C8E8D5;
                    font-size:12px;
                    line-height:1.45;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            controles_proyeccion = st.columns(2)
            with controles_proyeccion[0]:
                with st.container(border=True, key="tendencias_control_inversion"):
                    st.markdown(
                        f"""
                        <div style="min-height:58px;">
                            <div style="font-size:13px;color:#D8FBE6;font-weight:700;letter-spacing:.04em;">
                                💰 CAPITAL INICIAL PARA INVERTIR
                            </div>
                            <div class="proyeccion-control-disponible">
                                Máximo disponible · <b>{maximo_inversion_texto}</b>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if maximo_inversion_disponible > 0:
                        paso_inversion = max(1, int(maximo_inversion_disponible / 100))
                        capital_inicial_proyeccion = st.slider(
                            "Monto que se va a invertir",
                            min_value=0,
                            max_value=maximo_inversion_disponible,
                            step=paso_inversion,
                            key=clave_inversion_inicial,
                            help=(
                                "Reduce la barra si deseas proyectar solamente una parte del capital "
                                "disponible. Las gráficas y las tarjetas se recalculan automáticamente."
                            ),
                        )
                    else:
                        capital_inicial_proyeccion = 0
                        st.progress(0, text="No hay capital positivo disponible para invertir")
                    porcentaje_invertido = (
                        capital_inicial_proyeccion / maximo_inversion_disponible * 100
                        if maximo_inversion_disponible else 0.0
                    )
                    proporcion_capital_elegida = (
                        capital_inicial_proyeccion / maximo_inversion_disponible
                        if maximo_inversion_disponible else 0.0
                    )
                    aporte_mensual_proyectado = (
                        saldo_mensual_tendencia * proporcion_capital_elegida
                    )
                    capital_inicial_texto = f"${capital_inicial_proyeccion:,.0f}".replace(",", ".")
                    aporte_mensual_texto = f"${aporte_mensual_proyectado:,.0f}".replace(",", ".")
                    st.markdown(
                        f"""
                        <div class="proyeccion-control-numero">
                            {capital_inicial_texto}
                        </div>
                        <div class="proyeccion-control-detalle">
                            {porcentaje_invertido:.0f}% del capital disponible · aporte mensual proyectado:
                            <b>{aporte_mensual_texto}</b>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            with controles_proyeccion[1]:
                with st.container(border=True, key="tendencias_control_tasa"):
                    st.markdown(
                        """
                        <div style="min-height:58px;">
                            <div style="font-size:13px;color:#D8FBE6;font-weight:700;letter-spacing:.04em;">
                                📈 RENDIMIENTO EFECTIVO ANUAL
                            </div>
                            <div style="font-size:12px;color:#B9DCC6;margin-top:7px;">
                                Compara el escenario base con el crecimiento de la inversión.
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    tasa_interes_ea_pct = st.slider(
                        "Tasa de interés efectiva anual (EA)",
                        min_value=2,
                        max_value=25,
                        value=10,
                        step=1,
                        format="%d%%",
                        help=(
                            "Selecciona el rendimiento anual estimado para la proyección "
                            "de 10, 20 y 30 años."
                        ),
                        key="tendencias_tasa_interes_ea_v13",
                    )
                    st.markdown(
                        f"""
                        <div class="proyeccion-control-numero">
                            {tasa_interes_ea_pct}% EA
                        </div>
                        <div class="proyeccion-control-detalle">
                            Tasa elegida para el escenario con rendimiento compuesto
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            st.markdown("## Proyección de ahorro a 10, 20 y 30 años")
            st.caption(
                "El monto elegido funciona como capital inicial y también define qué proporción del saldo "
                "mensual observado se seguirá invirtiendo. El escenario con rendimiento añade la tasa EA seleccionada."
            )

            meses_proyectados = 30 * 12
            periodos_futuros = pd.period_range(
                start=periodos_observados_proyeccion[-1] + 1,
                periods=meses_proyectados,
                freq="M",
            )
            salarios_futuros = []
            gastos_futuros = []
            saldos_mensuales_futuros = []
            ahorro_acumulado_futuro = []
            acumulado = float(capital_inicial_proyeccion)
            for _ in range(meses_proyectados):
                acumulado += aporte_mensual_proyectado
                salarios_futuros.append(salario_mensual_tendencia)
                gastos_futuros.append(gasto_mensual_tendencia)
                saldos_mensuales_futuros.append(aporte_mensual_proyectado)
                ahorro_acumulado_futuro.append(acumulado)

            valores_horizonte = {
                10: capital_inicial_proyeccion + aporte_mensual_proyectado * 10 * 12,
                20: capital_inicial_proyeccion + aporte_mensual_proyectado * 20 * 12,
                30: capital_inicial_proyeccion + aporte_mensual_proyectado * 30 * 12,
            }
            st.markdown("### Escenario base · sin rendimiento")
            tarjetas_proyeccion = st.columns(3)
            for tarjeta, anios_horizonte in zip(tarjetas_proyeccion, [10, 20, 30]):
                valor_horizonte = float(valores_horizonte[anios_horizonte])
                es_favorable = valor_horizonte >= 0
                color_tarjeta = "#00E676" if es_favorable else "#FF1744"
                fondo_tarjeta = (
                    "linear-gradient(145deg, rgba(0,230,118,0.20), rgba(0,45,25,0.72))"
                    if es_favorable
                    else "linear-gradient(145deg, rgba(255,23,68,0.22), rgba(55,4,16,0.78))"
                )
                estado_tarjeta = "Saldo a favor" if es_favorable else "Deuda proyectada"
                with tarjeta:
                    st.markdown(
                        f"""
                        <div style="background:{fondo_tarjeta};border:1px solid {color_tarjeta};
                                    border-radius:18px;padding:20px 18px;min-height:145px;
                                    box-shadow:0 0 22px {color_tarjeta}33;">
                            <div style="font-size:13px;color:#D8FBE6;font-weight:700;letter-spacing:.04em;">
                                PROYECCIÓN A {anios_horizonte} AÑOS
                            </div>
                            <div style="font-size:27px;color:{color_tarjeta};font-weight:800;margin-top:12px;">
                                ${abs(valor_horizonte):,.0f}
                            </div>
                            <div style="font-size:13px;color:#F4FFF8;margin-top:8px;">{estado_tarjeta}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            fechas_futuras = periodos_futuros.to_timestamp(how="end")
            ahorro_positivo = [
                valor if valor >= 0 else None for valor in ahorro_acumulado_futuro
            ]
            ahorro_negativo = [
                valor if valor < 0 else None for valor in ahorro_acumulado_futuro
            ]
            datos_proyeccion_hover = pd.DataFrame({
                "Salario proyectado": salarios_futuros,
                "Gasto proyectado": gastos_futuros,
                "Aporte mensual elegido": saldos_mensuales_futuros,
                "Capital inicial": [capital_inicial_proyeccion] * meses_proyectados,
            })
            fig_proyeccion_largo_plazo = go.Figure()
            fig_proyeccion_largo_plazo.add_trace(go.Scatter(
                x=fechas_futuras,
                y=ahorro_positivo,
                mode="lines",
                line=dict(color="#00E676", width=2),
                fill="tozeroy",
                fillcolor="rgba(0,230,118,0.18)",
                hoverinfo="skip",
                name="Saldo a favor",
            ))
            fig_proyeccion_largo_plazo.add_trace(go.Scatter(
                x=fechas_futuras,
                y=ahorro_negativo,
                mode="lines",
                line=dict(color="#FF1744", width=2),
                fill="tozeroy",
                fillcolor="rgba(255,23,68,0.18)",
                hoverinfo="skip",
                name="Deuda",
            ))
            fig_proyeccion_largo_plazo.add_trace(go.Scatter(
                x=fechas_futuras,
                y=ahorro_acumulado_futuro,
                mode="lines",
                line=dict(color="#F8FAFC", width=2.2),
                customdata=datos_proyeccion_hover,
                hovertemplate=(
                    "<b>%{x|%B %Y}</b><br>"
                    "Saldo acumulado: <b>$%{y:,.0f}</b><br>"
                    "Salario mensual proyectado: $%{customdata[0]:,.0f}<br>"
                    "Gasto mensual proyectado: $%{customdata[1]:,.0f}<br>"
                    "Aporte mensual elegido: $%{customdata[2]:,.0f}<br>"
                    "Capital inicial elegido: $%{customdata[3]:,.0f}<extra></extra>"
                ),
                showlegend=False,
            ))
            fig_proyeccion_largo_plazo.add_hline(
                y=0, line_color="#94A3B8", line_width=1.2, line_dash="dot"
            )

            def formato_horizonte_compacto(valor):
                valor = float(valor)
                signo = "-" if valor < 0 else ""
                valor_abs = abs(valor)
                for divisor, sufijo in [(1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")]:
                    if valor_abs >= divisor:
                        return f"{signo}${valor_abs / divisor:.1f}{sufijo}"
                return f"{signo}${valor_abs:,.0f}"

            for anios_horizonte in [10, 20, 30]:
                fecha_horizonte = fechas_futuras[anios_horizonte * 12 - 1]
                valor_horizonte_grafica = float(valores_horizonte[anios_horizonte])
                fig_proyeccion_largo_plazo.add_shape(
                    type="line",
                    xref="x",
                    yref="paper",
                    x0=fecha_horizonte,
                    x1=fecha_horizonte,
                    y0=0,
                    y1=1,
                    line=dict(color="rgba(255,238,0,0.48)", width=1, dash="dot"),
                )
                fig_proyeccion_largo_plazo.add_annotation(
                    x=fecha_horizonte,
                    y=valor_horizonte_grafica,
                    text=(
                        f"<b>{anios_horizonte} años</b><br>"
                        f"{formato_horizonte_compacto(valor_horizonte_grafica)}"
                    ),
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="#00FF88" if valor_horizonte_grafica >= 0 else "#FF1744",
                    ax=0,
                    ay=-48 if valor_horizonte_grafica >= 0 else 48,
                    bgcolor="rgba(0,20,12,.92)",
                    bordercolor="#00FF88" if valor_horizonte_grafica >= 0 else "#FF1744",
                    borderpad=5,
                    font=dict(color="#F8FAFC", size=10),
                )
            fig_proyeccion_largo_plazo.update_layout(
                height=520,
                xaxis_title="Horizonte de proyección",
                yaxis_title="Ahorro acumulado / deuda acumulada",
                hovermode="x unified",
                legend=dict(orientation="h", y=1.08, x=0),
            )
            fig_proyeccion_largo_plazo.update_yaxes(tickprefix="$", tickformat="~s")
            st.markdown(f"### Escenario base · con rendimiento del {tasa_interes_ea_pct}% EA")
            tasa_efectiva_anual = tasa_interes_ea_pct / 100
            tasa_efectiva_mensual = (1 + tasa_efectiva_anual) ** (1 / 12) - 1
            capital_con_interes = []
            interes_generado_mensual = []
            rendimiento_acumulado = []
            capital_actual = float(capital_inicial_proyeccion)
            for numero_mes in range(1, meses_proyectados + 1):
                interes_del_mes = capital_actual * tasa_efectiva_mensual
                capital_actual += interes_del_mes + aporte_mensual_proyectado
                aporte_neto_acumulado = (
                    capital_inicial_proyeccion + aporte_mensual_proyectado * numero_mes
                )
                capital_con_interes.append(capital_actual)
                interes_generado_mensual.append(interes_del_mes)
                rendimiento_acumulado.append(capital_actual - aporte_neto_acumulado)

            valores_horizonte_interes = {
                10: capital_con_interes[10 * 12 - 1],
                20: capital_con_interes[20 * 12 - 1],
                30: capital_con_interes[30 * 12 - 1],
            }
            tarjetas_interes = st.columns(3)
            for tarjeta, anios_horizonte in zip(tarjetas_interes, [10, 20, 30]):
                indice_horizonte = anios_horizonte * 12 - 1
                valor_horizonte = float(valores_horizonte_interes[anios_horizonte])
                rendimiento_horizonte = float(rendimiento_acumulado[indice_horizonte])
                es_favorable = valor_horizonte >= 0
                color_tarjeta = "#00E676" if es_favorable else "#FF1744"
                fondo_tarjeta = (
                    "linear-gradient(145deg, rgba(0,230,118,0.20), rgba(0,45,25,0.72))"
                    if es_favorable
                    else "linear-gradient(145deg, rgba(255,23,68,0.22), rgba(55,4,16,0.78))"
                )
                estado_tarjeta = (
                    "Capital acumulado" if es_favorable else "Deuda acumulada"
                )
                detalle_rendimiento = (
                    "Rendimiento estimado"
                    if rendimiento_horizonte >= 0
                    else "Interés acumulado sobre la deuda"
                )
                with tarjeta:
                    st.markdown(
                        f"""
                        <div style="background:{fondo_tarjeta};border:1px solid {color_tarjeta};
                                    border-radius:18px;padding:20px 18px;min-height:172px;
                                    box-shadow:0 0 22px {color_tarjeta}33;">
                            <div style="font-size:13px;color:#D8FBE6;font-weight:700;letter-spacing:.04em;">
                                {tasa_interes_ea_pct}% EA · {anios_horizonte} AÑOS
                            </div>
                            <div style="font-size:27px;color:{color_tarjeta};font-weight:800;margin-top:12px;">
                                ${abs(valor_horizonte):,.0f}
                            </div>
                            <div style="font-size:13px;color:#F4FFF8;margin-top:7px;">{estado_tarjeta}</div>
                            <div style="font-size:11px;color:#B9DCC6;margin-top:10px;">
                                {detalle_rendimiento}: ${abs(rendimiento_horizonte):,.0f}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            capital_positivo = [
                valor if valor >= 0 else None for valor in capital_con_interes
            ]
            capital_negativo = [
                valor if valor < 0 else None for valor in capital_con_interes
            ]
            datos_interes_hover = pd.DataFrame({
                "Aporte neto mensual": [aporte_mensual_proyectado] * meses_proyectados,
                "Interés del mes": interes_generado_mensual,
                "Rendimiento acumulado": rendimiento_acumulado,
                "Capital inicial": [capital_inicial_proyeccion] * meses_proyectados,
            })
            fig_proyeccion_interes = go.Figure()
            fig_proyeccion_interes.add_trace(go.Scatter(
                x=fechas_futuras,
                y=capital_positivo,
                mode="lines",
                line=dict(color="#00E676", width=2),
                fill="tozeroy",
                fillcolor="rgba(0,230,118,0.20)",
                hoverinfo="skip",
                name="Capital a favor",
            ))
            fig_proyeccion_interes.add_trace(go.Scatter(
                x=fechas_futuras,
                y=capital_negativo,
                mode="lines",
                line=dict(color="#FF1744", width=2),
                fill="tozeroy",
                fillcolor="rgba(255,23,68,0.20)",
                hoverinfo="skip",
                name="Deuda con interés",
            ))
            fig_proyeccion_interes.add_trace(go.Scatter(
                x=fechas_futuras,
                y=capital_con_interes,
                mode="lines",
                line=dict(color="#FFEE00", width=2.4),
                customdata=datos_interes_hover,
                hovertemplate=(
                    "<b>%{x|%B %Y}</b><br>"
                    "Capital acumulado: <b>$%{y:,.0f}</b><br>"
                    "Aporte neto mensual: $%{customdata[0]:,.0f}<br>"
                    "Interés del mes: $%{customdata[1]:,.0f}<br>"
                    "Rendimiento acumulado: $%{customdata[2]:,.0f}<br>"
                    "Capital inicial elegido: $%{customdata[3]:,.0f}"
                    "<extra></extra>"
                ),
                showlegend=False,
            ))
            fig_proyeccion_interes.add_hline(
                y=0, line_color="#94A3B8", line_width=1.2, line_dash="dot"
            )
            for anios_horizonte in [10, 20, 30]:
                fecha_horizonte = fechas_futuras[anios_horizonte * 12 - 1]
                valor_horizonte_grafica = float(valores_horizonte_interes[anios_horizonte])
                fig_proyeccion_interes.add_shape(
                    type="line",
                    xref="x",
                    yref="paper",
                    x0=fecha_horizonte,
                    x1=fecha_horizonte,
                    y0=0,
                    y1=1,
                    line=dict(color="rgba(255,238,0,0.48)", width=1, dash="dot"),
                )
                fig_proyeccion_interes.add_annotation(
                    x=fecha_horizonte,
                    y=valor_horizonte_grafica,
                    text=(
                        f"<b>{anios_horizonte} años</b><br>"
                        f"{formato_horizonte_compacto(valor_horizonte_grafica)}"
                    ),
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="#00FF88" if valor_horizonte_grafica >= 0 else "#FF1744",
                    ax=0,
                    ay=-48 if valor_horizonte_grafica >= 0 else 48,
                    bgcolor="rgba(0,20,12,.92)",
                    bordercolor="#00FF88" if valor_horizonte_grafica >= 0 else "#FF1744",
                    borderpad=5,
                    font=dict(color="#F8FAFC", size=10),
                )
            fig_proyeccion_interes.update_layout(
                height=520,
                xaxis_title="Horizonte de inversión",
                yaxis_title="Capital acumulado / deuda acumulada",
                hovermode="x unified",
                legend=dict(orientation="h", y=1.08, x=0),
            )
            fig_proyeccion_interes.update_yaxes(tickprefix="$", tickformat="~s")

            st.markdown("### Comparación visual de los dos escenarios")
            columnas_graficas_proyeccion = st.columns(2)
            with columnas_graficas_proyeccion[0]:
                st.plotly_chart(
                    estilo_grafico(
                        fig_proyeccion_largo_plazo,
                        "Sin rendimiento · tendencia de salarios menos gastos",
                    ),
                    use_container_width=True,
                    key="tendencias_proyeccion_ahorro_30_anios_v13",
                )
                st.caption(
                    f"Capital inicial de ${capital_inicial_proyeccion:,.0f} más un aporte mensual ajustado "
                    f"de ${aporte_mensual_proyectado:,.0f}, sin aplicar intereses."
                )
            with columnas_graficas_proyeccion[1]:
                st.plotly_chart(
                    estilo_grafico(
                        fig_proyeccion_interes,
                        f"Con rendimiento compuesto · {tasa_interes_ea_pct}% EA",
                    ),
                    use_container_width=True,
                    key="tendencias_proyeccion_interes_ea_v13",
                )
                st.caption(
                    f"Aplica {tasa_interes_ea_pct}% EA sobre ${capital_inicial_proyeccion:,.0f}; "
                    f"se aportan ${aporte_mensual_proyectado:,.0f} al mes y los rendimientos se reinvierten."
                )

            if len(periodos_observados_proyeccion) < 6:
                st.warning(
                    "La proyección se construye con menos de seis meses observados; úsala con especial cautela."
                )
            st.caption(
                "Los valores señalados en 10, 20 y 30 años facilitan la comparación. "
                "Son escenarios orientativos y no garantizan resultados futuros."
            )
        else:
            st.info(
                "No hay salarios laborales o gastos con fechas válidas suficientes para construir la proyección."
            )

        # ======================================================

    if pestana_activa == etiquetas_pestanas[3]:
        contexto_pestana("¿Estoy cumpliendo mis metas?", "Contrasta el gasto real con el plan, identifica desviaciones y muestra qué ajustes tendrían mayor impacto.")
        st.markdown("## 1. 🧭 Estado general del presupuesto")
        sub_df = df.copy()
        sub_df["GASTOS_SUBCATEGORIA"] = sub_df["GASTOS_SUBCATEGORIA"].fillna("Sin subcategoría")
        sub_df["GASTOS_SUBCATEGORIA_2"] = sub_df["GASTOS_SUBCATEGORIA_2"].fillna("Sin detalle")

        presupuesto_periodo_total = float(presupuesto_mensual_general or 0.0)
        gasto_presupuesto_total = float(total_gastos)
        disponible_presupuesto = presupuesto_periodo_total - gasto_presupuesto_total
        ejecucion_presupuesto_pct = gasto_presupuesto_total / presupuesto_periodo_total * 100 if presupuesto_periodo_total > 0 else 0.0

        presupuesto_categoria_tabla = (
            df.groupby("GASTOS_CATEGORIA", as_index=False)["GASTOS_CANTIDAD"].sum()
            .rename(columns={"GASTOS_CANTIDAD": "Gasto"})
        ) if not df.empty else pd.DataFrame(columns=["GASTOS_CATEGORIA", "Gasto"])
        presupuesto_categoria_tabla["Presupuesto"] = presupuesto_categoria_tabla["GASTOS_CATEGORIA"].map(
            lambda c: float(presupuesto_cat.get(normalizar(c), 0.0))
        )
        presupuesto_categoria_tabla["Diferencia"] = presupuesto_categoria_tabla["Gasto"] - presupuesto_categoria_tabla["Presupuesto"]
        presupuesto_categoria_tabla["% ejecutado"] = presupuesto_categoria_tabla.apply(
            lambda r: r["Gasto"] / r["Presupuesto"] * 100 if r["Presupuesto"] > 0 else 0.0, axis=1
        )
        presupuesto_categoria_tabla["Estado"] = presupuesto_categoria_tabla.apply(
            lambda r: "Sin presupuesto" if r["Presupuesto"] <= 0 else (
                "Controlado" if r["% ejecutado"] <= 80 else "Atención" if r["% ejecutado"] <= 100 else "Excedido"
            ), axis=1
        )
        categorias_excedidas = int((presupuesto_categoria_tabla["Estado"] == "Excedido").sum())

        bp1, bp2, bp3, bp4, bp5 = st.columns(5)
        bp1.metric("Presupuesto", f"${presupuesto_periodo_total:,.0f}")
        bp2.metric("Ejecutado", f"${gasto_presupuesto_total:,.0f}")
        bp3.metric("Disponible", f"${disponible_presupuesto:,.0f}")
        bp4.metric("Ejecución", f"{ejecucion_presupuesto_pct:.1f}%")
        bp5.metric("Categorías excedidas", categorias_excedidas)
        st.markdown("## 2. 🚦 Semáforo presupuestal")
        estados_conteo = presupuesto_categoria_tabla["Estado"].value_counts() if not presupuesto_categoria_tabla.empty else pd.Series(dtype=int)
        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("🟢 Controlado", int(estados_conteo.get("Controlado", 0)))
        sm2.metric("🟡 Atención", int(estados_conteo.get("Atención", 0)))
        sm3.metric("🔴 Excedido", int(estados_conteo.get("Excedido", 0)))
        sm4.metric("⚪ Sin presupuesto", int(estados_conteo.get("Sin presupuesto", 0)))

        st.markdown("## 3. 📊 Ranking de desviaciones")
        st.caption(
            "🔴 Los excesos muestran dónde el gasto superó el plan. "
            "🟢 Las disponibilidades muestran el margen que aún queda dentro del presupuesto asignado."
        )

        def estilo_ranking_neon(
            fig, valores, titulo, nombre_escala, margen_izquierdo=155,
            paleta="exceso",
        ):
            """Aplica el estilo de referencia con color semántico por tipo de ranking."""
            valores_color = pd.to_numeric(pd.Series(valores), errors="coerce").fillna(0).tolist()
            max_valor = max(valores_color, default=0.0)
            if paleta == "disponibilidad":
                escala_neon = [
                    [0.00, "#04150C"],
                    [0.25, "#075C30"],
                    [0.50, "#00A854"],
                    [0.75, "#00E676"],
                    [1.00, "#00FF88"],
                ]
                color_acento = "#00FF88"
                color_linea = "rgba(0,255,136,0.55)"
                color_grid = "rgba(0,255,136,0.08)"
                color_borde_barra = "rgba(150,255,205,0.28)"
            else:
                escala_neon = [
                    [0.00, "#1B050A"],
                    [0.25, "#651020"],
                    [0.50, "#B80F32"],
                    [0.75, "#F01845"],
                    [1.00, "#FF003C"],
                ]
                color_acento = "#FF1744"
                color_linea = "rgba(255,23,68,0.58)"
                color_grid = "rgba(255,23,68,0.09)"
                color_borde_barra = "rgba(255,185,200,0.28)"
            fig.update_traces(
                marker=dict(
                    color=valores_color,
                    colorscale=escala_neon,
                    cmin=0,
                    cmax=max(max_valor, 1.0),
                    line=dict(color=color_borde_barra, width=0.8),
                    colorbar=dict(
                        title=dict(text=nombre_escala, font=dict(color=color_acento, size=11)),
                        tickprefix="$",
                        tickformat="~s",
                        thickness=12,
                        len=0.70,
                        x=1.02,
                        outlinewidth=0,
                        tickfont=dict(color="#E7F8FF", size=10),
                    ),
                ),
                texttemplate="<b>$%{text:,.0f}</b>",
                textfont=dict(color="#FFFFFF", size=11),
                textposition="outside",
                cliponaxis=False,
            )
            fig = estilo_grafico(fig, titulo)
            fig.update_layout(
                height=max(370, len(valores_color) * 44 + 115),
                paper_bgcolor="#020407",
                plot_bgcolor="#020407",
                title=dict(
                    text=f"<b>{titulo}</b>",
                    x=0.015,
                    xanchor="left",
                    font=dict(color="#F4FBFF", size=15),
                ),
                margin=dict(l=margen_izquierdo, r=100, t=72, b=58),
                bargap=0.26,
                showlegend=False,
                hoverlabel=dict(
                    bgcolor="#07111C",
                    bordercolor=color_acento,
                    font=dict(color="#FFFFFF", size=12),
                ),
            )
            fig.update_xaxes(
                title_text=nombre_escala,
                tickprefix="$",
                tickformat="~s",
                gridcolor=color_grid,
                linecolor=color_linea,
                zeroline=False,
                showline=True,
                ticks="outside",
                tickcolor=color_acento,
                tickfont=dict(color="#D9F8FF", size=10),
                title_font=dict(color="#D9F8FF", size=11),
            )
            fig.update_yaxes(
                title_text="",
                gridcolor="rgba(0,0,0,0)",
                linecolor=color_linea,
                showline=True,
                tickfont=dict(color="#F3FBFF", size=10),
            )
            fig.add_shape(
                type="rect",
                xref="paper",
                yref="paper",
                x0=0,
                y0=0,
                x1=1,
                y1=1,
                line=dict(color=color_linea, width=1),
                fillcolor="rgba(0,0,0,0)",
                layer="below",
            )
            fig.add_annotation(
                x=1,
                y=1.08,
                xref="paper",
                yref="paper",
                text="BAJO&nbsp;&nbsp;→&nbsp;&nbsp;ALTO",
                showarrow=False,
                xanchor="right",
                font=dict(color=color_acento, size=9),
            )
            return fig

        rk1, rk2 = st.columns(2)
        with rk1:
            excedidas = presupuesto_categoria_tabla[presupuesto_categoria_tabla["Diferencia"] > 0].nlargest(10, "Diferencia").copy()
            excedidas["Exceso %"] = excedidas.apply(
                lambda r: r["Diferencia"] / r["Presupuesto"] * 100 if r["Presupuesto"] > 0 else 0.0,
                axis=1,
            )
            fig_exc = px.bar(
                excedidas.sort_values("Diferencia"),
                x="Diferencia", y="GASTOS_CATEGORIA", orientation="h", text="Diferencia",
            )
            fig_exc.update_traces(
                marker=dict(color="#FF1744", line=dict(color="#FF8A9D", width=1.3)),
                texttemplate="$%{text:,.0f}", textposition="outside", cliponaxis=False,
                customdata=excedidas.sort_values("Diferencia")[["Gasto", "Presupuesto", "Exceso %", "% ejecutado"]],
                hovertemplate=(
                    "🔴 <b>%{y}</b><br>"
                    "Exceso: <b>$%{x:,.0f}</b><br>"
                    "Gasto real: $%{customdata[0]:,.0f}<br>"
                    "Presupuesto: $%{customdata[1]:,.0f}<br>"
                    "Exceso sobre el plan: %{customdata[2]:.1f}%<br>"
                    "Ejecución total: %{customdata[3]:.1f}%<extra></extra>"
                ),
            )
            fig_exc.update_layout(
                hoverlabel=dict(bgcolor="#2B0610", bordercolor="#FF1744", font=dict(color="#FFFFFF", size=13)),
                margin=dict(l=145, r=45, t=65, b=35),
            )
            fig_exc = estilo_ranking_neon(
                fig_exc,
                excedidas.sort_values("Diferencia")["Diferencia"],
                "🔴 Categorías con mayor exceso",
                "Exceso",
                paleta="exceso",
            )
            st.plotly_chart(fig_exc, use_container_width=True)
        with rk2:
            disponibles = presupuesto_categoria_tabla[(presupuesto_categoria_tabla["Presupuesto"] > 0) & (presupuesto_categoria_tabla["Diferencia"] < 0)].copy()
            disponibles["Disponible"] = -disponibles["Diferencia"]
            disponibles["Disponible %"] = disponibles.apply(
                lambda r: r["Disponible"] / r["Presupuesto"] * 100 if r["Presupuesto"] > 0 else 0.0,
                axis=1,
            )
            disponibles = disponibles.nlargest(10, "Disponible")
            fig_disp = px.bar(
                disponibles.sort_values("Disponible"),
                x="Disponible", y="GASTOS_CATEGORIA", orientation="h", text="Disponible",
            )
            fig_disp.update_traces(
                marker=dict(color="#00E676", line=dict(color="#8AFFB7", width=1.3)),
                texttemplate="$%{text:,.0f}", textposition="outside", cliponaxis=False,
                customdata=disponibles.sort_values("Disponible")[["Gasto", "Presupuesto", "Disponible %", "% ejecutado"]],
                hovertemplate=(
                    "🟢 <b>%{y}</b><br>"
                    "Disponible: <b>$%{x:,.0f}</b><br>"
                    "Gasto real: $%{customdata[0]:,.0f}<br>"
                    "Presupuesto: $%{customdata[1]:,.0f}<br>"
                    "Margen disponible: %{customdata[2]:.1f}%<br>"
                    "Ejecución total: %{customdata[3]:.1f}%<extra></extra>"
                ),
            )
            fig_disp.update_layout(
                hoverlabel=dict(bgcolor="#032B17", bordercolor="#00E676", font=dict(color="#FFFFFF", size=13)),
                margin=dict(l=145, r=45, t=65, b=35),
            )
            fig_disp = estilo_ranking_neon(
                fig_disp,
                disponibles.sort_values("Disponible")["Disponible"],
                "🟢 Categorías con mayor disponibilidad",
                "Disponible",
                paleta="disponibilidad",
            )
            st.plotly_chart(fig_disp, use_container_width=True)

        st.markdown("### Ranking por subcategoría")
        st.caption(
            "Aplica la misma comparación a cada subcategoría. La categoría se incluye en la etiqueta "
            "para diferenciar subcategorías con nombres iguales."
        )

        presupuesto_subcategoria_tabla = (
            df.groupby(
                ["GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA"],
                as_index=False,
            )["GASTOS_CANTIDAD"]
            .sum()
            .rename(columns={"GASTOS_CANTIDAD": "Gasto"})
        ) if not df.empty else pd.DataFrame(
            columns=["GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA", "Gasto"]
        )
        presupuesto_subcategoria_tabla["Presupuesto"] = presupuesto_subcategoria_tabla.apply(
            lambda r: float(
                buscar_presupuesto_sub(
                    r["GASTOS_CATEGORIA"],
                    r["GASTOS_SUBCATEGORIA"],
                    presupuesto_sub,
                )
            ),
            axis=1,
        )
        presupuesto_subcategoria_tabla["Diferencia"] = (
            presupuesto_subcategoria_tabla["Gasto"]
            - presupuesto_subcategoria_tabla["Presupuesto"]
        )
        presupuesto_subcategoria_tabla["% ejecutado"] = presupuesto_subcategoria_tabla.apply(
            lambda r: r["Gasto"] / r["Presupuesto"] * 100 if r["Presupuesto"] > 0 else 0.0,
            axis=1,
        )
        presupuesto_subcategoria_tabla["Concepto"] = (
            presupuesto_subcategoria_tabla["GASTOS_CATEGORIA"].astype(str)
            + " › "
            + presupuesto_subcategoria_tabla["GASTOS_SUBCATEGORIA"].astype(str)
        )

        rks1, rks2 = st.columns(2)
        with rks1:
            sub_excedidas = presupuesto_subcategoria_tabla[
                presupuesto_subcategoria_tabla["Diferencia"] > 0
            ].nlargest(10, "Diferencia").copy()
            sub_excedidas["Exceso %"] = sub_excedidas.apply(
                lambda r: r["Diferencia"] / r["Presupuesto"] * 100 if r["Presupuesto"] > 0 else 0.0,
                axis=1,
            )
            sub_excedidas_orden = sub_excedidas.sort_values("Diferencia")
            fig_sub_exc = px.bar(
                sub_excedidas_orden,
                x="Diferencia", y="Concepto", orientation="h", text="Diferencia",
            )
            fig_sub_exc.update_traces(
                marker=dict(color="#FF1744", line=dict(color="#FF8A9D", width=1.3)),
                texttemplate="$%{text:,.0f}", textposition="outside", cliponaxis=False,
                customdata=sub_excedidas_orden[["Gasto", "Presupuesto", "Exceso %", "% ejecutado"]],
                hovertemplate=(
                    "🔴 <b>%{y}</b><br>"
                    "Exceso: <b>$%{x:,.0f}</b><br>"
                    "Gasto real: $%{customdata[0]:,.0f}<br>"
                    "Presupuesto: $%{customdata[1]:,.0f}<br>"
                    "Exceso sobre el plan: %{customdata[2]:.1f}%<br>"
                    "Ejecución total: %{customdata[3]:.1f}%<extra></extra>"
                ),
            )
            fig_sub_exc.update_layout(
                hoverlabel=dict(bgcolor="#2B0610", bordercolor="#FF1744", font=dict(color="#FFFFFF", size=13)),
                margin=dict(l=190, r=45, t=65, b=35),
            )
            fig_sub_exc = estilo_ranking_neon(
                fig_sub_exc,
                sub_excedidas_orden["Diferencia"],
                "🔴 Subcategorías con mayor exceso",
                "Exceso",
                margen_izquierdo=195,
                paleta="exceso",
            )
            st.plotly_chart(
                fig_sub_exc,
                use_container_width=True,
                key="presupuesto_ranking_subcategorias_exceso",
            )

        with rks2:
            sub_disponibles = presupuesto_subcategoria_tabla[
                (presupuesto_subcategoria_tabla["Presupuesto"] > 0)
                & (presupuesto_subcategoria_tabla["Diferencia"] < 0)
            ].copy()
            sub_disponibles["Disponible"] = -sub_disponibles["Diferencia"]
            sub_disponibles["Disponible %"] = sub_disponibles.apply(
                lambda r: r["Disponible"] / r["Presupuesto"] * 100 if r["Presupuesto"] > 0 else 0.0,
                axis=1,
            )
            sub_disponibles = sub_disponibles.nlargest(10, "Disponible")
            sub_disponibles_orden = sub_disponibles.sort_values("Disponible")
            fig_sub_disp = px.bar(
                sub_disponibles_orden,
                x="Disponible", y="Concepto", orientation="h", text="Disponible",
            )
            fig_sub_disp.update_traces(
                marker=dict(color="#00E676", line=dict(color="#8AFFB7", width=1.3)),
                texttemplate="$%{text:,.0f}", textposition="outside", cliponaxis=False,
                customdata=sub_disponibles_orden[["Gasto", "Presupuesto", "Disponible %", "% ejecutado"]],
                hovertemplate=(
                    "🟢 <b>%{y}</b><br>"
                    "Disponible: <b>$%{x:,.0f}</b><br>"
                    "Gasto real: $%{customdata[0]:,.0f}<br>"
                    "Presupuesto: $%{customdata[1]:,.0f}<br>"
                    "Margen disponible: %{customdata[2]:.1f}%<br>"
                    "Ejecución total: %{customdata[3]:.1f}%<extra></extra>"
                ),
            )
            fig_sub_disp.update_layout(
                hoverlabel=dict(bgcolor="#032B17", bordercolor="#00E676", font=dict(color="#FFFFFF", size=13)),
                margin=dict(l=190, r=45, t=65, b=35),
            )
            fig_sub_disp = estilo_ranking_neon(
                fig_sub_disp,
                sub_disponibles_orden["Disponible"],
                "🟢 Subcategorías con mayor disponibilidad",
                "Disponible",
                margen_izquierdo=195,
                paleta="disponibilidad",
            )
            st.plotly_chart(
                fig_sub_disp,
                use_container_width=True,
                key="presupuesto_ranking_subcategorias_disponibilidad",
            )

        st.markdown("## 4. 🧪 Calidad del presupuesto")
        categorias_con_presupuesto = int((presupuesto_categoria_tabla["Presupuesto"] > 0).sum())
        cobertura_categorias = categorias_con_presupuesto / max(len(presupuesto_categoria_tabla), 1) * 100
        gasto_con_presupuesto = float(presupuesto_categoria_tabla.loc[presupuesto_categoria_tabla["Presupuesto"] > 0, "Gasto"].sum())
        cobertura_gasto = gasto_con_presupuesto / gasto_presupuesto_total * 100 if gasto_presupuesto_total else 0.0
        error_medio = float(presupuesto_categoria_tabla.loc[presupuesto_categoria_tabla["Presupuesto"] > 0, "% ejecutado"].sub(100).abs().mean()) if categorias_con_presupuesto else 0.0
        q1, q2, q3 = st.columns(3)
        q1.metric("Categorías cubiertas", f"{cobertura_categorias:.1f}%")
        q2.metric("Gasto cubierto", f"{cobertura_gasto:.1f}%")
        q3.metric("Desviación media", f"{error_medio:.1f}%")

        st.markdown("## 5. 📅 Evolución mensual del presupuesto")
        st.caption(
            "Compara la ejecución real de cada mes con el presupuesto asignado. "
            "Esta sección analiza disciplina presupuestal; la evolución completa de ingresos y balance permanece en Tendencias."
        )

        presupuesto_mensual_df = flujo_reporte.copy() if isinstance(flujo_reporte, pd.DataFrame) else pd.DataFrame()
        if not presupuesto_mensual_df.empty:
            presupuesto_mensual_df["Gastos"] = pd.to_numeric(
                presupuesto_mensual_df.get("Gastos", 0), errors="coerce"
            ).fillna(0)
            presupuesto_mensual_df["Presupuesto mensual"] = pd.to_numeric(
                presupuesto_mensual_df.get("Presupuesto mensual", 0), errors="coerce"
            ).fillna(0)
            presupuesto_mensual_df["Diferencia"] = (
                presupuesto_mensual_df["Presupuesto mensual"] - presupuesto_mensual_df["Gastos"]
            )
            presupuesto_mensual_df["% ejecutado"] = presupuesto_mensual_df.apply(
                lambda r: r["Gastos"] / r["Presupuesto mensual"] * 100
                if r["Presupuesto mensual"] > 0 else 0.0,
                axis=1,
            )
            presupuesto_mensual_df["Estado"] = presupuesto_mensual_df.apply(
                lambda r: "Sin presupuesto" if r["Presupuesto mensual"] <= 0 else (
                    "Cumplido" if r["Gastos"] <= r["Presupuesto mensual"] else "Excedido"
                ),
                axis=1,
            )

            colores_mensuales = presupuesto_mensual_df.apply(
                lambda r: "#94A3B8" if r["Presupuesto mensual"] <= 0 else (
                    "#00E676" if r["Gastos"] <= r["Presupuesto mensual"] else "#FF1744"
                ),
                axis=1,
            ).tolist()

            fig_presupuesto_mensual = go.Figure()
            fig_presupuesto_mensual.add_trace(go.Bar(
                x=presupuesto_mensual_df["MES"],
                y=presupuesto_mensual_df["Gastos"],
                name="Gasto real",
                marker=dict(color=colores_mensuales),
                text=presupuesto_mensual_df["Gastos"],
                texttemplate="$%{text:,.0f}",
                textposition="outside",
                customdata=presupuesto_mensual_df[["Presupuesto mensual", "Diferencia", "% ejecutado", "Estado"]],
                hovertemplate=(
                    "📅 <b>%{x}</b><br>"
                    "Gasto ejecutado: <b>$%{y:,.0f}</b><br>"
                    "Presupuesto asignado: $%{customdata[0]:,.0f}<br>"
                    "Saldo del mes: $%{customdata[1]:+,.0f}<br>"
                    "Porcentaje ejecutado: %{customdata[2]:.1f}%<br>"
                    "Estado: <b>%{customdata[3]}</b><br>"
                    "Lectura: verde = dentro del plan · rojo = presupuesto excedido"
                    "<extra></extra>"
                ),
            ))
            fig_presupuesto_mensual.add_trace(go.Scatter(
                x=presupuesto_mensual_df["MES"],
                y=presupuesto_mensual_df["Presupuesto mensual"],
                name="Presupuesto",
                mode="lines+markers",
                line=dict(color="#FFD600", width=3.6, dash="dash"),
                marker=dict(size=10, symbol="diamond", color="#FFD600", line=dict(color="#5C4500", width=1.2)),
                hovertemplate="🎯 <b>%{x}</b><br>Meta presupuestal: <b>$%{y:,.0f}</b><br>Esta línea representa el límite planificado para el mes.<extra></extra>",
            ))
            fig_presupuesto_mensual.update_layout(
                barmode="group", height=470,
                xaxis=dict(categoryorder="array", categoryarray=MESES_ORDEN),
                yaxis=dict(tickprefix="$", tickformat=",.0f"),
                legend=dict(orientation="h", y=1.08),
                hoverlabel=dict(bgcolor="#07111F", bordercolor="#38BDF8", font=dict(color="#FFFFFF", size=13)),
            )
            st.plotly_chart(
                estilo_grafico(fig_presupuesto_mensual, "Presupuesto mensual frente a ejecución real"),
                use_container_width=True,
                key="presupuesto_evolucion_mensual_v914",
            )

            meses_cumplidos = int((presupuesto_mensual_df["Estado"] == "Cumplido").sum())
            meses_excedidos = int((presupuesto_mensual_df["Estado"] == "Excedido").sum())
            pm1, pm2, pm3 = st.columns(3)
            pm1.metric("Meses cumplidos", meses_cumplidos)
            pm2.metric("Meses excedidos", meses_excedidos)
            pm3.metric(
                "Desviación acumulada",
                f"${presupuesto_mensual_df['Diferencia'].sum():,.0f}",
                help="Valor positivo = disponibilidad; valor negativo = exceso acumulado.",
            )
        else:
            st.info("No hay información mensual suficiente para evaluar la evolución del presupuesto.")

        st.markdown("## 6. ⏱️ Ritmo de ejecución y proyección al cierre")
        fecha_actual = pd.Timestamp.today().normalize()
        mes_actual_nombre = MESES_ORDEN[fecha_actual.month - 1]
        filtro_incluye_mes_actual = fecha_desde_ts.normalize() <= fecha_actual <= fecha_hasta_ts.normalize()

        if filtro_incluye_mes_actual and presupuesto_periodo_total > 0:
            inicio_mes_actual = fecha_actual.replace(day=1)
            fin_mes_actual = inicio_mes_actual + pd.offsets.MonthEnd(0)
            dias_transcurridos = int(fecha_actual.day)
            dias_mes = int(fin_mes_actual.day)
            avance_calendario_pct = dias_transcurridos / dias_mes * 100

            gastos_mes_actual = df[
                pd.to_datetime(df["GASTOS_FECHA"], errors="coerce").dt.to_period("M")
                == fecha_actual.to_period("M")
            ]["GASTOS_CANTIDAD"].sum() if not df.empty else 0.0

            presupuesto_mes_actual = float(
                presupuesto_mensual_por_periodo.get((int(fecha_actual.year), mes_actual_nombre), 0.0)
                if isinstance(presupuesto_mensual_por_periodo, dict) else 0.0
            )
            if presupuesto_mes_actual <= 0 and not presupuesto_mensual_df.empty:
                fila_mes_actual = presupuesto_mensual_df[
                    presupuesto_mensual_df["MES"].astype(str).str.upper().eq(mes_actual_nombre)
                ]
                if not fila_mes_actual.empty:
                    presupuesto_mes_actual = float(fila_mes_actual.iloc[-1]["Presupuesto mensual"])

            ritmo_ejecucion_pct = gastos_mes_actual / presupuesto_mes_actual * 100 if presupuesto_mes_actual > 0 else 0.0
            gasto_promedio_diario_actual = gastos_mes_actual / max(dias_transcurridos, 1)
            gasto_proyectado_mes = gasto_promedio_diario_actual * dias_mes
            diferencia_proyectada = presupuesto_mes_actual - gasto_proyectado_mes
            estado_ritmo = (
                "Acelerado" if ritmo_ejecucion_pct > avance_calendario_pct + 10 else
                "Controlado" if ritmo_ejecucion_pct <= avance_calendario_pct + 3 else
                "En atención"
            )

            rt1, rt2, rt3, rt4 = st.columns(4)
            rt1.metric("Avance del mes", f"{avance_calendario_pct:.1f}%")
            rt2.metric("Presupuesto ejecutado", f"{ritmo_ejecucion_pct:.1f}%")
            rt3.metric("Ritmo de gasto", estado_ritmo)
            rt4.metric("Proyección al cierre", f"${gasto_proyectado_mes:,.0f}")

            if presupuesto_mes_actual > 0 and gasto_promedio_diario_actual > 0:
                dias_hasta_agotar = presupuesto_mes_actual / gasto_promedio_diario_actual
                fecha_agotamiento = inicio_mes_actual + pd.Timedelta(days=max(int(dias_hasta_agotar) - 1, 0))
                if gasto_proyectado_mes > presupuesto_mes_actual:
                    st.warning(
                        f"Al ritmo actual, el presupuesto mensual podría agotarse aproximadamente el "
                        f"**{fecha_agotamiento:%d/%m/%Y}**. La proyección indica un exceso de "
                        f"**${abs(diferencia_proyectada):,.0f}** al cierre."
                    )
                else:
                    st.success(
                        f"Al ritmo actual, terminarías el mes con aproximadamente "
                        f"**${diferencia_proyectada:,.0f} disponibles** frente al presupuesto."
                    )
            else:
                st.info("No existe presupuesto mensual suficiente para estimar la fecha de agotamiento.")
        else:
            st.info(
                "El análisis de ritmo se activa cuando el filtro incluye el mes actual y existe presupuesto definido."
            )

        st.markdown("## 7. Calidad y cobertura del presupuesto")
        gasto_sin_presupuesto = float(
            presupuesto_categoria_tabla.loc[
                presupuesto_categoria_tabla["Presupuesto"] <= 0, "Gasto"
            ].sum()
        ) if not presupuesto_categoria_tabla.empty else 0.0
        pct_gasto_sin_presupuesto = gasto_sin_presupuesto / gasto_presupuesto_total * 100 if gasto_presupuesto_total else 0.0
        categorias_sin_presupuesto = presupuesto_categoria_tabla[
            presupuesto_categoria_tabla["Presupuesto"] <= 0
        ].copy()

        cq1, cq2, cq3, cq4 = st.columns(4)
        cq1.metric("Cobertura por categorías", f"{cobertura_categorias:.1f}%")
        cq2.metric("Cobertura del gasto", f"{cobertura_gasto:.1f}%")
        cq3.metric("Gasto sin presupuesto", f"${gasto_sin_presupuesto:,.0f}")
        cq4.metric("% no planificado", f"{pct_gasto_sin_presupuesto:.1f}%")

        if not categorias_sin_presupuesto.empty:
            st.warning(
                f"Hay **{len(categorias_sin_presupuesto)} categoría(s)** con movimientos, pero sin presupuesto asignado."
            )
            with st.expander("Ver categorías con gasto sin presupuesto"):
                st.dataframe(
                    categorias_sin_presupuesto[["GASTOS_CATEGORIA", "Gasto"]]
                    .rename(columns={"GASTOS_CATEGORIA": "Categoría"})
                    .sort_values("Gasto", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )

        st.markdown("## 8. 🔁 Categorías sistemáticamente mal presupuestadas")
        historial_categoria = []
        if not df.empty and {"ANIO", "MES", "GASTOS_CATEGORIA", "GASTOS_CANTIDAD"}.issubset(df.columns):
            mensual_categoria = (
                df.groupby(["ANIO", "MES", "GASTOS_CATEGORIA"], dropna=False)["GASTOS_CANTIDAD"]
                .sum().reset_index(name="Gasto")
            )
            for fila in mensual_categoria.itertuples(index=False):
                presupuesto_mes_cat = float(
                    presupuesto_categoria_mes(historico_presupuesto, fila.GASTOS_CATEGORIA, fila.MES)
                ) if not historico_presupuesto.empty else 0.0
                historial_categoria.append({
                    "Categoría": fila.GASTOS_CATEGORIA,
                    "Año": fila.ANIO,
                    "Mes": fila.MES,
                    "Gasto": float(fila.Gasto),
                    "Presupuesto": presupuesto_mes_cat,
                    "Excedida": presupuesto_mes_cat > 0 and float(fila.Gasto) > presupuesto_mes_cat,
                    "Exceso %": ((float(fila.Gasto) - presupuesto_mes_cat) / presupuesto_mes_cat * 100)
                    if presupuesto_mes_cat > 0 else 0.0,
                })

        historico_eval = pd.DataFrame(historial_categoria)
        if not historico_eval.empty:
            resumen_sistematico = historico_eval.groupby("Categoría").agg(
                Meses_analizados=("Mes", "count"),
                Meses_excedidos=("Excedida", "sum"),
                Exceso_promedio_pct=("Exceso %", lambda s: float(s[s > 0].mean()) if (s > 0).any() else 0.0),
            ).reset_index()
            resumen_sistematico["Frecuencia de exceso %"] = (
                resumen_sistematico["Meses_excedidos"] / resumen_sistematico["Meses_analizados"] * 100
            )
            resumen_sistematico = resumen_sistematico.sort_values(
                ["Meses_excedidos", "Frecuencia de exceso %"], ascending=False
            )
            sistematicas = resumen_sistematico[
                (resumen_sistematico["Meses_excedidos"] >= 2)
                | (resumen_sistematico["Frecuencia de exceso %"] >= 60)
            ]
            if not sistematicas.empty:
                st.error(
                    "Estas categorías exceden el presupuesto de forma repetida. Esto puede indicar "
                    "un gasto estructural o un presupuesto subestimado."
                )
                st.dataframe(sistematicas, use_container_width=True, hide_index=True)
            else:
                st.success("No se detectaron incumplimientos sistemáticos con el histórico filtrado.")
        else:
            st.info("No hay histórico suficiente para evaluar categorías sistemáticamente mal presupuestadas.")

        st.markdown("## 9. Redistribución posible")
        excesos_redistribucion = presupuesto_categoria_tabla[
            presupuesto_categoria_tabla["Diferencia"] > 0
        ].copy().sort_values("Diferencia", ascending=False)
        disponibles_redistribucion = presupuesto_categoria_tabla[
            (presupuesto_categoria_tabla["Presupuesto"] > 0)
            & (presupuesto_categoria_tabla["Diferencia"] < 0)
        ].copy()
        disponibles_redistribucion["Disponible"] = -disponibles_redistribucion["Diferencia"]
        disponibles_redistribucion = disponibles_redistribucion.sort_values("Disponible", ascending=False)

        total_exceso = float(excesos_redistribucion["Diferencia"].sum()) if not excesos_redistribucion.empty else 0.0
        total_disponible_otras = float(disponibles_redistribucion["Disponible"].sum()) if not disponibles_redistribucion.empty else 0.0
        red1, red2, red3 = st.columns(3)
        red1.metric("Exceso por cubrir", f"${total_exceso:,.0f}")
        red2.metric("Disponibilidad contable", f"${total_disponible_otras:,.0f}")
        red3.metric("Cobertura posible", f"{min(total_disponible_otras / total_exceso * 100, 100):.1f}%" if total_exceso else "100.0%")

        if total_exceso > 0 and total_disponible_otras > 0:
            st.info(
                "Existe disponibilidad contable en otras categorías para cubrir parte del exceso. "
                "Antes de redistribuir, verifica compromisos futuros: dinero no ejecutado todavía no siempre está realmente libre."
            )
            rcol1, rcol2 = st.columns(2)
            with rcol1:
                st.markdown("#### Excesos prioritarios")
                st.dataframe(
                    excesos_redistribucion[["GASTOS_CATEGORIA", "Diferencia"]]
                    .rename(columns={"GASTOS_CATEGORIA": "Categoría", "Diferencia": "Exceso"})
                    .head(10), use_container_width=True, hide_index=True,
                )
            with rcol2:
                st.markdown("#### Disponibilidades potenciales")
                st.dataframe(
                    disponibles_redistribucion[["GASTOS_CATEGORIA", "Disponible"]]
                    .rename(columns={"GASTOS_CATEGORIA": "Categoría"})
                    .head(10), use_container_width=True, hide_index=True,
                )
        elif total_exceso <= 0:
            st.success("No existen excesos presupuestales que requieran redistribución.")
        else:
            st.warning("Existen excesos, pero no se identificó disponibilidad en otras categorías.")

        st.markdown("## 10. 🛠️ Plan de acción para cerrar dentro del presupuesto")
        acciones = []
        for _, fila in excesos_redistribucion.head(5).iterrows():
            acciones.append(
                f"Revisar **{fila['GASTOS_CATEGORIA']}**: excede el plan en **${fila['Diferencia']:,.0f}** "
                f"({fila['% ejecutado']:.1f}% ejecutado)."
            )
        categorias_en_atencion = presupuesto_categoria_tabla[
            presupuesto_categoria_tabla["Estado"] == "Atención"
        ].sort_values("% ejecutado", ascending=False)
        for _, fila in categorias_en_atencion.head(3).iterrows():
            margen = max(float(fila["Presupuesto"]) - float(fila["Gasto"]), 0.0)
            acciones.append(
                f"Limitar nuevos gastos en **{fila['GASTOS_CATEGORIA']}** a aproximadamente **${margen:,.0f}** "
                "durante el resto del periodo."
            )
        if gasto_sin_presupuesto > 0:
            acciones.append(
                f"Asignar presupuesto a los movimientos no planificados, que suman **${gasto_sin_presupuesto:,.0f}**."
            )
        if not acciones:
            acciones.append("Mantener el ritmo actual y revisar semanalmente las categorías en atención.")

        for accion in acciones:
            st.markdown(f"- {accion}")

        st.caption(
            "Las acciones son reglas calculadas con los datos filtrados. No sustituyen la revisión de pagos futuros, "
            "obligaciones contractuales o gastos extraordinarios pendientes."
        )

        st.markdown("## 11. Tabla maestra de cumplimiento")
        st.dataframe(
            presupuesto_categoria_tabla.rename(columns={"GASTOS_CATEGORIA": "Categoría"}),
            use_container_width=True, hide_index=True,
        )

        st.markdown("## 12. Comparación detallada por categoría")
        st.caption("Los gráficos se trasladaron desde Gastos sin modificar su construcción ni sus datos.")
        # CATEGORÍAS + DINERO NO UTILIZADO + LÍNEA DE PRESUPUESTO
        # ======================================================
        st.markdown("### Contexto presupuestal por categoría")
        st.caption(
            "Este gráfico fue trasladado desde Gastos. La lectura de cumplimiento, "
            "desviaciones y acciones correctivas está en la pestaña Presupuesto."
        )

        categorias_ingresos = (
            df.groupby("GASTOS_CATEGORIA", dropna=False)["GASTOS_CANTIDAD"]
            .sum()
            .reset_index()
            .rename(columns={
                "GASTOS_CATEGORIA": "Categoría",
                "GASTOS_CANTIDAD": "Monto",
            })
        )

        if not categorias_ingresos.empty:
            no_utilizado = max(float(total_ingresos) - float(total_gastos), 0.0)
            porcentaje_no_utilizado = (
                no_utilizado / float(total_ingresos) * 100
                if total_ingresos > 0
                else 0.0
            )

            fila_no_utilizado = pd.DataFrame({
                "Categoría": ["No utilizado"],
                "Monto": [no_utilizado],
            })

            categorias_ingresos = pd.concat(
                [categorias_ingresos, fila_no_utilizado],
                ignore_index=True,
            )

            categorias_ingresos["% de ingresos"] = (
                categorias_ingresos["Monto"] / total_ingresos * 100
                if total_ingresos > 0
                else 0.0
            )

            # Número de periodos reales filtrados para ajustar el presupuesto mensual.
            periodos_categoria = (
                df[["ANIO", "MES"]]
                .dropna(how="all")
                .drop_duplicates()
            )
            n_periodos_categoria = max(len(periodos_categoria), 1)

            # Presupuesto total por categoría para el periodo filtrado.
            categorias_ingresos["Presupuesto"] = categorias_ingresos["Categoría"].map(
                lambda categoria: (
                    0.0
                    if categoria == "No utilizado"
                    else float(
                        presupuesto_cat.get(normalizar(categoria), 0.0)
                    )
                )
            )

            categorias_ingresos["Diferencia vs presupuesto"] = (
                categorias_ingresos["Monto"] - categorias_ingresos["Presupuesto"]
            )
            categorias_ingresos["Lectura porcentual vs presupuesto"] = categorias_ingresos.apply(
                lambda r: (
                    "No aplica"
                    if r["Categoría"] == "No utilizado"
                    else "Sin presupuesto definido"
                    if r["Presupuesto"] <= 0
                    else f"Exceso: {(r['Monto'] - r['Presupuesto']) / r['Presupuesto'] * 100:.1f}%"
                    if r["Monto"] > r["Presupuesto"]
                    else f"Faltante: {(r['Presupuesto'] - r['Monto']) / r['Presupuesto'] * 100:.1f}%"
                    if r["Monto"] < r["Presupuesto"]
                    else "En presupuesto: 0.0%"
                ),
                axis=1,
            )

            categorias_ingresos = categorias_ingresos.sort_values(
                "Monto",
                ascending=False,
            ).reset_index(drop=True)

            categorias_ingresos["Etiqueta"] = categorias_ingresos.apply(
                lambda r: f"${r['Monto']:,.0f}<br>{r['% de ingresos']:.1f}%",
                axis=1,
            )

            categorias_gasto = categorias_ingresos[
                categorias_ingresos["Categoría"] != "No utilizado"
            ]
            categoria_mayor = (
                categorias_gasto.iloc[0]
                if not categorias_gasto.empty
                else None
            )

            if categoria_mayor is not None:
                st.success(
                    f"La categoría de mayor gasto es **{categoria_mayor['Categoría']}** con "
                    f"**${categoria_mayor['Monto']:,.0f}**, equivalente al "
                    f"**{categoria_mayor['% de ingresos']:.1f}%** de los ingresos."
                )

            st.info(
                f"Dinero **no utilizado: ${no_utilizado:,.0f}**, equivalente al "
                f"**{porcentaje_no_utilizado:.1f}%** de los ingresos filtrados."
            )

            # Blanco si el gasto está dentro de una tolerancia de ±10% frente al
            # punto amarillo del presupuesto. Fuera de esa zona se conservan
            # los colores actuales: rojo sobre presupuesto, azul por debajo y
            # verde para No utilizado. Sin presupuesto definido se muestra azul.
            colores_categorias = []
            for _, fila in categorias_ingresos.iterrows():
                if fila["Categoría"] == "No utilizado":
                    colores_categorias.append("#00FF66")
                elif (
                    fila["Presupuesto"] > 0
                    and abs(fila["Monto"] - fila["Presupuesto"]) / fila["Presupuesto"] <= 0.10
                ):
                    colores_categorias.append("#FFFFFF")
                elif fila["Presupuesto"] > 0 and fila["Monto"] > fila["Presupuesto"]:
                    colores_categorias.append("#FF003C")
                else:
                    colores_categorias.append("#3B82F6")

            fig_categoria_ingresos = go.Figure()

            fig_categoria_ingresos.add_trace(go.Bar(
                x=categorias_ingresos["Categoría"],
                y=categorias_ingresos["Monto"],
                name="Gasto real",
                text=categorias_ingresos["Etiqueta"],
                textposition="outside",
                cliponaxis=False,
                marker=dict(
                    color=colores_categorias,
                    line=dict(color="#E2E8F0", width=1.1),
                ),
                customdata=categorias_ingresos[
                    [
                        "% de ingresos",
                        "Presupuesto",
                        "Diferencia vs presupuesto",
                        "Lectura porcentual vs presupuesto",
                    ]
                ],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Gasto real: $%{y:,.0f}<br>"
                    "Porcentaje de los ingresos: %{customdata[0]:.2f}%<br>"
                    "Presupuesto ajustado: $%{customdata[1]:,.0f}<br>"
                    "Diferencia: $%{customdata[2]:,.0f}<br>"
                    "Desviación porcentual: <b>%{customdata[3]}</b>"
                    "<extra></extra>"
                ),
            ))

            # Línea de presupuesto sobre cada categoría.
            categorias_presupuesto = categorias_ingresos[
                categorias_ingresos["Categoría"] != "No utilizado"
            ]

            fig_categoria_ingresos.add_trace(go.Scatter(
                x=categorias_presupuesto["Categoría"],
                y=categorias_presupuesto["Presupuesto"],
                name="Presupuesto ajustado",
                mode="lines+markers",
                line=dict(
                    color="#FFEE00",
                    width=3,
                    dash="dash",
                    shape="linear",
                ),
                marker=dict(
                    size=9,
                    color="#FFEE00",
                    symbol="diamond",
                    line=dict(color="#422006", width=1.2),
                ),
                customdata=categorias_presupuesto[
                    ["Monto", "Diferencia vs presupuesto"]
                ],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Presupuesto ajustado: $%{y:,.0f}<br>"
                    "Gasto real: $%{customdata[0]:,.0f}<br>"
                    "Diferencia: $%{customdata[1]:,.0f}"
                    "<extra></extra>"
                ),
            ))

            fig_categoria_ingresos.update_layout(
                template="plotly_dark",
                height=610,
                paper_bgcolor="#000000",
                plot_bgcolor="#000000",
                font=dict(color="#E2E8F0"),
                title=dict(
                    text="Categorías de gasto, dinero no utilizado y presupuesto",
                    font=dict(color="#F8FAFC"),
                ),
                xaxis=dict(
                    title="Categoría",
                    type="category",
                    categoryorder="array",
                    categoryarray=categorias_ingresos["Categoría"].tolist(),
                    tickangle=-35,
                    gridcolor="rgba(148,163,184,0.08)",
                ),
                yaxis=dict(
                    title="Valor",
                    tickprefix="$",
                    tickformat=",.0f",
                    gridcolor="rgba(148,163,184,0.14)",
                    rangemode="tozero",
                ),
                bargap=0.28,
                margin=dict(t=95, b=145, l=70, r=35),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0,
                ),
                hoverlabel=dict(
                    bgcolor="#0F172A",
                    bordercolor="#FFEE00",
                    font=dict(color="#F8FAFC"),
                ),
            )

            st.plotly_chart(
                fig_categoria_ingresos,
                use_container_width=True,
                key="grafico_categorias_presupuesto_v1",
            )

            tabla_categoria_ingresos = categorias_ingresos.copy()
            tabla_categoria_ingresos["Monto"] = tabla_categoria_ingresos["Monto"].map(
                lambda x: f"${x:,.0f}"
            )
            tabla_categoria_ingresos["% de ingresos"] = tabla_categoria_ingresos[
                "% de ingresos"
            ].map(lambda x: f"{x:.2f}%")
            tabla_categoria_ingresos["Presupuesto"] = tabla_categoria_ingresos[
                "Presupuesto"
            ].map(lambda x: f"${x:,.0f}")
            tabla_categoria_ingresos["Diferencia vs presupuesto"] = (
                tabla_categoria_ingresos["Diferencia vs presupuesto"]
                .map(lambda x: f"${x:,.0f}")
            )

            st.dataframe(
                tabla_categoria_ingresos[
                    [
                        "Categoría",
                        "Monto",
                        "% de ingresos",
                        "Presupuesto",
                        "Diferencia vs presupuesto",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No hay datos de categorías para mostrar con los filtros actuales.")

        st.divider()
        st.markdown("## 13. Comparación detallada por subcategoría")
        # SUBCATEGORÍAS + LÍNEA DE PRESUPUESTO
        # ======================================================
        st.markdown("### 📊 Distribución de los ingresos por subcategoría")
        st.caption(
            "La línea amarilla muestra el presupuesto ajustado al periodo filtrado. "
            "Rojo = gasto por encima del presupuesto · Azul = gasto por debajo o igual al presupuesto."
        )

        subcategorias_ingresos = (
            sub_df.groupby("GASTOS_SUBCATEGORIA", dropna=False)["GASTOS_CANTIDAD"]
            .sum()
            .reset_index()
            .rename(columns={
                "GASTOS_SUBCATEGORIA": "Subcategoría",
                "GASTOS_CANTIDAD": "Monto",
            })
        )

        if not subcategorias_ingresos.empty:
            no_utilizado_sub = max(float(total_ingresos) - float(total_gastos), 0.0)
            porcentaje_no_utilizado_sub = (
                no_utilizado_sub / float(total_ingresos) * 100
                if total_ingresos > 0
                else 0.0
            )

            subcategorias_ingresos["% de ingresos"] = (
                subcategorias_ingresos["Monto"] / total_ingresos * 100
                if total_ingresos > 0
                else 0.0
            )

            periodos_subcategoria = (
                sub_df[["ANIO", "MES"]]
                .dropna(how="all")
                .drop_duplicates()
            )
            n_periodos_subcategoria = max(len(periodos_subcategoria), 1)

            # El presupuesto se busca por categoría + subcategoría y luego se suma
            # cuando una misma subcategoría aparece en más de una categoría.
            presupuesto_sub_agrupado = {}
            for categoria, subcategoria in (
                sub_df[["GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA"]]
                .drop_duplicates()
                .itertuples(index=False)
            ):
                valor_presupuesto = buscar_presupuesto_sub(
                    categoria,
                    subcategoria,
                    presupuesto_sub,
                )
                clave = str(subcategoria)
                presupuesto_sub_agrupado[clave] = (
                    presupuesto_sub_agrupado.get(clave, 0.0)
                    + float(valor_presupuesto)
                )

            subcategorias_ingresos["Presupuesto"] = subcategorias_ingresos[
                "Subcategoría"
            ].map(
                lambda subcategoria: presupuesto_sub_agrupado.get(str(subcategoria), 0.0)
            )

            subcategorias_ingresos["Diferencia vs presupuesto"] = (
                subcategorias_ingresos["Monto"]
                - subcategorias_ingresos["Presupuesto"]
            )
            subcategorias_ingresos["Lectura porcentual vs presupuesto"] = subcategorias_ingresos.apply(
                lambda r: (
                    "Sin presupuesto definido"
                    if r["Presupuesto"] <= 0
                    else f"Exceso: {(r['Monto'] - r['Presupuesto']) / r['Presupuesto'] * 100:.1f}%"
                    if r["Monto"] > r["Presupuesto"]
                    else f"Faltante: {(r['Presupuesto'] - r['Monto']) / r['Presupuesto'] * 100:.1f}%"
                    if r["Monto"] < r["Presupuesto"]
                    else "En presupuesto: 0.0%"
                ),
                axis=1,
            )

            subcategorias_ingresos = subcategorias_ingresos.sort_values(
                "Monto",
                ascending=False,
            ).reset_index(drop=True)

            subcategorias_ingresos["Etiqueta"] = subcategorias_ingresos.apply(
                lambda r: f"${r['Monto']:,.0f}<br>{r['% de ingresos']:.1f}%",
                axis=1,
            )

            subcategorias_gasto = subcategorias_ingresos.copy()
            subcategoria_mayor = (
                subcategorias_gasto.iloc[0]
                if not subcategorias_gasto.empty
                else None
            )

            if subcategoria_mayor is not None:
                st.success(
                    f"La subcategoría de mayor gasto es **{subcategoria_mayor['Subcategoría']}** con "
                    f"**${subcategoria_mayor['Monto']:,.0f}**, equivalente al "
                    f"**{subcategoria_mayor['% de ingresos']:.1f}%** de los ingresos."
                )

            st.info(
                f"Dinero **no utilizado: ${no_utilizado_sub:,.0f}**, equivalente al "
                f"**{porcentaje_no_utilizado_sub:.1f}%** de los ingresos filtrados."
            )

            colores_subcategorias = []
            for _, fila in subcategorias_ingresos.iterrows():
                if (
                    fila["Presupuesto"] > 0
                    and abs(fila["Monto"] - fila["Presupuesto"]) / fila["Presupuesto"] <= 0.10
                ):
                    colores_subcategorias.append("#FFFFFF")
                elif fila["Presupuesto"] > 0 and fila["Monto"] > fila["Presupuesto"]:
                    colores_subcategorias.append("#FF003C")
                else:
                    colores_subcategorias.append("#3B82F6")

            fig_subcategoria_ingresos = go.Figure()

            fig_subcategoria_ingresos.add_trace(go.Bar(
                x=subcategorias_ingresos["Subcategoría"],
                y=subcategorias_ingresos["Monto"],
                name="Gasto real",
                text=subcategorias_ingresos["Etiqueta"],
                textposition="outside",
                cliponaxis=False,
                marker=dict(
                    color=colores_subcategorias,
                    line=dict(color="#E2E8F0", width=1.1),
                ),
                customdata=subcategorias_ingresos[
                    [
                        "% de ingresos",
                        "Presupuesto",
                        "Diferencia vs presupuesto",
                        "Lectura porcentual vs presupuesto",
                    ]
                ],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Gasto real: $%{y:,.0f}<br>"
                    "Porcentaje de los ingresos: %{customdata[0]:.2f}%<br>"
                    "Presupuesto ajustado: $%{customdata[1]:,.0f}<br>"
                    "Diferencia: $%{customdata[2]:,.0f}<br>"
                    "Desviación porcentual: <b>%{customdata[3]}</b>"
                    "<extra></extra>"
                ),
            ))

            subcategorias_presupuesto = subcategorias_ingresos.copy()

            fig_subcategoria_ingresos.add_trace(go.Scatter(
                x=subcategorias_presupuesto["Subcategoría"],
                y=subcategorias_presupuesto["Presupuesto"],
                name="Presupuesto ajustado",
                mode="lines+markers",
                line=dict(
                    color="#FFEE00",
                    width=3,
                    dash="dash",
                    shape="linear",
                ),
                marker=dict(
                    size=9,
                    color="#FFEE00",
                    symbol="diamond",
                    line=dict(color="#422006", width=1.2),
                ),
                customdata=subcategorias_presupuesto[
                    ["Monto", "Diferencia vs presupuesto"]
                ],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Presupuesto ajustado: $%{y:,.0f}<br>"
                    "Gasto real: $%{customdata[0]:,.0f}<br>"
                    "Diferencia: $%{customdata[1]:,.0f}"
                    "<extra></extra>"
                ),
            ))

            fig_subcategoria_ingresos.update_layout(
                template="plotly_dark",
                height=680,
                paper_bgcolor="#000000",
                plot_bgcolor="#000000",
                font=dict(color="#E2E8F0"),
                title=dict(
                    text="Subcategorías de gasto y presupuesto",
                    font=dict(color="#F8FAFC"),
                ),
                xaxis=dict(
                    title="Subcategoría",
                    type="category",
                    categoryorder="array",
                    categoryarray=subcategorias_ingresos["Subcategoría"].tolist(),
                    tickangle=-40,
                    gridcolor="rgba(148,163,184,0.08)",
                    automargin=True,
                ),
                yaxis=dict(
                    title="Valor",
                    tickprefix="$",
                    tickformat=",.0f",
                    gridcolor="rgba(148,163,184,0.14)",
                    rangemode="tozero",
                ),
                bargap=0.24,
                margin=dict(t=95, b=190, l=70, r=35),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0,
                ),
                hoverlabel=dict(
                    bgcolor="#0F172A",
                    bordercolor="#FFEE00",
                    font=dict(color="#F8FAFC"),
                ),
            )

            st.plotly_chart(
                fig_subcategoria_ingresos,
                use_container_width=True,
                key="grafico_subcategorias_presupuesto_v1",
            )

            tabla_subcategorias_ingresos = subcategorias_ingresos.copy()
            tabla_subcategorias_ingresos["Monto"] = tabla_subcategorias_ingresos["Monto"].map(
                lambda x: f"${x:,.0f}"
            )
            tabla_subcategorias_ingresos["% de ingresos"] = tabla_subcategorias_ingresos[
                "% de ingresos"
            ].map(lambda x: f"{x:.2f}%")
            tabla_subcategorias_ingresos["Presupuesto"] = tabla_subcategorias_ingresos[
                "Presupuesto"
            ].map(lambda x: f"${x:,.0f}")
            tabla_subcategorias_ingresos["Diferencia vs presupuesto"] = (
                tabla_subcategorias_ingresos["Diferencia vs presupuesto"]
                .map(lambda x: f"${x:,.0f}")
            )

            st.dataframe(
                tabla_subcategorias_ingresos[
                    [
                        "Subcategoría",
                        "Monto",
                        "% de ingresos",
                        "Presupuesto",
                        "Diferencia vs presupuesto",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No hay datos de subcategorías para mostrar con los filtros actuales.")

        st.markdown("#### Detalle completo")
        resumen_sub = (
            sub_df.groupby(["GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA", "GASTOS_SUBCATEGORIA_2"])
            .agg(monto=("GASTOS_CANTIDAD", "sum"), transacciones=("GASTOS_CANTIDAD", "count"))
            .reset_index().sort_values("monto", ascending=False)
        )
        resumen_sub["presupuesto"] = resumen_sub.apply(
            lambda r: buscar_presupuesto_sub(r["GASTOS_CATEGORIA"], r["GASTOS_SUBCATEGORIA"], presupuesto_sub),
            axis=1,
        )
        resumen_sub["diferencia"] = resumen_sub["monto"] - resumen_sub["presupuesto"]
        st.dataframe(resumen_sub, use_container_width=True)
        csv = resumen_sub.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar resumen de subcategorías (CSV)", csv, "subcategorias.csv", "text/csv")


        st.markdown("## 14. Visualización avanzada del cumplimiento")
        st.subheader("🕸️ Radar Financiero Ejecutivo")
        st.caption(
            "🔴 Rojo = sobre presupuesto · ⚪ Blanco = cerca del presupuesto · 🔵 Azul = bajo presupuesto. "
            "Línea amarilla punteada = presupuesto acumulado del periodo desde Historico_presupuesto."
        )

        radar_df = df.copy()
        meses_radar = ", ".join(map(str, sorted(radar_df["MES"].dropna().unique())))
        periodos_radar = radar_df[["ANIO", "MES"]].dropna(how="all").drop_duplicates()
        n_periodos_radar = max(len(periodos_radar), 1)
        presupuesto_cat_radar = presupuesto_cat.copy()
        presupuesto_sub_radar = presupuesto_sub.copy()
        st.info(
            "El radar usa automáticamente los filtros del panel izquierdo"
            + (f". Periodo incluido: {meses_radar}." if meses_radar else ".")
            + f" Presupuesto ajustado a {n_periodos_radar} periodo(s) filtrado(s)."
        )

        st.markdown("#### Por categoría")
        fig_cat = construir_radar_categorias(radar_df, presupuesto_cat_radar)
        st.plotly_chart(fig_cat, use_container_width=True)

        comp_cat = (
            radar_df.groupby("GASTOS_CATEGORIA")["GASTOS_CANTIDAD"]
            .sum()
            .reset_index()
            .rename(columns={"GASTOS_CATEGORIA": "Categoría", "GASTOS_CANTIDAD": "Gasto"})
        )
        comp_cat["Presupuesto"] = comp_cat["Categoría"].map(
            lambda c: presupuesto_cat_radar.get(normalizar(c), 0)
        )
        comp_cat["Diferencia"] = comp_cat["Gasto"] - comp_cat["Presupuesto"]
        st.dataframe(comp_cat, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### Por subcategoría")
        fig_sub = construir_radar_subcategorias(radar_df, presupuesto_sub_radar)
        st.plotly_chart(fig_sub, use_container_width=True)

        comp_sub = (
            radar_df.dropna(subset=["GASTOS_SUBCATEGORIA"])
            .groupby(["GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA"])["GASTOS_CANTIDAD"]
            .sum()
            .reset_index()
            .rename(columns={"GASTOS_SUBCATEGORIA": "Subcategoría", "GASTOS_CANTIDAD": "Gasto"})
        )
        comp_sub["Presupuesto"] = comp_sub.apply(
            lambda r: buscar_presupuesto_sub(r["GASTOS_CATEGORIA"], r["Subcategoría"], presupuesto_sub_radar),
            axis=1,
        )
        comp_sub["Diferencia"] = comp_sub["Gasto"] - comp_sub["Presupuesto"]
        st.dataframe(comp_sub, use_container_width=True, hide_index=True)

        st.markdown("## 15. 🌱 Presupuesto aún sin estrenar")
        st.caption(
            "Muestra únicamente subcategorías con presupuesto asignado que nunca han tenido "
            "un movimiento de gasto en todo el historial, independientemente del periodo filtrado."
        )

        subcategorias_utilizadas = set()
        if not gastos.empty and "GASTOS_SUBCATEGORIA" in gastos.columns:
            subcategorias_utilizadas = {
                normalizar(subcategoria)
                for subcategoria in gastos["GASTOS_SUBCATEGORIA"].dropna()
                if str(subcategoria).strip()
            }

        presupuesto_sin_estrenar = []
        for (categoria, subcategoria), valor_presupuestado in presupuesto_sub.items():
            valor_presupuestado = float(valor_presupuestado or 0.0)
            subcategoria_normalizada = normalizar(subcategoria)
            if (
                valor_presupuestado <= 0
                or not subcategoria_normalizada
                or subcategoria_normalizada in subcategorias_utilizadas
            ):
                continue
            presupuesto_sin_estrenar.append({
                "Categoría": str(categoria).title(),
                "Subcategoría": str(subcategoria).title(),
                "Presupuesto disponible": valor_presupuestado,
            })

        presupuesto_sin_estrenar_df = pd.DataFrame(presupuesto_sin_estrenar)
        if not presupuesto_sin_estrenar_df.empty:
            presupuesto_sin_estrenar_df = presupuesto_sin_estrenar_df.sort_values(
                "Presupuesto disponible", ascending=False
            )
            total_sin_estrenar = float(
                presupuesto_sin_estrenar_df["Presupuesto disponible"].sum()
            )
            cantidad_sin_estrenar = len(presupuesto_sin_estrenar_df)
            porcentaje_sin_estrenar = (
                total_sin_estrenar / presupuesto_periodo_total * 100
                if presupuesto_periodo_total > 0 else 0.0
            )

            se1, se2, se3 = st.columns(3)
            se1.metric("💰 Presupuesto disponible", f"${total_sin_estrenar:,.0f}")
            se2.metric("🌱 Subcategorías sin estrenar", cantidad_sin_estrenar)
            se3.metric("📊 % del presupuesto", f"{porcentaje_sin_estrenar:.1f}%")

            presupuesto_sin_estrenar_df["Concepto"] = (
                presupuesto_sin_estrenar_df["Categoría"]
                + " › "
                + presupuesto_sin_estrenar_df["Subcategoría"]
            )
            max_presupuesto_sin_estrenar = float(
                presupuesto_sin_estrenar_df["Presupuesto disponible"].max()
            )
            promedio_sin_estrenar = float(
                presupuesto_sin_estrenar_df["Presupuesto disponible"].mean()
            )
            presupuesto_sin_estrenar_orden = presupuesto_sin_estrenar_df.sort_values(
                "Presupuesto disponible", ascending=True
            )
            valores_sin_estrenar = presupuesto_sin_estrenar_orden[
                "Presupuesto disponible"
            ].astype(float).tolist()
            conceptos_sin_estrenar = presupuesto_sin_estrenar_orden["Concepto"].tolist()

            # Plotly no admite gradientes nativos dentro de una barra. Se crea un
            # degradado real con 32 segmentos apilados y sin bordes visibles.
            segmentos_degradado = 32
            ancho_segmento = max(max_presupuesto_sin_estrenar, 1.0) / segmentos_degradado
            color_inicial = (4, 18, 11)      # negro con matiz verde
            color_final = (0, 255, 102)      # verde neón intenso

            def color_degradado(fraccion):
                rgb = tuple(
                    round(inicio + (fin - inicio) * fraccion)
                    for inicio, fin in zip(color_inicial, color_final)
                )
                return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"

            fig_sin_estrenar = go.Figure()
            for indice_segmento in range(segmentos_degradado):
                inicio_segmento = indice_segmento * ancho_segmento
                valores_segmento = [
                    max(min(valor - inicio_segmento, ancho_segmento), 0.0)
                    for valor in valores_sin_estrenar
                ]
                fig_sin_estrenar.add_trace(go.Bar(
                    x=valores_segmento,
                    y=conceptos_sin_estrenar,
                    orientation="h",
                    width=0.62,
                    marker=dict(
                        color=color_degradado(
                            indice_segmento / max(segmentos_degradado - 1, 1)
                        ),
                        line=dict(width=0),
                    ),
                    customdata=valores_sin_estrenar,
                    hovertemplate=(
                        "<b>🌱 %{y}</b><br><br>"
                        "Presupuesto disponible&nbsp; <b>$%{customdata:,.0f}</b><br>"
                        "Estado&nbsp; Sin movimientos en todo el historial"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                ))

            # Etiquetas independientes para mantener el valor al final del degradado.
            fig_sin_estrenar.add_trace(go.Scatter(
                x=valores_sin_estrenar,
                y=conceptos_sin_estrenar,
                mode="text",
                text=[f"<b>${valor:,.0f}</b>" for valor in valores_sin_estrenar],
                textposition="middle right",
                textfont=dict(color="#EFFFF4", size=12),
                cliponaxis=False,
                hoverinfo="skip",
                showlegend=False,
            ))
            fig_sin_estrenar.update_layout(
                height=max(390, len(presupuesto_sin_estrenar_df) * 52),
                barmode="stack",
                bargap=0.28,
                xaxis_title="",
                yaxis_title="",
                showlegend=False,
                margin=dict(l=210, r=95, t=105, b=45),
                hoverlabel=dict(
                    bgcolor="#052E1A",
                    bordercolor="#00FF66",
                    font=dict(color="#F3FFF7", size=13),
                ),
                uniformtext=dict(minsize=11, mode="show"),
            )
            fig_sin_estrenar.update_xaxes(
                tickprefix="$",
                tickformat=",.0f",
                range=[0, max(max_presupuesto_sin_estrenar * 1.22, 1.0)],
                gridcolor="rgba(120,255,170,0.10)",
                zeroline=False,
                showline=False,
                tickfont=dict(color="#A7CDB4", size=11),
            )
            fig_sin_estrenar.update_yaxes(
                gridcolor="rgba(0,0,0,0)",
                showline=False,
                tickfont=dict(color="#E9FFF0", size=12),
            )
            if len(presupuesto_sin_estrenar_df) > 1:
                fig_sin_estrenar.add_vline(
                    x=promedio_sin_estrenar,
                    line_width=1.2,
                    line_dash="dot",
                    line_color="rgba(255,255,255,0.42)",
                    annotation_text=f"Promedio ${promedio_sin_estrenar:,.0f}",
                    annotation_position="top",
                    annotation_font=dict(color="#D7FFE4", size=10),
                )
            fig_sin_estrenar = estilo_grafico(
                fig_sin_estrenar,
                "🌱 Subcategorías con presupuesto aún sin estrenar",
            )
            fig_sin_estrenar.update_layout(
                paper_bgcolor="#020A06",
                plot_bgcolor="#020A06",
                title=dict(
                    text=(
                        "<b>🌱 Subcategorías con presupuesto aún sin estrenar</b>"
                        "<br><span style='font-size:12px;color:#8FD8A8'>"
                        "De negro a verde neón = mayor presupuesto asignado sin ningún uso histórico</span>"
                    ),
                    x=0.01,
                    xanchor="left",
                    font=dict(color="#F2FFF6", size=20),
                ),
                margin=dict(l=210, r=95, t=105, b=45),
            )
            fig_sin_estrenar.update_xaxes(
                gridcolor="rgba(120,255,170,0.10)",
                linecolor="rgba(0,0,0,0)",
                zeroline=False,
                showline=False,
            )
            fig_sin_estrenar.update_yaxes(
                gridcolor="rgba(0,0,0,0)",
                linecolor="rgba(0,0,0,0)",
                zeroline=False,
                showline=False,
            )
            st.plotly_chart(
                fig_sin_estrenar,
                use_container_width=True,
                key="presupuesto_subcategorias_nunca_utilizadas",
            )

            with st.expander("Ver detalle del presupuesto sin estrenar"):
                st.dataframe(
                    presupuesto_sin_estrenar_df[
                        ["Categoría", "Subcategoría", "Presupuesto disponible"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Presupuesto disponible": st.column_config.NumberColumn(
                            "Presupuesto disponible", format="$%d"
                        )
                    },
                )
        else:
            st.success(
                "Todas las subcategorías con presupuesto asignado ya han sido utilizadas "
                "al menos una vez en el historial."
            )

        st.markdown("## 16. ✅ Resultado final del presupuesto")
        st.caption(
            "Una lectura directa del período filtrado: blanco = dentro del margen de ±10 %, "
            "verde = disponibilidad y rojo = exceso. Los gastos sin presupuesto se destacan "
            "en morado dentro de las tarjetas y el detalle."
        )

        selector_nivel, selector_vista = st.columns(2)
        with selector_nivel:
            nivel_cumplimiento = st.radio(
                "Nivel de análisis",
                ["Categorías", "Subcategorías"],
                horizontal=True,
                key="presupuesto_resultado_final_nivel_v13",
            )
        with selector_vista:
            vista_cumplimiento = st.radio(
                "Forma de visualizar",
                ["Porcentaje", "Valor en efectivo"],
                horizontal=True,
                key="presupuesto_resultado_final_vista_v13",
            )

        if nivel_cumplimiento == "Categorías":
            gastos_resultado = (
                df.groupby("GASTOS_CATEGORIA", as_index=False)["GASTOS_CANTIDAD"]
                .sum()
                .rename(columns={"GASTOS_CATEGORIA": "Categoría", "GASTOS_CANTIDAD": "Gasto"})
            ) if not df.empty else pd.DataFrame(columns=["Categoría", "Gasto"])
            gasto_por_clave = {
                normalizar(fila["Categoría"]): float(fila["Gasto"])
                for _, fila in gastos_resultado.iterrows()
            }
            claves_resultado = set(gasto_por_clave) | set(presupuesto_cat)
            categorias_filtro_explicito = {
                normalizar(categoria) for categoria in categorias_elegidas
            }
            if categorias_filtro_explicito:
                claves_resultado &= categorias_filtro_explicito
            resultado_final_df = pd.DataFrame([
                {
                    "Concepto": str(clave).title(),
                    "Presupuesto": float(presupuesto_cat.get(clave, 0.0) or 0.0),
                    "Gasto": float(gasto_por_clave.get(clave, 0.0) or 0.0),
                }
                for clave in sorted(claves_resultado)
            ])
        else:
            gastos_resultado = (
                df.dropna(subset=["GASTOS_SUBCATEGORIA"])
                .groupby(["GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA"], as_index=False)["GASTOS_CANTIDAD"]
                .sum()
                .rename(columns={"GASTOS_CANTIDAD": "Gasto"})
            ) if not df.empty else pd.DataFrame(
                columns=["GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA", "Gasto"]
            )
            gasto_por_clave = {
                (normalizar(fila["GASTOS_CATEGORIA"]), normalizar(fila["GASTOS_SUBCATEGORIA"])):
                float(fila["Gasto"])
                for _, fila in gastos_resultado.iterrows()
            }
            claves_resultado = set(gasto_por_clave) | set(presupuesto_sub)
            categorias_filtro_explicito = {
                normalizar(categoria) for categoria in categorias_elegidas
            }
            subcategorias_filtro_explicito = {
                normalizar(subcategoria) for subcategoria in subcategorias_elegidas
            }
            if categorias_filtro_explicito:
                claves_resultado = {
                    clave for clave in claves_resultado if clave[0] in categorias_filtro_explicito
                }
            if subcategorias_filtro_explicito:
                claves_resultado = {
                    clave for clave in claves_resultado if clave[1] in subcategorias_filtro_explicito
                }
            resultado_final_df = pd.DataFrame([
                {
                    "Concepto": f"{str(clave[0]).title()} › {str(clave[1]).title()}",
                    "Presupuesto": float(presupuesto_sub.get(clave, 0.0) or 0.0),
                    "Gasto": float(gasto_por_clave.get(clave, 0.0) or 0.0),
                }
                for clave in sorted(claves_resultado)
            ])

        if resultado_final_df.empty:
            st.info("No hay información presupuestal para evaluar con los filtros actuales.")
        else:
            resultado_final_df["Saldo"] = (
                resultado_final_df["Presupuesto"] - resultado_final_df["Gasto"]
            )
            resultado_final_df["% ejecutado"] = resultado_final_df.apply(
                lambda fila: fila["Gasto"] / fila["Presupuesto"] * 100
                if fila["Presupuesto"] > 0 else None,
                axis=1,
            )

            def clasificar_cumplimiento(fila):
                presupuesto_valor = float(fila["Presupuesto"])
                gasto_valor = float(fila["Gasto"])
                if presupuesto_valor <= 0:
                    return "Sin presupuesto" if gasto_valor > 0 else "Sin actividad"
                if gasto_valor == 0:
                    return "Sin utilizar"
                ejecucion = gasto_valor / presupuesto_valor * 100
                if ejecucion > 110:
                    return "Excedido"
                if ejecucion < 90:
                    return "Con disponibilidad"
                return "Cumplido"

            resultado_final_df["Estado"] = resultado_final_df.apply(
                clasificar_cumplimiento, axis=1
            )
            resultado_final_df["Desviación %"] = resultado_final_df.apply(
                lambda fila: (fila["Gasto"] - fila["Presupuesto"]) / fila["Presupuesto"] * 100
                if fila["Presupuesto"] > 0 else None,
                axis=1,
            )
            resultado_final_df["Desviación texto"] = resultado_final_df.apply(
                lambda fila: f"{fila['Desviación %']:+.1f}%"
                if fila["Presupuesto"] > 0 else "No aplica: sin presupuesto",
                axis=1,
            )
            resultado_final_df["Impacto"] = resultado_final_df["Saldo"].abs()
            resultado_final_df["Resultado efectivo"] = resultado_final_df["Saldo"].map(
                lambda valor: (
                    f"Disponible ${valor:,.0f}" if valor >= 0
                    else f"Exceso ${abs(valor):,.0f}"
                )
            )

            presupuesto_evaluable = float(resultado_final_df["Presupuesto"].sum())
            gasto_evaluable = float(resultado_final_df["Gasto"].sum())
            ejecucion_general = (
                gasto_evaluable / presupuesto_evaluable * 100
                if presupuesto_evaluable > 0 else 0.0
            )
            cantidad_cumplida = int((resultado_final_df["Estado"] == "Cumplido").sum())
            exceso_total = float(
                (-resultado_final_df.loc[resultado_final_df["Saldo"] < 0, "Saldo"]).sum()
            )
            disponibilidad_total = float(
                resultado_final_df.loc[resultado_final_df["Saldo"] > 0, "Saldo"].sum()
            )
            sin_presupuesto_total = float(
                resultado_final_df.loc[
                    resultado_final_df["Estado"] == "Sin presupuesto", "Gasto"
                ].sum()
            )

            rf1, rf2, rf3, rf4, rf5 = st.columns(5)
            rf1.metric("Ejecución general", f"{ejecucion_general:.1f}%")
            rf2.metric("✅ Cumplidas", cantidad_cumplida)
            rf3.metric("🟢 Disponible", f"${disponibilidad_total:,.0f}")
            rf4.metric("🔴 Exceso", f"${exceso_total:,.0f}")
            rf5.metric("🟣 Sin presupuesto", f"${sin_presupuesto_total:,.0f}")

            if presupuesto_evaluable > 0:
                balance_periodo = presupuesto_evaluable - gasto_evaluable
                estado_periodo = "disponibles" if balance_periodo >= 0 else "de exceso"
                st.info(
                    f"En el período filtrado se ejecutó el {ejecucion_general:.1f}% del presupuesto "
                    f"evaluado. El resultado neto es ${abs(balance_periodo):,.0f} {estado_periodo}."
                )

            if vista_cumplimiento == "Porcentaje":
                resultado_grafico = resultado_final_df[
                    resultado_final_df["Presupuesto"] > 0
                ].copy()
            else:
                resultado_grafico = resultado_final_df[
                    (resultado_final_df["Presupuesto"] > 0)
                    | (resultado_final_df["Gasto"] > 0)
                ].copy()
            if not resultado_grafico.empty:
                colores_estado = {
                    "Cumplido": "#F8FAFC",
                    "Con disponibilidad": "#00FF88",
                    "Excedido": "#FF1744",
                    "Sin utilizar": "#064E3B",
                    "Sin presupuesto": "#A855F7",
                    "Sin actividad": "#475569",
                }
                resultado_grafico["Color"] = resultado_grafico["Estado"].map(colores_estado)
                if vista_cumplimiento == "Porcentaje":
                    resultado_grafico = resultado_grafico.sort_values(
                        ["% ejecutado", "Impacto"], ascending=[True, False]
                    )
                else:
                    resultado_grafico["Mayor valor"] = resultado_grafico[
                        ["Presupuesto", "Gasto"]
                    ].max(axis=1)
                    resultado_grafico = resultado_grafico.sort_values(
                        ["Mayor valor", "Impacto"], ascending=[True, True]
                    )
                altura_resultado = max(430, min(1050, len(resultado_grafico) * 43 + 150))
                datos_tooltip = resultado_grafico[
                    [
                        "Presupuesto", "Gasto", "Saldo", "Desviación texto", "Estado",
                        "Resultado efectivo",
                    ]
                ]
                tooltip_cumplimiento = (
                    "<b>%{y}</b><br><br>"
                    "Estado: <b>%{customdata[4]}</b><br>"
                    "Presupuesto: $%{customdata[0]:,.0f}<br>"
                    "Gasto: $%{customdata[1]:,.0f}<br>"
                    "Resultado: <b>%{customdata[5]}</b><br>"
                    "Desviación: %{customdata[3]}"
                    "<extra></extra>"
                )

                if vista_cumplimiento == "Porcentaje":
                    max_ejecucion = float(
                        pd.to_numeric(
                            resultado_grafico["% ejecutado"], errors="coerce"
                        ).max()
                    )
                    fig_resultado_final = go.Figure(go.Bar(
                        x=resultado_grafico["% ejecutado"],
                        y=resultado_grafico["Concepto"],
                        orientation="h",
                        marker=dict(
                            color=resultado_grafico["Color"],
                            line=dict(color="rgba(255,255,255,0.32)", width=0.7),
                        ),
                        text=resultado_grafico["% ejecutado"].map(
                            lambda valor: f"{valor:.1f}%"
                        ),
                        textposition="outside",
                        textfont=dict(color="#FFFFFF", size=11),
                        cliponaxis=False,
                        customdata=datos_tooltip,
                        hovertemplate=tooltip_cumplimiento,
                        showlegend=False,
                    ))
                    fig_resultado_final.add_vrect(
                        x0=90, x1=110,
                        fillcolor="rgba(255,255,255,0.055)",
                        line_width=0,
                        layer="below",
                    )
                    fig_resultado_final.add_vline(
                        x=100,
                        line_width=2,
                        line_dash="dot",
                        line_color="#FFEE00",
                        annotation_text="Presupuesto 100%",
                        annotation_position="top",
                        annotation_font=dict(color="#FFEE00", size=11),
                    )
                    titulo_eje_resultado = "Porcentaje del presupuesto ejecutado"
                    titulo_resultado = f"Cumplimiento por {nivel_cumplimiento.lower()}"
                else:
                    resultado_grafico["Gastado dentro del presupuesto"] = resultado_grafico.apply(
                        lambda fila: min(fila["Gasto"], fila["Presupuesto"])
                        if fila["Presupuesto"] > 0 else 0.0,
                        axis=1,
                    )
                    resultado_grafico["Disponible"] = (
                        resultado_grafico["Presupuesto"] - resultado_grafico["Gasto"]
                    ).clip(lower=0)
                    resultado_grafico["Exceso"] = resultado_grafico.apply(
                        lambda fila: max(fila["Gasto"] - fila["Presupuesto"], 0.0)
                        if fila["Presupuesto"] > 0 else 0.0,
                        axis=1,
                    )
                    resultado_grafico["Sin presupuesto"] = resultado_grafico.apply(
                        lambda fila: fila["Gasto"] if fila["Presupuesto"] <= 0 else 0.0,
                        axis=1,
                    )
                    max_valor_efectivo = float(
                        resultado_grafico[["Presupuesto", "Gasto"]].max().max()
                    )
                    fig_resultado_final = go.Figure()
                    segmentos_efectivo = [
                        ("Gastado dentro del presupuesto", "#F8FAFC"),
                        ("Disponible", "#00FF66"),
                        ("Exceso", "#FF0033"),
                        ("Sin presupuesto", "#A855F7"),
                    ]
                    for nombre_segmento, color_segmento in segmentos_efectivo:
                        fig_resultado_final.add_trace(go.Bar(
                            x=resultado_grafico[nombre_segmento],
                            y=resultado_grafico["Concepto"],
                            orientation="h",
                            name=nombre_segmento,
                            marker=dict(
                                color=color_segmento,
                                line=dict(color="rgba(255,255,255,0.20)", width=0.5),
                            ),
                            customdata=datos_tooltip,
                            hovertemplate=(
                                "<b>%{y}</b><br><br>"
                                f"{nombre_segmento}: <b>$%{{x:,.0f}}</b><br>"
                                "Presupuesto: $%{customdata[0]:,.0f}<br>"
                                "Gasto total: $%{customdata[1]:,.0f}<br>"
                                "Resultado: <b>%{customdata[5]}</b><br>"
                                "Desviación: %{customdata[3]}"
                                "<extra></extra>"
                            ),
                        ))
                    fig_resultado_final.add_trace(go.Scatter(
                        x=resultado_grafico["Mayor valor"],
                        y=resultado_grafico["Concepto"],
                        mode="text",
                        name="Resultado",
                        text=resultado_grafico["Resultado efectivo"],
                        textposition="middle right",
                        textfont=dict(color="#FFFFFF", size=10),
                        cliponaxis=False,
                        hoverinfo="skip",
                        showlegend=False,
                    ))
                    titulo_eje_resultado = "Valor en efectivo"
                    titulo_resultado = (
                        f"Cómo se distribuyó el presupuesto por {nivel_cumplimiento.lower()}"
                    )

                    resultado_grafico["Estado del saldo"] = resultado_grafico.apply(
                        lambda fila: "Sin presupuesto"
                        if fila["Presupuesto"] <= 0 and fila["Gasto"] > 0
                        else "Disponible" if fila["Saldo"] > 0
                        else "Exceso" if fila["Saldo"] < 0
                        else "Exacto",
                        axis=1,
                    )
                    colores_saldo = {
                        "Disponible": "#00FF66",
                        "Exceso": "#FF0033",
                        "Exacto": "#F8FAFC",
                        "Sin presupuesto": "#A855F7",
                    }
                    max_saldo_absoluto = max(
                        float(resultado_grafico["Saldo"].abs().max()), 1.0
                    )
                    fig_saldo_efectivo = go.Figure(go.Bar(
                        x=resultado_grafico["Saldo"],
                        y=resultado_grafico["Concepto"],
                        orientation="h",
                        marker=dict(
                            color=resultado_grafico["Estado del saldo"].map(colores_saldo),
                            line=dict(color="rgba(255,255,255,0.20)", width=0.5),
                        ),
                        text=resultado_grafico["Resultado efectivo"],
                        textposition="outside",
                        textfont=dict(color="#FFFFFF", size=10),
                        cliponaxis=False,
                        customdata=datos_tooltip,
                        hovertemplate=tooltip_cumplimiento,
                        showlegend=False,
                    ))
                    for nombre_estado, color_estado in colores_saldo.items():
                        fig_saldo_efectivo.add_trace(go.Scatter(
                            x=[None],
                            y=[None],
                            mode="markers",
                            name=nombre_estado,
                            marker=dict(color=color_estado, size=10, symbol="square"),
                            hoverinfo="skip",
                        ))
                    fig_saldo_efectivo.add_vline(
                        x=0,
                        line_width=2,
                        line_color="#FFEE00",
                        annotation_text="Saldo exacto $0",
                        annotation_position="top",
                        annotation_font=dict(color="#FFEE00", size=11),
                    )
                    fig_saldo_efectivo.add_annotation(
                        x=0.02,
                        y=1.07,
                        xref="paper",
                        yref="paper",
                        text="← Exceso",
                        showarrow=False,
                        font=dict(color="#FF6B81", size=12),
                    )
                    fig_saldo_efectivo.add_annotation(
                        x=0.98,
                        y=1.07,
                        xref="paper",
                        yref="paper",
                        text="Disponibilidad →",
                        showarrow=False,
                        font=dict(color="#00FF66", size=12),
                    )
                    fig_saldo_efectivo.update_layout(
                        height=altura_resultado,
                        showlegend=True,
                        bargap=0.28,
                        margin=dict(l=220, r=90, t=95, b=65),
                        paper_bgcolor="#020407",
                        plot_bgcolor="#020407",
                        hoverlabel=dict(
                            bgcolor="#07111F",
                            bordercolor="#38BDF8",
                            font=dict(color="#F8FAFC", size=13),
                        ),
                    )
                    fig_saldo_efectivo.update_xaxes(
                        title="Exceso ← Saldo en efectivo → Disponibilidad",
                        tickprefix="$",
                        tickformat=",.0f",
                        range=[-max_saldo_absoluto * 1.35, max_saldo_absoluto * 1.35],
                        gridcolor="rgba(148,163,184,0.10)",
                        zeroline=False,
                    )
                    fig_saldo_efectivo.update_yaxes(
                        title="",
                        gridcolor="rgba(0,0,0,0)",
                    )
                    fig_saldo_efectivo = estilo_grafico(
                        fig_saldo_efectivo,
                        f"Saldo disponible o excedido por {nivel_cumplimiento.lower()}",
                    )

                fig_resultado_final.update_layout(
                    height=altura_resultado,
                    showlegend=vista_cumplimiento == "Valor en efectivo",
                    barmode="stack" if vista_cumplimiento == "Valor en efectivo" else "relative",
                    bargap=0.28,
                    margin=dict(l=220, r=90, t=85, b=65),
                    paper_bgcolor="#020407",
                    plot_bgcolor="#020407",
                    hoverlabel=dict(
                        bgcolor="#07111F",
                        bordercolor="#38BDF8",
                        font=dict(color="#F8FAFC", size=13),
                    ),
                )
                if vista_cumplimiento == "Porcentaje":
                    fig_resultado_final.update_xaxes(
                        title=titulo_eje_resultado,
                        ticksuffix="%",
                        range=[0, max(125, max_ejecucion * 1.14)],
                        gridcolor="rgba(148,163,184,0.10)",
                        zeroline=False,
                    )
                else:
                    fig_resultado_final.update_xaxes(
                        title=titulo_eje_resultado,
                        tickprefix="$",
                        tickformat=",.0f",
                        range=[0, max(max_valor_efectivo * 1.34, 1.0)],
                        gridcolor="rgba(148,163,184,0.10)",
                        zeroline=False,
                    )
                fig_resultado_final.update_yaxes(
                    title="",
                    gridcolor="rgba(0,0,0,0)",
                )
                fig_resultado_final = estilo_grafico(
                    fig_resultado_final,
                    titulo_resultado,
                )
                if vista_cumplimiento == "Valor en efectivo":
                    st.caption(
                        "La línea amarilla representa un saldo exacto de $0. A la derecha está el dinero "
                        "disponible; a la izquierda, el exceso. La longitud de la barra indica el valor en pesos."
                    )
                    st.plotly_chart(
                        fig_saldo_efectivo,
                        use_container_width=True,
                        key=(
                            f"presupuesto_saldo_efectivo_{nivel_cumplimiento.lower()}_v13"
                        ),
                    )
                else:
                    st.plotly_chart(
                        fig_resultado_final,
                        use_container_width=True,
                        key=(
                            f"presupuesto_resultado_final_{nivel_cumplimiento.lower()}_"
                            f"{vista_cumplimiento.lower()}_v13"
                        ),
                    )

            excepciones_df = resultado_final_df[
                ~resultado_final_df["Estado"].isin(["Cumplido", "Sin actividad"])
            ].sort_values("Impacto", ascending=False)
            with st.expander(
                f"Ver partidas que requieren atención ({len(excepciones_df)})",
                expanded=False,
            ):
                if excepciones_df.empty:
                    st.success("Todas las partidas evaluables están dentro del margen de ±10 %.")
                else:
                    iconos_estado = {
                        "Excedido": "🔴 Excedido",
                        "Con disponibilidad": "🟢 Con disponibilidad",
                        "Sin utilizar": "🌱 Sin utilizar",
                        "Sin presupuesto": "🟣 Sin presupuesto",
                    }
                    tabla_excepciones = excepciones_df.copy()
                    tabla_excepciones["Estado"] = tabla_excepciones["Estado"].map(
                        iconos_estado
                    ).fillna(tabla_excepciones["Estado"])
                    st.dataframe(
                        tabla_excepciones[
                            [
                                "Estado", "Concepto", "Presupuesto", "Gasto",
                                "Saldo", "% ejecutado", "Desviación %",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Presupuesto": st.column_config.NumberColumn(format="$%d"),
                            "Gasto": st.column_config.NumberColumn(format="$%d"),
                            "Saldo": st.column_config.NumberColumn(format="$%d"),
                            "% ejecutado": st.column_config.NumberColumn(format="%.1f%%"),
                            "Desviación %": st.column_config.NumberColumn(format="%+.1f%%"),
                        },
                    )

            resultado_distribucion_final = resultado_final_df[
                (resultado_final_df["Presupuesto"] > 0)
                | (resultado_final_df["Gasto"] > 0)
            ].copy()
            if not resultado_distribucion_final.empty:
                resultado_distribucion_final["Mayor valor"] = resultado_distribucion_final[
                    ["Presupuesto", "Gasto"]
                ].max(axis=1)
                resultado_distribucion_final = resultado_distribucion_final.sort_values(
                    ["Mayor valor", "Impacto"], ascending=[True, True]
                )
                resultado_distribucion_final[
                    "Gastado dentro del presupuesto"
                ] = resultado_distribucion_final.apply(
                    lambda fila: min(fila["Gasto"], fila["Presupuesto"])
                    if fila["Presupuesto"] > 0 else 0.0,
                    axis=1,
                )
                resultado_distribucion_final["Disponible"] = (
                    resultado_distribucion_final["Presupuesto"]
                    - resultado_distribucion_final["Gasto"]
                ).clip(lower=0)
                resultado_distribucion_final["Exceso"] = resultado_distribucion_final.apply(
                    lambda fila: max(fila["Gasto"] - fila["Presupuesto"], 0.0)
                    if fila["Presupuesto"] > 0 else 0.0,
                    axis=1,
                )
                resultado_distribucion_final["Sin presupuesto"] = (
                    resultado_distribucion_final.apply(
                        lambda fila: fila["Gasto"]
                        if fila["Presupuesto"] <= 0 else 0.0,
                        axis=1,
                    )
                )
                datos_tooltip_distribucion = resultado_distribucion_final[
                    [
                        "Presupuesto", "Gasto", "Saldo", "Desviación texto", "Estado",
                        "Resultado efectivo",
                    ]
                ]
                max_distribucion_efectivo = float(
                    resultado_distribucion_final[["Presupuesto", "Gasto"]].max().max()
                )
                altura_distribucion = max(
                    430, min(1050, len(resultado_distribucion_final) * 43 + 150)
                )
                fig_distribucion_final = go.Figure()
                segmentos_distribucion = [
                    ("Gastado dentro del presupuesto", "#F8FAFC"),
                    ("Disponible", "#00FF66"),
                    ("Exceso", "#FF0033"),
                    ("Sin presupuesto", "#A855F7"),
                ]
                for nombre_segmento, color_segmento in segmentos_distribucion:
                    fig_distribucion_final.add_trace(go.Bar(
                        x=resultado_distribucion_final[nombre_segmento],
                        y=resultado_distribucion_final["Concepto"],
                        orientation="h",
                        name=nombre_segmento,
                        marker=dict(
                            color=color_segmento,
                            line=dict(color="rgba(255,255,255,0.20)", width=0.5),
                        ),
                        customdata=datos_tooltip_distribucion,
                        hovertemplate=(
                            "<b>%{y}</b><br><br>"
                            f"{nombre_segmento}: <b>$%{{x:,.0f}}</b><br>"
                            "Presupuesto: $%{customdata[0]:,.0f}<br>"
                            "Gasto total: $%{customdata[1]:,.0f}<br>"
                            "Resultado: <b>%{customdata[5]}</b><br>"
                            "Desviación: %{customdata[3]}"
                            "<extra></extra>"
                        ),
                    ))
                fig_distribucion_final.add_trace(go.Scatter(
                    x=resultado_distribucion_final["Mayor valor"],
                    y=resultado_distribucion_final["Concepto"],
                    mode="text",
                    name="Resultado",
                    text=resultado_distribucion_final["Resultado efectivo"],
                    textposition="middle right",
                    textfont=dict(color="#FFFFFF", size=10),
                    cliponaxis=False,
                    hoverinfo="skip",
                    showlegend=False,
                ))
                fig_distribucion_final.update_layout(
                    height=altura_distribucion,
                    showlegend=True,
                    barmode="stack",
                    bargap=0.28,
                    margin=dict(l=220, r=90, t=85, b=65),
                    paper_bgcolor="#020407",
                    plot_bgcolor="#020407",
                    hoverlabel=dict(
                        bgcolor="#07111F",
                        bordercolor="#38BDF8",
                        font=dict(color="#F8FAFC", size=13),
                    ),
                )
                fig_distribucion_final.update_xaxes(
                    title="Valor en efectivo",
                    tickprefix="$",
                    tickformat=",.0f",
                    range=[0, max(max_distribucion_efectivo * 1.34, 1.0)],
                    gridcolor="rgba(148,163,184,0.10)",
                    zeroline=False,
                )
                fig_distribucion_final.update_yaxes(
                    title="",
                    gridcolor="rgba(0,0,0,0)",
                )
                fig_distribucion_final = estilo_grafico(
                    fig_distribucion_final,
                    f"Cómo se distribuyó el presupuesto por {nivel_cumplimiento.lower()}",
                )
                st.markdown("#### Distribución final del presupuesto")
                st.caption(
                    "Esta gráfica permanece visible como cierre: blanco es lo gastado dentro del plan, "
                    "verde es el dinero disponible, rojo es el exceso y morado es gasto sin presupuesto."
                )
                st.plotly_chart(
                    fig_distribucion_final,
                    use_container_width=True,
                    key=f"presupuesto_distribucion_final_{nivel_cumplimiento.lower()}_v13",
                )

    if pestana_activa == etiquetas_pestanas[4]:
        contexto_pestana("¿De dónde proviene el dinero?", "Muestra las fuentes, la composición y la evolución de los ingresos dentro del periodo seleccionado.")
        st.markdown("## Fuentes y comportamiento de los ingresos")
        st.subheader("💰 Panel de Ingresos")
        st.caption("Los ingresos se leen del bloque transaccional y se clasifican por la fecha real del movimiento.")

        if ingresos_filtrados.empty:
            st.warning("No se encontraron ingresos con fecha válida dentro del periodo seleccionado.")
        else:
            ingresos_mes = ingresos_filtrados.groupby("MES", as_index=False)["INGRESOS_CANTIDAD"].sum()
            ingresos_mes = ordenar_por_mes(ingresos_mes)
            ingresos_fuente = ingresos_filtrados.groupby("INGRESOS_FUENTE", as_index=False)["INGRESOS_CANTIDAD"].sum().sort_values("INGRESOS_CANTIDAD", ascending=False)
            ingresos_tipo = ingresos_filtrados.groupby("INGRESOS_CATEGORIA", as_index=False)["INGRESOS_CANTIDAD"].sum().sort_values("INGRESOS_CANTIDAD", ascending=False)


            # ============================================================
            # V9.15 · PANORAMA, ESTABILIDAD, DIVERSIFICACIÓN Y RIESGO
            # ============================================================
            ingresos_analisis = ingresos_filtrados.copy()
            ingresos_analisis["INGRESOS_FECHA"] = pd.to_datetime(
                ingresos_analisis["INGRESOS_FECHA"], errors="coerce", dayfirst=True
            )
            ingresos_analisis["INGRESOS_CANTIDAD"] = pd.to_numeric(
                ingresos_analisis["INGRESOS_CANTIDAD"], errors="coerce"
            ).fillna(0)
            ingresos_analisis["INGRESOS_FUENTE"] = (
                ingresos_analisis["INGRESOS_FUENTE"].astype("string").fillna("Sin fuente").str.strip()
            )
            ingresos_analisis["INGRESOS_CATEGORIA"] = (
                ingresos_analisis["INGRESOS_CATEGORIA"].astype("string").fillna("Sin tipo").str.strip()
            )
            ingresos_analisis["PERIODO"] = ingresos_analisis["INGRESOS_FECHA"].dt.to_period("M").astype("string")

            total_ingresos_panel = float(ingresos_analisis["INGRESOS_CANTIDAD"].sum())
            meses_validos_ing = ingresos_analisis.loc[
                ingresos_analisis["INGRESOS_FECHA"].notna(), "PERIODO"
            ].nunique()
            promedio_mensual_ing = total_ingresos_panel / max(int(meses_validos_ing), 1)
            fuente_principal = ingresos_fuente.iloc[0]["INGRESOS_FUENTE"] if not ingresos_fuente.empty else "Sin fuente"
            monto_fuente_principal = float(ingresos_fuente.iloc[0]["INGRESOS_CANTIDAD"]) if not ingresos_fuente.empty else 0.0
            pct_fuente_principal = monto_fuente_principal / total_ingresos_panel * 100 if total_ingresos_panel else 0.0
            pct_top3_fuentes = float(ingresos_fuente.head(3)["INGRESOS_CANTIDAD"].sum()) / total_ingresos_panel * 100 if total_ingresos_panel else 0.0
            numero_fuentes = int(ingresos_fuente["INGRESOS_FUENTE"].nunique()) if not ingresos_fuente.empty else 0

            # Clasificación exacta y excluyente. ``NO LABORAL`` se evalúa antes
            # que cualquier coincidencia laboral para evitar falsos positivos.
            ingresos_analisis["TIPO_INGRESO"] = ingresos_analisis["INGRESOS_CATEGORIA"].map(etiqueta_tipo_ingreso)
            mask_laboral_ing = ingresos_analisis["TIPO_INGRESO"].eq("Laborales")
            mask_no_laboral_ing = ingresos_analisis["TIPO_INGRESO"].eq("No laborales")
            mask_sin_clasificar_ing = ingresos_analisis["TIPO_INGRESO"].eq("Sin clasificar")
            ingreso_laboral = float(ingresos_analisis.loc[mask_laboral_ing, "INGRESOS_CANTIDAD"].sum())
            ingreso_no_laboral = float(ingresos_analisis.loc[mask_no_laboral_ing, "INGRESOS_CANTIDAD"].sum())
            ingreso_sin_clasificar = float(ingresos_analisis.loc[mask_sin_clasificar_ing, "INGRESOS_CANTIDAD"].sum())
            pct_laboral = ingreso_laboral / total_ingresos_panel * 100 if total_ingresos_panel else 0.0
            pct_no_laboral = ingreso_no_laboral / total_ingresos_panel * 100 if total_ingresos_panel else 0.0
            pct_sin_clasificar = ingreso_sin_clasificar / total_ingresos_panel * 100 if total_ingresos_panel else 0.0
            ingresos_tipo = (
                ingresos_analisis.groupby("TIPO_INGRESO", as_index=False)["INGRESOS_CANTIDAD"]
                .sum().sort_values("INGRESOS_CANTIDAD", ascending=False)
            )

            ingresos_periodo = (
                ingresos_analisis.dropna(subset=["INGRESOS_FECHA"])
                .groupby("PERIODO", as_index=False)["INGRESOS_CANTIDAD"].sum()
                .sort_values("PERIODO")
            )
            ingreso_max_mensual = float(ingresos_periodo["INGRESOS_CANTIDAD"].max()) if not ingresos_periodo.empty else 0.0
            ingreso_min_mensual = float(ingresos_periodo["INGRESOS_CANTIDAD"].min()) if not ingresos_periodo.empty else 0.0
            desviacion_ingresos = float(ingresos_periodo["INGRESOS_CANTIDAD"].std(ddof=0)) if len(ingresos_periodo) > 1 else 0.0
            coef_variacion_ing = desviacion_ingresos / promedio_mensual_ing * 100 if promedio_mensual_ing else 0.0
            if coef_variacion_ing <= 10:
                estabilidad_ing = "Muy estable"
                icono_estabilidad = "🟢"
            elif coef_variacion_ing <= 25:
                estabilidad_ing = "Estable"
                icono_estabilidad = "🔵"
            elif coef_variacion_ing <= 45:
                estabilidad_ing = "Variable"
                icono_estabilidad = "🟠"
            else:
                estabilidad_ing = "Muy variable"
                icono_estabilidad = "🔴"

            st.markdown("### 🧭 Panorama general de los ingresos")
            st.caption("Lectura rápida del volumen, origen, diversificación y estabilidad de los ingresos filtrados.")
            pi1, pi2, pi3, pi4 = st.columns(4)
            pi1.metric("💰 Ingresos totales", f"${total_ingresos_panel:,.0f}")
            pi2.metric("📆 Promedio mensual", f"${promedio_mensual_ing:,.0f}")
            pi3.metric("🏆 Fuente principal", str(fuente_principal), f"{pct_fuente_principal:.1f}% del total")
            pi4.metric("🧩 Fuentes activas", numero_fuentes)
            pi5, pi6, pi7, pi8 = st.columns(4)
            pi5.metric("💼 Ingreso laboral", f"{pct_laboral:.1f}%", f"${ingreso_laboral:,.0f}")
            pi6.metric("🌱 No laboral", f"{pct_no_laboral:.1f}%", f"${ingreso_no_laboral:,.0f}")
            pi7.metric("❔ Sin clasificar", f"{pct_sin_clasificar:.1f}%", f"${ingreso_sin_clasificar:,.0f}")
            pi8.metric(f"{icono_estabilidad} Estabilidad", estabilidad_ing, f"Variación: {coef_variacion_ing:.1f}%")
            if ingreso_sin_clasificar > 0:
                st.warning(f"🟣 Hay **${ingreso_sin_clasificar:,.0f}** sin clasificación. Revise la categoría en el bloque de ingresos de la hoja Transaccional.")

            st.markdown("### 🧩 Concentración y diversificación")
            cd1, cd2, cd3, cd4 = st.columns(4)
            cd1.metric("🎯 Fuente principal", f"{pct_fuente_principal:.1f}%")
            cd2.metric("🔝 Tres principales", f"{pct_top3_fuentes:.1f}%")
            cd3.metric("🔗 Dependencia", "Alta" if pct_fuente_principal >= 60 else "Media" if pct_fuente_principal >= 35 else "Baja")
            cd4.metric("🌐 Diversificación", "Alta" if numero_fuentes >= 5 and pct_fuente_principal < 40 else "Media" if numero_fuentes >= 3 else "Baja")
            if pct_fuente_principal >= 60:
                st.warning(f"⚠️ **Dependencia alta:** {fuente_principal} aporta {pct_fuente_principal:.1f}% de los ingresos del periodo.")
            else:
                st.success(f"✅ La fuente principal representa {pct_fuente_principal:.1f}% del total; la concentración no es crítica con los datos filtrados.")

            # ============================================================
            # V9.15 MEJORADA · CALIDAD, ESTABILIDAD Y ESCENARIOS POR FUENTE
            # ============================================================
            participaciones_fuente = (
                ingresos_fuente["INGRESOS_CANTIDAD"] / total_ingresos_panel
                if total_ingresos_panel else pd.Series(dtype=float)
            )
            indice_hhi = float((participaciones_fuente.pow(2).sum()) * 10000) if not participaciones_fuente.empty else 10000.0
            puntaje_diversificacion = max(0.0, min(30.0, 30.0 * (1 - min(indice_hhi, 10000) / 10000)))
            puntaje_estabilidad = max(0.0, min(30.0, 30.0 * (1 - min(coef_variacion_ing, 100) / 100)))
            meses_por_fuente_score = (
                ingresos_analisis.dropna(subset=["INGRESOS_FECHA"])
                .groupby("INGRESOS_FUENTE")["PERIODO"].nunique()
            )
            recurrencia_promedio = float(meses_por_fuente_score.mean()) if not meses_por_fuente_score.empty else 0.0
            puntaje_recurrencia = min(20.0, recurrencia_promedio / max(int(meses_validos_ing), 1) * 20.0)
            puntaje_dependencia = max(0.0, min(15.0, 15.0 * (1 - pct_fuente_principal / 100)))
            puntaje_calidad = 5.0 if ingreso_sin_clasificar == 0 else max(0.0, 5.0 * (1 - pct_sin_clasificar / 100))
            score_calidad_ingresos = round(
                puntaje_diversificacion + puntaje_estabilidad + puntaje_recurrencia
                + puntaje_dependencia + puntaje_calidad, 1
            )
            if score_calidad_ingresos >= 80:
                nivel_calidad_ing = "Muy sólida"
                icono_calidad_ing = "🟢"
            elif score_calidad_ingresos >= 65:
                nivel_calidad_ing = "Sólida"
                icono_calidad_ing = "🔵"
            elif score_calidad_ingresos >= 45:
                nivel_calidad_ing = "Vulnerable"
                icono_calidad_ing = "🟠"
            else:
                nivel_calidad_ing = "Frágil"
                icono_calidad_ing = "🔴"

            st.markdown("### 🛡️ Score de calidad de los ingresos")
            sc1, sc2 = st.columns([1, 2])
            with sc1:
                st.metric(f"{icono_calidad_ing} Calidad", f"{score_calidad_ingresos:.1f}/100", nivel_calidad_ing)
                st.caption("Integra diversificación, estabilidad, recurrencia, dependencia y calidad de clasificación.")
            with sc2:
                score_componentes = pd.DataFrame({
                    "Componente": ["Diversificación", "Estabilidad", "Recurrencia", "Baja dependencia", "Calidad de datos"],
                    "Puntos": [puntaje_diversificacion, puntaje_estabilidad, puntaje_recurrencia, puntaje_dependencia, puntaje_calidad],
                    "Máximo": [30, 30, 20, 15, 5],
                    "Icono": ["🌐", "📉", "🔁", "🛡️", "🧹"],
                })
                score_componentes["Etiqueta"] = score_componentes.apply(
                    lambda r: f"{r['Icono']} {r['Componente']}", axis=1
                )
                fig_score_ing = px.bar(
                    score_componentes, x="Puntos", y="Etiqueta", orientation="h", text="Puntos",
                    color="Puntos", color_continuous_scale=["#FF1744", "#FFD600", "#00FF88"],
                    range_x=[0, 30],
                )
                fig_score_ing.update_traces(
                    texttemplate="%{text:.1f}", textposition="outside",
                    customdata=score_componentes[["Máximo"]],
                    hovertemplate="<b>%{y}</b><br>⭐ Puntos: %{x:.1f}<br>🎯 Máximo: %{customdata[0]:.0f}<extra></extra>",
                )
                fig_score_ing.update_layout(height=350, showlegend=False, coloraxis_showscale=False)
                st.plotly_chart(estilo_grafico(fig_score_ing, "Componentes de la calidad del ingreso"), use_container_width=True)

            # Estabilidad y riqueza de información por fuente.
            fuente_periodo = (
                ingresos_analisis.dropna(subset=["INGRESOS_FECHA"])
                .groupby(["INGRESOS_FUENTE", "PERIODO"], as_index=False)["INGRESOS_CANTIDAD"].sum()
            )
            estabilidad_fuentes = []
            for fuente, grupo in fuente_periodo.groupby("INGRESOS_FUENTE"):
                valores = grupo["INGRESOS_CANTIDAD"].astype(float)
                promedio_f = float(valores.mean()) if not valores.empty else 0.0
                desv_f = float(valores.std(ddof=0)) if len(valores) > 1 else 0.0
                cv_f = desv_f / promedio_f * 100 if promedio_f else 0.0
                meses_f = int(grupo["PERIODO"].nunique())
                movimientos_f = int((ingresos_analisis["INGRESOS_FUENTE"] == fuente).sum())
                total_f = float(valores.sum())
                if meses_f <= 1:
                    nivel_f = "Esporádica"
                    icono_f = "⚪"
                elif cv_f <= 15:
                    nivel_f = "Muy estable"
                    icono_f = "🟢"
                elif cv_f <= 35:
                    nivel_f = "Estable"
                    icono_f = "🔵"
                elif cv_f <= 60:
                    nivel_f = "Variable"
                    icono_f = "🟠"
                else:
                    nivel_f = "Muy variable"
                    icono_f = "🔴"
                estabilidad_fuentes.append({
                    "Fuente": fuente, "Total": total_f, "Participación %": total_f / total_ingresos_panel * 100 if total_ingresos_panel else 0,
                    "Promedio mensual": promedio_f, "Meses activos": meses_f, "Movimientos": movimientos_f,
                    "Variación %": cv_f, "Estabilidad": f"{icono_f} {nivel_f}",
                })
            estabilidad_fuentes_df = pd.DataFrame(estabilidad_fuentes).sort_values("Total", ascending=False)

            st.markdown("### 🏦 Estabilidad y recurrencia por fuente")
            if not estabilidad_fuentes_df.empty:
                ef1, ef2 = st.columns([1.25, 1])
                with ef1:
                    fig_est_fuente = px.bar(
                        estabilidad_fuentes_df.sort_values("Total"),
                        x="Total", y="Fuente", orientation="h", text="Participación %",
                        color="Variación %", color_continuous_scale=["#00FF88", "#FFD600", "#FF1744"],
                    )
                    fig_est_fuente.update_traces(
                        texttemplate="%{text:.1f}%", textposition="outside",
                        customdata=estabilidad_fuentes_df.sort_values("Total")[["Promedio mensual", "Meses activos", "Movimientos", "Variación %", "Estabilidad"]],
                        hovertemplate=(
                            "<b>🏦 %{y}</b><br>💰 Total: $%{x:,.0f}<br>📊 Participación: %{text:.1f}%<br>"
                            "📆 Promedio mensual: $%{customdata[0]:,.0f}<br>🗓️ Meses activos: %{customdata[1]}<br>"
                            "🧾 Movimientos: %{customdata[2]}<br>📉 Variación: %{customdata[3]:.1f}%<br>"
                            "🛡️ Estado: %{customdata[4]}<extra></extra>"
                        ),
                    )
                    fig_est_fuente.update_layout(height=max(410, len(estabilidad_fuentes_df) * 42), coloraxis_colorbar_title="Variación %")
                    st.plotly_chart(estilo_grafico(fig_est_fuente, "Valor y estabilidad de cada fuente"), use_container_width=True)
                with ef2:
                    st.dataframe(
                        estabilidad_fuentes_df.style.format({
                            "Total": "${:,.0f}", "Participación %": "{:.1f}%", "Promedio mensual": "${:,.0f}", "Variación %": "{:.1f}%"
                        }), use_container_width=True, hide_index=True,
                    )

            # Eficiencia laboral usando el bloque original K:Q conservado en felicidad_trabajos.
            if felicidad_trabajos_filtrados is not None and not felicidad_trabajos_filtrados.empty:
                eficiencia_ing = felicidad_trabajos_filtrados.copy()
                fuente_col_eff = next((c for c in ["EMPRESA", "TRABAJO", "FUENTE", "NOMBRE"] if c in eficiencia_ing.columns), None)
                valor_col_eff = next((c for c in ["VALOR", "INGRESO", "MONTO"] if c in eficiencia_ing.columns), None)
                horas_col_eff = next((c for c in ["HORAS", "HORAS_TRABAJADAS"] if c in eficiencia_ing.columns), None)
                if fuente_col_eff and valor_col_eff and horas_col_eff:
                    eficiencia_ing[valor_col_eff] = pd.to_numeric(eficiencia_ing[valor_col_eff], errors="coerce").fillna(0)
                    eficiencia_ing[horas_col_eff] = pd.to_numeric(eficiencia_ing[horas_col_eff], errors="coerce").fillna(0)
                    resumen_eff = eficiencia_ing.groupby(fuente_col_eff, as_index=False).agg(
                        Ingreso=(valor_col_eff, "sum"), Horas=(horas_col_eff, "sum")
                    )
                    resumen_eff["Valor por hora"] = resumen_eff.apply(
                        lambda r: r["Ingreso"] / r["Horas"] if r["Horas"] > 0 else 0.0, axis=1
                    )
                    resumen_eff = resumen_eff[resumen_eff["Ingreso"] > 0].sort_values("Valor por hora", ascending=False)
                    if not resumen_eff.empty:
                        st.markdown("### ⏱️ Eficiencia de las fuentes laborales")
                        fig_eff = px.scatter(
                            resumen_eff, x="Horas", y="Ingreso", size="Valor por hora", color="Valor por hora",
                            text=fuente_col_eff, color_continuous_scale=["#00B7FF", "#00FF88", "#FFD600"],
                        )
                        fig_eff.update_traces(
                            textposition="top center",
                            customdata=resumen_eff[["Valor por hora"]],
                            hovertemplate=(
                                "<b>🏢 %{text}</b><br>⏱️ Horas: %{x:,.1f}<br>💰 Ingreso: $%{y:,.0f}<br>"
                                "⚡ Valor por hora: $%{customdata[0]:,.0f}<extra></extra>"
                            ),
                        )
                        fig_eff.update_layout(height=480, coloraxis_colorbar_title="$/hora")
                        st.plotly_chart(estilo_grafico(fig_eff, "Horas invertidas frente al ingreso generado"), use_container_width=True)

            # Simulador de reducción o pérdida de la fuente principal.
            st.markdown("### 🧪 Simulador de dependencia")
            reduccion_fuente = st.slider(
                f"Reducción simulada de {fuente_principal}", 0, 100, 100, 5,
                help="100% simula la pérdida completa de la fuente principal; no modifica los datos.",
                key="simulador_reduccion_fuente_ingresos_v915m",
            )
            perdida_simulada = monto_fuente_principal * reduccion_fuente / 100
            ingreso_restante_sim = max(total_ingresos_panel - perdida_simulada, 0.0)
            cobertura_sim = ingreso_restante_sim / total_gastos * 100 if total_gastos else 0.0
            sim1, sim2, sim3, sim4 = st.columns(4)
            sim1.metric("🏦 Fuente evaluada", str(fuente_principal))
            sim2.metric("📉 Reducción", f"{reduccion_fuente}%", f"-${perdida_simulada:,.0f}")
            sim3.metric("💰 Ingreso restante", f"${ingreso_restante_sim:,.0f}")
            sim4.metric("🛡️ Cobertura de gastos", f"{cobertura_sim:.1f}%")
            if cobertura_sim < 100:
                st.error(f"🚨 Con este escenario faltarían **${max(total_gastos - ingreso_restante_sim, 0):,.0f}** para cubrir los gastos filtrados.")
            else:
                st.success(f"✅ Incluso con este escenario, los ingresos restantes cubrirían el **{cobertura_sim:.1f}%** de los gastos filtrados.")

            # Curva acumulada y previsión simple.
            if not ingresos_periodo.empty:
                ingresos_periodo_acum = ingresos_periodo.copy()
                ingresos_periodo_acum["Acumulado"] = ingresos_periodo_acum["INGRESOS_CANTIDAD"].cumsum()
                st.markdown("### 📈 Crecimiento acumulado y previsión")
                ca1, ca2 = st.columns([1.4, 1])
                with ca1:
                    fig_acum_ing = go.Figure()
                    fig_acum_ing.add_trace(go.Bar(
                        x=ingresos_periodo_acum["PERIODO"], y=ingresos_periodo_acum["INGRESOS_CANTIDAD"],
                        name="Ingreso mensual", marker_color="#00B7FF",
                        hovertemplate="<b>📅 %{x}</b><br>💰 Ingreso mensual: $%{y:,.0f}<extra></extra>",
                    ))
                    fig_acum_ing.add_trace(go.Scatter(
                        x=ingresos_periodo_acum["PERIODO"], y=ingresos_periodo_acum["Acumulado"],
                        name="Acumulado", mode="lines+markers+text", line=dict(color="#00FF88", width=4),
                        marker=dict(size=10), text=ingresos_periodo_acum["Acumulado"], texttemplate="$%{text:,.0f}",
                        textposition="top center",
                        hovertemplate="<b>📈 %{x}</b><br>💎 Acumulado: $%{y:,.0f}<extra></extra>",
                    ))
                    fig_acum_ing.update_layout(height=450, legend=dict(orientation="h", y=1.08))
                    st.plotly_chart(estilo_grafico(fig_acum_ing, "Ingreso mensual y acumulado"), use_container_width=True)
                with ca2:
                    ultimos_ing = ingresos_periodo["INGRESOS_CANTIDAD"].tail(3).astype(float)
                    ingreso_proyectado = float(ultimos_ing.mean()) if not ultimos_ing.empty else 0.0
                    variacion_reciente = (
                        (float(ultimos_ing.iloc[-1]) - float(ultimos_ing.iloc[0])) / float(ultimos_ing.iloc[0]) * 100
                        if len(ultimos_ing) >= 2 and float(ultimos_ing.iloc[0]) else 0.0
                    )
                    st.metric("🔮 Próximo mes estimado", f"${ingreso_proyectado:,.0f}")
                    st.metric("📊 Cambio reciente", f"{variacion_reciente:+.1f}%")
                    st.caption("Estimación simple con el promedio de los últimos tres meses disponibles. No representa un ingreso confirmado.")

            # Recurrencia aproximada: una fuente presente en al menos dos meses se considera habitual.
            meses_por_fuente = (
                ingresos_analisis.dropna(subset=["INGRESOS_FECHA"])
                .groupby("INGRESOS_FUENTE")["PERIODO"].nunique()
            )
            fuentes_recurrentes = set(meses_por_fuente[meses_por_fuente >= 2].index)
            texto_extra_ing = (
                ingresos_analisis.get("INGRESOS_DESCRIPCION", pd.Series("", index=ingresos_analisis.index)).astype(str).map(normalizar)
                + " " + ingresos_analisis["INGRESOS_CATEGORIA"].astype(str).map(normalizar)
            )
            claves_extra_ing = ["PRIMA", "BONIFIC", "EXTRAORD", "RETROACT", "INDEMNIZ", "VENTA", "PREMIO"]
            mask_extra_ing = texto_extra_ing.map(lambda valor: any(clave in valor for clave in claves_extra_ing))
            mask_recurrente_ing = ingresos_analisis["INGRESOS_FUENTE"].isin(fuentes_recurrentes) & ~mask_extra_ing
            ingreso_habitual = float(ingresos_analisis.loc[mask_recurrente_ing, "INGRESOS_CANTIDAD"].sum())
            ingreso_extraordinario = float(ingresos_analisis.loc[mask_extra_ing, "INGRESOS_CANTIDAD"].sum())
            ingreso_ocasional = max(total_ingresos_panel - ingreso_habitual - ingreso_extraordinario, 0.0)
            habitual_mensual = ingreso_habitual / max(int(meses_validos_ing), 1)

            st.markdown("### 🔁 Ingreso habitual, ocasional y extraordinario")
            clas_ing = pd.DataFrame({
                "Naturaleza": ["Habitual", "Ocasional", "Extraordinario"],
                "Valor": [ingreso_habitual, ingreso_ocasional, ingreso_extraordinario],
            })
            fig_nat_ing = px.bar(
                clas_ing, x="Naturaleza", y="Valor", color="Naturaleza", text="Valor",
                color_discrete_map={"Habitual":"#00FF9C", "Ocasional":"#38BDF8", "Extraordinario":"#FFB000"},
            )
            fig_nat_ing.update_traces(
                texttemplate="$%{text:,.0f}", textposition="outside",
                customdata=clas_ing[["Valor"]],
                hovertemplate="<b>💵 %{x}</b><br>💰 Valor: $%{y:,.0f}<extra></extra>",
            )
            fig_nat_ing.update_layout(showlegend=False, height=390)
            st.plotly_chart(estilo_grafico(fig_nat_ing, "Naturaleza de los ingresos"), use_container_width=True)
            st.info(f"💡 Ingreso habitual mensual estimado: **${habitual_mensual:,.0f}**. Las primas y bonificaciones no se tratan como ingreso mensual permanente.")

            st.markdown("### 📊 Estabilidad mensual y comparación reciente")
            est1, est2 = st.columns([1.45, 1])
            with est1:
                fig_est_ing = go.Figure()
                fig_est_ing.add_trace(go.Bar(
                    x=ingresos_periodo["PERIODO"], y=ingresos_periodo["INGRESOS_CANTIDAD"],
                    name="Ingreso mensual", marker_color="#00DFA2",
                    text=ingresos_periodo["INGRESOS_CANTIDAD"], texttemplate="$%{text:,.0f}", textposition="outside",
                    hovertemplate="<b>📅 %{x}</b><br>Ingreso: $%{y:,.0f}<br>Comparación visual con el promedio<extra></extra>",
                ))
                fig_est_ing.add_hline(y=promedio_mensual_ing, line_color="#FFEE00", line_dash="dash", line_width=3,
                                      annotation_text=f"Promedio ${promedio_mensual_ing:,.0f}")
                fig_est_ing.update_layout(height=430, showlegend=False)
                st.plotly_chart(estilo_grafico(fig_est_ing, "Ingreso mensual frente a tu promedio"), use_container_width=True)
            with est2:
                if len(ingresos_periodo) >= 2:
                    actual_ing = float(ingresos_periodo.iloc[-1]["INGRESOS_CANTIDAD"])
                    anterior_ing = float(ingresos_periodo.iloc[-2]["INGRESOS_CANTIDAD"])
                    cambio_ing = actual_ing - anterior_ing
                    cambio_pct_ing = cambio_ing / anterior_ing * 100 if anterior_ing else 0.0
                    st.metric("🔄 Cambio último mes", f"{cambio_pct_ing:+.1f}%", f"${cambio_ing:+,.0f}")
                    st.metric("📉 Mínimo mensual", f"${ingreso_min_mensual:,.0f}")
                    st.metric("📈 Máximo mensual", f"${ingreso_max_mensual:,.0f}")
                    st.metric("📏 Desviación mensual", f"${desviacion_ingresos:,.0f}")
                else:
                    st.info("ℹ️ Se necesitan al menos dos meses con ingresos para comparar la evolución.")

            # Fuentes nuevas, perdidas y cambios entre los dos últimos meses.
            if len(ingresos_periodo) >= 2:
                periodo_actual_ing = ingresos_periodo.iloc[-1]["PERIODO"]
                periodo_anterior_ing = ingresos_periodo.iloc[-2]["PERIODO"]
                tabla_fuentes_periodo = ingresos_analisis.pivot_table(
                    index="INGRESOS_FUENTE", columns="PERIODO", values="INGRESOS_CANTIDAD", aggfunc="sum", fill_value=0
                )
                for per in [periodo_actual_ing, periodo_anterior_ing]:
                    if per not in tabla_fuentes_periodo.columns:
                        tabla_fuentes_periodo[per] = 0.0
                cambios_fuente = tabla_fuentes_periodo[[periodo_anterior_ing, periodo_actual_ing]].copy()
                cambios_fuente["Cambio"] = cambios_fuente[periodo_actual_ing] - cambios_fuente[periodo_anterior_ing]
                nuevas_fuentes = cambios_fuente[(cambios_fuente[periodo_anterior_ing] == 0) & (cambios_fuente[periodo_actual_ing] > 0)].index.tolist()
                fuentes_perdidas = cambios_fuente[(cambios_fuente[periodo_anterior_ing] > 0) & (cambios_fuente[periodo_actual_ing] == 0)].index.tolist()
                st.markdown("### 🆕 Fuentes nuevas, perdidas y principales cambios")
                cf1, cf2 = st.columns(2)
                with cf1:
                    st.success("🆕 **Fuentes nuevas:** " + (", ".join(map(str, nuevas_fuentes)) if nuevas_fuentes else "Ninguna"))
                    st.error("📭 **Fuentes sin ingreso reciente:** " + (", ".join(map(str, fuentes_perdidas)) if fuentes_perdidas else "Ninguna"))
                with cf2:
                    cambios_mostrar = cambios_fuente.reset_index().sort_values("Cambio", ascending=False)
                    fig_cambios_fuente = px.bar(
                        cambios_mostrar, x="Cambio", y="INGRESOS_FUENTE", orientation="h", text="Cambio",
                        color="Cambio", color_continuous_scale=[(0,"#FF1744"),(0.5,"#94A3B8"),(1,"#00E676")],
                    )
                    fig_cambios_fuente.update_traces(
                        texttemplate="$%{text:+,.0f}", textposition="outside",
                        customdata=cambios_mostrar[[periodo_anterior_ing, periodo_actual_ing]],
                        hovertemplate=("<b>🔄 %{y}</b><br>" + periodo_anterior_ing + ": $%{customdata[0]:,.0f}<br>" + periodo_actual_ing + ": $%{customdata[1]:,.0f}<br>Cambio: $%{x:+,.0f}<extra></extra>"),
                    )
                    fig_cambios_fuente.update_yaxes(autorange="reversed")
                    st.plotly_chart(estilo_grafico(fig_cambios_fuente, "Cambio por fuente frente al mes anterior"), use_container_width=True)

            # Cobertura de gastos habituales y simulación de pérdida de fuente principal.
            gastos_habituales_df = agregar_tipo_gasto(df) if not df.empty else df.copy()
            if not gastos_habituales_df.empty and "TIPO_GASTO" in gastos_habituales_df.columns:
                mask_no_extra_g = ~gastos_habituales_df["TIPO_GASTO"].astype(str).map(normalizar).str.contains("EXTRAORD")
                gasto_habitual_total = float(gastos_habituales_df.loc[mask_no_extra_g, "GASTOS_CANTIDAD"].sum())
            else:
                gasto_habitual_total = float(total_gastos)
            gasto_habitual_mensual = gasto_habitual_total / max(int(meses_validos_ing), 1)
            cobertura_habitual = habitual_mensual / gasto_habitual_mensual * 100 if gasto_habitual_mensual else 0.0
            ingreso_restante_sin_principal = max(promedio_mensual_ing - (monto_fuente_principal / max(int(meses_validos_ing), 1)), 0.0)
            resultado_sin_principal = ingreso_restante_sin_principal - gasto_habitual_mensual

            st.markdown("### 🛡️ Cobertura y escenario de riesgo")
            cr1, cr2, cr3, cr4 = st.columns(4)
            cr1.metric("🔁 Ingreso habitual mensual", f"${habitual_mensual:,.0f}")
            cr2.metric("🏠 Gasto habitual mensual", f"${gasto_habitual_mensual:,.0f}")
            cr3.metric("🛡️ Cobertura habitual", f"{cobertura_habitual:.1f}%")
            cr4.metric("⚠️ Sin fuente principal", f"${resultado_sin_principal:,.0f}", "Superávit" if resultado_sin_principal >= 0 else "Déficit mensual")
            if resultado_sin_principal < 0:
                st.error(f"🚨 Si desapareciera **{fuente_principal}**, el ingreso restante estimado produciría un déficit mensual de **${abs(resultado_sin_principal):,.0f}** frente al gasto habitual.")
            else:
                st.success(f"✅ Sin la fuente principal todavía existiría un margen estimado de **${resultado_sin_principal:,.0f}** sobre el gasto habitual.")

            # Calendario de entradas.
            st.markdown("### 🗓️ Calendario de ingresos")
            ingresos_calendario = ingresos_analisis.dropna(subset=["INGRESOS_FECHA"]).copy()
            if not ingresos_calendario.empty:
                ingresos_calendario["Fecha"] = pd.to_datetime(ingresos_calendario["INGRESOS_FECHA"], errors="coerce")
                ingresos_calendario["Día"] = ingresos_calendario["Fecha"].dt.day
                ingresos_calendario["Mes"] = ingresos_calendario["Fecha"].dt.strftime("%Y-%m")
                ingresos_calendario["Fuente"] = ingresos_calendario["INGRESOS_FUENTE"].fillna("Sin fuente").astype(str)
                ingresos_calendario["Tipo"] = ingresos_calendario["TIPO_INGRESO"].fillna("Sin clasificar").astype(str)
                ingresos_calendario["Etiqueta"] = ingresos_calendario.apply(
                    lambda r: f"{r['Fuente']} · ${r['INGRESOS_CANTIDAD']:,.0f}", axis=1
                )
                fig_cal_ing = px.scatter(
                    ingresos_calendario,
                    x="Día",
                    y="Mes",
                    size="INGRESOS_CANTIDAD",
                    color="Tipo",
                    text="Fuente",
                    color_discrete_map={
                        "Laborales": "#00F58A",
                        "No laborales": "#008CFF",
                        "Sin clasificar": "#B026FF",
                    },
                    size_max=42,
                )
                fig_cal_ing.update_traces(
                    customdata=ingresos_calendario[["Fecha", "Fuente", "Tipo", "INGRESOS_CANTIDAD"]],
                    hovertemplate=(
                        "<b>📅 %{customdata[0]|%d/%m/%Y}</b><br>"
                        "🏢 Consigna: %{customdata[1]}<br>"
                        "🏷️ Tipo: %{customdata[2]}<br>"
                        "💰 Valor: $%{customdata[3]:,.0f}<extra></extra>"
                    ),
                    textposition="top center",
                    marker=dict(line=dict(color="#F8FAFC", width=1.4), opacity=0.92),
                )
                fig_cal_ing.update_layout(legend_title_text="Tipo de ingreso", height=430)
                st.plotly_chart(estilo_grafico(fig_cal_ing, "Días de entrada del dinero y quién consigna"), use_container_width=True)

            # Próximo ingreso estimado por periodicidad mediana de la fuente principal.
            fechas_principal = ingresos_analisis.loc[
                (ingresos_analisis["INGRESOS_FUENTE"] == fuente_principal) & ingresos_analisis["INGRESOS_FECHA"].notna(),
                "INGRESOS_FECHA",
            ].sort_values().drop_duplicates()
            if len(fechas_principal) >= 2:
                intervalos = fechas_principal.diff().dropna().dt.days
                intervalo_estimado = int(intervalos.median()) if not intervalos.empty else 0
                if intervalo_estimado > 0:
                    proxima_fecha_ing = fechas_principal.iloc[-1] + pd.Timedelta(days=intervalo_estimado)
                    valor_estimado_ing = float(
                        ingresos_analisis.loc[ingresos_analisis["INGRESOS_FUENTE"] == fuente_principal, "INGRESOS_CANTIDAD"].median()
                    )
                    st.info(f"🔮 **Próximo ingreso estimado:** {fuente_principal}, alrededor del **{proxima_fecha_ing:%d/%m/%Y}**, por aproximadamente **${valor_estimado_ing:,.0f}**. Es una estimación basada en recurrencia histórica, no un ingreso confirmado.")

            # Calidad de datos.
            st.markdown("### 🧹 Calidad de los datos de ingresos")
            sin_fuente_ing = int(ingresos_analisis["INGRESOS_FUENTE"].astype(str).map(normalizar).isin(["", "SIN FUENTE", "NAN"]).sum())
            sin_tipo_ing = int(ingresos_analisis["INGRESOS_CATEGORIA"].astype(str).map(normalizar).isin(["", "SIN TIPO", "NAN"]).sum())
            sin_fecha_ing = int(ingresos_analisis["INGRESOS_FECHA"].isna().sum())
            valores_no_positivos_ing = int((ingresos_analisis["INGRESOS_CANTIDAD"] <= 0).sum())
            cols_dup_ing = [c for c in ["INGRESOS_FECHA", "INGRESOS_FUENTE", "INGRESOS_CANTIDAD", "INGRESOS_DESCRIPCION"] if c in ingresos_analisis.columns]
            dup_ing = ingresos_analisis.duplicated(subset=cols_dup_ing, keep=False) if cols_dup_ing else pd.Series(False, index=ingresos_analisis.index)
            qi1, qi2, qi3, qi4, qi5 = st.columns(5)
            qi1.metric("🏷️ Sin fuente", sin_fuente_ing)
            qi2.metric("🧾 Sin tipo", sin_tipo_ing)
            qi3.metric("📅 Sin fecha", sin_fecha_ing)
            qi4.metric("➖ Valores no positivos", valores_no_positivos_ing)
            qi5.metric("👯 Posibles duplicados", int(dup_ing.sum()))
            if dup_ing.any():
                with st.expander("🔍 Revisar posibles ingresos duplicados"):
                    st.dataframe(ingresos_analisis.loc[dup_ing].sort_values("INGRESOS_FECHA"), use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("### 📚 Visualizaciones existentes y detalle completo")
            col1, col2 = st.columns(2)
            with col1:
                fig_ing_mes = px.bar(
                    ingresos_mes, x="MES", y="INGRESOS_CANTIDAD", text_auto=",.0f",
                    color="INGRESOS_CANTIDAD", color_continuous_scale=["#0066FF", "#00B7FF", "#00FF88"]
                )
                fig_ing_mes.update_traces(hovertemplate="<b>📅 Mes: %{x}</b><br>💰 Ingresos recibidos: $%{y:,.0f}<br>📊 Participación visual dentro del periodo<extra></extra>")
                st.plotly_chart(estilo_grafico(fig_ing_mes, "Ingresos mensuales"), use_container_width=True)
            with col2:
                fig_ing_pie = px.pie(
                    ingresos_fuente, names="INGRESOS_FUENTE", values="INGRESOS_CANTIDAD",
                    hole=0.42, color_discrete_sequence=["#00FF88", "#00B7FF", "#B026FF", "#FFD600", "#FF1744", "#00E5FF", "#7C4DFF", "#76FF03"]
                )
                fig_ing_pie.update_traces(textinfo="percent+label", marker=dict(line=dict(color="#000000", width=2)), hovertemplate="<b>🏦 %{label}</b><br>💰 Valor: $%{value:,.0f}<br>📊 Participación: %{percent}<extra></extra>")
                st.plotly_chart(estilo_grafico(fig_ing_pie, "Participación por fuente de ingreso"), use_container_width=True)

            col3, col4 = st.columns(2)
            with col3:
                fig_fuente = px.bar(
                    ingresos_fuente, x="INGRESOS_CANTIDAD", y="INGRESOS_FUENTE", orientation="h",
                    color="INGRESOS_CANTIDAD", color_continuous_scale=["#0066FF", "#00B7FF", "#00FF88"], text_auto=",.0f"
                )
                fig_fuente.update_traces(marker_line_color="rgba(255,255,255,0.35)", marker_line_width=1, hovertemplate="<b>🏦 %{y}</b><br>💰 Ingreso acumulado: $%{x:,.0f}<br>📌 Posición dentro del ranking de fuentes<extra></extra>")
                fig_fuente.update_yaxes(autorange="reversed")
                st.plotly_chart(estilo_grafico(fig_fuente, "Ranking de fuentes de ingreso"), use_container_width=True)
            with col4:
                ingresos_tipo_mostrar = ingresos_tipo.copy().rename(columns={"TIPO_INGRESO": "Tipo de fuente"})
                fig_tipo_bar = px.bar(
                    ingresos_tipo_mostrar,
                    x="Tipo de fuente", y="INGRESOS_CANTIDAD",
                    color="Tipo de fuente", text_auto=",.0f",
                    color_discrete_map={"Laborales": "#00FF88", "No laborales": "#00B7FF", "Sin clasificar": "#B026FF"},
                )
                total_tipo_graf = float(ingresos_tipo_mostrar["INGRESOS_CANTIDAD"].sum()) or 1.0
                ingresos_tipo_mostrar["Participación"] = ingresos_tipo_mostrar["INGRESOS_CANTIDAD"] / total_tipo_graf * 100
                fig_tipo_bar.update_traces(
                    marker_line_color="rgba(255,255,255,0.65)", marker_line_width=1.4,
                    customdata=ingresos_tipo_mostrar[["Participación"]],
                    hovertemplate="<b>🧭 %{x}</b><br>💰 Valor: $%{y:,.0f}<br>📊 Participación: %{customdata[0]:.1f}%<extra></extra>",
                )
                fig_tipo_bar.update_layout(showlegend=False)
                st.plotly_chart(estilo_grafico(fig_tipo_bar, "Ingresos por tipo de fuente"), use_container_width=True)

            st.markdown("#### Mapa de ingresos: tipo de fuente → fuente")
            st.caption("Agrupa claramente las fuentes **laborales** y **no laborales**; dentro de cada bloque aparecen las fuentes específicas.")
            st.plotly_chart(
                fig_mapa_ingresos_tipo_fuente(ingresos_filtrados),
                use_container_width=True,
            )

            st.caption(
                "🟢 Verde = muy por debajo del promedio de esa fuente · "
                "🔴 Rojo = muy por encima del promedio. El promedio de cada fuente se usa como su meta de referencia."
            )
            # El mapa se construye con el mes calculado desde la fecha real.
            # Se normalizan espacios y mayúsculas para impedir que el ordenamiento
            # elimine todas las columnas aun cuando sí existan ingresos.
            ingresos_heatmap = ingresos_filtrados.copy()
            ingresos_heatmap["INGRESOS_FECHA"] = pd.to_datetime(
                ingresos_heatmap["INGRESOS_FECHA"], errors="coerce", dayfirst=True
            )
            mes_desde_fecha_heatmap = ingresos_heatmap["INGRESOS_FECHA"].dt.month.map(
                {1:"ENERO", 2:"FEBRERO", 3:"MARZO", 4:"ABRIL", 5:"MAYO", 6:"JUNIO",
                 7:"JULIO", 8:"AGOSTO", 9:"SEPTIEMBRE", 10:"OCTUBRE", 11:"NOVIEMBRE", 12:"DICIEMBRE"}
            )
            ingresos_heatmap["MES_HEATMAP"] = mes_desde_fecha_heatmap.fillna(
                ingresos_heatmap["MES"].astype("string").str.strip().str.upper()
            )
            ingresos_heatmap["INGRESOS_FUENTE"] = (
                ingresos_heatmap["INGRESOS_FUENTE"].astype("string").str.strip().fillna("Sin fuente")
            )

            tabla_ing = pd.pivot_table(
                ingresos_heatmap,
                values="INGRESOS_CANTIDAD",
                index="INGRESOS_FUENTE",
                columns="MES_HEATMAP",
                aggfunc="sum",
                fill_value=0,
            )
            tabla_ing_trans = pd.pivot_table(
                ingresos_heatmap,
                values="INGRESOS_CANTIDAD",
                index="INGRESOS_FUENTE",
                columns="MES_HEATMAP",
                aggfunc="count",
                fill_value=0,
            )

            meses_heatmap = [mes for mes in MESES_ORDEN if mes in tabla_ing.columns]
            meses_extra = [mes for mes in tabla_ing.columns if mes not in meses_heatmap]
            columnas_heatmap = meses_heatmap + meses_extra

            if columnas_heatmap:
                tabla_ing = tabla_ing[columnas_heatmap]
                tabla_ing_trans = tabla_ing_trans.reindex(
                    index=tabla_ing.index,
                    columns=columnas_heatmap,
                    fill_value=0,
                )
                promedio_por_fuente = (
                    tabla_ing.replace(0, pd.NA).mean(axis=1, skipna=True).fillna(0)
                )
                fig_heat_ing = crear_heatmap_presupuesto(
                    tabla_ing,
                    lambda fuente: float(promedio_por_fuente.get(fuente, 0)),
                    etiqueta_fila="Fuente",
                    tabla_transacciones=tabla_ing_trans,
                    colorscale=COLORSCALE_NEON_CALOR,
                    colorbar_title="Desviación vs. promedio",
                    etiqueta_valor="Ingreso",
                    etiqueta_meta="Promedio de la fuente",
                )
                st.plotly_chart(fig_heat_ing, use_container_width=True)
            else:
                st.info("No existen meses válidos para construir el mapa de ingresos en este periodo.")

            st.markdown("#### Tabla de ingresos cargados")
            st.dataframe(ingresos_filtrados.sort_values(["ANIO", "MES", "INGRESOS_FUENTE"]), use_container_width=True, hide_index=True)

    if pestana_activa == etiquetas_pestanas[5]:
        contexto_pestana("¿Qué obligaciones tengo?", "Resume saldos pendientes, intereses, avance de pago y orden recomendado para atender las deudas.")
        st.markdown("## Obligaciones y estrategia de pago")
        st.subheader("💳 Deudas")
        st.caption(
            "Prioridad de pago por método avalancha: primero la tasa de interés más alta. "
            "Cuando dos deudas tienen el mismo interés, se muestra primero la de mayor saldo pendiente."
        )

        if deudas.empty:
            st.info(
                "No se encontraron registros válidos en la hoja **Deudas**. "
                "Usa las columnas: nombre, deuda, interés mensual, saldo, avance e inicio del crédito."
            )
        else:
            total_deuda_inicial = float(deudas["Deuda inicial"].sum())
            total_saldo_deudas = float(deudas["Saldo"].sum())
            total_pagado_deudas = float(deudas["Pagado"].sum())
            avance_total_deudas = (
                total_pagado_deudas / total_deuda_inicial * 100
                if total_deuda_inicial > 0
                else 0.0
            )
            interes_promedio_ponderado = (
                (
                    deudas["Interés"] * deudas["Saldo"]
                ).sum() / total_saldo_deudas * 100
                if total_saldo_deudas > 0
                else 0.0
            )

            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Deuda inicial total", f"${total_deuda_inicial:,.0f}")
            d2.metric("Saldo pendiente", f"${total_saldo_deudas:,.0f}")
            d3.metric("Total pagado", f"${total_pagado_deudas:,.0f}")
            d4.metric(
                "Avance total",
                f"{avance_total_deudas:.1f}%",
                f"Interés ponderado: {interes_promedio_ponderado:.2f}%",
            )

            st.progress(min(max(avance_total_deudas, 0), 100) / 100)

            # ============================================================
            # ANÁLISIS EJECUTIVO DE DEUDAS V9.17
            # ============================================================
            deudas_analisis = deudas.copy()

            # La hoja utiliza tasas como 0.01 = 1% mensual.
            # Si accidentalmente se registra 1 en vez de 0.01, se interpreta como 1%.
            deudas_analisis["Tasa mensual"] = pd.to_numeric(
                deudas_analisis["Interés"], errors="coerce"
            ).fillna(0.0)
            deudas_analisis.loc[
                deudas_analisis["Tasa mensual"].gt(1),
                "Tasa mensual",
            ] = deudas_analisis.loc[
                deudas_analisis["Tasa mensual"].gt(1),
                "Tasa mensual",
            ] / 100.0

            deudas_analisis["Interés %"] = deudas_analisis["Tasa mensual"] * 100
            deudas_analisis["Tasa efectiva anual %"] = (
                (1 + deudas_analisis["Tasa mensual"]).pow(12) - 1
            ) * 100

            fecha_analisis_deudas = pd.Timestamp(fecha_hasta).normalize()
            deudas_analisis["Inicio del crédito"] = pd.to_datetime(
                deudas_analisis.get("Inicio del crédito"),
                errors="coerce",
                dayfirst=True,
            )
            deudas_analisis["Días transcurridos"] = (
                fecha_analisis_deudas - deudas_analisis["Inicio del crédito"]
            ).dt.days.clip(lower=0)
            deudas_analisis["Meses transcurridos"] = (
                deudas_analisis["Días transcurridos"] / 30.4375
            ).fillna(0.0)
            deudas_analisis["Saldo promedio estimado"] = (
                deudas_analisis["Deuda inicial"] + deudas_analisis["Saldo"]
            ) / 2
            deudas_analisis["Interés acumulado estimado"] = (
                deudas_analisis["Saldo promedio estimado"]
                * deudas_analisis["Tasa mensual"]
                * deudas_analisis["Meses transcurridos"]
            )
            deudas_analisis.loc[
                deudas_analisis["Inicio del crédito"].isna(),
                "Interés acumulado estimado",
            ] = 0.0
            deudas_analisis["Pago económico estimado"] = (
                deudas_analisis["Pagado"]
                + deudas_analisis["Interés acumulado estimado"]
            )
            deudas_analisis["Participación saldo %"] = (
                deudas_analisis["Saldo"] / total_saldo_deudas * 100 if total_saldo_deudas else 0.0
            )
            deudas_analisis["Costo mensual estimado"] = (
                deudas_analisis["Saldo"] * deudas_analisis["Tasa mensual"]
            )
            deudas_analisis["Costo anual estimado"] = (
                deudas_analisis["Costo mensual estimado"] * 12
            )
            deudas_analisis["Prioridad"] = range(1, len(deudas_analisis) + 1)
            deudas_analisis["Estado"] = deudas_analisis.apply(
                lambda r: "Pagada" if r["Saldo"] <= 0 or r["Avance"] >= 100
                else "Cerca de terminar" if r["Avance"] >= 75
                else "En progreso" if r["Avance"] >= 40
                else "Saldo alto",
                axis=1,
            )

            interes_total_estimado = float(
                deudas_analisis["Interés acumulado estimado"].sum()
            )
            creditos_con_fecha = int(
                deudas_analisis["Inicio del crédito"].notna().sum()
            )
            antiguedad_promedio_meses = float(
                deudas_analisis.loc[
                    deudas_analisis["Inicio del crédito"].notna(),
                    "Meses transcurridos",
                ].mean()
            ) if creditos_con_fecha else 0.0

            st.markdown("### 🗓️ Antigüedad y costo acumulado estimado")
            ai1, ai2, ai3, ai4 = st.columns(4)
            ai1.metric("📅 Créditos con fecha", creditos_con_fecha)
            ai2.metric("⏳ Antigüedad promedio", f"{antiguedad_promedio_meses:.1f} meses")
            ai3.metric("🔥 Interés acumulado estimado", f"${interes_total_estimado:,.0f}")
            ai4.metric(
                "💸 Principal + interés estimado",
                f"${total_pagado_deudas + interes_total_estimado:,.0f}",
            )
            st.info(
                "ℹ️ **Estimación:** la hoja no contiene el historial de cuotas ni los "
                "intereses efectivamente cobrados. El cálculo usa la tasa mensual, el "
                "tiempo desde el inicio del crédito y el saldo promedio entre el valor "
                "inicial y el saldo actual."
            )

            # ============================================================
            # CONTINÚA EL ANÁLISIS EJECUTIVO
            # ============================================================

            deuda_prioritaria = deudas_analisis.iloc[0]
            st.markdown("### 🎯 Deuda prioritaria y razón")
            st.error(
                f"🚨 **Prioridad 1: {deuda_prioritaria['Nombre']}** · "
                f"tasa **{deuda_prioritaria['Interés %']:.2f}%**, saldo **${deuda_prioritaria['Saldo']:,.0f}**. "
                "Se ubica primero por el método avalancha: mayor interés y, en empate, mayor saldo."
            )

            st.markdown("### 📊 Ranking por saldo, costo financiero e interés acumulado")
            rk1, rk2 = st.columns(2)
            with rk1:
                saldo_rank = deudas_analisis.sort_values("Saldo", ascending=True)
                fig_saldo_rank = px.bar(
                    saldo_rank, x="Saldo", y="Nombre", orientation="h", text="Saldo",
                    color="Saldo", color_continuous_scale=["#38BDF8", "#7B2FFF", "#FF1744"],
                )
                fig_saldo_rank.update_traces(
                    texttemplate="$%{text:,.0f}", textposition="outside",
                    customdata=saldo_rank[["Deuda inicial", "Pagado", "Avance", "Participación saldo %", "Inicio del crédito", "Interés acumulado estimado", "Interés %"]],
                    hovertemplate=(
                        "<b>💳 Obligación: %{y}</b><br>"
                        "🔴 Saldo pendiente: $%{x:,.0f}<br>"
                        "💰 Deuda inicial: $%{customdata[0]:,.0f}<br>"
                        "✅ Capital amortizado: $%{customdata[1]:,.0f}<br>"
                        "📊 Avance del capital: %{customdata[2]:.1f}%<br>"
                        "🧩 Participación del saldo: %{customdata[3]:.1f}%<br>"
                        "📅 Inicio del crédito: %{customdata[4]|%d/%m/%Y}<br>"
                        "🔥 Interés acumulado estimado: $%{customdata[5]:,.0f}<br>"
                        "📈 Tasa mensual: %{customdata[6]:.2f}%"
                        "<extra></extra>"
                    ),
                )
                fig_saldo_rank.update_yaxes(title="", automargin=True)
                st.plotly_chart(estilo_grafico(fig_saldo_rank, "💰 Mayor saldo pendiente"), use_container_width=True)
            with rk2:
                costo_rank = deudas_analisis.sort_values("Interés acumulado estimado", ascending=True)
                fig_costo_rank = px.bar(
                    costo_rank, x="Interés acumulado estimado", y="Nombre", orientation="h", text="Interés acumulado estimado",
                    color="Interés %", color_continuous_scale=["#FFD600", "#FF7A00", "#FF003C"],
                )
                fig_costo_rank.update_traces(
                    texttemplate="$%{text:,.0f}", textposition="outside",
                    customdata=costo_rank[["Saldo", "Interés %", "Costo mensual estimado", "Inicio del crédito", "Meses transcurridos", "Tasa efectiva anual %"]],
                    hovertemplate=(
                        "<b>🔥 Obligación: %{y}</b><br>"
                        "💸 Interés acumulado estimado: $%{x:,.0f}<br>"
                        "🔴 Saldo actual: $%{customdata[0]:,.0f}<br>"
                        "📈 Tasa mensual: %{customdata[1]:.2f}%<br>"
                        "🧾 Interés del mes sobre saldo actual: $%{customdata[2]:,.0f}<br>"
                        "📅 Inicio del crédito: %{customdata[3]|%d/%m/%Y}<br>"
                        "⏳ Tiempo transcurrido: %{customdata[4]:.1f} meses<br>"
                        "📊 Tasa efectiva anual aprox.: %{customdata[5]:.2f}%"
                        "<extra></extra>"
                    ),
                )
                fig_costo_rank.update_yaxes(title="", automargin=True)
                st.plotly_chart(estilo_grafico(fig_costo_rank, "🔥 Interés acumulado estimado desde el inicio"), use_container_width=True)

            st.markdown("### 🧩 Concentración del saldo total")
            fig_conc_deuda = px.pie(
                deudas_analisis, names="Nombre", values="Saldo", hole=0.50,
                color_discrete_sequence=PALETA_NEON,
            )
            fig_conc_deuda.update_traces(
                textinfo="percent+label",
                customdata=deudas_analisis[["Saldo", "Interés %", "Avance", "Inicio del crédito", "Interés acumulado estimado"]],
                hovertemplate=(
                    "<b>💳 Obligación: %{label}</b><br>"
                    "🔴 Saldo pendiente: $%{customdata[0]:,.0f}<br>"
                    "📈 Tasa mensual: %{customdata[1]:.2f}%<br>"
                    "✅ Avance del capital: %{customdata[2]:.1f}%<br>"
                    "📅 Inicio: %{customdata[3]|%d/%m/%Y}<br>"
                    "🔥 Interés acumulado estimado: $%{customdata[4]:,.0f}<br>"
                    "🧩 Participación del saldo total: %{percent}"
                    "<extra></extra>"
                ),
            )
            st.plotly_chart(estilo_grafico(fig_conc_deuda, "Participación de cada obligación en el saldo total"), use_container_width=True)

            st.markdown("### 🛡️ Capacidad de pago")
            texto_deuda_periodo = (
                df.get("GASTOS_CATEGORIA", pd.Series(dtype=str)).astype(str).map(normalizar) + " " +
                df.get("GASTOS_SUBCATEGORIA", pd.Series(dtype=str)).astype(str).map(normalizar) + " " +
                df.get("GASTOS_SUBCATEGORIA_2", pd.Series(dtype=str)).astype(str).map(normalizar) + " " +
                df.get("GASTOS_DESCRIPCION", pd.Series(dtype=str)).astype(str).map(normalizar)
            ) if not df.empty else pd.Series(dtype=str)
            claves_deuda_periodo = ("DEUDA", "CREDITO", "PRESTAMO", "CUOTA", "HIPOTECA", "TARJETA", "LIBRANZA")
            mask_deuda_periodo = texto_deuda_periodo.str.contains("|".join(claves_deuda_periodo), regex=True, na=False)
            pagos_deuda_periodo = float(df.loc[mask_deuda_periodo, "GASTOS_CANTIDAD"].sum()) if not df.empty else 0.0
            meses_deuda_ref = max(len(flujo_reporte[flujo_reporte["Ingresos"].gt(0)]) if not flujo_reporte.empty else 1, 1)
            pago_mensual_estimado = pagos_deuda_periodo / meses_deuda_ref
            meses_ingreso_deuda = flujo_reporte.loc[flujo_reporte["Ingresos"].gt(0), "Ingresos"] if not flujo_reporte.empty else pd.Series(dtype=float)
            ingreso_habitual_ref = float(meses_ingreso_deuda.mean()) if not meses_ingreso_deuda.empty else 0.0
            compromiso_deuda_pct = pago_mensual_estimado / ingreso_habitual_ref * 100 if ingreso_habitual_ref else 0.0
            margen_despues_deuda = ingreso_habitual_ref - pago_mensual_estimado
            cp1, cp2, cp3, cp4 = st.columns(4)
            cp1.metric("💳 Pago mensual detectado", f"${pago_mensual_estimado:,.0f}")
            cp2.metric("💵 Ingreso mensual promedio", f"${ingreso_habitual_ref:,.0f}")
            cp3.metric("📊 Compromiso de ingresos", f"{compromiso_deuda_pct:.1f}%")
            cp4.metric("🛡️ Margen después de deuda", f"${margen_despues_deuda:,.0f}")
            if compromiso_deuda_pct > 30:
                st.error("🚨 Más del 30% del ingreso mensual estimado está comprometido en pagos detectados de deuda.")
            elif compromiso_deuda_pct > 20:
                st.warning("⚠️ El compromiso mensual de deuda se encuentra en una zona de atención.")
            else:
                st.success("✅ El compromiso mensual estimado de deuda permanece en una zona controlada.")

            st.markdown("### 🧮 Simulador aproximado de pago adicional")
            st.caption("La hoja no contiene cuota ni plazo. Por eso esta simulación usa saldo, tasa y un pago adicional mensual; es orientativa, no contractual.")
            max_extra = max(int(total_saldo_deudas * 0.10), 100000)
            pago_adicional = st.slider(
                "💸 Pago adicional mensual", min_value=0, max_value=max_extra, value=min(300000, max_extra), step=50000,
                key="simulador_pago_adicional_deudas_v917",
            )
            saldo_prioritario = float(deuda_prioritaria["Saldo"])
            interes_mensual_prioritario = float(deuda_prioritaria["Tasa mensual"])
            pago_base_simulado = max(pago_mensual_estimado, saldo_prioritario * 0.02)
            pago_total_simulado = pago_base_simulado + pago_adicional
            if pago_total_simulado > saldo_prioritario * interes_mensual_prioritario and saldo_prioritario > 0:
                import math
                if interes_mensual_prioritario > 0:
                    meses_sin_extra = math.ceil(-math.log(1 - interes_mensual_prioritario * saldo_prioritario / pago_base_simulado) / math.log(1 + interes_mensual_prioritario)) if pago_base_simulado > interes_mensual_prioritario * saldo_prioritario else 0
                    meses_con_extra = math.ceil(-math.log(1 - interes_mensual_prioritario * saldo_prioritario / pago_total_simulado) / math.log(1 + interes_mensual_prioritario))
                else:
                    meses_sin_extra = math.ceil(saldo_prioritario / pago_base_simulado)
                    meses_con_extra = math.ceil(saldo_prioritario / pago_total_simulado)
                meses_ahorrados = max(meses_sin_extra - meses_con_extra, 0)
                sm1, sm2, sm3 = st.columns(3)
                sm1.metric("⏳ Meses estimados sin extra", meses_sin_extra)
                sm2.metric("⚡ Meses estimados con extra", meses_con_extra)
                sm3.metric("🎉 Meses potencialmente ahorrados", meses_ahorrados)
            else:
                st.warning("⚠️ El pago estimado no supera los intereses mensuales de la deuda prioritaria; no es posible proyectar una reducción confiable.")

            st.markdown("### ⚖️ Avalancha frente a bola de nieve")
            avalancha = deudas_analisis.sort_values(["Interés", "Saldo"], ascending=[False, False]).copy()
            nieve = deudas_analisis.sort_values(["Saldo", "Interés"], ascending=[True, False]).copy()
            comp_metodos = pd.DataFrame({
                "Posición": range(1, len(deudas_analisis) + 1),
                "Avalancha": avalancha["Nombre"].tolist(),
                "Bola de nieve": nieve["Nombre"].tolist(),
            })
            st.dataframe(comp_metodos, use_container_width=True, hide_index=True)
            st.info("ℹ️ Avalancha minimiza costo financiero; bola de nieve prioriza victorias rápidas. La mejor elección depende de disciplina, liquidez y condiciones reales de cada crédito.")

            st.markdown("### 🧹 Alertas de calidad de datos")
            sin_tasa = int((deudas_analisis["Interés"] <= 0).sum())
            saldo_mayor_inicial = int((deudas_analisis["Saldo"] > deudas_analisis["Deuda inicial"]).sum())
            avance_inconsistente = int(((deudas_analisis["Avance"] < 0) | (deudas_analisis["Avance"] > 100)).sum())
            nombres_duplicados = int(deudas_analisis["Nombre"].astype(str).str.strip().duplicated(keep=False).sum())
            qd1, qd2, qd3, qd4 = st.columns(4)
            qd1.metric("📉 Sin tasa", sin_tasa)
            qd2.metric("⚠️ Saldo > inicial", saldo_mayor_inicial)
            qd3.metric("📊 Avance inconsistente", avance_inconsistente)
            qd4.metric("👯 Nombres duplicados", nombres_duplicados)

            st.markdown("### Prioridad de pago")
            st.caption(
                "La primera deuda es la más costosa por interés. "
                "El color se intensifica con la tasa."
            )

            deudas_grafico = deudas.copy()
            deudas_grafico["Interés %"] = deudas_grafico["Interés"] * 100
            deudas_grafico["Etiqueta"] = deudas_grafico.apply(
                lambda fila: (
                    f"${fila['Saldo']:,.0f}<br>"
                    f"{fila['Interés %']:.2f}%"
                ),
                axis=1,
            )

            fig_deudas = go.Figure(
                go.Bar(
                    x=deudas_grafico["Saldo"],
                    y=deudas_grafico["Nombre"],
                    orientation="h",
                    text=deudas_grafico["Etiqueta"],
                    textposition="outside",
                    cliponaxis=False,
                    marker=dict(
                        color=deudas_grafico["Interés %"],
                        colorscale=[
                            [0.0, "#38BDF8"],
                            [0.5, "#F59E0B"],
                            [1.0, "#FF003C"],
                        ],
                        showscale=True,
                        colorbar=dict(title="Interés %"),
                        line=dict(color="#E2E8F0", width=1),
                    ),
                    customdata=deudas_grafico[
                        ["Deuda inicial", "Interés %", "Pagado", "Avance"]
                    ],
                    hovertemplate=(
                        "<b>💳 %{y}</b><br>"
                        "🔴 Saldo pendiente: $%{x:,.0f}<br>"
                        "💰 Deuda inicial: $%{customdata[0]:,.0f}<br>"
                        "📈 📈 Interés: %{customdata[1]:.2f}%<br>"
                        "✅ ✅ Pagado: $%{customdata[2]:,.0f}<br>"
                        "📊 📊 Avance: %{customdata[3]:.1f}%"
                        "<extra></extra>"
                    ),
                )
            )

            fig_deudas.update_layout(
                template="plotly_dark",
                height=max(430, len(deudas_grafico) * 62),
                paper_bgcolor="#000000",
                plot_bgcolor="#000000",
                title="Deudas ordenadas por costo financiero",
                xaxis=dict(
                    title="Saldo pendiente",
                    tickprefix="$",
                    tickformat=",.0f",
                    gridcolor="rgba(148,163,184,0.14)",
                ),
                yaxis=dict(
                    title="Deuda",
                    autorange="reversed",
                ),
                margin=dict(t=75, b=45, l=40, r=150),
                showlegend=False,
            )

            st.plotly_chart(
                fig_deudas,
                use_container_width=True,
                key="grafico_prioridad_deudas_v1",
            )

            st.markdown("### Avance de cada deuda")

            for posicion, (_, deuda_row) in enumerate(
                deudas.iterrows(),
                start=1,
            ):
                nombre_deuda = str(deuda_row["Nombre"])
                deuda_inicial = float(deuda_row["Deuda inicial"])
                saldo_deuda = float(deuda_row["Saldo"])
                pagado_deuda = float(deuda_row["Pagado"])
                interes_deuda_pct = float(deuda_row["Interés"]) * 100
                avance_deuda = float(deuda_row["Avance"])
                avance_deuda_limitado = min(max(avance_deuda, 0), 100)
                faltante_deuda = max(saldo_deuda, 0)

                if avance_deuda >= 100 or saldo_deuda <= 0:
                    estado_deuda = "Pagada"
                    color_estado = "#34D399"
                elif avance_deuda >= 75:
                    estado_deuda = "Cerca de terminar"
                    color_estado = "#38BDF8"
                elif avance_deuda >= 40:
                    estado_deuda = "En progreso"
                    color_estado = "#FBBF24"
                else:
                    estado_deuda = "Saldo alto"
                    color_estado = "#FB7185"

                st.markdown(
                    f"""
                    <div style="
                        background:linear-gradient(135deg,rgba(15,23,42,.98),rgba(2,6,23,.98));
                        border:1px solid {color_estado};
                        border-radius:18px;
                        padding:18px;
                        margin-top:14px;
                        box-shadow:0 10px 28px rgba(0,0,0,.35);
                    ">
                        <div style="display:flex;justify-content:space-between;align-items:center;gap:15px;">
                            <div>
                                <div style="color:#94a3b8;font-size:.82rem;font-weight:700;">
                                    PRIORIDAD {posicion}
                                </div>
                                <div style="color:#f8fafc;font-size:1.25rem;font-weight:800;">
                                    💳 {nombre_deuda}
                                </div>
                            </div>
                            <div style="
                                color:{color_estado};
                                border:1px solid {color_estado};
                                border-radius:999px;
                                padding:6px 12px;
                                font-weight:800;
                            ">
                                {estado_deuda}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
                c1.metric("Interés", f"{interes_deuda_pct:.2f}%")
                c2.metric("Deuda inicial", f"${deuda_inicial:,.0f}")
                c3.metric("Pagado", f"${pagado_deuda:,.0f}")
                c4.metric("Saldo pendiente", f"${saldo_deuda:,.0f}")
                c5.metric("Falta para terminar", f"${faltante_deuda:,.0f}")
                inicio_credito = pd.to_datetime(
                    deuda_row.get("Inicio del crédito"), errors="coerce"
                )
                meses_credito = (
                    max((pd.Timestamp(fecha_hasta) - inicio_credito).days, 0) / 30.4375
                    if pd.notna(inicio_credito)
                    else 0.0
                )
                tasa_mensual_deuda = float(deuda_row["Interés"])
                if tasa_mensual_deuda > 1:
                    tasa_mensual_deuda = tasa_mensual_deuda / 100.0
                interes_acumulado_deuda = (
                    ((deuda_inicial + saldo_deuda) / 2)
                    * tasa_mensual_deuda
                    * meses_credito
                    if pd.notna(inicio_credito)
                    else 0.0
                )
                c6.metric(
                    "Inicio",
                    inicio_credito.strftime("%d/%m/%Y")
                    if pd.notna(inicio_credito)
                    else "Sin registrar",
                )
                c7.metric(
                    "Interés estimado",
                    f"${interes_acumulado_deuda:,.0f}",
                    f"{meses_credito:.1f} meses",
                )

                st.progress(avance_deuda_limitado / 100)

                st.markdown(
                    f"""
                    <div style="color:#cbd5e1;margin:4px 0 12px 0;">
                        📊 Avance: <b style="color:{color_estado};">{avance_deuda:.1f}%</b>
                        · Falta pagar <b>${faltante_deuda:,.0f}</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                fig_avance_deuda = go.Figure()

                fig_avance_deuda.add_trace(
                    go.Bar(
                        x=[pagado_deuda],
                        y=[nombre_deuda],
                        orientation="h",
                        name="Pagado",
                        marker_color="#34D399",
                        text=[f"Pagado ${pagado_deuda:,.0f}"],
                        textposition="inside",
                        hovertemplate="<b>✅ Capital amortizado</b><br>💳 %{y}<br>💰 Valor: $%{x:,.0f}<extra></extra>",
                    )
                )

                fig_avance_deuda.add_trace(
                    go.Bar(
                        x=[faltante_deuda],
                        y=[nombre_deuda],
                        orientation="h",
                        name="Pendiente",
                        marker_color="#FB7185",
                        text=[f"Pendiente ${faltante_deuda:,.0f}"],
                        textposition="inside",
                        hovertemplate="<b>🔴 Saldo pendiente</b><br>💳 %{y}<br>💰 Valor: $%{x:,.0f}<extra></extra>",
                    )
                )

                fig_avance_deuda.update_layout(
                    barmode="stack",
                    template="plotly_dark",
                    height=190,
                    paper_bgcolor="#000000",
                    plot_bgcolor="#000000",
                    xaxis=dict(
                        title="Valor de la deuda",
                        tickprefix="$",
                        tickformat=",.0f",
                        range=[0, max(deuda_inicial, 1)],
                    ),
                    yaxis=dict(title=""),
                    legend=dict(
                        orientation="h",
                        y=1.18,
                        x=0,
                    ),
                    margin=dict(t=55, b=35, l=20, r=20),
                )

                st.plotly_chart(
                    fig_avance_deuda,
                    use_container_width=True,
                    key=f"avance_deuda_{posicion}",
                )

                st.divider()

            tabla_deudas = deudas.copy()
            tabla_deudas["Interés"] = tabla_deudas["Interés"].map(
                lambda valor: f"{valor * 100:.2f}%"
            )
            tabla_deudas["Deuda inicial"] = tabla_deudas["Deuda inicial"].map(
                lambda valor: f"${valor:,.0f}"
            )
            tabla_deudas["Saldo"] = tabla_deudas["Saldo"].map(
                lambda valor: f"${valor:,.0f}"
            )
            tabla_deudas["Pagado"] = tabla_deudas["Pagado"].map(
                lambda valor: f"${valor:,.0f}"
            )
            tabla_deudas["Avance"] = tabla_deudas["Avance"].map(
                lambda valor: f"{valor:.1f}%"
            )
            tabla_deudas["Inicio del crédito"] = pd.to_datetime(
                tabla_deudas["Inicio del crédito"], errors="coerce"
            ).dt.strftime("%d/%m/%Y").fillna("Sin registrar")
            tabla_deudas = tabla_deudas.merge(
                deudas_analisis[[
                    "Nombre",
                    "Meses transcurridos",
                    "Interés acumulado estimado",
                    "Tasa efectiva anual %",
                ]],
                on="Nombre",
                how="left",
            )
            tabla_deudas["Meses transcurridos"] = tabla_deudas[
                "Meses transcurridos"
            ].map(lambda valor: f"{valor:.1f}")
            tabla_deudas["Interés acumulado estimado"] = tabla_deudas[
                "Interés acumulado estimado"
            ].map(lambda valor: f"${valor:,.0f}")
            tabla_deudas["Tasa efectiva anual %"] = tabla_deudas[
                "Tasa efectiva anual %"
            ].map(lambda valor: f"{valor:.2f}%")

            with st.expander("Ver tabla completa de deudas"):
                st.dataframe(
                    tabla_deudas[
                        [
                            "Nombre",
                            "Interés",
                            "Deuda inicial",
                            "Pagado",
                            "Saldo",
                            "Avance",
                            "Inicio del crédito",
                            "Meses transcurridos",
                            "Interés acumulado estimado",
                            "Tasa efectiva anual %",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            csv_deudas = deudas.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar deudas procesadas (CSV)",
                csv_deudas,
                "deudas_procesadas.csv",
                "text/csv",
            )

    if pestana_activa == etiquetas_pestanas[6]:
        contexto_pestana("¿Cuál es mi riqueza?", "Integra activos, pasivos y patrimonio neto para mostrar la posición financiera acumulada y su evolución.")
        st.markdown("## Composición del patrimonio")
        st.subheader("🏠 Patrimonio Neto")
        st.caption(
            "Lee automáticamente una hoja llamada Patrimonio. Cada fila puede ser un activo o un pasivo. "
            "El valor neto se calcula si la columna viene vacía."
        )

        plantilla_patrimonio = pd.DataFrame(columns=[
            "Fecha", "Tipo", "Categoría", "Subcategoría", "Descripción", "Entidad",
            "Valor actual", "Saldo pendiente", "Valor neto", "Fecha compra",
            "Fecha valoración", "Estado", "Observaciones", "Liquidez",
        ])

        if patrimonio.empty:
            st.warning("No encontré datos en una hoja llamada 'Patrimonio'. Crea esa hoja en el Excel con estas columnas y vuelve a subir el archivo.")
            st.dataframe(plantilla_patrimonio, use_container_width=True, hide_index=True)
            st.markdown("#### Ejemplo de cómo llenar la hoja")
            ejemplo_patrimonio = pd.DataFrame([
                {
                    "Fecha": "06/07/2026", "Tipo": "Activo", "Categoría": "Vivienda",
                    "Subcategoría": "Casa", "Descripción": "Casa principal", "Entidad": "Propia / Banco",
                    "Valor actual": 420000000, "Saldo pendiente": 165000000, "Valor neto": 255000000,
                    "Fecha compra": "18/09/2020", "Fecha valoración": "06/07/2026",
                    "Estado": "Activo", "Observaciones": "Avalúo comercial 2026", "Liquidez": "Baja",
                },
                {
                    "Fecha": "06/07/2026", "Tipo": "Activo", "Categoría": "Bancos",
                    "Subcategoría": "Cuenta de ahorros", "Descripción": "Cuenta principal", "Entidad": "Bancolombia",
                    "Valor actual": 8500000, "Saldo pendiente": 0, "Valor neto": 8500000,
                    "Fecha compra": "10/01/2018", "Fecha valoración": "06/07/2026",
                    "Estado": "Activo", "Observaciones": "Saldo actualizado", "Liquidez": "Alta",
                },
                {
                    "Fecha": "06/07/2026", "Tipo": "Pasivo", "Categoría": "Tarjeta de crédito",
                    "Subcategoría": "Visa", "Descripción": "Tarjeta principal", "Entidad": "BBVA",
                    "Valor actual": 0, "Saldo pendiente": 3250000, "Valor neto": -3250000,
                    "Fecha compra": "12/02/2020", "Fecha valoración": "06/07/2026",
                    "Estado": "Activa", "Observaciones": "Corte mensual", "Liquidez": "No aplica",
                },
            ])
            st.dataframe(ejemplo_patrimonio, use_container_width=True, hide_index=True)
        else:
            total_activos = float(patrimonio.loc[patrimonio["Tipo"].map(normalizar).eq("ACTIVO"), "Valor neto"].sum())
            total_pasivos = abs(float(patrimonio.loc[~patrimonio["Tipo"].map(normalizar).eq("ACTIVO"), "Valor neto"].sum()))
            patrimonio_neto = float(patrimonio["Valor neto"].sum())
            deuda_activos_pct = (total_pasivos / total_activos * 100) if total_activos else 0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total activos", f"${total_activos:,.0f}")
            m2.metric("Total pasivos", f"${total_pasivos:,.0f}")
            m3.metric("Patrimonio neto", f"${patrimonio_neto:,.0f}")
            m4.metric("Endeudamiento", f"{deuda_activos_pct:.1f}%")

            # ======================================================
            # ANÁLISIS EJECUTIVO DE PATRIMONIO V9.17
            # ======================================================
            patrimonio_v917 = patrimonio.copy()
            for col in ["Valor actual", "Saldo pendiente", "Valor neto"]:
                if col in patrimonio_v917.columns:
                    patrimonio_v917[col] = pd.to_numeric(patrimonio_v917[col], errors="coerce").fillna(0.0)

            # Nombre legible: nunca se toman fechas como etiquetas del eje.
            columnas_nombre_pat = [c for c in ["Descripción", "Subcategoría", "Categoría", "Entidad"] if c in patrimonio_v917.columns]
            if columnas_nombre_pat:
                patrimonio_v917["Elemento"] = patrimonio_v917[columnas_nombre_pat].astype(str).apply(
                    lambda fila: next((v.strip() for v in fila if v and v.strip().lower() not in {"nan", "none", "nat", ""}), "Sin nombre"),
                    axis=1,
                )
            else:
                patrimonio_v917["Elemento"] = "Sin nombre"

            tipo_norm_pat = patrimonio_v917.get("Tipo", pd.Series("", index=patrimonio_v917.index)).map(normalizar)
            patrimonio_v917["Clase"] = tipo_norm_pat.map(lambda x: "Activo" if x == "ACTIVO" else "Pasivo")
            patrimonio_v917["Valor visual"] = patrimonio_v917["Valor neto"].abs()

            # 💧 Liquidez: se respeta la clasificación explícita de la hoja.
            liquidez_norm = patrimonio_v917.get("Liquidez", pd.Series("SIN CLASIFICAR", index=patrimonio_v917.index)).map(normalizar)
            patrimonio_v917["Nivel liquidez"] = liquidez_norm.map(
                lambda x: "Alta" if any(k in x for k in ["ALTA", "LIQUID", "INMEDIATA"])
                else "Media" if "MEDIA" in x
                else "Baja" if "BAJA" in x
                else "No aplica" if "NO APLICA" in x
                else "Sin clasificar"
            )

            activos_v917 = patrimonio_v917[patrimonio_v917["Clase"].eq("Activo")].copy()
            pasivos_v917 = patrimonio_v917[patrimonio_v917["Clase"].eq("Pasivo")].copy()
            activos_liquidos = float(activos_v917.loc[activos_v917["Nivel liquidez"].isin(["Alta", "Media"]), "Valor visual"].sum())
            activos_no_liquidos = float(activos_v917.loc[activos_v917["Nivel liquidez"].eq("Baja"), "Valor visual"].sum())
            pct_liquidez_pat = activos_liquidos / total_activos * 100 if total_activos else 0.0
            activo_principal_valor = float(activos_v917["Valor visual"].max()) if not activos_v917.empty else 0.0
            activo_principal_nombre = activos_v917.loc[activos_v917["Valor visual"].idxmax(), "Elemento"] if not activos_v917.empty else "Sin registrar"
            concentracion_principal = activo_principal_valor / total_activos * 100 if total_activos else 0.0
            top3_activos_pct = activos_v917.nlargest(3, "Valor visual")["Valor visual"].sum() / total_activos * 100 if total_activos else 0.0

            st.markdown("### 🧭 Estado patrimonial y liquidez")
            ep1, ep2, ep3, ep4 = st.columns(4)
            ep1.metric("💧 Activos líquidos", f"${activos_liquidos:,.0f}", f"{pct_liquidez_pat:.1f}% de activos")
            ep2.metric("🏘️ Activos no líquidos", f"${activos_no_liquidos:,.0f}")
            ep3.metric("🎯 Activo principal", str(activo_principal_nombre)[:24], f"{concentracion_principal:.1f}% de activos")
            ep4.metric("🧩 Top 3 activos", f"{top3_activos_pct:.1f}%", "Concentración patrimonial")

            if concentracion_principal >= 70:
                st.warning(f"⚠️ **Concentración alta:** {activo_principal_nombre} representa {concentracion_principal:.1f}% de los activos. Un patrimonio alto puede seguir siendo poco líquido o depender demasiado de un solo bien.")
            elif concentracion_principal >= 45:
                st.info(f"ℹ️ **Concentración media:** {activo_principal_nombre} representa {concentracion_principal:.1f}% de los activos.")
            else:
                st.success("✅ La composición de activos no depende excesivamente de un único elemento.")

            st.markdown("### 🏦 Composición de activos y pasivos")
            cp1, cp2 = st.columns(2)
            with cp1:
                activos_plot = activos_v917.groupby("Elemento", as_index=False)["Valor visual"].sum().sort_values("Valor visual", ascending=True)
                fig_activos_v917 = px.bar(
                    activos_plot, x="Valor visual", y="Elemento", orientation="h", text="Valor visual",
                    color="Valor visual", color_continuous_scale=["#00D9FF", "#7B2FFF", "#FF2E9A"],
                )
                fig_activos_v917.update_traces(
                    texttemplate="$%{text:,.0f}", textposition="outside", cliponaxis=False,
                    customdata=activos_plot[["Valor visual"]],
                    hovertemplate=(
                        "<b>🏠 %{y}</b><br>💰 💰 Valor neto: $%{x:,.0f}<br>"
                        "📊 📊 Participación en activos: %{x}<extra></extra>"
                    ),
                )
                # Se calcula el porcentaje en customdata para un tooltip preciso.
                if not activos_plot.empty:
                    fig_activos_v917.data[0].customdata = [[v, (v/total_activos*100 if total_activos else 0)] for v in activos_plot["Valor visual"]]
                    fig_activos_v917.data[0].hovertemplate = "<b>🏠 %{y}</b><br>💰 💰 Valor neto: $%{customdata[0]:,.0f}<br>📊 📊 Participación en activos: %{customdata[1]:.1f}%<extra></extra>"
                fig_activos_v917.update_yaxes(title="", automargin=True)
                st.plotly_chart(estilo_grafico(fig_activos_v917, "🏠 Composición de activos por nombre"), use_container_width=True, key="pat_activos_nombres_v917")
            with cp2:
                if not pasivos_v917.empty:
                    pasivos_plot = pasivos_v917.groupby("Elemento", as_index=False)["Valor visual"].sum().sort_values("Valor visual", ascending=True)
                    fig_pasivos_v917 = px.bar(
                        pasivos_plot, x="Valor visual", y="Elemento", orientation="h", text="Valor visual",
                        color="Valor visual", color_continuous_scale=["#FFB000", "#FF5A36", "#FF003C"],
                    )
                    fig_pasivos_v917.update_traces(
                        texttemplate="$%{text:,.0f}", textposition="outside", cliponaxis=False,
                        customdata=[[v, (v/total_pasivos*100 if total_pasivos else 0)] for v in pasivos_plot["Valor visual"]],
                        hovertemplate="<b>💳 %{y}</b><br>🔴 Saldo patrimonial: $%{customdata[0]:,.0f}<br>📊 📊 Participación en pasivos: %{customdata[1]:.1f}%<extra></extra>",
                    )
                    fig_pasivos_v917.update_yaxes(title="", automargin=True)
                    st.plotly_chart(estilo_grafico(fig_pasivos_v917, "💳 Composición de pasivos por nombre"), use_container_width=True, key="pat_pasivos_nombres_v917")
                else:
                    st.success("✅ No hay pasivos patrimoniales registrados.")

            st.markdown("### 💧 Liquidez patrimonial")
            liquidez_resumen = activos_v917.groupby("Nivel liquidez", as_index=False)["Valor visual"].sum() if not activos_v917.empty else pd.DataFrame()
            if not liquidez_resumen.empty:
                colores_liq = {"Alta":"#00FF9C", "Media":"#00D9FF", "Baja":"#FFB000", "Sin clasificar":"#A855F7", "No aplica":"#64748B"}
                fig_liq_v917 = go.Figure(go.Pie(
                    labels=liquidez_resumen["Nivel liquidez"], values=liquidez_resumen["Valor visual"], hole=.55,
                    marker=dict(colors=[colores_liq.get(x, "#94A3B8") for x in liquidez_resumen["Nivel liquidez"]], line=dict(color="#000", width=2)),
                    customdata=[[v, (v/total_activos*100 if total_activos else 0)] for v in liquidez_resumen["Valor visual"]],
                    hovertemplate="<b>💧 %{label}</b><br>💰 💰 Valor: $%{customdata[0]:,.0f}<br>📊 📊 Participación: %{customdata[1]:.1f}%<extra></extra>",
                    textinfo="label+percent",
                ))
                fig_liq_v917.add_annotation(text=f"{pct_liquidez_pat:.1f}%<br><span style='font-size:11px'>liquidez</span>", x=.5, y=.5, showarrow=False, font=dict(color="#F8FAFC", size=18))
                st.plotly_chart(estilo_grafico(fig_liq_v917, "💧 Distribución por nivel de liquidez"), use_container_width=True, key="pat_liquidez_v917")

            st.markdown("### ⚖️ Solidez patrimonial")
            sp1, sp2, sp3 = st.columns(3)
            sp1.metric("🏦 Activos por cada $100 de pasivos", f"${(total_activos/total_pasivos*100 if total_pasivos else total_activos):,.0f}" if total_pasivos else "Sin pasivos")
            sp2.metric("💳 Pasivos / activos", f"{deuda_activos_pct:.1f}%")
            sp3.metric("💎 Patrimonio libre", f"{(patrimonio_neto/total_activos*100 if total_activos else 0):.1f}% de activos")
            st.info(f"⚖️ Por cada $100 en activos existen aproximadamente **${deuda_activos_pct:,.0f} en pasivos**. Esta relación describe estructura patrimonial, no capacidad mensual de pago.")

            st.markdown("### 🧹 Calidad de los datos patrimoniales")
            sin_nombre_pat = int(patrimonio_v917["Elemento"].eq("Sin nombre").sum())
            sin_tipo_pat = int(tipo_norm_pat.eq("").sum())
            valores_cero_pat = int(patrimonio_v917["Valor visual"].le(0).sum())
            fechas_val_col = "Fecha valoración" if "Fecha valoración" in patrimonio_v917.columns else "Fecha" if "Fecha" in patrimonio_v917.columns else None
            sin_fecha_pat = int(pd.to_datetime(patrimonio_v917[fechas_val_col], errors="coerce", dayfirst=True).isna().sum()) if fechas_val_col else len(patrimonio_v917)
            duplicados_pat = int(patrimonio_v917[["Elemento", "Valor visual"]].duplicated(keep=False).sum())
            qp1, qp2, qp3, qp4, qp5 = st.columns(5)
            qp1.metric("🏷️ Sin nombre", sin_nombre_pat)
            qp2.metric("📂 Sin tipo", sin_tipo_pat)
            qp3.metric("0️⃣ Valor cero", valores_cero_pat)
            qp4.metric("📅 Sin valoración", sin_fecha_pat)
            qp5.metric("👯 Posibles duplicados", duplicados_pat)

            with st.expander("🔎 Ver tabla patrimonial enriquecida"):
                columnas_tabla_pat = [c for c in ["Elemento", "Clase", "Categoría", "Subcategoría", "Entidad", "Valor actual", "Saldo pendiente", "Valor neto", "Nivel liquidez", "Fecha valoración", "Estado"] if c in patrimonio_v917.columns]
                st.dataframe(patrimonio_v917[columnas_tabla_pat], use_container_width=True, hide_index=True)

            # ======================================================
            # EVOLUCIÓN ACUMULADA MENSUAL DEL PATRIMONIO
            # - Cada registro del mes se interpreta como un movimiento neto.
            # - El patrimonio acumulado suma esos movimientos mes a mes.
            # - Los meses sin movimientos conservan el saldo acumulado anterior.
            # - El acumulado se calcula desde el primer registro histórico, aunque
            #   la gráfica solo muestre el periodo seleccionado en los filtros.
            # ======================================================
            patrimonio_mensual = pd.DataFrame()
            patrimonio_hist = patrimonio.copy()
            patrimonio_hist["Fecha"] = pd.to_datetime(
                patrimonio_hist["Fecha"],
                errors="coerce",
                dayfirst=True,
            )
            patrimonio_hist["Valor neto"] = pd.to_numeric(
                patrimonio_hist["Valor neto"],
                errors="coerce",
            ).fillna(0.0)
            patrimonio_hist = patrimonio_hist.dropna(subset=["Fecha"])
            patrimonio_hist = patrimonio_hist[
                patrimonio_hist["Fecha"].le(fecha_hasta_ts)
            ].copy()

            if patrimonio_hist.empty:
                st.info(
                    "No hay movimientos de patrimonio con fecha hasta el periodo seleccionado. "
                    "Agrega registros mensuales en la columna Fecha para construir la evolución acumulada."
                )
            else:
                patrimonio_hist["Periodo"] = patrimonio_hist["Fecha"].dt.to_period("M")
                patrimonio_mensual_base = (
                    patrimonio_hist.groupby("Periodo", as_index=False)["Valor neto"]
                    .sum()
                    .rename(columns={"Valor neto": "Movimiento mensual"})
                    .sort_values("Periodo")
                )

                periodo_inicio_hist = patrimonio_mensual_base["Periodo"].min()
                periodo_fin_hist = pd.Period(fecha_hasta_ts, freq="M")
                periodos_completos = pd.period_range(
                    start=periodo_inicio_hist,
                    end=periodo_fin_hist,
                    freq="M",
                )

                patrimonio_mensual = (
                    patrimonio_mensual_base.set_index("Periodo")
                    .reindex(periodos_completos, fill_value=0.0)
                    .rename_axis("Periodo")
                    .reset_index()
                )
                patrimonio_mensual["Patrimonio acumulado"] = (
                    patrimonio_mensual["Movimiento mensual"].cumsum()
                )
                patrimonio_mensual["Variación"] = patrimonio_mensual["Movimiento mensual"]
                patrimonio_mensual["Variación %"] = (
                    patrimonio_mensual["Variación"]
                    / patrimonio_mensual["Patrimonio acumulado"].shift(1).abs().replace(0, pd.NA)
                    * 100
                ).fillna(0.0)

                periodo_desde = pd.Period(fecha_desde_ts, freq="M")
                patrimonio_mensual = patrimonio_mensual[
                    patrimonio_mensual["Periodo"].between(periodo_desde, periodo_fin_hist)
                ].copy()

                tolerancia_estable = 1.0
                patrimonio_mensual["Estado"] = patrimonio_mensual["Variación"].apply(
                    lambda valor: (
                        "Subió"
                        if valor > tolerancia_estable
                        else "Bajó"
                        if valor < -tolerancia_estable
                        else "Estable"
                    )
                )
                patrimonio_mensual["Mes"] = patrimonio_mensual["Periodo"].dt.strftime("%b %Y")
                patrimonio_mensual["Color"] = patrimonio_mensual["Estado"].map(
                    {
                        "Subió": "#22C55E",
                        "Bajó": "#EF4444",
                        "Estable": "#FBBF24",
                    }
                ).fillna("#38BDF8")

                if patrimonio_mensual.empty:
                    st.info("No hay meses de patrimonio dentro del periodo filtrado.")
                else:
                    saldo_inicial_periodo = float(
                        patrimonio_mensual.iloc[0]["Patrimonio acumulado"]
                        - patrimonio_mensual.iloc[0]["Movimiento mensual"]
                    )
                    saldo_final_periodo = float(
                        patrimonio_mensual.iloc[-1]["Patrimonio acumulado"]
                    )
                    variacion_total_pat = saldo_final_periodo - saldo_inicial_periodo
                    meses_subida = int(patrimonio_mensual["Estado"].eq("Subió").sum())
                    meses_bajada = int(patrimonio_mensual["Estado"].eq("Bajó").sum())
                    meses_estables = int(patrimonio_mensual["Estado"].eq("Estable").sum())

                    st.markdown("#### 🚀 Construcción mensual de tu patrimonio")
                    st.caption(
                        "La línea representa el patrimonio acumulado. Cada barra parte del nivel alcanzado el mes anterior "
                        "y muestra el avance o retroceso del mes; si no hay movimiento, el patrimonio se mantiene estable."
                    )

                    pm1, pm2, pm3, pm4 = st.columns(4)
                    pm1.metric(
                        "Patrimonio acumulado",
                        f"${saldo_final_periodo:,.0f}",
                        delta=f"{'+' if variacion_total_pat >= 0 else ''}${variacion_total_pat:,.0f} en el periodo",
                    )
                    pm2.metric("Meses creciendo", meses_subida)
                    pm3.metric("Meses estables", meses_estables)
                    pm4.metric("Meses bajando", meses_bajada)

                    # Para que los cambios mensuales sean visibles, el eje vertical
                    # se expresa como variación respecto al patrimonio inicial del periodo.
                    # En esta gráfica, $0 equivale al saldo_inicial_periodo.
                    patrimonio_mensual["Crecimiento desde inicio"] = (
                        patrimonio_mensual["Patrimonio acumulado"] - saldo_inicial_periodo
                    )

                    meses_linea = ["Inicio"] + patrimonio_mensual["Mes"].tolist()
                    crecimiento_linea = [0.0] + patrimonio_mensual["Crecimiento desde inicio"].tolist()
                    patrimonio_real_linea = [saldo_inicial_periodo] + patrimonio_mensual["Patrimonio acumulado"].tolist()
                    movimiento_linea = [0.0] + patrimonio_mensual["Movimiento mensual"].tolist()
                    variacion_pct_linea = [0.0] + patrimonio_mensual["Variación %"].tolist()
                    estado_linea = ["Patrimonio inicial"] + patrimonio_mensual["Estado"].tolist()
                    colores_linea = ["#F8FAFC"] + patrimonio_mensual["Color"].tolist()

                    # Cada barra comienza exactamente en el nivel alcanzado al cierre
                    # del mes anterior. Así funciona como un puente mensual: el ancho
                    # vertical de la barra es el movimiento del mes y su punto de partida
                    # es el crecimiento acumulado previo.
                    patrimonio_mensual["Base mes anterior"] = (
                        patrimonio_mensual["Crecimiento desde inicio"]
                        - patrimonio_mensual["Movimiento mensual"]
                    )

                    fig_pat_mensual = go.Figure()
                    fig_pat_mensual.add_trace(go.Bar(
                        x=patrimonio_mensual["Mes"],
                        y=patrimonio_mensual["Movimiento mensual"],
                        base=patrimonio_mensual["Base mes anterior"],
                        name="Movimiento desde el mes anterior",
                        marker=dict(
                            color=patrimonio_mensual["Color"],
                            opacity=0.55,
                            line=dict(color=patrimonio_mensual["Color"], width=1.2),
                        ),
                        customdata=patrimonio_mensual[[
                            "Estado",
                            "Patrimonio acumulado",
                            "Base mes anterior",
                            "Crecimiento desde inicio",
                        ]],
                        hovertemplate=(
                            "<b>📅 %{x}</b><br>"
                            "Base del mes anterior: $%{customdata[2]:+,.0f}<br>"
                            "🔄 Movimiento del mes: $%{y:+,.0f}<br>"
                            "🚀 Crecimiento acumulado al cierre: $%{customdata[3]:+,.0f}<br>"
                            "💎 Patrimonio real al cierre: $%{customdata[1]:,.0f}<br>"
                            "🚦 Estado: %{customdata[0]}<extra></extra>"
                        ),
                    ))
                    fig_pat_mensual.add_trace(go.Scatter(
                        x=meses_linea,
                        y=crecimiento_linea,
                        mode="lines+markers",
                        name="Crecimiento sobre patrimonio inicial",
                        line=dict(color="#38BDF8", width=4, shape="spline"),
                        marker=dict(
                            size=13,
                            color=colores_linea,
                            line=dict(color="#F8FAFC", width=1.5),
                        ),
                        fill="tozeroy",
                        fillcolor="rgba(56,189,248,0.10)",
                        customdata=list(zip(
                            patrimonio_real_linea,
                            movimiento_linea,
                            variacion_pct_linea,
                            estado_linea,
                        )),
                        hovertemplate=(
                            "<b>📅 %{x}</b><br>"
                            "💎 Patrimonio real: $%{customdata[0]:,.0f}<br>"
                            "🚀 Crecimiento desde el inicio: $%{y:,.0f}<br>"
                            "🔄 Movimiento del mes: $%{customdata[1]:,.0f}<br>"
                            "📈 Variación mensual: %{customdata[2]:+.2f}%<br>"
                            "🚦 Estado: %{customdata[3]}<extra></extra>"
                        ),
                    ))
                    fig_pat_mensual.add_hline(
                        y=0,
                        line_dash="dot",
                        line_color="rgba(248,250,252,0.65)",
                        annotation_text=f"Patrimonio inicial = ${saldo_inicial_periodo:,.0f}",
                        annotation_position="top left",
                    )
                    fig_pat_mensual.update_layout(
                        template="plotly_dark",
                        height=540,
                        paper_bgcolor="#000000",
                        plot_bgcolor="#000000",
                        title=dict(
                            text="Crecimiento del patrimonio sobre el valor inicial",
                            font=dict(color="#F8FAFC"),
                        ),
                        xaxis=dict(
                            title="Mes",
                            type="category",
                            categoryorder="array",
                            categoryarray=meses_linea,
                            gridcolor="rgba(148,163,184,0.08)",
                        ),
                        yaxis=dict(
                            title="Cambio frente al patrimonio inicial",
                            tickprefix="$",
                            tickformat="+,.0f",
                            zeroline=True,
                            zerolinecolor="rgba(248,250,252,0.65)",
                            zerolinewidth=2,
                            gridcolor="rgba(148,163,184,0.14)",
                        ),
                        legend=dict(orientation="h", y=1.08),
                        barmode="overlay",
                        margin=dict(t=95, b=45, l=70, r=35),
                        hoverlabel=dict(
                            bgcolor="#0F172A",
                            bordercolor="#38BDF8",
                            font=dict(color="#F8FAFC"),
                        ),
                    )
                    st.caption(
                        f"En esta escala, la línea $0 representa tu patrimonio inicial de "
                        f"${saldo_inicial_periodo:,.0f}. Así se aprecia con claridad cuánto ha subido "
                        "o bajado el patrimonio respecto a ese punto de partida. Las barras se enlazan desde el cierre de cada mes anterior."
                    )
                    st.plotly_chart(
                        fig_pat_mensual,
                        use_container_width=True,
                        key="evolucion_patrimonio_base_inicial_v4",
                    )

                    ultimo_estado = str(patrimonio_mensual.iloc[-1]["Estado"])
                    ultimo_cambio = float(patrimonio_mensual.iloc[-1]["Movimiento mensual"])
                    if ultimo_estado == "Subió":
                        st.success(
                            f"📈 Este mes agregaste ${ultimo_cambio:,.0f} a tu patrimonio. "
                            "Ese avance se acumula y fortalece tu base financiera."
                        )
                    elif ultimo_estado == "Bajó":
                        st.warning(
                            f"📉 Este mes el patrimonio acumulado disminuyó ${abs(ultimo_cambio):,.0f}. "
                            "Revisa si corresponde a una deuda, retiro, pérdida o ajuste de valoración."
                        )
                    else:
                        st.info(
                            "⏸️ Este mes no hubo movimiento: el patrimonio conservó todo lo acumulado. "
                            "Mantenerlo también es una forma de proteger el progreso."
                        )

                    # ======================================================
                    # EXPLICACIÓN DEL CRECIMIENTO DEL PATRIMONIO
                    # Descompone la variación del periodo por categoría para
                    # responder visualmente qué impulsó o redujo el patrimonio.
                    # ======================================================
                    st.markdown("---")
                    st.markdown("#### 🧭 ¿Qué hizo crecer o reducir tu patrimonio?")
                    st.caption(
                        "Esta sección distribuye el cambio del periodo entre las categorías registradas en la hoja Patrimonio. "
                        "Los valores positivos impulsan el patrimonio y los negativos lo reducen."
                    )

                    aportes_periodo = patrimonio_hist[
                        patrimonio_hist["Fecha"].between(fecha_desde_ts, fecha_hasta_ts)
                    ].copy()
                    aportes_periodo["Categoría"] = (
                        aportes_periodo["Categoría"]
                        .fillna("Sin categoría")
                        .astype(str)
                        .str.strip()
                        .replace("", "Sin categoría")
                    )

                    contribucion_categoria = (
                        aportes_periodo.groupby("Categoría", as_index=False)["Valor neto"]
                        .sum()
                        .rename(columns={"Valor neto": "Contribución"})
                    )
                    contribucion_categoria = contribucion_categoria[
                        contribucion_categoria["Contribución"].abs() > tolerancia_estable
                    ].copy()
                    contribucion_categoria["Impacto absoluto"] = contribucion_categoria["Contribución"].abs()
                    contribucion_categoria["Estado"] = contribucion_categoria["Contribución"].apply(
                        lambda valor: "Impulsó" if valor > 0 else "Redujo"
                    )

                    if contribucion_categoria.empty:
                        st.info("No hay movimientos por categoría dentro del periodo seleccionado.")
                    else:
                        positivos = contribucion_categoria[contribucion_categoria["Contribución"] > 0].copy()
                        negativos = contribucion_categoria[contribucion_categoria["Contribución"] < 0].copy()
                        total_impulsos = float(positivos["Contribución"].sum())
                        total_reducciones = abs(float(negativos["Contribución"].sum()))
                        aporte_principal = (
                            positivos.sort_values("Contribución", ascending=False).iloc[0]
                            if not positivos.empty else None
                        )
                        freno_principal = (
                            negativos.sort_values("Contribución", ascending=True).iloc[0]
                            if not negativos.empty else None
                        )

                        q1, q2, q3 = st.columns(3)
                        q1.metric("Impulsos positivos", f"${total_impulsos:,.0f}")
                        q2.metric("Reducciones", f"-${total_reducciones:,.0f}" if total_reducciones else "$0")
                        q3.metric(
                            "Resultado neto explicado",
                            f"${contribucion_categoria['Contribución'].sum():+,.0f}",
                        )

                        # 1. Cascada: del patrimonio inicial al patrimonio final.
                        contribucion_ordenada = contribucion_categoria.sort_values(
                            "Contribución", ascending=False
                        )
                        waterfall_x = ["Patrimonio inicial"] + contribucion_ordenada["Categoría"].tolist() + ["Patrimonio final"]
                        waterfall_y = [saldo_inicial_periodo] + contribucion_ordenada["Contribución"].tolist() + [saldo_final_periodo]
                        waterfall_measure = ["absolute"] + ["relative"] * len(contribucion_ordenada) + ["total"]
                        waterfall_text = [
                            f"${saldo_inicial_periodo:,.0f}"
                        ] + [
                            f"{valor:+,.0f}" for valor in contribucion_ordenada["Contribución"]
                        ] + [f"${saldo_final_periodo:,.0f}"]

                        fig_cascada_pat = go.Figure(go.Waterfall(
                            orientation="v",
                            measure=waterfall_measure,
                            x=waterfall_x,
                            y=waterfall_y,
                            text=waterfall_text,
                            textposition="outside",
                            connector={"line": {"color": "rgba(148,163,184,0.45)", "dash": "dot"}},
                            increasing={"marker": {"color": "#22C55E"}},
                            decreasing={"marker": {"color": "#EF4444"}},
                            totals={"marker": {"color": "#38BDF8"}},
                            hovertemplate="<b>📅 %{x}</b><br>⚡ Impacto: $%{y:+,.0f}<extra></extra>",
                        ))
                        fig_cascada_pat.update_layout(
                            template="plotly_dark",
                            paper_bgcolor="#000000",
                            plot_bgcolor="#000000",
                            height=500,
                            title="Puente del patrimonio: qué explicó el cambio",
                            showlegend=False,
                            xaxis_title="Factor",
                            yaxis=dict(title="Patrimonio", tickprefix="$", tickformat=",.0f"),
                            margin=dict(t=70, b=90, l=70, r=30),
                        )
                        st.plotly_chart(
                            fig_cascada_pat,
                            use_container_width=True,
                            key="cascada_impulsores_patrimonio_v1",
                        )

                        # 2. Treemap y motor de crecimiento lado a lado.
                        col_imp1, col_imp2 = st.columns(2)
                        with col_imp1:
                            fig_treemap_impulsores = px.treemap(
                                contribucion_categoria,
                                path=["Estado", "Categoría"],
                                values="Impacto absoluto",
                                color="Contribución",
                                color_continuous_scale=[
                                    [0.0, "#EF4444"],
                                    [0.5, "#64748B"],
                                    [1.0, "#22C55E"],
                                ],
                                color_continuous_midpoint=0,
                                custom_data=["Contribución", "Estado"],
                                title="Mapa de contribución",
                            )
                            fig_treemap_impulsores.update_traces(
                                texttemplate="<b>🏷️ %{label}</b><br>$%{customdata[0]:+,.0f}",
                                hovertemplate=(
                                    "<b>🏷️ %{label}</b><br>"
                                    "⚡ Impacto: $%{customdata[0]:+,.0f}<br>"
                                    "Resultado: %{customdata[1]}<extra></extra>"
                                ),
                            )
                            fig_treemap_impulsores.update_layout(
                                template="plotly_dark",
                                paper_bgcolor="#000000",
                                margin=dict(t=55, b=10, l=10, r=10),
                                height=440,
                                coloraxis_colorbar=dict(title="Impacto"),
                            )
                            st.plotly_chart(
                                fig_treemap_impulsores,
                                use_container_width=True,
                                key="treemap_impulsores_patrimonio_v1",
                            )

                        with col_imp2:
                            if positivos.empty:
                                st.info("No hubo impulsores positivos en el periodo seleccionado.")
                            else:
                                motor = positivos.sort_values("Contribución", ascending=True).tail(6).copy()
                                motor["Participación %"] = (
                                    motor["Contribución"] / total_impulsos * 100
                                    if total_impulsos else 0
                                )
                                fig_motor_pat = go.Figure(go.Bar(
                                    x=motor["Participación %"],
                                    y=motor["Categoría"],
                                    orientation="h",
                                    marker=dict(color="#22C55E"),
                                    customdata=motor[["Contribución"]],
                                    text=motor["Participación %"].map(lambda x: f"{x:.1f}%"),
                                    textposition="outside",
                                    hovertemplate=(
                                        "<b>🏠 %{y}</b><br>"
                                        "Aporte: $%{customdata[0]:,.0f}<br>"
                                        "📊 Participación: %{x:.1f}%<extra></extra>"
                                    ),
                                ))
                                fig_motor_pat.update_layout(
                                    template="plotly_dark",
                                    paper_bgcolor="#000000",
                                    plot_bgcolor="#000000",
                                    title="Motor del crecimiento",
                                    height=440,
                                    xaxis=dict(title="Participación en los impulsos positivos", ticksuffix="%"),
                                    yaxis=dict(title=""),
                                    margin=dict(t=55, b=55, l=110, r=35),
                                    showlegend=False,
                                )
                                st.plotly_chart(
                                    fig_motor_pat,
                                    use_container_width=True,
                                    key="motor_crecimiento_patrimonio_v1",
                                )

                        if aporte_principal is not None:
                            participacion_principal = (
                                float(aporte_principal["Contribución"]) / total_impulsos * 100
                                if total_impulsos else 0
                            )
                            mensaje = (
                                f"🏆 El principal impulsor fue **{aporte_principal['Categoría']}**, "
                                f"con un aporte de **${float(aporte_principal['Contribución']):,.0f}**, "
                                f"equivalente al **{participacion_principal:.1f}%** de todos los movimientos positivos."
                            )
                            if freno_principal is not None:
                                mensaje += (
                                    f" El mayor freno fue **{freno_principal['Categoría']}**, "
                                    f"que redujo el patrimonio en **${abs(float(freno_principal['Contribución'])):,.0f}**."
                                )
                            st.success(mensaje)

            resumen_tipo = patrimonio.groupby("Tipo", as_index=False)["Valor neto"].sum()
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(fig_patrimonio_donut(resumen_tipo), use_container_width=True)
            with col2:
                st.markdown("#### Tendencia mensual del patrimonio")
                if patrimonio_mensual.empty:
                    st.info(
                        "No hay suficientes fechas mensuales para mostrar la tendencia del patrimonio."
                    )
                else:
                    tendencia_pat = patrimonio_mensual.copy()
                    tendencia_pat["Mes gráfico"] = tendencia_pat["Periodo"].dt.to_timestamp()
                    fig_tendencia_pat = go.Figure()
                    fig_tendencia_pat.add_trace(
                        go.Scatter(
                            x=tendencia_pat["Mes gráfico"],
                            y=tendencia_pat["Patrimonio acumulado"],
                            mode="lines+markers",
                            name="Patrimonio acumulado",
                            line=dict(width=4, shape="spline"),
                            marker=dict(size=10),
                            fill="tozeroy",
                            customdata=tendencia_pat[["Movimiento mensual", "Estado"]],
                            hovertemplate=(
                                "<b>%{x|%B %Y}</b><br>"
                                "Patrimonio: $%{y:,.0f}<br>"
                                "🔄 Movimiento del mes: $%{customdata[0]:+,.0f}<br>"
                                "Tendencia: %{customdata[1]}<extra></extra>"
                            ),
                        )
                    )
                    fig_tendencia_pat.update_layout(
                        template="plotly_dark",
                        height=420,
                        paper_bgcolor="#000000",
                        plot_bgcolor="#000000",
                        title="Patrimonio mes a mes",
                        xaxis=dict(title="Mes", tickformat="%b %Y"),
                        yaxis=dict(title="Patrimonio acumulado", tickprefix="$", tickformat=",.0f"),
                        margin=dict(t=65, b=45, l=65, r=25),
                        hovermode="x unified",
                    )
                    st.plotly_chart(
                        fig_tendencia_pat,
                        use_container_width=True,
                        key="tendencia_mensual_patrimonio_resumen_v1",
                    )
                    st.caption(
                        "La línea permite identificar de forma directa si el patrimonio viene creciendo, "
                        "se mantiene estable o presenta una tendencia descendente mes a mes."
                    )

            st.markdown("#### Mapa del patrimonio")
            st.plotly_chart(fig_patrimonio_treemap(patrimonio), use_container_width=True)

            col3, col4 = st.columns(2)
            with col3:
                st.plotly_chart(fig_patrimonio_liquidez(patrimonio), use_container_width=True)
            with col4:
                st.plotly_chart(fig_patrimonio_concentracion_categoria(patrimonio), use_container_width=True)

            st.markdown("#### Detalle de patrimonio")
            st.dataframe(
                patrimonio.sort_values(["Tipo", "Categoría", "Valor neto"], ascending=[True, True, False]),
                use_container_width=True,
                hide_index=True,
            )

            csv_patrimonio = patrimonio.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar patrimonio procesado (CSV)",
                csv_patrimonio,
                "patrimonio_procesado.csv",
                "text/csv",
            )

    if pestana_activa == etiquetas_pestanas[7]:
        contexto_pestana(
            "¿Qué tan saludable es mi situación financiera?",
            "Integra ahorro, presupuesto, endeudamiento, fondo de emergencia y metas; explica qué fortalece o debilita el resultado y qué acción tendría mayor impacto.",
        )
        st.markdown("## 🏆 Diagnóstico integral de salud financiera")
        st.caption(
            "El score conserva la fórmula actual de la aplicación y muestra de forma transparente "
            "cómo se construye. No corresponde a un score crediticio bancario."
        )

        # ======================================================
        # UTILIDADES LOCALES DE LA PESTAÑA SCORE
        # ======================================================
        def _pct_0_100(valor):
            """Normaliza proporciones 0–1 y porcentajes 0–100 a una escala 0–100."""
            try:
                numero = float(valor)
            except (TypeError, ValueError):
                return 0.0
            if pd.isna(numero):
                return 0.0
            if -1.0 <= numero <= 1.0:
                numero *= 100.0
            return min(max(numero, 0.0), 100.0)

        def _nivel_score(valor):
            if valor >= 85:
                return "Excelente", "🟢"
            if valor >= 70:
                return "Bueno", "🔵"
            if valor >= 50:
                return "En atención", "🟡"
            return "Riesgo alto", "🔴"

        def _estado_componente(pct):
            if pct >= 80:
                return "Fortaleza", "🟢"
            if pct >= 60:
                return "Aceptable", "🔵"
            if pct >= 40:
                return "En atención", "🟡"
            return "Riesgo", "🔴"

        def _calcular_componentes_score(
            gastos_valor,
            ingresos_valor,
            presupuesto_valor,
            activos_valor,
            pasivos_valor,
            fondo_valor,
            gasto_mensual_valor,
            metas_df,
            gastos_df,
        ):
            pts_pres, ratio_pres = puntaje_presupuesto(gastos_valor, presupuesto_valor)
            pts_aho, pct_aho = puntaje_ahorro(ingresos_valor - gastos_valor, ingresos_valor)
            pts_end, pct_end = puntaje_endeudamiento(pasivos_valor, activos_valor)
            pts_inn, pct_inn, monto_inn, innecesarios_df = puntaje_gastos_innecesarios(gastos_df)
            pts_eme, _ = puntaje_fondo_emergencia(fondo_valor, gasto_mensual_valor)
            pts_met, avance_met = puntaje_metas(metas_df)

            ratio_pres = _pct_0_100(ratio_pres)
            pct_aho = max(min(float(pct_aho), 100.0), -100.0)
            pct_end = _pct_0_100(pct_end)
            pct_inn = _pct_0_100(pct_inn)
            avance_met = _pct_0_100(avance_met)

            datos = [
                {
                    "Indicador": "Presupuesto",
                    "Icono": "🎯",
                    "Puntos": float(pts_pres),
                    "Máximo": 25.0,
                    "Puntaje %": _pct_0_100(float(pts_pres) / 25.0),
                    "Base": f"Ejecución presupuestal: {ratio_pres:.1f}%",
                },
                {
                    "Indicador": "Ahorro",
                    "Icono": "💰",
                    "Puntos": float(pts_aho),
                    "Máximo": 20.0,
                    "Puntaje %": _pct_0_100(float(pts_aho) / 20.0),
                    "Base": f"Capacidad de ahorro: {pct_aho:.1f}%",
                },
                {
                    "Indicador": "Endeudamiento",
                    "Icono": "💳",
                    "Puntos": float(pts_end),
                    "Máximo": 20.0,
                    "Puntaje %": _pct_0_100(float(pts_end) / 20.0),
                    "Base": f"Pasivos / activos: {pct_end:.1f}%",
                },
                {
                    "Indicador": "Gastos innecesarios",
                    "Icono": "🛒",
                    "Puntos": float(pts_inn),
                    "Máximo": 10.0,
                    "Puntaje %": _pct_0_100(float(pts_inn) / 10.0),
                    "Base": f"Gasto marcado: {pct_inn:.1f}%",
                },
                {
                    "Indicador": "Fondo emergencia",
                    "Icono": "🛡️",
                    "Puntos": float(pts_eme),
                    "Máximo": 15.0,
                    "Puntaje %": _pct_0_100(float(pts_eme) / 15.0),
                    "Base": (
                        f"Cobertura: {(fondo_valor / gasto_mensual_valor):.1f} meses"
                        if gasto_mensual_valor > 0
                        else "Sin gasto mensual de referencia"
                    ),
                },
                {
                    "Indicador": "Metas",
                    "Icono": "🏁",
                    "Puntos": float(pts_met),
                    "Máximo": 10.0,
                    "Puntaje %": _pct_0_100(float(pts_met) / 10.0),
                    "Base": f"Cumplimiento promedio: {avance_met:.1f}%",
                },
            ]
            return datos, {
                "ratio_presupuesto": ratio_pres,
                "pct_ahorro": pct_aho,
                "pct_endeuda": pct_end,
                "pct_innecesarios": pct_inn,
                "monto_innecesarios": float(monto_inn),
                "avance_metas": avance_met,
                "df_innecesarios": innecesarios_df,
            }

        # ======================================================
        # 1. BASE ACTUAL DEL SCORE
        # ======================================================
        total_activos_score = (
            float(
                patrimonio.loc[
                    patrimonio["Tipo"].map(normalizar).eq("ACTIVO"),
                    "Valor neto",
                ].sum()
            )
            if not patrimonio.empty
            else 0.0
        )
        total_pasivos_score = (
            abs(
                float(
                    patrimonio.loc[
                        ~patrimonio["Tipo"].map(normalizar).eq("ACTIVO"),
                        "Valor neto",
                    ].sum()
                )
            )
            if not patrimonio.empty
            else 0.0
        )
        periodos_score = (
            max(len(df[["ANIO", "MES"]].dropna(how="all").drop_duplicates()), 1)
            if not df.empty
            else 1
        )
        presupuesto_total_score = float(presupuesto_mensual_general or 0.0)
        gasto_mensual_promedio = float(total_gastos) / periodos_score if periodos_score else 0.0
        gasto_promedio_diario_fondo = gasto_mensual_promedio / 30 if gasto_mensual_promedio else 0.0
        fondo_emergencia_valor = valor_fondo_emergencia(patrimonio)
        meta_fondo_emergencia = gasto_mensual_promedio * 3
        avance_fondo_emergencia = (
            fondo_emergencia_valor / meta_fondo_emergencia * 100
            if meta_fondo_emergencia
            else 0.0
        )
        avance_fondo_emergencia = _pct_0_100(avance_fondo_emergencia)
        avance_fondo_emergencia_limitado = min(max(avance_fondo_emergencia, 0), 100)
        faltante_fondo_emergencia = max(meta_fondo_emergencia - fondo_emergencia_valor, 0.0)
        meses_emergencia = (
            fondo_emergencia_valor / gasto_mensual_promedio
            if gasto_mensual_promedio
            else 0.0
        )
        dias_cubiertos_fondo = (
            fondo_emergencia_valor / gasto_promedio_diario_fondo
            if gasto_promedio_diario_fondo
            else 0.0
        )

        componentes, metricas_score = _calcular_componentes_score(
            gastos_valor=float(total_gastos),
            ingresos_valor=float(total_ingresos),
            presupuesto_valor=presupuesto_total_score,
            activos_valor=total_activos_score,
            pasivos_valor=total_pasivos_score,
            fondo_valor=fondo_emergencia_valor,
            gasto_mensual_valor=gasto_mensual_promedio,
            metas_df=metas,
            gastos_df=df,
        )
        score_total = round(sum(c["Puntos"] for c in componentes), 1)
        nivel_score, icono_score = _nivel_score(score_total)
        estado_score = etiqueta_score(score_total)

        ratio_presupuesto = metricas_score["ratio_presupuesto"]
        pct_ahorro = metricas_score["pct_ahorro"]
        pct_endeuda = metricas_score["pct_endeuda"]
        pct_innecesarios = metricas_score["pct_innecesarios"]
        monto_innecesarios = metricas_score["monto_innecesarios"]
        avance_metas = metricas_score["avance_metas"]
        df_innecesarios = metricas_score["df_innecesarios"]

        componentes_df = pd.DataFrame(componentes)
        componentes_df["Estado"] = componentes_df["Puntaje %"].map(
            lambda valor: _estado_componente(valor)[0]
        )
        componentes_df["Icono estado"] = componentes_df["Puntaje %"].map(
            lambda valor: _estado_componente(valor)[1]
        )
        componentes_df["Contribución % del score"] = (
            componentes_df["Puntos"] / max(score_total, 1) * 100
        )

        fortalezas_df = componentes_df.sort_values("Puntaje %", ascending=False)
        debilidades_df = componentes_df.sort_values("Puntaje %", ascending=True)
        principal_fortaleza = fortalezas_df.iloc[0]
        principal_debilidad = debilidades_df.iloc[0]

        # ======================================================
        # 2. RESULTADO GENERAL
        # ======================================================
        st.markdown("### 1. 🏆 Resultado general")
        sg1, sg2, sg3, sg4 = st.columns(4)
        sg1.metric("🏆 Score financiero", f"{score_total:.1f}/100", f"{icono_score} {nivel_score}")
        sg2.metric(
            "✅ Principal fortaleza",
            str(principal_fortaleza["Indicador"]),
            f"{principal_fortaleza['Puntaje %']:.1f}/100",
        )
        sg3.metric(
            "⚠️ Principal debilidad",
            str(principal_debilidad["Indicador"]),
            f"{principal_debilidad['Puntaje %']:.1f}/100",
        )
        sg4.metric(
            "🎯 Cumplimiento de metas",
            f"{avance_metas:.1f}%",
            "Escala 0–100",
        )

        col_score, col_radar = st.columns([1, 1])
        with col_score:
            fig_gauge_score = fig_score_gauge(score_total)
            fig_gauge_score.update_traces(
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#00E5FF"},
                    "steps": [
                        {"range": [0, 50], "color": "#7F1D1D"},
                        {"range": [50, 70], "color": "#854D0E"},
                        {"range": [70, 85], "color": "#075985"},
                        {"range": [85, 100], "color": "#065F46"},
                    ],
                    "threshold": {
                        "line": {"color": "#F8FAFC", "width": 4},
                        "thickness": 0.8,
                        "value": score_total,
                    },
                },
                number={"suffix": "/100"},
                title={
                    "text": (
                        f"🏆 Score financiero<br>"
                        f"<span style='font-size:13px'>"
                        f"{icono_score} {nivel_score} · "
                        f"Fortaleza: {principal_fortaleza['Indicador']} · "
                        f"Debilidad: {principal_debilidad['Indicador']}"
                        f"</span>"
                    )
                },
            )
            st.plotly_chart(fig_gauge_score, use_container_width=True)
            st.markdown(f"### {icono_score} {estado_score}")
        with col_radar:
            fig_radar_score = fig_score_radar(componentes)
            fig_radar_score.update_traces(
                hovertemplate=(
                    "<b>📊 %{theta}</b><br>"
                    "🏆 Cumplimiento: %{r:.1f}/100<br>"
                    "🎯 Referencia saludable: 80/100"
                    "<extra></extra>"
                )
            )
            st.plotly_chart(fig_radar_score, use_container_width=True)

        # ======================================================
        # 3. FORTALEZAS Y DEBILIDADES
        # ======================================================
        st.markdown("### 2. ✅ Fortalezas y ⚠️ debilidades")
        fcol, dcol = st.columns(2)
        with fcol:
            st.markdown("#### ✅ Factores que fortalecen el score")
            for _, row in fortalezas_df.head(3).iterrows():
                estado_nombre, estado_icono = _estado_componente(row["Puntaje %"])
                st.success(
                    f"{row['Icono']} **{row['Indicador']}** — "
                    f"{row['Puntaje %']:.1f}/100 · {estado_icono} {estado_nombre}. "
                    f"{row['Base']}."
                )
        with dcol:
            st.markdown("#### ⚠️ Factores que limitan el score")
            for _, row in debilidades_df.head(3).iterrows():
                estado_nombre, estado_icono = _estado_componente(row["Puntaje %"])
                st.warning(
                    f"{row['Icono']} **{row['Indicador']}** — "
                    f"{row['Puntaje %']:.1f}/100 · {estado_icono} {estado_nombre}. "
                    f"{row['Base']}."
                )

        # ======================================================
        # 4. DESGLOSE TRANSPARENTE
        # ======================================================
        st.markdown("### 3. 🧩 Desglose transparente por componentes")
        fig_componentes = go.Figure()
        colores_componentes = [
            "#22C55E" if valor >= 80 else
            "#38BDF8" if valor >= 60 else
            "#FACC15" if valor >= 40 else
            "#EF4444"
            for valor in componentes_df["Puntaje %"]
        ]
        fig_componentes.add_trace(
            go.Bar(
                x=componentes_df["Puntaje %"],
                y=componentes_df["Icono"] + " " + componentes_df["Indicador"],
                orientation="h",
                marker=dict(
                    color=colores_componentes,
                    line=dict(color="#F8FAFC", width=1.0),
                ),
                text=componentes_df["Puntaje %"],
                texttemplate="%{text:.1f}/100",
                textposition="outside",
                customdata=componentes_df[
                    ["Puntos", "Máximo", "Base", "Estado", "Contribución % del score"]
                ],
                hovertemplate=(
                    "<b>🧩 %{y}</b><br>"
                    "🏆 Cumplimiento: %{x:.1f}/100<br>"
                    "📌 Puntos aportados: %{customdata[0]:.1f} de %{customdata[1]:.0f}<br>"
                    "🧾 Base de cálculo: %{customdata[2]}<br>"
                    "🚦 Estado: %{customdata[3]}<br>"
                    "📊 Participación en el score: %{customdata[4]:.1f}%"
                    "<extra></extra>"
                ),
            )
        )
        fig_componentes.add_vline(
            x=80,
            line_dash="dot",
            line_color="#FDE047",
            annotation_text="🎯 Referencia 80/100",
            annotation_position="top",
        )
        fig_componentes.update_layout(
            template="plotly_dark",
            height=430,
            paper_bgcolor="#000000",
            plot_bgcolor="#000000",
            xaxis=dict(title="Cumplimiento (0–100)", range=[0, 105]),
            yaxis=dict(title="", autorange="reversed"),
            showlegend=False,
            margin=dict(t=55, b=45, l=30, r=55),
        )
        st.plotly_chart(fig_componentes, use_container_width=True)

        with st.expander("📋 Ver fórmula y tabla completa del score"):
            tabla_score = componentes_df[
                [
                    "Icono",
                    "Indicador",
                    "Puntos",
                    "Máximo",
                    "Puntaje %",
                    "Estado",
                    "Base",
                    "Contribución % del score",
                ]
            ].copy()
            tabla_score["Puntaje %"] = tabla_score["Puntaje %"].map(
                lambda valor: f"{valor:.1f}%"
            )
            tabla_score["Contribución % del score"] = tabla_score[
                "Contribución % del score"
            ].map(lambda valor: f"{valor:.1f}%")
            st.dataframe(tabla_score, use_container_width=True, hide_index=True)

        # ======================================================
        # 5. WATERFALL DE CONTRIBUCIÓN
        # ======================================================
        st.markdown("### 4. 🌊 ¿Qué construye el score?")
        fig_waterfall_score = go.Figure(
            go.Waterfall(
                orientation="v",
                measure=["relative"] * len(componentes_df) + ["total"],
                x=(
                    componentes_df["Icono"] + " " + componentes_df["Indicador"]
                ).tolist() + ["🏆 Score final"],
                y=componentes_df["Puntos"].tolist() + [score_total],
                text=[
                    f"+{valor:.1f}" for valor in componentes_df["Puntos"]
                ] + [f"{score_total:.1f}/100"],
                textposition="outside",
                connector={"line": {"color": "rgba(226,232,240,0.45)"}},
                increasing={"marker": {"color": "#22C55E"}},
                totals={"marker": {"color": "#00E5FF"}},
                customdata=componentes_df[
                    ["Máximo", "Puntaje %", "Base"]
                ].values.tolist() + [[100, score_total, "Suma de los componentes"]],
                hovertemplate=(
                    "<b>📊 %{x}</b><br>"
                    "🏆 Aporte: %{y:.1f} puntos<br>"
                    "🎯 Máximo: %{customdata[0]:.0f} puntos<br>"
                    "📈 Cumplimiento: %{customdata[1]:.1f}/100<br>"
                    "🧾 Base: %{customdata[2]}"
                    "<extra></extra>"
                ),
            )
        )
        fig_waterfall_score.update_layout(
            template="plotly_dark",
            height=470,
            paper_bgcolor="#000000",
            plot_bgcolor="#000000",
            yaxis=dict(title="Puntos del score", range=[0, 110]),
            margin=dict(t=45, b=95, l=55, r=30),
            xaxis_tickangle=-25,
        )
        st.plotly_chart(fig_waterfall_score, use_container_width=True)

        # ======================================================
        # 6. EVOLUCIÓN HISTÓRICA DEL SCORE
        # ======================================================
        st.markdown("### 5. 📅 Evolución histórica del score")
        flujo_score_hist = construir_flujo_mensual(
            gastos_df=df,
            ingresos_df=ingresos_filtrados,
            meses_sel=meses_sel,
            presupuesto_mensual=presupuesto_mensual_por_periodo or presupuesto_mensual_general,
        )

        historial_score_rows = []
        if not flujo_score_hist.empty:
            for _, fila_mes in flujo_score_hist.iterrows():
                mes_nombre = fila_mes["MES"]
                gastos_mes_df = df[
                    df["MES"].astype(str).str.upper().eq(str(mes_nombre).upper())
                ].copy()
                gasto_mes = float(fila_mes.get("Gastos", 0.0))
                ingreso_mes = float(fila_mes.get("Ingresos", 0.0))
                presupuesto_mes = float(fila_mes.get("Presupuesto mensual", 0.0))
                comps_mes, _ = _calcular_componentes_score(
                    gastos_valor=gasto_mes,
                    ingresos_valor=ingreso_mes,
                    presupuesto_valor=presupuesto_mes,
                    activos_valor=total_activos_score,
                    pasivos_valor=total_pasivos_score,
                    fondo_valor=fondo_emergencia_valor,
                    gasto_mensual_valor=gasto_mes,
                    metas_df=metas,
                    gastos_df=gastos_mes_df,
                )
                historial_score_rows.append(
                    {
                        "MES": mes_nombre,
                        "Score": round(sum(c["Puntos"] for c in comps_mes), 1),
                        "Ingresos": ingreso_mes,
                        "Gastos": gasto_mes,
                        "Balance": ingreso_mes - gasto_mes,
                    }
                )

        historial_score = pd.DataFrame(historial_score_rows)
        if not historial_score.empty:
            historial_score["Cambio"] = historial_score["Score"].diff().fillna(0.0)
            fig_hist_score = go.Figure()
            fig_hist_score.add_trace(
                go.Scatter(
                    x=historial_score["MES"],
                    y=historial_score["Score"],
                    mode="lines+markers+text",
                    line=dict(color="#00E5FF", width=4, shape="spline"),
                    marker=dict(
                        size=11,
                        color=historial_score["Score"],
                        colorscale=[
                            [0.0, "#EF4444"],
                            [0.5, "#FACC15"],
                            [0.7, "#38BDF8"],
                            [1.0, "#22C55E"],
                        ],
                        cmin=0,
                        cmax=100,
                        line=dict(color="#F8FAFC", width=1.2),
                    ),
                    text=historial_score["Score"],
                    texttemplate="%{text:.1f}",
                    textposition="top center",
                    customdata=historial_score[
                        ["Cambio", "Ingresos", "Gastos", "Balance"]
                    ],
                    hovertemplate=(
                        "<b>📅 Mes: %{x}</b><br>"
                        "🏆 Score: %{y:.1f}/100<br>"
                        "🔄 Cambio mensual: %{customdata[0]:+.1f} puntos<br>"
                        "💰 Ingresos: $%{customdata[1]:,.0f}<br>"
                        "🧾 Gastos: $%{customdata[2]:,.0f}<br>"
                        "⚖️ Balance: $%{customdata[3]:,.0f}"
                        "<extra></extra>"
                    ),
                )
            )
            fig_hist_score.add_hrect(
                y0=70,
                y1=100,
                fillcolor="rgba(34,197,94,0.08)",
                line_width=0,
            )
            fig_hist_score.add_hline(
                y=70,
                line_dash="dot",
                line_color="#38BDF8",
                annotation_text="🔵 Nivel bueno",
            )
            fig_hist_score.update_layout(
                template="plotly_dark",
                height=430,
                paper_bgcolor="#000000",
                plot_bgcolor="#000000",
                xaxis=dict(title="Mes", categoryorder="array", categoryarray=MESES_ORDEN),
                yaxis=dict(title="Score (0–100)", range=[0, 105]),
                margin=dict(t=55, b=45, l=55, r=35),
                showlegend=False,
            )
            st.plotly_chart(fig_hist_score, use_container_width=True)

            mejor_mes_score = historial_score.loc[historial_score["Score"].idxmax()]
            peor_mes_score = historial_score.loc[historial_score["Score"].idxmin()]
            ultimo_cambio_score = float(historial_score.iloc[-1]["Cambio"])
            eh1, eh2, eh3 = st.columns(3)
            eh1.metric(
                "🏅 Mejor mes",
                str(mejor_mes_score["MES"]),
                f"{mejor_mes_score['Score']:.1f}/100",
            )
            eh2.metric(
                "⚠️ Mes más débil",
                str(peor_mes_score["MES"]),
                f"{peor_mes_score['Score']:.1f}/100",
            )
            eh3.metric(
                "🔄 Último cambio",
                f"{ultimo_cambio_score:+.1f} puntos",
                "Mejora" if ultimo_cambio_score > 0 else "Deterioro" if ultimo_cambio_score < 0 else "Sin cambio",
            )
        else:
            st.info("ℹ️ No hay suficiente historial mensual para construir la evolución del score.")

        # ======================================================
        # 7. CONFIABILIDAD DEL SCORE
        # ======================================================
        st.markdown("### 6. 🔍 Confiabilidad del score")
        controles_calidad = [
            ("Presupuesto definido", presupuesto_total_score > 0, 20),
            ("Ingresos disponibles", not ingresos_filtrados.empty and total_ingresos > 0, 20),
            ("Patrimonio disponible", not patrimonio.empty and total_activos_score > 0, 20),
            ("Metas disponibles", isinstance(metas, pd.DataFrame) and not metas.empty, 15),
            ("Historial suficiente", periodos_score >= 3, 15),
            ("Fondo identificado", fondo_emergencia_valor > 0, 10),
        ]
        confianza_score = sum(peso for _, cumple, peso in controles_calidad if cumple)
        nivel_confianza = (
            "Alta" if confianza_score >= 80
            else "Media" if confianza_score >= 60
            else "Baja"
        )
        conf1, conf2 = st.columns([1, 2])
        with conf1:
            st.metric(
                "🔍 Confiabilidad",
                f"{confianza_score:.0f}%",
                nivel_confianza,
            )
            st.progress(confianza_score / 100)
        with conf2:
            for nombre_control, cumple, peso in controles_calidad:
                simbolo = "✅" if cumple else "⚠️"
                st.write(
                    f"{simbolo} **{nombre_control}** — "
                    f"{'Disponible' if cumple else 'Falta o es insuficiente'} "
                    f"({peso} puntos de confiabilidad)."
                )

        # ======================================================
        # 8. ALERTAS Y PLAN DE MEJORA PRIORIZADO
        # ======================================================
        st.markdown("### 7. 🚦 Alertas prioritarias y plan de mejora")
        acciones = []

        if ratio_presupuesto > 100:
            acciones.append(
                {
                    "Prioridad": 1,
                    "Icono": "🎯",
                    "Acción": "Reducir el exceso presupuestal",
                    "Diagnóstico": f"Ejecución actual: {ratio_presupuesto:.1f}%.",
                    "Impacto": max(25 - componentes_df.loc[componentes_df["Indicador"].eq("Presupuesto"), "Puntos"].iloc[0], 0),
                }
            )
        if pct_ahorro < 20:
            acciones.append(
                {
                    "Prioridad": 1,
                    "Icono": "💰",
                    "Acción": "Aumentar la capacidad de ahorro",
                    "Diagnóstico": f"Ahorro actual: {pct_ahorro:.1f}% de los ingresos.",
                    "Impacto": max(20 - componentes_df.loc[componentes_df["Indicador"].eq("Ahorro"), "Puntos"].iloc[0], 0),
                }
            )
        if pct_endeuda > 35:
            acciones.append(
                {
                    "Prioridad": 1,
                    "Icono": "💳",
                    "Acción": "Reducir el peso de los pasivos",
                    "Diagnóstico": f"Pasivos / activos: {pct_endeuda:.1f}%.",
                    "Impacto": max(20 - componentes_df.loc[componentes_df["Indicador"].eq("Endeudamiento"), "Puntos"].iloc[0], 0),
                }
            )
        if avance_fondo_emergencia < 100:
            acciones.append(
                {
                    "Prioridad": 2,
                    "Icono": "🛡️",
                    "Acción": "Completar el fondo de emergencia",
                    "Diagnóstico": (
                        f"Avance: {avance_fondo_emergencia:.1f}%; "
                        f"faltan ${faltante_fondo_emergencia:,.0f}."
                    ),
                    "Impacto": max(15 - componentes_df.loc[componentes_df["Indicador"].eq("Fondo emergencia"), "Puntos"].iloc[0], 0),
                }
            )
        if avance_metas < 70:
            acciones.append(
                {
                    "Prioridad": 2,
                    "Icono": "🏁",
                    "Acción": "Acelerar las metas financieras",
                    "Diagnóstico": f"Cumplimiento promedio: {avance_metas:.1f}%.",
                    "Impacto": max(10 - componentes_df.loc[componentes_df["Indicador"].eq("Metas"), "Puntos"].iloc[0], 0),
                }
            )
        if pct_innecesarios > 10:
            acciones.append(
                {
                    "Prioridad": 3,
                    "Icono": "🛒",
                    "Acción": "Revisar gastos prescindibles",
                    "Diagnóstico": (
                        f"{pct_innecesarios:.1f}% de los gastos; "
                        f"${monto_innecesarios:,.0f} detectados."
                    ),
                    "Impacto": max(10 - componentes_df.loc[componentes_df["Indicador"].eq("Gastos innecesarios"), "Puntos"].iloc[0], 0),
                }
            )

        if acciones:
            acciones_df = pd.DataFrame(acciones).sort_values(
                ["Prioridad", "Impacto"], ascending=[True, False]
            )
            for _, accion in acciones_df.iterrows():
                tipo_mensaje = st.error if accion["Prioridad"] == 1 else st.warning if accion["Prioridad"] == 2 else st.info
                tipo_mensaje(
                    f"{accion['Icono']} **{accion['Acción']}** — "
                    f"{accion['Diagnóstico']} "
                    f"Impacto máximo orientativo: **+{accion['Impacto']:.1f} puntos**."
                )
        else:
            st.success("✅ No se identificaron acciones críticas con los filtros actuales.")

        # ======================================================
        # 9. SIMULADOR DEL SCORE
        # ======================================================
        st.markdown("### 8. 🧪 Simulador de mejora")
        st.caption(
            "El simulador reutiliza la misma fórmula del score. No modifica los datos del Excel."
        )
        sim1, sim2, sim3 = st.columns(3)
        with sim1:
            reduccion_gastos_pct = st.slider(
                "🧾 Reducir gastos",
                min_value=0,
                max_value=40,
                value=0,
                step=1,
                format="%d%%",
                key="score_sim_reduccion_gastos",
            )
        with sim2:
            pago_pasivos_pct = st.slider(
                "💳 Reducir pasivos",
                min_value=0,
                max_value=40,
                value=0,
                step=1,
                format="%d%%",
                key="score_sim_reduccion_pasivos",
            )
        with sim3:
            aporte_fondo = st.number_input(
                "🛡️ Aporte al fondo",
                min_value=0.0,
                value=0.0,
                step=100000.0,
                format="%.0f",
                key="score_sim_aporte_fondo",
            )

        gastos_simulados = float(total_gastos) * (1 - reduccion_gastos_pct / 100)
        pasivos_simulados = total_pasivos_score * (1 - pago_pasivos_pct / 100)
        fondo_simulado = fondo_emergencia_valor + float(aporte_fondo)
        gasto_mensual_simulado = gastos_simulados / periodos_score if periodos_score else gastos_simulados

        componentes_sim, _ = _calcular_componentes_score(
            gastos_valor=gastos_simulados,
            ingresos_valor=float(total_ingresos),
            presupuesto_valor=presupuesto_total_score,
            activos_valor=total_activos_score,
            pasivos_valor=pasivos_simulados,
            fondo_valor=fondo_simulado,
            gasto_mensual_valor=gasto_mensual_simulado,
            metas_df=metas,
            gastos_df=df.assign(
                GASTOS_CANTIDAD=df["GASTOS_CANTIDAD"] * (1 - reduccion_gastos_pct / 100)
            ) if not df.empty else df,
        )
        score_simulado = round(sum(c["Puntos"] for c in componentes_sim), 1)
        cambio_simulado = score_simulado - score_total
        nivel_simulado, icono_simulado = _nivel_score(score_simulado)

        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("🏆 Score actual", f"{score_total:.1f}/100")
        sm2.metric(
            "🧪 Score simulado",
            f"{score_simulado:.1f}/100",
            f"{cambio_simulado:+.1f} puntos",
        )
        sm3.metric("🚦 Estado simulado", f"{icono_simulado} {nivel_simulado}")
        sm4.metric(
            "💰 Balance simulado",
            f"${float(total_ingresos) - gastos_simulados:,.0f}",
        )

        comparacion_sim = pd.DataFrame(
            {
                "Escenario": ["Actual", "Simulado"],
                "Score": [score_total, score_simulado],
            }
        )
        fig_sim = px.bar(
            comparacion_sim,
            x="Escenario",
            y="Score",
            text="Score",
            color="Escenario",
            color_discrete_map={
                "Actual": "#38BDF8",
                "Simulado": "#22C55E" if cambio_simulado >= 0 else "#EF4444",
            },
        )
        fig_sim.update_traces(
            texttemplate="%{text:.1f}/100",
            textposition="outside",
            hovertemplate=(
                "<b>🧪 %{x}</b><br>"
                "🏆 Score: %{y:.1f}/100"
                "<extra></extra>"
            ),
        )
        fig_sim.update_layout(
            template="plotly_dark",
            height=340,
            paper_bgcolor="#000000",
            plot_bgcolor="#000000",
            yaxis=dict(title="Score", range=[0, 105]),
            showlegend=False,
            margin=dict(t=40, b=35, l=45, r=30),
        )
        st.plotly_chart(fig_sim, use_container_width=True)

        # ======================================================
        # 10. FONDO DE EMERGENCIA
        # ======================================================
        st.divider()
        st.markdown("### 9. 🛡️ Fondo de emergencia")
        estado_fondo = estado_meta(avance_fondo_emergencia)

        fe1, fe2, fe3, fe4, fe5 = st.columns(5)
        fe1.metric("💰 Fondo actual", f"${fondo_emergencia_valor:,.0f}")
        fe2.metric("🎯 Meta 3 meses", f"${meta_fondo_emergencia:,.0f}")
        fe3.metric("📊 Cumplimiento", f"{avance_fondo_emergencia:.1f}%", estado_fondo)
        fe4.metric(
            "📅 Días cubiertos",
            f"{dias_cubiertos_fondo:,.0f} días",
            f"Gasto diario ${gasto_promedio_diario_fondo:,.0f}",
        )
        fe5.metric(
            "⚠️ Faltante",
            f"${faltante_fondo_emergencia:,.0f}",
            f"{meses_emergencia:.1f} meses cubiertos",
        )

        st.progress(avance_fondo_emergencia_limitado / 100)
        fig_fondo = fig_progreso_meta(
            "Fondo de emergencia",
            fondo_emergencia_valor,
            meta_fondo_emergencia,
            faltante_fondo_emergencia,
            texto_meta="Meta 3 meses",
        )
        fig_fondo.update_layout(height=260)
        st.plotly_chart(fig_fondo, use_container_width=True)

        # ======================================================
        # 11. METAS FINANCIERAS: CUMPLIMIENTO 0–100
        # ======================================================
        st.divider()
        st.markdown("### 10. 🏁 Metas financieras")
        st.caption(
            "El porcentaje de cumplimiento se muestra siempre en una escala de 0 a 100."
        )

        if metas.empty:
            st.info(
                "ℹ️ No se encontró la hoja **Metas** o está vacía. "
                "Agrega Meta, Objetivo y Actual para evaluar el cumplimiento."
            )
        else:
            for _, meta_row in metas.iterrows():
                nombre_meta = (
                    str(meta_row["Meta"]).strip()
                    if pd.notna(meta_row["Meta"]) and str(meta_row["Meta"]).strip()
                    else "Meta sin nombre"
                )
                objetivo_meta = float(meta_row["Objetivo"])
                actual_meta = float(meta_row["Actual"])

                avance_original = meta_row.get("Avance", 0.0)
                avance_meta_pct = _pct_0_100(avance_original)
                if objetivo_meta > 0:
                    avance_calculado = _pct_0_100(actual_meta / objetivo_meta)
                    # Se prioriza el cálculo directo cuando la columna Avance está vacía
                    # o no coincide razonablemente con Objetivo y Actual.
                    if (
                        pd.isna(avance_original)
                        or abs(avance_meta_pct - avance_calculado) > 1.0
                    ):
                        avance_meta_pct = avance_calculado

                avance_meta_limitado = min(max(avance_meta_pct, 0), 100)
                faltante_meta = max(objetivo_meta - actual_meta, 0)
                estado_meta_actual = estado_meta(avance_meta_pct)

                st.markdown(f"#### 🎯 {nombre_meta}")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("💰 Valor actual", f"${actual_meta:,.0f}")
                m2.metric("🏁 Valor objetivo", f"${objetivo_meta:,.0f}")
                m3.metric(
                    "📊 Porcentaje de cumplimiento",
                    f"{avance_meta_pct:.1f}%",
                    estado_meta_actual,
                )
                m4.metric("⚠️ Faltante", f"${faltante_meta:,.0f}")

                st.progress(avance_meta_limitado / 100)
                fig_meta = fig_progreso_meta(
                    nombre_meta,
                    actual_meta,
                    objetivo_meta,
                    faltante_meta,
                )
                fig_meta.update_traces(
                    hovertemplate=(
                        f"<b>🎯 Meta: {nombre_meta}</b><br>"
                        "💰 Valor actual: $%{x:,.0f}<br>"
                        f"🏁 Objetivo: ${objetivo_meta:,.0f}<br>"
                        f"📊 Cumplimiento: {avance_meta_pct:.1f}%<br>"
                        f"⚠️ Faltante: ${faltante_meta:,.0f}"
                        "<extra></extra>"
                    )
                )
                st.plotly_chart(fig_meta, use_container_width=True)
                st.divider()

        if not df_innecesarios.empty:
            with st.expander("🛒 Ver gastos detectados como prescindibles"):
                st.caption(
                    "La detección usa palabras clave en categoría, subcategoría, "
                    "descripción y observación."
                )
                columnas_innecesarios = [
                    columna
                    for columna in [
                        "MES",
                        "GASTOS_FECHA",
                        "GASTOS_CANTIDAD",
                        "GASTOS_DESCRIPCION",
                        "GASTOS_CATEGORIA",
                        "GASTOS_SUBCATEGORIA",
                        "GASTOS_OBSERVACION",
                    ]
                    if columna in df_innecesarios.columns
                ]
                st.dataframe(
                    df_innecesarios[columnas_innecesarios].sort_values(
                        "GASTOS_CANTIDAD", ascending=False
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

    if pestana_activa == etiquetas_pestanas[8]:
        contexto_pestana(
            "¿Mi dinero está alineado con mi bienestar?",
            "Relaciona ingresos, tiempo, eficiencia laboral, diversificación y patrimonio. Es una lectura financiera del bienestar laboral; no mide satisfacción psicológica.",
        )
        st.markdown("## Trabajo, tiempo y bienestar financiero")
        st.caption(
            "Esta pestaña usa los trabajos registrados en **Transaccional K:Q**: fecha, valor, empresa, mes, categoría, horas y valor hora. "
            "Todos los resultados respetan los filtros globales Desde/Hasta."
        )

        if felicidad_trabajos_filtrados.empty:
            st.info(
                "No hay trabajos registrados en las columnas K:Q para el rango seleccionado. "
                "Cambia el filtro Desde/Hasta o registra nuevos trabajos."
            )
        else:
            trabajos_validos = felicidad_trabajos_filtrados.copy()
            trabajos_validos["FECHA"] = pd.to_datetime(trabajos_validos["FECHA"], errors="coerce")
            trabajos_validos["VALOR"] = pd.to_numeric(trabajos_validos["VALOR"], errors="coerce").fillna(0)
            trabajos_validos["HORAS"] = pd.to_numeric(trabajos_validos["HORAS"], errors="coerce").fillna(0).clip(lower=0)
            trabajos_validos["VALOR_HORA"] = pd.to_numeric(trabajos_validos["VALOR_HORA"], errors="coerce").fillna(0)

            total_valor_trabajos = float(trabajos_validos["VALOR"].sum())
            total_horas_trabajadas = float(trabajos_validos["HORAS"].sum())
            valor_hora_promedio = total_valor_trabajos / total_horas_trabajadas if total_horas_trabajadas > 0 else float(trabajos_validos["VALOR_HORA"].mean() or 0)
            empresas_activas = int(trabajos_validos["EMPRESA"].fillna("Sin empresa").nunique())
            dias_actividad = int(trabajos_validos["FECHA"].dropna().dt.date.nunique())
            ingreso_dia_activo = total_valor_trabajos / dias_actividad if dias_actividad else 0.0

            ingresos_felicidad_base = trabajos_validos.rename(columns={"VALOR": "INGRESOS_CANTIDAD", "CATEGORIA": "INGRESOS_CATEGORIA"}).copy()
            ingresos_felicidad = resumen_ingresos_laborales_no_laborales(ingresos_felicidad_base)
            ingreso_laboral = float(ingresos_felicidad["Laborales"].sum()) if not ingresos_felicidad.empty else 0.0
            ingreso_no_laboral = float(ingresos_felicidad["No laborales"].sum()) if not ingresos_felicidad.empty else 0.0
            ingreso_sin_clasificar = float(ingresos_felicidad["Sin clasificar"].sum()) if not ingresos_felicidad.empty and "Sin clasificar" in ingresos_felicidad.columns else 0.0
            participacion_no_laboral = ingreso_no_laboral / total_valor_trabajos * 100 if total_valor_trabajos else 0.0

            fecha_min_f = trabajos_validos["FECHA"].min()
            fecha_max_f = trabajos_validos["FECHA"].max()
            if pd.notna(fecha_min_f) and pd.notna(fecha_max_f):
                meses_periodo_completo = max((fecha_max_f.year - fecha_min_f.year) * 12 + fecha_max_f.month - fecha_min_f.month + 1, 1)
            else:
                meses_periodo_completo = 1
            meses_activos = max(int(trabajos_validos["FECHA"].dropna().dt.to_period("M").nunique()), 1)
            promedio_laboral_mensual = ingreso_laboral / meses_periodo_completo
            promedio_no_laboral_mensual = ingreso_no_laboral / meses_periodo_completo
            promedio_total_mensual = total_valor_trabajos / meses_periodo_completo

            resumen_empresas = resumen_felicidad_por_empresa(trabajos_validos)
            principal_ingreso = resumen_empresas.sort_values("PART_INGRESOS", ascending=False).iloc[0] if not resumen_empresas.empty else None
            principal_horas = resumen_empresas.sort_values("PART_HORAS", ascending=False).iloc[0] if not resumen_empresas.empty else None
            mas_eficiente = resumen_empresas.sort_values("VALOR_HORA", ascending=False).iloc[0] if not resumen_empresas.empty else None
            menos_eficiente = resumen_empresas[resumen_empresas["HORAS"].gt(0)].sort_values("VALOR_HORA").iloc[0] if not resumen_empresas[resumen_empresas["HORAS"].gt(0)].empty else None

            seccion_resumen("1", "Panorama del periodo", "Cuánto dinero se generó, cuánto tiempo requirió y cuántas fuentes participaron.")
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Ingresos registrados", f"${total_valor_trabajos:,.0f}")
            k2.metric("Horas trabajadas", f"{total_horas_trabajadas:,.1f} h")
            k3.metric("Valor promedio por hora", f"${valor_hora_promedio:,.0f}")
            k4.metric("Empresas activas", empresas_activas)
            k5.metric("Meses analizados", meses_periodo_completo, help=f"{meses_activos} meses contienen registros.")

            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Ingreso laboral", f"${ingreso_laboral:,.0f}")
            p2.metric("Ingreso no laboral", f"${ingreso_no_laboral:,.0f}", delta=f"{participacion_no_laboral:.1f}% del total")
            p3.metric("Promedio mensual del periodo", f"${promedio_total_mensual:,.0f}")
            p4.metric("Ingreso por día activo", f"${ingreso_dia_activo:,.0f}", help="Ingreso total dividido entre fechas distintas con actividad registrada.")

            seccion_resumen("2", "Eficiencia del tiempo", "Compara remuneración, carga laboral y aporte económico de cada empresa.")
            e1, e2 = st.columns(2)
            with e1:
                st.plotly_chart(fig_felicidad_valor_hora_por_empresa(trabajos_validos), use_container_width=True)
            with e2:
                st.plotly_chart(fig_felicidad_matriz_eficiencia(resumen_empresas), use_container_width=True)

            e3, e4 = st.columns(2)
            with e3:
                st.plotly_chart(fig_felicidad_ingresos_horas_mes(trabajos_validos), use_container_width=True)
            with e4:
                st.plotly_chart(fig_felicidad_concentracion_empresa(resumen_empresas), use_container_width=True)

            st.plotly_chart(fig_felicidad_valor_hora_por_mes(trabajos_validos), use_container_width=True)

            st.markdown("#### Ranking ejecutivo de trabajos")
            ranking = resumen_empresas.copy()
            if not ranking.empty:
                ranking["LECTURA"] = ranking["EFICIENCIA_RELATIVA"].map(lambda x: "Favorable" if x >= 1.15 else "Equilibrada" if x >= 0.85 else "Revisar")
                ranking_mostrar = ranking.rename(columns={
                    "EMPRESA": "Empresa", "INGRESOS": "Ingresos", "HORAS": "Horas", "VALOR_HORA": "Valor/hora",
                    "PART_INGRESOS": "% ingresos", "PART_HORAS": "% horas", "EFICIENCIA_RELATIVA": "Eficiencia relativa",
                    "BRECHA_PARTICIPACION": "Brecha ingresos-horas", "LECTURA": "Lectura",
                })
                st.dataframe(
                    ranking_mostrar.style.format({"Ingresos": "${:,.0f}", "Horas": "{:,.1f}", "Valor/hora": "${:,.0f}", "% ingresos": "{:.1f}%", "% horas": "{:.1f}%", "Eficiencia relativa": "{:.2f}x", "Brecha ingresos-horas": "{:+.1f} pp"}),
                    use_container_width=True, hide_index=True,
                )
                st.caption("Eficiencia relativa = participación en ingresos ÷ participación en horas. Es una comparación interna entre los trabajos registrados, no una evaluación de satisfacción personal.")

            seccion_resumen("3", "Diversificación y estabilidad", "Mide dependencia de las fuentes y composición laboral/no laboral.")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Fuente principal", str(principal_ingreso["EMPRESA"]) if principal_ingreso is not None else "Sin dato")
            d2.metric("Concentración principal", f"{float(principal_ingreso['PART_INGRESOS']):.1f}%" if principal_ingreso is not None else "0%")
            d3.metric("Mayor concentración de tiempo", str(principal_horas["EMPRESA"]) if principal_horas is not None else "Sin dato", delta=f"{float(principal_horas['PART_HORAS']):.1f}% de horas" if principal_horas is not None else None)
            d4.metric("Sin clasificar", f"${ingreso_sin_clasificar:,.0f}", help="Ingresos cuya categoría no permite determinar si son laborales o no laborales.")
            st.plotly_chart(fig_felicidad_ingresos_laborales_vs_no_laborales(ingresos_felicidad_base), use_container_width=True)

            seccion_resumen("4", "Simulador de decisión laboral", "Explora cambios de horas y tarifa sin modificar los datos del archivo.")
            if not resumen_empresas.empty:
                empresa_sim = st.selectbox("Empresa o trabajo para simular", resumen_empresas["EMPRESA"].tolist(), key="felicidad_empresa_sim_v920")
                fila_sim = resumen_empresas.loc[resumen_empresas["EMPRESA"].eq(empresa_sim)].iloc[0]
                s1, s2 = st.columns(2)
                horas_sim = s1.number_input("Horas simuladas", min_value=0.0, value=float(fila_sim["HORAS"]), step=1.0, key="felicidad_horas_sim_v920")
                tarifa_sim = s2.number_input("Valor por hora simulado", min_value=0.0, value=float(fila_sim["VALOR_HORA"]), step=1000.0, key="felicidad_tarifa_sim_v920")
                ingreso_actual_sim = float(fila_sim["INGRESOS"])
                ingreso_simulado = horas_sim * tarifa_sim
                horas_liberadas = float(fila_sim["HORAS"]) - horas_sim
                diferencia_ingreso = ingreso_simulado - ingreso_actual_sim
                tarifa_equilibrio = ingreso_actual_sim / horas_sim if horas_sim > 0 else 0.0
                s3, s4, s5, s6 = st.columns(4)
                s3.metric("Ingreso actual", f"${ingreso_actual_sim:,.0f}")
                s4.metric("Ingreso simulado", f"${ingreso_simulado:,.0f}", delta=f"${diferencia_ingreso:,.0f}")
                s5.metric("Horas liberadas", f"{horas_liberadas:,.1f} h")
                s6.metric("Tarifa para conservar ingreso", f"${tarifa_equilibrio:,.0f}/h" if horas_sim > 0 else "No aplica")

            seccion_resumen("5", "Patrimonio e IDR", "Conserva el análisis existente y muestra la relación entre patrimonio actual e ingreso de referencia.")
            if "idr_incluir_no_laborales" not in st.session_state:
                st.session_state["idr_incluir_no_laborales"] = True
            incluir_no_laborales_idr = bool(st.session_state.get("idr_incluir_no_laborales", True))
            ingresos_totales_idr = ingreso_laboral + (ingreso_no_laboral if incluir_no_laborales_idr else 0.0)
            texto_fuentes_idr = "laborales y no laborales" if incluir_no_laborales_idr else "laborales"
            sueldo_promedio_mensual = ingresos_totales_idr / meses_periodo_completo if meses_periodo_completo > 0 else 0.0
            try:
                edad_para_idr = float(edad_persona) if edad_persona is not None else 0.0
            except (TypeError, ValueError):
                edad_para_idr = 0.0
            idr = sueldo_promedio_mensual * edad_para_idr * 1.2
            patrimonio_neto_idr = float(patrimonio["Valor neto"].sum()) if not patrimonio.empty else 0.0
            ratio_idr = patrimonio_neto_idr / idr if idr > 0 else 0.0
            nivel_idr = max(0.0, min(float(ratio_idr), 3.0))

            if ratio_idr >= 2:
                resultado_riqueza, color_medidor = "Patrimonio por encima de la referencia", "#22C55E"
                popup_riqueza = "El patrimonio es dos veces o más la referencia IDR calculada con los datos disponibles."
            elif ratio_idr > 0.55:
                resultado_riqueza, color_medidor = "Dentro del rango de referencia", "#FACC15"
                popup_riqueza = "El patrimonio se encuentra dentro del rango intermedio frente a la referencia IDR."
            else:
                resultado_riqueza, color_medidor = "Patrimonio por debajo de la referencia", "#EF4444"
                popup_riqueza = "El patrimonio está por debajo del 55% de la referencia IDR. El indicador es orientativo y no reemplaza un diagnóstico completo."
            popup_idr = "El IDR es una referencia orientativa basada en ingreso mensual, edad y el factor 1.2; no incorpora todas las circunstancias financieras personales."

            fig_medidor_idr = go.Figure(go.Indicator(
                mode="gauge+number", value=nivel_idr,
                number={"valueformat": ".2f", "font": {"color": "#f8fafc", "size": 38}},
                title={"text": "Medidor IDR", "font": {"color": "#e2e8f0", "size": 18}},
                gauge={"axis": {"range": [0, 3], "tickvals": [0, .55, 1, 2, 3]}, "bar": {"color": color_medidor, "thickness": .28},
                       "bgcolor": "#0a0a0a", "borderwidth": 1, "bordercolor": "#00D9FF",
                       "steps": [{"range": [0, .55], "color": "rgba(239,68,68,.35)"}, {"range": [.55, 2], "color": "rgba(250,204,21,.35)"}, {"range": [2, 3], "color": "rgba(34,197,94,.35)"}],
                       "threshold": {"line": {"color": "#fff", "width": 3}, "thickness": .8, "value": nivel_idr}},
            ))
            fig_medidor_idr.update_layout(template="plotly_dark", height=330, margin=dict(t=55,b=20,l=25,r=25), paper_bgcolor="#000", plot_bgcolor="#000", font=dict(color="#e2e8f0"))

            idr_panel, medidor_panel = st.columns([1, 1.25], gap="large")
            with idr_panel:
                promedio_col1, promedio_col2 = st.columns(2)
                promedio_col1.metric("Promedio laboral mensual", f"${promedio_laboral_mensual:,.0f}")
                promedio_col2.metric("Promedio no laboral mensual", f"${promedio_no_laboral_mensual:,.0f}")
                st.metric("IDR", f"${idr:,.0f}", help=popup_idr + f" Fórmula: promedio mensual de ingresos {texto_fuentes_idr} × edad × 1.2.")
                st.markdown(f'''<div title="{popup_riqueza}" style="background:#0a0a0a;border:1px solid rgba(0,240,255,.40);border-radius:14px;padding:.75rem 1rem;margin-bottom:.75rem"><div style="color:#bfdbfe;font-size:.86rem;font-weight:700">Resultado generación de riqueza</div><div style="color:{color_medidor};font-size:1.25rem;font-weight:900">{resultado_riqueza}</div><div style="color:#94a3b8;font-size:.82rem">Patrimonio / IDR: {ratio_idr:.2f}x</div></div>''', unsafe_allow_html=True)
                st.markdown(f'''<div style="background:#0a0a0a;border:1px solid rgba(0,240,255,.40);border-radius:14px;padding:.75rem 1rem;margin-bottom:.75rem"><div style="color:#bfdbfe;font-size:.86rem;font-weight:700">Medidor IDR (1 a 3)</div><div style="color:{color_medidor};font-size:1.35rem;font-weight:900">{nivel_idr:.2f}</div></div>''', unsafe_allow_html=True)
            with medidor_panel:
                st.markdown("<div style='text-align:center;color:#cbd5e1;font-weight:700'>Patrimonio neto / IDR</div>", unsafe_allow_html=True)
                st.markdown('<div class="checkbox-center">', unsafe_allow_html=True)
                st.checkbox("Incluir ingresos no laborales", key="idr_incluir_no_laborales", help="Cambia la base del IDR entre ingresos laborales y el total laboral + no laboral.")
                st.markdown('</div>', unsafe_allow_html=True)
                st.plotly_chart(fig_medidor_idr, use_container_width=True)

            cumplimiento_idr_pct = patrimonio_neto_idr / idr * 100 if idr > 0 else 0.0
            cumplimiento_barra = max(0.0, min(cumplimiento_idr_pct, 300.0))
            color_cumplimiento = "#22C55E" if cumplimiento_idr_pct >= 200 else "#FACC15" if cumplimiento_idr_pct > 55 else "#EF4444"
            st.markdown(f'''<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:.6rem 0 1.2rem"><div style="background:#0a0a0a;border:1px solid rgba(0,240,255,.45);border-radius:16px;padding:15px 17px"><div style="color:#bfdbfe;font-weight:700">IDR esperado</div><div style="color:#f8fafc;font-size:1.35rem;font-weight:800">${idr:,.0f}</div></div><div style="background:#0a0a0a;border:1px solid rgba(0,240,255,.45);border-radius:16px;padding:15px 17px"><div style="color:#bfdbfe;font-weight:700">Patrimonio actual</div><div style="color:#f8fafc;font-size:1.35rem;font-weight:800">${patrimonio_neto_idr:,.0f}</div></div><div style="background:#0a0a0a;border:1px solid rgba(0,240,255,.45);border-radius:16px;padding:15px 17px"><div style="display:flex;justify-content:space-between"><div style="color:#bfdbfe;font-weight:700">Cumplimiento del IDR</div><div style="color:{color_cumplimiento};font-weight:900">{cumplimiento_idr_pct:,.1f}%</div></div><div style="height:13px;background:#111827;border-radius:999px;overflow:hidden;margin-top:13px"><div style="height:100%;width:{cumplimiento_barra/3:.2f}%;background:{color_cumplimiento}"></div></div><div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:.72rem"><span>0%</span><span>100%</span><span>200%</span><span>300%</span></div></div></div>''', unsafe_allow_html=True)

            # Se conservan las cuatro métricas originales de la pestaña.
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Valor hora promedio", f"${valor_hora_promedio:,.0f}")
            f2.metric("Horas registradas", f"{total_horas_trabajadas:,.1f}")
            f3.metric("Ingreso laboral", f"${ingreso_laboral:,.0f}")
            f4.metric("Ingreso no laboral", f"${ingreso_no_laboral:,.0f}")

            seccion_resumen("6", "Hallazgos y prioridad", "Convierte los indicadores en observaciones concretas para revisar.")
            hallazgos = []
            if mas_eficiente is not None:
                hallazgos.append(f"<b>{mas_eficiente['EMPRESA']}</b> registra el mayor valor por hora: <b>${mas_eficiente['VALOR_HORA']:,.0f}</b>.")
            if principal_ingreso is not None:
                hallazgos.append(f"<b>{principal_ingreso['EMPRESA']}</b> concentra el <b>{principal_ingreso['PART_INGRESOS']:.1f}%</b> de los ingresos.")
            if principal_horas is not None:
                hallazgos.append(f"<b>{principal_horas['EMPRESA']}</b> consume el <b>{principal_horas['PART_HORAS']:.1f}%</b> de las horas registradas.")
            hallazgos.append(f"Los ingresos no laborales representan el <b>{participacion_no_laboral:.1f}%</b> del total.")
            st.markdown("<div style='background:#07111f;border:1px solid rgba(56,189,248,.45);border-radius:16px;padding:16px 20px'><ol style='margin:0;color:#cbd5e1'>" + "".join(f"<li style='margin:.4rem 0'>{h}</li>" for h in hallazgos) + "</ol></div>", unsafe_allow_html=True)
            if menos_eficiente is not None and menos_eficiente["PART_HORAS"] > menos_eficiente["PART_INGRESOS"]:
                st.warning(f"Prioridad sugerida: revisar **{menos_eficiente['EMPRESA']}**, porque utiliza {menos_eficiente['PART_HORAS']:.1f}% de las horas y genera {menos_eficiente['PART_INGRESOS']:.1f}% de los ingresos. Evalúa tarifa, carga o reasignación de tiempo.")
            elif principal_ingreso is not None and principal_ingreso["PART_INGRESOS"] > 60:
                st.warning(f"Prioridad sugerida: reducir el riesgo de concentración. **{principal_ingreso['EMPRESA']}** aporta {principal_ingreso['PART_INGRESOS']:.1f}% de los ingresos.")
            else:
                st.success("No se detectó una desalineación dominante entre participación de ingresos y participación de horas.")

            seccion_resumen("7", "Calidad y detalle de datos", "Revisa registros incompletos antes de convertir las conclusiones en decisiones.")
            sin_empresa = int(trabajos_validos["EMPRESA"].isna().sum() + trabajos_validos["EMPRESA"].astype(str).str.strip().eq("").sum())
            sin_horas = int(trabajos_validos["HORAS"].le(0).sum())
            sin_fecha = int(trabajos_validos["FECHA"].isna().sum())
            total_registros = max(len(trabajos_validos), 1)
            problemas = min(sin_empresa + sin_horas + sin_fecha, total_registros)
            calidad = max(0.0, 100 * (1 - problemas / total_registros))
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Calidad estimada", f"{calidad:.1f}%")
            q2.metric("Sin empresa", sin_empresa)
            q3.metric("Sin horas válidas", sin_horas)
            q4.metric("Sin fecha válida", sin_fecha)

            with st.expander("Ver trabajos registrados", expanded=False):
                mostrar_trabajos = trabajos_validos.copy().sort_values("FECHA", ascending=False)
                mostrar_trabajos["FECHA"] = mostrar_trabajos["FECHA"].dt.strftime("%d/%m/%Y")
                st.dataframe(
                    mostrar_trabajos[["FECHA", "VALOR", "EMPRESA", "MES", "CATEGORIA", "HORAS", "VALOR_HORA"]].style.format({"VALOR": "${:,.0f}", "HORAS": "{:,.1f}", "VALOR_HORA": "${:,.0f}"}),
                    use_container_width=True, hide_index=True,
                )

            # ============================================================
            # BRÚJULA ALTIUM
            # Síntesis propia de equilibrio entre dinero, tiempo y bienestar
            # financiero estimado. No pretende medir felicidad psicológica.
            # ============================================================
            seccion_resumen(
                "8",
                "Brújula Altium",
                "Resume el equilibrio entre fortaleza económica, uso del tiempo y estabilidad de las fuentes de ingreso.",
            )

            def _limitar_0_100(valor):
                try:
                    return max(0.0, min(float(valor), 100.0))
                except (TypeError, ValueError):
                    return 0.0

            # DINERO (0-100)
            # 40% capacidad de ahorro, 35% patrimonio frente al IDR y
            # 25% estabilidad de los ingresos mensuales registrados.
            ahorro_pct_brujula = (balance / total_ingresos * 100) if total_ingresos > 0 else 0.0
            puntaje_ahorro_brujula = _limitar_0_100(ahorro_pct_brujula / 30 * 100)
            puntaje_idr_brujula = _limitar_0_100(ratio_idr / 2 * 100)

            mensual_brujula = (
                trabajos_validos.dropna(subset=["FECHA"])
                .assign(PERIODO=lambda x: x["FECHA"].dt.to_period("M").astype(str))
                .groupby("PERIODO")["VALOR"]
                .sum()
            )
            if len(mensual_brujula) >= 2 and float(mensual_brujula.mean()) > 0:
                cv_ingresos_brujula = float(mensual_brujula.std(ddof=0) / mensual_brujula.mean())
                puntaje_estabilidad_brujula = _limitar_0_100((1 - min(cv_ingresos_brujula, 1.0)) * 100)
            elif len(mensual_brujula) == 1:
                cv_ingresos_brujula = None
                puntaje_estabilidad_brujula = 50.0
            else:
                cv_ingresos_brujula = None
                puntaje_estabilidad_brujula = 0.0

            puntaje_dinero_brujula = _limitar_0_100(
                puntaje_ahorro_brujula * 0.40
                + puntaje_idr_brujula * 0.35
                + puntaje_estabilidad_brujula * 0.25
            )

            # TIEMPO (0-100)
            # Se estima la carga semanal del periodo y se complementa con la
            # proporción de horas ubicada en trabajos de eficiencia relativa >= 1.
            dias_calendario_brujula = max((fecha_hasta - fecha_desde).days + 1, 1)
            semanas_brujula = max(dias_calendario_brujula / 7, 1)
            horas_semana_brujula = total_horas_trabajadas / semanas_brujula
            if horas_semana_brujula <= 30:
                puntaje_carga_brujula = 100.0
            elif horas_semana_brujula <= 40:
                puntaje_carga_brujula = 100 - (horas_semana_brujula - 30) * 3
            elif horas_semana_brujula <= 48:
                puntaje_carga_brujula = 70 - (horas_semana_brujula - 40) * 3.75
            elif horas_semana_brujula <= 70:
                puntaje_carga_brujula = 40 - (horas_semana_brujula - 48) * (40 / 22)
            else:
                puntaje_carga_brujula = 0.0
            puntaje_carga_brujula = _limitar_0_100(puntaje_carga_brujula)

            if not resumen_empresas.empty and total_horas_trabajadas > 0:
                horas_eficientes_brujula = float(
                    resumen_empresas.loc[
                        resumen_empresas["EFICIENCIA_RELATIVA"].ge(1.0), "HORAS"
                    ].sum()
                )
                pct_horas_eficientes_brujula = horas_eficientes_brujula / total_horas_trabajadas * 100
            else:
                pct_horas_eficientes_brujula = 0.0
            puntaje_tiempo_brujula = _limitar_0_100(
                puntaje_carga_brujula * 0.70 + pct_horas_eficientes_brujula * 0.30
            )

            # BIENESTAR FINANCIERO ESTIMADO (0-100)
            # Combina diversificación, independencia parcial del trabajo y
            # estabilidad. No utiliza respuestas subjetivas de bienestar.
            concentracion_principal_brujula = (
                float(principal_ingreso["PART_INGRESOS"])
                if principal_ingreso is not None else 100.0
            )
            puntaje_diversificacion_brujula = _limitar_0_100(
                (1 - max(concentracion_principal_brujula - 25, 0) / 75) * 100
            )
            puntaje_no_laboral_brujula = _limitar_0_100(participacion_no_laboral / 30 * 100)
            puntaje_bienestar_brujula = _limitar_0_100(
                puntaje_diversificacion_brujula * 0.45
                + puntaje_no_laboral_brujula * 0.25
                + puntaje_estabilidad_brujula * 0.30
            )

            valores_brujula = [
                puntaje_dinero_brujula,
                puntaje_tiempo_brujula,
                puntaje_bienestar_brujula,
            ]
            ejes_brujula = ["Dinero", "Tiempo", "Bienestar financiero"]
            valores_cerrados_brujula = valores_brujula + [valores_brujula[0]]
            ejes_cerrados_brujula = ejes_brujula + [ejes_brujula[0]]

            fig_brujula = go.Figure()
            fig_brujula.add_trace(go.Scatterpolar(
                r=[100, 100, 100, 100],
                theta=ejes_cerrados_brujula,
                fill="toself",
                fillcolor="rgba(148,163,184,0.10)",
                line=dict(color="rgba(148,163,184,0.65)", width=2, dash="dot"),
                name="Equilibrio ideal",
                hovertemplate="Objetivo ideal: 100<extra></extra>",
            ))
            fig_brujula.add_trace(go.Scatterpolar(
                r=valores_cerrados_brujula,
                theta=ejes_cerrados_brujula,
                fill="toself",
                fillcolor="rgba(0,217,255,0.28)",
                line=dict(color="#00D9FF", width=4),
                marker=dict(size=11, color=["#22C55E", "#FACC15", "#A855F7", "#22C55E"]),
                name="Situación actual",
                text=[
                    f"Ahorro: {ahorro_pct_brujula:.1f}%<br>Patrimonio/IDR: {ratio_idr:.2f}x",
                    f"Carga: {horas_semana_brujula:.1f} h/semana<br>Horas eficientes: {pct_horas_eficientes_brujula:.1f}%",
                    f"Fuente principal: {concentracion_principal_brujula:.1f}%<br>No laborales: {participacion_no_laboral:.1f}%",
                    f"Ahorro: {ahorro_pct_brujula:.1f}%<br>Patrimonio/IDR: {ratio_idr:.2f}x",
                ],
                hovertemplate="<b>%{theta}</b><br>Puntaje: %{r:.1f}/100<br>%{text}<extra></extra>",
            ))
            fig_brujula.update_layout(
                template="plotly_dark",
                height=560,
                paper_bgcolor="#000000",
                plot_bgcolor="#000000",
                margin=dict(t=70, b=45, l=80, r=80),
                title=dict(
                    text="Brújula Altium · equilibrio actual frente al ideal",
                    x=0.5,
                    font=dict(color="#F8FAFC", size=21),
                ),
                polar=dict(
                    bgcolor="#050505",
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100],
                        tickvals=[20, 40, 60, 80, 100],
                        ticksuffix="",
                        gridcolor="rgba(148,163,184,0.22)",
                        linecolor="rgba(0,217,255,0.35)",
                        tickfont=dict(color="#94A3B8"),
                    ),
                    angularaxis=dict(
                        gridcolor="rgba(0,217,255,0.25)",
                        linecolor="rgba(0,217,255,0.45)",
                        tickfont=dict(color="#E2E8F0", size=14),
                    ),
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.04,
                    xanchor="center",
                    x=0.5,
                    bgcolor="rgba(0,0,0,0)",
                ),
            )

            equilibrio_brujula = min(valores_brujula)
            promedio_brujula = sum(valores_brujula) / 3
            eje_debil_idx = valores_brujula.index(min(valores_brujula))
            eje_fuerte_idx = valores_brujula.index(max(valores_brujula))
            eje_debil_brujula = ejes_brujula[eje_debil_idx]
            eje_fuerte_brujula = ejes_brujula[eje_fuerte_idx]

            bcol1, bcol2 = st.columns([1.35, 0.65], gap="large")
            with bcol1:
                st.plotly_chart(fig_brujula, use_container_width=True)
            with bcol2:
                st.markdown("#### Lectura de la brújula")
                bm1, bm2 = st.columns(2)
                bm1.metric("Equilibrio Altium", f"{equilibrio_brujula:.0f}/100", help="Se usa el menor de los tres ejes para evitar que una fortaleza oculte un desequilibrio importante.")
                bm2.metric("Promedio general", f"{promedio_brujula:.0f}/100")
                st.metric("Eje más fuerte", eje_fuerte_brujula, delta=f"{max(valores_brujula):.1f}/100")
                st.metric("Prioridad de mejora", eje_debil_brujula, delta=f"{min(valores_brujula):.1f}/100", delta_color="inverse")

                if equilibrio_brujula >= 75:
                    st.success("La brújula muestra un equilibrio alto: ningún eje cae por debajo de 75 puntos.")
                elif equilibrio_brujula >= 50:
                    st.warning(f"El equilibrio es intermedio. La mejora con mayor impacto está en **{eje_debil_brujula}**.")
                else:
                    st.error(f"Existe un desequilibrio relevante en **{eje_debil_brujula}**. Conviene intervenir ese eje antes de optimizar los demás.")

            explicaciones_brujula = {
                "Dinero": "Combina capacidad de ahorro (40%), patrimonio frente al IDR (35%) y estabilidad mensual de ingresos (25%).",
                "Tiempo": "Combina carga semanal estimada (70%) y proporción de horas en trabajos con eficiencia relativa igual o superior a 1 (30%).",
                "Bienestar financiero": "Combina diversificación de fuentes (45%), participación de ingresos no laborales (25%) y estabilidad mensual (30%).",
            }
            with st.expander("Cómo se calcula la Brújula Altium", expanded=False):
                st.markdown(
                    f"""
                    - **Dinero ({puntaje_dinero_brujula:.1f}/100):** {explicaciones_brujula['Dinero']}
                    - **Tiempo ({puntaje_tiempo_brujula:.1f}/100):** {explicaciones_brujula['Tiempo']}
                    - **Bienestar financiero ({puntaje_bienestar_brujula:.1f}/100):** {explicaciones_brujula['Bienestar financiero']}
                    - **Equilibrio Altium ({equilibrio_brujula:.1f}/100):** corresponde al eje con menor puntuación. Así se penalizan los desequilibrios y no se ocultan detrás de un promedio alto.

                    La brújula es un indicador orientativo construido con los datos financieros y laborales disponibles. No mide felicidad psicológica, salud mental ni satisfacción personal.
                    """
                )




else:
    st.info("Sube el archivo **altium.xlsx** para comenzar el análisis presupuestal.")
