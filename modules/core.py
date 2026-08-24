
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import unicodedata
import json
from urllib.request import Request, urlopen

st.set_page_config(page_title="Estado Financiero", layout="wide", page_icon="📊")

PALETA_CATEGORIAS = [
    "#4F46E5", "#0EA5E9", "#14B8A6", "#22C55E", "#F59E0B",
    "#F97316", "#EF4444", "#EC4899", "#8B5CF6", "#06B6D4",
    "#84CC16", "#A855F7",
]

# Paleta neón: colores muy saturados y brillantes para máximo impacto visual sobre fondo negro.
PALETA_NEON = [
    "#00F0FF", "#7B2FFF", "#00FF9C", "#FFEE00", "#FF2E9A",
    "#FF6B00", "#39FF14", "#FF003C", "#00D9FF", "#D400FF",
    "#FFD500", "#00FFC6",
]

PALETA_SUBCATEGORIAS = [
    "#00F0FF", "#3DA9FC", "#7B2FFF", "#B026FF", "#FF2E9A",
    "#FF61E6", "#00FFC6", "#00FFA3", "#39FF14", "#CBFF00",
    "#FFEE00", "#FF9E00", "#FF4D00", "#FF003C",
]

COLORSCALE_SUBCATEGORIAS = [
    [0.0, "#0A0A1A"],
    [0.18, "#7B2FFF"],
    [0.36, "#00D9FF"],
    [0.54, "#00FF9C"],
    [0.72, "#CBFF00"],
    [1.0, "#FF2E9A"],
]

# Colorscale de mapas de calor vs. meta/referencia:
# Verde = muy por debajo de la meta · Rojo = muy por encima de la meta.
# Se usa con zmid=0 (0 = exactamente en la meta) en todos los mapas de calor del dashboard.
COLORSCALE_NEON_CALOR = [
    [0.0, "#00FF66"],
    [0.15, "#7CFF00"],
    [0.35, "#CFFF00"],
    [0.5, "#FFEE00"],
    [0.65, "#FFA600"],
    [0.85, "#FF4D00"],
    [1.0, "#FF0033"],
]

COLOR_INGRESOS = "#00FF9C"
COLOR_GASTOS = "#FF2E6E"
COLOR_BALANCE = "#00E5FF"
COLOR_PRESUPUESTO = "#FFEE00"




def limpiar_titulos_plotly(fig, titulo=None, x=None, y=None, leyenda=None):
    """Evita títulos undefined/None en gráficas Plotly."""
    if titulo:
        fig.update_layout(title=dict(text=str(titulo), font=dict(color="#e2e8f0")))
    else:
        fig.update_layout(title=None)
    if x:
        fig.update_xaxes(title_text=str(x))
    else:
        fig.update_xaxes(title_text="")
    if y:
        fig.update_yaxes(title_text=str(y))
    else:
        fig.update_yaxes(title_text="")
    if leyenda:
        fig.update_layout(legend_title_text=str(leyenda))
    else:
        fig.update_layout(legend_title_text="")
    return fig

def estilo_grafico(fig, titulo=None):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#e2e8f0"),
        title=dict(text=str(titulo), font=dict(color="#e2e8f0")) if titulo else None,
        legend=dict(font=dict(color="#e2e8f0"), bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=50 if titulo else 30, b=30, l=30, r=30),
    )
    fig.update_xaxes(gridcolor="rgba(0,240,255,0.14)", linecolor="rgba(0,240,255,0.35)", zerolinecolor="rgba(0,240,255,0.25)")
    fig.update_yaxes(gridcolor="rgba(0,240,255,0.14)", linecolor="rgba(0,240,255,0.35)", zerolinecolor="rgba(0,240,255,0.25)")
    return fig



def limpiar_undefined_texto(valor, reemplazo=""):
    """Quita textos undefined/None que a veces aparecen en títulos, ejes, leyendas o tooltips."""
    if valor is None:
        return reemplazo
    texto = str(valor)
    if texto.strip().lower() in {"undefined", "none", "nan", "nat"}:
        return reemplazo
    return texto.replace("undefined", reemplazo).replace("Undefined", reemplazo).replace("UNDEFINED", reemplazo)


def preparar_grafico_resumen(fig, titulo, x=None, y=None, leyenda=None, mostrar_leyenda=None):
    """Aplica estilo y nombres limpios a los gráficos de la pestaña Resumen."""
    fig = estilo_grafico(fig, titulo=titulo)
    fig.update_layout(
        title=dict(text=limpiar_undefined_texto(titulo), font=dict(color="#e2e8f0")),
        legend_title_text=limpiar_undefined_texto(leyenda, "") if leyenda is not None else "",
    )
    if mostrar_leyenda is not None:
        fig.update_layout(showlegend=mostrar_leyenda)
    if x is not None:
        fig.update_xaxes(title_text=limpiar_undefined_texto(x, ""))
    if y is not None:
        fig.update_yaxes(title_text=limpiar_undefined_texto(y, ""))

    for traza in fig.data:
        if hasattr(traza, "name"):
            traza.name = limpiar_undefined_texto(traza.name, "")
        if hasattr(traza, "legendgroup"):
            traza.legendgroup = limpiar_undefined_texto(traza.legendgroup, "")
        if hasattr(traza, "hovertemplate") and traza.hovertemplate:
            traza.hovertemplate = limpiar_undefined_texto(traza.hovertemplate, "")
        if hasattr(traza, "texttemplate") and traza.texttemplate:
            traza.texttemplate = limpiar_undefined_texto(traza.texttemplate, "")
    return fig

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: #000000 !important;
    background-color: #000000 !important;
}

.stApp::before {
    display: none;
}

.block-container {
    position: relative;
    z-index: 1;
    background: transparent;
    width: 100% !important;
    max-width: 100vw !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* Mantiene estable el ancho del dashboard y de Plotly al recargar la página. */
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="column"],
[data-testid="stPlotlyChart"] {
    max-width: 100% !important;
}

[data-testid="stPlotlyChart"] > div {
    width: 100% !important;
}

.checkbox-center {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
    margin-top: -0.35rem;
    margin-bottom: 0.35rem;
}

.checkbox-center [data-testid="stCheckbox"] {
    width: fit-content;
    margin-left: auto;
    margin-right: auto;
}

section[data-testid="stSidebar"] {
    background:
        radial-gradient(circle at 12% 8%, rgba(0, 217, 255, 0.12), transparent 28%),
        radial-gradient(circle at 88% 42%, rgba(123, 47, 255, 0.12), transparent 34%),
        linear-gradient(180deg, #020408 0%, #05030B 52%, #010405 100%) !important;
    border-right: 1px solid rgba(0, 217, 255, 0.65);
    box-shadow: 12px 0 34px rgba(0, 217, 255, 0.08);
}

section[data-testid="stSidebar"] > div {
    background: transparent !important;
}

header[data-testid="stHeader"] {
    background: rgba(0, 0, 0, 0.95) !important;
}

.main .block-container {
    color: #e2e8f0;
}

[data-testid="stAppViewContainer"] {
    background: #000000 !important;
}

[data-testid="stMain"] {
    background: #000000 !important;
}

section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
    background: linear-gradient(90deg, #00F0FF, #A855F7, #FF2E9A);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    color: #00F0FF !important;
    font-weight: 800;
    letter-spacing: 0.045em;
    text-transform: uppercase;
    font-size: 1.05rem;
    margin-bottom: 0.8rem;
}

.filter-card {
    position: relative;
    overflow: hidden;
    background: linear-gradient(145deg, rgba(7, 20, 29, 0.96), rgba(13, 5, 24, 0.94));
    border: 1px solid rgba(0, 240, 255, 0.58);
    border-radius: 18px;
    padding: 0.9rem 1rem 0.55rem 1rem;
    margin-bottom: 0.85rem;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.06),
        0 0 18px rgba(0, 240, 255, 0.13),
        0 8px 24px rgba(0, 0, 0, 0.62);
}

.filter-card label, .filter-card p, .filter-card span {
    color: #dbeafe !important;
    font-weight: 600 !important;
}

.filter-card::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: linear-gradient(180deg, #00F0FF, #7B2FFF, #FF2E9A);
    box-shadow: 0 0 12px #00F0FF;
}

/* Controles de filtro: superficie oscura, borde neón y enfoque visible. */
section[data-testid="stSidebar"] [data-testid="stSelectbox"],
section[data-testid="stSidebar"] [data-testid="stMultiSelect"],
section[data-testid="stSidebar"] [data-testid="stDateInput"] {
    background: linear-gradient(145deg, rgba(4, 12, 19, 0.86), rgba(10, 4, 19, 0.86));
    border: 1px solid rgba(123, 47, 255, 0.24);
    border-radius: 16px;
    padding: 0.68rem 0.72rem 0.58rem;
    margin: 0.25rem 0 0.42rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.035), 0 7px 20px rgba(0,0,0,0.42);
    transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
}

section[data-testid="stSidebar"] [data-testid="stSelectbox"]:hover,
section[data-testid="stSidebar"] [data-testid="stMultiSelect"]:hover,
section[data-testid="stSidebar"] [data-testid="stDateInput"]:hover {
    border-color: rgba(0, 240, 255, 0.68);
    box-shadow: 0 0 18px rgba(0, 240, 255, 0.13), 0 8px 22px rgba(0,0,0,0.48);
    transform: translateY(-1px);
}

section[data-testid="stSidebar"] [data-testid="stSelectbox"]:focus-within,
section[data-testid="stSidebar"] [data-testid="stMultiSelect"]:focus-within,
section[data-testid="stSidebar"] [data-testid="stDateInput"]:focus-within {
    border-color: #00F0FF;
    box-shadow: 0 0 0 1px rgba(0,240,255,0.28), 0 0 24px rgba(0,240,255,0.22);
}

section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: #BDEFFF !important;
    font-size: 0.77rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.065em;
    text-transform: uppercase;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
section[data-testid="stSidebar"] div[data-baseweb="input"] {
    background: linear-gradient(135deg, rgba(1, 8, 14, 0.98), rgba(12, 4, 22, 0.98)) !important;
    border: 1px solid rgba(0, 217, 255, 0.50) !important;
    border-radius: 12px !important;
    min-height: 42px;
    color: #F4FBFF !important;
    box-shadow: inset 0 0 14px rgba(0,217,255,0.035);
}

section[data-testid="stSidebar"] div[data-baseweb="select"]:focus-within > div,
section[data-testid="stSidebar"] div[data-baseweb="input"]:focus-within {
    border-color: #00F0FF !important;
    box-shadow: 0 0 0 1px rgba(0,240,255,0.22), 0 0 14px rgba(0,240,255,0.20) !important;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] span,
section[data-testid="stSidebar"] div[data-baseweb="select"] input,
section[data-testid="stSidebar"] div[data-baseweb="input"] input {
    color: #F4FBFF !important;
    -webkit-text-fill-color: #F4FBFF !important;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] svg,
section[data-testid="stSidebar"] div[data-baseweb="input"] svg {
    fill: #00F0FF !important;
    color: #00F0FF !important;
}

section[data-testid="stSidebar"] [data-baseweb="tag"] {
    background: linear-gradient(135deg, rgba(0,217,255,0.28), rgba(123,47,255,0.42)) !important;
    border: 1px solid rgba(0,240,255,0.55) !important;
    border-radius: 999px !important;
    color: #FFFFFF !important;
    box-shadow: 0 0 10px rgba(0,217,255,0.14);
}

section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: #7DDFF4 !important;
    font-size: 0.70rem !important;
    letter-spacing: 0.025em;
    margin-top: 0.1rem;
}

