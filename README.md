🌦️ ClimaTech - Monitoramento Climático de Goiás

🚀 Projeto em Desenvolvimento Ativo

Pipeline ETL automatizado com ingestão diária e dashboard analítico para monitoramento meteorológico dos 246 municípios do estado de Goiás.

🌐 Acesso ao Dashboard

O painel já está online e pode ser acessado de qualquer navegador (computador ou celular):

🔗 https://climatec.streamlit.app/

📌 Sobre o Projeto

O ClimaTech é uma plataforma focada em engenharia e ciência de dados climáticos. O pipeline extrai dados diários históricos e recentes de todos os 246 municípios goianos via API da Open-Meteo (reanálise ERA5), persiste as informações em arquivos colunares de alta performance (Apache Parquet) e disponibiliza gráficos interativos em um dashboard Streamlit.

⚙️ Funcionalidades Principais:

🗺️ Cobertura Total: Dados consolidados para os 246 municípios de Goiás.

⚡ Formato Colunar Parquet: Alta compressão e leitura rápida de séries históricas.

🤖 Automação Diária (CI/CD): Robô via GitHub Actions agendado para rodar todos os dias às 06:00 (horário de Brasília) buscando os dados do dia anterior.

📊 Visualização Interativa: Gráficos de temperatura, precipitação e umidade desenvolvidos em Plotly.

🛠️ Tecnologias Utilizadas

Linguagem: Python 3.11+

Manipulação de Dados: Pandas, NumPy

Armazenamento: PyArrow (Apache Parquet)

Visualização: Streamlit, Plotly

Orquestração & Automação: GitHub Actions (Cron Jobs)

Fonte de Dados: Open-Meteo Archive API

📂 Estrutura do Projeto

Clima_Tech/
├── .github/
│   └── workflows/
│       └── atualizar_clima.yml   # Automação agendada diária (06:00 BRT)
├── app/
│   └── dashboard.py              # Interface visual e gráficos Streamlit
├── data/
│   ├── municipios_go.json        # Coordenadas e códigos IBGE das 246 cidades
│   └── clima_2026.parquet        # Base histórica consolidada em Parquet
├── etl/
│   ├── extract.py                # Extração histórica
│   ├── transform.py              # Limpeza e transformação
│   ├── load.py                   # Carga e persistência em Parquet
│   └── atualizar_dia.py          # Script de ingestão incremental diária
├── requirements.txt              # Bibliotecas necessárias
└── README.md                     # Documentação do projeto


🎯 Próximos Passos (Roadmap)

[x] Coleta inicial e limpeza dos 246 municípios.

[x] Construção do dashboard com Streamlit e filtros temporais.

[x] Automação diária com GitHub Actions.

[ ] Extração direta das medições oficiais de umidade relativa (relative_humidity_2m_mean).

[ ] Ampliação do histórico para os anos de 2025 e anteriores.

[ ] Desenvolvimento de modelos de Machine Learning para predição climática regional.

👨‍💻 Autor

Desenvolvido por Célio Vinícius

GitHub: @celiovinicius-ds
