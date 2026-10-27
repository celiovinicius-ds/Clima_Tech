import requests
import time

def extrair_municipios_ibge(uf_id=52):
    """
    Busca a lista completa de municípios de Goiás.
    Nota: Se a API padrão não retornar lat/lon, integramos com a base de coordenadas do IBGE na etapa de transformação.
    """
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf_id}/municipios"
    resposta = requests.get(url, timeout=15)
    resposta.raise_for_status()
    return resposta.json()

def extrair_clima_lote(lista_municipios, data_inicio, data_fim):
    """
    Faz um loop pelos municípios puxando o histórico climático completo da Open-Meteo.
    """
    historico_completo = []
    
    for mun in lista_municipios:
        # Pega as coordenadas (exemplo de chaves, ajustamos conforme o JSON real na transformação)
        lat = mun.get('latitude') 
        lon = mun.get('longitude')
        nome = mun.get('nome')
        
        print(f"Extraindo dados de {nome}...")
        
        url = "https://archive-api.open-meteo.com/v1/archive"
        parametros = {
            "latitude": lat,
            "longitude": lon,
            "start_date": data_inicio,
            "end_date": data_fim,
            "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
            "timezone": "America/Sao_Paulo"
        }
        
        try:
            resposta = requests.get(url, params=parametros, timeout=20)
            resposta.raise_for_status()
            dados = resposta.json()
            dados['municipio'] = nome # Anexa o nome para não perdermos a referência
            historico_completo.append(dados)
        except Exception as e:
            print(f"Erro ao extrair {nome}: {e}")
            
        # Pausa de 1 segundo para não sobrecarregar a API (Rate Limit)
        time.sleep(1)
        
    return historico_completo