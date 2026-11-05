import zipfile
import io
import json
import time
import sys
import os
from pathlib import Path
import pandas as pd
import requests

# Importação robusta do módulo de transformação
try:
    from etl.transform import aplicar_calibracao
except ModuleNotFoundError:
    from transform import aplicar_calibracao

if len(sys.argv) > 1:
    ANO = str(sys.argv[1]).strip()
else:
    ANO = input("Digite o ano que deseja processar (ex: 2021): ").strip()

ZIP_PATH = f"{ANO}.zip"
JSON_MUNICIPIOS = "data/municipios_go.json"
OUTPUT_PARQUET = f"data/clima_{ANO}.parquet"
TEMP_RAW_PARQUET = f"data/temp_raw_{ANO}.parquet"

print(f"\n--- Iniciando Processamento do Ano: {ANO} ---")

# 1. Carregar lista dos 246 municípios de Goiás
with open(JSON_MUNICIPIOS, "r", encoding="utf-8") as f:
    municipios = json.load(f)

# 2. Extração e agregação diária das estações do INMET em Goiás
print(f"1. Lendo estações do INMET dentro de {ZIP_PATH}...")
dados_inmet = []

try:
    with zipfile.ZipFile(ZIP_PATH, 'r') as z:
        ficheiros_go = [nome for nome in z.namelist() if "_GO_" in nome and nome.endswith(".CSV")]
        print(f"Estações de Goiás encontradas no ZIP: {len(ficheiros_go)}")

        for nome_arq in ficheiros_go:
            with z.open(nome_arq) as f:
                conteudo = io.TextIOWrapper(f, encoding="latin-1")
                
                linhas_cabecalho = [conteudo.readline() for _ in range(8)]
                nome_estacao = linhas_cabecalho[1].split(";")[1].strip().upper()
                
                conteudo.seek(0)
                df_est = pd.read_csv(
                    conteudo,
                    sep=";",
                    skiprows=8,
                    decimal=",",
                    na_values=["-9999", -9999]
                )
                
                df_est.columns = [c.strip().upper() for c in df_est.columns]
                
                col_data = [c for c in df_est.columns if "DATA" in c][0]
                col_precip = [c for c in df_est.columns if "PRECIPITAÇÃO TOTAL" in c or "PRECIPITACAO TOTAL" in c][0]
                col_temp = [c for c in df_est.columns if "TEMPERATURA DO AR - BULBO SECO" in c][0]
                col_umid = [c for c in df_est.columns if "HUMIDADE RELATIVA DO AR" in c or "UMIDADE RELATIVA DO AR" in c][0]
                
                df_est["DATA"] = pd.to_datetime(df_est[col_data].astype(str).str.replace("/", "-"))
                
                df_diario = df_est.groupby("DATA").agg(
                    temp_max=(col_temp, "max"),
                    temp_min=(col_temp, "min"),
                    chuva_mm=(col_precip, "sum"),
                    umidade_media=(col_umid, "mean")
                ).reset_index()
                
                df_diario["estacao_inmet"] = nome_estacao
                dados_inmet.append(df_diario)

    df_inmet_total = pd.concat(dados_inmet, ignore_index=True) if dados_inmet else pd.DataFrame()
except FileNotFoundError:
    print(f"[AVISO] O arquivo {ZIP_PATH} não foi encontrado na raiz. O script seguirá apenas com dados Open-Meteo calibrados.")
    df_inmet_total = pd.DataFrame()

# 3. Baixar dados da Open-Meteo com Sistema de Checkpoint / Retomada
print(f"\n2. Baixando série histórica de {ANO} da Open-Meteo para 246 municípios...")

# Carregar checkpoint se já existir
if os.path.exists(TEMP_RAW_PARQUET):
    df_checkpoint = pd.read_parquet(TEMP_RAW_PARQUET)
    ibges_processados = set(df_checkpoint["codigo_ibge"].unique())
    registros_openmeteo = [df_checkpoint]
    print(f"[RECUPERAÇÃO] Encontrado progresso anterior: {len(ibges_processados)} municípios já salvos.")
else:
    ibges_processados = set()
    registros_openmeteo = []

total_m = len(municipios)

