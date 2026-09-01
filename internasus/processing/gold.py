
"""
internasus.processing.gold
Camada Gold: constrói o star schema para consumo analítico.
"""

from datetime import date
import duckdb
from internasus.config import GOLD_DATA_DIR, SILVER_DATA_DIR

def conectar_silver() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    fontes = {
        "cnes_eq": SILVER_DATA_DIR / "cnes" / "cnes_eq.parquet",
        "cnes_lt": SILVER_DATA_DIR / "cnes" / "cnes_lt.parquet",
        "cnes_pf": SILVER_DATA_DIR / "cnes" / "cnes_pf.parquet",
        "cnes_sr": SILVER_DATA_DIR / "cnes" / "cnes_sr.parquet",
        "sia": SILVER_DATA_DIR / "sia" / "sia.parquet",
        "sih": SILVER_DATA_DIR / "sih" / "sih.parquet",
        "ibge_pop": SILVER_DATA_DIR / "ibge" / "ibge_pop.parquet",
        "sisab": SILVER_DATA_DIR / "sisab" / "sisab.parquet",
    }
    for nome, caminho in fontes.items():
        if caminho.exists():
            con.execute(f"CREATE OR REPLACE VIEW {nome} AS SELECT * FROM read_parquet('{caminho.as_posix()}')")
    return con

def _preparar_views_derivadas(con: duckdb.DuckDBPyConnection) -> int | None:
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()
    for view in ["cnes_eq", "cnes_lt", "cnes_pf", "cnes_sr"]:
        if view in tabelas:
            con.execute(f"CREATE OR REPLACE VIEW {view}_atual AS SELECT * FROM {view} WHERE COMPETEN = (SELECT MAX(COMPETEN) FROM {view})")
    
    if "sia" not in tabelas or "ibge_pop" not in tabelas:
        return None
        
    ano_ref = con.execute("SELECT DISTINCT ano FROM sia").fetchone()[0]
    con.execute(f"CREATE OR REPLACE VIEW ibge_pop_ref AS SELECT cod_mun, nome_mun, populacao FROM ibge_pop WHERE ano = {ano_ref}")
    con.execute("CREATE OR REPLACE VIEW dim_municipio AS SELECT cod_mun, nome_mun, populacao AS populacao_ref FROM ibge_pop_ref")
    return ano_ref

def _salvar(df, nome: str) -> None:
    destino = GOLD_DATA_DIR / f"{nome}.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    print(f"[_salvar] {nome} -> {destino} ({len(df)} linhas)")

def gold_dim_municipio(con): _salvar(con.execute("SELECT * FROM dim_municipio").df(), "dim_municipio")

def gold_fato_atencao_primaria(con: duckdb.DuckDBPyConnection, data_ref: date) -> None:
    df = con.execute(f"""
        WITH cobertura_aps AS (
            SELECT cod_mun, cobertura_esf, cobertura_eab FROM sisab
        ),
        internacoes_totais AS (
            SELECT MUNIC_RES AS cod_mun, COUNT(*) AS total_internacoes FROM sih GROUP BY MUNIC_RES
        ),
        internacoes_icsap AS (
            SELECT MUNIC_RES AS cod_mun, COUNT(*) AS total_internacoes_icsap FROM sih 
            WHERE SUBSTRING(DIAG_PRINC, 1, 3) IN (
                'A15', 'A16', 'A17', 'A18', 'A19', 'A36', 'A37', 'A33', 'A34', 'A35', 
                'E10', 'E11', 'E12', 'E13', 'E14', 'I10', 'I11', 'I20', 
                'J44', 'J45', 'J46', 'J00', 'J01', 'J02', 'J03', 'J06', 
                'K25', 'K26', 'K27', 'K28'
            )
            GROUP BY MUNIC_RES
        )
        SELECT
            d.cod_mun, DATE '{data_ref.isoformat()}' AS data_referencia,
            COALESCE(aps.cobertura_esf, 0) AS cobertura_esf_pct,
            COALESCE(aps.cobertura_eab, 0) AS cobertura_eab_pct,
            COALESCE(i.total_internacoes, 0) AS total_internacoes,
            COALESCE(icsap.total_internacoes_icsap, 0) AS internacoes_icsap,
            ROUND(COALESCE(icsap.total_internacoes_icsap, 0) * 100.0 / NULLIF(i.total_internacoes, 0), 2) AS taxa_icsap_pct,
            ROUND(COALESCE(icsap.total_internacoes_icsap, 0) * 10000.0 / NULLIF(d.populacao_ref, 0), 2) AS icsap_por_10k_hab
        FROM dim_municipio d
        LEFT JOIN cobertura_aps aps ON d.cod_mun = aps.cod_mun
        LEFT JOIN internacoes_totais i ON d.cod_mun = i.cod_mun
        LEFT JOIN internacoes_icsap icsap ON d.cod_mun = icsap.cod_mun
        WHERE d.populacao_ref > 0
    """).df()
    _salvar(df, "fato_atencao_primaria")

def gerar_gold() -> None:
    con = conectar_silver()
    ano_ref = _preparar_views_derivadas(con)
    if not ano_ref: return
    data_ref = date(ano_ref, 12, 31)
    
    gold_dim_municipio(con)
    try:
        gold_fato_atencao_primaria(con, data_ref)
        print("[gerar_gold] Bloco de Atenção Primária gerado com sucesso.")
    except Exception as e:
        print(f"[gerar_gold] Falha ao gerar Bloco de Atenção Primária: {e}")

if __name__ == "__main__":
    gerar_gold()
