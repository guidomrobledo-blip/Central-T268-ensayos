import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logic_clientes, logic_faltantes, logic_domicilios, logic_informe, logic_seguridad
import os
import json
import hashlib

# 🎨 ESTILOS PERSONALIZADOS
st.markdown("""
<style>

/* Nombre archivo */
[data-testid="stFileUploader"] span {
    color: #374151 !important;
    font-weight: 500;
}

/* Tamaño archivo */
[data-testid="stFileUploader"] small {
    color: #6B7280 !important;
}

</style>
""", unsafe_allow_html=True)

# --- CONFIGURACION ---
st.set_page_config(
    page_title="Panel Operaciones Online Carrefour",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- FECHA ARGENTINA (UTC-3) ---
fecha_ar_ahora = datetime.utcnow() - timedelta(hours=3)
hoy_ar = fecha_ar_ahora.date()
manana_ar_obj = hoy_ar + timedelta(days=1)
manana_txt = manana_ar_obj.strftime("%d/%m/%Y")

# --- ARCHIVO DE PERSISTENCIA PARA DATOS MENSUALES ---
DATA_FILE = "pedidos_mensuales.json"

# Diccionario para traducir dias de la semana
DIAS_SEMANA_ES = {
    0: "Lun", 1: "Mar", 2: "Mie", 3: "Jue", 4: "Vie", 5: "Sab", 6: "Dom"
}

def cargar_datos_mensuales():
    """Carga los datos del mes desde el archivo JSON. Reinicia si cambia de mes."""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                datos = json.load(f)
            # Verificar si es el mismo mes
            mes_guardado = datos.get("mes", "")
            mes_actual = hoy_ar.strftime("%Y-%m")
            if mes_guardado != mes_actual:
                # Nuevo mes, reiniciar datos
                return {"mes": mes_actual, "pedidos_por_dia": {}, "archivos_procesados": [], "modalidades": {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}}
            return datos
        else:
            return {"mes": hoy_ar.strftime("%Y-%m"), "pedidos_por_dia": {}, "archivos_procesados": [], "modalidades": {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}}
    except Exception:
        return {"mes": hoy_ar.strftime("%Y-%m"), "pedidos_por_dia": {}, "archivos_procesados": [], "modalidades": {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}}

def guardar_datos_mensuales(datos):
    """Guarda los datos del mes en el archivo JSON."""
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(datos, f)
    except Exception:
        pass

def reiniciar_contador_mensual():
    """Reinicia el contador mensual."""
    datos = {"mes": hoy_ar.strftime("%Y-%m"), "pedidos_por_dia": {}, "archivos_procesados": [], "modalidades": {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}}
    guardar_datos_mensuales(datos)
    return datos

def obtener_hash_archivo(archivo_bytes):
    """Genera un hash unico para identificar archivos duplicados."""
    return hashlib.md5(archivo_bytes).hexdigest()

def extraer_fecha_entrega(df):
    """Extrae la fecha de la columna FECHA ENTREGA del DataFrame."""
    col_fecha = None
    for col in df.columns:
        if "FECHA" in str(col).upper() and "ENTREGA" in str(col).upper():
            col_fecha = col
            break
    
    if col_fecha is None:
        return None
    
    try:
        # Obtener el primer valor no nulo de la columna
        fecha_val = df[col_fecha].dropna().iloc[0]
        
        # Si ya es datetime
        if isinstance(fecha_val, (pd.Timestamp, datetime)):
            return fecha_val.date() if hasattr(fecha_val, 'date') else fecha_val
        
        # Si es string, intentar parsear con multiples formatos
        fecha_str = str(fecha_val)
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d-%b-%y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(fecha_str, fmt).date()
            except ValueError:
                continue
        return None
    except Exception:
        return None

def contar_modalidades(df):
    """Cuenta las modalidades de entrega del DataFrame."""
    modalidades_conteo = {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}
    
    # Buscar la columna de modalidad de entrega (priorizar "MODALIDAD DE ENTREGA")
    col_modalidad = None
    
    # Primera busqueda: columna exacta o similar a "MODALIDAD DE ENTREGA"
    for col in df.columns:
        col_upper = str(col).upper().strip()
        if "MODALIDAD" in col_upper and "ENTREGA" in col_upper:
            col_modalidad = col
            break
    
    # Segunda busqueda: solo "MODALIDAD"
    if col_modalidad is None:
        for col in df.columns:
            col_upper = str(col).upper().strip()
            if "MODALIDAD" in col_upper and "FECHA" not in col_upper:
                col_modalidad = col
                break
    
    # Tercera busqueda: "TIPO ENTREGA" o "CANAL"
    if col_modalidad is None:
        for col in df.columns:
            col_upper = str(col).upper().strip()
            if ("TIPO" in col_upper and "ENTREGA" in col_upper) or "CANAL" in col_upper:
                col_modalidad = col
                break
    
    if col_modalidad is not None:
        for valor in df[col_modalidad].dropna():
            valor_upper = str(valor).upper().strip()
            # Detectar DOMICILIO/DOMICILIOS
            if "DOMICILIO" in valor_upper or "A DOMICILIO" in valor_upper:
                modalidades_conteo["DOMICILIOS"] += 1
            # Detectar DRIVE
            elif "DRIVE" in valor_upper:
                modalidades_conteo["DRIVE"] += 1
            # Detectar SUCURSAL (retiro en tienda, pick up, etc.)
            elif "SUCURSAL" in valor_upper or "RETIRO" in valor_upper or "PICK" in valor_upper or "TIENDA" in valor_upper:
                modalidades_conteo["SUCURSAL"] += 1
    
    return modalidades_conteo


def registrar_pedidos_cdp(archivo_bytes, df):
    """Registra los pedidos del archivo CDP si no fue procesado antes."""
    datos = cargar_datos_mensuales()
    
    # Verificar si el archivo ya fue procesado
    archivo_hash = obtener_hash_archivo(archivo_bytes)
    if archivo_hash in datos["archivos_procesados"]:
        return datos, False  # Ya fue procesado, no registrar de nuevo
    
    # Extraer la fecha de entrega del Excel
    fecha_entrega = extraer_fecha_entrega(df)
    if fecha_entrega is None:
        return datos, False
    
    # Solo registrar si la fecha es del mes actual
    if fecha_entrega.strftime("%Y-%m") != datos["mes"]:
        return datos, False
    
    # Registrar los pedidos para esa fecha
    fecha_str = fecha_entrega.strftime("%Y-%m-%d")
    cantidad_pedidos = len(df)

    # Guardar la cantidad de pedidos para esa fecha
    datos["pedidos_por_dia"][fecha_str] = cantidad_pedidos
    datos["archivos_procesados"].append(archivo_hash)
    
    # Contar modalidades y acumular al total mensual
    modalidades_archivo = contar_modalidades(df)
    if "modalidades" not in datos:
        datos["modalidades"] = {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}
    
    datos["modalidades"]["DOMICILIOS"] += modalidades_archivo["DOMICILIOS"]
    datos["modalidades"]["DRIVE"] += modalidades_archivo["DRIVE"]
    datos["modalidades"]["SUCURSAL"] += modalidades_archivo["SUCURSAL"]
    
    guardar_datos_mensuales(datos)
    return datos, True

def obtener_datos_semana(datos_mensuales, inicio_semana):
    """Obtiene los datos de pedidos para la semana especificada."""
    pedidos_semana = []
    dias_labels = []
    
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        fecha_str = dia.strftime("%Y-%m-%d")
        dia_semana = DIAS_SEMANA_ES[dia.weekday()]
        dia_num = dia.day
        
        # Formato: "Lun-9", "Mar-10", etc.
        label = f"{dia_semana}-{dia_num}"
        dias_labels.append(label)
        
        # Obtener pedidos de ese dia (0 si no hay datos)
        pedidos = datos_mensuales.get("pedidos_por_dia", {}).get(fecha_str, 0)
        pedidos_semana.append(pedidos)
    
    return dias_labels, pedidos_semana

def obtener_datos_mes(datos_mensuales):
    """Obtiene los datos de pedidos para todo el mes."""
    pedidos_mes = []
    dias_labels = []
    
    # Obtener el primer dia del mes actual
    primer_dia_mes = hoy_ar.replace(day=1)
    
    # Calcular el ultimo dia del mes
    if hoy_ar.month == 12:
        ultimo_dia_mes = hoy_ar.replace(day=31)
    else:
        ultimo_dia_mes = (hoy_ar.replace(month=hoy_ar.month + 1, day=1) - timedelta(days=1))
    
    dia_actual = primer_dia_mes
    while dia_actual <= ultimo_dia_mes:
        fecha_str = dia_actual.strftime("%Y-%m-%d")
        dias_labels.append(dia_actual.day)
        pedidos = datos_mensuales.get("pedidos_por_dia", {}).get(fecha_str, 0)
        pedidos_mes.append(pedidos)
        dia_actual += timedelta(days=1)
    
    return dias_labels, pedidos_mes

def calcular_total_mes(datos_mensuales):
    """Calcula el total de pedidos del mes (solo dias con datos)."""
    pedidos_por_dia = datos_mensuales.get("pedidos_por_dia", {})
    return sum(pedidos_por_dia.values())

# --- CSS LIGHT CORPORATE DASHBOARD ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ===== MAIN BACKGROUND ===== */
    .stApp {
        background: #F5F6F8 !important;
        font-family: 'Inter', sans-serif !important;
    }

    /* Remove default Streamlit styling */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* ===== FULL WIDTH LAYOUT ===== */
    .block-container {
        padding: 1.5rem 2rem !important;
        max-width: 100% !important;
    }

    @media (min-width: 1400px) {
        .block-container {
            padding: 1.5rem 4rem !important;
        }
    }

    /* ===== LOADING SCREEN ===== */
    .loading-screen {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: #F5F6F8;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        animation: fadeOut 0.5s ease-out 1.5s forwards;
    }

    .loading-logo {
        animation: microZoom 2s ease-in-out infinite;
    }

    @keyframes microZoom {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }

    @keyframes fadeOut {
        to { opacity: 0; visibility: hidden; }
    }

    /* ===== HEADER ===== */
    .header-container {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        border: 1px solid #E5E7EB;
        border-bottom: 3px solid #3B82F6;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 16px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }

    .header-left {
        display: flex;
        align-items: center;
        gap: 20px;
    }

    .header-logo {
        height: 50px;
        width: auto;
    }

    .header-text {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .title-main {
        color: #111827;
        font-weight: 700;
        font-size: 1.5em;
        margin: 0;
        letter-spacing: 0.3px;
    }

    .title-main::after {
        content: "";
        display: block;
        width: 350px;
        height: 2px;
        margin: 8px auto 0 auto;
        background: linear-gradient(90deg, transparent, #3B82F6, transparent);
        opacity: 0.7;
    }

    .title-main,
    .title-main span {
        color: #111827 !important;
    }

    .subtitle-main {
        color: #6B7280;
        font-size: 0.9em;
        margin: 0;
        font-weight: 400;
    }

    .header-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, #3B82F6, transparent);
        margin-top: 16px;
        opacity: 0.3;
    }

    /* ===== CARDS ===== */
    .glass-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        border: 1px solid #E5E7EB;
    }

    .card-title {
        color: #374151;
        font-weight: 600;
        font-size: 0.95em;
        text-transform: uppercase;
        letter-spacing: 1px;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #F3F4F6;
    }

    .card-icon {
        font-size: 1.1em;
    }

    /* ===== BUTTONS — BASE ===== */
    div.stButton > button {
        border-radius: 999px !important;
        height: 48px !important;
        font-weight: 600 !important;
        font-size: 0.85em !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12) !important;
        transition: all 0.2s ease !important;
        background: #6B7280 !important;
    }

    div.stButton > button:hover {
        filter: brightness(0.92) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
    }

    div.stButton > button:active {
        transform: translateY(0) !important;
        filter: brightness(0.88) !important;
    }

    /* CLIENTES — col 1 */
    [data-testid="column"]:nth-child(1) div.stButton > button {
        background: #4CAF50 !important;
    }

    /* PERSONAL SEGURIDAD — col 2 */
    [data-testid="column"]:nth-child(2) div.stButton > button {
        background: #6366F1 !important;
    }

    /* FALTANTES — col 3 */
    [data-testid="column"]:nth-child(3) div.stButton > button {
        background: #3B82F6 !important;
    }

    /* DOMICILIOS — col 4 */
    [data-testid="column"]:nth-child(4) div.stButton > button {
        background: #F59E0B !important;
    }

    /* INFORME — col 5 */
    [data-testid="column"]:nth-child(5) div.stButton > button {
        background: #F97316 !important;
    }

    /* Link Button (Planilla MEC) — col 6 */
    [data-testid="column"]:nth-child(6) .stLinkButton > a {
        background: #F3F4F6 !important;
        border-radius: 999px !important;
        height: 48px !important;
        font-weight: 600 !important;
        font-size: 0.85em !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        color: #374151 !important;
        border: 1px solid #D1D5DB !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06) !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-decoration: none !important;
    }

    [data-testid="column"]:nth-child(6) .stLinkButton > a:hover {
        filter: brightness(0.96) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.10) !important;
        text-decoration: none !important;
    }

    /* ===== FILE UPLOADER ===== */
    [data-testid="stFileUploader"] {
        background: #FFFFFF;
        border-radius: 10px;
        padding: 16px;
        border: 1.5px dashed #D1D5DB;
        transition: all 0.2s ease;
    }

    [data-testid="stFileUploader"]:hover {
        border-color: #3B82F6;
        background: #EFF6FF;
    }

    [data-testid="stFileUploader"] label {
        color: #6B7280 !important;
        font-size: 0.85em !important;
    }

    [data-testid="stFileUploader"] p {
        color: #6B7280 !important;
    }

    [data-testid="stFileUploader"] span {
        color: #374151 !important;
    }

    [data-testid="stFileUploaderDropzone"] {
        background: #FFFFFF !important;
        border: none !important;
    }

    [data-testid="stFileUploaderDropzone"] svg {
        color: #3B82F6 !important;
        opacity: 0.7;
    }

    [data-testid="stFileUploaderDropzone"] > div {
        color: #6B7280 !important;
    }

    [data-testid="stFileUploaderDropzone"] small {
        color: #9CA3AF !important;
    }

    [data-testid="stFileUploader"] button {
        background: #EFF6FF !important;
        color: #1D4ED8 !important;
        border: 1px solid #BFDBFE !important;
        border-radius: 6px !important;
    }

    [data-testid="stFileUploader"] button:hover {
        background: #DBEAFE !important;
        border-color: #3B82F6 !important;
    }

    /* ===== TEXT AREA ===== */
    .stTextArea textarea {
        background: #FFFFFF !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 8px !important;
        color: #111827 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9em !important;
        padding: 12px !important;
    }

    .stTextArea textarea:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15) !important;
    }

    .stTextArea textarea::placeholder {
        color: #9CA3AF !important;
    }

    .stTextArea label {
        color: #374151 !important;
        font-weight: 500 !important;
        font-size: 0.95em !important;
    }

    /* ===== METRICS / COUNTERS ===== */
    .metric-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #E5E7EB;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
    }

    .metric-value {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 2.5em;
        color: #111827;
        margin: 0;
    }

    .metric-value-gold {
        color: #1D4ED8;
    }

    .metric-label {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        font-size: 0.8em;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 8px;
    }

    .reset-btn {
        background: transparent;
        border: 1px solid #E5E7EB;
        border-radius: 6px;
        color: #9CA3AF;
        padding: 4px 8px;
        font-size: 0.8em;
        cursor: pointer;
        transition: all 0.2s ease;
        margin-left: 8px;
    }

    .reset-btn:hover {
        border-color: #3B82F6;
        color: #3B82F6;
    }

    /* ===== CHARTS ===== */
    [data-testid="stVegaLiteChart"] {
        background: transparent;
        border-radius: 8px;
    }

    /* ===== ALERTS ===== */
    .stSuccess {
        background: rgba(34, 197, 94, 0.08) !important;
        border: 1px solid rgba(34, 197, 94, 0.3) !important;
        border-radius: 8px !important;
        color: #15803D !important;
    }

    .stInfo {
        background: rgba(59, 130, 246, 0.08) !important;
        border: 1px solid rgba(59, 130, 246, 0.3) !important;
        border-radius: 8px !important;
        color: #1D4ED8 !important;
    }

    .stWarning {
        background: rgba(234, 179, 8, 0.08) !important;
        border: 1px solid rgba(234, 179, 8, 0.3) !important;
        border-radius: 8px !important;
        color: #B45309 !important;
    }

    .stError {
        background: rgba(239, 68, 68, 0.08) !important;
        border: 1px solid rgba(239, 68, 68, 0.3) !important;
        border-radius: 8px !important;
        color: #DC2626 !important;
    }

    /* ===== DOWNLOAD BUTTON ===== */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #3B82F6, #1D4ED8) !important;
        border: none !important;
        border-radius: 999px !important;
        color: white !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        box-shadow: 0 2px 10px rgba(59, 130, 246, 0.35) !important;
        transition: all 0.2s ease !important;
    }

    .stDownloadButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 16px rgba(59, 130, 246, 0.45) !important;
        filter: brightness(1.05) !important;
    }

    /* ===== SPINNER ===== */
    .stSpinner > div {
        border-color: #3B82F6 transparent transparent transparent !important;
    }

    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: #F3F4F6;
    }

    ::-webkit-scrollbar-thumb {
        background: #D1D5DB;
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #9CA3AF;
    }

    /* ===== DONUT CHART LEGEND ===== */
    .donut-legend {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 10px;
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.85em;
        color: #374151;
    }

    .legend-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    /* ===== FOOTER ===== */
    .footer {
        text-align: center;
        padding: 20px;
        color: #9CA3AF;
        font-size: 0.75em;
        letter-spacing: 1px;
        border-top: 1px solid #E5E7EB;
        margin-top: 24px;
    }

    </style>
