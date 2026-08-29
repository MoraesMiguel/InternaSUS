from pathlib import Path

from internasus.ingestion.paths import ja_existe, pasta_datasus, pasta_sidra
from tests.conftest import escrever_parquet


def test_pasta_datasus_monta_path_hive_correto(base_dir: Path):
    pasta = pasta_datasus(base_dir, "CNES", "PF", ano=2021, mes=3)

    assert pasta == base_dir / "fonte=CNES" / "uf=SP" / "ano=2021" / "mes=03" / "dataset=PF"


def test_pasta_sidra_nao_tem_segmento_mes(base_dir: Path):
    pasta = pasta_sidra(base_dir, ano=2020, tabela=6579)

    assert pasta == base_dir / "fonte=IBGE_SIDRA" / "uf=SP" / "ano=2020" / "dataset=6579"
    assert "mes=" not in str(pasta)


def test_ja_existe_false_para_arquivo_inexistente(base_dir: Path):
    pasta = base_dir / "fonte=CNES" / "uf=SP" / "ano=2024" / "mes=01" / "dataset=PF"

    assert ja_existe(pasta / "dados.parquet") is False


def test_ja_existe_true_apos_gravar_parquet(base_dir: Path, df_valido):
    pasta = base_dir / "fonte=CNES" / "uf=SP" / "ano=2024" / "mes=01" / "dataset=PF"
    escrever_parquet(pasta / "dados.parquet", df_valido)

    assert ja_existe(pasta / "dados.parquet") is True


def test_ja_existe_false_para_outra_parte_da_mesma_particao(base_dir: Path, df_valido):
    """Uma partição (ano/mes/grupo) pode ter várias partes (ex.: SIA/PA
    quebrado em a/b/c) — a parte "a" já existir não pode marcar a "b" como
    já baixada."""
    pasta = base_dir / "fonte=SIA" / "uf=SP" / "ano=2020" / "mes=01" / "dataset=PA"
    escrever_parquet(pasta / "PASP2001a.parquet", df_valido)

    assert ja_existe(pasta / "PASP2001b.parquet") is False
