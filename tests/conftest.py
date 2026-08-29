"""Fixtures compartilhadas da suíte de testes."""

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    """Diretório raiz isolado para simular data/raw/ em cada teste."""
    return tmp_path / "raw"


@pytest.fixture
def df_valido() -> pd.DataFrame:
    """DataFrame pequeno, representativo de um grupo DataSUS/SIDRA válido."""
    return pd.DataFrame(
        {
            "municipio_codigo": ["3550308", "3509502"],
            "valor": [100, 200],
        }
    )


def escrever_parquet(caminho: Path, df: pd.DataFrame) -> Path:
    """Utilitário de teste: grava um DataFrame como Parquet num caminho dado."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), caminho)
    return caminho
