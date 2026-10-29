import os
import json
from datetime import datetime, timedelta
import pandas as pd
import requests

# Importa a função de calibração que criamos no transform.py
from etl.transform import aplicar_calibracao

URL_OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"

def atualizar_dados_dia_anterior():
    # Coleta os dados consolidados do dia anterior
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    ano_atual = datetime.now().year
    
    caminho_parquet = os.path.join("data", f"clima_{ano_atual}.parquet")
    caminho_municipios = os.path.join("data", "municipios_go.json")

    if not os.path.exists(caminho_municipios):
        print(f"[ERRO] Metadados dos municípios não encontrados em {caminho_municipios}.")
        return

    with open(caminho_municipios, "r", encoding="utf-8") as f:
        municipios = json.load(f)

    print(f"Iniciando coleta automática para {ontem} ({len(municipios)} municípios)...")
    novos_registros = []

    for m in municipios:
        parametros = {
            "latitude": m["latitude"],
            "longitude": m["longitude"],
            "start_date": ontem,
            "end_date": ontem,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "relative_humidity_2m_mean"  # Dado medido oficial
            ],
            "timezone": "America/Sao_Paulo"
        }
        try:
            resposta = requests.get(URL_OPEN_METEO, params=parametros, timeout=20)
            if resposta.status_code == 200:
                dados = resposta.json().get("daily", {})
                umidade_bruta = dados.get("relative_humidity_2m_mean", [None])[0]
                umidade_final = round(umidade_bruta) if umidade_bruta is not None else None

                novos_registros.append({
                    "codigo_ibge": m["codigo_ibge"],
                    "municipio": m["nome"],
                    "data": ontem,
                    "temp_max": dados.get("temperature_2m_max", [None])[0],
                    "temp_min": dados.get("temperature_2m_min", [None])[0],
                    "chuva_mm": dados.get("precipitation_sum", [0.0])[0],
                    "umidade_media": umidade_final
                })
        except Exception as e:
            print(f"[ALERTA] Falha na coleta de {m['nome']}: {e}")
            continue

    if not novos_registros:
        print("[AVISO] Nenhum registro novo foi obtido.")
        return

    df_novos = pd.DataFrame(novos_registros)
    
    # --- APLICAÇÃO DA CALIBRAÇÃO (MOS) ---
    # Corrige as temperaturas da Open-Meteo com base no viés histórico
    df_novos = aplicar_calibracao(df_novos)
    # -------------------------------------

    df_novos["data"] = pd.to_datetime(df_novos["data"])

    if os.path.exists(caminho_parquet):
        df_existente = pd.read_parquet(caminho_parquet)
        df_existente["data"] = pd.to_datetime(df_existente["data"])
        
        # Concatena e remove duplicações se já tiver rodado
        df_final = pd.concat([df_existente, df_novos], ignore_index=True)
        df_final = df_final.drop_duplicates(subset=["codigo_ibge", "data"], keep="last")
    else:
        df_final = df_novos

    df_final.to_parquet(caminho_parquet, index=False, engine="pyarrow")
    print(f"[SUCESSO] Base {caminho_parquet} atualizada e calibrada com os dados de {ontem}!")

if __name__ == "__main__":
    atualizar_dados_dia_anterior()