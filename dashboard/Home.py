from pathlib import Path
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_access import carregar, com_municipio

st.set_page_config(page_title="InternaSUS", page_icon="🏥", layout="wide")

# Mantém o seu título e introdução (que já cobrem o SISAB)
st.title("InternaSUS — Inteligência e Pressão Hospitalar em São Paulo")
st.markdown(
    """
O InternaSUS integra dados públicos do **CNES**, **SIA/SUS**, **SIH/SUS**, **SISAB** e **IBGE**
para apoiar gestores de saúde pública na identificação de:

- **Filas e gargalos** de exames, cirurgias e serviços especializados
- **Desigualdade regional** de acesso à rede de saúde
- **Falta ou má distribuição de profissionais** especializados
- **Efetividade da Atenção Primária** (cobertura vs. internações evitáveis)

Este é um **MVP**: os dados abaixo vêm da camada **Gold** local
(`data/gold/`), gerada por `internasus.processing.silver` e
`internasus.processing.gold`. A leitura direto do Object Storage / Autonomous
Database do OCI ainda não está conectada a este dashboard.
"""
)

# Carrega as suas bases e as bases novas que o João adicionou[cite: 27]
dim_mun = carregar("dim_municipio")
dim_estab = carregar("dim_estabelecimento")
dim_diag = carregar("dim_diagnostico")
recursos = carregar("fato_recursos_estabelecimento")
profissionais = carregar("fato_profissionais")
desigualdade = carregar("fato_desigualdade_regional")
gargalos = carregar("fato_filas_gargalos")
leitos = carregar("fato_leitos_estabelecimento")
diagnosticos = carregar("fato_internacoes_diagnostico")
aps = carregar("fato_atencao_primaria") # A sua tabela de APS

# Agregações para a Régua do Estado[cite: 27]
populacao = dim_mun["populacao_ref"].sum()
total_leitos = recursos["total_leitos"].sum()
total_medicos = profissionais["medicos"].sum()
total_internacoes = diagnosticos["total_internacoes"].sum()
ano_ref = pd.to_datetime(gargalos["data_referencia"].iloc[0]).year if len(gargalos) else "-"

# Mesclamos as métricas do João com as suas
st.subheader("Régua do estado")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("População coberta", f"{populacao:,.0f}")
col2.metric("Ano de ref.", ano_ref)
col3.metric("Estabelecimentos ativos", f"{len(dim_estab):,.0f}")
col4.metric(f"Internações Totais", f"{total_internacoes:,.0f}")
col5.metric("Internações Evitáveis", f"{aps['internacoes_icsap'].sum():,.0f}")
col6.metric("Leitos / mil hab.", f"{total_leitos * 1000 / populacao:.2f}")

st.caption(
    "Use estes números como régua — todo indicador 'por mil hab.' nas outras páginas "
    "compara um município contra esta média estadual."
)

st.divider()

# Código do João: Top 10 municípios críticos[cite: 27]
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

st.markdown("""
**Como ler este gráfico**

- 🔵 **Leitos/mil hab. ausentes não é erro** — municípios sem barra azul-clara possuem **zero leitos**, o dado mais crítico do grupo.
- 📊 **Valores brutos, não scores** — cada indicador aparece em seu valor real, deixando visível *onde* está o problema, não apenas *quão grave* ele é.
- ⚠️ **Perfis diferentes, causas diferentes:**
  - Cidades como **Ocauçu** e **Coroados** têm poucos equipamentos, mas médicos relativamente presentes — gargalo físico.
  - Cidades como **Pedra Bela** e **Lupércio** têm equipamentos em quantidade, mas faltam médicos — gargalo de pessoal.
  - Demais municípios apresentam carência equilibrada nos três indicadores.
- 🎯 **Seleção por média de percentis** — um município entra na lista por ser ruim na combinação dos três fatores, não necessariamente péssimo em todos. Isso explica perfis tão distintos num mesmo ranking.

> O objetivo é orientar **políticas direcionadas**: saber se falta estrutura, profissional ou ambos é o primeiro passo para um investimento eficiente.
""")

st.divider()

# Código do João: Panorama por tema[cite: 27]
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

# Adicionamos a sua página "Atenção Primária" como um dos cards aqui
cards = [
    (
        "⏳ Gargalos",
        f"{gargalo_count} municípios",
        "Sem nenhum equipamento de imagem próprio, mesmo com demanda de exames.",
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
        "Sem nenhum médico",
        "pages/3_Profissionais.py",
    ),
    (
        "🏥 Atenção Primária",
        f"{aps['internacoes_icsap'].sum():,.0f}",
        "Internações no estado foram por condições sensíveis (evitáveis).",
        "pages/4_Atenção_Primaria.py", 
    ),
    (
        "🏨 Estabelecimentos",
        f"{pct_publico:.0f}%",
        "Dos estabelecimentos são de gestão pública (municipal/estadual).",
        "pages/4_Estabelecimentos.py",
    ),
    (
        "🛏️ Leitos",
        f"{sem_uti} municípios",
        "Não têm nenhum leito complementar (UTI) cadastrado.",
        "pages/5_Capacidade_Hospitalar.py",
    ),
    (
        "🧬 Diagnósticos",
        top_capitulo,
        "É o capítulo CID-10 que mais interna gente no estado.",
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
            try:
                st.page_link(pagina, label="Ver página →")
            except Exception:
                pass # Tratamento para caso o nome do arquivo da página seja levemente diferente no seu disco