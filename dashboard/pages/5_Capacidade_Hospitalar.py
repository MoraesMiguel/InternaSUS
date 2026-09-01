from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_leito, com_municipio, filtrar, opcoes

st.set_page_config(page_title="Capacidade Hospitalar", page_icon="🛏️", layout="wide")
st.title("Capacidade hospitalar (leitos)")

leitos = com_municipio(com_leito(carregar("fato_leitos_estabelecimento")))

f_tipo_leito = st.multiselect("Tipo de leito", opcoes(leitos, "tipo_leito_desc"), key="leito_tipo")
leitos_f = filtrar(leitos, "tipo_leito_desc", f_tipo_leito)

col1, col2, col3 = st.columns(3)
col1.metric("Leitos existentes (após filtro)", f"{leitos_f['qtd_leitos_existentes'].sum():,.0f}")
col2.metric("Leitos SUS", f"{leitos_f['qtd_leitos_sus'].sum():,.0f}")
col3.metric("Estabelecimentos com leito", f"{leitos_f['cnes'].nunique():,.0f}")

st.subheader("Leitos complementares (UTI) por mil hab.")
st.caption(
    "Leito complementar (UTI, unidade de cuidados intermediários etc.) é o recurso mais "
    "citado em qualquer crise de saúde — merece ranking próprio, não uma linha a mais num "
    "gráfico com outras 6 categorias."
)
dim_mun = carregar("dim_municipio")
uti = leitos[leitos["tp_leito"] == "3"].groupby("cod_mun")["qtd_leitos_existentes"].sum().reset_index()
uti = dim_mun.merge(uti, on="cod_mun", how="left").fillna({"qtd_leitos_existentes": 0})
uti["uti_por_mil_hab"] = uti["qtd_leitos_existentes"] * 1000 / uti["populacao_ref"]
top_uti = uti[uti["populacao_ref"] > 0].nlargest(15, "uti_por_mil_hab")
st.bar_chart(top_uti.set_index("nome_mun")["uti_por_mil_hab"])

st.subheader("% de leitos SUS sobre o total existente, por município")
st.caption("A diferença entre 'leito que existe' e 'leito que o SUS pode de fato usar'.")
sus_pct = leitos_f.groupby("nome_mun").agg(
    existentes=("qtd_leitos_existentes", "sum"), sus=("qtd_leitos_sus", "sum")
)
sus_pct = sus_pct[sus_pct["existentes"] >= 10]
sus_pct["pct_sus"] = sus_pct["sus"] * 100 / sus_pct["existentes"]
st.bar_chart(sus_pct["pct_sus"].sort_values().head(15))
st.caption("Os 15 municípios com menor % SUS, entre os que têm pelo menos 10 leitos existentes.")

st.subheader("Mix de especialidade de leito nos 10 municípios mais populosos")
st.caption("Compara como os grandes centros distribuem a capacidade entre tipos de leito.")
maiores = dim_mun.nlargest(10, "populacao_ref")["cod_mun"]
mix_grandes = leitos[leitos["cod_mun"].isin(maiores)]
mix_grandes_agg = (
    mix_grandes.groupby(["nome_mun", "tipo_leito_desc"])["qtd_leitos_existentes"].sum().reset_index()
)
st.bar_chart(
    mix_grandes_agg, x="nome_mun", y="qtd_leitos_existentes", color="tipo_leito_desc", stack="normalize"
)

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("Top 15 municípios por leitos existentes")
    top_mun_leitos = (
        leitos_f.groupby("nome_mun")["qtd_leitos_existentes"].sum().sort_values(ascending=False).head(15)
    )
    st.bar_chart(top_mun_leitos)
with col2:
    st.subheader("Leitos por tipo (estado)")
    leitos_por_tipo = (
        leitos_f.groupby("tipo_leito_desc")["qtd_leitos_existentes"].sum().sort_values(ascending=False)
    )
    st.bar_chart(leitos_por_tipo)

st.subheader("Detalhe por município")
municipios_leitos = st.multiselect("Filtrar município(s)", opcoes(leitos_f, "nome_mun"), key="mun_leitos")
tabela_leitos = filtrar(leitos_f, "nome_mun", municipios_leitos)
st.dataframe(
    tabela_leitos.groupby(["nome_mun", "tipo_leito_desc"])
    .agg(
        leitos_existentes=("qtd_leitos_existentes", "sum"),
        leitos_sus=("qtd_leitos_sus", "sum"),
    )
    .reset_index()
    .sort_values("leitos_existentes", ascending=False),
    use_container_width=True,
    hide_index=True,
)
