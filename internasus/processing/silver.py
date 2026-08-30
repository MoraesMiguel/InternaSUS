"""
internasus.processing.silver
Camada Silver: lê as views "bronze" (via conectar_datasus), aplica limpeza,
padronização e o recorte temporal do MVP, e grava o resultado em Parquet em
data/silver/.

Recorte temporal (MVP — ver plano/README §5.2.1):
* CNES (EQ/LT/PF/SR) é um retrato mensal repetido (a mesma linha aparece em
  toda competência em que esteve ativa) — mantemos só as últimas
  N_COMPETENCIAS_CNES competências, calculadas dinamicamente a partir do que
  existe em data/raw/.
* SIA/SIH são bases de eventos (não de retrato) — mantemos só ANO_REF, o
  último ano com população estimada (SIDRA) E os 12 meses completos de SIA,
  calculado dinamicamente (mesma lógica validada em notebooks/InternaSUS.ipynb).
* ibge_pop mantém todos os anos disponíveis (poucas linhas), necessário para
  calcular variação populacional entre anos.
"""

from pathlib import Path

import duckdb

from internasus.config import SILVER_DATA_DIR
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
    """N competências mais recentes disponíveis numa view CNES, mais recente primeiro."""
    return (
        con.execute(f"SELECT DISTINCT COMPETEN FROM {view} ORDER BY COMPETEN DESC LIMIT {n}")
        .df()["COMPETEN"]
        .tolist()
    )


def _ano_referencia(con: duckdb.DuckDBPyConnection) -> int:
    """Último ano com população estimada (ibge_pop) E 12 meses completos de SIA."""
    anos_pop = con.execute("SELECT DISTINCT ano FROM ibge_pop").df()["ano"].tolist()
    anos_sia_completos = (
        con.execute("""
        SELECT ano FROM sia GROUP BY ano HAVING COUNT(DISTINCT mes) = 12
    """)
        .df()["ano"]
        .tolist()
    )
    return max(a for a in anos_pop if a in anos_sia_completos)


