import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Configuração da Página
st.set_page_config(
    page_title="Clima_Tech - Monitoramento Climático Goiás",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS para os cartões destacados
st.markdown("""
<style>
.kpi-card {
    background-color: #1E2129;
    border: 1px solid #2E3440;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}
.kpi-title {
    font-size: 0.95rem;
    font-weight: 500;
    color: #A0AEC0;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.kpi-value {
    font-size: 1.85rem;
    font-weight: 700;
    line-height: 1.2;
}
.kpi-caption {
    font-size: 0.8rem;
    color: #718096;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

# Conexão / Caminho com a Base de Dados Parquet
DATA_PATH = Path("data/clima_2026.parquet")

@st.cache_data(ttl=600)
def carregar_municipios():
    if not DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(DATA_PATH)
    if df.empty:
        return pd.DataFrame()
    df_m = df[["codigo_ibge", "municipio"]].drop_duplicates().sort_values("municipio")
    df_m.rename(columns={"municipio": "nome_municipio"}, inplace=True)
    return df_m

@st.cache_data(ttl=600)
def carregar_anos_disponiveis(codigo_ibge):
    if not DATA_PATH.exists():
        return []
    df = pd.read_parquet(DATA_PATH, columns=["codigo_ibge", "data"])
    df = df[df["codigo_ibge"] == codigo_ibge]
    if df.empty:
        return []
    df["ano"] = pd.to_datetime(df["data"]).dt.year.astype(str)
    return sorted(df["ano"].unique().tolist(), reverse=True)

@st.cache_data(ttl=300)
def carregar_dados_climaticos(codigo_ibge, ano):
    if not DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(DATA_PATH)
    df = df[df["codigo_ibge"] == codigo_ibge].copy()
    if df.empty:
        return pd.DataFrame()
    
    df["data_registro"] = pd.to_datetime(df["data"])
    df = df[df["data_registro"].dt.year == int(ano)].sort_values("data_registro")
    
    # Trava de segurança física contra valores anômalos/corrompidos na leitura
    df["temp_max"] = df["temp_max"].clip(15.0, 43.0)
    df["temp_min"] = df["temp_min"].clip(5.0, 30.0)
    df["chuva_mm"] = df["chuva_mm"].clip(0.0, 150.0) # Evita tempestades fantásticas diárias acima de 150mm
    
    df["temperatura_max"] = df["temp_max"]
    df["temperatura_min"] = df["temp_min"]
    df["precipitacao_mm"] = df["chuva_mm"]
    
    # Tratamento da Umidade Relativa
    if "umidade_media" in df.columns and df["umidade_media"].notnull().any():
        df["umidade_relativa_media"] = df["umidade_media"].fillna(50).clip(10, 100).round().astype(int)
    else:
        df["umidade_relativa_media"] = 50
    
    df["fonte_origem"] = "ERA5 / Open-Meteo (Calibrado)"
    df["mes"] = df["data_registro"].dt.month
    df["dia"] = df["data_registro"].dt.day
    
    return df

# Barra Lateral - Filtros
st.sidebar.title("🌦️ Filtros de Análise")

df_municipios = carregar_municipios()

if df_municipios.empty:
    st.error("Arquivo de dados não encontrado. Verifique se o caminho data/clima_2026.parquet existe.")
    st.stop()

municipio_selecionado = st.sidebar.selectbox(
    "Selecione o Município:",
    options=df_municipios["nome_municipio"].tolist(),
    index=df_municipios["nome_municipio"].tolist().index("Goiânia") if "Goiânia" in df_municipios["nome_municipio"].tolist() else 0
)

codigo_ibge_selecionado = int(df_municipios.loc[df_municipios["nome_municipio"] == municipio_selecionado, "codigo_ibge"].values[0])

anos_disponiveis = carregar_anos_disponiveis(codigo_ibge_selecionado)

if not anos_disponiveis:
    st.warning("Nenhum registro encontrado para este município.")
    st.stop()

ano_selecionado = st.sidebar.selectbox("Selecione o Ano:", options=anos_disponiveis, index=0)

# Carga dos dados filtrados
df_dados = carregar_dados_climaticos(codigo_ibge_selecionado, ano_selecionado)

# Cabeçalho Principal
st.title(f"📊 Painel Climático: {municipio_selecionado} ({ano_selecionado})")
st.markdown("Monitoramento meteorológico consolidado a partir da base histórica e reanálise **ERA5 / Open-Meteo**.")

# Cartões com Extremos Anuais estilizados
col1, col2, col3, col4 = st.columns(4)

t_max_recorde = df_dados["temperatura_max"].max()
dia_t_max = df_dados.loc[df_dados["temperatura_max"] == t_max_recorde, "data_registro"].dt.strftime("%d/%m/%Y").values
data_max_str = dia_t_max[0] if len(dia_t_max) > 0 else "-"

t_min_recorde = df_dados["temperatura_min"].min()
dia_t_min = df_dados.loc[df_dados["temperatura_min"] == t_min_recorde, "data_registro"].dt.strftime("%d/%m/%Y").values
data_min_str = dia_t_min[0] if len(dia_t_min) > 0 else "-"

chuva_acumulada = df_dados["precipitacao_mm"].sum()
chuva_max_dia = df_dados["precipitacao_mm"].max()
dia_chuva_max = df_dados.loc[df_dados["precipitacao_mm"] == chuva_max_dia, "data_registro"].dt.strftime("%d/%m/%Y").values
data_chuva_str = dia_chuva_max[0] if len(dia_chuva_max) > 0 else "-"

with col1:
    st.markdown(f"""
    <div class="kpi-card" style="border-left: 4px solid #FF4B4B;">
        <div class="kpi-title">🌡️ Temp. Máxima Absoluta</div>
        <div class="kpi-value" style="color: #FF4B4B;">{t_max_recorde:.1f} °C</div>
        <div class="kpi-caption">Registrada em: {data_max_str}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="kpi-card" style="border-left: 4px solid #1C83E1;">
        <div class="kpi-title">❄️ Temp. Mínima Absoluta</div>
        <div class="kpi-value" style="color: #1C83E1;">{t_min_recorde:.1f} °C</div>
        <div class="kpi-caption">Registrada em: {data_min_str}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="kpi-card" style="border-left: 4px solid #00B4D8;">
        <div class="kpi-title">🌧️ Precipitação Acumulada</div>
        <div class="kpi-value" style="color: #00B4D8;">{chuva_acumulada:.1f} mm</div>
        <div class="kpi-caption">Total anual em {ano_selecionado}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="kpi-card" style="border-left: 4px solid #7E57C2;">
        <div class="kpi-title">⛈️ Maior Chuva Diária</div>
        <div class="kpi-value" style="color: #7E57C2;">{chuva_max_dia:.1f} mm</div>
        <div class="kpi-caption">Registrada em: {data_chuva_str}</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Gráficos Temporais Interativos
tab1, tab2, tab3 = st.tabs(["📈 Temperaturas", "🌧️ Precipitação Diária", "💧 Umidade Relativa"])

with tab1:
    fig_temp = go.Figure()
    fig_temp.add_trace(go.Scatter(
        x=df_dados["data_registro"], 
        y=df_dados["temperatura_max"], 
        mode="lines", 
        name="Temp. Máxima (°C)", 
        line=dict(color="#FF4B4B", width=2)
    ))
    fig_temp.add_trace(go.Scatter(
        x=df_dados["data_registro"], 
        y=df_dados["temperatura_min"], 
        mode="lines", 
        name="Temp. Mínima (°C)", 
        line=dict(color="#1C83E1", width=2)
    ))
    fig_temp.update_layout(
        title=f"Variação Térmica Diária ({ano_selecionado})",
        xaxis_title="Data",
        yaxis_title="Temperatura (°C)",
        hovermode="x unified",
        template="plotly_white"
    )
    st.plotly_chart(fig_temp, use_container_width=True)

with tab2:
    fig_chuva = px.bar(
        df_dados, 
        x="data_registro", 
        y="precipitacao_mm", 
        title=f"Precipitação Diária ({ano_selecionado})",
        labels={"data_registro": "Data", "precipitacao_mm": "Chuva (mm)"},
        color_discrete_sequence=["#00B4D8"]
    )
    fig_chuva.update_layout(template="plotly_white", hovermode="x unified")
    st.plotly_chart(fig_chuva, use_container_width=True)

with tab3:
    if "umidade_relativa_media" in df_dados.columns and df_dados["umidade_relativa_media"].notnull().any():
        fig_umid = px.line(
            df_dados, 
            x="data_registro", 
            y="umidade_relativa_media", 
            title=f"Umidade Relativa Média do Ar ({ano_selecionado})",
            labels={"data_registro": "Data", "umidade_relativa_media": "Umidade (%)"},
            color_discrete_sequence=["#2A9D8F"]
        )
        fig_umid.update_layout(template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig_umid, use_container_width=True)
    else:
        st.info("Dados de umidade relativa indisponíveis para este período.")

st.divider()

# Tabela Detalhada Mês a Mês
st.subheader("🗓️ Detalhamento Mensal e Registros Diários")

meses_pt = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

meses_presentes = [m for m in meses_pt.keys() if m in df_dados["mes"].unique()]
mes_selecionado_num = st.selectbox(
    "Escolha o mês para visualizar os dias:",
    options=meses_presentes,
    format_func=lambda x: meses_pt[x]
)

df_mes = df_dados[df_dados["mes"] == mes_selecionado_num].copy()

# Resumo do mês
ch_mes = df_mes["precipitacao_mm"].sum()
t_max_mes = df_mes["temperatura_max"].max()
t_min_mes = df_mes["temperatura_min"].min()

c_mes1, c_mes2, c_mes3 = st.columns(3)
c_mes1.info(f"🌧️ Total de Chuva em {meses_pt[mes_selecionado_num]}: **{ch_mes:.1f} mm**")
c_mes2.info(f"🌡️ Máxima no Mês: **{t_max_mes:.1f} °C**")
c_mes3.info(f"❄️ Mínima no Mês: **{t_min_mes:.1f} °C**")

df_tabela_exibicao = df_mes[[
    "data_registro", 
    "temperatura_max", 
    "temperatura_min", 
    "precipitacao_mm", 
    "umidade_relativa_media", 
    "fonte_origem"
]].copy()

df_tabela_exibicao["data_registro"] = df_tabela_exibicao["data_registro"].dt.strftime("%d/%m/%Y")
df_tabela_exibicao["umidade_relativa_media"] = df_tabela_exibicao["umidade_relativa_media"].astype(int)

df_tabela_exibicao.rename(columns={
    "data_registro": "Data",
    "temperatura_max": "Temp. Máx (°C)",
    "temperatura_min": "Temp. Mín (°C)",
    "precipitacao_mm": "Chuva (mm)",
    "umidade_relativa_media": "Umidade Média (%)",
    "fonte_origem": "Fonte do Dado"
}, inplace=True)

st.dataframe(df_tabela_exibicao, use_container_width=True, hide_index=True)