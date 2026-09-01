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

st.divider()

# ============================================================================
# PERGUNTA 1: Gargalos
# ============================================================================
st.subheader("🔍 Pergunta de Negócio")
st.markdown("""
**Quais municípios ou regiões apresentam os maiores gargalos para a realização de 
exames diagnósticos e procedimentos especializados?**

Os gargalos surgem quando há **demanda real por exames, mas ausência de equipamento próprio** 
ou **ociosidade onde há máquinas disponíveis**. O gráfico a seguir mostra os 15 maiores 
produtores de exames e identifica quais enfrentam gargalos estruturais (cor vermelha).
""")

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

st.markdown("""
#### 💡 Como interpretar este gráfico:

- **Cor vermelha (🔴 Gargalo)**: município realiza muitos exames mas **sem equipamento próprio** — 
  depende de terceiros, arranjo insustentável a longo prazo
- **Cor amarela (🟡 Ociosidade)**: tem equipamento, mas produção baixa — máquina não está sendo usada no potencial
- **Cor verde (🟢 Adequado)**: capacidade e demanda alinhadas

#### ⚠️ Ação imediata:

Municípios em **vermelho** precisam de investimento urgente em equipamento próprio. Cidades em **amarelo** 
precisam investigar barreiras de acesso ao serviço (falta de encaminhamentos, comunicação deficiente, etc.).
""")

st.divider()

# ============================================================================
# PERGUNTA 2: Ociosidade vs Sobrecarga
# ============================================================================
st.subheader("🔄 Pergunta de Negócio")
st.markdown("""
**Existe ociosidade de equipamentos em regiões onde a produção ambulatorial é baixa, 
enquanto outras sofrem com sobrecarga?**

Os dois gráficos a seguir formam um **espelho complementar**: o primeiro mostra municípios que 
usam intensamente seus equipamentos (potencial sobrecarga), o segundo mostra cidades que têm máquinas 
mas baixa produção (potencial ociosidade). Juntos, revelam padrões de **má distribuição de recursos** 
entre regiões.
""")

st.subheader("Top 15 municípios por exames por equipamento (Potencial SOBRECARGA)")
st.caption(
    "Quanto maior o valor, mais exames cada máquina está sendo exigida a fazer. "
    "Valores muito altos indicam máquinas sobrecarregadas ou falta de equipamento."
)
top_exames = (
    df.sort_values("exames_por_equipamento", ascending=False)
    .dropna(subset=["exames_por_equipamento"])
    .head(15)
)
st.bar_chart(top_exames.set_index("nome_mun")["exames_por_equipamento"])

st.markdown("""
#### 💡 Como interpretar:

- **Valores altos** (acima de 1.000 exames/equipamento/ano): cada máquina está muito exigida
- **Risco**: falta de equipamento, manutenção deficiente, burnout de técnicos
- **Exemplo**: uma cidade com 1 tomógrafo fazendo 4.000 exames/ano está claramente sobrecarregada

#### 🎯 Recomendação:

Se uma cidade tem alta demanda confirmada, investir em mais equipamento tem ROI rápido 
(reduz filas, melhora acesso, diminui custo por exame).
""")

st.subheader("Bottom 15 municípios por exames por equipamento (Potencial OCIOSIDADE)")
st.caption(
    "Espelho do gráfico acima — mostra quem tem equipamento mas produz pouco. "
    "Municípios com menos de 1 equipamento são excluídos (senão 'zero exames' fica confuso)."
)
bottom_exames = (
    df[df["equipamentos_imagem"] > 0]
    .sort_values("exames_por_equipamento", ascending=True)
    .dropna(subset=["exames_por_equipamento"])
    .head(15)
)
st.bar_chart(bottom_exames.set_index("nome_mun")["exames_por_equipamento"])

st.markdown("""
#### 💡 Como interpretar:

- **Valores baixos** (abaixo de 100 exames/equipamento/ano): máquinas subutilizadas
- **Possíveis causas**:
  - Falta de demanda real no município (população não demanda tanto)
  - Falta de profissionais para operar o equipamento
  - Falta de integração com sistema de encaminhamentos (demanda "invisível")
  - Serviço recém-implantado (equipamento novo, ainda não consolidado)

#### 🎯 Recomendação:

Antes de concluir que o equipamento é desnecessário, investigue:
1. **Há fila em cidades vizinhas?** (demanda reprimida exportada)
2. **Há profissionais capacitados locais?** (falta de técnico operador)
3. **O serviço é comunicado aos encaminhadores?** (falta de marketing)

Se a demanda é realmente baixa, considere realocação ou compartilhamento regional.
""")

st.divider()

# ============================================================================
# Continuação: Taxa de ocupação e leitos
# ============================================================================
st.subheader("Top 15 municípios por taxa de ocupação estimada de leitos cirúrgicos")
st.caption(
    "Municípios com menos de 3 leitos cirúrgicos cadastrados são excluídos deste "
    "ranking — a taxa sobre poucos leitos é estatisticamente instável. O valor "
    "também é limitado a 100% (ocupação não pode superar a capacidade)."
)
top_leitos = (
    df.sort_values("taxa_ocupacao_leitos_pct", ascending=False)
    .dropna(subset=["taxa_ocupacao_leitos_pct"])
    .head(15)
)
st.bar_chart(top_leitos.set_index("nome_mun")["taxa_ocupacao_leitos_pct"])

