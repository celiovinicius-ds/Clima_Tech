from etl.extract import extrair_municipios_ibge, extrair_clima_lote
from etl.transform import transformar_municipios, transformar_clima_lote
from etl.load import obter_conexao, carregar_dados

def executar_etl():
    print("1. A extrair municípios do IBGE...")
    dados_ibge = extrair_municipios_ibge(uf_id=52)
    df_municipios = transformar_municipios(dados_ibge)
    
    conexao = obter_conexao()
    carregar_dados(df_municipios, "municipios", conexao, modo="replace")
    print(f"Municípios gravados: {len(df_municipios)}")
    
    # Lista de teste com coordenadas para validar o motor em lote
    municipios_amostra = [
        {"nome": "Goiânia", "latitude": -16.6869, "longitude": -49.2648},
        {"nome": "Aparecida de Goiânia", "latitude": -16.8239, "longitude": -49.2439},
        {"nome": "Anápolis", "latitude": -16.3268, "longitude": -48.9534}
    ]
    
    print("2. A extrair histórico climático da amostra...")
    dados_clima = extrair_clima_lote(
        lista_municipios=municipios_amostra,
        data_inicio="2024-01-01",
        data_fim="2024-01-31"
    )
    
    print("3. A transformar dados climáticos...")
    df_clima = transformar_clima_lote(dados_clima)
    
    print("4. A carregar no banco de dados...")
    carregar_dados(df_clima, "clima_historico", conexao, modo="replace")
    
    conexao.close()
    print("Processo concluído com sucesso!")

if __name__ == "__main__":
    executar_etl()