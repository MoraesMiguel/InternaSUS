from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_leito, com_municipio, filtrar, opcoes

st.set_page_config(page_title="Filas e Gargalos", page_icon="⏳", layout="wide")
st.title("Filas para especialistas, exames e cirurgias")

df = com_municipio(carregar("fato_filas_gargalos"))
df["equipamentos_por_mil_hab"] = df["equipamentos_imagem"] * 1000 / df["populacao_ref"]

col1, col2, col3 = st.columns(3)
col1.metric("Exames realizados (ano de referência)", f"{df['exames_realizados'].sum():,.0f}")
col2.metric(
    "Municípios sem equipamento próprio (gargalo)",
    int((df["situacao_exames"] == "Sem equipamento próprio (gargalo)").sum()),
)
col3.metric(
    "Municípios com equipamento ocioso", int((df["situacao_exames"] == "Equipamento ocioso").sum())
)

st.subheader("Top 15 municípios por exames realizados por mil hab.")
st.caption(
    "A cor já vem da classificação que a Gold calcula (`situacao_exames`), em vez de "
    "precisar ler uma tabela linha a linha pra achar o gargalo."
)
top_exames_mun = df.dropna(subset=["exames_por_mil_hab"]).nlargest(15, "exames_por_mil_hab")
st.bar_chart(
    top_exames_mun,
    x="nome_mun",
    y="exames_por_mil_hab",
    color="situacao_exames",
    x_label="Município",
    y_label="Exames realizados / mil hab.",
    sort="-exames_por_mil_hab",
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

st.subheader("Leitos por tipo nos 15 municípios com menor infraestrutura de leito per capita")
st.caption(
    "Poucos leitos no total pode esconder um mix errado — ex. só leito clínico, zero "
    "complementar (UTI). Entre os municípios que têm pelo menos 1 leito (quem tem zero já "
    "está coberto pelo indicador simples de leitos por mil hab.), o ranking abaixo pega os "
    "15 piores; a barra empilhada mostra a composição por tipo de cada um."
)
leitos_por_mil_hab = carregar("fato_desigualdade_regional")[["cod_mun", "leitos_por_mil_hab"]]
piores_leitos_mun = (
    leitos_por_mil_hab[leitos_por_mil_hab["leitos_por_mil_hab"] > 0]
    .nsmallest(15, "leitos_por_mil_hab")["cod_mun"]
    .tolist()
)
leitos_tipo = com_municipio(com_leito(carregar("fato_leitos_estabelecimento")))
leitos_tipo = leitos_tipo[leitos_tipo["cod_mun"].isin(piores_leitos_mun)]
leitos_tipo_agg = (
    leitos_tipo.groupby(["nome_mun", "tipo_leito_desc"])["qtd_leitos_existentes"].sum().reset_index()
)
st.bar_chart(
    leitos_tipo_agg,
    x="nome_mun",
    y="qtd_leitos_existentes",
    color="tipo_leito_desc",
    sort="-qtd_leitos_existentes",
)

st.subheader("Serviços especializados cadastrados × produção ambulatorial sustentada")
intensidade = df[df["servicos_especializados_cadastrados"] > 0].copy()
intensidade["producao_por_servico"] = (
    intensidade["producao_ambulatorial"] / intensidade["servicos_especializados_cadastrados"]
)
top_intensidade = intensidade[intensidade["producao_por_servico"] > 0].nlargest(
    15, "producao_por_servico"
)
st.caption(
    "Produção ambulatorial dividida pelo nº de serviços especializados cadastrados — quanto "
    "maior, mais cada serviço formal está sustentando, o que em valores muito altos pode "
    "indicar sobrecarga informal. **Limitação de dado:** `producao_ambulatorial` vem do campo "
    "`PA_UFMUN` do SIA, que nesta base só tem valor para 4 municípios de SP — não significa que "
    "os demais não produzam, é uma lacuna de cobertura desse campo específico (diferente de "
    "`exames_por_mil_hab`, calculado por `PA_MUNPCN`, que cobre a base toda). Por isso o "
    f"ranking abaixo tem só {len(top_intensidade)} município(s)."
)
st.bar_chart(
    top_intensidade,
    x="nome_mun",
    y="producao_por_servico",
    horizontal=True,
    sort="-producao_por_servico",
)

st.divider()
st.subheader("Detalhe por município")
f_situacao = st.multiselect("Situação dos exames", opcoes(df, "situacao_exames"), key="situacao_exames")
municipios = st.multiselect("Filtrar município(s)", opcoes(df, "nome_mun"))
tabela = filtrar(filtrar(df, "situacao_exames", f_situacao), "nome_mun", municipios)

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