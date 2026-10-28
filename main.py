import json
import os
import time
from etl.extract import extrair_clima_ano
from etl.transform import transformar_dados_clima
from etl.load import salvar_em_parquet

def executar_pipeline(ano=2026, limite_teste=None):
    caminho_municipios = os.path.join("data", "municipios_go.json")
    if not os.path.exists(caminho_municipios):
        print("Arquivo de municípios não encontrado. Execute gerar_municipios.py primeiro.")
        return

    with open(caminho_municipios, "r", encoding="utf-8") as f:
        municipios = json.load(f)

    if limite_teste:
        municipios = municipios[:limite_teste]

    total = len(municipios)
    print(f"Iniciando pipeline ClimaTech | Ano: {ano} | Total de municípios: {total}")

    respostas = []
    for i, mun in enumerate(municipios, 1):
        print(f"[{i}/{total}] Extraindo {mun['nome']}...")
        dados = extrair_clima_ano(
            codigo_ibge=mun["codigo_ibge"],
            nome_municipio=mun["nome"],
            lat=mun["latitude"],
            lon=mun["longitude"],
            ano=ano
        )
        if dados:
            respostas.append(dados)
        
        # Pausa de 0.8s para respeitar as diretrizes da Open-Meteo
        time.sleep(0.8)

    print("Transformando dados e gerando features...")
    df_transformado = transformar_dados_clima(respostas)

    print("Gravando dados processados em Parquet...")
    salvar_em_parquet(df_transformado, ano=ano)
    print("Pipeline de 2026 finalizado!")

if __name__ == "__main__":
    # Para validar sem gastar chamadas, você pode rodar executar_pipeline(ano=2026, limite_teste=5)
    executar_pipeline(ano=2026)