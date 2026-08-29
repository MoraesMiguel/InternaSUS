"""Construção de pastas particionadas (Hive-style) em data/raw/."""

from pathlib import Path


def pasta_datasus(base: Path, fonte: str, grupo: str, ano: int, mes: int) -> Path:
    """Monta a pasta particionada para um arquivo DataSUS (CNES/SIA/SIH).

    Layout: base/fonte=<FONTE>/uf=SP/ano=<AAAA>/mes=<MM>/dataset=<GRUPO>/
    """
    return (
        base
        / f"fonte={fonte.upper()}"
        / "uf=SP"
        / f"ano={ano:04d}"
        / f"mes={mes:02d}"
        / f"dataset={grupo.upper()}"
    )


def pasta_sidra(base: Path, ano: int, tabela: int | str) -> Path:
    """Monta a pasta particionada para um dataset SIDRA (IBGE).

    Layout: base/fonte=IBGE_SIDRA/uf=SP/ano=<AAAA>/dataset=<TABELA>/
    """
    return base / "fonte=IBGE_SIDRA" / "uf=SP" / f"ano={ano:04d}" / f"dataset={tabela}"


def ja_existe(caminho_parquet: Path) -> bool:
    """Retorna True se o arquivo .parquet de destino já existe.

    Recebe o caminho completo do arquivo (não a pasta): fontes como
    SIA/SIH podem quebrar a competência de um mês em várias partes
    (ex.: PASP2001a/b/c.dbc), cada uma virando um .parquet distinto na
    mesma pasta — checar "a pasta já tem algum .parquet" marcaria as
    partes b/c como já baixadas assim que a parte a existisse.
    """
    return caminho_parquet.exists()
