from pathlib import Path
import sys

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_access import carregar, com_municipio

st.set_page_config(page_title="Atenção Primária", page_icon="🏥", layout="wide")
st.title("Atenção Primária e Internações Evitáveis (ICSAP)")

# Carregamento e junção com a dimensão de municípios
df = com_municipio(carregar("fato_atencao_primaria"))

col1, col2, col3 = st.columns(3)
col1.metric("Média Cobertura ESF", f"{df['cobertura_esf_pct'].mean():.1f}%")
col2.metric("Média Taxa ICSAP", f"{df['taxa_icsap_pct'].mean():.1f}%")
col3.metric("Total Internações por ICSAP", f"{df['internacoes_icsap'].sum():,.0f}")

st.markdown("---")

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("Cobertura ESF vs. Taxa de Internações Sensíveis")
    st.caption("Verifique se municípios com baixa cobertura tendem a ter maior taxa de internações evitáveis.")
    
    fig = px.scatter(
        df,
        x="cobertura_esf_pct",
        y="taxa_icsap_pct",
        hover_name="nome_mun",
        size="total_internacoes",
        color="taxa_icsap_pct",
        color_continuous_scale="RdYlGn_r", 
        labels={
            "cobertura_esf_pct": "Cobertura ESF (%)",
            "taxa_icsap_pct": "Taxa de ICSAP (%)"
        }
    )
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with col_chart2:
    st.subheader("Top 15 municípios por Taxa de ICSAP")
    st.caption("Municípios com maior proporção de internações por condições sensíveis à atenção primária em relação ao total de internações.")
    
    top_icsap = (
        df.sort_values("taxa_icsap_pct", ascending=False)
        .dropna(subset=["taxa_icsap_pct"])
        .head(15)
    )
    st.bar_chart(top_icsap.set_index("nome_mun")["taxa_icsap_pct"])

st.subheader("Detalhe por município")
municipios = st.multiselect("Filtrar município(s)", sorted(df["nome_mun"].dropna().unique()))
tabela = df[df["nome_mun"].isin(municipios)] if municipios else df

st.dataframe(
    tabela[
        [
            "nome_mun",
            "populacao_ref",
            "cobertura_esf_pct",
            "cobertura_eab_pct",
            "total_internacoes",
            "internacoes_icsap",
            "taxa_icsap_pct",
            "icsap_por_10k_hab"
        ]
    ].sort_values("taxa_icsap_pct", ascending=False),
    use_container_width=True,
    hide_index=True,
)