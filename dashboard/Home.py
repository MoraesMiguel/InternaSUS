from pathlib import Path
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_access import carregar

st.set_page_config(page_title="InternaSUS", page_icon="🏥", layout="wide")

st.title("InternaSUS — Inteligência e Pressão Hospitalar em São Paulo")
st.markdown(
    """
O InternaSUS integra dados públicos do **CNES**, **SIA/SUS**, **SIH/SUS** e **IBGE**
para apoiar gestores de saúde pública na identificação de:

- **Filas e gargalos** de exames, cirurgias e serviços especializados
- **Desigualdade regional** de acesso à rede de saúde
- **Falta ou má distribuição de profissionais** especializados

Este é um **MVP**: os dados abaixo vêm da camada **Gold** local
(`data/gold/`), gerada por `internasus.processing.silver` e
`internasus.processing.gold`. A leitura direto do Object Storage / Autonomous
Database do OCI ainda não está conectada a este dashboard.
"""
)

dim = carregar("dim_municipio")
gargalos = carregar("fato_filas_gargalos")
recursos = carregar("fato_recursos_estabelecimento")
ano_ref = pd.to_datetime(gargalos["data_referencia"].iloc[0]).year if len(gargalos) else "-"

col1, col2, col3 = st.columns(3)
col1.metric("Municípios cobertos", len(dim))
col2.metric("Ano de referência (SIA/SIH) / competência (CNES)", ano_ref)
col3.metric("Estabelecimentos de saúde (CNES) mapeados", len(recursos))

st.info(
    "O bloco de **Atenção Primária** (cobertura de UBS/Estratégia Saúde da Família) "
    "não está disponível: depende do SISAB/SIAPS, que ainda não foi ingerido no projeto."
)

st.markdown(
    "Use o menu à esquerda para navegar: **Filas e Gargalos**, **Desigualdade Regional** e **Profissionais**."
)
