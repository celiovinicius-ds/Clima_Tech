import os
import pandas as pd

def salvar_em_parquet(df, ano=2026):
    """
    Grava os dados consolidados em formato colunar Parquet de alta performance.
    """
    if df.empty:
        print("[AVISO] Nenhum dado para salvar.")
        return
        
    os.makedirs("data", exist_ok=True)
    caminho_arquivo = os.path.join("data", f"clima_{ano}.parquet")
    
    # Salva com compressão snappy
    df.to_parquet(caminho_arquivo, index=False, engine="pyarrow")
    tamanho_mb = os.path.getsize(caminho_arquivo) / (1024 * 1024)
    print(f"[SUCESSO] Dados salvos em '{caminho_arquivo}' ({tamanho_mb:.2f} MB)")