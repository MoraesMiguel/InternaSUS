"""Extração de CNES/SIA/SIH do DATASUS via pysus.

Usa só o cliente FTP puro do pysus (`pysus.api.ftp`), falando direto com
ftp.datasus.gov.br, tanto para listar quanto para baixar os arquivos. A
conversão DBC -> Parquet reaproveita `BaseTabularFile.to_parquet()`
(`pysus.api.extensions`), que é uma operação puramente local (lê o DBC já
baixado e escreve o Parquet ao lado).

Deliberadamente NÃO usa o orquestrador `pysus.api.client.PySUS`/`query()`:
em testes manuais, `PySUS().query(client=FTP, ...)` retornou 0 arquivos
para uma competência que existe de fato no FTP oficial, porque essa API
consulta primeiro um catálogo "DuckLake" hospedado por terceiros (mirror
em object storage mantido pelos autores do pysus) e só filtra o resultado
por origem depois — não é o FTP em si. Ir direto ao FTP oficial do
DATASUS é mais simples e mais confiável.
"""

import asyncio
from pathlib import Path
import shutil
import tempfile

from loguru import logger
from pysus.api.ftp.client import FTP
from pysus.api.ftp.databases import CNES, SIA, SIH

from internasus.ingestion.paths import ja_existe, pasta_datasus
from internasus.ingestion.util import tentar_novamente_async
from internasus.ingestion.validacao import validar_parquet

_DATASET_CLASSES = {"CNES": CNES, "SIA": SIA, "SIH": SIH}


async def _extrair_grupo_async(
    dataset_cls: type,
    dataset_nome: str,
    grupo: str,
    uf: str,
    anos: set[int],
    base_dir: Path,
    tentativas: int,
    espera_segundos: float,
) -> dict:
    resultado: dict = {"baixados": 0, "pulados": 0, "falhas": []}

    client = FTP()
    await client.connect()
    try:
        dataset = dataset_cls(client=client)
        conteudo = await dataset._fetch_content()

        # Datasets como CNES organizam os arquivos em subpastas por grupo
        # (Group, com _fetch_files), mas SIA/SIH ficam soltos direto na
        # pasta "Dados" — o grupo vem embutido no prefixo do nome do
        # arquivo e é exposto via File.group. Os dois formatos precisam
        # ser tratados aqui (duck typing em vez de isinstance para não
        # acoplar nas classes internas do pysus).
        arquivos = []
        for item in conteudo:
            if hasattr(item, "_fetch_files"):
                if getattr(item, "name", None) == grupo:
                    arquivos.extend(await item._fetch_files())
            else:
                item_grupo = getattr(item, "group", None)
                if item_grupo is not None and getattr(item_grupo, "name", None) == grupo:
                    arquivos.append(item)
        arquivos = [f for f in arquivos if f.state == uf.upper() and f.year in anos]

        if not arquivos:
            logger.warning(
                f"Nenhum arquivo encontrado para {dataset_nome}/{grupo}/{uf} "
                f"em {min(anos)}-{max(anos)}"
            )
            return resultado

        with tempfile.TemporaryDirectory(prefix="internasus_dbc_") as tmp_dir:
            tmp_path = Path(tmp_dir)

            for arquivo in arquivos:
                pasta = pasta_datasus(base_dir, dataset_nome, grupo, arquivo.year, arquivo.month)
                nome_destino = f"{Path(arquivo.basename).stem}.parquet"
                destino = pasta / nome_destino
                if ja_existe(destino):
                    logger.info(f"Pulando (já existe): {destino}")
                    resultado["pulados"] += 1
                    continue

                async def _baixar_e_converter(arq=arquivo):
                    local_dbc = await arq.download(output=tmp_path)
                    parquet_obj = await local_dbc.to_parquet()
                    Path(local_dbc.path).unlink(missing_ok=True)
                    return parquet_obj

                try:
                    parquet_obj = await tentar_novamente_async(
                        _baixar_e_converter,
                        tentativas=tentativas,
                        espera_segundos=espera_segundos,
                    )
                    validar_parquet(parquet_obj.path)

                    pasta.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(parquet_obj.path, destino)
                    parquet_obj.path.unlink(missing_ok=True)

                    resultado["baixados"] += 1
                    logger.success(f"Gravado: {destino}")
                except Exception as erro:  # noqa: BLE001 — isola a falha deste arquivo, sem abortar os demais
                    logger.error(f"Falha ao processar {arquivo.basename}: {erro}")
                    resultado["falhas"].append(
                        {
                            "dataset": dataset_nome,
                            "grupo": grupo,
                            "arquivo": str(arquivo),
                            "erro": str(erro),
                        }
                    )
    finally:
        await client.close()

    return resultado


def baixar_grupo(
    dataset: str,
    grupo: str,
    uf: str,
    ano_inicio: int,
    ano_fim: int,
    base_dir: Path,
    tentativas: int = 3,
    espera_segundos: float = 2.0,
) -> dict:
    """Lista, baixa, converte e particiona todos os arquivos de um grupo
    DATASUS (ex.: CNES/PF) para um estado e intervalo de anos.

    Pula arquivos cuja partição de destino já existe (idempotência).
    Falha em um arquivo específico não interrompe os demais.
    """
    dataset_cls = _DATASET_CLASSES[dataset.upper()]
    anos = set(range(ano_inicio, ano_fim + 1))
    return asyncio.run(
        _extrair_grupo_async(
            dataset_cls, dataset.upper(), grupo, uf, anos, base_dir, tentativas, espera_segundos
        )
    )


def _baixar_grupos(
    dataset: str, uf: str, ano_inicio: int, ano_fim: int, grupos: list[str], base_dir: Path
) -> dict:
    """Executa baixar_grupo para uma lista de grupos, agregando o resultado."""
    agregado: dict = {"baixados": 0, "pulados": 0, "falhas": []}
    for grupo in grupos:
        logger.info(f"Iniciando {dataset}/{grupo} (UF={uf}, {ano_inicio}-{ano_fim})")
        parcial = baixar_grupo(dataset, grupo, uf, ano_inicio, ano_fim, base_dir)
        agregado["baixados"] += parcial["baixados"]
        agregado["pulados"] += parcial["pulados"]
        agregado["falhas"].extend(parcial["falhas"])
    return agregado


def baixar_cnes(uf: str, ano_inicio: int, ano_fim: int, grupos: list[str], base_dir: Path) -> dict:
    return _baixar_grupos("CNES", uf, ano_inicio, ano_fim, grupos, base_dir)


def baixar_sia(uf: str, ano_inicio: int, ano_fim: int, grupos: list[str], base_dir: Path) -> dict:
    return _baixar_grupos("SIA", uf, ano_inicio, ano_fim, grupos, base_dir)


def baixar_sih(uf: str, ano_inicio: int, ano_fim: int, grupos: list[str], base_dir: Path) -> dict:
    return _baixar_grupos("SIH", uf, ano_inicio, ano_fim, grupos, base_dir)
