import streamlit as st
import pandas as pd
from datetime import datetime
import logic_clientes, logic_faltantes, logic_domicilios, logic_informe

# --- CONFIG ---
st.set_page_config(
    page_title="Panel Operaciones Carrefour",
    layout="wide"
)

# --- CSS AVANZADO ---
st.markdown("""
<style>

/* GENERAL */
html, body, .stApp {
    margin: 0;
    padding: 0;
    font-family: 'Segoe UI', sans-serif;
}

/* HERO */
.hero {
    background: #0d2c6c;
    padding: 80px 60px;
    color: white;
}

.hero h1 {
    font-size: 48px;
    margin-bottom: 10px;
}

.hero p {
    font-size: 18px;
    opacity: 0.9;
}

/* SECCIONES */
.section {
    padding: 60px;
}

/* CARD */
.card {
    background: white;
    padding: 25px;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

/* BOTONES GRID */
.btn-card {
    background: #1976d2;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    color: white;
    font-weight: 500;
    margin: 10px;
}

/* TITULOS */
.section-title {
    font-size: 28px;
    margin-bottom: 20px;
}

/* FONDO AZUL SECCION */
.blue-section {
    background: #1565c0;
    color: white;
}

</style>
""", unsafe_allow_html=True)

# --- HERO ---
st.markdown("""
<div class="hero">
    <h1>Panel de Operaciones</h1>
    <p>Carrefour Online - Tienda 268</p>
    <p>Abril 2026</p>
</div>
""", unsafe_allow_html=True)

# --- PROCESADOR ---
st.markdown('<div class="section">', unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Procesador de Planillas</div>', unsafe_allow_html=True)

archivo = st.file_uploader("Cargar archivo Excel", type=["xlsx", "csv"])

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# --- FUNCIONES ---
st.markdown('<div class="section blue-section">', unsafe_allow_html=True)

st.markdown('<div class="section-title">Funciones rápidas</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("Clientes"):
        if archivo:
            df = pd.read_excel(archivo)
            logic_clientes.procesar(df)

with col2:
    if st.button("Faltantes"):
        if archivo:
            df = pd.read_excel(archivo)
            logic_faltantes.procesar(df)

with col3:
    if st.button("Domicilios"):
        if archivo:
            df = pd.read_excel(archivo)
            logic_domicilios.procesar(df)

with col4:
    if st.button("Informe"):
        if archivo:
            df = pd.read_excel(archivo)
            logic_informe.procesar(df)

st.markdown('</div>', unsafe_allow_html=True)

# --- RESULTADOS ---
st.markdown('<div class="section">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Resultados</div>', unsafe_allow_html=True)

st.info("Aquí se mostrarán los resultados del procesamiento")

st.markdown('</div>', unsafe_allow_html=True)
