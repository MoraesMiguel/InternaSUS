"""
internasus.loaders
Conexão DuckDB que expõe os parquets ingeridos em data/raw/ como views SQL.
"""

from pathlib import Path
import duckdb

PROJ_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJ_ROOT / "data" / "raw"

# Confirmados a partir da estrutura real de data/raw:
#   fonte=CNES/uf=SP/ano=YYYY/mes=MM/dataset={EQ,LT,PF,SR,ST}/*.parquet
#   fonte=SIA/uf=SP/ano=YYYY/mes=MM/dataset=PA/*.parquet
# Ainda não confirmados (SIH/SIDRA não baixados ainda) — ajuste quando existirem:
VIEWS = {
    "cnes_eq": "fonte=CNES/uf=SP/**/dataset=EQ/*.parquet",
    "cnes_lt": "fonte=CNES/uf=SP/**/dataset=LT/*.parquet",
    "cnes_pf": "fonte=CNES/uf=SP/**/dataset=PF/*.parquet",
    "cnes_sr": "fonte=CNES/uf=SP/**/dataset=SR/*.parquet",
    "cnes_st": "fonte=CNES/uf=SP/**/dataset=ST/*.parquet",
    "sia": "fonte=SIA/uf=SP/**/dataset=PA/*.parquet",
    # "sih": "fonte=SIH/uf=SP/**/dataset=???/*.parquet",   # ajustar quando baixar
    # "sidra": "fonte=SIDRA/**/*.parquet",                  # ajustar quando baixar
    # "ibge_pop": "fonte=IBGE/**/*.parquet",                # ajustar quando baixar
}


def conectar_datasus(data_raw: Path | None = None) -> duckdb.DuckDBPyConnection:
    """
    Abre uma conexão DuckDB em memória e cria uma VIEW para cada fonte de dados
    disponível em data/raw. Fontes sem parquet encontrado são puladas com aviso.
    """
    root = data_raw or DATA_RAW
    con = duckdb.connect(database=":memory:")

    for view_name, pattern in VIEWS.items():
        full_pattern = str(root / pattern)
        matches = list(root.glob(pattern))
        if not matches:
            print(f"[conectar_datasus] Aviso: nenhum parquet para '{view_name}' em {full_pattern} — pulando.")
            continue

        con.execute(f"""
            CREATE OR REPLACE VIEW {view_name} AS
            SELECT * FROM read_parquet('{full_pattern}', union_by_name=True)
        """)
        print(f"[conectar_datasus] View '{view_name}' criada ({len(matches)} arquivo(s)).")

    return con


if __name__ == "__main__":
    conn = conectar_datasus()
    print(conn.execute("SHOW TABLES").df())
