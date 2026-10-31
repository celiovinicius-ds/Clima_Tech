import zipfile
import io
import json
import time
import sys
import pandas as pd
import requests

# Importação robusta do módulo de transformação
try:
    from etl.transform import aplicar_calibracao
except ModuleNotFoundError:
    from transform import aplicar_calibracao

# Se passar o ano no terminal (ex: python etl/processar_anos.py 2025), usa ele.
# Senão, pergunta interativamente no console.
if len(sys.argv) > 1:
    ANO = str(sys.argv[1]).strip()
else:
    ANO = input("Digite o ano que deseja processar (ex: 2025): ").strip()

ZIP_PATH = f"{ANO}.zip"
JSON_MUNICIPIOS = "data/municipios_go.json"
OUTPUT_PARQUET = f"data/clima_{ANO}.parquet"

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
                
                # Leitura do cabeçalho para pegar o nome da estação
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

# 3. Baixar dados da Open-Meteo para os 246 municípios no ano selecionado
print(f"\n2. Baixando série histórica de {ANO} da Open-Meteo para 246 municípios...")
registros_openmeteo = []

for m in municipios:
    nome = m["nome"]
    ibge = m["codigo_ibge"]
    lat = m["latitude"]
    lon = m["longitude"]
    
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={ANO}-01-01&end_date={ANO}-12-31&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_mean&timezone=America/Sao_Paulo"
    
    sucesso = False
    tentativas = 0
    while not sucesso and tentativas < 3:
        try:
            res = requests.get(url, timeout=15).json()
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
                sucesso = True
        except Exception:
            tentativas += 1
            time.sleep(2)
            
    time.sleep(0.15)

if len(registros_openmeteo) < 240:
    raise RuntimeError(f"Download incompleto ({len(registros_openmeteo)} municípios). Processo cancelado para proteger a integridade.")

df_om_bruto = pd.concat(registros_openmeteo, ignore_index=True)
df_final = aplicar_calibracao(df_om_bruto)
df_final['data'] = pd.to_datetime(df_final['data'])

# Converte explicitamente as colunas numéricas para float64 para evitar LossySetitemError
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

# 5. Salvar Parquet com o nome dinâmico do ano
df_final['data'] = df_final['data'].dt.strftime('%Y-%m-%d')
df_final.to_parquet(OUTPUT_PARQUET, index=False)
print(f"\n[SUCESSO] Base final de {ANO} gravada com sucesso em: {OUTPUT_PARQUET}")