for i, m in enumerate(municipios, 1):
    ibge = m["codigo_ibge"]
    nome = m["nome"]
    
    # Pula as cidades que já foram baixadas e salvas em disco
    if ibge in ibges_processados:
        print(f"\r[{i:03d}/{total_m:03d}] ({(i/total_m)*100:5.1f}%) [CACHE] Já baixado: {nome:<30}", end="", flush=True)
        continue

    lat = m["latitude"]
    lon = m["longitude"]
    
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}&start_date={ANO}-01-01&end_date={ANO}-12-31&"
        f"daily=temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_mean&"
        f"timezone=America/Sao_Paulo"
    )
    
    sucesso = False
    tentativas = 0
    while not sucesso and tentativas < 3:
        try:
            resposta = requests.get(url, timeout=15)
            
            if resposta.status_code == 429:
                print(f"\n[AVISO] Limite da API atingido. Aguardando 15 segundos antes de tentar novamente...")
                time.sleep(15)
                tentativas += 1
                continue
                
            res = resposta.json()
            if "daily" in res:
                df_m = pd.DataFrame({
                    'codigo_ibge': ibge,
                    'municipio': nome,
                    'data': res['daily']['time'],
                    'temp_max': res['daily']['temperature_2m_max'],
                    'temp_min': res['daily']['temperature_2m_min'],
                    'chuva_mm': res['daily']['precipitation_sum'],
                    'umidade_media': res['daily']['relative_humidity_2m_mean']
                })
                registros_openmeteo.append(df_m)
                ibges_processados.add(ibge)
                
                # Salva em disco a cada nova cidade baixada para garantir que nenhum dado se perca
                df_acumulado = pd.concat(registros_openmeteo, ignore_index=True)
                df_acumulado.to_parquet(TEMP_RAW_PARQUET, index=False)
                
                sucesso = True
                porcentagem = (i / total_m) * 100
                print(f"\r[{i:03d}/{total_m:03d}] ({porcentagem:5.1f}%) Baixado: {nome:<30}", end="", flush=True)
        except Exception:
            tentativas += 1
            time.sleep(2)
            
    time.sleep(0.15)

print()

df_om_bruto = pd.read_parquet(TEMP_RAW_PARQUET)

if df_om_bruto["codigo_ibge"].nunique() < 240:
    raise RuntimeError(f"Download incompleto ({df_om_bruto['codigo_ibge'].nunique()} municípios). Processo pausado. Execute novamente após a API liberar.")

df_final = aplicar_calibracao(df_om_bruto)
df_final['data'] = pd.to_datetime(df_final['data'])

# Converte colunas numéricas para float64
for col in ['temp_max', 'temp_min', 'chuva_mm', 'umidade_media']:
    df_final[col] = df_final[col].astype('float64')

# 4. Imputação / Sobreposição das estações do INMET
if not df_inmet_total.empty:
    print("\n3. Sobrepondo dados oficiais do INMET e preenchendo falhas...")
    for estacao in df_inmet_total['estacao_inmet'].unique():
        sub_inmet = df_inmet_total[df_inmet_total['estacao_inmet'] == estacao]
        mascara_mun = df_final['municipio'].str.upper().str.contains(estacao, na=False)
        
        if mascara_mun.any():
            mun_alvo = df_final.loc[mascara_mun, 'municipio'].iloc[0]
            for _, linha in sub_inmet.iterrows():
                idx = (df_final['municipio'] == mun_alvo) & (df_final['data'] == linha['DATA'])
                if idx.any():
                    if pd.notna(linha['temp_max']):
                        df_final.loc[idx, 'temp_max'] = float(linha['temp_max'])
                    if pd.notna(linha['temp_min']):
                        df_final.loc[idx, 'temp_min'] = float(linha['temp_min'])
                    if pd.notna(linha['chuva_mm']):
                        df_final.loc[idx, 'chuva_mm'] = float(linha['chuva_mm'])
                    if pd.notna(linha['umidade_media']):
                        df_final.loc[idx, 'umidade_media'] = float(linha['umidade_media'])

# 5. Salvar Parquet final e remover checkpoint temporário
df_final['data'] = df_final['data'].dt.strftime('%Y-%m-%d')
df_final.to_parquet(OUTPUT_PARQUET, index=False)

if os.path.exists(TEMP_RAW_PARQUET):
    os.remove(TEMP_RAW_PARQUET)

print(f"\n[SUCESSO] Base final de {ANO} gravada com sucesso em: {OUTPUT_PARQUET}")