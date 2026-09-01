"""CLI de ingestão de dados (README §5.1) — CNES/SIA/SIH (DataSUS) e IBGE/SIDRA."""

from loguru import logger
import typer

from internasus.config import (
    ANO_FIM,
    ANO_INICIO,
    CNES_GRUPOS,
    EXTERNAL_DATA_DIR,
    RAW_DATA_DIR,
    SIA_GRUPOS,
    SIDRA_TABELAS,
    SIH_GRUPOS,
    UF_ALVO,
)
from internasus.ingestion import cid10, datasus, sidra

app = typer.Typer()


def _finalizar(resultado: dict) -> None:
    logger.info(f"Resultado: {resultado}")
    if resultado["falhas"]:
        logger.error(f"{len(resultado['falhas'])} falha(s) durante a ingestão.")
        raise typer.Exit(code=1)


@app.command("ingest-cnes")
def ingest_cnes(
    ano_inicio: int = ANO_INICIO,
    ano_fim: int = ANO_FIM,
    uf: str = UF_ALVO,
) -> None:
    """Extrai CNES (grupos PF/EQ/LT/SR) do DATASUS para data/raw/."""
    resultado = datasus.baixar_cnes(uf, ano_inicio, ano_fim, CNES_GRUPOS, RAW_DATA_DIR)
    _finalizar(resultado)


@app.command("ingest-sia")
def ingest_sia(
    ano_inicio: int = ANO_INICIO,
    ano_fim: int = ANO_FIM,
    uf: str = UF_ALVO,
) -> None:
    """Extrai SIA (Produção Ambulatorial) do DATASUS para data/raw/."""
    resultado = datasus.baixar_sia(uf, ano_inicio, ano_fim, SIA_GRUPOS, RAW_DATA_DIR)
    _finalizar(resultado)


@app.command("ingest-sih")
def ingest_sih(
    ano_inicio: int = ANO_INICIO,
    ano_fim: int = ANO_FIM,
    uf: str = UF_ALVO,
) -> None:
    """Extrai SIH (AIH Reduzida) do DATASUS para data/raw/."""
    resultado = datasus.baixar_sih(uf, ano_inicio, ano_fim, SIH_GRUPOS, RAW_DATA_DIR)
    _finalizar(resultado)


@app.command("ingest-sidra")
def ingest_sidra(
    ano_inicio: int = ANO_INICIO,
    ano_fim: int = ANO_FIM,
) -> None:
    """Extrai dados populacionais do IBGE (API SIDRA) para data/raw/."""
    resultado = sidra.baixar_sidra(SIDRA_TABELAS, ano_inicio, ano_fim, RAW_DATA_DIR)
    _finalizar(resultado)


@app.command("ingest-cid10")
def ingest_cid10(forcar: bool = False) -> None:
    """Extrai a tabela oficial CID-10 (referência estática) para data/external/cid10/."""
    resultado = cid10.baixar_cid10(EXTERNAL_DATA_DIR, forcar=forcar)
    _finalizar(resultado)


@app.command("ingest-all")
def ingest_all(
    ano_inicio: int = ANO_INICIO,
    ano_fim: int = ANO_FIM,
    uf: str = UF_ALVO,
) -> None:
    """Executa toda a ingestão: CNES, SIA, SIH, SIDRA e CID-10, em sequência."""
    agregado = {"baixados": 0, "pulados": 0, "falhas": []}

    for nome, fn in [
        ("CNES", lambda: datasus.baixar_cnes(uf, ano_inicio, ano_fim, CNES_GRUPOS, RAW_DATA_DIR)),
        ("SIA", lambda: datasus.baixar_sia(uf, ano_inicio, ano_fim, SIA_GRUPOS, RAW_DATA_DIR)),
        ("SIH", lambda: datasus.baixar_sih(uf, ano_inicio, ano_fim, SIH_GRUPOS, RAW_DATA_DIR)),
        ("SIDRA", lambda: sidra.baixar_sidra(SIDRA_TABELAS, ano_inicio, ano_fim, RAW_DATA_DIR)),
        ("CID-10", lambda: cid10.baixar_cid10(EXTERNAL_DATA_DIR)),
    ]:
        logger.info(f"=== Ingestão: {nome} ===")
        parcial = fn()
        agregado["baixados"] += parcial["baixados"]
        agregado["pulados"] += parcial["pulados"]
        agregado["falhas"].extend(parcial["falhas"])

    _finalizar(agregado)


if __name__ == "__main__":
    app()
