from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_estabelecimento, com_municipio, filtrar, opcoes

st.set_page_config(page_title="Profissionais", page_icon="🩺", layout="wide")
st.title("Falta ou má distribuição de profissionais especializados")

df = com_municipio(carregar("fato_profissionais"))

col1, col2, col3 = st.columns(3)
col1.metric("Médicos cadastrados (CBO 225%)", f"{df['medicos'].sum():,.0f}")
col2.metric("Enfermeiros cadastrados (CBO 2235%)", f"{df['enfermeiros'].sum():,.0f}")
col3.metric("Municípios sem nenhum médico", int((df["medicos"] == 0).sum()))

st.subheader("Quadrante de déficit: densidade de médicos × demanda de alta complexidade")
st.caption(
    "Cruza os dois rankings que hoje ficam em gráficos separados. Poucos médicos e pouca "
    "demanda não é urgente; poucos médicos e muita demanda, é — o quadrante 'Déficit crítico' "
    "aponta direto pra onde priorizar. A mediana que define os quadrantes é sempre calculada "
    "sobre o estado inteiro, mesmo com o filtro de município aplicado."
)
quad_base = df.dropna(subset=["medicos_por_mil_hab", "demanda_por_especialista"]).copy()
med_medicos = quad_base["medicos_por_mil_hab"].median()
med_demanda = quad_base["demanda_por_especialista"].median()

municipios_quad = st.multiselect(
    "Filtrar município(s)", opcoes(quad_base, "nome_mun"), key="municipios_quadrante"
)
quad = filtrar(quad_base, "nome_mun", municipios_quad).copy()


def _quadrante(row: object) -> str:
    baixa_densidade = row["medicos_por_mil_hab"] <= med_medicos
    alta_demanda = row["demanda_por_especialista"] > med_demanda
    if baixa_densidade and alta_demanda:
        return "Déficit crítico"
    if not baixa_densidade and not alta_demanda:
        return "Confortável"
    return "Intermediário"


quad["quadrante"] = quad.apply(_quadrante, axis=1)
st.scatter_chart(
    quad,
    x="medicos_por_mil_hab",
    y="demanda_por_especialista",
    color="quadrante",
    x_label="Médicos / mil hab.",
    y_label="Demanda de alta complexidade por especialista",
)

st.divider()
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
infra = com_municipio(com_estabelecimento(carregar("fato_infra_estabelecimento")))

col_f1, col_f2 = st.columns(2)
f_tipo_unidade_infra = col_f1.multiselect(
    "Tipo de unidade", opcoes(infra, "tipo_unidade_desc"), key="infra_tipo_unidade"
)
f_esfera_infra = col_f2.multiselect(
    "Esfera administrativa", opcoes(infra, "esfera_administrativa_desc"), key="infra_esfera"
)
infra_f = filtrar(infra, "tipo_unidade_desc", f_tipo_unidade_infra)
infra_f = filtrar(infra_f, "esfera_administrativa_desc", f_esfera_infra)

ociosos = infra_f[infra_f["status_capacidade"] == "Infra Ociosa (Falta RH)"]
st.metric("Estabelecimentos com infra ociosa por falta de RH", len(ociosos))
st.dataframe(
    infra_f.sort_values("qtd_equipamentos_imagem", ascending=False).head(50)[
        [
            "nome_mun",
            "cnes",
            "tipo_unidade_desc",
            "esfera_administrativa_desc",
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
recursos = com_municipio(com_estabelecimento(carregar("fato_recursos_estabelecimento")))

col_f1, col_f2, col_f3 = st.columns(3)
f_tipo_unidade_rec = col_f1.multiselect(
    "Tipo de unidade", opcoes(recursos, "tipo_unidade_desc"), key="recursos_tipo_unidade"
)
f_esfera_rec = col_f2.multiselect(
    "Esfera administrativa", opcoes(recursos, "esfera_administrativa_desc"), key="recursos_esfera"
)
f_gestao_rec = col_f3.multiselect(
    "Tipo de gestão", opcoes(recursos, "tipo_gestao_desc"), key="recursos_gestao"
)
recursos_f = filtrar(recursos, "tipo_unidade_desc", f_tipo_unidade_rec)
recursos_f = filtrar(recursos_f, "esfera_administrativa_desc", f_esfera_rec)
recursos_f = filtrar(recursos_f, "tipo_gestao_desc", f_gestao_rec)

municipios_recursos = st.multiselect(
    "Filtrar município(s)",
    opcoes(recursos_f, "nome_mun"),
    key="municipios_recursos",
)
tabela_recursos = filtrar(recursos_f, "nome_mun", municipios_recursos)
st.dataframe(
    tabela_recursos[
        [
            "nome_mun",
            "cnes",
            "tipo_unidade_desc",
            "esfera_administrativa_desc",
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
