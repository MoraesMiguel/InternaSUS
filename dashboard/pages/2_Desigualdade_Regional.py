from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_municipio

st.set_page_config(page_title="Desigualdade Regional", page_icon="🗺️", layout="wide")
st.title("Desigualdade regional de acesso")

df = com_municipio(carregar("fato_desigualdade_regional"))

col1, col2, col3 = st.columns(3)
col1.metric(
    "Município com maior % de evasão",
    df.loc[df["pct_evasao"].idxmax(), "nome_mun"] if df["pct_evasao"].notna().any() else "-",
)
col2.metric(
    "Polo com maior % de pressão externa",
    df.loc[df["pct_pressao_externa"].idxmax(), "nome_mun"]
    if df["pct_pressao_externa"].notna().any()
    else "-",
)
col3.metric("Municípios analisados", len(df))

st.subheader("Top 15 municípios exportadores de pacientes (% de evasão hospitalar)")
top_evasao = df.sort_values("pct_evasao", ascending=False).dropna(subset=["pct_evasao"]).head(15)
st.bar_chart(top_evasao.set_index("nome_mun")["pct_evasao"])

st.subheader("15 municípios com menor infraestrutura per capita (leitos por mil hab.)")
bottom_leitos = (
    df[df["leitos_por_mil_hab"].notna()].sort_values("leitos_por_mil_hab", ascending=True).head(15)
)
st.bar_chart(bottom_leitos.set_index("nome_mun")["leitos_por_mil_hab"])

st.subheader("Detalhe por município")
municipios = st.multiselect("Filtrar município(s)", sorted(df["nome_mun"].dropna().unique()))
tabela = df[df["nome_mun"].isin(municipios)] if municipios else df
st.dataframe(
    tabela[
        [
            "nome_mun",
            "populacao_ref",
            "total_internacoes_residentes",
            "evasao_hospitalar",
            "pct_evasao",
            "total_atendimentos_polo",
            "pacientes_externos",
            "pct_pressao_externa",
            "leitos_total",
            "equipamentos_total",
            "servicos_total",
            "leitos_por_mil_hab",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)