/* Menús desplegables se renderizan fuera del sidebar mediante un portal. */
div[data-baseweb="popover"] ul[role="listbox"] {
    background: linear-gradient(160deg, #030B12, #10051D) !important;
    border: 1px solid rgba(0, 240, 255, 0.62) !important;
    border-radius: 14px !important;
    padding: 0.35rem !important;
    box-shadow: 0 0 26px rgba(0,217,255,0.18), 0 18px 50px rgba(0,0,0,0.78) !important;
}

div[data-baseweb="popover"] li[role="option"] {
    color: #EAFBFF !important;
    border-radius: 9px !important;
    margin: 2px 0;
}

div[data-baseweb="popover"] li[role="option"]:hover,
div[data-baseweb="popover"] li[aria-selected="true"] {
    background: linear-gradient(90deg, rgba(0,217,255,0.25), rgba(123,47,255,0.32)) !important;
    color: #FFFFFF !important;
}

section[data-testid="stSidebar"]::-webkit-scrollbar,
section[data-testid="stSidebar"] *::-webkit-scrollbar {
    width: 7px;
}

section[data-testid="stSidebar"]::-webkit-scrollbar-thumb,
section[data-testid="stSidebar"] *::-webkit-scrollbar-thumb {
    background: linear-gradient(#00D9FF, #7B2FFF);
    border-radius: 999px;
}

div[data-testid="stMetric"] {
    background: #0a0a0a;
    border: 1px solid rgba(0, 240, 255, 0.4);
    border-radius: 14px;
    padding: 0.75rem 1rem;
    box-shadow: 0 0 12px rgba(0, 240, 255, 0.12), 0 4px 16px rgba(0, 0, 0, 0.5);
}

div[data-testid="stMetric"] label {
    color: #bfdbfe !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #f8fafc !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: #0a0a0a;
    border-radius: 14px;
    padding: 6px;
    border: 1px solid rgba(99, 102, 241, 0.35);
}

.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    color: #c7d2fe;
    font-weight: 600;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #00D9FF, #7B2FFF) !important;
    color: white !important;
    box-shadow: 0 0 14px rgba(0, 217, 255, 0.55);
}

.hero-title {
    font-size: 2.6rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    background: linear-gradient(90deg, #00F0FF, #7B2FFF, #FF2E9A);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
    filter: drop-shadow(0 0 14px rgba(0, 240, 255, 0.35));
}

.hero-accent {
    height: 4px;
    width: 160px;
    background: linear-gradient(90deg, #00F0FF, #7B2FFF, #FF2E9A);
    border-radius: 3px;
    margin-bottom: 1.1rem;
    box-shadow: 0 0 12px rgba(0, 240, 255, 0.6), 0 0 12px rgba(255, 46, 154, 0.4);
}

.hero-sub {
    color: #94a3b8;
    margin-bottom: 1.2rem;
}

div[data-baseweb="select"] > div,
div[data-baseweb="input"] {
    border-color: rgba(99, 102, 241, 0.5) !important;
    background: #0a0a0a !important;
    color: #e2e8f0 !important;
}

span[data-baseweb="tag"] {
    background: linear-gradient(135deg, #00D9FF, #7B2FFF) !important;
    border: none !important;
    color: white !important;
    border-radius: 999px !important;
    box-shadow: 0 0 8px rgba(0, 217, 255, 0.5);
}

.stFileUploader section {
    background: #0a0a0a;
    border: 1px dashed rgba(99, 102, 241, 0.5);
    border-radius: 14px;
}

.stDataFrame, [data-testid="stDataFrame"] {
    background: #0a0a0a;
}

[data-testid="stPlotlyChart"] {
    background: #050505;
    border: 1px solid rgba(0, 240, 255, 0.55);
    border-radius: 18px;
    padding: 0.7rem;
    box-shadow: 0 0 22px rgba(0, 240, 255, 0.18), 0 0 46px rgba(123, 47, 255, 0.12), 0 10px 28px rgba(0,0,0,0.5);
    margin-bottom: 1.1rem;
    transition: box-shadow 0.25s ease;
}

[data-testid="stPlotlyChart"]:hover {
    box-shadow: 0 0 32px rgba(0, 240, 255, 0.32), 0 0 60px rgba(255, 46, 154, 0.18), 0 10px 28px rgba(0,0,0,0.55);
}

hr {
    border-color: rgba(99, 102, 241, 0.25);
}
</style>
"""


def normalizar(texto):
    if pd.isna(texto):
        return ""
    t = unicodedata.normalize("NFKD", str(texto).strip().upper())
    return "".join(c for c in t if not unicodedata.combining(c))


def _lerp_color(c1, c2, t):
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return r, g, b


def color_presupuesto(gasto, presupuesto, max_desv):
    if presupuesto <= 0:
        return "#94A3B8"   # Gris

    diferencia = (gasto - presupuesto) / presupuesto

    # Dentro del margen de tolerancia ±10%
    if -0.10 <= diferencia <= 0.10:
        return "#FFFFFF"

    # Se pasó del presupuesto
    elif diferencia > 0.10:
        return "#FF2E2E"

    # Ahorró más del 10%
    else:
        return "#2E6FEF"


def rgb_a(rgb, alpha=0.62):
    if rgb.startswith("rgb("):
        return f"rgba({rgb[4:-1]},{alpha})"
    return rgb


def buscar_presupuesto_sub(categoria, subcategoria, presupuesto_sub):
    cat_n = normalizar(categoria)
    sub_n = normalizar(subcategoria)
    if (cat_n, sub_n) in presupuesto_sub:
        return presupuesto_sub[(cat_n, sub_n)]
    for (c, s), valor in presupuesto_sub.items():
        if c != cat_n:
            continue
        if sub_n == s or sub_n in s or s in sub_n:
            return valor
    return 0.0


def calc_max_desv(pares):
    desviaciones = []
    for gasto, pres in pares:
        if pres > 0:
            desviaciones.append(abs((gasto - pres) / pres))
    return max(desviaciones, default=1.0)


def arco_wedge(theta_start, theta_end, r_inner, r_outer, n_pts=18):
    if theta_end < theta_start:
        theta_end += 360
    inner_t = [theta_start + (theta_end - theta_start) * i / (n_pts - 1) for i in range(n_pts)]
    outer_t = list(reversed(inner_t))
    theta = inner_t + outer_t + [theta_start]
    r = [r_inner] * n_pts + [r_outer] * n_pts + [r_inner]
    return r, theta


def texto_tooltip_radar(titulo, gasto, presupuesto, nivel=""):
    pref = f"{nivel}: " if nivel else ""
    if presupuesto > 0:
        diff = gasto - presupuesto
        pct = (diff / presupuesto) * 100
        estado = "Sobre presupuesto" if diff > 0 else "Bajo presupuesto" if diff < 0 else "En presupuesto"
        return (
            f"{pref}{titulo}\n"
            f"Gasto: ${gasto:,.0f}\n"
            f"Presupuesto: ${presupuesto:,.0f}\n"
            f"Diferencia: ${diff:,.0f} ({pct:+.1f}%)\n"
            f"{estado}"
        )
    return f"{pref}{titulo}\nGasto: ${gasto:,.0f}\nSin presupuesto definido"


def agregar_zona(fig, theta_start, theta_end, r_inner, r_outer, color, tooltip="", alpha=0.72):
    r_vals, theta_vals = arco_wedge(theta_start, theta_end, r_inner, r_outer)
    fig.add_trace(
        go.Scatterpolar(
            r=r_vals,
            theta=theta_vals,
            fill="toself",
            fillcolor=rgb_a(color, alpha),
            line=dict(color=color, width=1.2),
            mode="lines",
            text=[tooltip] * len(theta_vals),
            hoverinfo="text",
            hoveron="fills",
            hoverlabel=dict(bgcolor="#111111", bordercolor="#6366f1", font=dict(size=13, color="#f8fafc")),
            showlegend=False,
            name="",
        )
    )


def construir_radar_categorias(radar_df, presupuesto_cat):
    grouped = (
        radar_df.groupby("GASTOS_CATEGORIA")["GASTOS_CANTIDAD"]
        .sum()
        .sort_index()
    )
    return _construir_radar_zonas(
        grouped,
        [presupuesto_cat.get(normalizar(l), 0) for l in grouped.index],
        list(grouped.index),
        "Categoría",
    )


def construir_radar_subcategorias(radar_df, presupuesto_sub):
    tmp = radar_df.dropna(subset=["GASTOS_SUBCATEGORIA"]).copy()
    if tmp.empty:
        return go.Figure()

    tmp["ETIQUETA"] = (
        tmp["GASTOS_CATEGORIA"].astype(str) + " › " + tmp["GASTOS_SUBCATEGORIA"].astype(str)
    )
    grouped = tmp.groupby("ETIQUETA")["GASTOS_CANTIDAD"].sum().sort_index()
    pres_lookup = {}
    for _, row in tmp.drop_duplicates("ETIQUETA").iterrows():
        pres_lookup[row["ETIQUETA"]] = buscar_presupuesto_sub(
            row["GASTOS_CATEGORIA"], row["GASTOS_SUBCATEGORIA"], presupuesto_sub
        )
    return _construir_radar_zonas(
        grouped,
        [pres_lookup.get(l, 0) for l in grouped.index],
        list(grouped.index),
        "Subcategoría",
    )


def _construir_radar_zonas(grouped, presupuestos, labels, titulo_nivel):
    if grouped.empty:
        return go.Figure()

    gastos = [float(grouped[l]) for l in labels]
    pares = list(zip(gastos, presupuestos))
    max_desv = max(calc_max_desv(pares), 0.1)
    colores = [color_presupuesto(g, p, max_desv) for g, p in pares]

    n = len(labels)
    gap = 1.8
    span = (360 - n * gap) / n
    r_max = max(max(gastos), max(presupuestos), 1)
    r_inner = r_max * 0.2
    centers = []
    fig = go.Figure()

    theta = 0.0
    for i, label in enumerate(labels):
        start, end = theta, theta + span
        centers.append((start + end) / 2)
        tooltip = texto_tooltip_radar(str(label), gastos[i], presupuestos[i], titulo_nivel)
        agregar_zona(
            fig, start, end, r_inner, gastos[i], colores[i],
            tooltip=tooltip,
            alpha=0.76,
        )
        theta = end + gap

    textos_gasto = [
        texto_tooltip_radar(str(l), gastos[i], presupuestos[i], titulo_nivel)
        for i, l in enumerate(labels)
    ]
    textos_pres = [
        f"Presupuesto\n{l}\nMonto: ${presupuestos[i]:,.0f}"
        if presupuestos[i] > 0
        else f"Presupuesto\n{l}\nSin valor definido"
        for i, l in enumerate(labels)
    ]

    fig.add_trace(
        go.Scatterpolar(
            r=gastos + [gastos[0]],
            theta=centers + [centers[0]],
            mode="lines",
            line=dict(color="rgba(248,250,252,0.7)", width=2.2, shape="spline"),
            hoverinfo="skip",
            showlegend=False,
            name="",
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=presupuestos + [presupuestos[0]],
            theta=centers + [centers[0]],
            mode="lines",
            line=dict(color="rgba(250,204,21,0.9)", width=2, dash="dot", shape="spline"),
            hoverinfo="skip",
            showlegend=False,
            name="",
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=gastos,
            theta=centers,
            mode="markers",
            name="Gasto real",
            marker=dict(
                size=16,
                color=colores,
                line=dict(color="rgba(255,255,255,0.9)", width=1.5),
                symbol="circle",
            ),
            text=textos_gasto,
            hoverinfo="text",
            hoverlabel=dict(bgcolor="#111111", bordercolor="#6366f1", font=dict(size=13, color="#f8fafc")),
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=[presupuestos[i] for i in range(n) if presupuestos[i] > 0],
            theta=[centers[i] for i in range(n) if presupuestos[i] > 0],
            mode="markers",
            name="Presupuesto",
            marker=dict(size=10, color="rgba(250,204,21,0.95)", symbol="diamond"),
            text=[textos_pres[i] for i in range(n) if presupuestos[i] > 0],
            hoverinfo="text",
            hoverlabel=dict(bgcolor="#111111", bordercolor="#facc15", font=dict(size=13, color="#f8fafc")),
        )
    )
    altura = 700 if n <= 10 else 820 if n <= 18 else 920
    _estilo_polar(fig, centers, labels, r_max, height=altura)
    return fig


def _estilo_polar(fig, tick_vals, tick_text, r_max, height=760):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        margin=dict(t=60, b=40, l=70, r=70),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            font=dict(color="#c7d2fe"),
            bgcolor="rgba(0,0,0,0.8)",
        ),
        hovermode="closest",
        polar=dict(
            bgcolor="#0a0a0a",
            angularaxis=dict(
                tickmode="array",
                tickvals=tick_vals,
                ticktext=[str(t)[:28] + ("…" if len(str(t)) > 28 else "") for t in tick_text],
                direction="clockwise",
                gridcolor="rgba(99,102,241,0.2)",
                linecolor="rgba(99,102,241,0.3)",
                tickfont=dict(size=10, color="#cbd5e1"),
            ),
            radialaxis=dict(
                visible=True,
                tickformat=",.0f",
                gridcolor="rgba(99,102,241,0.18)",
                linecolor="rgba(99,102,241,0.25)",
                range=[0, r_max * 1.12],
                tickfont=dict(color="#94a3b8"),
            ),
        ),
    )


def texto_tooltip_heatmap(
    etiqueta_fila, fila, mes, gasto, presupuesto, transacciones=None,
    etiqueta_valor="Gasto", etiqueta_meta="Presupuesto mensual",
):
    lineas = [f"<b>{etiqueta_fila}: {fila}</b>", f"Mes: {mes}", f"{etiqueta_valor}: ${gasto:,.0f}"]
    if transacciones is not None:
        lineas.append(f"Transacciones: {transacciones:,.0f}")
    if presupuesto > 0:
        diff = gasto - presupuesto
        pct = (diff / presupuesto) * 100
        estado = "🔴 Sobre la meta" if diff > 0 else "🟢 Bajo la meta" if diff < 0 else "🟡 En la meta"
        lineas.extend([
            f"{etiqueta_meta}: ${presupuesto:,.0f}",
            f"Diferencia: ${diff:,.0f} ({pct:+.1f}%)",
            estado,
        ])
    else:
        lineas.append(f"{etiqueta_meta}: sin valor definido")
    return "<br>".join(lineas)


def crear_heatmap_presupuesto(
    tabla_gastos, presupuesto_fn, etiqueta_fila="Categoría",
    tabla_transacciones=None, colorscale=None, colorbar_title="Desviación",
    etiqueta_valor="Gasto", etiqueta_meta="Presupuesto mensual",
):
    if tabla_gastos is None or tabla_gastos.empty or tabla_gastos.shape[0] == 0 or tabla_gastos.shape[1] == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No hay datos suficientes para generar el mapa de calor",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=17, color="#cbd5e1"),
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        fig.update_layout(
            template="plotly_dark",
            height=420,
            paper_bgcolor="#000000",
            plot_bgcolor="#000000",
            margin=dict(t=30, b=30, l=30, r=30),
        )
        return fig

    def _resolver_presupuesto(fila, columna):
        try:
            return float(presupuesto_fn(fila, columna) or 0)
        except TypeError:
            return float(presupuesto_fn(fila) or 0)

    desv = tabla_gastos.astype(float).copy()
    for idx in desv.index:
        for col in desv.columns:
            pres = _resolver_presupuesto(idx, col)
            gasto = float(tabla_gastos.loc[idx, col])
            desv.loc[idx, col] = ((gasto - pres) / pres) if pres > 0 else 0.0

    valores = desv.to_numpy(dtype=float).ravel()
    if valores.size == 0:
        max_abs = 0.1
    else:
        max_abs = max(float(abs(valores.min())), float(abs(valores.max())), 0.1)
    max_abs = min(max_abs, 1.5)

    filas = desv.index.tolist()
    columnas = desv.columns.tolist()
    customdata = []
    for fila in filas:
        fila_textos = []
        for col in columnas:
            pres = _resolver_presupuesto(fila, col)
            gasto = float(tabla_gastos.loc[fila, col])
            trans = float(tabla_transacciones.loc[fila, col]) if tabla_transacciones is not None else None
            fila_textos.append(
                texto_tooltip_heatmap(
                    etiqueta_fila, fila, col, gasto, pres, trans,
                    etiqueta_valor=etiqueta_valor, etiqueta_meta=etiqueta_meta,
                )
            )
        customdata.append(fila_textos)

    fig = go.Figure(
        data=go.Heatmap(
            z=desv.values,
            x=columnas,
            y=filas,
            text=tabla_gastos.values,
            texttemplate="$%{text:,.0f}",
            textfont={"size": 11, "color": "#1e293b", "family": "DM Sans, sans-serif"},
            customdata=customdata,
            hovertemplate="%{customdata}<extra></extra>",
            colorscale=colorscale or COLORSCALE_NEON_CALOR,
            zmid=0,
            zmin=-max_abs,
            zmax=max_abs,
            xgap=4,
            ygap=4,
            hoverlabel=dict(
                bgcolor="#0a0a0a",
                bordercolor="#00F0FF",
                font=dict(size=13, color="#f8fafc", family="DM Sans, sans-serif"),
                align="left",
            ),
            colorbar=dict(
                title=dict(text=colorbar_title, font=dict(color="#e2e8f0")),
                tickformat="+.0%",
                tickfont=dict(color="#e2e8f0"),
                outlinewidth=0,
            ),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=800,
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#e2e8f0"),
        xaxis=dict(title="Mes", side="bottom"),
        yaxis=dict(title=etiqueta_fila, autorange="reversed"),
        margin=dict(t=30, b=40, l=10, r=10),
    )
    return fig


def tooltip_jerarquia(nivel, nombre, monto, presupuesto, transacciones, pct_total, pct_padre=None, mostrar_presupuesto=True):
    titulo = f"<b>{nivel}: {nombre}</b>" if nivel else f"<b>{nombre}</b>"
    lineas = [
        titulo,
        f"Gasto: ${monto:,.0f}",
        f"% del total filtrado: {pct_total:.1f}%",
        f"Transacciones: {transacciones:,}",
    ]
    if pct_padre is not None and nivel not in ("", "Categoría"):
        lineas.insert(3, f"% dentro de la categoría: {pct_padre:.1f}%")
    if mostrar_presupuesto:
        if presupuesto > 0:
            diff = monto - presupuesto
            pct = (diff / presupuesto) * 100
            estado = "🔴 Sobre presupuesto" if diff > 0 else "🔵 Bajo presupuesto" if diff < 0 else "⚪ En presupuesto"
            lineas.extend([
                f"Presupuesto mensual: ${presupuesto:,.0f}",
                f"Diferencia: ${diff:,.0f} ({pct:+.1f}%)",
                estado,
            ])
        else:
            lineas.append("Presupuesto: sin valor definido")
    return "<br>".join(lineas)


def construir_nodos_categorias(df, presupuesto_cat, presupuesto_sub):
    total = float(df["GASTOS_CANTIDAD"].sum()) or 1.0
    ids, labels, parents, values, tooltips = [], [], [], [], []

    for cat in sorted(df["GASTOS_CATEGORIA"].dropna().unique()):
        cat_df = df[df["GASTOS_CATEGORIA"] == cat]
        cat_monto = float(cat_df["GASTOS_CANTIDAD"].sum())
        cat_pres = presupuesto_cat.get(normalizar(cat), 0)
        cat_trans = len(cat_df)
        cat_pct = cat_monto / total * 100
        cat_id = str(cat)

        ids.append(cat_id)
        labels.append(cat_id)
        parents.append("")
        values.append(cat_monto)
        tooltips.append(tooltip_jerarquia("Categoría", cat_id, cat_monto, cat_pres, cat_trans, cat_pct))

        subs = (
            cat_df.groupby("GASTOS_SUBCATEGORIA", dropna=False)["GASTOS_CANTIDAD"]
            .agg(["sum", "count"])
            .reset_index()
        )
        for _, row in subs.iterrows():
            sub = row["GASTOS_SUBCATEGORIA"]
            sub_nombre = "Sin subcategoría" if pd.isna(sub) else str(sub)
            sub_monto = float(row["sum"])
            sub_trans = int(row["count"])
            sub_pres = buscar_presupuesto_sub(cat, sub, presupuesto_sub)
            sub_pct_total = sub_monto / total * 100
            sub_pct_padre = sub_monto / cat_monto * 100 if cat_monto > 0 else 0
            sub_id = f"{cat_id}/{sub_nombre}"

            ids.append(sub_id)
            labels.append(sub_nombre)
            parents.append(cat_id)
            values.append(sub_monto)
            tooltips.append(
                tooltip_jerarquia(
                    "Subcategoría", sub_nombre, sub_monto, sub_pres,
                    sub_trans, sub_pct_total, sub_pct_padre,
                )
            )

    return ids, labels, parents, values, tooltips


def fig_jerarquia_categorias(df, presupuesto_cat, presupuesto_sub, tipo="treemap"):
    ids, labels, parents, values, tooltips = construir_nodos_categorias(
        df, presupuesto_cat, presupuesto_sub
    )
    if not ids:
        return go.Figure()

    trace_cls = go.Treemap if tipo == "treemap" else go.Sunburst
    colores = colores_nodos_subcategorias(ids, parents)
    fig = go.Figure(
        trace_cls(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            customdata=tooltips,
            hovertemplate="%{customdata}<extra></extra>",
            hoverlabel=dict(bgcolor="#111111", bordercolor="#38BDF8", font=dict(size=13, color="#f8fafc")),
            branchvalues="total",
            marker=dict(colors=colores, line=dict(color="#050505", width=1.5)),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=620,
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#e2e8f0"),
        margin=dict(t=40, b=20, l=10, r=10),
    )
    return fig


def construir_nodos_subcategorias_detalle(df, presupuesto_sub):
    tmp = df.copy()
    tmp["GASTOS_SUBCATEGORIA"] = tmp["GASTOS_SUBCATEGORIA"].fillna("Sin subcategoría")
    tmp["GASTOS_SUBCATEGORIA_2"] = tmp["GASTOS_SUBCATEGORIA_2"].fillna("Sin detalle")

    total = float(tmp["GASTOS_CANTIDAD"].sum()) or 1.0
    ids, labels, parents, values, tooltips = [], [], [], [], []

    for cat in sorted(tmp["GASTOS_CATEGORIA"].dropna().unique()):
        cat_df = tmp[tmp["GASTOS_CATEGORIA"] == cat]
        cat_monto = float(cat_df["GASTOS_CANTIDAD"].sum())
        cat_trans = len(cat_df)
        cat_pct = cat_monto / total * 100
        cat_id = str(cat)

        ids.append(cat_id)
        labels.append(cat_id)
        parents.append("")
        values.append(cat_monto)
        tooltips.append(
            tooltip_jerarquia("Categoría", cat_id, cat_monto, 0, cat_trans, cat_pct, mostrar_presupuesto=False)
        )

        for sub in sorted(cat_df["GASTOS_SUBCATEGORIA"].unique()):
            sub_df_n = cat_df[cat_df["GASTOS_SUBCATEGORIA"] == sub]
            sub_monto = float(sub_df_n["GASTOS_CANTIDAD"].sum())
            sub_trans = len(sub_df_n)
            sub_pres = buscar_presupuesto_sub(cat, sub, presupuesto_sub)
            sub_pct_total = sub_monto / total * 100
            sub_pct_padre = sub_monto / cat_monto * 100 if cat_monto > 0 else 0
            sub_id = f"{cat_id}/{sub}"

            ids.append(sub_id)
            labels.append(str(sub))
            parents.append(cat_id)
            values.append(sub_monto)
            tooltips.append(
                tooltip_jerarquia(
                    "Subcategoría", str(sub), sub_monto, sub_pres,
                    sub_trans, sub_pct_total, sub_pct_padre,
                )
            )

            for sub2 in sorted(sub_df_n["GASTOS_SUBCATEGORIA_2"].unique()):
                sub2_df = sub_df_n[sub_df_n["GASTOS_SUBCATEGORIA_2"] == sub2]
                sub2_monto = float(sub2_df["GASTOS_CANTIDAD"].sum())
                sub2_trans = len(sub2_df)
                sub2_pct_total = sub2_monto / total * 100
                sub2_pct_padre = sub2_monto / sub_monto * 100 if sub_monto > 0 else 0
                sub2_id = f"{sub_id}/{sub2}"

                ids.append(sub2_id)
                labels.append(str(sub2))
                parents.append(sub_id)
                values.append(sub2_monto)
                tooltips.append(
                    tooltip_jerarquia(
                        "Detalle", str(sub2), sub2_monto, 0,
                        sub2_trans, sub2_pct_total, sub2_pct_padre,
                        mostrar_presupuesto=False,
                    )
                )

    return ids, labels, parents, values, tooltips


def colores_nodos_subcategorias(ids, parents):
    colores = []
    color_por_categoria = {}
    idx_cat = 0
    for node_id, parent in zip(ids, parents):
        if parent == "":
            color = PALETA_SUBCATEGORIAS[idx_cat % len(PALETA_SUBCATEGORIAS)]
            color_por_categoria[node_id] = color
            colores.append(color)
            idx_cat += 1
        else:
            categoria_raiz = str(node_id).split("/")[0]
            base = color_por_categoria.get(categoria_raiz, "#818cf8")
            # Los detalles quedan más suaves para diferenciar la jerarquía sin perder legibilidad.
            colores.append(base if str(parent) == categoria_raiz else "rgba(226,232,240,0.82)")
    return colores


def fig_jerarquia_subcategorias(df, presupuesto_sub, tipo="treemap"):
    ids, labels, parents, values, tooltips = construir_nodos_subcategorias_detalle(df, presupuesto_sub)
    if not ids:
        return go.Figure()

    trace_cls = go.Treemap if tipo == "treemap" else go.Sunburst
    colores = colores_nodos_subcategorias(ids, parents)
    fig = go.Figure(
        trace_cls(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            customdata=tooltips,
            hovertemplate="%{customdata}<extra></extra>",
            hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="#6366f1", font=dict(size=13, color="#f8fafc")),
            branchvalues="total",
            marker=dict(colors=colores, line=dict(color="#050505", width=1.5)),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=640,
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#e2e8f0"),
        margin=dict(t=40, b=20, l=10, r=10),
    )
    return fig




def parse_historico_presupuesto(file):
    """Lee Historico_presupuesto en formato ancho y lo convierte a formato mensual.

    Columnas esperadas: Categoría, Concepto, propuesto y columnas de mes/año.
    El valor mensual tiene prioridad; si está vacío, se usa propuesto.
    """
    try:
        raw = pd.read_excel(file, sheet_name="Historico_presupuesto")
    except Exception:
        return pd.DataFrame(columns=["CATEGORIA", "CONCEPTO", "ANIO", "MES", "PRESUPUESTO", "FUENTE"])

    if raw.empty or raw.shape[1] < 3:
        return pd.DataFrame(columns=["CATEGORIA", "CONCEPTO", "ANIO", "MES", "PRESUPUESTO", "FUENTE"])

    cols = list(raw.columns)
    cat_col = next((c for c in cols if normalizar(c) in {"CATEGORIA", "CATEGORÍA"}), cols[0])
    concepto_col = next((c for c in cols if normalizar(c) in {"CONCEPTO", "SUBCATEGORIA", "SUBCATEGORÍA"}), cols[1])
    propuesto_col = next((c for c in cols if normalizar(c) in {"PROPUESTO", "VIGENTE", "POR DEFECTO", "PREDETERMINADO"}), cols[2])

    filas = []
    for _, row in raw.iterrows():
        categoria = row.get(cat_col)
        concepto = row.get(concepto_col)
        if pd.isna(categoria) or pd.isna(concepto):
            continue
        propuesto = pd.to_numeric(row.get(propuesto_col), errors="coerce")
        propuesto = float(propuesto) if pd.notna(propuesto) else 0.0

        for col in cols:
            if col in {cat_col, concepto_col, propuesto_col}:
                continue
            fecha = pd.to_datetime(col, errors="coerce", dayfirst=True)
            if pd.isna(fecha):
                texto = normalizar(col).replace("_", "-").replace("/", "-")
                partes = [x for x in texto.split("-") if x]
                if len(partes) >= 2:
                    mes_txt, anio_txt = partes[0], partes[-1]
                    mes = normalizar_mes(mes_txt)
                    try:
                        anio = int(anio_txt) + (2000 if int(anio_txt) < 100 else 0)
                    except Exception:
                        continue
                    if mes not in MESES_NUM:
                        continue
                else:
                    continue
            else:
                mes = MESES_ORDEN[int(fecha.month) - 1]
                anio = int(fecha.year)

            mensual = pd.to_numeric(row.get(col), errors="coerce")
            usa_mensual = pd.notna(mensual)
            valor = float(mensual) if usa_mensual else propuesto
            filas.append({
                "CATEGORIA": normalizar(categoria),
                "CONCEPTO": normalizar(concepto),
                "ANIO": anio,
                "MES": mes,
                "PRESUPUESTO": max(valor, 0.0),
                "FUENTE": "MES" if usa_mensual else "PROPUESTO",
            })

    return pd.DataFrame(filas)


def obtener_presupuestos_periodo(historico, periodos):
    """Agrega presupuestos para una colección de pares (año, mes)."""
    if historico is None or historico.empty:
        return {}, {}, 0.0, {}
    claves = {(int(a), normalizar_mes(m)) for a, m in periodos if pd.notna(a)}
    tmp = historico[historico.apply(lambda r: (int(r["ANIO"]), r["MES"]) in claves, axis=1)].copy()
    if tmp.empty:
        return {}, {}, 0.0, {}
    cat = tmp.groupby("CATEGORIA")["PRESUPUESTO"].sum().to_dict()
    sub = tmp.groupby(["CATEGORIA", "CONCEPTO"])["PRESUPUESTO"].sum().to_dict()
    total = float(tmp["PRESUPUESTO"].sum())
    mensual = tmp.groupby(["ANIO", "MES"])["PRESUPUESTO"].sum().to_dict()
    return cat, sub, total, mensual


def presupuestos_para_dataframe(
    historico,
    df=None,
    periodos=None,
    categorias=None,
    subcategorias=None,
):
    """Calcula el presupuesto con el mismo periodo y clasificación de los gastos.

    ``periodos`` permite conservar meses sin movimientos. Si no se proporciona,
    se mantiene la compatibilidad usando los pares ANIO/MES del DataFrame.
    """
    if historico is None or historico.empty:
        return {}, {}, 0.0, {}

    if periodos is None:
        if df is None or df.empty or "ANIO" not in df.columns or "MES" not in df.columns:
            return {}, {}, 0.0, {}
        periodos = list(
            df[["ANIO", "MES"]]
            .dropna()
            .drop_duplicates()
            .itertuples(index=False, name=None)
        )

    claves = {
        (int(anio), normalizar_mes(mes))
        for anio, mes in periodos
        if pd.notna(anio) and normalizar_mes(mes) in MESES_NUM
    }
    if not claves:
        return {}, {}, 0.0, {}

    tmp = historico[
        historico.apply(
            lambda fila: (int(fila["ANIO"]), normalizar_mes(fila["MES"])) in claves,
            axis=1,
        )
    ].copy()

    if categorias is not None:
        categorias_norm = {normalizar(valor) for valor in categorias}
        tmp = tmp[tmp["CATEGORIA"].isin(categorias_norm)]
    if subcategorias is not None:
        subcategorias_norm = {normalizar(valor) for valor in subcategorias}
        tmp = tmp[tmp["CONCEPTO"].isin(subcategorias_norm)]

    if tmp.empty:
        return {}, {}, 0.0, {}
    cat = tmp.groupby("CATEGORIA")["PRESUPUESTO"].sum().to_dict()
    sub = tmp.groupby(["CATEGORIA", "CONCEPTO"])["PRESUPUESTO"].sum().to_dict()
    total = float(tmp["PRESUPUESTO"].sum())
    mensual = tmp.groupby(["ANIO", "MES"])["PRESUPUESTO"].sum().to_dict()
    return cat, sub, total, mensual


def presupuesto_categoria_mes(historico, categoria, mes, anio=None):
    if historico is None or historico.empty:
        return 0.0
    tmp = historico[(historico["CATEGORIA"] == normalizar(categoria)) & (historico["MES"] == normalizar_mes(mes))]
    if anio is not None:
        tmp = tmp[tmp["ANIO"] == int(anio)]
    return float(tmp["PRESUPUESTO"].sum())


def presupuesto_subcategoria_mes(historico, categoria, subcategoria, mes, anio=None):
    if historico is None or historico.empty:
        return 0.0
    tmp = historico[(historico["CATEGORIA"] == normalizar(categoria)) & (historico["CONCEPTO"] == normalizar(subcategoria)) & (historico["MES"] == normalizar_mes(mes))]
    if anio is not None:
        tmp = tmp[tmp["ANIO"] == int(anio)]
    return float(tmp["PRESUPUESTO"].sum())


def parse_presupuesto_datos(file):
    df = pd.read_excel(file, sheet_name="Datos", header=None)
    presupuesto_cat = {}
    presupuesto_sub = {}

    for start_row in range(len(df)):
        for cat_col in range(0, df.shape[1], 3):
            monto_col = cat_col + 1
            if monto_col >= df.shape[1]:
                continue
            header = df.iloc[start_row, cat_col]
            monto_header = df.iloc[start_row, monto_col]
            if pd.isna(header) or normalizar(monto_header) != "MONTO":
                continue

            categoria = normalizar(header)
            for i in range(start_row + 1, len(df)):
                sub = df.iloc[i, cat_col]
                monto = df.iloc[i, monto_col]
                if pd.isna(sub) and pd.isna(monto):
                    continue
                sub_nombre = str(sub).strip() if pd.notna(sub) else ""
                if normalizar(sub_nombre) == "TOTAL":
                    if pd.notna(monto):
                        presupuesto_cat[categoria] = float(monto)
                    break
                if pd.notna(sub) and pd.notna(monto):
                    try:
                        presupuesto_sub[(categoria, normalizar(sub_nombre))] = float(monto)
                    except (TypeError, ValueError):
                        pass

    return presupuesto_cat, presupuesto_sub


def leer_presupuesto_mensual_general(file):
    """Lee el presupuesto mensual general desde Datos!O19.

    Se usa como línea de referencia en Tendencias para comparar el gasto mensual
    contra el presupuesto total disponible del mes.
    """
    try:
        datos = pd.read_excel(file, sheet_name="Datos", header=None)
        valor = pd.to_numeric(datos.iloc[18, 14], errors="coerce")  # O19
        return float(valor) if pd.notna(valor) else 0.0
    except Exception:
        return 0.0



MESES_ORDEN = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
MESES_NUM = {m: i + 1 for i, m in enumerate(MESES_ORDEN)}


def normalizar_mes(valor):
    """Convierte cualquier forma del mes a ENE, FEB, MAR...

    Evita duplicados visuales como MAY/MAYO o JUN/JUNIO al cruzar ingresos y gastos.
    """
    if pd.isna(valor):
        return ""
    texto = normalizar(valor)
    mapa = {
        "1": "ENE", "01": "ENE", "ENERO": "ENE", "ENE": "ENE",
        "2": "FEB", "02": "FEB", "FEBRERO": "FEB", "FEB": "FEB",
        "3": "MAR", "03": "MAR", "MARZO": "MAR", "MAR": "MAR",
        "4": "ABR", "04": "ABR", "ABRIL": "ABR", "ABR": "ABR",
        "5": "MAY", "05": "MAY", "MAYO": "MAY", "MAY": "MAY",
        "6": "JUN", "06": "JUN", "JUNIO": "JUN", "JUN": "JUN",
        "7": "JUL", "07": "JUL", "JULIO": "JUL", "JUL": "JUL",
        "8": "AGO", "08": "AGO", "AGOSTO": "AGO", "AGO": "AGO",
        "9": "SEP", "09": "SEP", "SEPTIEMBRE": "SEP", "SETIEMBRE": "SEP", "SEP": "SEP", "SET": "SEP",
        "10": "OCT", "OCTUBRE": "OCT", "OCT": "OCT",
        "11": "NOV", "NOVIEMBRE": "NOV", "NOV": "NOV",
        "12": "DIC", "DICIEMBRE": "DIC", "DIC": "DIC",
    }
    return mapa.get(texto, texto)


def ordenar_por_mes(df, col="MES"):
    tmp = df.copy()
    tmp[col] = tmp[col].map(normalizar_mes)
    tmp["_MES_ORDEN"] = tmp[col].map(lambda x: MESES_NUM.get(str(x).strip().upper(), 99))
    tmp = tmp.sort_values("_MES_ORDEN").drop(columns="_MES_ORDEN")
    return tmp


def construir_flujo_mensual(
    gastos_df,
    ingresos_df,
    meses_sel=None,
    presupuesto_mensual=0,
    periodos_sel=None,
):
    """Construye una sola tabla mensual para todas las gráficas ejecutivas.

    La clave es normalizar el mes antes de agrupar y combinar, de manera que
    ingresos y gastos compartan un único eje X.
    """
    def _periodos_dataframe(frame, fecha_columna):
        if frame is None or frame.empty:
            return pd.Series(dtype="period[M]")
        if fecha_columna in frame.columns:
            fechas = pd.to_datetime(frame[fecha_columna], errors="coerce")
            return fechas.dt.to_period("M")
        if {"ANIO", "MES"}.issubset(frame.columns):
            fechas = frame.apply(
                lambda fila: pd.Timestamp(
                    year=int(fila["ANIO"]),
                    month=MESES_NUM.get(normalizar_mes(fila["MES"]), 1),
                    day=1,
                ) if pd.notna(fila["ANIO"]) and normalizar_mes(fila["MES"]) in MESES_NUM else pd.NaT,
                axis=1,
            )
            return pd.to_datetime(fechas, errors="coerce").dt.to_period("M")
        return pd.Series(pd.NaT, index=frame.index, dtype="period[M]")

    if periodos_sel:
        periodos_base = []
        for valor in periodos_sel:
            if isinstance(valor, tuple) and len(valor) == 2:
                anio, mes = valor
                mes_norm = normalizar_mes(mes)
                if pd.notna(anio) and mes_norm in MESES_NUM:
                    periodos_base.append(pd.Period(year=int(anio), month=MESES_NUM[mes_norm], freq="M"))
            else:
                try:
                    periodos_base.append(pd.Period(valor, freq="M"))
                except (TypeError, ValueError):
                    continue
    else:
        periodos_base = list(_periodos_dataframe(gastos_df, "GASTOS_FECHA").dropna())
        periodos_base += list(_periodos_dataframe(ingresos_df, "INGRESOS_FECHA").dropna())
        if not periodos_base and meses_sel:
            anio_actual = int(pd.Timestamp.today().year)
            periodos_base = [
                pd.Period(year=anio_actual, month=MESES_NUM[m], freq="M")
                for m in (normalizar_mes(x) for x in meses_sel)
                if m in MESES_NUM
            ]

    periodos_base = sorted(set(periodos_base))
    if not periodos_base:
        return pd.DataFrame(columns=[
            "PERIODO", "ANIO", "MES_NOMBRE", "MES", "Gastos", "Ingresos",
            "Presupuesto mensual", "Balance", "Balance acumulado",
            "Diferencia vs presupuesto", "Capacidad ahorro %",
            "Estado balance", "Estado presupuesto",
        ])

    gastos_tmp = gastos_df.copy()
    if not gastos_tmp.empty:
        gastos_tmp["PERIODO"] = _periodos_dataframe(gastos_tmp, "GASTOS_FECHA")
        gastos_mes = (
            gastos_tmp.dropna(subset=["PERIODO"]).groupby("PERIODO", as_index=False)["GASTOS_CANTIDAD"]
            .sum()
            .rename(columns={"GASTOS_CANTIDAD": "Gastos"})
        )
    else:
        gastos_mes = pd.DataFrame(columns=["PERIODO", "Gastos"])

    ingresos_tmp = ingresos_df.copy()
    if not ingresos_tmp.empty:
        ingresos_tmp["PERIODO"] = _periodos_dataframe(ingresos_tmp, "INGRESOS_FECHA")
        ingresos_mes = (
            ingresos_tmp.dropna(subset=["PERIODO"]).groupby("PERIODO", as_index=False)["INGRESOS_CANTIDAD"]
            .sum()
            .rename(columns={"INGRESOS_CANTIDAD": "Ingresos"})
        )
    else:
        ingresos_mes = pd.DataFrame(columns=["PERIODO", "Ingresos"])

    flujo = pd.DataFrame({"PERIODO": periodos_base})
    flujo = flujo.merge(gastos_mes, on="PERIODO", how="left")
    flujo = flujo.merge(ingresos_mes, on="PERIODO", how="left")
    flujo[["Gastos", "Ingresos"]] = flujo[["Gastos", "Ingresos"]].fillna(0)
    flujo["ANIO"] = flujo["PERIODO"].map(lambda periodo: int(periodo.year))
    flujo["MES_NOMBRE"] = flujo["PERIODO"].map(lambda periodo: MESES_ORDEN[int(periodo.month) - 1])
    varios_anios = flujo["ANIO"].nunique() > 1
    flujo["MES"] = flujo.apply(
        lambda fila: f"{fila['MES_NOMBRE']} {fila['ANIO']}" if varios_anios else fila["MES_NOMBRE"],
        axis=1,
    )
    if isinstance(presupuesto_mensual, dict):
        def _pres_mes(fila):
            return float(presupuesto_mensual.get((int(fila["ANIO"]), fila["MES_NOMBRE"]), 0.0) or 0.0)
        flujo["Presupuesto mensual"] = flujo.apply(_pres_mes, axis=1)
    else:
        flujo["Presupuesto mensual"] = float(presupuesto_mensual or 0)
    flujo["Balance"] = flujo["Ingresos"] - flujo["Gastos"]
    flujo["Balance acumulado"] = flujo["Balance"].cumsum()
    flujo["Diferencia vs presupuesto"] = flujo["Gastos"] - flujo["Presupuesto mensual"]
    flujo["Capacidad ahorro %"] = flujo.apply(lambda r: (r["Balance"] / r["Ingresos"] * 100) if r["Ingresos"] else 0, axis=1)
    flujo["Estado balance"] = flujo["Balance"].apply(
        lambda x: "Ganó más de lo que gastó" if x > 0 else "Gastó más de lo que ganó" if x < 0 else "Ingresos y gastos iguales"
    )
    flujo["Estado presupuesto"] = flujo["Diferencia vs presupuesto"].apply(
        lambda x: "Sobre presupuesto" if x > 0 else "Bajo presupuesto" if x < 0 else "En presupuesto"
    )
    return flujo


def parse_ingresos_hoja(file, anio_ref=2026):
    """Lee la hoja Ingresos aunque venga como matriz ENE-DIC.

    Salida estándar compatible con el dashboard:
    MES, INGRESOS_FECHA, INGRESOS_CANTIDAD, INGRESOS_DESCRIPCION,
    INGRESOS_CATEGORIA, INGRESOS_FUENTE, ANIO
    """
    try:
        raw = pd.read_excel(file, sheet_name="Ingresos", header=None)
    except Exception:
        return pd.DataFrame(columns=[
            "MES", "INGRESOS_FECHA", "INGRESOS_CANTIDAD", "INGRESOS_DESCRIPCION",
            "INGRESOS_CATEGORIA", "INGRESOS_FUENTE", "ANIO"
        ])

    registros = []
    tipo_actual = None

    for i in range(len(raw)):
        primera = raw.iloc[i, 0]
        primera_n = normalizar(primera)

        if primera_n in {"CATEGORIA LABORAL", "CATEGORIA NO LABORAL"}:
            tipo_actual = "LABORAL" if "LABORAL" in primera_n and "NO" not in primera_n else "NO LABORAL"
            continue

        if primera_n in {"TOTAL", "TOTAL GENERAL", "INGRESO"}:
            if primera_n == "INGRESO":
                break
            continue

        if pd.isna(primera) or tipo_actual is None:
            continue

        fuente = str(primera).strip()
        if not fuente or fuente.lower() == "nan":
            continue

        for mes in MESES_ORDEN:
            col_mes = None
            # En el archivo los meses están desde la columna 3, pero buscamos por seguridad.
            for c in range(raw.shape[1]):
                if normalizar(raw.iloc[0, c]) == mes or normalizar(raw.iloc[8, c]) == mes:
                    col_mes = c
                    break
            if col_mes is None:
                continue
            valor = pd.to_numeric(raw.iloc[i, col_mes], errors="coerce")
            if pd.isna(valor) or float(valor) == 0:
                continue
            registros.append({
                "MES": mes,
                "INGRESOS_FECHA": pd.Timestamp(year=int(anio_ref), month=MESES_NUM[mes], day=1),
                "INGRESOS_CANTIDAD": float(valor),
                "INGRESOS_DESCRIPCION": fuente,
                "INGRESOS_CATEGORIA": tipo_actual,
                "INGRESOS_FUENTE": fuente,
                "ANIO": int(anio_ref),
            })

    ingresos = pd.DataFrame(registros)

    # Si la matriz no trae datos, intenta leer el bloque inferior INGRESO/FUENTE/VALOR/FECHA.
    if ingresos.empty:
        header_rows = raw.index[raw.iloc[:, 0].astype(str).str.upper().str.strip().eq("INGRESO")].tolist()
        if header_rows:
            h = header_rows[0]
            detalle = raw.iloc[h + 1:, [0, 1, 2, 3]].copy()
            detalle.columns = ["INGRESOS_DESCRIPCION", "INGRESOS_CATEGORIA", "INGRESOS_CANTIDAD", "INGRESOS_FECHA"]
            detalle["INGRESOS_CANTIDAD"] = pd.to_numeric(detalle["INGRESOS_CANTIDAD"], errors="coerce")
            detalle = detalle.dropna(subset=["INGRESOS_CANTIDAD"])
            detalle["INGRESOS_FECHA"] = pd.to_datetime(detalle["INGRESOS_FECHA"], errors="coerce")
            detalle["ANIO"] = detalle["INGRESOS_FECHA"].dt.year.fillna(anio_ref).astype(int)
            detalle["MES"] = detalle["INGRESOS_FECHA"].dt.month.map({v: k for k, v in MESES_NUM.items()}).fillna("SIN MES")
            detalle["INGRESOS_FUENTE"] = detalle["INGRESOS_DESCRIPCION"]
            ingresos = detalle[["MES", "INGRESOS_FECHA", "INGRESOS_CANTIDAD", "INGRESOS_DESCRIPCION", "INGRESOS_CATEGORIA", "INGRESOS_FUENTE", "ANIO"]]

    return ingresos



def etiqueta_tipo_ingreso(tipo):
    """Clasifica con prioridad explícita: laboral, no laboral o sin clasificar.

    Evita el error de coincidencia parcial donde ``NO LABORAL`` terminaba
    clasificado como laboral porque contiene la palabra ``LABOR``.
    """
    tipo_n = normalizar(tipo).replace("-", " ")
    tipo_n = " ".join(tipo_n.split())
    no_laborales = {
        "NO LABORAL", "NO LABORALES", "NO LABOR", "NO LABORALES",
        "RENTAS", "RENDIMIENTOS", "INVERSION", "INVERSIONES",
    }
    laborales = {
        "LABORAL", "LABORALES", "SALARIO", "SALARIAL", "NOMINA",
        "HONORARIOS", "EMPLEO", "TRABAJO",
    }
    if tipo_n in no_laborales or tipo_n.startswith("NO LABOR"):
        return "No laborales"
    if tipo_n in laborales:
        return "Laborales"
    if any(palabra in tipo_n for palabra in ["SALAR", "NOMINA", "HONOR", "EMPLEO", "TRABAJO"]):
        return "Laborales"
    if tipo_n in {"", "NAN", "NONE", "SIN TIPO", "SIN CLASIFICAR"}:
        return "Sin clasificar"
    return "Sin clasificar"


def fig_mapa_ingresos_tipo_fuente(ingresos_df):
    """Mapa ejecutivo: Ingresos → tipo de fuente → fuente específica.

    Construye manualmente ids/labels/parents/values y un tooltip de texto ya
    calculado para CADA nodo (raíz, tipo de fuente y fuente). Esto evita que
    Plotly muestre "undefined" en los nodos agregados (raíz y tipo de fuente),
    algo que sí ocurre si se usa `custom_data` de px.treemap directamente,
    porque esas columnas solo existen a nivel de fila (fuente) y no se
    agregan automáticamente hacia los nodos padre.
    """
    if ingresos_df.empty:
        return go.Figure()

    tmp = ingresos_df.copy()
    tmp["TIPO_FUENTE"] = tmp["INGRESOS_CATEGORIA"].map(etiqueta_tipo_ingreso)
    tmp["INGRESOS_FUENTE"] = tmp["INGRESOS_FUENTE"].fillna(tmp["INGRESOS_DESCRIPCION"]).astype(str).str.strip()

    mapa = (
        tmp.groupby(["TIPO_FUENTE", "INGRESOS_FUENTE"], as_index=False)
        .agg(INGRESOS_CANTIDAD=("INGRESOS_CANTIDAD", "sum"))
        .sort_values(["TIPO_FUENTE", "INGRESOS_CANTIDAD"], ascending=[True, False])
    )
    total = float(mapa["INGRESOS_CANTIDAD"].sum()) or 1.0
    color_por_tipo = {"Laborales": "#00FF88", "No laborales": "#00B7FF", "Sin clasificar": "#B026FF"}

    raiz_id = "Ingresos"
    ids, labels, parents, values, tooltips, colores = [], [], [], [], [], []

    ids.append(raiz_id)
    labels.append(raiz_id)
    parents.append("")
    values.append(total)
    tooltips.append(f"<b>{raiz_id}</b><br>Total: ${total:,.0f}<br>Participación: 100.0%")
    colores.append("#111827")

    for tipo_fuente, grupo_tipo in mapa.groupby("TIPO_FUENTE", sort=False):
        tipo_id = f"{raiz_id}/{tipo_fuente}"
        total_tipo = float(grupo_tipo["INGRESOS_CANTIDAD"].sum())
        pct_tipo_total = (total_tipo / total * 100) if total else 0
        color_tipo = color_por_tipo.get(str(tipo_fuente), "#A78BFA")

        ids.append(tipo_id)
        labels.append(str(tipo_fuente))
        parents.append(raiz_id)
        values.append(total_tipo)
        tooltips.append(
            f"<b>{tipo_fuente}</b><br>Total: ${total_tipo:,.0f}<br>"
            f"Participación del total: {pct_tipo_total:.1f}%"
        )
        colores.append(color_tipo)

        for _, fila in grupo_tipo.iterrows():
            fuente = str(fila["INGRESOS_FUENTE"])
            monto = float(fila["INGRESOS_CANTIDAD"])
            pct_total = (monto / total * 100) if total else 0
            pct_tipo = (monto / total_tipo * 100) if total_tipo else 0
            fuente_id = f"{tipo_id}/{fuente}"

            ids.append(fuente_id)
            labels.append(fuente)
            parents.append(tipo_id)
            values.append(monto)
            tooltips.append(
                f"<b>{fuente}</b><br>Ingreso: ${monto:,.0f}<br>"
                f"Participación total: {pct_total:.1f}%<br>"
                f"Participación dentro del tipo: {pct_tipo:.1f}%<br>"
                f"Total tipo ({tipo_fuente}): ${total_tipo:,.0f}"
            )
            colores.append(color_tipo)

    fig = go.Figure(
        go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            customdata=tooltips,
            texttemplate="<b>%{label}</b><br>$%{value:,.0f}",
            hovertemplate="%{customdata}<extra></extra>",
            marker=dict(colors=colores, line=dict(color="#020617", width=2)),
            root_color="#111827",
            hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="#34D399", font=dict(size=13, color="#f8fafc")),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=620,
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#e2e8f0"),
        margin=dict(t=50, b=20, l=10, r=10),
    )
    return fig


def crear_gauge_salud(balance, ingresos):
    pct = (balance / ingresos * 100) if ingresos else 0
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number={"suffix": "%", "font": {"color": "#f8fafc"}},
        delta={"reference": 20, "suffix": "%", "increasing": {"color": "#39FF14"}, "decreasing": {"color": "#FF0033"}},
        title={"text": "Capacidad de ahorro / balance", "font": {"color": "#00F0FF"}},
        gauge={
            "axis": {"range": [-100, 100], "tickcolor": "#94a3b8"},
            "bar": {"color": "#00F0FF"},
            "bgcolor": "#0a0a0a",
            "borderwidth": 1,
            "bordercolor": "#00D9FF",
            "steps": [
                {"range": [-100, 0], "color": "#4a0012"},
                {"range": [0, 20], "color": "#4a3b00"},
                {"range": [20, 100], "color": "#003d1a"},
            ],
        },
    ))
    fig.update_layout(template="plotly_dark", height=360, paper_bgcolor="#000000", plot_bgcolor="#000000", font=dict(color="#e2e8f0"))
    return fig

def clasificar_tipo_gasto(row):
    """Clasifica cada gasto por tipo, respetando primero el valor digitado en Excel.

    La hoja Transaccional puede traer la columna "Fijo/Variable"; al cargar el Excel
    se renombra internamente como TIPO_GASTO. También se aceptan nombres alternativos
    para mantener compatibilidad con otras plantillas.
    """
    columnas_tipo = [
        "TIPO_GASTO", "TIPO", "FIJO_VARIABLE", "FIJO/VARIABLE",
        "Fijo/Variable", "CLASIFICACION", "CLASIFICACIÓN"
    ]

    for col in columnas_tipo:
        if col in row.index and pd.notna(row[col]):
            valor = normalizar(row[col])
            if "EXTRAORDINARIO" in valor or "IMPREVISTO" in valor or "OCASIONAL" in valor:
                return "Extraordinario"
            if "PRESCINDIBLE" in valor or "DISCRECIONAL" in valor or "GUSTO" in valor:
                return "Prescindible"
            if "FIJO" in valor:
                return "Fijo"
            if "VARIABLE" in valor:
                return "Variable"

    texto = " ".join([
        normalizar(row.get("GASTOS_CATEGORIA", "")),
        normalizar(row.get("GASTOS_SUBCATEGORIA", "")),
        normalizar(row.get("GASTOS_SUBCATEGORIA_2", "")),
        normalizar(row.get("GASTOS_DESCRIPCION", "")),
        normalizar(row.get("GASTOS_OBSERVACION", "")),
    ])

    claves_extraordinarias = [
        "EXTRAORDINARIO", "IMPREVISTO", "EMERGENCIA", "REPARACION", "ARREGLO",
        "MULTA", "IMPUESTO", "COMPRA RELOJ", "COMPRA AMAZON", "EVENTUAL", "OCASIONAL",
    ]
    claves_prescindibles = [
        "PRESCINDIBLE", "DISCRECIONAL", "GUSTO", "OCIO", "RUMBA", "CINE",
        "LICOR", "STREAMING", "RESTAURANTE", "DOMICILIO", "COMIDA RAPIDA",
    ]
    claves_fijas = [
        "ARRIENDO", "ALQUILER", "CANON", "ADMINISTRACION", "HIPOTECA",
        "CUOTA", "CREDITO", "PRESTAMO", "SEGURO", "POLIZA",
        "INTERNET", "WIFI", "PLAN CELULAR", "TELEFONIA", "TELEFONO",
        "NETFLIX", "SPOTIFY", "SUSCRIPCION", "MEMBRESIA",
        "COLEGIO", "UNIVERSIDAD", "MATRICULA", "PENSION",
        "SERVICIO", "SERVICIOS PUBLICOS", "ENERGIA", "LUZ", "AGUA", "GAS",
    ]
    claves_variables = [
        "MERCADO", "SUPERMERCADO", "COMIDA", "TRANSPORTE", "GASOLINA",
        "TAXI", "UBER", "DIDI", "ROPA", "CALZADO", "SALUD", "MEDICAMENTO",
        "FARMACIA", "VIAJE", "REGALO", "VARIOS", "COMPRA",
    ]

    if any(k in texto for k in claves_extraordinarias):
        return "Extraordinario"
    if any(k in texto for k in claves_prescindibles):
        return "Prescindible"
    if any(k in texto for k in claves_fijas):
        return "Fijo"
    if any(k in texto for k in claves_variables):
        return "Variable"
    return "Variable"


def agregar_tipo_gasto(df_gastos):
    tmp = df_gastos.copy()
    if tmp.empty:
        tmp["TIPO_GASTO"] = []
        return tmp
    tmp["TIPO_GASTO"] = tmp.apply(clasificar_tipo_gasto, axis=1)
    return tmp


def fig_fijos_variables_mensual(tipo_mes):
    if tipo_mes.empty:
        return go.Figure()
    fig = px.bar(
        tipo_mes,
        x="MES",
        y="GASTOS_CANTIDAD",
        color="TIPO_GASTO",
        barmode="group",
        text="GASTOS_CANTIDAD",
        category_orders={"MES": MESES_ORDEN, "TIPO_GASTO": ["Fijo", "Variable", "Extraordinario", "Prescindible"]},
        color_discrete_map={
            "Fijo": "#00D9FF",
            "Variable": "#FF2E6E",
            "Extraordinario": "#FFEE00",
            "Prescindible": "#B026FF",
        },
    )
    fig.update_traces(
        texttemplate="$%{text:,.0f}",
        textposition="outside",
        marker=dict(line=dict(color="rgba(255,255,255,0.25)", width=1)),
        hovertemplate="Mes: %{x}<br>Tipo: %{fullData.name}<br>Gasto: $%{y:,.0f}<extra></extra>",
    )
    fig.update_layout(
        xaxis_title="Mes",
        yaxis_title="Valor",
        legend_title="Tipo de gasto",
        bargap=0.25,
    )
    return estilo_grafico(fig, "Gastos por tipo: fijo, variable y extraordinario")


def fig_fijos_variables_pie(tipo_resumen):
    if tipo_resumen.empty:
        return go.Figure()
    fig = px.pie(
        tipo_resumen,
        names="TIPO_GASTO",
        values="GASTOS_CANTIDAD",
        hole=0.45,
        color="TIPO_GASTO",
        color_discrete_map={
            "Fijo": "#00D9FF",
            "Variable": "#FF2E6E",
            "Extraordinario": "#FFEE00",
            "Prescindible": "#B026FF",
        },
    )
    fig.update_traces(
        textinfo="percent+label",
        textfont=dict(color="#ffffff", size=12),
        marker=dict(line=dict(color="#000000", width=2)),
        hovertemplate="<b>%{label}</b><br>Gasto: $%{value:,.0f}<br>Participación: %{percent}<extra></extra>",
    )
    return estilo_grafico(fig, "Participación de gastos por tipo")



def normalizar_columnas_patrimonio(df):
    """Estandariza los nombres de columnas esperados para la hoja Patrimonio."""
    mapa = {}
    equivalencias = {
        "FECHA": "Fecha",
        "TIPO": "Tipo",
        "CLASIFICACION": "Tipo",
        "TIPO DE PRODUCTO": "Tipo de producto",
        "TIPO PRODUCTO": "Tipo de producto",
        "DISPONIBILIDAD EFECTIVO": "Disponibilidad de efectivo",
        "DISPONIBILIDAD DE EFECTIVO": "Disponibilidad de efectivo",
        "CATEGORIA": "Categoría",
        "SUBCATEGORIA": "Subcategoría",
        "DESCRIPCION": "Descripción",
        "ENTIDAD": "Entidad",
        "ENTIDAD/TITULAR": "Entidad",
        "ENTIDAD / TITULAR": "Entidad",
        "VALOR ACTUAL": "Valor actual",
        "VALOR_ACTUAL": "Valor actual",
        "SALDO PENDIENTE": "Saldo pendiente",
        "SALDO_PENDIENTE": "Saldo pendiente",
        "VALOR NETO": "Valor neto",
        "VALOR_NETO": "Valor neto",
        "FECHA COMPRA": "Fecha compra",
        "FHCAH DE COMPRA": "Fecha compra",
        "FECHA DE COMPRA": "Fecha compra",
        "FECHA VALORACION": "Fecha valoración",
        "FECHA DE VALORACION": "Fecha valoración",
        "FECHA VALORACIÓN": "Fecha valoración",
        "ESTADO": "Estado",
        "OBSERVACIONES": "Observaciones",
        "OBRESVACIONES": "Observaciones",
        "OBSERVACION": "Observaciones",
        "LIQUIDEZ": "Liquidez",
        "PORCENTAJE": "Porcentaje",
        "PORCENTAJE PROPIEDAD": "Porcentaje",
        "PORCENTAJE DE PROPIEDAD": "Porcentaje",
        "MONEDA": "Moneda",
        "DIVISA": "Moneda",
        "TASA A COP": "Tasa a COP",
        "TASA DE CAMBIO": "Tasa a COP",
    }
    for col in df.columns:
        clave = normalizar(col)
        if clave in equivalencias:
            mapa[col] = equivalencias[clave]
    df = df.rename(columns=mapa)
    columnas = [
        "Fecha", "Tipo", "Tipo de producto", "Disponibilidad de efectivo", "Liquidez",
        "Categoría", "Subcategoría", "Descripción", "Entidad", "Porcentaje",
        "Valor actual", "Saldo pendiente", "Valor neto", "Fecha compra",
        "Fecha valoración", "Estado", "Observaciones", "Moneda", "Tasa a COP",
    ]
    for col in columnas:
        if col not in df.columns:
            df[col] = pd.NA
    return df[columnas]


@st.cache_data(ttl=21600, show_spinner=False)
def obtener_trm_colombia():
    """Consulta la TRM USD/COP oficial publicada por la Superfinanciera."""
    endpoint = (
        "https://www.datos.gov.co/resource/32sa-8pi3.json"
        "?%24select=valor%2Cunidad%2Cvigenciadesde%2Cvigenciahasta"
        "&%24order=vigenciadesde%20DESC&%24limit=1"
    )
    resultado = {
        "valor": None,
        "unidad": "COP por USD",
        "vigencia_desde": None,
        "vigencia_hasta": None,
        "fuente": "Superintendencia Financiera de Colombia",
        "url": "https://www.datos.gov.co/resource/32sa-8pi3",
        "disponible": False,
        "mensaje": "No fue posible consultar la TRM en este momento.",
    }
    try:
        solicitud = Request(endpoint, headers={"User-Agent": "Altium-Financiero-V14/1.0"})
        with urlopen(solicitud, timeout=7) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        if datos:
            valor = float(datos[0].get("valor", 0))
            if valor > 0:
                resultado.update({
                    "valor": valor,
                    "unidad": datos[0].get("unidad") or "COP por USD",
                    "vigencia_desde": datos[0].get("vigenciadesde"),
                    "vigencia_hasta": datos[0].get("vigenciahasta"),
                    "disponible": True,
                    "mensaje": "TRM oficial consultada correctamente.",
                })
    except Exception:
        pass
    return resultado


def normalizar_moneda_patrimonio(valor):
    """Convierte nombres habituales de divisas a códigos ISO legibles."""
    moneda = normalizar(valor)
    equivalencias = {
        "": "COP", "NAN": "COP", "NONE": "COP", "PESO": "COP", "PESOS": "COP",
        "PESO COLOMBIANO": "COP", "PESOS COLOMBIANOS": "COP", "COP": "COP",
        "DOLAR": "USD", "DOLARES": "USD", "DOLAR AMERICANO": "USD", "USD": "USD",
        "EURO": "EUR", "EUROS": "EUR", "EUR": "EUR",
        "LIBRA": "GBP", "LIBRAS": "GBP", "GBP": "GBP",
    }
    return equivalencias.get(moneda, moneda[:12] or "COP")


def leer_deudas_excel(file):
    """Lee pasivos desde la hoja Pasivos o, por compatibilidad, Deudas."""
    columnas = [
        "Nombre", "Tipo", "Deuda inicial", "Interés", "Saldo",
        "Avance Excel", "Inicio del crédito", "Pago mensual", "Hoja origen",
    ]
    raw = None
    hoja_origen = None
    for hoja in ("Pasivos", "Deudas"):
        try:
            raw = pd.read_excel(file, sheet_name=hoja)
            hoja_origen = hoja
            break
        except Exception:
            continue

    if raw is None or raw.empty:
        return pd.DataFrame(columns=columnas)

    equivalencias = {
        "ENTIDAD": "Nombre",
        "NOMBRE": "Nombre",
        "ACREEDOR": "Nombre",
        "TIPO": "Tipo",
        "TIPO DE DEUDA": "Tipo",
        "DEUDA": "Deuda inicial",
        "DEUDA INICIAL": "Deuda inicial",
        "VALOR INICIAL": "Deuda inicial",
        "INTERES": "Interés",
        "INTERES NM": "Interés",
        "INTERES MENSUAL": "Interés",
        "SALDO": "Saldo",
        "SALDO PENDIENTE": "Saldo",
        "AVANCE": "Avance Excel",
        "AVANCE EXCEL": "Avance Excel",
        "INICIO DEL CREDITO": "Inicio del crédito",
        "FECHA INICIO": "Inicio del crédito",
        "PAGO MENSUAL": "Pago mensual",
        "CUOTA MENSUAL": "Pago mensual",
    }
    mapa = {
        col: equivalencias[normalizar(col)]
        for col in raw.columns
        if normalizar(col) in equivalencias
    }
    deudas = raw.rename(columns=mapa).copy()

    for col in columnas[:-1]:
        if col not in deudas.columns:
            deudas[col] = pd.NA
    deudas["Hoja origen"] = hoja_origen
    deudas["Nombre"] = deudas["Nombre"].astype("string").str.strip()
    deudas = deudas[
        deudas["Nombre"].notna()
        & deudas["Nombre"].ne("")
        & deudas["Nombre"].str.lower().ne("nan")
    ].copy()

    for col in ["Deuda inicial", "Interés", "Saldo", "Avance Excel", "Pago mensual"]:
        deudas[col] = pd.to_numeric(deudas[col], errors="coerce")
    deudas["Deuda inicial"] = deudas["Deuda inicial"].fillna(deudas["Saldo"]).fillna(0).clip(lower=0)
    deudas["Saldo"] = deudas["Saldo"].fillna(deudas["Deuda inicial"]).fillna(0).clip(lower=0)
    deudas["Interés"] = deudas["Interés"].fillna(0).clip(lower=0)
    deudas["Avance Excel"] = deudas["Avance Excel"].fillna(0)
    deudas["Pago mensual"] = deudas["Pago mensual"].fillna(0).clip(lower=0)
    deudas["Inicio del crédito"] = pd.to_datetime(deudas["Inicio del crédito"], errors="coerce")
    deudas["Tipo"] = deudas["Tipo"].fillna("Deuda").astype(str).str.strip().str.title()
    return deudas[columnas].reset_index(drop=True)


def convertir_deudas_a_patrimonio(deudas):
    """Convierte los saldos vigentes de Pasivos/Deudas al formato patrimonial."""
    columnas = [
        "Fecha", "Tipo", "Tipo de producto", "Disponibilidad de efectivo", "Liquidez",
        "Categoría", "Subcategoría", "Descripción", "Entidad", "Porcentaje",
        "Valor actual", "Saldo pendiente", "Valor neto", "Fecha compra",
        "Fecha valoración", "Estado", "Observaciones", "Moneda", "Valor original",
        "Tasa a COP", "Conversión disponible",
    ]
    if deudas is None or deudas.empty:
        return pd.DataFrame(columns=columnas)

    pasivos = pd.DataFrame(index=deudas.index)
    pasivos["Fecha"] = deudas["Inicio del crédito"]
    pasivos["Tipo"] = "Pasivo"
    pasivos["Tipo de producto"] = deudas["Tipo"].fillna("Deuda")
    pasivos["Disponibilidad de efectivo"] = "No aplica"
    pasivos["Liquidez"] = "No aplica"
    pasivos["Categoría"] = "Deudas"
    pasivos["Subcategoría"] = deudas["Tipo"].fillna("Deuda")
    pasivos["Descripción"] = deudas["Nombre"]
    pasivos["Entidad"] = deudas["Nombre"]
    pasivos["Porcentaje"] = 1.0
    pasivos["Valor actual"] = deudas["Saldo"]
    pasivos["Saldo pendiente"] = deudas["Saldo"]
    pasivos["Valor neto"] = -deudas["Saldo"].abs()
    pasivos["Fecha compra"] = deudas["Inicio del crédito"]
    pasivos["Fecha valoración"] = pd.NaT
    pasivos["Estado"] = deudas["Saldo"].gt(0).map({True: "Activo", False: "Pagado"})
    pasivos["Observaciones"] = "Origen: hoja " + deudas["Hoja origen"].fillna("Pasivos").astype(str)
    pasivos["Moneda"] = "COP"
    pasivos["Valor original"] = deudas["Saldo"]
    pasivos["Tasa a COP"] = 1.0
    pasivos["Conversión disponible"] = True
    return pasivos[columnas].reset_index(drop=True)


@st.cache_data
def leer_patrimonio_excel(file, trm_usd_cop=None):
    """Lee la hoja Patrimonio si existe y prepara datos para gráficos ejecutivos."""
    columnas = [
        "Fecha", "Tipo", "Tipo de producto", "Disponibilidad de efectivo", "Liquidez",
        "Categoría", "Subcategoría", "Descripción", "Entidad", "Porcentaje",
        "Valor actual", "Saldo pendiente", "Valor neto", "Fecha compra",
        "Fecha valoración", "Estado", "Observaciones", "Moneda", "Valor original",
        "Tasa a COP", "Conversión disponible",
    ]
    try:
        raw = pd.read_excel(file, sheet_name="Patrimonio")
    except Exception:
        return pd.DataFrame(columns=columnas)

    patrimonio = normalizar_columnas_patrimonio(raw)
    patrimonio = patrimonio.dropna(how="all")
    if patrimonio.empty:
        patrimonio = pd.DataFrame(columns=columnas)

    patrimonio["Tipo"] = patrimonio["Tipo"].fillna("Activo").astype(str).str.strip().str.title()
    patrimonio["Categoría"] = patrimonio["Categoría"].fillna("Sin categoría").astype(str).str.strip()
    patrimonio["Subcategoría"] = patrimonio["Subcategoría"].fillna("Sin subcategoría").astype(str).str.strip()
    patrimonio["Descripción"] = patrimonio["Descripción"].fillna("Sin descripción").astype(str).str.strip()
    patrimonio["Entidad"] = patrimonio["Entidad"].fillna("Sin entidad").astype(str).str.strip()
    patrimonio["Estado"] = patrimonio["Estado"].fillna("Activo").astype(str).str.strip().str.title()
    patrimonio["Liquidez"] = patrimonio["Liquidez"].fillna("Sin clasificar").astype(str).str.strip().str.title()
    patrimonio["Tipo de producto"] = patrimonio["Tipo de producto"].fillna("Sin clasificar").astype(str).str.strip().str.title()
    patrimonio["Disponibilidad de efectivo"] = patrimonio["Disponibilidad de efectivo"].fillna("Sin clasificar").astype(str).str.strip().str.title()

    for col in ["Valor actual", "Saldo pendiente", "Valor neto"]:
        patrimonio[col] = pd.to_numeric(patrimonio[col], errors="coerce").fillna(0)

    patrimonio["Porcentaje"] = pd.to_numeric(patrimonio["Porcentaje"], errors="coerce").fillna(1.0)
    patrimonio.loc[patrimonio["Porcentaje"] > 1, "Porcentaje"] /= 100.0
    patrimonio["Porcentaje"] = patrimonio["Porcentaje"].clip(lower=0, upper=1)

    patrimonio["Fecha"] = pd.to_datetime(patrimonio["Fecha"], errors="coerce")
    patrimonio["Fecha compra"] = pd.to_datetime(patrimonio["Fecha compra"], errors="coerce")
    patrimonio["Fecha valoración"] = pd.to_datetime(patrimonio["Fecha valoración"], errors="coerce")

    # Si la fórmula del fondo de emergencia llega sin valor calculado, se reconstruye
    # desde las consignaciones de la hoja Dale.
    fondo_mask = patrimonio["Categoría"].map(normalizar).eq("FONDO DE EMERGENCIA")
    if fondo_mask.any() and patrimonio.loc[fondo_mask, "Valor actual"].eq(0).any():
        try:
            dale_aportes = pd.read_excel(file, sheet_name="Dale", usecols="A", header=None)
            fondo_dale = float(pd.to_numeric(dale_aportes.iloc[:, 0], errors="coerce").fillna(0).sum())
            patrimonio.loc[fondo_mask & patrimonio["Valor actual"].eq(0), "Valor actual"] = fondo_dale
        except Exception:
            pass

    # Conserva el saldo escrito en la moneda original y convierte a COP para que
    # todas las tarjetas y diagnósticos trabajen sobre una unidad comparable.
    patrimonio["Moneda"] = patrimonio["Moneda"].map(normalizar_moneda_patrimonio)
    patrimonio["Valor original"] = patrimonio["Valor actual"]
    if trm_usd_cop is None:
        trm_usd_cop = obtener_trm_colombia().get("valor")
    trm_usd_cop = pd.to_numeric(trm_usd_cop, errors="coerce")
    tasas = pd.to_numeric(patrimonio["Tasa a COP"], errors="coerce")
    tasas.loc[patrimonio["Moneda"].eq("COP")] = 1.0
    if pd.notna(trm_usd_cop) and float(trm_usd_cop) > 0:
        tasas.loc[patrimonio["Moneda"].eq("USD")] = float(trm_usd_cop)
    patrimonio["Tasa a COP"] = tasas
    patrimonio["Conversión disponible"] = patrimonio["Tasa a COP"].notna()
    for col in ["Valor actual", "Saldo pendiente", "Valor neto"]:
        patrimonio[col] = (patrimonio[col] * patrimonio["Tasa a COP"]).fillna(0.0)

    # Si Valor neto no viene diligenciado, se calcula usando el porcentaje de propiedad.
    sin_valor_neto = patrimonio["Valor neto"].eq(0)
    es_activo = patrimonio["Tipo"].map(normalizar).eq("ACTIVO")
    patrimonio.loc[sin_valor_neto & es_activo, "Valor neto"] = (
        patrimonio.loc[sin_valor_neto & es_activo, "Valor actual"]
        * patrimonio.loc[sin_valor_neto & es_activo, "Porcentaje"]
        - patrimonio.loc[sin_valor_neto & es_activo, "Saldo pendiente"]
    )
    deuda_base = patrimonio["Saldo pendiente"].where(
        patrimonio["Saldo pendiente"].ne(0),
        patrimonio["Valor actual"] * patrimonio["Porcentaje"],
    )
    patrimonio.loc[sin_valor_neto & ~es_activo, "Valor neto"] = -deuda_base.loc[sin_valor_neto & ~es_activo].abs()

    deudas = leer_deudas_excel(file)
    pasivos = convertir_deudas_a_patrimonio(deudas)
    if not pasivos.empty:
        # Cuando existe una hoja dedicada de pasivos, Patrimonio es la fuente exclusiva
        # de activos. Esto evita contar dos veces una deuda copiada en ambas hojas.
        patrimonio = patrimonio[patrimonio["Tipo"].map(normalizar).eq("ACTIVO")].copy()
        patrimonio = pd.concat([patrimonio, pasivos], ignore_index=True, sort=False)

    return patrimonio[columnas].reset_index(drop=True)


def calcular_diagnostico_patrimonial(patrimonio):
    """Calcula indicadores personales con soporte para hipotecas futuras."""
    resultado_vacio = {
        "patrimonio_financiero": 0.0,
        "activos_liquidos": 0.0,
        "solvencia": None,
        "concentracion_inmuebles_pct": 0.0,
        "valor_inmuebles_bruto": 0.0,
        "saldo_hipotecas": 0.0,
        "ltv_pct": None,
        "pasivos_corrientes": 0.0,
        "fondo_maniobra": 0.0,
        "fondo_maniobra_inmediato": 0.0,
        "estado": "Sin datos",
        "mensaje": "No hay información suficiente para evaluar la salud patrimonial.",
    }
    if patrimonio is None or patrimonio.empty:
        return resultado_vacio

    df = patrimonio.copy()
    for col in ["Valor actual", "Valor neto", "Porcentaje"]:
        if col not in df.columns:
            df[col] = 0.0 if col != "Porcentaje" else 1.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0 if col != "Porcentaje" else 1.0)
    df.loc[df["Porcentaje"].gt(1), "Porcentaje"] /= 100.0
    df["Porcentaje"] = df["Porcentaje"].clip(0.0, 1.0)

    tipo_norm = df.get("Tipo", pd.Series("", index=df.index)).map(normalizar)
    activos_mask = tipo_norm.eq("ACTIVO")
    pasivos_mask = ~activos_mask
    activos = df.loc[activos_mask].copy()
    pasivos = df.loc[pasivos_mask].copy()

    total_activos = float(activos["Valor neto"].clip(lower=0).sum())
    total_pasivos = abs(float(pasivos["Valor neto"].sum()))

    def texto_normalizado(tabla, columnas):
        partes = [
            tabla.get(col, pd.Series("", index=tabla.index)).fillna("").astype(str).map(normalizar)
            for col in columnas
        ]
        if not partes:
            return pd.Series("", index=tabla.index)
        texto = partes[0]
        for parte in partes[1:]:
            texto = texto + " " + parte
        return texto.str.strip()

    descripcion_activos = texto_normalizado(
        activos,
        ["Tipo de producto", "Categoría", "Subcategoría", "Descripción", "Entidad"],
    )
    inmuebles_mask = descripcion_activos.str.contains("INMUEBLE", regex=False)
    valor_inmuebles_bruto = float(
        (activos.loc[inmuebles_mask, "Valor actual"] * activos.loc[inmuebles_mask, "Porcentaje"]).sum()
    )

    palabras_financieras = (
        "MONETARIO|RENTA FIJA|RENTA VARIABLE|INVERSION|AHORRO|PENSION|CESANTIA|"
        "FONDO|CUENTA|BANCO|EFECTIVO|CDT|ACCION|BONO|CRIPTO|CODEMA"
    )
    financieros_mask = descripcion_activos.str.contains(palabras_financieras, regex=True)
    financieros_mask &= ~inmuebles_mask
    patrimonio_financiero = float(activos.loc[financieros_mask, "Valor neto"].clip(lower=0).sum())

    disponibilidad = activos.get(
        "Disponibilidad de efectivo", pd.Series("", index=activos.index)
    ).fillna("").astype(str).map(normalizar)
    liquidez = activos.get("Liquidez", pd.Series("", index=activos.index)).fillna("").astype(str).map(normalizar)
    disponibilidad_definida = ~disponibilidad.isin(["", "NAN", "SIN CLASIFICAR", "NO APLICA"])
    disponibilidad_corriente = disponibilidad.str.contains("CORRIENTE", regex=False) & ~disponibilidad.str.contains("NO CORRIENTE", regex=False)
    liquidez_util = liquidez.str.contains("ALTA|MEDIA|LIQUID|INMEDIATA", regex=True)
    liquidos_mask = disponibilidad_corriente | (~disponibilidad_definida & liquidez_util)
    activos_liquidos = float(activos.loc[liquidos_mask, "Valor neto"].clip(lower=0).sum())

    descripcion_liquida = descripcion_activos.loc[liquidos_mask]
    inmediatos_mask_local = descripcion_liquida.str.contains(
        "MONETARIO|FONDO DE EMERGENCIA|AHORRO|CUENTA|BANCO|EFECTIVO|CODEMA",
        regex=True,
    )
    activos_inmediatos = float(
        activos.loc[descripcion_liquida.index[inmediatos_mask_local], "Valor neto"].clip(lower=0).sum()
    )

    descripcion_pasivos = texto_normalizado(
        pasivos,
        ["Tipo de producto", "Categoría", "Subcategoría", "Descripción", "Entidad"],
    )
    hipotecas_mask = descripcion_pasivos.str.contains("HIPOTECA", regex=False)
    saldo_hipotecas = abs(float(pasivos.loc[hipotecas_mask, "Valor neto"].sum()))
    pasivos_corrientes = abs(float(pasivos.loc[~hipotecas_mask, "Valor neto"].sum()))
    fondo_maniobra = activos_liquidos - pasivos_corrientes
    fondo_maniobra_inmediato = activos_inmediatos - pasivos_corrientes
    ltv_pct = (
        saldo_hipotecas / valor_inmuebles_bruto * 100
        if saldo_hipotecas > 0 and valor_inmuebles_bruto > 0
        else None
    )

    solvencia = total_activos / total_pasivos if total_pasivos > 0 else None
    deuda_activos = total_pasivos / total_activos if total_activos > 0 else 0.0
    if total_pasivos <= 0:
        estado = "Excelente"
        mensaje = "No hay pasivos registrados; la posición patrimonial no tiene deuda pendiente."
    elif fondo_maniobra < 0:
        estado = "Atención"
        mensaje = (
            "El patrimonio total es solvente, pero los activos corrientes no alcanzan a cubrir "
            "los pasivos corrientes; conviene reforzar la liquidez de corto plazo."
        )
    elif solvencia is not None and solvencia >= 2 and deuda_activos <= 0.40:
        estado = "Sólida"
        mensaje = "Los activos cubren ampliamente las deudas y el endeudamiento patrimonial es bajo."
    elif solvencia is not None and solvencia >= 1.2 and deuda_activos <= 0.70:
        estado = "Estable"
        mensaje = "La estructura patrimonial es estable, aunque conviene vigilar la deuda y la liquidez."
    else:
        estado = "Atención"
        mensaje = "La relación entre activos y deudas requiere seguimiento y un plan de reducción de pasivos."

    return {
        "patrimonio_financiero": patrimonio_financiero,
        "activos_liquidos": activos_liquidos,
        "solvencia": solvencia,
        "concentracion_inmuebles_pct": (
            valor_inmuebles_bruto / total_activos * 100 if total_activos > 0 else 0.0
        ),
        "valor_inmuebles_bruto": valor_inmuebles_bruto,
        "saldo_hipotecas": saldo_hipotecas,
        "ltv_pct": ltv_pct,
        "pasivos_corrientes": pasivos_corrientes,
        "fondo_maniobra": fondo_maniobra,
        "fondo_maniobra_inmediato": fondo_maniobra_inmediato,
        "estado": estado,
        "mensaje": mensaje,
    }


def calcular_carteras_por_objetivo(patrimonio):
    """Replica la tabla Objetivo/Tiempo de la hoja Situación Patrimonial.

    La distribución se calcula únicamente sobre activos financieros. Los
    inmuebles, vehículos y otros bienes físicos permanecen en el análisis
    patrimonial general para no mezclar patrimonio con cartera financiera.
    """
    columnas = [
        "Cartera", "Objetivo", "Tiempo", "Activo",
        "Renta fija", "Renta variable", "Actual", "Porcentaje", "Componentes",
    ]
    base = pd.DataFrame([
        {
            "Cartera": "A", "Objetivo": "Ahorro", "Tiempo": "Corto",
            "Activo": "Monetario", "Renta fija": "Sí", "Renta variable": "No",
            "Actual": 0.0, "Componentes": [],
        },
        {
            "Cartera": "B", "Objetivo": "Inversión", "Tiempo": "Medio",
            "Activo": "Renta fija", "Renta fija": "Sí", "Renta variable": "Sí",
            "Actual": 0.0, "Componentes": [],
        },
        {
            "Cartera": "C", "Objetivo": "Previsión", "Tiempo": "Largo",
            "Activo": "Renta variable / Criptos", "Renta fija": "No", "Renta variable": "Sí",
            "Actual": 0.0, "Componentes": [],
        },
    ])
    if patrimonio is None or patrimonio.empty:
        base["Porcentaje"] = 0.0
        return base[columnas]

    df = patrimonio.copy()
    tipo = df.get("Tipo", pd.Series("", index=df.index)).fillna("").astype(str).map(normalizar)
    df = df.loc[tipo.eq("ACTIVO")].copy()
    if df.empty:
        base["Porcentaje"] = 0.0
        return base[columnas]

    df["Valor objetivo"] = pd.to_numeric(
        df.get("Valor neto", pd.Series(0.0, index=df.index)), errors="coerce"
    ).fillna(0.0).clip(lower=0.0)
    producto = df.get("Tipo de producto", pd.Series("", index=df.index)).fillna("").astype(str).map(normalizar)
    categoria = df.get("Categoría", pd.Series("", index=df.index)).fillna("").astype(str).map(normalizar)
    subcategoria = df.get("Subcategoría", pd.Series("", index=df.index)).fillna("").astype(str).map(normalizar)
    descripcion = (producto + " " + categoria + " " + subcategoria).str.strip()

    bienes_fisicos = descripcion.str.contains(
        "INMUEBLE|VEHICULO|TECNOLOG|COMPUTADOR|MUEBLE|MAQUINARIA|JOYAS|ARTE",
        regex=True,
    )
    activos_financieros = descripcion.str.contains(
        "MONETARIO|RENTA FIJA|RENTA VARIABLE|INVERSION|AHORRO|PENSION|CESANTIA|"
        "FONDO|CUENTA|BANCO|EFECTIVO|CDT|ACCION|BONO|CRIPTO|CODEMA",
        regex=True,
    ) & ~bienes_fisicos

    ahorro = activos_financieros & (
        categoria.str.contains("FONDO DE EMERGENCIA|AHORRO|CUENTA|BANCO|EFECTIVO|CODEMA", regex=True)
        | producto.str.contains("MONETARIO", regex=False)
    )
    prevision = activos_financieros & ~ahorro & (
        producto.str.contains("RENTA VARIABLE|CRIPTO", regex=True)
        | categoria.str.contains("PENSION|CESANTIA|PREVISION", regex=True)
    )
    inversion = activos_financieros & ~ahorro & ~prevision

    columnas_nombre = [
        col for col in ["Elemento", "Descripción", "Subcategoría", "Categoría", "Entidad"]
        if col in df.columns
    ]
    if columnas_nombre:
        df["Elemento objetivo"] = df[columnas_nombre].fillna("").astype(str).apply(
            lambda fila: next(
                (
                    valor.strip() for valor in fila
                    if valor.strip() and normalizar(valor) not in {"NAN", "NONE", "NAT", "SIN NOMBRE", "SIN DESCRIPCION"}
                ),
                "Sin nombre",
            ),
            axis=1,
        )
    else:
        df["Elemento objetivo"] = "Sin nombre"

    def componentes_de(mascara):
        if not mascara.any():
            return []
        detalle = (
            df.loc[mascara]
            .groupby("Elemento objetivo", as_index=False)["Valor objetivo"]
            .sum()
            .sort_values("Valor objetivo", ascending=False)
        )
        return [
            {"nombre": str(fila["Elemento objetivo"]), "valor": float(fila["Valor objetivo"])}
            for _, fila in detalle.iterrows()
        ]

    importes = {
        "A": float(df.loc[ahorro, "Valor objetivo"].sum()),
        "B": float(df.loc[inversion, "Valor objetivo"].sum()),
        "C": float(df.loc[prevision, "Valor objetivo"].sum()),
    }
    base["Actual"] = base["Cartera"].map(importes).fillna(0.0)
    base["Componentes"] = base["Cartera"].map({
        "A": componentes_de(ahorro),
        "B": componentes_de(inversion),
        "C": componentes_de(prevision),
    })
    total = float(base["Actual"].sum())
    base["Porcentaje"] = base["Actual"].div(total).mul(100) if total > 0 else 0.0
    return base[columnas]


def calcular_distribucion_renta_patrimonio(patrimonio):
    """Separa los activos según produzcan o no algún tipo de renta."""
    columnas = ["Estado renta", "Valor", "Porcentaje", "Componentes"]
    if patrimonio is None or patrimonio.empty:
        return pd.DataFrame(columns=columnas)

    df = patrimonio.copy()
    tipo = df.get("Tipo", pd.Series("", index=df.index)).fillna("").astype(str).map(normalizar)
    df = df.loc[tipo.eq("ACTIVO")].copy()
    if df.empty:
        return pd.DataFrame(columns=columnas)

    df["Valor renta"] = pd.to_numeric(
        df.get("Valor neto", pd.Series(0.0, index=df.index)), errors="coerce"
    ).fillna(0.0).clip(lower=0.0)
    producto = df.get("Tipo de producto", pd.Series("", index=df.index)).fillna("").astype(str).map(normalizar)
    categoria = df.get("Categoría", pd.Series("", index=df.index)).fillna("").astype(str).map(normalizar)
    descripcion = df.get("Descripción", pd.Series("", index=df.index)).fillna("").astype(str).map(normalizar)
    texto_renta = (producto + " " + categoria + " " + descripcion).str.strip()

    sin_renta = producto.str.contains("SIN RENTA", regex=False)
    produce_renta = ~sin_renta & texto_renta.str.contains(
        "RENTA FIJA|RENTA VARIABLE|CON RENTA|ALQUILER|ARREND|INTERES|DIVIDENDO|CUPON|RENDIMIENTO",
        regex=True,
    )
    df["Estado renta"] = produce_renta.map({True: "Produce renta", False: "No produce renta"})

    columnas_nombre = [
        col for col in ["Elemento", "Descripción", "Subcategoría", "Categoría", "Entidad"]
        if col in df.columns
    ]
    if columnas_nombre:
        df["Elemento renta"] = df[columnas_nombre].fillna("").astype(str).apply(
            lambda fila: next(
                (
                    valor.strip() for valor in fila
                    if valor.strip() and normalizar(valor) not in {"NAN", "NONE", "NAT", "SIN NOMBRE", "SIN DESCRIPCION"}
                ),
                "Sin nombre",
            ),
            axis=1,
        )
    else:
        df["Elemento renta"] = "Sin nombre"

    filas = []
    total = float(df["Valor renta"].sum())
    for estado in ["Produce renta", "No produce renta"]:
        grupo = df.loc[df["Estado renta"].eq(estado)]
        valor = float(grupo["Valor renta"].sum())
        detalle = (
            grupo.groupby("Elemento renta", as_index=False)["Valor renta"]
            .sum()
            .sort_values("Valor renta", ascending=False)
        )
        componentes = [
            {"nombre": str(fila["Elemento renta"]), "valor": float(fila["Valor renta"])}
            for _, fila in detalle.iterrows()
        ]
        filas.append({
            "Estado renta": estado,
            "Valor": valor,
            "Porcentaje": valor / total * 100 if total > 0 else 0.0,
            "Componentes": componentes,
        })
    return pd.DataFrame(filas, columns=columnas)


def fig_patrimonio_donut(resumen_tipo):
    if resumen_tipo.empty:
        return go.Figure()
    tmp = resumen_tipo.copy()
    tmp["Valor gráfico"] = tmp["Valor neto"].abs()
    fig = px.pie(
        tmp,
        names="Tipo",
        values="Valor gráfico",
        hole=0.55,
        color="Tipo",
        color_discrete_map={"Activo": COLOR_INGRESOS, "Pasivo": COLOR_GASTOS},
    )
    fig.update_traces(
        textinfo="percent+label",
        textfont=dict(color="#ffffff", size=12),
        marker=dict(line=dict(color="#000000", width=2)),
        hovertemplate="<b>%{label}</b><br>Valor: $%{value:,.0f}<br>Participación: %{percent}<extra></extra>",
    )
    return estilo_grafico(fig, "Composición: activos vs pasivos")


def fig_patrimonio_categoria(patrimonio):
    tmp = (
        patrimonio.groupby(["Tipo", "Categoría"], as_index=False)["Valor neto"]
        .sum()
        .sort_values("Valor neto", key=lambda s: s.abs(), ascending=False)
    )
    if tmp.empty:
        return go.Figure()
    tmp["Valor gráfico"] = tmp["Valor neto"].abs()
    fig = px.bar(
        tmp,
        x="Valor gráfico",
        y="Categoría",
        color="Tipo",
        orientation="h",
        text="Valor neto",
        color_discrete_map={"Activo": COLOR_INGRESOS, "Pasivo": COLOR_GASTOS},
    )
    fig.update_traces(
        texttemplate="$%{text:,.0f}",
        textposition="outside",
        marker=dict(line=dict(color="rgba(255,255,255,0.25)", width=1)),
        hovertemplate="Tipo: %{fullData.name}<br>Categoría: %{y}<br>Valor neto: $%{text:,.0f}<extra></extra>",
    )
    fig.update_layout(xaxis_title="Valor absoluto", yaxis_title="Categoría", yaxis=dict(autorange="reversed"))
    return estilo_grafico(fig, "Patrimonio por categoría")


def fig_patrimonio_treemap(patrimonio):
    """Treemap Patrimonio → Tipo → Categoría → Subcategoría → Descripción.

    Igual que en fig_mapa_ingresos_tipo_fuente, se calculan a mano ids,
    labels, parents, values, texto (valor neto con signo) y tooltip por
    cada nodo de la jerarquía -incluyendo los agregados (raíz, tipo,
    categoría, subcategoría)- para que ningún nodo dependa de una
    agregación automática de `custom_data` que Plotly no calcula y que
    es la causa de los "undefined" en los mapas jerárquicos.
    """
    tmp = patrimonio.copy()
    tmp["Valor gráfico"] = tmp["Valor neto"].abs()
    tmp = tmp[tmp["Valor gráfico"] > 0]
    if tmp.empty:
        return go.Figure()

    color_por_tipo = {"Activo": COLOR_INGRESOS, "Pasivo": COLOR_GASTOS}
    raiz_id = "Patrimonio"
    total_general = float(tmp["Valor gráfico"].sum()) or 1.0
    neto_general = float(tmp["Valor neto"].sum())

    ids, labels, parents, values, textos, tooltips, colores = [], [], [], [], [], [], []

    ids.append(raiz_id)
    labels.append(raiz_id)
    parents.append("")
    values.append(total_general)
    textos.append(neto_general)
    tooltips.append(f"<b>{raiz_id}</b><br>Valor neto: ${neto_general:,.0f}")
    colores.append("#0A0A1A")

    for tipo, grupo_tipo in tmp.groupby("Tipo", sort=False):
        tipo_id = f"{raiz_id}/{tipo}"
        total_tipo = float(grupo_tipo["Valor gráfico"].sum())
        neto_tipo = float(grupo_tipo["Valor neto"].sum())
        color_tipo = color_por_tipo.get(str(tipo), "#818CF8")
        pct_tipo = (total_tipo / total_general * 100) if total_general else 0

        ids.append(tipo_id)
        labels.append(str(tipo))
        parents.append(raiz_id)
        values.append(total_tipo)
        textos.append(neto_tipo)
        tooltips.append(
            f"<b>{tipo}</b><br>Valor neto: ${neto_tipo:,.0f}<br>Participación del total: {pct_tipo:.1f}%"
        )
        colores.append(color_tipo)

        for categoria, grupo_cat in grupo_tipo.groupby("Categoría", sort=False):
            cat_id = f"{tipo_id}/{categoria}"
            total_cat = float(grupo_cat["Valor gráfico"].sum())
            neto_cat = float(grupo_cat["Valor neto"].sum())
            pct_cat = (total_cat / total_tipo * 100) if total_tipo else 0

            ids.append(cat_id)
            labels.append(str(categoria))
            parents.append(tipo_id)
            values.append(total_cat)
            textos.append(neto_cat)
            tooltips.append(
                f"<b>{categoria}</b><br>Valor neto: ${neto_cat:,.0f}<br>Dentro de {tipo}: {pct_cat:.1f}%"
            )
            colores.append(color_tipo)

            for subcategoria, grupo_sub in grupo_cat.groupby("Subcategoría", sort=False):
                sub_id = f"{cat_id}/{subcategoria}"
                total_sub = float(grupo_sub["Valor gráfico"].sum())
                neto_sub = float(grupo_sub["Valor neto"].sum())
                pct_sub = (total_sub / total_cat * 100) if total_cat else 0

                ids.append(sub_id)
                labels.append(str(subcategoria))
                parents.append(cat_id)
                values.append(total_sub)
                textos.append(neto_sub)
                tooltips.append(
                    f"<b>{subcategoria}</b><br>Valor neto: ${neto_sub:,.0f}<br>Dentro de {categoria}: {pct_sub:.1f}%"
                )
                colores.append(color_tipo)

                desc_agg = grupo_sub.groupby("Descripción", as_index=False).agg(
                    valor_neto=("Valor neto", "sum"),
                    valor_grafico=("Valor gráfico", "sum"),
                    entidad=("Entidad", lambda s: ", ".join(sorted(set(s.dropna().astype(str)))) or "Sin entidad"),
                    saldo_pendiente=("Saldo pendiente", "sum"),
                    liquidez=("Liquidez", lambda s: ", ".join(sorted(set(s.dropna().astype(str)))) or "Sin clasificar"),
                )
                for _, fila in desc_agg.iterrows():
                    descripcion = str(fila["Descripción"])
                    desc_id = f"{sub_id}/{descripcion}"

                    ids.append(desc_id)
                    labels.append(descripcion)
                    parents.append(sub_id)
                    values.append(float(fila["valor_grafico"]))
                    textos.append(float(fila["valor_neto"]))
                    tooltips.append(
                        f"<b>{descripcion}</b><br>"
                        f"Valor neto: ${float(fila['valor_neto']):,.0f}<br>"
                        f"Entidad: {fila['entidad'] or 'Sin entidad'}<br>"
                        f"Saldo pendiente: ${float(fila['saldo_pendiente']):,.0f}<br>"
                        f"Liquidez: {fila['liquidez'] or 'Sin clasificar'}"
                    )
                    colores.append(color_tipo)

    fig = go.Figure(
        go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            text=textos,
            customdata=tooltips,
            texttemplate="<b>%{label}</b><br>$%{text:,.0f}",
            hovertemplate="%{customdata}<extra></extra>",
            marker=dict(colors=colores, line=dict(color="#000000", width=2)),
            root_color="#0A0A1A",
            hoverlabel=dict(bgcolor="#0a0a0a", bordercolor="#00F0FF", font=dict(size=13, color="#f8fafc")),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=650,
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#e2e8f0"),
        margin=dict(t=50, b=20, l=10, r=10),
    )
    return fig


def fig_patrimonio_liquidez(patrimonio):
    activos = patrimonio[patrimonio["Tipo"].map(normalizar).eq("ACTIVO")].copy()
    if activos.empty:
        return go.Figure()
    tmp = activos.groupby("Liquidez", as_index=False)["Valor neto"].sum().sort_values("Valor neto", ascending=False)
    fig = px.pie(tmp, names="Liquidez", values="Valor neto", hole=0.45, color_discrete_sequence=PALETA_NEON)
    fig.update_traces(
        textinfo="percent+label",
        textfont=dict(color="#ffffff", size=12),
        marker=dict(line=dict(color="#000000", width=2)),
        hovertemplate="Liquidez: %{label}<br>Valor: $%{value:,.0f}<br>Participación: %{percent}<extra></extra>",
    )
    return estilo_grafico(fig, "Activos por liquidez")


def fig_patrimonio_concentracion_categoria(patrimonio):
    """Donut de concentración de patrimonio por categoría leída desde Excel.

    No usa categorías escritas manualmente: toma todos los valores existentes
    en la columna Categoría de la hoja Patrimonio, por lo que nuevas categorías
    aparecerán automáticamente en el gráfico.
    
    Se filtran activos porque el objetivo es mostrar la concentración de los
    activos patrimoniales por categoría.
    """
    activos = patrimonio[patrimonio["Tipo"].map(normalizar).eq("ACTIVO")].copy()
    if activos.empty:
        return go.Figure()

    tmp = (
        activos.groupby("Categoría", as_index=False)["Valor neto"]
        .sum()
        .sort_values("Valor neto", ascending=False)
    )
    tmp = tmp[tmp["Valor neto"].abs() > 0]

    if tmp.empty:
        return go.Figure()

    tmp["Valor gráfico"] = tmp["Valor neto"].abs()
    total = float(tmp["Valor gráfico"].sum()) or 1.0
    tmp["Participación"] = tmp["Valor gráfico"] / total * 100

    fig = px.pie(
        tmp,
        names="Categoría",
        values="Valor gráfico",
        hole=0.55,
        color="Categoría",
        color_discrete_sequence=PALETA_NEON,
    )
    fig.update_traces(
        textinfo="percent+label",
        textfont=dict(color="#ffffff", size=12),
        marker=dict(line=dict(color="#000000", width=2)),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Valor neto: $%{value:,.0f}<br>"
            "Participación: %{percent}"
            "<extra></extra>"
        ),
    )
    fig.update_layout(
        showlegend=True,
        legend_title_text="Categoría",
    )
    return estilo_grafico(fig, "Concentración de patrimonio por categoría")


def puntaje_presupuesto(gastos, presupuesto_total):
    if presupuesto_total <= 0:
        return 0, 0
    ratio = gastos / presupuesto_total if presupuesto_total else 0
    if ratio <= 1.00:
        pts = 25
    elif ratio <= 1.05:
        pts = 20
    elif ratio <= 1.10:
        pts = 15
    elif ratio <= 1.20:
        pts = 10
    else:
        pts = 0
    return pts, ratio * 100


def puntaje_ahorro(balance, ingresos):
    pct = (balance / ingresos * 100) if ingresos else 0
    if pct >= 30:
        pts = 20
    elif pct >= 25:
        pts = 18
    elif pct >= 20:
        pts = 15
    elif pct >= 15:
        pts = 10
    elif pct >= 10:
        pts = 5
    else:
        pts = 0
    return pts, pct


def puntaje_endeudamiento(total_pasivos, total_activos):
    pct = (total_pasivos / total_activos * 100) if total_activos else 0
    if pct < 20:
        pts = 20
    elif pct <= 35:
        pts = 15
    elif pct <= 50:
        pts = 10
    elif pct <= 70:
        pts = 5
    else:
        pts = 0
    return pts, pct


def detectar_gastos_innecesarios(df_gastos):
    if df_gastos.empty:
        return df_gastos.copy()
    tmp = df_gastos.copy()
    texto = (
        tmp.get("GASTOS_CATEGORIA", "").astype(str).map(normalizar) + " " +
        tmp.get("GASTOS_SUBCATEGORIA", "").astype(str).map(normalizar) + " " +
        tmp.get("GASTOS_SUBCATEGORIA_2", "").astype(str).map(normalizar) + " " +
        tmp.get("GASTOS_DESCRIPCION", "").astype(str).map(normalizar) + " " +
        tmp.get("GASTOS_OBSERVACION", "").astype(str).map(normalizar)
    )
    claves = [
        "PRESCINDIBLE", "NO ESENCIAL", "GUSTO", "GUSTOS", "OCIO", "RUMBA",
        "ENTRETENIMIENTO", "SALIDA", "RESTAURANTE", "DOMICILIO", "COMIDA RAPIDA",
        "ROPA", "CALZADO", "CAPRICHO", "JUEGO", "STREAMING", "CINE", "LICOR",
    ]
    return tmp[texto.map(lambda x: any(k in x for k in claves))]


def puntaje_gastos_innecesarios(df_gastos):
    total = float(df_gastos["GASTOS_CANTIDAD"].sum()) if not df_gastos.empty else 0
    innecesarios = detectar_gastos_innecesarios(df_gastos)
    monto = float(innecesarios["GASTOS_CANTIDAD"].sum()) if not innecesarios.empty else 0
    pct = (monto / total * 100) if total else 0
    if pct < 5:
        pts = 10
    elif pct <= 10:
        pts = 8
    elif pct <= 20:
        pts = 5
    elif pct <= 30:
        pts = 2
    else:
        pts = 0
    return pts, pct, monto, innecesarios


def valor_fondo_emergencia(patrimonio):
    if patrimonio.empty:
        return 0.0
    activos = patrimonio[patrimonio["Tipo"].map(normalizar).eq("ACTIVO")].copy()
    if activos.empty:
        return 0.0
    texto = (
        activos["Categoría"].astype(str).map(normalizar) + " " +
        activos["Subcategoría"].astype(str).map(normalizar) + " " +
        activos["Descripción"].astype(str).map(normalizar)
    )
    fondo = activos[texto.str.contains("FONDO DE EMERGENCIA|EMERGENCIA", regex=True, na=False)]
    return float(fondo["Valor neto"].sum()) if not fondo.empty else 0.0


def puntaje_fondo_emergencia(fondo, gasto_mensual_promedio):
    """Puntaje del fondo de emergencia con meta de 3 meses de gasto promedio.

    La meta no se digita manualmente: se calcula como gasto mensual promedio * 3.
    """
    meses = (fondo / gasto_mensual_promedio) if gasto_mensual_promedio else 0
    if meses >= 3:
        pts = 15
    elif meses >= 2.5:
        pts = 13
    elif meses >= 2:
        pts = 10
    elif meses >= 1:
        pts = 5
    else:
        pts = 0
    return pts, meses


def leer_metas_excel(file):
    cols = ["Meta", "Objetivo", "Actual", "Avance"]
    try:
        raw = pd.read_excel(file, sheet_name="Metas")
    except Exception:
        return pd.DataFrame(columns=cols)
    if raw.empty:
        return pd.DataFrame(columns=cols)
    mapa = {}
    for c in raw.columns:
        n = normalizar(c)
        if n in {"META", "NOMBRE", "DESCRIPCION"}:
            mapa[c] = "Meta"
        elif n in {"OBJETIVO", "VALOR OBJETIVO", "META VALOR"}:
            mapa[c] = "Objetivo"
        elif n in {"ACTUAL", "AHORRADO", "VALOR ACTUAL", "AVANCE ACTUAL"}:
            mapa[c] = "Actual"
        elif n in {"AVANCE", "PORCENTAJE", "% AVANCE"}:
            mapa[c] = "Avance"
    df = raw.rename(columns=mapa)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[cols].dropna(how="all")
    df["Objetivo"] = pd.to_numeric(df["Objetivo"], errors="coerce").fillna(0)
    df["Actual"] = pd.to_numeric(df["Actual"], errors="coerce").fillna(0)
    df["Avance"] = pd.to_numeric(df["Avance"], errors="coerce")
    sin_avance = df["Avance"].isna()
    df.loc[sin_avance, "Avance"] = df.loc[sin_avance].apply(
        lambda r: (r["Actual"] / r["Objetivo"] * 100) if r["Objetivo"] else 0,
        axis=1,
    )
    df["Avance"] = df["Avance"].clip(lower=0, upper=100)
    return df


def puntaje_metas(metas):
    if metas.empty:
        return 0, 0
    avance = float(metas["Avance"].mean())
    pts = min(10, max(0, avance / 10))
    return pts, avance


def normalizar_pct_0_100(valor):
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


def calcular_componentes_score(
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
    """Fuente única de los seis componentes del score financiero."""
    pts_pres, ratio_pres = puntaje_presupuesto(gastos_valor, presupuesto_valor)
    pts_aho, pct_aho = puntaje_ahorro(ingresos_valor - gastos_valor, ingresos_valor)
    pts_end, pct_end = puntaje_endeudamiento(pasivos_valor, activos_valor)
    pts_inn, pct_inn, monto_inn, innecesarios_df = puntaje_gastos_innecesarios(gastos_df)
    pts_eme, _ = puntaje_fondo_emergencia(fondo_valor, gasto_mensual_valor)
    pts_met, avance_met = puntaje_metas(metas_df)

    ratio_pres = normalizar_pct_0_100(ratio_pres)
    pct_aho = max(min(float(pct_aho), 100.0), -100.0)
    pct_end = normalizar_pct_0_100(pct_end)
    pct_inn = normalizar_pct_0_100(pct_inn)
    avance_met = normalizar_pct_0_100(avance_met)

    datos = [
        {"Indicador": "Presupuesto", "Icono": "🎯", "Puntos": float(pts_pres), "Máximo": 25.0,
         "Puntaje %": normalizar_pct_0_100(float(pts_pres) / 25.0), "Base": f"Ejecución presupuestal: {ratio_pres:.1f}%"},
        {"Indicador": "Ahorro", "Icono": "💰", "Puntos": float(pts_aho), "Máximo": 20.0,
         "Puntaje %": normalizar_pct_0_100(float(pts_aho) / 20.0), "Base": f"Capacidad de ahorro: {pct_aho:.1f}%"},
        {"Indicador": "Endeudamiento", "Icono": "💳", "Puntos": float(pts_end), "Máximo": 20.0,
         "Puntaje %": normalizar_pct_0_100(float(pts_end) / 20.0), "Base": f"Pasivos / activos: {pct_end:.1f}%"},
        {"Indicador": "Gastos innecesarios", "Icono": "🛒", "Puntos": float(pts_inn), "Máximo": 10.0,
         "Puntaje %": normalizar_pct_0_100(float(pts_inn) / 10.0), "Base": f"Gasto marcado: {pct_inn:.1f}%"},
        {"Indicador": "Fondo emergencia", "Icono": "🛡️", "Puntos": float(pts_eme), "Máximo": 15.0,
         "Puntaje %": normalizar_pct_0_100(float(pts_eme) / 15.0),
         "Base": f"Cobertura: {(fondo_valor / gasto_mensual_valor):.1f} meses" if gasto_mensual_valor > 0 else "Sin gasto mensual de referencia"},
        {"Indicador": "Metas", "Icono": "🏁", "Puntos": float(pts_met), "Máximo": 10.0,
         "Puntaje %": normalizar_pct_0_100(float(pts_met) / 10.0), "Base": f"Cumplimiento promedio: {avance_met:.1f}%"},
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


def calcular_score_financiero(
    *, gastos_valor, ingresos_valor, presupuesto_valor,
    patrimonio, metas_df, gastos_df, cantidad_periodos,
):
    """Calcula el score y devuelve también todas sus bases auditables."""
    if patrimonio is not None and not patrimonio.empty:
        activos = float(patrimonio.loc[patrimonio["Tipo"].map(normalizar).eq("ACTIVO"), "Valor neto"].sum())
        pasivos = abs(float(patrimonio.loc[~patrimonio["Tipo"].map(normalizar).eq("ACTIVO"), "Valor neto"].sum()))
    else:
        activos = pasivos = 0.0
    periodos = max(int(cantidad_periodos or 0), 1)
    gasto_mensual = float(gastos_valor) / periodos
    fondo = valor_fondo_emergencia(patrimonio) if patrimonio is not None else 0.0
    componentes, metricas = calcular_componentes_score(
        gastos_valor=float(gastos_valor), ingresos_valor=float(ingresos_valor),
        presupuesto_valor=float(presupuesto_valor), activos_valor=activos,
        pasivos_valor=pasivos, fondo_valor=fondo,
        gasto_mensual_valor=gasto_mensual, metas_df=metas_df, gastos_df=gastos_df,
    )
    return {
        "score": round(sum(item["Puntos"] for item in componentes), 1),
        "componentes": componentes,
        "metricas": metricas,
        "activos": activos,
        "pasivos": pasivos,
        "fondo": fondo,
        "gasto_mensual": gasto_mensual,
        "cantidad_periodos": periodos,
    }


def estado_meta(avance):
    """Estado visual de avance, reutilizado para el fondo de emergencia y cada meta del Excel."""
    if avance >= 100:
        return "🟢 Meta completa"
    elif avance >= 75:
        return "🟡 Cerca de la meta"
    elif avance >= 33:
        return "🟠 En construcción"
    else:
        return "🔴 Prioridad alta"


def fig_progreso_meta(nombre, actual, objetivo, faltante, texto_meta="Meta"):
    """Gráfico de progreso Actual/Faltante con línea de meta.

    Replica exactamente el mismo tipo de gráfico usado para el Fondo de
    Emergencia (barra horizontal apilada Actual/Faltante + línea vertical
    de meta), de modo que cada meta del Excel se vea con el mismo estilo.
    """
    parte_actual = min(actual, objetivo) if objetivo else actual
    barra = pd.DataFrame({
        "Concepto": [nombre, nombre],
        "Parte": ["Actual", "Faltante"],
        "Valor": [parte_actual, faltante],
    })
    fig = px.bar(
        barra,
        x="Valor",
        y="Concepto",
        color="Parte",
        orientation="h",
        text="Valor",
        color_discrete_map={"Actual": COLOR_INGRESOS, "Faltante": "#FF0033"},
    )
    fig.update_traces(
        texttemplate="$%{text:,.0f}",
        textposition="inside",
        textfont=dict(color="#000000"),
        marker=dict(line=dict(color="rgba(255,255,255,0.3)", width=1)),
        hovertemplate="%{fullData.name}: $%{x:,.0f}<extra></extra>",
    )
    if objetivo > 0:
        fig.add_vline(
            x=objetivo,
            line_dash="dash",
            line_color=COLOR_PRESUPUESTO,
            annotation_text=texto_meta,
            annotation_position="top right",
        )
    fig.update_layout(
        template="plotly_dark",
        height=230,
        barmode="stack",
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        xaxis_title="Valor",
        yaxis_title="",
        legend_title="",
        showlegend=False,
        margin=dict(t=35, b=35, l=20, r=20),
        font=dict(color="#e2e8f0"),
    )
    return fig


def etiqueta_score(score):
    if score >= 90:
        return "🟢 Excelente"
    if score >= 80:
        return "🟢 Muy bueno"
    if score >= 70:
        return "🟡 Bueno"
    if score >= 60:
        return "🟠 Regular"
    return "🔴 Riesgo financiero"


def fig_score_gauge(score):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": "/100", "font": {"color": "#f8fafc", "size": 46}},
        title={"text": "Altium Score Financiero", "font": {"color": "#00F0FF", "size": 22}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#94a3b8"},
            "bar": {"color": "#00F0FF"},
            "bgcolor": "#0a0a0a",
            "borderwidth": 1,
            "bordercolor": "#00D9FF",
            "steps": [
                {"range": [0, 60], "color": "#4a0012"},
                {"range": [60, 70], "color": "#4a2400"},
                {"range": [70, 80], "color": "#4a3b00"},
                {"range": [80, 90], "color": "#1a4a00"},
                {"range": [90, 100], "color": "#003d1a"},
            ],
        },
    ))
    fig.update_layout(template="plotly_dark", height=430, paper_bgcolor="#000000", plot_bgcolor="#000000", font=dict(color="#e2e8f0"))
    return fig


def fig_score_radar(componentes):
    labels = [c["Indicador"] for c in componentes]
    valores = [c["Puntaje %"] for c in componentes]
    fig = go.Figure(go.Scatterpolar(
        r=valores + [valores[0]],
        theta=labels + [labels[0]],
        fill="toself",
        fillcolor="rgba(0,240,255,0.22)",
        line=dict(color="#00F0FF", width=3),
        marker=dict(size=9, color="#FFEE00", line=dict(color="#ffffff", width=1)),
        hovertemplate="%{theta}<br>Cumplimiento: %{r:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark", height=430, paper_bgcolor="#000000", plot_bgcolor="#000000",
        polar=dict(
            bgcolor="#0a0a0a",
            radialaxis=dict(range=[0, 100], tickfont=dict(color="#94a3b8"), gridcolor="rgba(0,240,255,0.18)"),
            angularaxis=dict(gridcolor="rgba(0,240,255,0.18)", tickfont=dict(color="#cbd5e1")),
        ),
        margin=dict(t=50, b=40, l=40, r=40),
    )
    return fig


def fig_score_barras(componentes):
    dfc = pd.DataFrame(componentes)
    fig = px.bar(
        dfc, x="Puntos", y="Indicador", orientation="h", text="Etiqueta",
        color="Puntaje %", color_continuous_scale=[
            [0.0, "#FF0033"], [0.5, "#FFEE00"], [1.0, "#00FF66"],
        ],
    )
    fig.update_traces(
        textposition="outside",
        textfont=dict(color="#e2e8f0"),
        marker=dict(line=dict(color="rgba(255,255,255,0.25)", width=1)),
        hovertemplate="%{y}<br>Puntos: %{x}<br>%{text}<extra></extra>",
    )
    fig.update_layout(xaxis_title="Puntos obtenidos", yaxis_title="", yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
    return estilo_grafico(fig, "Componentes del score")



def calcular_edad(fecha_nacimiento, fecha_referencia=None):
    """Calcula edad en años cumplidos a partir de una fecha de nacimiento."""
    fecha = pd.to_datetime(fecha_nacimiento, errors="coerce")
    if pd.isna(fecha):
        return None
    ref = pd.Timestamp.today() if fecha_referencia is None else pd.to_datetime(fecha_referencia, errors="coerce")
    if pd.isna(ref):
        ref = pd.Timestamp.today()
    edad = ref.year - fecha.year - ((ref.month, ref.day) < (fecha.month, fecha.day))
    return int(edad) if edad >= 0 else None


@st.cache_data
def leer_datos_personales(file):
    """Lee nombre y edad desde la hoja Personales.

    La plantilla actual trae:
    - B3: NOMBRE:
    - C3: nombre de la persona
    - B4: Fecha de nacimiento
    - C4: fecha de nacimiento

    También busca etiquetas similares para mantener compatibilidad si se mueve la información.
    """
    resultado = {"nombre": "Sin registrar", "fecha_nacimiento": pd.NaT, "edad": None}
    try:
        raw = pd.read_excel(file, sheet_name="Personales", header=None)
    except Exception:
        return resultado

    for i in range(raw.shape[0]):
        for j in range(raw.shape[1]):
            etiqueta = normalizar(raw.iat[i, j])
            if not etiqueta:
                continue
            valor_derecha = raw.iat[i, j + 1] if j + 1 < raw.shape[1] else pd.NA
            valor_abajo = raw.iat[i + 1, j] if i + 1 < raw.shape[0] else pd.NA
            valor = valor_derecha if pd.notna(valor_derecha) else valor_abajo

            if "NOMBRE" in etiqueta and pd.notna(valor):
                nombre = str(valor).strip()
                if nombre and nombre.lower() != "nan":
                    resultado["nombre"] = nombre

            if "NACIMIENTO" in etiqueta or "FECHA NAC" in etiqueta:
                fecha = pd.to_datetime(valor, errors="coerce")
                if pd.notna(fecha):
                    resultado["fecha_nacimiento"] = fecha
                    resultado["edad"] = calcular_edad(fecha)

    return resultado


@st.cache_data
def leer_felicidad_trabajos(file):
    """Lee la matriz de trabajos/ingresos de la hoja Transaccional.

    En el Excel actual el bloque está en K:Q:
    K Fecha, L Cantidad valor, M Empresa, N Mes, O Categoría, P Horas, Q Valor Hora.

    La lectura se hace por encabezados para que el dashboard no se rompa si el
    bloque se mueve una columna por la presencia de separadores vacíos.
    """
    columnas = ["FECHA", "VALOR", "EMPRESA", "MES", "CATEGORIA", "HORAS", "VALOR_HORA"]
    try:
        raw = pd.read_excel(file, sheet_name="Transaccional", header=None)
    except Exception:
        return pd.DataFrame(columns=columnas)

    if raw.empty or raw.shape[0] < 2:
        return pd.DataFrame(columns=columnas)

    encabezados = [normalizar(raw.iloc[0, c]) for c in range(raw.shape[1])]

    def buscar_columna(condicion, inicio=0):
        for idx in range(inicio, len(encabezados)):
            if condicion(encabezados[idx]):
                return idx
        return None

    idx_valor = buscar_columna(lambda h: "CANTIDAD" in h and "VALOR" in h, 0)
    if idx_valor is None:
        # Fallback para versiones anteriores donde el bloque se asumía por posición.
        if raw.shape[1] >= 17:
            posiciones = [10, 11, 12, 13, 14, 15, 16]
        elif raw.shape[1] >= 16:
            posiciones = [9, 10, 11, 12, 13, 14, 15]
        else:
            return pd.DataFrame(columns=columnas)
    else:
        idx_fecha = idx_valor - 1 if idx_valor > 0 else buscar_columna(lambda h: h.startswith("FECHA"), 0)
        idx_empresa = buscar_columna(lambda h: h == "EMPRESA", idx_valor + 1)
        idx_mes = buscar_columna(lambda h: h == "MES", idx_valor + 1)
        idx_categoria = buscar_columna(lambda h: "CATEGORIA" in h, idx_valor + 1)
        idx_horas = buscar_columna(lambda h: h == "HORAS", idx_valor + 1)
        idx_valor_hora = buscar_columna(lambda h: "VALOR" in h and "HORA" in h, idx_valor + 1)
        posiciones = [idx_fecha, idx_valor, idx_empresa, idx_mes, idx_categoria, idx_horas, idx_valor_hora]
        if any(p is None or p >= raw.shape[1] for p in posiciones):
            return pd.DataFrame(columns=columnas)

    trabajos = raw.iloc[1:, posiciones].copy()
    trabajos.columns = columnas
    trabajos = trabajos.dropna(how="all")

    trabajos["FECHA"] = pd.to_datetime(trabajos["FECHA"], errors="coerce")
    trabajos["VALOR"] = pd.to_numeric(trabajos["VALOR"], errors="coerce")
    trabajos["HORAS"] = pd.to_numeric(trabajos["HORAS"], errors="coerce")
    trabajos["VALOR_HORA"] = pd.to_numeric(trabajos["VALOR_HORA"], errors="coerce")

    # Si Valor Hora no viene digitado/calculado en Excel, se calcula como valor / horas.
    mask_calc = trabajos["VALOR_HORA"].isna() & trabajos["VALOR"].notna() & trabajos["HORAS"].gt(0)
    trabajos.loc[mask_calc, "VALOR_HORA"] = trabajos.loc[mask_calc, "VALOR"] / trabajos.loc[mask_calc, "HORAS"]

    trabajos["MES"] = trabajos["MES"].map(normalizar_mes)
    sin_mes = trabajos["MES"].eq("") | trabajos["MES"].isna()
    trabajos.loc[sin_mes, "MES"] = trabajos.loc[sin_mes, "FECHA"].dt.month.map({v: k for k, v in MESES_NUM.items()})

    trabajos["EMPRESA"] = trabajos["EMPRESA"].fillna("Sin empresa").astype(str).str.strip()
    trabajos["CATEGORIA"] = trabajos["CATEGORIA"].fillna("Sin categoría").astype(str).str.strip()

    # Conserva únicamente filas útiles: con valor, horas o empresa diligenciada.
    trabajos = trabajos[
        trabajos["VALOR"].notna()
        | trabajos["HORAS"].notna()
        | trabajos["EMPRESA"].ne("Sin empresa")
    ].copy()
    return trabajos


def fig_felicidad_valor_hora_por_empresa(trabajos):
    if trabajos.empty or trabajos["VALOR_HORA"].dropna().empty:
        return go.Figure()
    tmp = (
        trabajos.dropna(subset=["VALOR_HORA"])
        .groupby("EMPRESA", as_index=False)
        .agg(VALOR_HORA=("VALOR_HORA", "mean"), HORAS=("HORAS", "sum"), VALOR=("VALOR", "sum"))
        .sort_values("VALOR_HORA", ascending=False)
    )
    fig = px.bar(
        tmp,
        x="EMPRESA",
        y="VALOR_HORA",
        text="VALOR_HORA",
        hover_data={"HORAS": ":,.1f", "VALOR": ":,.0f", "VALOR_HORA": ":,.0f"},
    )
    fig.update_traces(
        texttemplate="$%{text:,.0f}",
        textposition="outside",
        marker=dict(color=COLOR_BALANCE, line=dict(color="rgba(255,255,255,0.25)", width=1)),
        hovertemplate="Empresa: %{x}<br>Valor hora promedio: $%{y:,.0f}<br>Horas: %{customdata[0]:,.1f}<br>Valor: $%{customdata[1]:,.0f}<extra></extra>",
    )
    fig.update_layout(xaxis_title="Empresa / trabajo", yaxis_title="Valor promedio por hora")
    return estilo_grafico(fig, "Valor promedio por hora trabajada")


def fig_felicidad_valor_hora_por_mes(trabajos):
    """Grafica el valor promedio de la hora trabajada por mes."""
    if trabajos.empty or trabajos["VALOR_HORA"].dropna().empty:
        return go.Figure()

    tmp = trabajos.dropna(subset=["VALOR_HORA"]).copy()
    tmp["MES"] = tmp["MES"].map(normalizar_mes)
    tmp = tmp[tmp["MES"].isin(MESES_ORDEN)]
    if tmp.empty:
        return go.Figure()

    resumen = (
        tmp.groupby("MES", as_index=False)
        .agg(VALOR_HORA=("VALOR_HORA", "mean"), HORAS=("HORAS", "sum"), VALOR=("VALOR", "sum"))
    )
    resumen["_ORDEN"] = resumen["MES"].map(MESES_NUM)
    resumen = resumen.sort_values("_ORDEN").drop(columns="_ORDEN")

    fig = px.line(
        resumen,
        x="MES",
        y="VALOR_HORA",
        markers=True,
        text="VALOR_HORA",
        hover_data={"HORAS": ":,.1f", "VALOR": ":,.0f", "VALOR_HORA": ":,.0f"},
        category_orders={"MES": MESES_ORDEN},
    )
    fig.update_traces(
        texttemplate="$%{text:,.0f}",
        textposition="top center",
        line=dict(color=COLOR_BALANCE, width=3),
        marker=dict(size=11, color=COLOR_BALANCE, line=dict(color="rgba(255,255,255,0.8)", width=1.5)),
        hovertemplate="Mes: %{x}<br>Valor hora promedio: $%{y:,.0f}<br>Horas: %{customdata[0]:,.1f}<br>Valor: $%{customdata[1]:,.0f}<extra></extra>",
    )
    fig.update_layout(xaxis_title="Mes", yaxis_title="Valor promedio por hora")
    return estilo_grafico(fig, "Valor promedio de la hora trabajada por mes")


def resumen_ingresos_laborales_no_laborales(ingresos_df):
    """Resume ingresos laborales y no laborales por mes."""
    columnas = ["MES", "Laborales", "No laborales", "Sin clasificar"]
    if ingresos_df.empty:
        return pd.DataFrame(columns=columnas)

    tmp = ingresos_df.copy()
    tmp["MES"] = tmp["MES"].map(normalizar_mes)
    tmp = tmp[tmp["MES"].isin(MESES_ORDEN)]
    if tmp.empty:
        return pd.DataFrame(columns=columnas)

    tmp["TIPO_FUENTE"] = tmp["INGRESOS_CATEGORIA"].map(etiqueta_tipo_ingreso)
    tmp["TIPO_FUENTE"] = tmp["TIPO_FUENTE"].where(tmp["TIPO_FUENTE"].isin(["Laborales", "No laborales", "Sin clasificar"]), "Sin clasificar")

    resumen = (
        tmp.groupby(["MES", "TIPO_FUENTE"], as_index=False)["INGRESOS_CANTIDAD"]
        .sum()
        .pivot(index="MES", columns="TIPO_FUENTE", values="INGRESOS_CANTIDAD")
        .fillna(0)
        .reset_index()
    )
    for col in ["Laborales", "No laborales", "Sin clasificar"]:
        if col not in resumen.columns:
            resumen[col] = 0.0
    resumen["_ORDEN"] = resumen["MES"].map(MESES_NUM)
    resumen = resumen.sort_values("_ORDEN").drop(columns="_ORDEN")
    return resumen[columnas]


def fig_felicidad_ingresos_laborales_vs_no_laborales(ingresos_df):
    """Compara mes a mes ingresos laborales y no laborales."""
    resumen = resumen_ingresos_laborales_no_laborales(ingresos_df)
    if resumen.empty:
        return go.Figure()

    fig = px.bar(
        resumen,
        x="MES",
        y=["Laborales", "No laborales", "Sin clasificar"],
        barmode="group",
        text_auto=False,
        category_orders={"MES": MESES_ORDEN},
        color_discrete_map={"Laborales": "#00FF88", "No laborales": "#00B7FF", "Sin clasificar": "#B026FF"},
    )
    fig.update_traces(
        texttemplate="$%{y:,.0f}",
        textposition="outside",
        marker=dict(line=dict(color="rgba(255,255,255,0.25)", width=1)),
        hovertemplate="Mes: %{x}<br>Tipo: %{fullData.name}<br>Ingreso: $%{y:,.0f}<extra></extra>",
    )
    fig.update_layout(xaxis_title="Mes", yaxis_title="Ingresos", legend_title="Tipo de ingreso")
    return estilo_grafico(fig, "Ingresos laborales vs no laborales por mes")


def convertir_trabajos_a_ingresos(trabajos):
    """Convierte Transaccional!K:Q al formato estándar de ingresos.

    La fecha real define MES y ANIO. Esto evita depender de matrices
    auxiliares o textos manuales de la hoja Ingresos.
    """
    columnas = [
        "MES", "INGRESOS_FECHA", "INGRESOS_CANTIDAD",
        "INGRESOS_DESCRIPCION", "INGRESOS_CATEGORIA",
        "INGRESOS_FUENTE", "ANIO"
    ]
    if trabajos is None or trabajos.empty:
        return pd.DataFrame(columns=columnas)

    ingresos = trabajos.copy()
    ingresos["FECHA"] = pd.to_datetime(ingresos["FECHA"], errors="coerce")
    ingresos["VALOR"] = pd.to_numeric(ingresos["VALOR"], errors="coerce")
    ingresos = ingresos[
        ingresos["FECHA"].notna()
        & ingresos["VALOR"].notna()
        & ingresos["VALOR"].ne(0)
    ].copy()

    if ingresos.empty:
        return pd.DataFrame(columns=columnas)

    meses_numero = {v: k for k, v in MESES_NUM.items()}
    ingresos["MES"] = ingresos["FECHA"].dt.month.map(meses_numero)
    ingresos["ANIO"] = ingresos["FECHA"].dt.year.astype("Int64")
    ingresos["INGRESOS_FECHA"] = ingresos["FECHA"]
    ingresos["INGRESOS_CANTIDAD"] = ingresos["VALOR"].astype(float)
    ingresos["INGRESOS_FUENTE"] = (
        ingresos["EMPRESA"].fillna("Sin fuente").astype(str).str.strip()
    )
    ingresos["INGRESOS_CATEGORIA"] = (
        ingresos["CATEGORIA"].fillna("NO LABORAL").astype(str).str.strip().str.upper()
    )
    ingresos["INGRESOS_DESCRIPCION"] = ingresos["INGRESOS_FUENTE"]
    return ingresos[columnas].reset_index(drop=True)


@st.cache_data
def cargar_excel(file, trm_usd_cop=None):
    """Carga el Excel de Altium de forma flexible.

    Esta versión acepta la Transaccional con gastos en A:H y el bloque de trabajos/ingresos en K:Q.
    También conserva compatibilidad con versiones anteriores de la plantilla.
    """
    try:
        df_raw = pd.read_excel(file, sheet_name="Transaccional")
    except Exception:
        df_raw = pd.read_excel(file, sheet_name="Transaccional", skiprows=1)

    # Si por alguna razón la primera fila no quedó como encabezado, intenta el formato anterior.
    cols_norm = [normalizar(c) for c in df_raw.columns]
    if "MES" not in cols_norm and df_raw.shape[1] >= 12:
        df_raw = pd.read_excel(file, sheet_name="Transaccional", skiprows=1)

    # Renombrado por posición para evitar problemas con columnas duplicadas: FECHA, CANTIDAD, etc.
    if df_raw.shape[1] >= 13:
        df_raw = df_raw.iloc[:, :13].copy()
        df_raw.columns = [
            "MES", "GASTOS_FECHA", "GASTOS_CANTIDAD", "GASTOS_DESCRIPCION",
            "GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA", "TIPO_GASTO",
            "GASTOS_OBSERVACION", "VACIA", "INGRESOS_FECHA", "INGRESOS_CANTIDAD",
            "INGRESOS_DESCRIPCION", "INGRESOS_CATEGORIA"
        ]
    elif df_raw.shape[1] >= 12:
        df_raw = df_raw.iloc[:, :12].copy()
        df_raw.columns = [
            "MES", "GASTOS_FECHA", "GASTOS_CANTIDAD", "GASTOS_DESCRIPCION",
            "GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA", "GASTOS_SUBCATEGORIA_2",
            "VACIA", "INGRESOS_FECHA", "INGRESOS_CANTIDAD",
            "INGRESOS_DESCRIPCION", "INGRESOS_CATEGORIA"
        ]
        df_raw["TIPO_GASTO"] = pd.NA
        df_raw["GASTOS_OBSERVACION"] = pd.NA
    else:
        st.error("La hoja Transaccional no tiene suficientes columnas para cargar gastos e ingresos.")
        return (
            pd.DataFrame(), pd.DataFrame(), {}, {}, 0.0,
            pd.DataFrame(columns=[
                "Fecha", "Tipo", "Categoría", "Subcategoría", "Descripción", "Entidad",
                "Valor actual", "Saldo pendiente", "Valor neto", "Fecha compra",
                "Fecha valoración", "Estado", "Observaciones", "Liquidez"
            ]),
            pd.DataFrame(columns=["Meta", "Objetivo", "Actual", "Avance"]),
            {"nombre": "Sin registrar", "fecha_nacimiento": pd.NaT, "edad": None},
            pd.DataFrame(columns=["FECHA", "VALOR", "EMPRESA", "MES", "CATEGORIA", "HORAS", "VALOR_HORA"]),
            pd.DataFrame(columns=["CATEGORIA", "CONCEPTO", "ANIO", "MES", "PRESUPUESTO", "FUENTE"])
        )

    # En la nueva plantilla no existe GASTOS_SUBCATEGORIA_2; se crea vacía para no romper gráficos previos.
    if "GASTOS_SUBCATEGORIA_2" not in df_raw.columns:
        df_raw["GASTOS_SUBCATEGORIA_2"] = pd.NA

    gastos_cols = [
        "MES", "GASTOS_FECHA", "GASTOS_CANTIDAD", "GASTOS_DESCRIPCION",
        "GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA", "GASTOS_SUBCATEGORIA_2",
        "TIPO_GASTO", "GASTOS_OBSERVACION"
    ]
    gastos = df_raw[gastos_cols].copy()

    gastos = gastos.dropna(subset=["GASTOS_CANTIDAD"])
    gastos["MES"] = gastos["MES"].map(normalizar_mes)
    gastos["GASTOS_CANTIDAD"] = pd.to_numeric(gastos["GASTOS_CANTIDAD"], errors="coerce").fillna(0)
    gastos["GASTOS_FECHA"] = pd.to_datetime(gastos["GASTOS_FECHA"], errors="coerce")
    gastos["ANIO"] = gastos["GASTOS_FECHA"].dt.year

    anio_ref = int(gastos["ANIO"].dropna().max()) if not gastos["ANIO"].dropna().empty else 2026

    # Fuente principal: bloque real de ingresos y trabajos en Transaccional!K:Q.
    felicidad_trabajos = leer_felicidad_trabajos(file)
    ingresos = convertir_trabajos_a_ingresos(felicidad_trabajos)

    # Compatibilidad con plantillas antiguas que no tengan el bloque K:Q.
    if ingresos.empty:
        ingresos = parse_ingresos_hoja(file, anio_ref=anio_ref)

    presupuesto_cat, presupuesto_sub = parse_presupuesto_datos(file)
    presupuesto_mensual_general = leer_presupuesto_mensual_general(file)
    historico_presupuesto = parse_historico_presupuesto(file)
    patrimonio = leer_patrimonio_excel(file, trm_usd_cop=trm_usd_cop)
    metas = leer_metas_excel(file)
    personales = leer_datos_personales(file)

    return gastos, ingresos, presupuesto_cat, presupuesto_sub, presupuesto_mensual_general, patrimonio, metas, personales, felicidad_trabajos, historico_presupuesto




# ============================================================
# FELICIDAD V13 · TRABAJO, TIEMPO Y BIENESTAR FINANCIERO
# ============================================================
def resumen_felicidad_por_empresa(trabajos):
    """Consolida ingresos, horas, valor/hora y eficiencia relativa por empresa."""
    columnas = [
        "EMPRESA", "INGRESOS", "HORAS", "VALOR_HORA", "PART_INGRESOS",
        "PART_HORAS", "EFICIENCIA_RELATIVA", "BRECHA_PARTICIPACION",
    ]
    if trabajos is None or trabajos.empty or "EMPRESA" not in trabajos.columns:
        return pd.DataFrame(columns=columnas)
    tmp = trabajos.copy()
    tmp["EMPRESA"] = tmp["EMPRESA"].fillna("Sin empresa").astype(str).str.strip().replace("", "Sin empresa")
    tmp["VALOR"] = pd.to_numeric(tmp.get("VALOR", 0), errors="coerce").fillna(0)
    tmp["HORAS"] = pd.to_numeric(tmp.get("HORAS", 0), errors="coerce").fillna(0).clip(lower=0)
    resumen = tmp.groupby("EMPRESA", as_index=False).agg(INGRESOS=("VALOR", "sum"), HORAS=("HORAS", "sum"))
    resumen["VALOR_HORA"] = resumen.apply(lambda r: r["INGRESOS"] / r["HORAS"] if r["HORAS"] > 0 else 0.0, axis=1)
    total_ingresos = float(resumen["INGRESOS"].sum())
    total_horas = float(resumen["HORAS"].sum())
    resumen["PART_INGRESOS"] = resumen["INGRESOS"] / total_ingresos * 100 if total_ingresos else 0.0
    resumen["PART_HORAS"] = resumen["HORAS"] / total_horas * 100 if total_horas else 0.0
    resumen["EFICIENCIA_RELATIVA"] = resumen.apply(
        lambda r: r["PART_INGRESOS"] / r["PART_HORAS"] if r["PART_HORAS"] > 0 else 0.0,
        axis=1,
    )
    resumen["BRECHA_PARTICIPACION"] = resumen["PART_INGRESOS"] - resumen["PART_HORAS"]
    return resumen.sort_values(["EFICIENCIA_RELATIVA", "INGRESOS"], ascending=[False, False]).reset_index(drop=True)


def fig_felicidad_matriz_eficiencia(resumen):
    """Matriz horas vs valor por hora; el tamaño representa ingresos."""
    if resumen is None or resumen.empty:
        return go.Figure()
    fig = px.scatter(
        resumen,
        x="HORAS",
        y="VALOR_HORA",
        size="INGRESOS",
        color="EMPRESA",
        hover_name="EMPRESA",
        custom_data=["INGRESOS", "PART_INGRESOS", "PART_HORAS", "EFICIENCIA_RELATIVA"],
        size_max=58,
        labels={"HORAS": "Horas trabajadas", "VALOR_HORA": "Valor por hora"},
    )
    med_horas = float(resumen["HORAS"].median()) if not resumen.empty else 0
    med_valor = float(resumen["VALOR_HORA"].median()) if not resumen.empty else 0
    fig.add_vline(x=med_horas, line_dash="dot", line_color="#94A3B8")
    fig.add_hline(y=med_valor, line_dash="dot", line_color="#94A3B8")
    fig.update_traces(hovertemplate=(
        "<b>%{hovertext}</b><br>Horas: %{x:,.1f}<br>Valor/hora: $%{y:,.0f}"
        "<br>Ingresos: $%{customdata[0]:,.0f}<br>% ingresos: %{customdata[1]:.1f}%"
        "<br>% horas: %{customdata[2]:.1f}%<br>Eficiencia relativa: %{customdata[3]:.2f}x<extra></extra>"
    ))
    fig = estilo_grafico(fig, "Matriz de eficiencia laboral")
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    fig.update_layout(height=480, showlegend=False)
    return fig


def fig_felicidad_ingresos_horas_mes(trabajos):
    """Compara ingresos y horas mensuales con doble eje, sin ocultar sus escalas."""
    if trabajos is None or trabajos.empty or "FECHA" not in trabajos.columns:
        return go.Figure()
    tmp = trabajos.copy()
    tmp["FECHA"] = pd.to_datetime(tmp["FECHA"], errors="coerce")
    tmp["VALOR"] = pd.to_numeric(tmp.get("VALOR", 0), errors="coerce").fillna(0)
    tmp["HORAS"] = pd.to_numeric(tmp.get("HORAS", 0), errors="coerce").fillna(0)
    tmp = tmp.dropna(subset=["FECHA"])
    if tmp.empty:
        return go.Figure()
    tmp["PERIODO"] = tmp["FECHA"].dt.to_period("M").astype(str)
    mensual = tmp.groupby("PERIODO", as_index=False).agg(INGRESOS=("VALOR", "sum"), HORAS=("HORAS", "sum"))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=mensual["PERIODO"], y=mensual["INGRESOS"], name="Ingresos", marker_color=COLOR_INGRESOS,
                         hovertemplate="%{x}<br>Ingresos: $%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=mensual["PERIODO"], y=mensual["HORAS"], name="Horas", yaxis="y2", mode="lines+markers",
                             line=dict(color=COLOR_PRESUPUESTO, width=3), hovertemplate="%{x}<br>Horas: %{y:,.1f}<extra></extra>"))
    fig = estilo_grafico(fig, "Ingresos y carga laboral por mes")
    fig.update_layout(
        height=430,
        yaxis=dict(title="Ingresos", tickprefix="$", tickformat=",.0f"),
        yaxis2=dict(title="Horas", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center"),
    )
    return fig


def fig_felicidad_concentracion_empresa(resumen):
    if resumen is None or resumen.empty:
        return go.Figure()
    orden = resumen.sort_values("PART_INGRESOS", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=orden["EMPRESA"], x=orden["PART_INGRESOS"], orientation="h", name="% ingresos", marker_color=COLOR_INGRESOS))
    fig.add_trace(go.Bar(y=orden["EMPRESA"], x=orden["PART_HORAS"], orientation="h", name="% horas", marker_color=COLOR_PRESUPUESTO))
    fig = estilo_grafico(fig, "Concentración de ingresos y tiempo")
    fig.update_layout(barmode="group", height=max(420, 42 * len(orden) + 160), legend=dict(orientation="h", y=1.06, x=.5, xanchor="center"))
    fig.update_xaxes(title="Participación", ticksuffix="%")
    return fig
