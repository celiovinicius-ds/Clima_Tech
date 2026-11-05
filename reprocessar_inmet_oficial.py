import zipfile
import io
import re
import json
import unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

ANOS_HISTORICOS = ["2022", "2023", "2024", "2025"]
JSON_MUNICIPIOS = Path("data/municipios_go.json")
LIMIAR_MINIMO_CHUVA = 1000.0

def normalizar_texto(texto):
    if not texto:
        return ""
    limpo = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^A-Z0-9]', '', limpo.upper())

def calcular_haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    return 2 * r * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

# 1. Carregar municípios e altitudes
if not JSON_MUNICIPIOS.exists():
    raise FileNotFoundError(f"Arquivo '{JSON_MUNICIPIOS}' não encontrado.")

with open(JSON_MUNICIPIOS, "r", encoding="utf-8") as f:
    lista_mun = json.load(f)

geo_map = {}
for m in lista_mun:
    nome = m["nome"]
    geo_map[nome] = {
        "lat": float(m["latitude"]),
        "lon": float(m["longitude"]),
        "alt": float(m.get("altitude", 650.0))
    }

def processar_ano(ano):
    zip_path = Path(f"{ano}.zip")
    parquet_path = Path(f"data/clima_{ano}.parquet")

    print(f"\n" + "=" * 60)
    print(f" PROCESSANDO HISTÓRICO: ANO {ano} (COM QC ATIVADO)")
    print("=" * 60)

    if not zip_path.exists():
        print(f"[AVISO] Arquivo '{zip_path}' não encontrado. Pulando ano {ano}...")
        return
    if not parquet_path.exists():
        print(f"[AVISO] Arquivo '{parquet_path}' não encontrado. Pulando ano {ano}...")
        return

    # 2. Carregar parquet base
    df = pd.read_parquet(parquet_path)
    df["data"] = pd.to_datetime(df["data"]).dt.strftime("%Y-%m-%d")

    for col in ["temp_max", "temp_min", "chuva_mm", "umidade_media"]:
        df[col] = df[col].astype("float64")

    mapa_nomes = {normalizar_texto(nome): nome for nome in df["municipio"].unique()}

    # 3. Ler dados das estações INMET com QC
    dados_inmet_lista = []
    with zipfile.ZipFile(zip_path, "r") as z:
        arquivos_go = [n for n in z.namelist() if "_GO_" in n and n.upper().endswith(".CSV")]
        estacoes_dict = {}
        for arq in arquivos_go:
            codigo = re.findall(r'_([AM]\d{3})_', arq)
            chave = codigo[0] if codigo else arq
            if chave not in estacoes_dict or len(arq) > len(estacoes_dict[chave]):
                estacoes_dict[chave] = arq

        for nome_arq in estacoes_dict.values():
            partes = Path(nome_arq).stem.split("_")
            nome_cidade_arq = partes[4] if len(partes) > 4 else partes[-1]

            with z.open(nome_arq) as f:
                conteudo = io.TextIOWrapper(f, encoding="latin-1")
                nome_cabecalho = ""
                for _ in range(12):
                    linha = conteudo.readline()
                    if "ESTACAO;" in linha.upper() or "ESTAÇÃO;" in linha.upper():
                        partes_l = linha.split(";")
                        if len(partes_l) > 1:
                            nome_cabecalho = partes_l[1].strip()
                        break
                
                nome_estacao = nome_cabecalho if (nome_cabecalho and len(nome_cabecalho) > 2) else nome_cidade_arq
                conteudo.seek(0)
                
                df_est = pd.read_csv(
                    conteudo,
                    sep=";",
                    skiprows=8,
                    decimal=",",
                    na_values=["-9999", -9999, "-9999.0", "null", "", "NAN", "NaN"]
                )
                df_est.columns = [c.strip().upper() for c in df_est.columns]
                
                cols_data = [c for c in df_est.columns if "DATA" in c]
                cols_precip = [c for c in df_est.columns if "PRECIPITA" in c]
                cols_tmax = [c for c in df_est.columns if "TEMPERATURA MÁXIMA" in c or "TEMPERATURA MAXIMA" in c]
                cols_tmin = [c for c in df_est.columns if "TEMPERATURA MÍNIMA" in c or "TEMPERATURA MINIMA" in c]
                cols_temp = [c for c in df_est.columns if "BULBO SECO" in c or "TEMPERATURA DO AR" in c]
                cols_umid = [c for c in df_est.columns if "UMIDADE" in c or "HUMIDADE" in c]
                
                if not (cols_data and cols_precip and (cols_tmax or cols_temp)):
                    continue
                    
                c_data = cols_data[0]
                c_precip = cols_precip[0]
                c_tmax = cols_tmax[0] if cols_tmax else cols_temp[0]
                c_tmin = cols_tmin[0] if cols_tmin else cols_temp[0]
                c_umid = cols_umid[0] if cols_umid else None
                
                df_est["DATA"] = pd.to_datetime(df_est[c_data].astype(str).str.replace("/", "-"), errors="coerce").dt.strftime("%Y-%m-%d")
                df_est = df_est.dropna(subset=["DATA"])

                # ========================================================
                # CONTROLE DE QUALIDADE METEOROLÓGICO (QC ANTI-OUTLIER)
                # ========================================================
                df_est[c_tmin] = pd.to_numeric(df_est[c_tmin], errors='coerce')
                df_est[c_tmax] = pd.to_numeric(df_est[c_tmax], errors='coerce')
                datas_dt = pd.to_datetime(df_est["DATA"], errors='coerce')
                meses = datas_dt.dt.month

                # 1. No auge do verão (Dez a Março) é impossível mínima < 15°C em Goiás
                verao = meses.isin([12, 1, 2, 3])
                df_est.loc[verao & (df_est[c_tmin] < 15.0), c_tmin] = np.nan

                # 2. Piso geral absoluto físico (ruídos de sensor < 3.0°C)
                df_est.loc[df_est[c_tmin] < 3.0, c_tmin] = np.nan

                # 3. Baixada do Araguaia (São Miguel / Aruanã): clima quente constante
                # Trava para eliminar falhas instrumentais como os 9.6°C
                nome_est_upper = normalizar_texto(nome_estacao)
                if "ARAGUAIA" in nome_est_upper or "SAOMIGUEL" in nome_est_upper:
                    # Fora do inverno (Mai-Jul), nunca faz menos de 15°C
                    fora_inverno = ~meses.isin([5, 6, 7])
                    df_est.loc[fora_inverno & (df_est[c_tmin] < 15.0), c_tmin] = np.nan
                    # Mesmo no inverno, o vale do Araguaia não rompe 12.0°C
                    df_est.loc[df_est[c_tmin] < 12.0, c_tmin] = np.nan

                # 4. Trava física para máximas absurdas (ex: sensor travado em > 45°C)
                df_est.loc[df_est[c_tmax] > 44.0, c_tmax] = np.nan
                # ========================================================
                
                aggs = {
                    "tmax_inmet": (c_tmax, lambda s: s.max() if s.notna().any() else np.nan),
                    "tmin_inmet": (c_tmin, lambda s: s.min() if s.notna().any() else np.nan),
                    "precip_inmet": (c_precip, lambda s: s.sum() if s.notna().any() else np.nan)
                }
                if c_umid:
                    aggs["umid_inmet"] = (c_umid, lambda s: s.mean() if s.notna().any() else np.nan)
                else:
                    aggs["umid_inmet"] = (c_precip, lambda s: np.nan)
                    
                df_resumo = df_est.groupby("DATA").agg(**aggs).reset_index()
                df_resumo["estacao_nome"] = nome_estacao
                dados_inmet_lista.append(df_resumo)

    if not dados_inmet_lista:
        print(f"[ERRO] Nenhum dado de estação do INMET encontrado para {ano}.")
        return

    df_inmet = pd.concat(dados_inmet_lista, ignore_index=True)
    data_limite_inmet = df_inmet["DATA"].max()
    print(f"Dados INMET limpos e validados até: {data_limite_inmet}")

    # 4. Mapear estações
    estacoes_mapeadas = {}
    totais_inmet = {}

    for estacao_raw in df_inmet["estacao_nome"].unique():
        norm = normalizar_texto(estacao_raw)
        mun_match = mapa_nomes.get(norm)
        if not mun_match:
            for m_norm, m_real in mapa_nomes.items():
                if len(m_norm) >= 5 and (m_norm in norm or norm in m_norm):
                    mun_match = m_real
                    break
                    
        if mun_match and mun_match not in estacoes_mapeadas:
            estacoes_mapeadas[mun_match] = estacao_raw
            sub = df_inmet[df_inmet["estacao_nome"] == estacao_raw]
            totais_inmet[mun_match] = sub["precip_inmet"].dropna().sum()

    estacoes_ancoras = [m for m, total in totais_inmet.items() if total >= LIMIAR_MINIMO_CHUVA]
    mascara_datas_inmet = df["data"] <= data_limite_inmet

    # 5. ETAPA 1: Estações físicas (com fallback automático onde o QC limpou ruído)
    for mun in estacoes_mapeadas.keys():
        estacao_raw = estacoes_mapeadas[mun]
        sub = df_inmet[df_inmet["estacao_nome"] == estacao_raw]
        
        sub_dict_tmax = dict(zip(sub["DATA"], sub["tmax_inmet"]))
        sub_dict_tmin = dict(zip(sub["DATA"], sub["tmin_inmet"]))
        sub_dict_umid = dict(zip(sub["DATA"], sub["umid_inmet"]))
        sub_dict_prec = dict(zip(sub["DATA"], sub["precip_inmet"]))
        
        idx = (df["municipio"] == mun) & mascara_datas_inmet
        datas = df.loc[idx, "data"]
        
        # O fillna garante que, se o QC descartou um pico absurdo, a reanálise entra no lugar
        df.loc[idx, "temp_max"] = datas.map(sub_dict_tmax).fillna(df.loc[idx, "temp_max"]).round(1)
        df.loc[idx, "temp_min"] = datas.map(sub_dict_tmin).fillna(df.loc[idx, "temp_min"]).round(1)
        df.loc[idx, "umidade_media"] = datas.map(sub_dict_umid).fillna(df.loc[idx, "umidade_media"]).round(0)
        
        if mun in estacoes_ancoras:
            df.loc[idx, "chuva_mm"] = datas.map(sub_dict_prec).fillna(df.loc[idx, "chuva_mm"]).round(1)
            df.loc[idx, "fonte_dado"] = "INMET (Oficial)"
        else:
            lat_m, lon_m = geo_map[mun]["lat"], geo_map[mun]["lon"]
            ancora_prox = min(estacoes_ancoras, key=lambda a: calcular_haversine(lat_m, lon_m, geo_map[a]["lat"], geo_map[a]["lon"]))
            sub_anc = df[(df["municipio"] == ancora_prox) & mascara_datas_inmet]
            dict_anc = dict(zip(sub_anc["data"], sub_anc["chuva_mm"]))
            diff_alt = geo_map[mun]["alt"] - geo_map[ancora_prox]["alt"]
            fator_relevo = np.clip(1.0 + (diff_alt * 0.0002), 0.90, 1.15)
            df.loc[idx, "chuva_mm"] = (datas.map(dict_anc).fillna(0.0) * fator_relevo).round(1)
            df.loc[idx, "fonte_dado"] = "INMET (Termométrica) / Calibrado"

    # 6. ETAPA 2: Modelo Físico Contínuo para cidades sem estação
    cidades_restantes = [m for m in df["municipio"].unique() if m not in estacoes_mapeadas]
    todas_estacoes = list(estacoes_mapeadas.keys())

    for cid_alvo in cidades_restantes:
        if cid_alvo not in geo_map:
            continue
        
        lat_a, lon_a, alt_a = geo_map[cid_alvo]["lat"], geo_map[cid_alvo]["lon"], geo_map[cid_alvo]["alt"]
        
        menor_d = float("inf")
        est_prox = None
        for est in todas_estacoes:
            d = calcular_haversine(lat_a, lon_a, geo_map[est]["lat"], geo_map[est]["lon"])
            if d < menor_d:
                menor_d = d
                est_prox = est
                
        if not est_prox:
            continue

        idx_alvo = (df["municipio"] == cid_alvo) & mascara_datas_inmet
        idx_est = (df["municipio"] == est_prox) & mascara_datas_inmet
        datas_alvo = df.loc[idx_alvo, "data"]
        
        sub_ref = df[idx_est].set_index("data")
        tmax_ref = sub_ref["temp_max"].reindex(datas_alvo).values
        tmin_ref = sub_ref["temp_min"].reindex(datas_alvo).values
        umid_ref = sub_ref["umidade_media"].reindex(datas_alvo).values
        
        alt_ref = geo_map[est_prox]["alt"]
        diff_alt = alt_a - alt_ref
        
        # Mínima: resfriamento noturno por altitude
        delta_tmin = - (diff_alt * 0.0060)
        tmin_estimada = tmin_ref + delta_tmin
        
        # Máxima: física contínua por altitude
        if alt_a > 700.0:
            ajuste_plato = - ((alt_a - 700.0) / 100.0) * 0.75
        elif alt_a < 500.0:
            ajuste_plato = + ((500.0 - alt_a) / 100.0) * 0.60
        else:
            ajuste_plato = 0.0
            
        delta_tmax = - (diff_alt * 0.0075) + ajuste_plato
        tmax_estimada = tmax_ref + delta_tmax
        
        ajuste_umid = (diff_alt * 0.015)
        
        df.loc[idx_alvo, "temp_max"] = np.round(tmax_estimada, 1)
        df.loc[idx_alvo, "temp_min"] = np.round(tmin_estimada, 1)
        df.loc[idx_alvo, "umidade_media"] = np.round(umid_ref + ajuste_umid, 0).clip(10, 100)
        df.loc[idx_alvo, "fonte_dado"] = "INMET / Física Contínua Topográfica"

    # 7. Auditoria do ano
    print(f"\n--- AUDITORIA TÉRMICA ({ano}) ---")
    cidades_auditoria = [
        "São Miguel do Araguaia",
        "Goiânia",
        "Aparecida de Goiânia",
        "Anápolis",
        "Cristalina"
    ]
    for cid in cidades_auditoria:
        if cid in geo_map:
            sub_c = df[(df["municipio"] == cid) & mascara_datas_inmet]
            alt = geo_map[cid]["alt"]
            print(f"   {cid:<24} | Alt: {alt:>5.0f}m | T.Máx Média: {sub_c['temp_max'].mean():.1f} °C | T.Mín Média: {sub_c['temp_min'].mean():.1f} °C | Máx Abs: {sub_c['temp_max'].max():.1f} °C | Mín Abs: {sub_c['temp_min'].min():.1f} °C")

    # 8. Gravar Parquet
    df.to_parquet(parquet_path, index=False)
    print(f"[SUCESSO] Base do ano {ano} salva em: {parquet_path}")

if __name__ == "__main__":
    for ano in ANOS_HISTORICOS:
        processar_ano(ano)
    print("\n[CONCLUÍDO] Todos os anos históricos (2022-2025) foram calibrados e protegidos com sucesso!\n")