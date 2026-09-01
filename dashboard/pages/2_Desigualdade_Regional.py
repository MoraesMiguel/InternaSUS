from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_municipio, filtrar, opcoes

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

st.subheader("Papel de cada município: exporta pacientes ou recebe de fora?")
st.caption(
    "Cada ponto é um município: eixo horizontal = % de internações de residentes que saem "
    "do município (evasão), eixo vertical = % do atendimento local que vem de fora (pressão "
    "externa). Cruza as duas métricas direto — em vez de duas listas separadas — pra revelar "
    "quem é exportador puro (satélite dependente de outro polo), polo puro (hub regional), os "
    "dois ao mesmo tempo (centro médio que também perde paciente pra um polo maior) ou "
    "autossuficiente."
)
quad_regional = df.dropna(subset=["pct_evasao", "pct_pressao_externa"]).copy()
med_evasao = quad_regional["pct_evasao"].median()
med_pressao = quad_regional["pct_pressao_externa"].median()


def _papel(row: object) -> str:
    evasao_alta = row["pct_evasao"] > med_evasao
    pressao_alta = row["pct_pressao_externa"] > med_pressao
    if evasao_alta and not pressao_alta:
        return "Exportador líquido"
    if pressao_alta and not evasao_alta:
        return "Polo regional"
    if evasao_alta and pressao_alta:
        return "Exportador e polo ao mesmo tempo"
    return "Autossuficiente"


quad_regional["papel"] = quad_regional.apply(_papel, axis=1)
st.scatter_chart(
    quad_regional,
    x="pct_evasao",
    y="pct_pressao_externa",
    color="papel",
    x_label="% de evasão (residentes que saem)",
    y_label="% de pressão externa (atendimento vindo de fora)",
)

st.subheader("Top 15 municípios exportadores de pacientes (% de evasão hospitalar)")
top_evasao = df.sort_values("pct_evasao", ascending=False).dropna(subset=["pct_evasao"]).head(15)
st.bar_chart(top_evasao.set_index("nome_mun")["pct_evasao"])

st.subheader("Perfil dos polos regionais — % de pressão externa nos 15 maiores")
st.caption(
    "Nos 15 municípios com maior volume de atendimento hospitalar, qual fatia desse volume "
    "vem de pacientes de fora — quantifica quanto da capacidade do hospital-referência é "
    "consumida por gente de outro município."
)
polos = df.nlargest(15, "total_atendimentos_polo")
st.bar_chart(
    polos, x="nome_mun", y="pct_pressao_externa", sort="-pct_pressao_externa"
)

st.subheader("15 municípios com menor infraestrutura per capita (leitos por mil hab.)")
bottom_leitos = (
    df[df["leitos_por_mil_hab"].notna()].sort_values("leitos_por_mil_hab", ascending=True).head(15)
)
st.bar_chart(bottom_leitos.set_index("nome_mun")["leitos_por_mil_hab"])

st.divider()
st.subheader("Detalhe por município")
municipios = st.multiselect("Filtrar município(s)", opcoes(df, "nome_mun"))
tabela = filtrar(df, "nome_mun", municipios)

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