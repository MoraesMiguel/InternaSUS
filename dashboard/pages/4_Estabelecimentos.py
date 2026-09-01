from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_estabelecimento, com_municipio, filtrar, opcoes

st.set_page_config(page_title="Estabelecimentos", page_icon="🏨", layout="wide")
st.title("Perfil dos estabelecimentos de saúde")

estab = com_municipio(carregar("dim_estabelecimento"))

col_f1, col_f2, col_f3 = st.columns(3)
f_tipo_unidade = col_f1.multiselect(
    "Tipo de unidade", opcoes(estab, "tipo_unidade_desc"), key="estab_tipo_unidade"
)
f_esfera = col_f2.multiselect(
    "Esfera administrativa", opcoes(estab, "esfera_administrativa_desc"), key="estab_esfera"
)
f_gestao = col_f3.multiselect("Tipo de gestão", opcoes(estab, "tipo_gestao_desc"), key="estab_gestao")

estab_f = filtrar(estab, "tipo_unidade_desc", f_tipo_unidade)
estab_f = filtrar(estab_f, "esfera_administrativa_desc", f_esfera)
estab_f = filtrar(estab_f, "tipo_gestao_desc", f_gestao)

st.metric("Estabelecimentos (após filtro)", f"{len(estab_f):,.0f}")

st.subheader("Estabelecimentos por natureza jurídica")
st.caption("As 10 naturezas jurídicas mais comuns entre os estabelecimentos filtrados.")
natureza_counts = estab_f["natureza_juridica_desc"].value_counts().head(10)
st.bar_chart(
    natureza_counts.rename_axis("natureza_juridica_desc").reset_index(name="estabelecimentos"),
    x="natureza_juridica_desc",
    y="estabelecimentos",
    sort="-estabelecimentos",
)

st.subheader("Profissionais e leitos por tipo de unidade")
st.caption(
    "Lado a lado pra comparar onde a rede concentra gente (profissionais) e onde concentra "
    "capacidade de internação (leitos) — nem sempre é o mesmo tipo de unidade."
)
recursos = com_municipio(com_estabelecimento(carregar("fato_recursos_estabelecimento")))
recursos_f = filtrar(recursos, "tipo_unidade_desc", f_tipo_unidade)
recursos_f = filtrar(recursos_f, "esfera_administrativa_desc", f_esfera)
recursos_f = filtrar(recursos_f, "tipo_gestao_desc", f_gestao)

col1, col2 = st.columns(2)
with col1:
    prof_por_tipo = (
        recursos_f.groupby("tipo_unidade_desc")["total_profissionais"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .rename_axis("tipo_unidade_desc")
        .reset_index(name="total_profissionais")
    )
    st.bar_chart(
        prof_por_tipo,
        x="tipo_unidade_desc",
        y="total_profissionais",
        sort="-total_profissionais",
        horizontal=True,
    )
with col2:
    leitos_por_tipo_estab = (
        recursos_f.groupby("tipo_unidade_desc")["total_leitos"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .rename_axis("tipo_unidade_desc")
        .reset_index(name="total_leitos")
    )
    st.bar_chart(
        leitos_por_tipo_estab,
        x="tipo_unidade_desc",
        y="total_leitos",
        sort="-total_leitos",
        horizontal=True,
    )

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("Top 15 municípios por nº de estabelecimentos")
    top_mun_estab = estab_f.groupby("nome_mun").size().sort_values(ascending=False).head(15)
    st.bar_chart(top_mun_estab)
with col2:
    st.subheader("Top 10 tipos de unidade")
    top_tipo = estab_f["tipo_unidade_desc"].value_counts().head(10)
    st.bar_chart(top_tipo)

st.subheader("Detalhe por município")
municipios_estab = st.multiselect("Filtrar município(s)", opcoes(estab_f, "nome_mun"), key="mun_estab")
tabela_estab = filtrar(estab_f, "nome_mun", municipios_estab)
st.dataframe(
    tabela_estab.groupby("nome_mun")
    .agg(estabelecimentos=("cnes", "count"))
    .reset_index()
    .sort_values("estabelecimentos", ascending=False),
    use_container_width=True,
    hide_index=True,
)
