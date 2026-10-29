import zipfile
import pandas as pd
import json
import math
import numpy as np
import requests
from datetime import datetime

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
    print("1. Mapeando 246 cidades...")
    estacoes = []
    with zipfile.ZipFile(CAMINHO_ZIP, 'r') as z:
        for arq in z.namelist():
            if "CO_GO" in arq and arq.upper().endswith(".CSV"):
                with z.open(arq) as f:
                    linhas = f.read().decode('latin1').splitlines()
                    try:
                        estacoes.append({
                            "wmo": linhas[3].split(';')[1].strip(),
                            "estacao": linhas[2].split(';')[1].strip(),
                            "lat": float(linhas[4].split(';')[1].replace(',', '.').strip()),
                            "lon": float(linhas[5].split(';')[1].replace(',', '.').strip()),
                            "csv": arq
                        })
                    except Exception:
                        continue

    with open(CAMINHO_MUNICIPIOS, 'r', encoding='utf-8') as f:
        municipios = json.load(f)

    mapeamento = []
    for m in municipios:
        est_proxima = min(estacoes, key=lambda e: haversine(m["latitude"], m["longitude"], e["lat"], e["lon"]))
        mapeamento.append({
            "municipio": m["nome"],
            "wmo": est_proxima["wmo"],
            "estacao": est_proxima["estacao"],
            "csv": est_proxima["csv"]
        })
    
    with open(OUT_MAP, 'w', encoding='utf-8') as f:
        json.dump(mapeamento, f, ensure_ascii=False, indent=2)

    print("2. Calculando fatores MOS seguros para o estado inteiro...")
    estacoes_unicas = {m["wmo"]: m for m in mapeamento}
    fatores = {}

    HOJE = datetime.now().strftime("%Y-%m-%d")

    with zipfile.ZipFile(CAMINHO_ZIP, 'r') as z:
        for wmo, est in estacoes_unicas.items():
            print(f"Analisando estação: {est['estacao']}...")
            try:
                with z.open(est["csv"]) as f:
                    df_inmet = pd.read_csv(f, sep=';', encoding='latin1', skiprows=8, decimal=',')
                
                col_data = [c for c in df_inmet.columns if 'DATA' in c.upper()][0]
                col_tmax = [c for c in df_inmet.columns if 'MÁX' in c.upper() and 'TEMP' in c.upper() and 'ORVALHO' not in c.upper()][0]
                col_tmin = [c for c in df_inmet.columns if 'MÍN' in c.upper() and 'TEMP' in c.upper() and 'ORVALHO' not in c.upper()][0]
                col_chuva = [c for c in df_inmet.columns if 'PRECIPITAÇÃO' in c.upper() or 'CHUVA' in c.upper()][0]
                col_umidade = [c for c in df_inmet.columns if 'UMIDADE' in c.upper()][0]

                df_inmet = df_inmet.rename(columns={
                    col_data: 'data', col_tmax: 'tmax', col_tmin: 'tmin', 
                    col_chuva: 'chuva', col_umidade: 'umidade'
                })[['data', 'tmax', 'tmin', 'chuva', 'umidade']].replace(-9999.0, np.nan)
                
                df_inmet['data'] = pd.to_datetime(df_inmet['data'], errors='coerce')
                df_inmet = df_inmet.dropna(subset=['data'])
                df_inmet['data'] = df_inmet['data'].dt.strftime('%Y-%m-%d')

                df_inmet = df_inmet.groupby('data').agg({
                    'tmax': 'max', 'tmin': 'min', 'chuva': 'sum', 'umidade': 'mean'
                }).reset_index().dropna(subset=['tmax', 'tmin'])

                if df_inmet.empty:
                    continue
                
                data_inicio = df_inmet['data'].min()
                data_fim = min(df_inmet['data'].max(), HOJE)

                lat = next(e["lat"] for e in estacoes if e["wmo"] == wmo)
                lon = next(e["lon"] for e in estacoes if e["wmo"] == wmo)

                res = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
                    "latitude": lat, "longitude": lon,
                    "start_date": data_inicio, "end_date": data_fim,
                    "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "relative_humidity_2m_mean"], 
                    "timezone": "America/Sao_Paulo"
                }, timeout=15).json()

                if "daily" not in res:
                    continue

                df_om = pd.DataFrame({
                    'data': res['daily']['time'], 
                    'om_tmax': res['daily']['temperature_2m_max'], 
                    'om_tmin': res['daily']['temperature_2m_min'],
                    'om_chuva': res['daily']['precipitation_sum'],
                    'om_umidade': res['daily']['relative_humidity_2m_mean']
                })
                df_merge = pd.merge(df_inmet, df_om, on='data').dropna(subset=['tmax', 'tmin', 'om_tmax', 'om_tmin'])
                
                if df_merge.empty:
                    continue

                # Trava de segurança para o multiplicador de chuva (entre 0.8 e 1.3)
                tot_inmet = df_merge['chuva'].sum()
                tot_om = df_merge['om_chuva'].sum()
                fator_chuva = float(max(0.8, min(1.3, tot_inmet / tot_om))) if tot_om > 1.0 else 1.0

                fatores[wmo] = {
                    "ajuste_tmax": round(float((df_merge['tmax'] - df_merge['om_tmax']).mean()), 2),
                    "ajuste_tmin": round(float((df_merge['tmin'] - df_merge['om_tmin']).mean()), 2),
                    "ajuste_umidade": round(float((df_merge['umidade'] - df_merge['om_umidade']).mean()), 2),
                    "fator_chuva": round(fator_chuva, 2)
                }
                print(f"  -> {est['estacao']}: OK")
            except Exception as e:
                print(f"  -> Erro na estação {wmo}: {e}")

    with open(OUT_FATORES, 'w', encoding='utf-8') as f:
        json.dump(fatores, f, ensure_ascii=False, indent=2)
    print(f"\n[SUCESSO] Total de estações calibradas: {len(fatores)}")

if __name__ == "__main__":
    main()