""", unsafe_allow_html=True)

# --- LOADING SCREEN ---
import base64

def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return None

# Show loading screen briefly
loading_logo_base64 = get_image_base64("logo.png.webp")
if loading_logo_base64:
    st.markdown(f"""
        <div class="loading-screen" id="loadingScreen">
            <img src="data:image/webp;base64,{loading_logo_base64}" class="loading-logo" style="max-width: 200px; height: auto;" alt="Carrefour">
        </div>
    """, unsafe_allow_html=True)

# --- HEADER ---
logo_base64 = get_image_base64("carrefour+logo.png")
logo_html = ""
if logo_base64:
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="header-logo" alt="Carrefour">'
else:
    logo_html = '<span style="color: #6B7280;">Carrefour</span>'

st.markdown(f"""
    <div class="header-container">
        <div class="header-left">
            {logo_html}
            <div class="header-text">
                <h1 class="title-main">Panel Operaciones Online Carrefour</h1>
                <p class="subtitle-main">Tienda 268 - Rosario | {hoy_ar.strftime("%d/%m/%Y")}</p>
            </div>
        </div>
    </div>
    <div class="header-divider"></div>
""", unsafe_allow_html=True)

# --- BUTTON ROW ---
st.write("")
b1, b2, b3, b4, b5, b6 = st.columns(6)
with b1: 
    btn_1 = st.button("CLIENTES", key="top_1", use_container_width=True)
with b2:  
    btn_seguridad = st.button("PERSONAL SEGURIDAD", key="top_seguridad", use_container_width=True)
with b3:  
    btn_2 = st.button("FALTANTES", key="top_2", use_container_width=True)
with b4:  
    btn_3 = st.button("DOMICILIOS", key="top_3", use_container_width=True)
with b5:  
    btn_4 = st.button("INFORME", key="top_4", use_container_width=True)
with b6:  
    st.link_button("PLANILLA MEC", "https://docs.google.com/spreadsheets/d/1v0Rls8fg_uIGfhA1t3CzINq3VfAUvPY3DY8_m_ZSmM8/edit#gid=0", use_container_width=True)
   
# --- MAIN BODY ---
st.write("")
col_izq, col_der = st.columns([1, 1], gap="large")

with col_izq:
    # --- CARD 1: CDP UPLOAD ---
    st.markdown('''
        <div class="glass-card">
            <div class="card-title"><span class="card-icon">📂</span> CARGAR EXCEL DE CDP</div>
    ''', unsafe_allow_html=True)
    archivo_cdp = st.file_uploader("Subir CDP", type=["xlsx"], label_visibility="collapsed", key="cdp_upload")
    
    # Variables para almacenar datos del CDP
    df_clean = None
    fecha_tit = None
    archivo_cdp_bytes = None
    
    if archivo_cdp:
        # Leer el archivo como bytes para hashear
        archivo_cdp_bytes = archivo_cdp.read()
        archivo_cdp.seek(0)  # Resetear el puntero para pd.read_excel
        
        with st.spinner("Procesando archivo..."):
            df_raw = pd.read_excel(archivo_cdp)
            df_clean, fecha_tit = logic_clientes.motor_limpieza(df_raw)
            
            # Registrar pedidos para el grafico (evita duplicados)
            datos_actualizados, fue_registrado = registrar_pedidos_cdp(archivo_cdp_bytes, df_clean)
            
            # Si se registro un nuevo archivo, recargar para actualizar graficos
            if fue_registrado:
                st.rerun()
        
        st.success(f"CDP CARGADO: {fecha_tit}")
        
        # PROCESAMIENTO DE BOTONES
        if btn_1:
            with st.spinner("Procesando archivo..."):
                pdf = logic_clientes.generar_pdf_clientes(df_clean, fecha_tit)
            st.download_button("DESCARGAR PDF CLIENTES", bytes(pdf), f"Clientes_{fecha_tit}.pdf", use_container_width=True)
        if btn_seguridad:
            with st.spinner("Procesando archivo..."):
                pdf = logic_seguridad.generar_pdf_seguridad(df_clean, fecha_tit)
            st.download_button(
                "DESCARGAR PDF SEGURIDAD",
                bytes(pdf),
                f"Seguridad_{fecha_tit}.pdf",
                use_container_width=True
            )    
        if btn_2:
            with st.spinner("Procesando archivo..."):
                pdf = logic_faltantes.generar_pdf_faltantes(df_clean, fecha_tit)
            st.download_button("DESCARGAR PDF FALTANTES", bytes(pdf), f"Faltantes_{fecha_tit}.pdf", use_container_width=True)
        if btn_3:
            with st.spinner("Procesando archivo..."):
                pdf = logic_domicilios.generar_pdf_domicilios(df_clean, fecha_tit)
            st.download_button("DESCARGAR PDF DOMICILIOS", bytes(pdf), f"Domicilios_{fecha_tit}.pdf", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)
    
    st.write("")

    # --- CARD 2: INFORME ---
    st.markdown(f'''
        <div class="glass-card">
            <div class="card-title"><span class="card-icon">📝</span> PROCESADOR DE INFORME (MAÑANA {manana_txt})</div>
    ''', unsafe_allow_html=True)
    archivo_inf = st.file_uploader("Subir CDP Manana", type=["xlsx"], key="inf_upload", label_visibility="collapsed")
    
    st.markdown('<label style="color: #374151; font-weight: 500; font-size: 0.95em; display: block; margin-bottom: 8px;">Observaciones</label>', unsafe_allow_html=True)
    obs = st.text_area("Observaciones:", height=100, placeholder="Ingresa las novedades del turno aqui...", key="obs_area", label_visibility="collapsed")
    
    if btn_4:
        if archivo_inf:
            with st.spinner("Procesando archivo..."):
                df_inf_raw = pd.read_excel(archivo_inf)
                df_inf_clean, fecha_inf_tit = logic_clientes.motor_limpieza(df_inf_raw)
                pdf_bytes = logic_informe.generar_pdf_informe(df_inf_clean, obs)
            st.download_button("DESCARGAR REPORTE FINAL", pdf_bytes, f"Informe_{fecha_inf_tit}.pdf", use_container_width=True)
        else:
            st.warning("Informe solo procesa archivos con fecha de mañana")
    
    st.markdown('</div>', unsafe_allow_html=True)

with col_der:
    # --- VISUALIZATION PANEL ---
    st.markdown('''
        <div class="glass-card">
            <div class="card-title"><span class="card-icon">📈</span> PANEL DE VISUALIZACION</div>
    ''', unsafe_allow_html=True)
    
    # Calcular fechas de la semana actual
    inicio_semana = hoy_ar - timedelta(days=hoy_ar.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    # Meses en español para el rango
    MESES_ES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
                7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
    rango_semana = f"Semana {inicio_semana.day}-{MESES_ES[inicio_semana.month]} al {fin_semana.day}-{MESES_ES[fin_semana.month]}"
    
    # Cargar datos mensuales guardados (recargar para obtener datos actualizados)
    datos_mensuales = cargar_datos_mensuales()
    
    # Obtener datos de la semana actual
    dias_labels, pedidos_semana = obtener_datos_semana(datos_mensuales, inicio_semana)
    
    # Calcular total del mes (solo dias con datos reales)
    total_pedidos_mes = calcular_total_mes(datos_mensuales)
    
    # Obtener pedidos del dia actual desde los datos guardados
    fecha_hoy_str = hoy_ar.strftime("%Y-%m-%d")
    pedidos_dia_actual = datos_mensuales.get("pedidos_por_dia", {}).get(fecha_hoy_str, 0)
    
    # Si se acaba de cargar un archivo CDP, usar esos datos
    if archivo_cdp and df_clean is not None:
        # Extraer fecha del archivo para mostrar
        fecha_archivo = extraer_fecha_entrega(df_raw)
        if fecha_archivo:
            fecha_archivo_str = fecha_archivo.strftime("%Y-%m-%d")
            pedidos_dia_actual = datos_mensuales.get("pedidos_por_dia", {}).get(fecha_archivo_str, len(df_clean))
    
    # --- COUNTERS ROW ---
    col_n1, col_n2, col_n3 = st.columns([1, 1, 0.3])
    
    with col_n1:
        valor_dia = pedidos_dia_actual if pedidos_dia_actual > 0 else "--"
        st.markdown(f'''
            <div class="metric-card">
                <p class="metric-value">{valor_dia}</p>
                <p class="metric-label">Pedidos del Dia</p>
            </div>
        ''', unsafe_allow_html=True)
    
    with col_n2:
        valor_mes = total_pedidos_mes if total_pedidos_mes > 0 else "--"
        st.markdown(f'''
            <div class="metric-card">
                <p class="metric-value metric-value-gold">{valor_mes}</p>
                <p class="metric-label">Total Mes</p>
            </div>
        ''', unsafe_allow_html=True)
    
    with col_n3:
        # Reset button
        if st.button("⟳", key="reset_counter", help="Reiniciar contador mensual"):
            st.session_state.show_reset_confirm = True
    
    # Reset confirmation dialog
    if st.session_state.get('show_reset_confirm', False):
        st.warning("¿Estás seguro de reiniciar el contador mensual? Esta acción no es reversible.")
        col_conf1, col_conf2 = st.columns(2)
        with col_conf1:
            if st.button("Confirmar", key="confirm_reset"):
                reiniciar_contador_mensual()
                st.session_state.show_reset_confirm = False
                st.rerun()
        with col_conf2:
            if st.button("Cancelar", key="cancel_reset"):
                st.session_state.show_reset_confirm = False
                st.rerun()
    
    st.write("")
    
    # --- WEEKLY CHART ---
    st.markdown(f'''
        <p style="color: #6B7280; font-size: 0.8em; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px;">
            {rango_semana}
        </p>
    ''', unsafe_allow_html=True)
    
    # Crear DataFrame para el grafico con datos reales
    chart_data = pd.DataFrame({
        'Dia': dias_labels,
        'Pedidos': pedidos_semana
    })
    
    # Grafico con Altair
    import altair as alt
    
    tiene_datos = any(p > 0 for p in pedidos_semana)
    opacidad_barras = 1.0 if tiene_datos else 0.3
    
    chart = alt.Chart(chart_data).mark_bar(
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
        color='#3B82F6',
        opacity=opacidad_barras,
        width=20
    ).encode(
        x=alt.X('Dia:N', sort=None, axis=alt.Axis(
            labelColor='#9CA3AF',
            labelAngle=0,
            labelFontSize=11,
            title=None,
            tickColor='#E5E7EB',
            domainColor='#E5E7EB'
        )),
        y=alt.Y('Pedidos:Q', axis=alt.Axis(
            labelColor='#9CA3AF',
            gridColor='#E5E7EB',
            title=None,
            tickColor='#E5E7EB',
            domainColor='#E5E7EB'
        )),
        tooltip=['Dia', 'Pedidos']
    ).properties(
        height=150
    ).configure(
        background='transparent'
    ).configure_view(
        strokeWidth=0
    )
    
    st.altair_chart(chart, use_container_width=True)
    
    st.write("")
    
    # --- MONTHLY EVOLUTION CHART ---
    st.markdown('''
        <p style="color: #6B7280; font-size: 0.8em; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px;">
            Evolucion Mensual
        </p>
    ''', unsafe_allow_html=True)
    
    dias_mes_labels, pedidos_mes = obtener_datos_mes(datos_mensuales)
    
    chart_mes_data = pd.DataFrame({
        'Dia': dias_mes_labels,
        'Pedidos': pedidos_mes
    })
    
    tiene_datos_mes = any(p > 0 for p in pedidos_mes)
    
    line_chart = alt.Chart(chart_mes_data).mark_line(
        color='#1D4ED8',
        strokeWidth=2,
        opacity=1.0 if tiene_datos_mes else 0.3
    ).encode(
        x=alt.X('Dia:O', axis=alt.Axis(
            labelColor='#9CA3AF',
            labelAngle=0,
            labelFontSize=9,
            title=None,
            tickColor='#E5E7EB',
            domainColor='#E5E7EB',
            values=list(range(1, len(dias_mes_labels)+1, 5))
        )),
        y=alt.Y('Pedidos:Q', axis=alt.Axis(
            labelColor='#9CA3AF',
            gridColor='#E5E7EB',
            title=None,
            tickColor='#E5E7EB',
            domainColor='#E5E7EB'
        ))
    )
    
    points = alt.Chart(chart_mes_data[chart_mes_data['Pedidos'] > 0] if tiene_datos_mes else chart_mes_data).mark_circle(
        color='#1D4ED8',
        size=40
    ).encode(
        x=alt.X('Dia:O'),
        y=alt.Y('Pedidos:Q'),
        tooltip=['Dia', 'Pedidos']
    )
    
    combined_chart = (line_chart + points).properties(
        height=120
    ).configure(
        background='transparent'
    ).configure_view(
        strokeWidth=0
    )
    
    st.altair_chart(combined_chart, use_container_width=True)
    
    # --- DONUT CHART (Modalidades) ---
    st.write("")
    st.markdown('''
        <p style="color: #6B7280; font-size: 0.8em; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px;">
            Modalidades de Entrega (Acumulado Mensual)
        </p>
    ''', unsafe_allow_html=True)
    
    modalidades = datos_mensuales.get("modalidades", {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0})
    total_modalidades = sum(modalidades.values())
    
    if total_modalidades > 0:
        col_donut, col_legend = st.columns([1, 1])
        
        with col_donut:
            donut_data = pd.DataFrame({
                'Modalidad': list(modalidades.keys()),
                'Cantidad': list(modalidades.values())
            })
            
            donut_chart = alt.Chart(donut_data).mark_arc(innerRadius=40, outerRadius=60).encode(
                theta=alt.Theta(field="Cantidad", type="quantitative"),
                color=alt.Color(field="Modalidad", type="nominal",
                    scale=alt.Scale(
                        domain=["DOMICILIOS", "DRIVE", "SUCURSAL"],
                        range=["#3B82F6", "#6B7280", "#D1D5DB"]
                    ),
                    legend=None
                ),
                tooltip=['Modalidad', 'Cantidad']
            ).properties(
                height=140,
                width=140
            ).configure(
                background='transparent'
            )
            
            st.altair_chart(donut_chart, use_container_width=True)
        
        with col_legend:
            st.markdown(f'''
                <div class="donut-legend">
                    <div class="legend-item">
                        <span class="legend-dot" style="background: #3B82F6;"></span>
                        <span>DOMICILIOS ({modalidades.get("DOMICILIOS", 0)})</span>
                    </div>
                    <div class="legend-item">
                        <span class="legend-dot" style="background: #6B7280;"></span>
                        <span>DRIVE ({modalidades.get("DRIVE", 0)})</span>
                    </div>
                    <div class="legend-item">
                        <span class="legend-dot" style="background: #D1D5DB;"></span>
                        <span>SUCURSAL ({modalidades.get("SUCURSAL", 0)})</span>
                    </div>
                </div>
            ''', unsafe_allow_html=True)
    else:
        # Mostrar leyenda con valores en cero cuando no hay datos
        st.markdown(f'''
            <div class="donut-legend" style="opacity: 0.5;">
                <div class="legend-item">
                    <span class="legend-dot" style="background: #3B82F6;"></span>
                    <span>DOMICILIOS (0)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background: #6B7280;"></span>
                    <span>DRIVE (0)</span>
                </div>
                <div class="legend-item">
                    <span class="legend-dot" style="background: #D1D5DB;"></span>
                    <span>SUCURSAL (0)</span>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    # Mensaje informativo si no hay archivo cargado
    if not archivo_cdp:
        st.info("Suba un archivo de CDP para visualizar las metricas del dia")
    
    st.markdown('</div>', unsafe_allow_html=True)

# --- FOOTER ---
st.markdown('''
    <div class="footer">
        CENTRAL DE ARMADO T268 | CARREFOUR ONLINE | ROSARIO
    </div>
''', unsafe_allow_html=True)
