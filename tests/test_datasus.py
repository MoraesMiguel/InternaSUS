"""Testes de internasus.ingestion.datasus, com o cliente FTP totalmente mockado
(nenhuma chamada de rede real)."""

from pathlib import Path
from unittest.mock import AsyncMock

import pandas as pd

from internasus.ingestion import datasus
from tests.conftest import escrever_parquet


class FakeParquetObj:
    def __init__(self, path: Path):
        self.path = path


class FakeLocalDbc:
    def __init__(self, path: Path):
        self.path = path

    async def to_parquet(self):
        destino = self.path.with_suffix(".parquet")
        escrever_parquet(destino, pd.DataFrame({"municipio_codigo": ["3550308"], "valor": [1]}))
        return FakeParquetObj(destino)


class FakeArquivo:
    def __init__(self, basename: str, state: str, year: int, month: int, falha: bool = False):
        self.basename = basename
        self.state = state
        self.year = year
        self.month = month
        self._falha = falha

    def __str__(self) -> str:
        return self.basename

    async def download(self, output: Path):
        if self._falha:
            raise ConnectionError("falha simulada de download")
        caminho_dbc = Path(output) / self.basename
        caminho_dbc.parent.mkdir(parents=True, exist_ok=True)
        caminho_dbc.write_bytes(b"conteudo fake dbc")
        return FakeLocalDbc(caminho_dbc)


class FakeGroup:
    def __init__(self, name: str, arquivos: list):
        self.name = name
        self._arquivos = arquivos

    async def _fetch_files(self):
        return self._arquivos


class FakeGrupoRef:
    """Simula o Group referenciado por File.group (SIA/SIH: arquivo solto,
    sem subpasta por grupo — o grupo vem do próprio arquivo)."""

    def __init__(self, name: str):
        self.name = name


def _fake_dataset_factory(grupos: list):
    class FakeDataset:
        def __init__(self, client=None):
            self.client = client

        async def _fetch_content(self):
            return grupos

    return FakeDataset


def _mockar_ftp(mocker):
    """Substitui o cliente FTP por um dublê sem I/O real."""
    ftp_cls = mocker.patch("internasus.ingestion.datasus.FTP")
    instancia = ftp_cls.return_value
    instancia.connect = AsyncMock()
    instancia.close = AsyncMock()
    return ftp_cls


def test_baixar_grupo_filtra_por_uf_e_ano(mocker, base_dir: Path):
    _mockar_ftp(mocker)
    arquivos = [
        FakeArquivo("PFSP2401.dbc", state="SP", year=2024, month=1),
        FakeArquivo("PFRJ2401.dbc", state="RJ", year=2024, month=1),  # outra UF, deve ser ignorado
        FakeArquivo("PFSP2019.dbc", state="SP", year=2019, month=1),  # fora do periodo, ignorado
    ]
    mocker.patch.dict(
        datasus._DATASET_CLASSES,
        {"CNES": _fake_dataset_factory([FakeGroup("PF", arquivos)])},
    )

    resultado = datasus.baixar_grupo("CNES", "PF", "SP", 2020, 2026, base_dir)

    assert resultado["baixados"] == 1
    assert resultado["falhas"] == []
    assert (
        base_dir / "fonte=CNES" / "uf=SP" / "ano=2024" / "mes=01" / "dataset=PF" / "PFSP2401.parquet"
    ).exists()


def test_baixar_grupo_pula_particao_ja_existente(mocker, base_dir: Path, df_valido):
    _mockar_ftp(mocker)
    arquivo = FakeArquivo("PFSP2401.dbc", state="SP", year=2024, month=1)
    pasta = base_dir / "fonte=CNES" / "uf=SP" / "ano=2024" / "mes=01" / "dataset=PF"
    escrever_parquet(pasta / "PFSP2401.parquet", df_valido)

    mocker.patch.dict(
        datasus._DATASET_CLASSES,
        {"CNES": _fake_dataset_factory([FakeGroup("PF", [arquivo])])},
    )

    resultado = datasus.baixar_grupo("CNES", "PF", "SP", 2024, 2024, base_dir)

    assert resultado == {"baixados": 0, "pulados": 1, "falhas": []}


