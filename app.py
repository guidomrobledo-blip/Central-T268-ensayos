import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logic_clientes, logic_faltantes, logic_domicilios, logic_informe
import os
import json
import hashlib

# --- CONFIGURACION ---
st.set_page_config(
    page_title="Panel Operaciones Online Carrefour",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ESTILO CORPORATIVO LIMPIO ---
st.markdown("""
<style>
/* Fondo general */
html, body, .stApp {
    background-color: #f5f7fa;
    font-family: 'Segoe UI', sans-serif;
}

/* Títulos */
h1 {
    font-size: 2.2rem;
    font-weight: 600;
    color: #1f3c88;
    margin-bottom: 0.5rem;
}

h2 {
    font-size: 1.4rem;
    color: #2c3e50;
}

/* Cards */
.block {
    background: white;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid #e3e6ea;
    margin-bottom: 20px;
}

/* Botones */
.stButton>button {
    width: 100%;
    border-radius: 8px;
    background-color: #1f3c88;
    color: white;
    border: none;
    padding: 10px;
    font-weight: 500;
}

.stButton>button:hover {
    background-color: #163172;
}

/* File uploader */
.stFileUploader {
    border: 1px dashed #ccd1d9;
    padding: 20px;
    border-radius: 10px;
    background-color: #fafbfc;
}

/* Separación */
.section {
    margin-top: 30px;
}
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown("<h1>Panel de Operaciones Online</h1>", unsafe_allow_html=True)
st.markdown("Gestión y procesamiento de pedidos Carrefour", unsafe_allow_html=True)

# --- BLOQUE PRINCIPAL ---
st.markdown('<div class="block">', unsafe_allow_html=True)
st.markdown("### Procesador de planillas")

archivo = st.file_uploader("Cargar archivo", type=["xlsx", "csv"])

st.markdown('</div>', unsafe_allow_html=True)

# --- ACCESOS RÁPIDOS ---
st.markdown('<div class="section"></div>', unsafe_allow_html=True)
st.markdown("## Funciones")

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

# --- RESULTADOS / ESPACIO FUTURO ---
st.markdown('<div class="section"></div>', unsafe_allow_html=True)
st.markdown("## Resultados")

st.info("Aquí se visualizarán los resultados del procesamiento.")
