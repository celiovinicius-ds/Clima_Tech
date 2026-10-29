import json
import os
import pandas as pd

def aplicar_calibracao(df_bruto):
    """
    Recebe o DataFrame da Open-Meteo e aplica a matemática de calibração 
    (Bias Correction) baseada nas estações do INMET mapeadas.
    """
    arq_map = os.path.join("data", "mapeamento_estacoes.json")
    arq_fat = os.path.join("data", "fatores_calibracao.json")

    if not os.path.exists(arq_map) or not os.path.exists(arq_fat):
        print("[AVISO] Arquivos de calibração ausentes. Retornando dados brutos.")
        return df_bruto

    with open(arq_map, "r", encoding="utf-8") as f:
        mapa = {item["municipio"]: item["wmo"] for item in json.load(f)}
    
    with open(arq_fat, "r", encoding="utf-8") as f:
        fatores = json.load(f)

    def corrigir(row):
        wmo = mapa.get(row["municipio"])
        if wmo and wmo in fatores:
            # Soma a diferença histórica à temperatura que a API reportou hoje
            row["temp_max"] = round(row["temp_max"] + fatores[wmo]["ajuste_tmax"], 1)
            row["temp_min"] = round(row["temp_min"] + fatores[wmo]["ajuste_tmin"], 1)
        return row

    return df_bruto.apply(corrigir, axis=1)