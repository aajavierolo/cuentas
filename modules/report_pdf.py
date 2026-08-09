from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Iterable, Optional
from xml.sax.saxutils import escape
import hashlib

_original_md5 = hashlib.md5

def _md5_compatible(*args, **kwargs):
    kwargs.pop("usedforsecurity", None)
    return _original_md5(*args, **kwargs)

hashlib.md5 = _md5_compatible

import matplotlib

# Docker no tiene una pantalla grafica. Agg permite crear los graficos del PDF
# completamente en memoria tanto en el contenedor como en ejecuciones locales.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
import textwrap
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

PAGE = landscape(A4)
DARK = colors.HexColor("#07111F")
PANEL = colors.HexColor("#0F2238")
BLUE = colors.HexColor("#38BDF8")
GREEN = colors.HexColor("#34D399")
RED = colors.HexColor("#FB7185")
YELLOW = colors.HexColor("#FDE68A")
PURPLE = colors.HexColor("#C084FC")
TEXT = colors.HexColor("#E2E8F0")
MUTED = colors.HexColor("#64748B")
WHITE = colors.white
INK = colors.HexColor("#172033")

# Paleta de impresión: contrastes altos sobre fondo claro.
PDF_BLUE = "#2563EB"
PDF_CYAN = "#06B6D4"
PDF_GREEN = "#00B85A"
PDF_RED = "#E6002D"
PDF_ORANGE = "#F97316"
PDF_PURPLE = "#8B5CF6"
PDF_YELLOW = "#EAB308"
PDF_PALETTE = [PDF_BLUE, PDF_CYAN, PDF_GREEN, PDF_ORANGE, PDF_PURPLE, PDF_RED, PDF_YELLOW, "#14B8A6", "#EC4899", "#84CC16", "#0EA5E9", "#A855F7"]

QUESTIONS = [
    ("1. Resumen", "¿Cómo estoy hoy?", "Sintetiza ingresos, gastos, balance, ahorro y señales prioritarias."),
    ("2. Gastos", "¿En qué se me va el dinero?", "Explica la concentración del gasto por categorías y tipos."),
    ("3. Tendencias", "¿Cómo he evolucionado?", "Compara el comportamiento mensual de ingresos, gastos y balance."),
    ("4. Presupuesto", "¿Estoy cumpliendo mis metas?", "Contrasta la ejecución mensual con el presupuesto disponible."),
    ("5. Ingresos", "¿De dónde proviene el dinero?", "Identifica las principales fuentes y su participación."),
    ("6. Deudas", "¿Qué obligaciones tengo?", "Resume saldos, intereses, pagos y prioridades."),
    ("7. Patrimonio", "¿Cuál es mi riqueza?", "Presenta la composición patrimonial disponible en el archivo."),
    ("8. Score", "¿Qué tan saludable es mi situación financiera?", "Integra ahorro, gasto, deuda y balance en una lectura referencial."),
    ("9. Felicidad", "¿Mi dinero está alineado con mi bienestar?", "Relaciona empresa, horas trabajadas, valor por hora, tipo de ingreso y patrimonio esperado."),
]


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def _number(value: Any) -> str:
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(value)

def _income_type(value: Any) -> str:
    """Clasifica ingresos sin confundir NO LABORAL con LABORAL."""
    if value is None:
        return "Sin clasificar"
    text = str(value).strip().upper().replace("-", " ").replace("_", " ")
    text = " ".join(text.split())
    if not text or text in {"NAN", "NONE", "SIN TIPO", "SIN CLASIFICAR"}:
        return "Sin clasificar"
    if text in {"NO LABORAL", "NO LABORALES", "NO LABOR", "NO LABORA"} or text.startswith("NO LABOR"):
        return "No laborales"
    if text in {"LABORAL", "LABORALES"}:
        return "Laborales"
    if any(token in text for token in ["SALARIO", "SALARIAL", "NOMINA", "EMPLEO", "HONORARIO", "CONTRATO LABORAL"]):
        return "Laborales"
    return "Sin clasificar"


def _safe_text(value: Any, max_len: int = 85) -> str:
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value)
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return escape(text, entities={"\n": "<br/>"})