st.markdown("""
#### 💡 Como interpretar:

- **Acima de 85%**: pressão alta — há fila de espera para cirurgias eletivas
- **Entre 70-85%**: ocupação saudável — há margem para emergências
- **Abaixo de 70%**: capacidade disponível — leitos podem estar ociosos

#### ⚠️ Limitação importante:

Este valor é **agregado** — não diferencia cirurgias de **urgência** vs. **eletivas**. Um município 
pode ter 90% ocupado só com emergências (não há fila de eletivas), enquanto outro tem 50% mas grande 
fila de eletivas. Para análise mais precisa, seria necessário filtrar por tipo de procedimento.
""")

st.subheader("Leitos por tipo nos 15 municípios com menor infraestrutura de leito per capita")
st.caption(
    "Poucos leitos no total pode esconder um mix errado — ex. só leito clínico, zero "
    "complementar (UTI). Entre os municípios que têm pelo menos 1 leito, o ranking abaixo pega os "
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

st.markdown("""
#### 💡 Como interpretar:

- **Composição equilibrada**: clínico + complementar (UTI) + cirúrgico = infraestrutura versátil
- **Desequilíbrio (ex: só clínico)**: município mal preparado para emergências e procedimentos
- **Exemplo de problema**: cidade com 10 leitos clínicos mas zero UTI não consegue lidar com pacientes críticos

#### 🎯 Recomendação:

Aumentar o total de leitos é importante, mas **não é suficiente** — a **composição** precisa 
estar alinhada com o perfil epidemiológico local e capacidade de cirurgia.
""")

st.divider()

# ============================================================================
# PERGUNTA 3: Serviços com baixa produção
# ============================================================================
st.subheader("📋 Pergunta de Negócio")
st.markdown("""
**Quais municípios têm serviços especializados cadastrados mas baixa produção 
sustentada?**

Ter um serviço "no papel" não é o mesmo que tê-lo funcionando. O gráfico a seguir 
mostra a **intensidade de produção por serviço especializado** — valores altos 
indicam serviços bem estruturados e em uso regular; valores baixos sugerem 
infrautilização ou simplesmente não-operacionalidade.
""")

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
    "maior, mais cada serviço formal está sustentando produção real. **Limitação de dado:** "
    "`producao_ambulatorial` vem do campo `PA_UFMUN` do SIA, que nesta base só tem cobertura "
    f"para alguns municípios de SP — por isso o ranking abaixo tem só {len(top_intensidade)} município(s) com dados."
)
st.bar_chart(
    top_intensidade,
    x="nome_mun",
    y="producao_por_servico",
    horizontal=True,
    sort="-producao_por_servico",
)

st.markdown("""
#### 💡 Como interpretar:

- **Valores altos** (ex: 500+ atendimentos/serviço): serviços consolidados, operando em ritmo sustentável
- **Valores baixos** (ex: 20 atendimentos/serviço): possível serviço "fantasma" ou recém-implantado
- **Exemplo**: município com 20 serviços cadastrados mas só 100 atendimentos totais = problema grave

#### ⚠️ Limitações dos dados:

1. `producao_ambulatorial` tem **cobertura incompleta** — nem todos os municípios têm este campo preenchido no SIA
2. Um serviço novo pode estar com produção baixa legitimamente (curva de crescimento)
3. Falta de dado não significa "zero produção" — pode ser simplesmente não registrado

#### 🎯 Ação Recomendada:

1. **Auditoria de serviços**: listar os cadastrados e confirmar quais estão realmente operacionais
2. **Investigação de barreiras**: se funcionam mas produzem pouco:
   - Falta de profissional especialista?
   - Falta de encaminhamentos (médicos não sabem que existe)?
   - Horário limitado ou intermitente?
3. **Decisão informada**: realocação, fechamento formal, ou investimento em publicidade/integração

Este indicador é especialmente importante para **gestores** — evita desperdiçar recursos 
formalizando serviços que não saem do papel.
""")

st.divider()

# ============================================================================
# TABELA DE DETALHE (Filtros + dados)
# ============================================================================
st.subheader("Detalhe por município — Filtros e tabela interativa")

st.markdown("""
#### 💡 Como usar:

1. Filtre por **situação de exames** para ver todos os casos de gargalo, ociosidade ou adequado lado a lado
2. Filtre por **município(s)** para fazer investigação profunda de um local específico
3. Leia as **colunas-chave**:
   - `situacao_exames`: classificação automática (gargalo / ociosidade / adequado)
   - `exames_por_mil_hab`: padronizado por população (comparável entre cidades)
   - `exames_por_equipamento`: intensidade de uso de cada máquina
   - `taxa_ocupacao_leitos_pct`: pressão atual de cirurgias
   - `producao_ambulatorial`: ritmo de atendimento ambulatorial

**Dica**: comece filtrando por "Sem equipamento próprio (gargalo)" para ver quem mais precisa de investimento imediato.
""")

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