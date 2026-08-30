"""Acesso aos dados da camada Gold (data/gold/) para o dashboard Streamlit.

MVP: lê os parquets locais gerados por internasus.processing.gold. A leitura
direto do bucket Gold no OCI (ou de um Autonomous Database carregado a partir
dele) fica para uma próxima iteração.
"""

import pandas as pd
import streamlit as st

from internasus.config import GOLD_DATA_DIR


@st.cache_data
def carregar(nome_tabela: str) -> pd.DataFrame:
    """Lê data/gold/<nome_tabela>.parquet (ex.: 'dim_municipio', 'fato_filas_gargalos')."""
    return pd.read_parquet(GOLD_DATA_DIR / f"{nome_tabela}.parquet")


def com_municipio(fato: pd.DataFrame) -> pd.DataFrame:
    """Junta uma tabela fato de grão município (coluna cod_mun) com dim_municipio
    (nome_mun, populacao_ref, microrregiao)."""
    return fato.merge(carregar("dim_municipio"), on="cod_mun", how="left")
