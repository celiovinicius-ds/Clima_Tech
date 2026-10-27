import sqlite3
import pandas as pd

def obter_conexao(caminho_banco="banco_oraculo.db"):
    """
    Cria ou conecta ao banco de dados SQLite local.
    """
    return sqlite3.connect(caminho_banco)

def carregar_dados(df, nome_tabela, conexao, modo="append"):
    """
    Grava o DataFrame na tabela correspondente.
    Modos comuns: 'append' (acrescenta registros) ou 'replace' (recria tabela).
    """
    df.to_sql(name=nome_tabela, con=conexao, if_exists=modo, index=False)