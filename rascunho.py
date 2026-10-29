import pandas as pd
import requests
import json
import time
from datetime import datetime
from etl.transform import aplicar_calibracao

print("1. Baixando dados limpos da Open-Meteo...")

with open("data/municipios_go.json", "r", encoding="utf-8") as f:
    municipios = json.load(f)

HOJE = datetime.now().strftime("%Y-%m-%d")
registros = []

for m in municipios:
    nome = m["nome"]
    ibge = m["codigo_ibge"]
    lat = m["latitude"]
    lon = m["longitude"]
    
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date=2026-01-01&end_date={HOJE}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_mean&timezone=America/Sao_Paulo"
    
    sucesso = False
    tentativas = 0
    while not sucesso and tentativas < 3:
        try:
            res = requests.get(url, timeout=30).json()
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
                registros.append(df_m)
                sucesso = True
        except Exception:
            tentativas += 1
            time.sleep(2)  # Espera 2 segundos antes de tentar de novo se der timeout
            
    time.sleep(0.2)  # Pausa leve para não sobrecarregar a API

# Trava de segurança: só salva se conseguiu baixar todos (ou pelo menos mais de 240 municípios)
if len(registros) >= 240:
    df_bruto = pd.concat(registros, ignore_index=True)
    df_calibrado = aplicar_calibracao(df_bruto)
    df_calibrado.to_parquet("data/clima_2026.parquet", index=False)
    print(f"\n[SUCESSO] Base atualizada com {len(registros)} cidades!")
else:
    print(f"[AVISO] Download incompleto ({len(registros)} cidades). O arquivo não foi sobrescrito para evitar perda de dados.")