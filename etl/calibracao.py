import zipfile
import pandas as pd
import json
import math
import numpy as np
import requests
import os

# Nome do arquivo corrigido com aspas (String)
CAMINHO_ZIP = "2026.zip"
CAMINHO_MUNICIPIOS = "data/municipios_go.json"
OUT_MAP = "data/mapeamento_estacoes.json"
OUT_FATORES = "data/fatores_calibracao.json"

def haversine(lat1, lon1, lat2, lon2):
    R, l1, l2 = 6371.0, math.radians(lat1), math.radians(lat2)
    dl, do = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dl/2)**2 + math.cos(l1) * math.cos(l2) * math.sin(do/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def main():
    print("1. Mapeando 246 cidades para as estações do INMET...")
    estacoes = []
    # O comando with agora usa a variável configurada lá em cima
    with zipfile.ZipFile(CAMINHO_ZIP, 'r') as z:
        for arq in z.namelist():
            if "CO_GO" in arq and arq.upper().endswith(".CSV"):
                with z.open(arq) as f:
                    linhas = f.read().decode('latin1').splitlines()
                    estacoes.append({
                        "wmo": linhas[3].split(';')[1],
                        "nome": linhas[2].split(';')[1],
                        "lat": float(linhas[4].split(';')[1].replace(',', '.')),
                        "lon": float(linhas[5].split(';')[1].replace(',', '.')),
                        "csv": arq
                    })

    with open(CAMINHO_MUNICIPIOS, 'r', encoding='utf-8') as f:
        municipios = json.load(f)

    mapeamento = []
    for m in municipios:
        est_proxima = min(estacoes, key=lambda e: haversine(m["latitude"], m["longitude"], e["lat"], e["lon"]))
        mapeamento.append({
            "municipio": m["nome"],
            "wmo": est_proxima["wmo"],
            "estacao": est_proxima["nome"],
            "csv": est_proxima["csv"]
        })
    
    with open(OUT_MAP, 'w', encoding='utf-8') as f:
        json.dump(mapeamento, f, ensure_ascii=False, indent=2)

    print("2. Calculando o viés (Bias Correction) com a Open-Meteo...")
    estacoes_unicas = {m["wmo"]: m for m in mapeamento}
    fatores = {}

    with zipfile.ZipFile(CAMINHO_ZIP, 'r') as z:
        for wmo, est in estacoes_unicas.items():
            try:
                with z.open(est["csv"]) as f:
                    df_inmet = pd.read_csv(f, sep=';', encoding='latin1', skiprows=8, decimal=',')
                df_inmet = df_inmet.rename(columns={
                    'DATA (YYYY-MM-DD)': 'data',
                    'TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C)': 'tmax',
                    'TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C)': 'tmin'
                })[['data', 'tmax', 'tmin']].replace(-9999.0, np.nan).groupby('data').agg({'tmax':'max', 'tmin':'min'}).reset_index().dropna()

                if df_inmet.empty: continue
                
                # Puxa Open-Meteo do mesmo período
                res = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
                    "latitude": next(e["lat"] for e in estacoes if e["wmo"] == wmo),
                    "longitude": next(e["lon"] for e in estacoes if e["wmo"] == wmo),
                    "start_date": df_inmet['data'].min(), "end_date": df_inmet['data'].max(),
                    "daily": ["temperature_2m_max", "temperature_2m_min"], "timezone": "America/Sao_Paulo"
                }).json()

                df_om = pd.DataFrame({'data': res['daily']['time'], 'om_tmax': res['daily']['temperature_2m_max'], 'om_tmin': res['daily']['temperature_2m_min']})
                df_merge = pd.merge(df_inmet, df_om, on='data')
                
                fatores[wmo] = {
                    "ajuste_tmax": round((df_merge['tmax'] - df_merge['om_tmax']).mean(), 2),
                    "ajuste_tmin": round((df_merge['tmin'] - df_merge['om_tmin']).mean(), 2)
                }
            except Exception as e:
                pass # Ignora erros pontuais de API para não travar o loop

    with open(OUT_FATORES, 'w', encoding='utf-8') as f:
        json.dump(fatores, f, ensure_ascii=False, indent=2)
    print(f"Sucesso! Regras de calibração salvas na pasta data/.")

if __name__ == "__main__":
    main()