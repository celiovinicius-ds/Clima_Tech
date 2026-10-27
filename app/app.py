import os
import sys
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

# Define a raiz real do projeto (um nível acima da pasta app/)
DIRETORIO_APP = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_RAIZ = os.path.dirname(DIRETORIO_APP)

# Garante que a raiz do projeto está no sys.path
if DIRETORIO_RAIZ not in sys.path:
    sys.path.insert(0, DIRETORIO_RAIZ)

# Caminho absoluto da base de dados na raiz
CAMINHO_BANCO = os.path.join(DIRETORIO_RAIZ, "data", "banco_oraculo.db")

@st.cache_data
def carregar_dados():
    # Se a base de dados não existir na nuvem, executa o pipeline diretamente
    if not os.path.exists(CAMINHO_BANCO):
        with st.spinner("Base de dados ausente. Baixando dados via API e gerando banco..."):
            os.makedirs(os.path.join(DIRETORIO_RAIZ, "data"), exist_ok=True)
            
            # Executa o script main.py a partir da raiz do projeto
            import subprocess
            caminho_main = os.path.join(DIRETORIO_RAIZ, "main.py")
            subprocess.run([sys.executable, caminho_main], cwd=DIRETORIO_RAIZ, check=True)

    conexao = sqlite3.connect(CAMINHO_BANCO)
    df = pd.read_sql_query("SELECT * FROM clima_historico", conexao)
    conexao.close()
    
    # Tratamento de tipos
    df["data"] = pd.to_datetime(df["data"])
    return df

# Título e cabeçalho
st.title("🌤️ Clima_Tech: Análise Climática de Goiás")
st.markdown("Painel de monitoramento e análise meteorológica construído com dados do **ERA5 / Open-Meteo**.")
st.markdown("EM DESENVOLVIMENTO😎")

# Carregar os dados
try:
    df_clima = carregar_dados()
    
    # Barra lateral - Filtros
    st.sidebar.header("Filtros")
    cidades_disponiveis = sorted(df_clima["municipio"].unique())
    cidade_selecionada = st.sidebar.selectbox("Selecione o Município:", cidades_disponiveis)
    
    # Filtrar dados pelo município
    df_filtrado = df_clima[df_clima["municipio"] == cidade_selecionada].sort_values("data")
    
    # Métricas principais (KPIs)
    t_max = df_filtrado["temp_max"].max()
    t_min = df_filtrado["temp_min"].min()
    chuva_total = df_filtrado["chuva_mm"].sum()
    dias_com_chuva = (df_filtrado["chuva_mm"] > 0).sum()
    
    st.subheader(f"Visão Geral: {cidade_selecionada}")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Temp. Máxima Registrada", f"{t_max:.1f} °C")
    col2.metric("Temp. Mínima Registrada", f"{t_min:.1f} °C")
    col3.metric("Precipitação Acumulada", f"{chuva_total:.1f} mm")
    col4.metric("Dias com Chuva", f"{dias_com_chuva} dias")
    
    st.divider()
    
    # Gráficos
    col_graf1, col_graf2 = st.columns(2)
    
    with col_graf1:
        st.subheader("📈 Variação de Temperatura Diária")
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(
            x=df_filtrado["data"], y=df_filtrado["temp_max"],
            mode="lines+markers", name="Máxima", line=dict(color="#FF4B4B")
        ))
        fig_temp.add_trace(go.Scatter(
            x=df_filtrado["data"], y=df_filtrado["temp_min"],
            mode="lines+markers", name="Mínima", line=dict(color="#0068C9")
        ))
        fig_temp.update_layout(
            xaxis_title="Data",
            yaxis_title="Temperatura (°C)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_temp, use_container_width=True)
        
    with col_graf2:
        st.subheader("🌧️ Volume de Chuva Diário")
        fig_chuva = px.bar(
            df_filtrado,
            x="data",
            y="chuva_mm",
            labels={"data": "Data", "chuva_mm": "Chuva (mm)"},
            color_discrete_sequence=["#1E88E5"]
        )
        fig_chuva.update_layout(xaxis_title="Data", yaxis_title="Precipitação (mm)")
        st.plotly_chart(fig_chuva, use_container_width=True)

    # Tabela com dados detalhados
    with st.expander("Ver Tabela de Dados"):
        st.dataframe(df_filtrado, use_container_width=True)

except Exception as e:
    st.error(f"Erro ao carregar dados do banco: {e}")
    st.info("Certifique-se de que o pipeline executou e gerou o 'data/banco_oraculo.db'.")