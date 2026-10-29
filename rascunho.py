import pandas as pd
from etl.transform import aplicar_calibracao

print("Lendo a base bruta de todas as cidades de 2026...")
df = pd.read_parquet("data/clima_2026.parquet")

print("Aplicando calibração oficial para todo o estado...")
df_calibrado = aplicar_calibracao(df)

df_calibrado.to_parquet("data/clima_2026.parquet", index=False)
print("Sucesso! Todas as cidades reescritas e calibradas.")