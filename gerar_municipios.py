import json
import os
import requests

def buscar_municipios_goias():
    print("Obtendo dados dos 246 municípios de Goiás via IBGE...")
    
    # API de malha municipal com centróides geográficos do IBGE
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/52/municipios"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    municipios_brutos = resp.json()
    
    # Buscar coordenadas da malha geográfica municipal
    # Usamos o endpoint de geolocalização do IBGE por município
    url_coordenadas = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/52?formato=application/vnd.geo+json&qualidade=intermediaria"
    
    # Alternativa direta: base centralizada dos municípios goianos
    url_lat_lon = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/municipios.csv"
    import pandas as pd
    df_coords = pd.read_csv(url_lat_lon)
    df_go = df_coords[df_coords["codigo_uf"] == 52]
    
    lista_municipios = []
    for _, row in df_go.iterrows():
        lista_municipios.append({
            "codigo_ibge": int(row["codigo_ibge"]),
            "nome": row["nome"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"])
        })
    
    os.makedirs("data", exist_ok=True)
    caminho_saida = os.path.join("data", "municipios_go.json")
    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(lista_municipios, f, ensure_ascii=False, indent=2)
        
    print(f"Sucesso! {len(lista_municipios)} municípios salvos em {caminho_saida}")

if __name__ == "__main__":
    buscar_municipios_goias()