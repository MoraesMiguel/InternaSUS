"""Validação básica dos arquivos Parquet extraídos."""

from pathlib import Path

import pyarrow.parquet as pq


class ValidacaoError(Exception):
    """Levantada quando um arquivo Parquet extraído não passa na validação básica."""


def validar_parquet(caminho: Path, linha_minima: int = 1) -> int:
    """Confirma que o Parquet abre e tem pelo menos `linha_minima` linhas.

    Retorna a contagem de linhas. Lança ValidacaoError se o arquivo estiver
    corrompido/ilegível ou não atingir a contagem mínima.
    """
    try:
        tabela = pq.read_table(caminho)
    except Exception as erro:
        raise ValidacaoError(f"Parquet ilegível/corrompido: {caminho} ({erro})") from erro

    num_linhas = tabela.num_rows
    if num_linhas < linha_minima:
        raise ValidacaoError(
            f"Parquet com {num_linhas} linha(s), esperado >= {linha_minima}: {caminho}"
        )
    return num_linhas
