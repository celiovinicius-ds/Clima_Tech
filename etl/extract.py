import time
import requests

URL_OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"

def extrair_clima_ano(codigo_ibge, nome_municipio, lat, lon, ano=2026):
    """
    Extrai dados diários da Open-Meteo para um município específico em um determinado ano.
    """
    parametros = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{ano}-01-01",
        "end_date": f"{ano}-12-31",
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "precipitation_sum",
            "wind_speed_10m_max",
            "shortwave_radiation_sum"
        ],
        "timezone": "America/Sao_Paulo"
    }
    
    try:
        resposta = requests.get(URL_OPEN_METEO, params=parametros, timeout=20)
        resposta.raise_for_status()
        dados = resposta.json()
        dados["codigo_ibge"] = codigo_ibge
        dados["municipio"] = nome_municipio
        return dados
    except Exception as erro:
        print(f"[ERRO] Falha ao extrair {nome_municipio} ({ano}): {erro}")
        return None