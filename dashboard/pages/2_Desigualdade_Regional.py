from pathlib import Path
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_municipio, filtrar, opcoes

st.set_page_config(page_title="Desigualdade Regional", page_icon="🗺️", layout="wide")
st.title("Desigualdade regional de acesso")

df = com_municipio(carregar("fato_desigualdade_regional"))

# ----------------------------------------------------------------------------
# Recortes reutilizados na página inteira (métricas do topo E os gráficos
# usam os MESMOS dataframes, pra não ter card do topo dizendo uma coisa e
# tabela mostrando outra).
# ----------------------------------------------------------------------------
TOP_N_EXPORTADORES = 20

top_evasao = (
    df.dropna(subset=["evasao_hospitalar", "pct_evasao"])
    .sort_values("evasao_hospitalar", ascending=False)
    .head(TOP_N_EXPORTADORES)
)
polos = df.nlargest(15, "total_atendimentos_polo")

col1, col2, col3 = st.columns(3)
col1.metric(
    "Maior % de evasão (entre os principais exportadores)",
    top_evasao.loc[top_evasao["pct_evasao"].idxmax(), "nome_mun"]
    if not top_evasao.empty else "-",
)
col2.metric(
    "Maior % de pressão externa (entre os 15 maiores polos)",
    polos.loc[polos["pct_pressao_externa"].idxmax(), "nome_mun"]
    if not polos.empty and polos["pct_pressao_externa"].notna().any()
    else "-",
)
col3.metric("Municípios analisados", len(df))

st.caption(
    "As duas métricas de % acima já consideram só os municípios de volume relevante. Municípios minúsculos sem hospital podem ter 100% de "
    "evasão isoladamente, mas por representarem poucos casos, ficam de fora do destaque; "
    "eles continuam disponíveis na tabela de detalhe no fim da página."
)

st.divider()

# ============================================================================
# PERGUNTA 1: Exportadores x Polos (visão combinada)
# ============================================================================
st.subheader("🗺️ Pergunta de Negócio")
st.markdown("""
**Quais são os principais municípios "exportadores" de pacientes, e quais polos regionais
estão sofrendo maior pressão por receber quem não tem infraestrutura própria?**

As duas perguntas são dois lados do mesmo fluxo de pacientes: quem sai (evasão) e quem recebe
(pressão externa). O gráfico a seguir cruza as duas métricas de uma vez, em vez de duas listas
separadas, pra revelar o papel de cada município nesse fluxo.
""")

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

st.markdown("""
#### 💡 Como interpretar este gráfico:

- **Canto inferior direito (Exportador líquido)**: alta evasão, baixa pressão externa — cidade
  satélite, depende de outro município pra internar seus residentes, mas não recebe ninguém de fora
- **Canto superior esquerdo (Polo regional)**: baixa evasão, alta pressão externa — hub que
  consegue atender bem os próprios residentes e ainda absorve demanda de municípios vizinhos
- **Canto superior direito (Exportador e polo ao mesmo tempo)**: perde paciente pra um polo maior
  *e* recebe de cidades menores — típico de centro médio no meio de uma hierarquia regional
- **Canto inferior esquerdo (Autossuficiente)**: nem depende de fora, nem é procurado de fora —
  atende a própria demanda dentro dos próprios limites
""")

st.subheader("Principais municípios exportadores de pacientes")
st.caption(
    f"Ranking por volume absoluto de internações que saíram do município — não por %. "
    "Muitos municípios pequenos sem hospital próprio batem 100% de evasão (todo mundo "
    "que interna, sai da cidade), mas isso sozinho não indica quem pesa mais na demanda "
    "dos polos vizinhos: uma cidade grande com 60% de evasão desloca muito mais gente do "
    "que uma cidade pequena com 100%. Por serem grandes o suficiente pra entrar neste "
    f"Top {TOP_N_EXPORTADORES}, nenhum município aqui chega a 100% — os que chegam ficam de "
    "fora por terem poucos casos no total (ver tabela de detalhe no fim da página). "
    "Cor mais clara = % de evasão mais alto, dentro do mesmo ranking por volume."
)

st.bar_chart(
    top_evasao.set_index("nome_mun"),
    y="evasao_hospitalar",
    color="pct_evasao",
    horizontal=True,
    sort="-evasao_hospitalar",
    y_label="Internações de residentes que saíram do município",
)

