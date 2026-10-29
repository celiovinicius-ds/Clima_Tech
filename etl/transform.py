import json
import os
import pandas as pd

def aplicar_calibracao(df_bruto):
    """
    Aplica correção de viés (MOS) para todas as 246 cidades de Goiás.
    """
    arq_map = os.path.join("data", "mapeamento_estacoes.json")
    arq_fat = os.path.join("data", "fatores_calibracao.json")

    if not os.path.exists(arq_map) or not os.path.exists(arq_fat):
        return df_bruto

    with open(arq_map, "r", encoding="utf-8") as f:
        mapa = {item["municipio"]: item["wmo"] for item in json.load(f)}
    
    with open(arq_fat, "r", encoding="utf-8") as f:
        fatores = json.load(f)

    def corrigir(row):
        wmo = mapa.get(row["municipio"])
        if wmo and wmo in fatores:
            f = fatores[wmo]
            
            # Temperaturas
            if pd.notna(row.get("temp_max")):
                row["temp_max"] = round(row["temp_max"] + f.get("ajuste_tmax", 0), 1)
            if pd.notna(row.get("temp_min")):
                row["temp_min"] = round(row["temp_min"] + f.get("ajuste_tmin", 0), 1)
                
            # Umidade (Trava 0-100%)
            if pd.notna(row.get("umidade_media")):
                umid = row["umidade_media"] + f.get("ajuste_umidade", 0)
                row["umidade_media"] = int(max(0, min(100, round(umid))))

            # Chuva (Multiplicador seguro)
            if pd.notna(row.get("chuva_mm")):
                chuva_corrigida = row["chuva_mm"] * f.get("fator_chuva", 1.0)
                row["chuva_mm"] = round(max(0.0, chuva_corrigida), 1)
                
        return row

    return df_bruto.apply(corrigir, axis=1)