def _footer(canvas, doc):
    canvas.saveState()
    width, _ = PAGE
    canvas.setFillColor(DARK)
    canvas.rect(0, 0, width, 0.65 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#CBD5E1"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(1.2 * cm, 0.25 * cm, "Altium Financiero V12 - Informe por preguntas")
    canvas.drawRightString(width - 1.2 * cm, 0.25 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=DARK, alignment=TA_CENTER, spaceAfter=8),
        "subtitle": ParagraphStyle("Subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=10.5, leading=15, textColor=MUTED, alignment=TA_CENTER),
        "section": ParagraphStyle("Section", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=19, textColor=BLUE, spaceBefore=3, spaceAfter=3),
        "question": ParagraphStyle("Question", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=INK, spaceAfter=3),
        "answer": ParagraphStyle("Answer", parent=base["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=MUTED, spaceAfter=8),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=8.7, leading=12.5, textColor=INK),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.2, leading=9.2, textColor=INK),
        "table_header": ParagraphStyle("TH", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.2, leading=9, textColor=WHITE),
        "card_title": ParagraphStyle("CardTitle", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.HexColor("#CBD5E1"), alignment=TA_CENTER),
        "card_value": ParagraphStyle("CardValue", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=WHITE, alignment=TA_CENTER),
    }


def _question_header(index: int, styles):
    title, question, answer = QUESTIONS[index]
    box = Table([
        [Paragraph(title, styles["section"])],
        [Paragraph(question, styles["question"])],
        [Paragraph(answer, styles["answer"])],
    ], colWidths=[PAGE[0] - 2.4 * cm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF8FF")),
        ("BOX", (0, 0), (-1, -1), 0.8, BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return box


def _kpi_table(items: Iterable[tuple[str, str]], styles):
    items = list(items)
    usable = PAGE[0] - 2.4 * cm
    table = Table([
        [Paragraph(t, styles["card_title"]) for t, _ in items],
        [Paragraph(v, styles["card_value"]) for _, v in items],
    ], colWidths=[usable / max(len(items), 1)] * len(items), rowHeights=[0.56 * cm, 0.88 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#24445F")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _hero_table(nombre_persona: str, edad_persona: Any, fecha_desde: Any, fecha_hasta: Any, styles):
    """Portada compacta con la misma identidad oscura y neon del dashboard."""
    usable = PAGE[0] - 2.4 * cm
    hero_title = Paragraph("ALTIUM FINANCIERO V12", ParagraphStyle(
        "HeroTitle", parent=styles["title"], fontSize=25, leading=29,
        textColor=WHITE, alignment=TA_LEFT, spaceAfter=3,
    ))
    hero_tag = Paragraph(
        "INFORME FINANCIERO EJECUTIVO  /  DATOS, DECISIONES Y PROYECCION",
        ParagraphStyle("HeroTag", parent=styles["small"], fontName="Helvetica-Bold",
                       fontSize=8, leading=10, textColor=GREEN, alignment=TA_LEFT),
    )
    person = Paragraph(
        f"<b>{_safe_text(nombre_persona, 120)}</b><br/>"
        f"Edad: {_safe_text(edad_persona)}<br/>"
        f"Periodo: {_safe_text(fecha_desde)} a {_safe_text(fecha_hasta)}",
        ParagraphStyle("HeroPerson", parent=styles["body"], fontSize=9.5, leading=14,
                       textColor=TEXT, alignment=TA_LEFT),
    )
    table = Table([[hero_tag, person], [hero_title, person]], colWidths=[usable * .70, usable * .30])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("SPAN", (1, 0), (1, 1)),
        ("BOX", (0, 0), (-1, -1), 1.1, BLUE),
        ("LINEBELOW", (0, 0), (0, 0), .6, colors.HexColor("#1E4C68")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def _insight_box(title: str, body: str, styles, tone: str = "blue"):
    """Bloque breve para explicar el significado de los datos, no solo mostrarlos."""
    accents = {"blue": BLUE, "green": GREEN, "red": RED, "yellow": colors.HexColor("#EAB308"), "purple": PURPLE}
    backgrounds = {
        "blue": colors.HexColor("#EFF8FF"), "green": colors.HexColor("#ECFDF5"),
        "red": colors.HexColor("#FFF1F2"), "yellow": colors.HexColor("#FFFBEB"),
        "purple": colors.HexColor("#FAF5FF"),
    }
    accent = accents.get(tone, BLUE)
    background = backgrounds.get(tone, backgrounds["blue"])
    content = Paragraph(
        f"<b>{_safe_text(title, 100)}</b><br/>{body}",
        ParagraphStyle("InsightBody", parent=styles["body"], fontSize=8.3, leading=11.5,
                       textColor=INK, spaceAfter=0),
    )
    usable = PAGE[0] - 2.4 * cm
    box = Table([["", content]], colWidths=[.16 * cm, usable - .16 * cm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BACKGROUND", (0, 0), (0, 0), accent),
        ("BOX", (0, 0), (-1, -1), .45, accent),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (1, 0), (1, 0), 9),
        ("RIGHTPADDING", (1, 0), (1, 0), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return box


def _format_df(df: pd.DataFrame, money_cols: Optional[Iterable[str]] = None) -> pd.DataFrame:
    out = pd.DataFrame() if df is None else df.copy()
    money_cols = set(money_cols or [])
    for col in out.columns:
        if col in money_cols:
            out[col] = out[col].map(_money)
        elif pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
        elif pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(_number)
        else:
            out[col] = out[col].map(_safe_text)
    return out


def _df_table(df: pd.DataFrame, styles, money_cols=None, max_rows=25, col_widths=None):
    if df is None or df.empty:
        return Paragraph("No se encontraron datos para esta sección.", styles["body"])
    view = _format_df(df.head(max_rows), money_cols)
    data = [[Paragraph(_safe_text(c), styles["table_header"]) for c in view.columns]]
    for row in view.itertuples(index=False, name=None):
        data.append([Paragraph(_safe_text(v), styles["small"]) for v in row])
    usable = PAGE[0] - 2.4 * cm
    widths = col_widths or [usable / max(len(view.columns), 1)] * len(view.columns)
    table = Table(data, repeatRows=1, colWidths=widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173A59")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.HexColor("#E8F0F7")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#90A4B7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _wrap_labels(values, width: int = 24):
    """Divide etiquetas largas para que no desaparezcan al lado izquierdo."""
    return ["\n".join(textwrap.wrap(str(v), width=width)) or "Sin dato" for v in values]


def _style_print_axis(ax, grid_axis="y"):
    ax.set_facecolor("#F8FAFC")
    ax.figure.patch.set_facecolor("white")
    ax.grid(axis=grid_axis, color="#CBD5E1", alpha=0.55, linewidth=0.7)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#94A3B8")
    ax.spines["bottom"].set_color("#94A3B8")
    ax.tick_params(axis="both", labelsize=8.5, colors="#334155")
    ax.xaxis.label.set_color("#334155")
    ax.yaxis.label.set_color("#334155")
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}")) if grid_axis == "y" else None


def _save_fig(fig) -> BytesIO:
    buff = BytesIO()
    fig.savefig(buff, format="png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buff.seek(0)
    return buff


def _chart_flow(flujo: pd.DataFrame, title="Ingresos, gastos y balance mensual") -> Optional[BytesIO]:
    if flujo is None or flujo.empty or "MES" not in flujo.columns:
        return None
    f = flujo.copy()
    ingresos = pd.to_numeric(f.get("Ingresos", 0), errors="coerce").fillna(0)
    gastos = pd.to_numeric(f.get("Gastos", 0), errors="coerce").fillna(0)
    balance = pd.to_numeric(f.get("Balance", ingresos - gastos), errors="coerce").fillna(0)
    x = list(range(len(f)))
    fig, ax = plt.subplots(figsize=(11.2, 3.8))
    ax.bar([i - .19 for i in x], ingresos, width=.38, label="Ingresos", color=PDF_GREEN, edgecolor="#047857", linewidth=.6)
    ax.bar([i + .19 for i in x], gastos, width=.38, label="Gastos", color=PDF_RED, edgecolor="#BE123C", linewidth=.6)
    ax.plot(x, balance, marker="o", markersize=5.5, linewidth=2.5, label="Balance", color=PDF_BLUE)
    ax.axhline(0, linewidth=.9, color="#64748B")
    ax.set_xticks(x, f["MES"].astype(str).tolist(), rotation=25, ha="right")
    ax.set_ylabel("Valor")
    ax.set_title(title, fontsize=12.5, fontweight="bold", color="#0F172A", pad=14)
    _style_print_axis(ax, "y")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(.5, 1.01), frameon=False)
    fig.subplots_adjust(left=.10, right=.98, top=.82, bottom=.22)
    return _save_fig(fig)



def _chart_income_stability(ingresos: pd.DataFrame) -> Optional[BytesIO]:
    if ingresos is None or ingresos.empty or "INGRESOS_FECHA" not in ingresos.columns or "INGRESOS_CANTIDAD" not in ingresos.columns:
        return None
    tmp = ingresos.copy()
    tmp["INGRESOS_FECHA"] = pd.to_datetime(tmp["INGRESOS_FECHA"], errors="coerce", dayfirst=True)
    tmp["INGRESOS_CANTIDAD"] = pd.to_numeric(tmp["INGRESOS_CANTIDAD"], errors="coerce").fillna(0)
    tmp = tmp.dropna(subset=["INGRESOS_FECHA"])
    if tmp.empty:
        return None
    tmp["PERIODO"] = tmp["INGRESOS_FECHA"].dt.strftime("%Y-%m")
    monthly = tmp.groupby("PERIODO")["INGRESOS_CANTIDAD"].sum().sort_index()
    avg = float(monthly.mean()) if not monthly.empty else 0.0
    fig, ax = plt.subplots(figsize=(11.2, 4.0))
    bars = ax.bar(monthly.index, monthly.values, color=PDF_GREEN, edgecolor="white", linewidth=.9)
    ax.axhline(avg, color="#F4B400", linewidth=2.6, linestyle="--", label=f"Promedio ${avg:,.0f}")
    ax.set_title("Estabilidad mensual de los ingresos", fontsize=12.5, fontweight="bold", color="#0F172A", pad=14)
    ax.set_ylabel("Ingreso")
    ax.tick_params(axis="x", rotation=25)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    _style_print_axis(ax, "y")
    ax.legend(frameon=False, loc="upper center")
    ax.bar_label(bars, labels=[f"${v:,.0f}" for v in monthly.values], padding=4, fontsize=7.5, color="#334155")
    fig.subplots_adjust(left=.12, right=.97, top=.80, bottom=.22)
    return _save_fig(fig)


def _chart_budget(flujo: pd.DataFrame) -> Optional[BytesIO]:
    if flujo is None or flujo.empty or "MES" not in flujo.columns or "Presupuesto mensual" not in flujo.columns:
        return None
    f = flujo.copy()
    gasto = pd.to_numeric(f.get("Gastos", 0), errors="coerce").fillna(0)
    pres = pd.to_numeric(f.get("Presupuesto mensual", 0), errors="coerce").fillna(0)
    x = list(range(len(f)))
    bar_colors = [PDF_GREEN if p > 0 and g <= p else PDF_RED if p > 0 else "#94A3B8" for g, p in zip(gasto, pres)]
    fig, ax = plt.subplots(figsize=(11.2, 3.9))
    bars = ax.bar(x, gasto, width=.58, label="Gasto real", color=bar_colors, edgecolor="white", linewidth=.9)
    ax.plot(x, pres, marker="D", markersize=5.5, linewidth=2.8, linestyle="--", label="Presupuesto", color="#F4B400")
    ax.set_xticks(x, f["MES"].astype(str).tolist(), rotation=25, ha="right")
    ax.set_ylabel("Valor")
    ax.set_title("Ejecución mensual frente al presupuesto", fontsize=12.5, fontweight="bold", color="#0F172A", pad=14)
    _style_print_axis(ax, "y")
    ax.legend(frameon=False, loc="upper center", ncol=3)
    fig.subplots_adjust(left=.10, right=.98, top=.80, bottom=.22)
    return _save_fig(fig)


def _chart_happiness_company(felicidad: pd.DataFrame) -> Optional[BytesIO]:
    """Muestra valor hora por empresa, que es la lectura central de la pestaña Felicidad."""
    if felicidad is None or felicidad.empty or "EMPRESA" not in felicidad.columns:
        return None
    tmp = felicidad.copy()
    for col in ["VALOR", "HORAS", "VALOR_HORA"]:
        if col in tmp.columns:
            tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
    if "VALOR_HORA" not in tmp.columns:
        return None
    resumen = (
        tmp.dropna(subset=["VALOR_HORA"])
        .groupby("EMPRESA", as_index=False)
        .agg(VALOR_HORA=("VALOR_HORA", "mean"), HORAS=("HORAS", "sum"), VALOR=("VALOR", "sum"))
        .sort_values("VALOR_HORA", ascending=True)
        .tail(12)
    )
    if resumen.empty:
        return None
    labels = _wrap_labels(resumen["EMPRESA"], 23)
    fig, ax = plt.subplots(figsize=(11.2, max(4.2, .45 * len(resumen) + 1.6)))
    bars = ax.barh(labels, resumen["VALOR_HORA"], color=PDF_PURPLE, edgecolor="white", linewidth=.8)
    ax.set_xlabel("Valor promedio por hora")
    ax.set_title("Valor por hora según empresa o trabajo", fontsize=12.5, fontweight="bold", color="#0F172A", pad=12)
    _style_print_axis(ax, "x")
    ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax.bar_label(bars, labels=[f"${v:,.0f}" for v in resumen["VALOR_HORA"]], padding=4, fontsize=7.5, color="#334155")
    fig.subplots_adjust(left=.31, right=.91, top=.88, bottom=.14)
    return _save_fig(fig)


def _chart_happiness_income_mix(felicidad: pd.DataFrame) -> Optional[BytesIO]:
    if felicidad is None or felicidad.empty or "CATEGORIA" not in felicidad.columns or "VALOR" not in felicidad.columns:
        return None
    tmp = felicidad.copy()
    tmp["VALOR"] = pd.to_numeric(tmp["VALOR"], errors="coerce").fillna(0)
    tmp["TIPO"] = tmp["CATEGORIA"].map(_income_type)
    resumen = tmp.groupby("TIPO")["VALOR"].sum()
    if resumen.empty or resumen.sum() == 0:
        return None
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    ax.pie(resumen.values, labels=resumen.index, autopct="%1.1f%%", startangle=90,
           colors=[PDF_GREEN, PDF_BLUE], wedgeprops={"width": .46, "edgecolor": "white", "linewidth": 1.2},
           textprops={"fontsize": 8.5, "color": "#334155"})
    ax.set_title("Ingresos laborales y no laborales", fontsize=12.5, fontweight="bold", color="#0F172A", pad=12)
    return _save_fig(fig)

def _chart_group(df: pd.DataFrame, group_col: str, value_col: str, title: str, top=12) -> Optional[BytesIO]:
    if df is None or df.empty or group_col not in df.columns or value_col not in df.columns:
        return None
    values = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
    tmp = df.assign(_valor=values).groupby(group_col, dropna=False)["_valor"].sum().sort_values().tail(top)
    if tmp.empty:
        return None
    labels = _wrap_labels(tmp.index, width=25)
    height = max(4.2, 0.42 * len(tmp) + 1.6)
    fig, ax = plt.subplots(figsize=(11.2, height))
    colors_bar = [PDF_PALETTE[i % len(PDF_PALETTE)] for i in range(len(tmp))]
    bars = ax.barh(labels, tmp.values, color=colors_bar, edgecolor="white", linewidth=.7)
    ax.set_xlabel("Valor")
    ax.set_title(title, fontsize=12.5, fontweight="bold", color="#0F172A", pad=12)
    _style_print_axis(ax, "x")
    ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax.bar_label(bars, labels=[f"${v:,.0f}" for v in tmp.values], padding=4, fontsize=7.5, color="#334155")
    # Margen izquierdo amplio: evita que desaparezcan categorías largas.
    fig.subplots_adjust(left=.31, right=.91, top=.88, bottom=.14)
    return _save_fig(fig)


def _chart_fixed_variable(gastos: pd.DataFrame) -> Optional[BytesIO]:
    if gastos is None or gastos.empty or "TIPO_GASTO" not in gastos.columns:
        return None
    tmp = gastos.groupby("TIPO_GASTO")["GASTOS_CANTIDAD"].sum().sort_values(ascending=False)
    if tmp.empty:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    colors_pie = [PDF_PALETTE[i % len(PDF_PALETTE)] for i in range(len(tmp))]
    ax.pie(tmp.values, labels=_wrap_labels(tmp.index, 17), autopct="%1.1f%%", startangle=90,
           colors=colors_pie, pctdistance=.78, labeldistance=1.08,
           wedgeprops={"width": .43, "edgecolor": "white", "linewidth": 1.2},
           textprops={"fontsize": 8, "color": "#334155"})
    ax.set_title("Composición por tipo de gasto", fontsize=12.5, fontweight="bold", color="#0F172A", pad=12)
    fig.subplots_adjust(left=.08, right=.92, top=.86, bottom=.08)
    return _save_fig(fig)


def _best_label_column(df: pd.DataFrame, title: str, value_col: str) -> Optional[str]:
    """Selecciona una columna descriptiva y evita usar fechas como etiquetas laterales."""
    candidates = [c for c in df.columns if c != value_col]
    if not candidates:
        return None

    title_norm = str(title).upper()
    if "PATRIMONIO" in title_norm:
        preferred_tokens = ["NOMBRE", "CONCEPTO", "ACTIVO", "ELEMENTO", "DESCRIP", "TIPO", "CATEGORIA"]
    elif "BIENESTAR" in title_norm or "FELICIDAD" in title_norm:
        preferred_tokens = ["NOMBRE", "TRABAJO", "EMPRESA", "FUENTE", "CONCEPTO", "DESCRIP", "ACTIVIDAD"]
    else:
        preferred_tokens = ["NOMBRE", "CONCEPTO", "DESCRIP", "CATEGORIA", "TIPO", "FUENTE"]

    def is_date_column(col: str) -> bool:
        name = str(col).upper()
        if any(token in name for token in ["FECHA", "DATE", "MES", "AÑO", "ANIO"]):
            return True
        return pd.api.types.is_datetime64_any_dtype(df[col])

    non_date = [c for c in candidates if not is_date_column(c)]
    search_space = non_date or candidates

    for token in preferred_tokens:
        for col in search_space:
            if token in str(col).upper():
                return col

    text_cols = [
        c for c in search_space
        if not pd.api.types.is_numeric_dtype(df[c])
        and df[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()
    ]
    if text_cols:
        return max(text_cols, key=lambda c: df[c].astype(str).nunique(dropna=True))
    return search_space[0] if search_space else None


def _best_value_column(df: pd.DataFrame, title: str) -> Optional[str]:
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric:
        return None
    title_norm = str(title).upper()
    preferred = (
        ["VALOR", "MONTO", "SALDO", "PATRIMONIO"]
        if "PATRIMONIO" in title_norm
        else ["FELICIDAD", "PUNTAJE", "VALOR", "INDICE", "NIVEL"]
    )
    for token in preferred:
        for col in numeric:
            if token in str(col).upper():
                return col
    return numeric[-1]


def _chart_generic_numeric(df: pd.DataFrame, title: str) -> Optional[BytesIO]:
    if df is None or df.empty:
        return None
    value_col = _best_value_column(df, title)
    if value_col is None:
        return None
    label_col = _best_label_column(df, title, value_col)
    if label_col is None:
        return None
    return _chart_group(df, label_col, value_col, title, top=10)


def _projection_data(gastos: pd.DataFrame, ingresos: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Replica la proyeccion del dashboard: salarios laborales menos gastos."""
    ing = pd.DataFrame() if ingresos is None else ingresos.copy()
    gas = pd.DataFrame() if gastos is None else gastos.copy()
    if ing.empty and gas.empty:
        return None

    salary_monthly = pd.Series(dtype=float)
    if {"INGRESOS_FECHA", "INGRESOS_CANTIDAD"}.issubset(ing.columns):
        ing["INGRESOS_FECHA"] = pd.to_datetime(ing["INGRESOS_FECHA"], errors="coerce", dayfirst=True)
        ing["INGRESOS_CANTIDAD"] = pd.to_numeric(ing["INGRESOS_CANTIDAD"], errors="coerce").fillna(0)
        ing = ing.dropna(subset=["INGRESOS_FECHA"])
        category_col = next((c for c in ["INGRESOS_CATEGORIA", "CATEGORIA"] if c in ing.columns), None)
        if category_col:
            ing = ing[ing[category_col].map(_income_type).eq("Laborales")].copy()
        ing["_PERIODO"] = ing["INGRESOS_FECHA"].dt.to_period("M")
        salary_monthly = ing.groupby("_PERIODO")["INGRESOS_CANTIDAD"].sum()

    expense_monthly = pd.Series(dtype=float)
    if {"GASTOS_FECHA", "GASTOS_CANTIDAD"}.issubset(gas.columns):
        gas["GASTOS_FECHA"] = pd.to_datetime(gas["GASTOS_FECHA"], errors="coerce", dayfirst=True)
        gas["GASTOS_CANTIDAD"] = pd.to_numeric(gas["GASTOS_CANTIDAD"], errors="coerce").fillna(0)
        gas = gas.dropna(subset=["GASTOS_FECHA"])
        gas["_PERIODO"] = gas["GASTOS_FECHA"].dt.to_period("M")
        expense_monthly = gas.groupby("_PERIODO")["GASTOS_CANTIDAD"].sum()

    known = sorted(set(salary_monthly.index).union(expense_monthly.index))
    if not known:
        return None
    observed = pd.period_range(known[0], known[-1], freq="M")
    avg_salary = float(salary_monthly.reindex(observed, fill_value=0).mean())
    avg_expense = float(expense_monthly.reindex(observed, fill_value=0).mean())
    monthly_net = avg_salary - avg_expense
    months = 30 * 12
    simple = [monthly_net * month for month in range(1, months + 1)]
    monthly_rate = (1.10 ** (1 / 12)) - 1
    capital = 0.0
    compound = []
    for _ in range(months):
        capital = capital * (1 + monthly_rate) + monthly_net
        compound.append(capital)
    horizons = [10, 20, 30]
    return {
        "observed_months": len(observed),
        "avg_salary": avg_salary,
        "avg_expense": avg_expense,
        "monthly_net": monthly_net,
        "monthly_rate": monthly_rate,
        "simple": simple,
        "compound": compound,
        "simple_horizons": {year: simple[year * 12 - 1] for year in horizons},
        "compound_horizons": {year: compound[year * 12 - 1] for year in horizons},
    }


def _projection_cards(values: Dict[int, float], styles, prefix: str = ""):
    cells = []
    for year in [10, 20, 30]:
        value = float(values.get(year, 0))
        accent = GREEN if value >= 0 else RED
        state = "Saldo a favor" if value >= 0 else "Deuda proyectada"
        cell = Table([
            [Paragraph(f"{prefix}{year} AÑOS", styles["card_title"])],
            [Paragraph(_money(abs(value)), styles["card_value"])],
            [Paragraph(state, ParagraphStyle("ProjectionState", parent=styles["small"],
                                             textColor=accent, alignment=TA_CENTER, fontName="Helvetica-Bold"))],
        ], colWidths=[(PAGE[0] - 3.2 * cm) / 3], rowHeights=[.52 * cm, .72 * cm, .48 * cm])
        cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PANEL),
            ("BOX", (0, 0), (-1, -1), 1.0, accent),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        cells.append(cell)
    outer = Table([cells], colWidths=[(PAGE[0] - 2.4 * cm) / 3] * 3)
    outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return outer


def _chart_projection(data: Dict[str, Any], compound: bool = False) -> Optional[BytesIO]:
    values = data["compound"] if compound else data["simple"]
    if not values:
        return None
    years = [month / 12 for month in range(1, len(values) + 1)]
    positive = [v if v >= 0 else 0 for v in values]
    negative = [v if v < 0 else 0 for v in values]
    fig, ax = plt.subplots(figsize=(11.2, 4.0))
    ax.plot(years, values, color=PDF_YELLOW if compound else PDF_BLUE, linewidth=2.7)
    ax.fill_between(years, 0, positive, color=PDF_GREEN, alpha=.20)
    ax.fill_between(years, 0, negative, color=PDF_RED, alpha=.20)
    ax.axhline(0, color="#64748B", linewidth=1)
    for year in [10, 20, 30]:
        value = values[year * 12 - 1]
        ax.axvline(year, color="#94A3B8", linewidth=.8, linestyle=":")
        ax.scatter([year], [value], s=46, color=PDF_GREEN if value >= 0 else PDF_RED,
                   edgecolor="white", linewidth=.8, zorder=5)
        ax.annotate(f"{year} años\n{_money(value)}", (year, value), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=7.6,
                    color="#172033", fontweight="bold")
    ax.set_xlim(0, 31)
    ax.set_xlabel("Horizonte en años")
    ax.set_ylabel("Capital acumulado")
    ax.set_title("Saldo mensual invertido al 10% efectivo anual" if compound
                 else "Continuidad del saldo promedio entre salarios y gastos",
                 fontsize=12.5, fontweight="bold", color="#0F172A", pad=14)
    _style_print_axis(ax, "y")
    fig.subplots_adjust(left=.12, right=.97, top=.82, bottom=.18)
    return _save_fig(fig)


def _add_chart(story, buff: Optional[BytesIO], width=24.6 * cm, height=8.0 * cm):
    if buff:
        story.extend([Spacer(1, .25 * cm), Image(buff, width=width, height=height), Spacer(1, .2 * cm)])


def generar_informe_financiero_pdf(
    *, nombre_persona: str, edad_persona: Any, fecha_desde: Any, fecha_hasta: Any,
    total_ingresos: float, total_gastos: float, balance: float,
    gastos: pd.DataFrame, ingresos: pd.DataFrame, flujo: pd.DataFrame,
    deudas: pd.DataFrame, patrimonio: pd.DataFrame, metas: Any,
    felicidad: pd.DataFrame, presupuesto_mensual: float = 0.0,
) -> bytes:
    styles = _styles()
    output = BytesIO()
    doc = BaseDocTemplate(
        output, pagesize=PAGE, leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=.9 * cm, bottomMargin=.9 * cm,
        title="Altium Financiero V12 - Informe por preguntas", author="Altium Financiero",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=_footer))
    story = [
        Spacer(1, .4 * cm),
        _hero_table(nombre_persona, edad_persona, fecha_desde, fecha_hasta, styles),
        Spacer(1, .55 * cm),
        _kpi_table([
            ("Ingresos", _money(total_ingresos)), ("Gastos", _money(total_gastos)),
            ("Balance", _money(balance)),
            ("Capacidad de ahorro", f"{(balance / total_ingresos * 100):.1f}%" if total_ingresos else "0,0%"),
        ], styles),
        Spacer(1, .6 * cm),
        Paragraph("Una lectura visual de las nueve preguntas del dashboard, con indicadores, graficos comparativos y escenarios de ahorro a largo plazo. Las proyecciones son orientativas y dependen del periodo filtrado.", styles["body"]),
        PageBreak(),
    ]

    # 1. Resumen
    story += [_question_header(0, styles), Spacer(1, .25 * cm)]
    deuda_saldo = float(pd.to_numeric(deudas.get("Saldo", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if deudas is not None and not deudas.empty else 0.0
    story.append(_kpi_table([
        ("Resultado", "Superávit" if balance >= 0 else "Déficit"),
        ("Transacciones", f"{len(gastos):,}".replace(",", ".")),
        ("Presupuesto mensual", _money(presupuesto_mensual)),
        ("Saldo de deudas", _money(deuda_saldo)),
    ], styles))
    _add_chart(story, _chart_flow(flujo))
    if total_ingresos:
        gasto_pct_resumen = total_gastos / total_ingresos * 100
        resumen_texto = (
            f"El periodo deja un <b>{'superávit' if balance >= 0 else 'déficit'} de {_money(abs(balance))}</b>. "
            f"Por cada $100 recibidos se utilizaron aproximadamente <b>${gasto_pct_resumen:.0f}</b> en gastos. "
            + ("Existe margen para ahorrar, invertir o reducir deuda." if balance >= 0
               else "El gasto supera la capacidad de ingreso y requiere ajustar el presupuesto o aumentar ingresos.")
        )
    else:
        resumen_texto = "No existen ingresos suficientes para medir la relación entre gasto, ahorro y capacidad financiera."
    story.append(_insight_box("Lectura del periodo", resumen_texto, styles, "green" if balance >= 0 else "red"))
    story.append(PageBreak())

    # 2. Gastos
    story += [_question_header(1, styles), Spacer(1, .2 * cm)]
    if gastos is not None and not gastos.empty:
        cat = gastos.groupby("GASTOS_CATEGORIA", dropna=False).agg(Monto=("GASTOS_CANTIDAD", "sum"), Transacciones=("GASTOS_CANTIDAD", "count")).reset_index().sort_values("Monto", ascending=False)
        _add_chart(story, _chart_group(gastos, "GASTOS_CATEGORIA", "GASTOS_CANTIDAD", "Principales categorías de gasto"), height=8.6 * cm)
        if not cat.empty:
            categoria_top = cat.iloc[0]
            participacion_top = float(categoria_top["Monto"]) / float(cat["Monto"].sum()) * 100 if float(cat["Monto"].sum()) else 0
            concentracion_txt = (
                f"La categoría <b>{_safe_text(categoria_top['GASTOS_CATEGORIA'])}</b> concentra <b>{participacion_top:.1f}%</b> del gasto total. "
                + ("Es una concentración alta: cualquier ajuste en esta categoría tendría un efecto importante en el resultado." if participacion_top >= 40
                   else "El gasto está relativamente distribuido; conviene revisar también las siguientes categorías del ranking.")
            )
            story += [Spacer(1, .12 * cm), _insight_box("Qué explica el gasto", concentracion_txt, styles, "yellow" if participacion_top >= 40 else "blue")]
        fixed_chart = _chart_fixed_variable(gastos)
        if fixed_chart:
            _add_chart(story, fixed_chart, width=15.0 * cm, height=8.0 * cm)
        if "GASTOS_SUBCATEGORIA" in gastos.columns:
            _add_chart(story, _chart_group(
                gastos, "GASTOS_SUBCATEGORIA", "GASTOS_CANTIDAD",
                "Subcategorias con mayor gasto", top=12,
            ), height=8.6 * cm)
        story.append(PageBreak())
        story.append(_df_table(cat, styles, money_cols=["Monto"], max_rows=18))
        top_cols = [c for c in ["GASTOS_FECHA", "GASTOS_DESCRIPCION", "GASTOS_CATEGORIA", "GASTOS_SUBCATEGORIA", "GASTOS_CANTIDAD"] if c in gastos.columns]
        if top_cols:
            story += [Spacer(1, .35 * cm), Paragraph("Movimientos individuales que más explican el gasto", styles["section"])]
            top_mov = gastos[top_cols].sort_values("GASTOS_CANTIDAD", ascending=False).head(15)
            story.append(_df_table(top_mov, styles, money_cols=["GASTOS_CANTIDAD"], max_rows=15))
    else:
        story.append(Paragraph("No hay gastos para el periodo seleccionado.", styles["body"]))
    story.append(PageBreak())

    # 3. Tendencias
    story += [_question_header(2, styles), Spacer(1, .2 * cm)]
    if flujo is not None and len(flujo) >= 2:
        gastos_tend = pd.to_numeric(flujo.get("Gastos", 0), errors="coerce").fillna(0)
        balances_tend = pd.to_numeric(flujo.get("Balance", 0), errors="coerce").fillna(0)
        gasto_anterior, gasto_ultimo = float(gastos_tend.iloc[-2]), float(gastos_tend.iloc[-1])
        cambio_gasto = (gasto_ultimo - gasto_anterior) / gasto_anterior * 100 if gasto_anterior else 0.0
        direccion = "aumentó" if cambio_gasto > 0 else "disminuyó" if cambio_gasto < 0 else "se mantuvo estable"
        balance_ultimo = float(balances_tend.iloc[-1])
        tendencia_texto = (
            f"Frente al mes anterior, el gasto <b>{direccion} {abs(cambio_gasto):.1f}%</b>. "
            f"El último balance mensual fue <b>{_money(balance_ultimo)}</b>. "
            + ("El periodo reciente sigue generando saldo a favor." if balance_ultimo >= 0 else "El último mes cerró en déficit y merece revisar qué categorías explicaron el aumento.")
        )
        story += [_insight_box("Qué cambió recientemente", tendencia_texto, styles, "green" if balance_ultimo >= 0 else "red"), Spacer(1, .08 * cm)]
    _add_chart(story, _chart_flow(flujo, "Evolución mensual del flujo financiero"), height=7.2 * cm)
    cols = [c for c in ["MES", "Ingresos", "Gastos", "Balance", "Balance acumulado", "Capacidad ahorro %"] if flujo is not None and c in flujo.columns]
    story.append(_df_table(flujo[cols] if cols else flujo, styles, money_cols=["Ingresos", "Gastos", "Balance", "Balance acumulado"], max_rows=18))
    story.append(PageBreak())

    # Escenarios de largo plazo incluidos en la pestaña Tendencias.
    projection = _projection_data(gastos, ingresos)
    story += [Paragraph("PROYECCIONES DE LARGO PLAZO", styles["section"]), Spacer(1, .12 * cm)]
    if projection:
        story.append(Paragraph(
            f"Base mensual observada en {projection['observed_months']} meses: salarios laborales promedio de "
            f"<b>{_money(projection['avg_salary'])}</b>, gastos promedio de <b>{_money(projection['avg_expense'])}</b> "
            f"y saldo neto de <b>{_money(projection['monthly_net'])}</b>.", styles["body"],
        ))
        story += [Spacer(1, .25 * cm), Paragraph("Escenario 1 - Continuidad del ritmo actual", styles["question"])]
        story.append(_projection_cards(projection["simple_horizons"], styles))
        _add_chart(story, _chart_projection(projection), height=8.1 * cm)
        story += [Spacer(1, .2 * cm), Paragraph("Escenario 2 - Saldo invertido al 10% efectivo anual", styles["question"])]
        story.append(_projection_cards(projection["compound_horizons"], styles, prefix="10% EA / "))
        _add_chart(story, _chart_projection(projection, compound=True), height=8.1 * cm)
        diferencia_interes = projection["compound_horizons"][30] - projection["simple_horizons"][30]
        story.append(_insight_box(
            "Cómo leer los escenarios",
            f"Sin rendimiento, el resultado depende únicamente del saldo mensual promedio. Al invertir al 10% EA, "
            f"la diferencia estimada al año 30 sería de <b>{_money(diferencia_interes)}</b> por efecto de la capitalización. "
            f"Se usa una tasa mensual equivalente de <b>{projection['monthly_rate'] * 100:.3f}%</b>. No se incluyen inflación, impuestos ni cambios futuros en salarios o gastos.",
            styles, "purple",
        ))
    else:
        story.append(Paragraph("No hay salarios laborales o gastos con fechas validas suficientes para construir la proyeccion.", styles["body"]))
    story.append(PageBreak())

    # 4. Presupuesto
    story += [_question_header(3, styles), Spacer(1, .2 * cm)]
    presupuesto_total_pdf = float(pd.to_numeric(flujo.get("Presupuesto mensual", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if flujo is not None and not flujo.empty else float(presupuesto_mensual or 0)
    gasto_total_pdf = float(pd.to_numeric(flujo.get("Gastos", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if flujo is not None and not flujo.empty else float(total_gastos)
    disponible_pdf = presupuesto_total_pdf - gasto_total_pdf
    ejecucion_pdf = gasto_total_pdf / presupuesto_total_pdf * 100 if presupuesto_total_pdf else 0.0
    story.append(_kpi_table([
        ("Presupuesto", _money(presupuesto_total_pdf)),
        ("Ejecutado", _money(gasto_total_pdf)),
        ("Disponible", _money(disponible_pdf)),
        ("Ejecución", f"{ejecucion_pdf:.1f}%"),
    ], styles))
    if presupuesto_total_pdf > 0:
        if ejecucion_pdf > 100:
            presupuesto_texto = f"Se superó el presupuesto en <b>{_money(abs(disponible_pdf))}</b>. La ejecución llegó a <b>{ejecucion_pdf:.1f}%</b>, por lo que el siguiente paso es identificar las categorías responsables del exceso."
            presupuesto_tono = "red"
        elif ejecucion_pdf >= 90:
            presupuesto_texto = f"El gasto está muy cerca del límite: se ha utilizado <b>{ejecucion_pdf:.1f}%</b> y quedan <b>{_money(disponible_pdf)}</b>. Hay poco margen para movimientos no previstos."
            presupuesto_tono = "yellow"
        else:
            presupuesto_texto = f"La ejecución se mantiene dentro del plan en <b>{ejecucion_pdf:.1f}%</b>, con <b>{_money(disponible_pdf)}</b> todavía disponibles."
            presupuesto_tono = "green"
        story += [Spacer(1, .14 * cm), _insight_box("Estado del presupuesto", presupuesto_texto, styles, presupuesto_tono)]
    _add_chart(story, _chart_budget(flujo), height=6.9 * cm)
    budget_cols = [c for c in ["MES", "Gastos", "Presupuesto mensual", "Diferencia vs presupuesto", "Estado presupuesto"] if flujo is not None and c in flujo.columns]
    story.append(_df_table(flujo[budget_cols] if budget_cols else flujo, styles, money_cols=["Gastos", "Presupuesto mensual", "Diferencia vs presupuesto"], max_rows=10))
    story.append(PageBreak())

    # 5. Ingresos
    story += [_question_header(4, styles), Spacer(1, .2 * cm)]
    if ingresos is None or ingresos.empty or "INGRESOS_CANTIDAD" not in ingresos.columns:
        story.append(Paragraph("No hay ingresos registrados para el periodo seleccionado.", styles["body"]))
    else:
        ing = ingresos.copy()
        ing["INGRESOS_CANTIDAD"] = pd.to_numeric(ing["INGRESOS_CANTIDAD"], errors="coerce").fillna(0)
        if "INGRESOS_FECHA" in ing.columns:
            ing["INGRESOS_FECHA"] = pd.to_datetime(ing["INGRESOS_FECHA"], errors="coerce", dayfirst=True)
            ing["PERIODO"] = ing["INGRESOS_FECHA"].dt.strftime("%Y-%m")
        total_ing_pdf = float(ing["INGRESOS_CANTIDAD"].sum())
        meses_ing_pdf = max(int(ing.get("PERIODO", pd.Series(dtype=str)).dropna().nunique()), 1)
        promedio_ing_pdf = total_ing_pdf / meses_ing_pdf
        fuente_col = next((c for c in ["INGRESOS_FUENTE", "FUENTE"] if c in ing.columns), None)
        tipo_col = next((c for c in ["INGRESOS_CATEGORIA", "CATEGORIA"] if c in ing.columns), None)
        fuente_principal_pdf = "Sin fuente"
        pct_principal_pdf = 0.0
        numero_fuentes_pdf = 0
        resumen_fuentes_pdf = pd.Series(dtype=float)
        if fuente_col:
            resumen_fuentes_pdf = ing.groupby(fuente_col, dropna=False)["INGRESOS_CANTIDAD"].sum().sort_values(ascending=False)
            numero_fuentes_pdf = int(resumen_fuentes_pdf.size)
            if not resumen_fuentes_pdf.empty:
                fuente_principal_pdf = str(resumen_fuentes_pdf.index[0])
                pct_principal_pdf = float(resumen_fuentes_pdf.iloc[0]) / total_ing_pdf * 100 if total_ing_pdf else 0.0
        if tipo_col:
            ing["TIPO_INGRESO"] = ing[tipo_col].map(_income_type)
        else:
            ing["TIPO_INGRESO"] = "Sin clasificar"
        resumen_tipo_pdf = ing.groupby("TIPO_INGRESO")["INGRESOS_CANTIDAD"].sum()
        laboral_pdf = float(resumen_tipo_pdf.get("Laborales", 0))
        no_laboral_pdf = float(resumen_tipo_pdf.get("No laborales", 0))
        sin_clasificar_pdf = float(resumen_tipo_pdf.get("Sin clasificar", 0))
        pct_no_laboral_pdf = no_laboral_pdf / total_ing_pdf * 100 if total_ing_pdf else 0.0
        participaciones_pdf = resumen_fuentes_pdf / total_ing_pdf if total_ing_pdf and not resumen_fuentes_pdf.empty else pd.Series(dtype=float)
        hhi_pdf = float(participaciones_pdf.pow(2).sum() * 10000) if not participaciones_pdf.empty else 10000.0
        mensual_pdf = ing.groupby("PERIODO")["INGRESOS_CANTIDAD"].sum() if "PERIODO" in ing.columns else pd.Series(dtype=float)
        cv_pdf = float(mensual_pdf.std(ddof=0) / mensual_pdf.mean() * 100) if len(mensual_pdf) > 1 and mensual_pdf.mean() else 0.0
        score_pdf = max(0.0, min(100.0,
            30 * (1 - min(hhi_pdf, 10000) / 10000)
            + 30 * (1 - min(cv_pdf, 100) / 100)
            + 20 * min(numero_fuentes_pdf / 5, 1)
            + 15 * (1 - pct_principal_pdf / 100)
            + (5 if sin_clasificar_pdf == 0 else max(0, 5 * (1 - sin_clasificar_pdf / total_ing_pdf)))
        ))
        story.append(_kpi_table([
            ("Ingresos totales", _money(total_ing_pdf)),
            ("Promedio mensual", _money(promedio_ing_pdf)),
            ("Fuentes activas", str(numero_fuentes_pdf)),
            ("Calidad ingresos", f"{score_pdf:.1f}/100"),
        ], styles))
        story += [Spacer(1, .2 * cm), _kpi_table([
            ("Laborales", _money(laboral_pdf)),
            ("No laborales", _money(no_laboral_pdf)),
            ("Sin clasificar", _money(sin_clasificar_pdf)),
            ("No laboral %", f"{pct_no_laboral_pdf:.1f}%"),
        ], styles)]
        dependencia_txt = (
            f"La principal fuente es <b>{_safe_text(fuente_principal_pdf)}</b> y aporta <b>{pct_principal_pdf:.1f}%</b> del ingreso. "
            + ("Existe una dependencia alta: una interrupción de esa fuente afectaría de forma importante el flujo mensual. Conviene fortalecer fuentes complementarias." if pct_principal_pdf > 60
               else "La distribución entre fuentes reduce la dependencia de un solo pagador.")
            + f" Los ingresos no laborales representan <b>{pct_no_laboral_pdf:.1f}%</b> del total."
        )
        story += [Spacer(1, .2 * cm), _insight_box("Estabilidad y dependencia de ingresos", dependencia_txt, styles, "yellow" if pct_principal_pdf > 60 else "green")]
        _add_chart(story, _chart_income_stability(ingresos), height=8.2 * cm)
        if fuente_col:
            _add_chart(story, _chart_group(ing, fuente_col, "INGRESOS_CANTIDAD", "Principales fuentes de ingreso"), height=8.3 * cm)
        story += [Spacer(1, .25 * cm), Paragraph("Composición por tipo de ingreso", styles["section"])]
        tipo_res_pdf = ing.groupby("TIPO_INGRESO", dropna=False)["INGRESOS_CANTIDAD"].sum().reset_index().sort_values("INGRESOS_CANTIDAD", ascending=False)
        story.append(_df_table(tipo_res_pdf, styles, money_cols=["INGRESOS_CANTIDAD"], max_rows=15))
        ing_cols = [c for c in ["INGRESOS_FECHA", "MES", "INGRESOS_FUENTE", "INGRESOS_CATEGORIA", "INGRESOS_CANTIDAD", "INGRESOS_DESCRIPCION"] if c in ing.columns]
        story += [Spacer(1, .3 * cm), Paragraph("Detalle de ingresos", styles["section"])]
        story.append(_df_table(ing[ing_cols] if ing_cols else ing, styles, money_cols=["INGRESOS_CANTIDAD"], max_rows=25))
    story.append(PageBreak())

    # 6. Deudas
    story += [_question_header(5, styles), Spacer(1, .2 * cm)]
    if deudas is not None and not deudas.empty:
        deuda_pdf = deudas.copy()
        for col in ["Deuda inicial", "Interés", "Saldo", "Pagado", "Avance"]:
            if col in deuda_pdf.columns:
                deuda_pdf[col] = pd.to_numeric(deuda_pdf[col], errors="coerce").fillna(0)
        total_inicial_pdf = float(deuda_pdf.get("Deuda inicial", pd.Series(dtype=float)).sum())
        total_saldo_pdf = float(deuda_pdf.get("Saldo", pd.Series(dtype=float)).sum())
        total_pagado_pdf = float(deuda_pdf.get("Pagado", pd.Series(dtype=float)).sum())
        avance_pdf = total_pagado_pdf / total_inicial_pdf * 100 if total_inicial_pdf else 0.0
        interes_pond_pdf = (
            float((deuda_pdf["Interés"] * deuda_pdf["Saldo"]).sum() / total_saldo_pdf * 100)
            if total_saldo_pdf and {"Interés", "Saldo"}.issubset(deuda_pdf.columns) else 0.0
        )
        story.append(_kpi_table([
            ("Deuda inicial", _money(total_inicial_pdf)),
            ("Saldo pendiente", _money(total_saldo_pdf)),
            ("Pagado", _money(total_pagado_pdf)),
            ("Avance global", f"{avance_pdf:.1f}%"),
            ("Interés ponderado", f"{interes_pond_pdf:.2f}%"),
        ], styles))
        if {"Nombre", "Saldo"}.issubset(deuda_pdf.columns):
            _add_chart(story, _chart_group(deuda_pdf, "Nombre", "Saldo", "Saldo pendiente por obligación", top=12), height=8.3 * cm)
        if {"Nombre", "Interés", "Saldo"}.issubset(deuda_pdf.columns):
            deuda_pdf["Interés %"] = deuda_pdf["Interés"] * 100
            deuda_pdf["Costo anual estimado"] = deuda_pdf["Interés"] * deuda_pdf["Saldo"]
            prioridad_pdf = deuda_pdf.sort_values(["Interés", "Saldo"], ascending=[False, False]).copy()
            prioridad_pdf["Prioridad"] = range(1, len(prioridad_pdf) + 1)
            prioridad_pdf["Participación saldo %"] = prioridad_pdf["Saldo"] / total_saldo_pdf * 100 if total_saldo_pdf else 0.0
            cols_deuda_pdf = [c for c in ["Prioridad", "Nombre", "Interés %", "Deuda inicial", "Pagado", "Saldo", "Avance", "Costo anual estimado", "Participación saldo %"] if c in prioridad_pdf.columns]
            story += [Spacer(1, .25 * cm), Paragraph("Prioridad de pago y costo estimado", styles["section"])]
            story.append(_df_table(prioridad_pdf[cols_deuda_pdf], styles, money_cols=["Deuda inicial", "Pagado", "Saldo", "Costo anual estimado"], max_rows=25))
            primera = prioridad_pdf.iloc[0]
            deuda_tono = "red" if interes_pond_pdf >= 20 else "yellow" if total_saldo_pdf > 0 else "green"
            story += [Spacer(1, .2 * cm), _insight_box(
                "Qué deuda conviene atender primero",
                f"Por el método avalancha, la primera obligación es <b>{_safe_text(primera.get('Nombre', 'Sin nombre'))}</b>, "
                f"con tasa de <b>{float(primera.get('Interés %', 0)):.2f}%</b> y saldo de <b>{_money(primera.get('Saldo', 0))}</b>. "
                f"En conjunto ya se ha pagado <b>{avance_pdf:.1f}%</b> de la deuda inicial. El costo anual es una aproximación y no reemplaza el extracto contractual.",
                styles, deuda_tono,
            )]
        else:
            story.append(_df_table(deuda_pdf, styles, money_cols=["Deuda inicial", "Interés", "Saldo", "Pagado"], max_rows=25))
    else:
        story.append(Paragraph("No hay deudas registradas.", styles["body"]))
    story.append(PageBreak())

    # 7. Patrimonio
    story += [_question_header(6, styles), Spacer(1, .2 * cm)]
    if patrimonio is None or patrimonio.empty:
        story.append(Paragraph("No hay registros patrimoniales para el periodo seleccionado.", styles["body"]))
    else:
        pat_pdf = patrimonio.copy()
        for col in ["Valor actual", "Saldo pendiente", "Valor neto", "VALOR", "Valor", "MONTO", "Monto", "SALDO", "Saldo"]:
            if col in pat_pdf.columns:
                pat_pdf[col] = pd.to_numeric(pat_pdf[col], errors="coerce").fillna(0)
        valor_col = next((c for c in ["Valor neto", "VALOR_NETO", "Valor actual", "VALOR", "Valor", "MONTO", "Monto"] if c in pat_pdf.columns), None)
        tipo_col = next((c for c in ["Tipo", "TIPO"] if c in pat_pdf.columns), None)
        nombre_col = next((c for c in ["Descripción", "DESCRIPCION", "Subcategoría", "SUBCATEGORIA", "Categoría", "CATEGORIA", "Entidad", "ENTIDAD"] if c in pat_pdf.columns), None)
        if valor_col:
            if tipo_col:
                tipo_norm_pdf = pat_pdf[tipo_col].astype(str).str.upper().str.strip()
                activos_pdf = float(pat_pdf.loc[tipo_norm_pdf.eq("ACTIVO"), valor_col].abs().sum())
                pasivos_pdf = float(pat_pdf.loc[~tipo_norm_pdf.eq("ACTIVO"), valor_col].abs().sum())
            else:
                activos_pdf = float(pat_pdf.loc[pat_pdf[valor_col] >= 0, valor_col].sum())
                pasivos_pdf = abs(float(pat_pdf.loc[pat_pdf[valor_col] < 0, valor_col].sum()))
            neto_pdf = activos_pdf - pasivos_pdf
            endeuda_pdf = pasivos_pdf / activos_pdf * 100 if activos_pdf else 0
            liquidez_col = next((c for c in ["Liquidez", "LIQUIDEZ"] if c in pat_pdf.columns), None)
            liquidos_pdf = 0.0
            if liquidez_col:
                liq_norm_pdf = pat_pdf[liquidez_col].astype(str).str.upper()
                liquidos_pdf = float(pat_pdf.loc[liq_norm_pdf.str.contains("ALTA|MEDIA|LIQUID", regex=True, na=False), valor_col].abs().sum())
            liquidez_pct_pdf = liquidos_pdf / activos_pdf * 100 if activos_pdf else 0.0
            story.append(_kpi_table([
                ("Activos", _money(activos_pdf)), ("Pasivos", _money(pasivos_pdf)),
                ("Patrimonio neto", _money(neto_pdf)), ("Pasivos / activos", f"{endeuda_pdf:.1f}%"),
                ("Activos líquidos", _money(liquidos_pdf)),
            ], styles))
            if nombre_col:
                # El eje usa nombres o descripciones; nunca fechas.
                chart_pat = _chart_group(pat_pdf.assign(**{nombre_col: pat_pdf[nombre_col].fillna("Sin nombre").astype(str)}), nombre_col, valor_col, "Composición del patrimonio por nombre", top=14)
                _add_chart(story, chart_pat, height=7.6 * cm)
            concentracion_pat_txt = ""
            if nombre_col and not pat_pdf.empty:
                valores_abs = pat_pdf.groupby(nombre_col, dropna=False)[valor_col].sum().abs().sort_values(ascending=False)
                if not valores_abs.empty and valores_abs.sum() > 0:
                    principal_pat_nombre = valores_abs.index[0]
                    principal_pat_pct = float(valores_abs.iloc[0] / valores_abs.sum() * 100)
                    concentracion_pat_txt = (
                        f" El componente de mayor peso es <b>{_safe_text(principal_pat_nombre)}</b>, con <b>{principal_pat_pct:.1f}%</b> del valor patrimonial registrado."
                    )
            nivel_deuda_pat = "bajo" if endeuda_pdf < 30 else "moderado" if endeuda_pdf <= 60 else "alto"
            patrimonio_texto = (
                f"El patrimonio neto es <b>{_money(neto_pdf)}</b>: los activos "
                f"{'superan' if neto_pdf >= 0 else 'no alcanzan a cubrir'} los pasivos por <b>{_money(abs(neto_pdf))}</b>. "
                f"Por cada $100 en activos existen aproximadamente <b>${endeuda_pdf:.0f} en pasivos</b>, un nivel de apalancamiento <b>{nivel_deuda_pat}</b>. "
                f"Los activos líquidos representan <b>{liquidez_pct_pdf:.1f}%</b> de los activos; esta es la parte que puede responder más rápidamente ante una emergencia."
                + concentracion_pat_txt
            )
            patrimonio_tono = "green" if neto_pdf >= 0 and endeuda_pdf < 50 else "yellow" if neto_pdf >= 0 else "red"
            story += [Spacer(1, .2 * cm), _insight_box("Qué está ocurriendo con el patrimonio", patrimonio_texto, styles, patrimonio_tono)]
        money_pat_cols = [c for c in ["Valor actual", "Saldo pendiente", "Valor neto", "VALOR", "Valor", "MONTO", "Monto", "SALDO", "Saldo"] if c in pat_pdf.columns]
        story += [Spacer(1, .3 * cm), Paragraph("Detalle patrimonial", styles["section"])]
        story.append(_df_table(pat_pdf, styles, money_cols=money_pat_cols, max_rows=30))
    story.append(PageBreak())

    # 8. Score
    gasto_ingreso = (total_gastos / total_ingresos * 100) if total_ingresos else 0.0
    deuda_ingreso = (deuda_saldo / total_ingresos * 100) if total_ingresos else 0.0
    ahorro_pct = (balance / total_ingresos * 100) if total_ingresos else 0.0
    score = max(0.0, min(100.0, 65 + min(max(ahorro_pct, -30), 25) - max(gasto_ingreso - 85, 0) - min(deuda_ingreso / 5, 20)))
    story += [_question_header(7, styles), Spacer(1, .25 * cm)]
    story.append(_kpi_table([
        ("Score referencial", f"{score:.1f}/100"), ("Ahorro", f"{ahorro_pct:.1f}%"),
        ("Gasto / ingreso", f"{gasto_ingreso:.1f}%"), ("Deuda / ingreso", f"{deuda_ingreso:.1f}%"),
    ], styles))
    nivel_score = "saludable" if score >= 75 else "intermedio" if score >= 50 else "vulnerable"
    score_texto = (
        f"El resultado de <b>{score:.1f}/100</b> ubica la situación en un nivel <b>{nivel_score}</b>. "
        f"El ahorro aporta positivamente cuando existe, mientras que una relación elevada de gasto o deuda frente al ingreso reduce el resultado. "
        "Es una señal orientativa; la pestaña Score conserva el cálculo detallado de cada componente."
    )
    story += [Spacer(1, .35 * cm), _insight_box("Interpretación del score", score_texto, styles, "green" if score >= 75 else "yellow" if score >= 50 else "red")]
    if isinstance(metas, pd.DataFrame) and not metas.empty:
        story += [Spacer(1, .4 * cm), Paragraph("Metas registradas", styles["question"]), _df_table(metas, styles, max_rows=20)]
    story.append(PageBreak())

    # 9. Felicidad
    story += [_question_header(8, styles), Spacer(1, .2 * cm)]
    if felicidad is None or felicidad.empty:
        story.append(Paragraph(
            "No hay registros de trabajo en las columnas K:Q de la hoja Transaccional para el periodo seleccionado.",
            styles["body"],
        ))
    else:
        fel = felicidad.copy()
        for col in ["VALOR", "HORAS", "VALOR_HORA"]:
            if col in fel.columns:
                fel[col] = pd.to_numeric(fel[col], errors="coerce")
        total_valor_fel = float(fel.get("VALOR", pd.Series(dtype=float)).fillna(0).sum())
        total_horas_fel = float(fel.get("HORAS", pd.Series(dtype=float)).fillna(0).sum())
        valor_hora_fel = total_valor_fel / total_horas_fel if total_horas_fel > 0 else float(fel.get("VALOR_HORA", pd.Series(dtype=float)).mean() or 0)
        meses_fel = max(int(fel.get("MES", pd.Series(dtype=str)).astype(str).nunique()), 1)
        promedio_mensual_fel = total_valor_fel / meses_fel
        try:
            edad_num = float(edad_persona)
        except (TypeError, ValueError):
            edad_num = 0.0
        idr_pdf = promedio_mensual_fel * edad_num * 1.2
        patrimonio_neto_pdf = 0.0
        if patrimonio is not None and not patrimonio.empty:
            for candidate in ["Valor neto", "VALOR_NETO", "Valor", "VALOR"]:
                if candidate in patrimonio.columns:
                    patrimonio_neto_pdf = float(pd.to_numeric(patrimonio[candidate], errors="coerce").fillna(0).sum())
                    break
        ratio_idr_pdf = patrimonio_neto_pdf / idr_pdf if idr_pdf > 0 else 0.0
        estado_idr_pdf = "Generador de riqueza" if ratio_idr_pdf >= 2 else "Escenario típico" if ratio_idr_pdf > .55 else "Destructor de patrimonio"
        story.append(_kpi_table([
            ("Ingresos de trabajos", _money(total_valor_fel)),
            ("Horas registradas", f"{total_horas_fel:,.1f}"),
            ("Valor hora promedio", _money(valor_hora_fel)),
            ("Patrimonio / IDR", f"{ratio_idr_pdf:.2f}x"),
        ], styles))
        felicidad_texto = (
            f"La lectura es <b>{_safe_text(estado_idr_pdf)}</b>. El patrimonio equivale a <b>{ratio_idr_pdf:.2f} veces</b> el IDR estimado de {_money(idr_pdf)}. "
            f"El trabajo produjo en promedio <b>{_money(valor_hora_fel)} por hora</b>; este indicador permite comparar si el tiempo invertido está generando una remuneración coherente con la acumulación patrimonial. "
            "No es una medición clínica de felicidad."
        )
        story += [Spacer(1, .22 * cm), _insight_box("Trabajo, tiempo y patrimonio", felicidad_texto, styles, "purple")]
        _add_chart(story, _chart_happiness_company(fel), height=8.2 * cm)
        _add_chart(story, _chart_happiness_income_mix(fel), width=14.5 * cm, height=8.0 * cm)
        fel_cols = [c for c in ["FECHA", "EMPRESA", "CATEGORIA", "HORAS", "VALOR", "VALOR_HORA"] if c in fel.columns]
        story.append(_df_table(fel[fel_cols] if fel_cols else fel, styles, money_cols=["VALOR", "VALOR_HORA"], max_rows=24))

    doc.build(story)
    output.seek(0)
    return output.getvalue()
