import pandas as pd
import requests
import json
import time
from datetime import datetime
from etl.transform import aplicar_calibracao

print("1. A descarregar dados limpos da Open-Meteo com espaçamento seguro...")

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
    
    try:
        # Timeout alargado para 30 segundos
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
            print(f"  -> {nome}: OK")
        
        # Pausa de 0.3 segundos para respeitar o servidor e evitar bloqueio
        time.sleep(0.3)
    except Exception as e:
        print(f"Erro em {nome}: {e}")

if registros:
    df_bruto = pd.concat(registros, ignore_index=True)
    
    print("2. A aplicar a calibração oficial do INMET...")
    df_calibrado = aplicar_calibracao(df_bruto)
    
    df_calibrado.to_parquet("data/clima_2026.parquet", index=False)
    print("\n[SUCESSO] Base gerada, calibrada e salva em data/clima_2026.parquet!")
else:
    print("[ERRO] Nenhum dado foi descarregado.")