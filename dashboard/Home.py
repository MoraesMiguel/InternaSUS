from pathlib import Path
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_access import carregar, com_municipio

st.set_page_config(page_title="InternaSUS", page_icon="🏥", layout="wide")

st.title("InternaSUS — Painel de Situação")
st.markdown(
    """
Leitura de estado da rede pública de saúde em São Paulo, a partir de **CNES**,
**SIA/SUS**, **SIH/SUS**, **IBGE** e **CID-10**. Dados da camada **Gold** local
(`data/gold/`) — a leitura direto do Object Storage/Autonomous Database do OCI
ainda não está conectada a este dashboard.
"""
)

dim_mun = carregar("dim_municipio")
dim_estab = carregar("dim_estabelecimento")
dim_diag = carregar("dim_diagnostico")
recursos = carregar("fato_recursos_estabelecimento")
profissionais = carregar("fato_profissionais")
desigualdade = carregar("fato_desigualdade_regional")
gargalos = carregar("fato_filas_gargalos")
leitos = carregar("fato_leitos_estabelecimento")
diagnosticos = carregar("fato_internacoes_diagnostico")

populacao = dim_mun["populacao_ref"].sum()
total_leitos = recursos["total_leitos"].sum()
total_medicos = profissionais["medicos"].sum()
total_internacoes = diagnosticos["total_internacoes"].sum()
ano_ref = pd.to_datetime(gargalos["data_referencia"].iloc[0]).year if len(gargalos) else "-"

st.subheader("Régua do estado")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("População coberta", f"{populacao:,.0f}")
col2.metric("Leitos / mil hab. (estado)", f"{total_leitos * 1000 / populacao:.2f}")
col3.metric("Médicos / mil hab. (estado)", f"{total_medicos * 1000 / populacao:.2f}")
col4.metric("Estabelecimentos ativos", f"{len(dim_estab):,.0f}")
col5.metric(f"Internações em {ano_ref}", f"{total_internacoes:,.0f}")
st.caption(
    "Use estes números como régua — todo indicador 'por mil hab.' nas outras páginas "
    "compara um município contra esta média estadual."
)

st.divider()

st.subheader("Top 10 municípios em situação mais crítica")
st.caption(
    "Combina 3 indicadores de infraestrutura per capita — o valor bruto de cada um, lado "
    "a lado, não um score único que esconde de onde vem o problema. Municípios escolhidos "
    "pela média dos 3 percentis (0 = pior do estado), mas exibidos no valor real: muitos dos "
    "piores têm **zero leitos** — mostrar isso como 0,0 é mais claro do que um percentil "
    "empatado, que parece erro de gráfico sem ser."
)
base = desigualdade[["cod_mun", "leitos_por_mil_hab", "equipamentos_por_mil_hab"]].merge(
    profissionais[["cod_mun", "medicos_por_mil_hab"]], on="cod_mun", how="inner"
)
base["media_percentil"] = (
    base["leitos_por_mil_hab"].rank(pct=True)
    + base["equipamentos_por_mil_hab"].rank(pct=True)
    + base["medicos_por_mil_hab"].rank(pct=True)
) / 3
piores = com_municipio(base).sort_values("media_percentil").head(10)
piores = piores.rename(
    columns={
        "leitos_por_mil_hab": "Leitos / mil hab.",
        "equipamentos_por_mil_hab": "Equipamentos / mil hab.",
        "medicos_por_mil_hab": "Médicos / mil hab.",
    }
)

piores_long = piores.melt(
    id_vars="nome_mun",
    value_vars=["Leitos / mil hab.", "Equipamentos / mil hab.", "Médicos / mil hab."],
    var_name="indicador",
    value_name="valor",
)
st.bar_chart(piores_long, x="nome_mun", y="valor", color="indicador", horizontal=True, stack=False)

st.divider()

st.subheader("Panorama por tema")

gargalo_count = int((gargalos["situacao_exames"] == "Sem equipamento próprio (gargalo)").sum())
sem_medico = int((profissionais["medicos"] == 0).sum())

desig_m = com_municipio(desigualdade)
if desig_m["pct_evasao"].notna().any():
    linha_evasao = desig_m.loc[desig_m["pct_evasao"].idxmax()]
    evasao_texto = (
        f"tem a maior evasão hospitalar do estado "
        f"({linha_evasao['pct_evasao']:.1f}% dos internados residentes saem do município)."
    )
    evasao_nome = linha_evasao["nome_mun"]
else:
    evasao_nome, evasao_texto = "-", "sem dado de evasão suficiente."

leitos_uti_por_mun = leitos[leitos["tp_leito"] == "3"].groupby("cod_mun")["qtd_leitos_existentes"].sum()
municipios_com_uti = set(leitos_uti_por_mun[leitos_uti_por_mun > 0].index)
sem_uti = int((~dim_mun["cod_mun"].isin(municipios_com_uti)).sum())

diag_capitulo = diagnosticos.merge(
    dim_diag[["codigo", "descricao_capitulo"]],
    left_on="diagnostico_principal",
    right_on="codigo",
    how="left",
)
top_capitulo = (
    diag_capitulo.groupby("descricao_capitulo")["total_internacoes"].sum().idxmax()
)

pct_publico = dim_estab["esfera_administrativa_desc"].isin(["Municipal", "Estadual"]).mean() * 100

cards = [
    (
        "⏳ Gargalos",
        f"{gargalo_count} municípios",
        "sem nenhum equipamento de imagem próprio, mesmo com demanda de exames.",
        "pages/1_Filas_e_Gargalos.py",
    ),
    (
        "🗺️ Desigualdade regional",
        evasao_nome,
        evasao_texto,
        "pages/2_Desigualdade_Regional.py",
    ),
    (
        "🩺 Profissionais",
        f"{sem_medico} municípios",
        "não têm nenhum médico cadastrado no CNES.",
        "pages/3_Profissionais.py",
    ),
    (
        "🏨 Estabelecimentos",
        f"{pct_publico:.0f}%",
        "dos estabelecimentos são de gestão pública (municipal/estadual).",
        "pages/4_Estabelecimentos.py",
    ),
    (
        "🛏️ Leitos",
        f"{sem_uti} municípios",
        "não têm nenhum leito complementar (UTI) cadastrado.",
        "pages/5_Capacidade_Hospitalar.py",
    ),
    (
        "🧬 Diagnósticos",
        top_capitulo,
        "é o capítulo CID-10 que mais interna gente no estado.",
        "pages/6_Causas_de_Internacao.py",
    ),
]

cols = st.columns(3)
for i, (titulo, numero, texto, pagina) in enumerate(cards):
    with cols[i % 3]:
        with st.container(border=True):
            st.markdown(f"**{titulo}**")
            st.markdown(f"#### {numero}")
            st.caption(texto)
            st.page_link(pagina, label="Ver página →")

st.info(
    "O bloco de **Atenção Primária** (cobertura de UBS/Estratégia Saúde da Família) "
    "não está disponível: depende do SISAB/SIAPS, que ainda não foi ingerido no projeto."
)
