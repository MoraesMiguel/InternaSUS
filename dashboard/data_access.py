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


def com_estabelecimento(fato: pd.DataFrame) -> pd.DataFrame:
    """Junta uma tabela fato de grão estabelecimento (coluna cnes) com
    dim_estabelecimento (tipo_unidade, esfera_administrativa, tipo_gestao,
    natureza_juridica etc.).

    `cod_mun` já vem como atributo degenerado nas fatos de grão estabelecimento
    (fato_infra_estabelecimento, fato_recursos_estabelecimento,
    fato_leitos_estabelecimento) — descartamos o `cod_mun` da dimensão pra não
    duplicar a coluna em `cod_mun_x`/`cod_mun_y` (validado: os dois sempre
    concordam, ver docs/docs/Resumo_Evolucao.md)."""
    dim = carregar("dim_estabelecimento").drop(columns=["cod_mun"])
    return fato.merge(dim, on="cnes", how="left")


def com_leito(fato: pd.DataFrame) -> pd.DataFrame:
    """Junta uma tabela fato com colunas (tp_leito, codleito) com dim_leito
    (tipo_leito_desc, codigo_leito_desc)."""
    return fato.merge(carregar("dim_leito"), on=["tp_leito", "codleito"], how="left")


def com_diagnostico(fato: pd.DataFrame) -> pd.DataFrame:
    """Junta uma tabela fato com coluna diagnostico_principal (CID-10) com
    dim_diagnostico (descricao, descricao_categoria, descricao_grupo,
    descricao_capitulo)."""
    return fato.merge(
        carregar("dim_diagnostico"),
        left_on="diagnostico_principal",
        right_on="codigo",
        how="left",
    )


def opcoes(df: pd.DataFrame, coluna: str) -> list:
    """Valores distintos não-nulos de `coluna`, ordenados — para popular
    filtros (st.multiselect/st.selectbox) sem repetir o mesmo boilerplate
    em cada página."""
    return sorted(df[coluna].dropna().unique().tolist())


def filtrar(df: pd.DataFrame, coluna: str, selecionados: list) -> pd.DataFrame:
    """Aplica um filtro de multiselect: sem seleção = sem filtro (mostra tudo)."""
    return df[df[coluna].isin(selecionados)] if selecionados else df
