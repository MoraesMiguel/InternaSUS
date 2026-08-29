from pathlib import Path

import pandas as pd
import pytest

from internasus.ingestion.validacao import ValidacaoError, validar_parquet
from tests.conftest import escrever_parquet


def test_validar_parquet_aceita_arquivo_valido(tmp_path: Path, df_valido: pd.DataFrame):
    caminho = escrever_parquet(tmp_path / "dados.parquet", df_valido)

    num_linhas = validar_parquet(caminho)

    assert num_linhas == len(df_valido)


def test_validar_parquet_rejeita_arquivo_vazio(tmp_path: Path):
    df_vazio = pd.DataFrame({"municipio_codigo": [], "valor": []})
    caminho = escrever_parquet(tmp_path / "vazio.parquet", df_vazio)

    with pytest.raises(ValidacaoError):
        validar_parquet(caminho)


def test_validar_parquet_rejeita_arquivo_corrompido(tmp_path: Path):
    caminho = tmp_path / "corrompido.parquet"
    caminho.write_bytes(b"isto nao e um parquet valido")

    with pytest.raises(ValidacaoError):
        validar_parquet(caminho)
