"""Testes de integração reais (rede), sem mocks — não rodam por padrão.

Servem para provar que a extração funciona de fato nesta máquina antes de
considerar a etapa de Ingestão concluída. Execute com: pytest -m integration
"""

from pathlib import Path

import pytest

from internasus.ingestion import datasus, sidra


@pytest.mark.integration
def test_datasus_integration_baixa_uma_competencia_real_pequena(tmp_path: Path):
    base_dir = tmp_path / "raw"

    resultado = datasus.baixar_grupo("CNES", "LT", "SP", 2024, 2024, base_dir)

    assert resultado["falhas"] == []
    assert resultado["baixados"] > 0
    arquivos = list(base_dir.rglob("*.parquet"))
    assert arquivos
    assert all(a.stat().st_size > 0 for a in arquivos)


@pytest.mark.integration
def test_sidra_integration_consulta_tabela_real():
    df = sidra.buscar_populacao(tabela=6579, variaveis=[9324], ano_inicio=2020, ano_fim=2026)

    assert not df.empty
    assert df["municipio_codigo"].str.startswith("35").all()