def _in_list(valores: list[str]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def gerar_silver_cnes(con: duckdb.DuckDBPyConnection) -> None:
    """CNES-EQ/LT/PF/SR: últimas N_COMPETENCIAS_CNES competências, tipos corrigidos."""
    print("[gerar_silver_cnes] Processando CNES-EQ/LT/PF/SR...")

    competencias_eq = _in_list(_competencias_recentes(con, "cnes_eq", N_COMPETENCIAS_CNES))
    _gravar(
        con,
        f"""
        SELECT DISTINCT * REPLACE (TRY_CAST(QT_EXIST AS INTEGER) AS QT_EXIST)
        FROM cnes_eq
        WHERE COMPETEN IN ({competencias_eq})
        """,
        SILVER_DATA_DIR / "cnes" / "cnes_eq.parquet",
    )

    competencias_lt = _in_list(_competencias_recentes(con, "cnes_lt", N_COMPETENCIAS_CNES))
    _gravar(
        con,
        f"""
        SELECT DISTINCT * REPLACE (TRY_CAST(QT_EXIST AS INTEGER) AS QT_EXIST)
        FROM cnes_lt
        WHERE COMPETEN IN ({competencias_lt})
        """,
        SILVER_DATA_DIR / "cnes" / "cnes_lt.parquet",
    )

    competencias_pf = _in_list(_competencias_recentes(con, "cnes_pf", N_COMPETENCIAS_CNES))
    _gravar(
        con,
        f"SELECT DISTINCT * FROM cnes_pf WHERE COMPETEN IN ({competencias_pf})",
        SILVER_DATA_DIR / "cnes" / "cnes_pf.parquet",
    )

    competencias_sr = _in_list(_competencias_recentes(con, "cnes_sr", N_COMPETENCIAS_CNES))
    _gravar(
        con,
        f"SELECT DISTINCT * FROM cnes_sr WHERE COMPETEN IN ({competencias_sr})",
        SILVER_DATA_DIR / "cnes" / "cnes_sr.parquet",
    )


def gerar_silver_sia(con: duckdb.DuckDBPyConnection, ano_ref: int) -> None:
    """SIA (produção ambulatorial): só o ano de referência e as colunas usadas
    na camada gold. SIA bruto tem ~524M linhas (2020-2026) e dezenas de
    colunas — mesmo escopado a 1 ano, um SELECT * DISTINCT satura o disco
    local (join hash espalha pra .tmp); projetar só as colunas necessárias
    reduz o volume em ordens de grandeza (README §5.2.1: "seleção das
    colunas necessárias"). Sem DISTINCT por ser uma base de eventos (cada
    linha é um procedimento) e a projeção estreita já não retém colunas
    que tipicamente causariam duplicatas espúrias."""
    print(f"[gerar_silver_sia] Processando SIA (ano={ano_ref})...")
    _gravar(
        con,
        f"""
        SELECT PA_MUNPCN, PA_UFMUN, PA_PROC_ID, PA_NIVCPL, PA_CBOCOD, PA_CMP, ano, mes
        FROM sia
        WHERE ano = {ano_ref}
        """,
        SILVER_DATA_DIR / "sia" / "sia.parquet",
    )


def gerar_silver_sih(con: duckdb.DuckDBPyConnection, ano_ref: int) -> None:
    """SIH (internações): só o ano de referência e as colunas usadas na
    camada gold (mesmo motivo de gerar_silver_sia — evitar SELECT * DISTINCT
    numa base de eventos grande)."""
    print(f"[gerar_silver_sih] Processando SIH (ano={ano_ref})...")
    _gravar(
        con,
        f"""
        SELECT
            CNES, MUNIC_RES, MUNIC_MOV, PROC_REA, DIAG_PRINC,
            TRY_CAST(DIAS_PERM AS INTEGER) AS DIAS_PERM,
            DT_INTER, DT_SAIDA, ano, mes
        FROM sih
        WHERE ano = {ano_ref}
        """,
        SILVER_DATA_DIR / "sih" / "sih.parquet",
    )


def gerar_silver_ibge(con: duckdb.DuckDBPyConnection) -> None:
    """População (IBGE/SIDRA): todos os anos, código de município normalizado para 6 dígitos."""
    print("[gerar_silver_ibge] Processando IBGE/SIDRA (população)...")
    _gravar(
        con,
        """
        SELECT DISTINCT
            LEFT(municipio_codigo, 6) AS cod_mun,
            municipio_nome AS nome_mun,
            ano,
            valor AS populacao
        FROM ibge_pop
        """,
        SILVER_DATA_DIR / "ibge" / "ibge_pop.parquet",
    )


def gerar_silver() -> None:
    """Gera a camada silver inteira a partir das views bronze (data/raw/)."""
    con = conectar_datasus()
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()

    if {"cnes_eq", "cnes_lt", "cnes_pf", "cnes_sr"} <= set(tabelas):
        gerar_silver_cnes(con)
    else:
        print("[gerar_silver] Aviso: nem todas as views de CNES estão disponíveis — pulando.")

    if "sia" in tabelas and "ibge_pop" in tabelas:
        ano_ref = _ano_referencia(con)
        gerar_silver_sia(con, ano_ref)
    else:
        print(
            "[gerar_silver] Aviso: 'sia' ou 'ibge_pop' não disponível — não é possível calcular o ano de referência, pulando SIA."
        )
        ano_ref = None

    if "sih" in tabelas and ano_ref is not None:
        gerar_silver_sih(con, ano_ref)
    else:
        print(
            "[gerar_silver] Aviso: 'sih' não disponível (ou ano de referência não calculado) — pulando."
        )

    if "ibge_pop" in tabelas:
        gerar_silver_ibge(con)
    else:
        print("[gerar_silver] Aviso: 'ibge_pop' não disponível — pulando.")


if __name__ == "__main__":
    gerar_silver()