def test_baixar_grupo_arquivos_soltos_com_grupo_no_proprio_arquivo(mocker, base_dir: Path):
    """SIA/SIH não têm subpasta por grupo: dataset._fetch_content() retorna
    os arquivos direto, com o grupo exposto via File.group (não Directory.name)."""
    _mockar_ftp(mocker)
    arquivo = FakeArquivo("PASP2001a.dbc", state="SP", year=2020, month=1)
    arquivo.group = FakeGrupoRef("PA")

    mocker.patch.dict(
        datasus._DATASET_CLASSES,
        {"SIA": _fake_dataset_factory([arquivo])},
    )

    resultado = datasus.baixar_grupo("SIA", "PA", "SP", 2020, 2020, base_dir)

    assert resultado == {"baixados": 1, "pulados": 0, "falhas": []}
    assert (
        base_dir / "fonte=SIA" / "uf=SP" / "ano=2020" / "mes=01" / "dataset=PA" / "PASP2001a.parquet"
    ).exists()


def test_baixar_grupo_nao_pula_outra_parte_da_mesma_particao(mocker, base_dir: Path, df_valido):
    """Uma partição (ano/mes/grupo) pode ter várias partes distintas (ex.:
    SIA/PA quebrado em a/b/c) — a parte "a" já existir não pode fazer a "b"
    ser pulada como se já tivesse sido baixada."""
    _mockar_ftp(mocker)
    pasta = base_dir / "fonte=SIA" / "uf=SP" / "ano=2020" / "mes=01" / "dataset=PA"
    escrever_parquet(pasta / "PASP2001a.parquet", df_valido)

    arquivo_b = FakeArquivo("PASP2001b.dbc", state="SP", year=2020, month=1)
    arquivo_b.group = FakeGrupoRef("PA")

    mocker.patch.dict(
        datasus._DATASET_CLASSES,
        {"SIA": _fake_dataset_factory([arquivo_b])},
    )

    resultado = datasus.baixar_grupo("SIA", "PA", "SP", 2020, 2020, base_dir)

    assert resultado == {"baixados": 1, "pulados": 0, "falhas": []}
    assert (pasta / "PASP2001b.parquet").exists()


def test_baixar_grupo_sem_arquivos_retorna_zerado_sem_erro(mocker, base_dir: Path):
    _mockar_ftp(mocker)
    mocker.patch.dict(
        datasus._DATASET_CLASSES,
        {"CNES": _fake_dataset_factory([FakeGroup("PF", [])])},
    )

    resultado = datasus.baixar_grupo("CNES", "PF", "SP", 2024, 2024, base_dir)

    assert resultado == {"baixados": 0, "pulados": 0, "falhas": []}


def test_baixar_grupo_falha_em_um_arquivo_nao_interrompe_os_demais(mocker, base_dir: Path):
    _mockar_ftp(mocker)
    arquivos = [
        FakeArquivo("PFSP2401.dbc", state="SP", year=2024, month=1, falha=True),
        FakeArquivo("PFSP2402.dbc", state="SP", year=2024, month=2),
    ]
    mocker.patch.dict(
        datasus._DATASET_CLASSES,
        {"CNES": _fake_dataset_factory([FakeGroup("PF", arquivos)])},
    )

    resultado = datasus.baixar_grupo(
        "CNES", "PF", "SP", 2024, 2024, base_dir, tentativas=1, espera_segundos=0
    )

    assert resultado["baixados"] == 1
    assert len(resultado["falhas"]) == 1
    assert (
        base_dir / "fonte=CNES" / "uf=SP" / "ano=2024" / "mes=02" / "dataset=PF" / "PFSP2402.parquet"
    ).exists()
