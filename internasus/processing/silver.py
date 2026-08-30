"""
internasus.processing.silver
Camada Silver: lê as views "bronze" (via conectar_datasus), aplica limpeza e
padronização básica, e grava o resultado em data/silver/<fonte>/.

Este script mantém os dados no nível de LINHA (um registro = uma linha),
ainda sem agregações — isso fica pra camada Gold (processing/gold.py).

As regras de limpeza aqui são genéricas (deduplicação, remoção de linhas
totalmente vazias, padronização de nomes de coluna). Ajuste as funções
_limpar_cnes / _limpar_sia com regras específicas do seu domínio conforme
for validando os dados (ex: CBOs válidos, faixas de data plausíveis, etc).
"""

from pathlib import Path
import duckdb
import pandas as pd

from internasus.loaders import conectar_datasus

PROJ_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_SILVER = PROJ_ROOT / "data" / "silver"


def _padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Nomes de coluna em maiúsculas e sem espaços nas pontas — padrão DATASUS."""
    df.columns = [c.strip().upper() for c in df.columns]
    return df


def _limpeza_basica(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicatas exatas e linhas 100% vazias."""
    antes = len(df)
    df = df.drop_duplicates()
    df = df.dropna(how="all")
    depois = len(df)
    if antes != depois:
        print(f"  [_limpeza_basica] Removidas {antes - depois} linha(s) duplicada(s)/vazia(s).")
    return df


def _limpar_cnes(con: duckdb.DuckDBPyConnection, dataset: str) -> pd.DataFrame:
    """
    Limpa um dataset do CNES (EQ, LT, PF, SR ou ST).
    dataset: nome da view, ex: 'cnes_pf', 'cnes_eq'
    """
    df = con.execute(f"SELECT * FROM {dataset}").df()
    df = _padronizar_colunas(df)
    df = _limpeza_basica(df)

    # TODO: adicionar regras específicas, ex:
    # - filtrar CODUFMUN válidos (não nulo, 6 ou 7 dígitos)
    # - remover linhas com QT_EXIST negativo ou não numérico

    return df


def _limpar_sia(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Limpa o dataset SIA (Sistema de Informações Ambulatoriais)."""
    df = con.execute("SELECT * FROM sia").df()
    df = _padronizar_colunas(df)
    df = _limpeza_basica(df)

    # TODO: adicionar regras específicas, ex:
    # - filtrar MUNIC_RES válidos
    # - remover PROC_REA nulos ou com formato inválido

    return df


def gerar_silver_cnes() -> None:
    """Gera a camada silver para todos os datasets do CNES disponíveis (EQ/LT/PF/SR/ST)."""
    con = conectar_datasus()
    views_cnes = [t for t in con.execute("SHOW TABLES").df()["name"].tolist() if t.startswith("cnes_")]

    if not views_cnes:
        print("[gerar_silver_cnes] Nenhuma view de CNES disponível (dados não encontrados em data/raw).")
        return

    for view in views_cnes:
        print(f"[gerar_silver_cnes] Processando {view}...")
        df = _limpar_cnes(con, view)
        destino = DATA_SILVER / "cnes" / f"{view}.parquet"
        destino.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(destino, index=False)
        print(f"  -> {destino} ({len(df)} linhas)")


def gerar_silver_sia() -> None:
    """Gera a camada silver para o SIA."""
    con = conectar_datasus()
    tabelas = con.execute("SHOW TABLES").df()["name"].tolist()

    if "sia" not in tabelas:
        print("[gerar_silver_sia] View 'sia' não disponível (dados não encontrados em data/raw).")
        return

    print("[gerar_silver_sia] Processando sia...")
    df = _limpar_sia(con)
    destino = DATA_SILVER / "sia" / "sia.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    print(f"  -> {destino} ({len(df)} linhas)")


# TODO: quando SIH e SIDRA/IBGE forem baixados, adicionar aqui:
# def gerar_silver_sih(): ...
# def gerar_silver_sidra(): ...


if __name__ == "__main__":
    gerar_silver_cnes()
    gerar_silver_sia()
