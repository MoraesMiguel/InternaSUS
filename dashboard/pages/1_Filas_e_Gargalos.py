from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_municipio

st.set_page_config(page_title="Filas e Gargalos", page_icon="⏳", layout="wide")
st.title("Filas para especialistas, exames e cirurgias")

df = com_municipio(carregar("fato_filas_gargalos"))

col1, col2, col3 = st.columns(3)
col1.metric("Exames realizados (ano de referência)", f"{df['exames_realizados'].sum():,.0f}")
col2.metric(
    "Municípios sem equipamento próprio (gargalo)",
    int((df["situacao_exames"] == "Sem equipamento próprio (gargalo)").sum()),
)
col3.metric(
    "Municípios com equipamento ocioso", int((df["situacao_exames"] == "Equipamento ocioso").sum())
)

st.subheader("Top 15 municípios por exames realizados por equipamento de imagem")
top_exames = (
    df.sort_values("exames_por_equipamento", ascending=False)
    .dropna(subset=["exames_por_equipamento"])
    .head(15)
)
st.bar_chart(top_exames.set_index("nome_mun")["exames_por_equipamento"])

st.subheader("Top 15 municípios por taxa de ocupação estimada de leitos cirúrgicos")
top_leitos = (
    df.sort_values("taxa_ocupacao_leitos_pct", ascending=False)
    .dropna(subset=["taxa_ocupacao_leitos_pct"])
    .head(15)
)
st.bar_chart(top_leitos.set_index("nome_mun")["taxa_ocupacao_leitos_pct"])

st.subheader("Detalhe por município")
municipios = st.multiselect("Filtrar município(s)", sorted(df["nome_mun"].dropna().unique()))
tabela = df[df["nome_mun"].isin(municipios)] if municipios else df
st.dataframe(
    tabela[
        [
            "nome_mun",
            "populacao_ref",
            "equipamentos_imagem",
            "exames_realizados",
            "exames_por_mil_hab",
            "exames_por_equipamento",
            "situacao_exames",
            "leitos_cirurgicos",
            "cirurgias_realizadas",
            "taxa_ocupacao_leitos_pct",
            "servicos_especializados_cadastrados",
            "producao_ambulatorial",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)
