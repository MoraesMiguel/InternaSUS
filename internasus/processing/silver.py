
"""
internasus.processing.silver
Camada Silver: lê as views "bronze" (via conectar_datasus), aplica limpeza,
padronização e o recorte temporal do MVP, e grava o resultado em Parquet em
data/silver/.
"""

from pathlib import Path
import duckdb
from internasus.config import SILVER_DATA_DIR, RAW_DATA_DIR
from internasus.loaders import conectar_datasus

N_COMPETENCIAS_CNES = 12

def _garantir_dir(caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)

def _gravar(con: duckdb.DuckDBPyConnection, query: str, destino: Path) -> None:
    _garantir_dir(destino)
    con.execute(f"COPY ({query}) TO '{destino.as_posix()}' (FORMAT PARQUET)")
    n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{destino.as_posix()}')").fetchone()[0]
    print(f"  -> {destino} ({n:,} linhas)")

def _competencias_recentes(con: duckdb.DuckDBPyConnection, view: str, n: int) -> list[str]:
    return (
        con.execute(f"SELECT DISTINCT COMPETEN FROM {view} ORDER BY COMPETEN DESC LIMIT {n}")
        .df()["COMPETEN"]
        .tolist()
    )

def _ano_referencia(con: duckdb.DuckDBPyConnection) -> int:
    anos_pop = con.execute("SELECT DISTINCT ano FROM ibge_pop").df()["ano"].tolist()
    anos_sia_completos = (
        con.execute("SELECT ano FROM sia GROUP BY ano HAVING COUNT(DISTINCT mes) = 12")
        .df()["ano"]
        .tolist()
    )
    return max(a for a in anos_pop if a in anos_sia_completos)

def _in_list(valores: list[str]) -> str:
    return ", ".join(f"'{v}'" for v in valores)

def gerar_silver_cnes(con: duckdb.DuckDBPyConnection) -> None:
    print("[gerar_silver_cnes] Processando CNES-EQ/LT/PF/SR...")
    for view in ["eq", "lt", "pf", "sr"]:
        competencias = _in_list(_competencias_recentes(con, f"cnes_{view}", N_COMPETENCIAS_CNES))
        if view in ["eq", "lt"]:
            query = f"SELECT DISTINCT * REPLACE (TRY_CAST(QT_EXIST AS INTEGER) AS QT_EXIST) FROM cnes_{view} WHERE COMPETEN IN ({competencias})"
        else:
            query = f"SELECT DISTINCT * FROM cnes_{view} WHERE COMPETEN IN ({competencias})"
        _gravar(con, query, SILVER_DATA_DIR / "cnes" / f"cnes_{view}.parquet")

def gerar_silver_sia(con: duckdb.DuckDBPyConnection, ano_ref: int) -> None:
    print(f"[gerar_silver_sia] Processando SIA (ano={ano_ref})...")
    _gravar(
        con,
        f"SELECT PA_MUNPCN, PA_UFMUN, PA_PROC_ID, PA_NIVCPL, PA_CBOCOD, PA_CMP, ano, mes FROM sia WHERE ano = {ano_ref}",
        SILVER_DATA_DIR / "sia" / "sia.parquet",
    )

def gerar_silver_sih(con: duckdb.DuckDBPyConnection, ano_ref: int) -> None:
    print(f"[gerar_silver_sih] Processando SIH (ano={ano_ref})...")
    _gravar(
        con,
        f"SELECT CNES, MUNIC_RES, MUNIC_MOV, PROC_REA, DIAG_PRINC, TRY_CAST(DIAS_PERM AS INTEGER) AS DIAS_PERM, DT_INTER, DT_SAIDA, ano, mes FROM sih WHERE ano = {ano_ref}",
        SILVER_DATA_DIR / "sih" / "sih.parquet",
    )

def gerar_silver_ibge(con: duckdb.DuckDBPyConnection) -> None:
    print("[gerar_silver_ibge] Processando IBGE/SIDRA (população)...")
    _gravar(
        con,
        "SELECT DISTINCT LEFT(municipio_codigo, 6) AS cod_mun, municipio_nome AS nome_mun, ano, valor AS populacao FROM ibge_pop",
        SILVER_DATA_DIR / "ibge" / "ibge_pop.parquet",
    )

def gerar_silver_sisab(con: duckdb.DuckDBPyConnection, ano_ref: int) -> None:
    print(f"[gerar_silver_sisab] Processando SISAB (ano={ano_ref})...")
    
    caminho_raw_base = RAW_DATA_DIR / "fonte=SISAB"
    if not caminho_raw_base.exists():
        print(f"[gerar_silver_sisab] Diretório {caminho_raw_base} não encontrado.")
        return
        
    caminho_glob = f"{caminho_raw_base.as_posix()}/**/*.parquet"
    
    # Mapeando os nomes reais das colunas da base SISAB:
    # - coMunicipioIbge -> cod_mun (pegando os 6 primeiros dígitos para compatibilidade com o IBGE/SIA/SIH)
    # - nuComp -> COMPETEN (referência temporal mensal, ex: '202512')
    # - qtCobertura -> cobertura_esf (ou qtCobertura percentual)
    query = f"""
        WITH filtrado_ano AS (
            SELECT 
                LEFT(CAST(coMunicipioIbge AS VARCHAR), 6) AS cod_mun,
                CAST(nuComp AS VARCHAR) AS COMPETEN,
                COALESCE(qtCobertura, 0.0) AS cobertura_esf,
                0.0 AS cobertura_eab
            FROM read_parquet('{caminho_glob}', union_by_name=true, hive_partitioning=true) 
            WHERE LEFT(CAST(nuComp AS VARCHAR), 4) = '{ano_ref}'
        ),
        ranqueado AS (
            SELECT *, ROW_NUMBER() OVER(PARTITION BY cod_mun ORDER BY COMPETEN DESC) as rn 
            FROM filtrado_ano
        )
        SELECT cod_mun, COMPETEN, cobertura_esf, cobertura_eab 
        FROM ranqueado 
        WHERE rn = 1
    """
    
    _gravar(con, query, SILVER_DATA_DIR / "sisab" / "sisab.parquet")

def gerar_silver() -> None:
    con = conectar_datasus()
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()

    if {"cnes_eq", "cnes_lt", "cnes_pf", "cnes_sr"} <= set(tabelas):
        gerar_silver_cnes(con)
        
    ano_ref = _ano_referencia(con) if "sia" in tabelas and "ibge_pop" in tabelas else None
    
    if ano_ref:
        gerar_silver_sia(con, ano_ref)
        if "sih" in tabelas: gerar_silver_sih(con, ano_ref)
        gerar_silver_sisab(con, ano_ref)
        
    if "ibge_pop" in tabelas:
        gerar_silver_ibge(con)

if __name__ == "__main__":
    gerar_silver()
