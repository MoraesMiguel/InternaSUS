from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_municipio

st.set_page_config(page_title="Profissionais", page_icon="🩺", layout="wide")
st.title("Falta ou má distribuição de profissionais especializados")

df = com_municipio(carregar("fato_profissionais"))

col1, col2, col3 = st.columns(3)
col1.metric("Médicos cadastrados (CBO 225%)", f"{df['medicos'].sum():,.0f}")
col2.metric("Enfermeiros cadastrados (CBO 2235%)", f"{df['enfermeiros'].sum():,.0f}")
col3.metric("Municípios sem nenhum médico", int((df["medicos"] == 0).sum()))

st.subheader("15 municípios com menor densidade de médicos por mil habitantes")
bottom_medicos = df.sort_values("medicos_por_mil_hab", ascending=True).head(15)
st.bar_chart(bottom_medicos.set_index("nome_mun")["medicos_por_mil_hab"])

st.subheader("Top 15 municípios por demanda de alta complexidade por especialista")
top_demanda = (
    df.sort_values("demanda_por_especialista", ascending=False)
    .dropna(subset=["demanda_por_especialista"])
    .head(15)
)
st.bar_chart(top_demanda.set_index("nome_mun")["demanda_por_especialista"])

st.subheader("Detalhe por município")
municipios = st.multiselect("Filtrar município(s)", sorted(df["nome_mun"].dropna().unique()))
tabela = df[df["nome_mun"].isin(municipios)] if municipios else df
st.dataframe(
    tabela[
        [
            "nome_mun",
            "populacao_ref",
            "medicos",
            "enfermeiros",
            "medicos_por_mil_hab",
            "enf_por_mil_hab",
            "producao_alta_complexidade",
            "cirurgias",
            "demanda_alta_complexidade",
            "demanda_por_especialista",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("Estabelecimentos com equipamento de imagem sem especialista vinculado")
infra = carregar("fato_infra_estabelecimento").merge(
    carregar("dim_municipio")[["cod_mun", "nome_mun"]], on="cod_mun", how="left"
)
ociosos = infra[infra["status_capacidade"] == "Infra Ociosa (Falta RH)"]
st.metric("Estabelecimentos com infra ociosa por falta de RH", len(ociosos))
st.dataframe(
    infra.sort_values("qtd_equipamentos_imagem", ascending=False).head(50)[
        [
            "nome_mun",
            "cnes",
            "qtd_equipamentos_imagem",
            "especialistas_vinculados",
            "status_capacidade",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("Recursos por estabelecimento (profissionais, leitos, equipamentos, serviços)")
st.caption(
    "Cada linha é um estabelecimento (CNES). As colunas 'por mil hab.' relativizam os "
    "recursos daquele estabelecimento pela população total do município onde ele fica — "
    "clique numa coluna 'por mil hab.' pra ordenar e achar estabelecimentos com pouco "
    "recurso perto do tamanho da população local. Não há um limiar fixo de 'pouco' — "
    "a régua fica a critério de quem está analisando."
)
recursos = com_municipio(carregar("fato_recursos_estabelecimento"))
municipios_recursos = st.multiselect(
    "Filtrar município(s)",
    sorted(recursos["nome_mun"].dropna().unique()),
    key="municipios_recursos",
)
tabela_recursos = (
    recursos[recursos["nome_mun"].isin(municipios_recursos)] if municipios_recursos else recursos
)
st.dataframe(
    tabela_recursos[
        [
            "nome_mun",
            "cnes",
            "populacao_municipio",
            "total_profissionais",
            "medicos",
            "enfermeiros",
            "total_leitos",
            "total_equipamentos",
            "total_servicos_especializados",
            "profissionais_por_mil_hab_municipio",
            "leitos_por_mil_hab_municipio",
            "equipamentos_por_mil_hab_municipio",
            "servicos_por_mil_hab_municipio",
        ]
    ].sort_values("profissionais_por_mil_hab_municipio"),
    use_container_width=True,
    hide_index=True,
)