st.dataframe(
    top_evasao[["nome_mun", "total_internacoes_residentes", "evasao_hospitalar", "pct_evasao"]].rename(
        columns={
            "nome_mun": "Município",
            "total_internacoes_residentes": "Total de internações (residentes)",
            "evasao_hospitalar": "Internações que saíram",
            "pct_evasao": "% de evasão",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("""
#### 🎯 Ação imediata:

Municípios no topo deste ranking são os que mais pressionam a rede regional em números
absolutos — são o alvo prioritário pra qualquer discussão de regionalização (consórcio
intermunicipal de saúde, leito de referência compartilhado) porque o volume desses pacientes
sozinho já justifica investimento coletivo, diferente de cidades pequenas isoladas em 100%
de evasão mas com poucas dezenas de internações/ano.
""")

st.divider()

# ============================================================================
# PERGUNTA 2: Pressão sobre os polos
# ============================================================================
st.subheader("🏥 Pergunta de Negócio")
st.markdown("""
**Quais polos regionais estão sofrendo maior pressão e sobrecarga por receberem pacientes
de municípios vizinhos que não possuem infraestrutura própria?**

Olhando só pelo volume total de atendimento, um hospital-referência grande pode parecer
"funcionando bem" — mas se boa parte desse volume é gente de fora, a capacidade real
disponível pros próprios moradores é menor do que os números brutos sugerem.
""")

st.subheader("Perfil dos polos regionais — % de pressão externa nos 15 maiores")
st.caption(
    "Nos 15 municípios com maior volume de atendimento hospitalar, qual fatia desse volume "
    "vem de pacientes de fora — quantifica quanto da capacidade do hospital-referência é "
    "consumida por gente de outro município."
)
st.bar_chart(
    polos, x="nome_mun", y="pct_pressao_externa", sort="-pct_pressao_externa"
)

st.markdown("""
#### 💡 Como interpretar:

- **% alto**: parte relevante da capacidade instalada desse polo é consumida por pacientes de
  outros municípios — em dias de pico, é o residente local que fica em fila
- **% baixo, mesmo com volume alto**: o hospital atende sobretudo a própria população;
  o volume alto reflete só o tamanho do município, não pressão externa

#### ⚠️ Ação recomendada:

Polos com % de pressão externa alto são candidatos naturais a receber investimento
compartilhado (leito extra, novo turno cirúrgico) — o custo se justifica porque atende
vários municípios de uma vez, não só a sede.
""")

st.divider()

# ============================================================================
# PERGUNTA 3: Infraestrutura per capita
# ============================================================================
st.subheader("🛏️ Pergunta de Negócio")
st.markdown("""
**Quais regiões do estado possuem a menor proporção de leitos, equipamentos e serviços
especializados por habitante?**

Infraestrutura per capita baixa em qualquer um dos três indicadores já é sinal de alerta —
mas ver os três juntos, em vez de um índice único, mostra se o problema é generalizado
(falta tudo) ou concentrado (ex.: tem leito, mas não tem equipamento).
""")

st.subheader("Bottom 15 municípios com menor infraestrutura per capita agregada")
st.caption(
    "Combina 3 indicadores de infraestrutura per capita (leitos, equipamentos e serviços por mil hab.). "
    "Mostra o valor bruto de cada indicador lado a lado (barras ausentes indicam valores zerados ou "
    "muito próximos de zero). Municípios selecionados pela média dos 3 percentis."
)

# Preparar dados
infra_base = df[["nome_mun", "leitos_por_mil_hab", "equipamentos_por_mil_hab", "servicos_por_mil_hab"]].copy()
infra_base = infra_base.dropna(subset=["leitos_por_mil_hab", "equipamentos_por_mil_hab", "servicos_por_mil_hab"])

# Calcular percentis
infra_base["pct_leitos"] = infra_base["leitos_por_mil_hab"].rank(pct=True)
infra_base["pct_equipamentos"] = infra_base["equipamentos_por_mil_hab"].rank(pct=True)
infra_base["pct_servicos"] = infra_base["servicos_por_mil_hab"].rank(pct=True)
infra_base["media_percentil"] = (infra_base["pct_leitos"] + infra_base["pct_equipamentos"] + infra_base["pct_servicos"]) / 3

# Bottom 15
piores_infra = infra_base.nsmallest(15, "media_percentil")

# Reformatar pra visualização
piores_long = piores_infra.melt(
    id_vars="nome_mun",
    value_vars=["leitos_por_mil_hab", "equipamentos_por_mil_hab", "servicos_por_mil_hab"],
    var_name="indicador",
    value_name="valor"
)
piores_long["indicador"] = piores_long["indicador"].map({
    "leitos_por_mil_hab": "Leitos / mil hab.",
    "equipamentos_por_mil_hab": "Equipamentos / mil hab.",
    "servicos_por_mil_hab": "Serviços / mil hab."
})

st.bar_chart(piores_long, x="nome_mun", y="valor", color="indicador", stack=False)

st.markdown("""
#### 💡 Como interpretar:

- **Métricas simultaneamente baixas/ausentes**: déficit generalizado — o município carece de
  estrutura hospitalar em qualquer frente, prioridade máxima
- **Apenas uma métrica deficitária**: déficit pontual — ex. tem leito e serviço, mas falta equipamento;
  o investimento aqui é focado e mais barato do que construir um hospital novo

#### 🎯 Recomendação:

Municípios que aparecem simultaneamente aqui **e** no ranking de exportadores acima são o
duplo alerta: têm pouca estrutura própria *e* pesam de forma relevante sobre os polos vizinhos —
esses são os candidatos mais fortes a qualquer expansão de infraestrutura regional.
""")

st.divider()
st.subheader("Detalhe por município")
st.markdown("""
#### 💡 Como usar:

Use o filtro abaixo pra ver os números brutos por trás de qualquer ponto que chamou sua
atenção nos gráficos acima — incluindo os municípios minúsculos com 100% de evasão que ficam
de fora dos rankings por volume no topo da página.
""")
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