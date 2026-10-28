import pandas as pd

def transformar_dados_clima(lista_respostas_api):
    """
    Transforma as respostas JSON da Open-Meteo em um DataFrame limpo e tipado.
    """
    registros = []
    
    for item in lista_respostas_api:
        if not item or "daily" not in item:
            continue
            
        codigo_ibge = item.get("codigo_ibge")
        municipio = item.get("municipio")
        daily = item.get("daily", {})
        
        datas = daily.get("time", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])
        temp_media = daily.get("temperature_2m_mean", [])
        precipitacao = daily.get("precipitation_sum", [])
        vento_max = daily.get("wind_speed_10m_max", [])
        radiacao = daily.get("shortwave_radiation_sum", [])
        
        for i in range(len(datas)):
            registros.append({
                "codigo_ibge": codigo_ibge,
                "municipio": municipio,
                "data": datas[i],
                "temp_max": temp_max[i] if i < len(temp_max) else None,
                "temp_min": temp_min[i] if i < len(temp_min) else None,
                "temp_media": temp_media[i] if i < len(temp_media) else None,
                "chuva_mm": precipitacao[i] if i < len(precipitacao) else 0.0,
                "vento_max_kmh": vento_max[i] if i < len(vento_max) else None,
                "radiacao_mj": radiacao[i] if i < len(radiacao) else None
            })
            
    df = pd.DataFrame(registros)
    if df.empty:
        return df

    # Tipagem e preenchimento
    df["data"] = pd.to_datetime(df["data"])
    df["chuva_mm"] = df["chuva_mm"].fillna(0.0)
    
    # Feature Engineering para Machine Learning
    df["amplitude_termica"] = df["temp_max"] - df["temp_min"]
    df["mes"] = df["data"].dt.month
    df["dia_do_ano"] = df["data"].dt.dayofyear
    
    return df