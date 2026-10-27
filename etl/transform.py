import pandas as pd

def transformar_municipios(dados_brutos_ibge):
    """
    Estrutura a lista de municípios do IBGE.
    """
    linhas = []
    for item in dados_brutos_ibge:
        linhas.append({
            "id_ibge": item["id"],
            "nome_municipio": item["nome"]
        })
    return pd.DataFrame(linhas)

def transformar_clima_lote(lista_dados_clima):
    """
    Recebe a lista de respostas da Open-Meteo e consolida tudo num único DataFrame.
    """
    todos_registos = []
    
    for item in lista_dados_clima:
        nome_mun = item.get("municipio", "Desconhecido")
        dados_diarios = item.get("daily", {})
        
        datas = dados_diarios.get("time", [])
        temp_max = dados_diarios.get("temperature_2m_max", [])
        temp_min = dados_diarios.get("temperature_2m_min", [])
        chuva = dados_diarios.get("precipitation_sum", [])
        
        for i in range(len(datas)):
            todos_registos.append({
                "municipio": nome_mun,
                "data": datas[i],
                "temp_max": temp_max[i] if i < len(temp_max) else None,
                "temp_min": temp_min[i] if i < len(temp_min) else None,
                "chuva_mm": chuva[i] if i < len(chuva) else 0.0
            })
            
    df_final = pd.DataFrame(todos_registos)
    
    if not df_final.empty:
        df_final["data"] = pd.to_datetime(df_final["data"])
        df_final["chuva_mm"] = df_final["chuva_mm"].fillna(0.0)
        
    return df_final