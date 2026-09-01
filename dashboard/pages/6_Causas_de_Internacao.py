from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_diagnostico, com_municipio, filtrar, opcoes

st.set_page_config(page_title="Causas de Internação", page_icon="🧬", layout="wide")
st.title("Causas de internação (epidemiologia)")

diag = com_municipio(com_diagnostico(carregar("fato_internacoes_diagnostico")))

f_capitulo = st.multiselect("Capítulo CID-10", opcoes(diag, "descricao_capitulo"), key="diag_capitulo")
diag_f = filtrar(diag, "descricao_capitulo", f_capitulo)

st.metric("Internações (após filtro)", f"{diag_f['total_internacoes'].sum():,.0f}")

st.subheader("Capítulos CID-10 por total de internações no estado")
por_capitulo = (
    diag_f.groupby("descricao_capitulo")["total_internacoes"].sum().sort_values(ascending=False)
)
top5_pct = por_capitulo.head(5).sum() * 100 / por_capitulo.sum() if por_capitulo.sum() else 0
st.caption(
    f"Os 5 capítulos mais frequentes concentram **{top5_pct:.0f}%** de todas as internações "
    "filtradas — visão macro de 'do que o SUS-SP mais trata'."
)
st.bar_chart(por_capitulo.head(15))

st.subheader("Capítulo × tempo médio de permanência")
st.caption(
    "Separa 'muitos casos rápidos' (ex. parto) de 'poucos casos que prendem leito por "
    "semanas' — dois problemas de gestão de leito completamente diferentes, hoje "
    "misturados num único número de 'dias de permanência totais'."
)
tempo_capitulo = diag_f.groupby("descricao_capitulo").agg(
    internacoes=("total_internacoes", "sum"), dias=("dias_permanencia_total", "sum")
)
tempo_capitulo = tempo_capitulo[tempo_capitulo["internacoes"] >= 30]
tempo_capitulo["permanencia_media"] = tempo_capitulo["dias"] / tempo_capitulo["internacoes"]
tempo_capitulo = tempo_capitulo.reset_index()
st.scatter_chart(
    tempo_capitulo,
    x="internacoes",
    y="permanencia_media",
    x_label="Total de internações (escala log ajuda a comparar)",
    y_label="Permanência média (dias)",
)

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("Top 15 municípios por internações")
    top_mun_diag = diag_f.groupby("nome_mun")["total_internacoes"].sum().sort_values(ascending=False).head(15)
    st.bar_chart(top_mun_diag)
with col2:
    st.subheader("Top 10 diagnósticos")
    top_diag = diag_f.groupby("descricao")["total_internacoes"].sum().sort_values(ascending=False).head(10)
    st.bar_chart(top_diag)

st.subheader("Detalhe por município")
municipios_diag = st.multiselect("Filtrar município(s)", opcoes(diag_f, "nome_mun"), key="mun_diag")
tabela_diag = filtrar(diag_f, "nome_mun", municipios_diag)
st.dataframe(
    tabela_diag.groupby(["nome_mun", "descricao_capitulo"])
    .agg(
        internacoes=("total_internacoes", "sum"),
        dias_permanencia=("dias_permanencia_total", "sum"),
    )
    .reset_index()
    .sort_values("internacoes", ascending=False)
    .head(200),
    use_container_width=True,
    hide_index=True,
)
st.caption("Tabela limitada às 200 combinações de maior volume — use os filtros acima para refinar.")
